"""
Celery tasks for FlawTrack domain scanning
Handles background scanning with rate limiting and retry logic
"""

import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from celery import current_task
from celery.exceptions import Retry

# Import Celery app
from celery_app import celery_app

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def scan_domain_batch(self, domains: List[str], upload_batch_id: str = None) -> Dict:
    """
    Scan multiple domains with 30-second delays between scans

    Args:
        domains: List of domain names to scan
        upload_batch_id: Optional batch identifier for tracking

    Returns:
        Dict with scan results and statistics
    """
    logger.info(f"Starting batch scan of {len(domains)} domains")

    results = {
        'batch_id': upload_batch_id,
        'domains_processed': 0,
        'domains_successful': 0,
        'domains_failed': 0,
        'total_domains': len(domains),
        'scan_results': {},
        'errors': []
    }

    try:
        for i, domain in enumerate(domains):
            try:
                logger.info(f"Processing domain {i+1}/{len(domains)}: {domain}")

                # Update task progress
                if current_task:
                    current_task.update_state(
                        state='PROGRESS',
                        meta={
                            'current_domain': domain,
                            'completed': i,
                            'total': len(domains),
                            'progress': int((i / len(domains)) * 100)
                        }
                    )

                # Scan individual domain
                scan_result = scan_single_domain.delay(domain, upload_batch_id)

                # Wait for result (with timeout)
                domain_result = scan_result.get(timeout=120)  # 2 minutes timeout

                if domain_result['success']:
                    results['domains_successful'] += 1
                    results['scan_results'][domain] = domain_result
                    logger.info(f"Successfully scanned {domain}")
                else:
                    results['domains_failed'] += 1
                    results['errors'].append(f"{domain}: {domain_result.get('error', 'Unknown error')}")
                    logger.error(f"Failed to scan {domain}: {domain_result.get('error')}")

                results['domains_processed'] += 1

                # 30-second delay between scans (except for the last domain)
                if i < len(domains) - 1:
                    logger.info(f"Waiting 30 seconds before next scan...")
                    time.sleep(30)

            except Exception as domain_error:
                results['domains_failed'] += 1
                results['domains_processed'] += 1
                error_msg = f"Error processing {domain}: {str(domain_error)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)

                # Continue with next domain even if one fails
                continue

        logger.info(f"Batch scan completed: {results['domains_successful']}/{results['total_domains']} successful")
        return results

    except Exception as e:
        error_msg = f"Batch scan failed: {str(e)}"
        logger.error(error_msg)

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying batch scan in 5 minutes (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=300, exc=e)

        results['errors'].append(error_msg)
        return results

@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def scan_single_domain(self, domain: str, upload_batch_id: str = None) -> Dict:
    """
    Scan a single domain using FlawTrack API

    Args:
        domain: Domain name to scan
        upload_batch_id: Optional batch identifier for tracking

    Returns:
        Dict with scan result and breach data
    """
    logger.info(f"Scanning domain: {domain}")

    result = {
        'domain': domain,
        'success': False,
        'scan_timestamp': datetime.utcnow().isoformat(),
        'batch_id': upload_batch_id,
        'breach_data': None,
        'contacts_updated': 0,
        'error': None
    }

    try:
        # Import here to avoid circular imports
        from app import create_app
        from models.database import db, Contact, Breach
        from services.flawtrack_service import create_flawtrack_service

        # Create app context for database operations
        app = create_app()
        with app.app_context():

            # Check if FlawTrack scanning is enabled
            flawtrack_enabled = app.config.get('FLAWTRACK_SCANNING_ENABLED', True)
            if not flawtrack_enabled:
                logger.info(f"FlawTrack scanning disabled, simulating scan for {domain}")
                return simulate_domain_scan(domain, upload_batch_id)

            # Get FlawTrack service
            flawtrack_service = create_flawtrack_service()

            # Perform the actual scan
            logger.info(f"Calling FlawTrack API for domain: {domain}")
            scan_response = flawtrack_service.scan_domain(domain)

            if scan_response['success']:
                breach_data = scan_response['data']

                # Update or create Breach record
                breach_record = Breach.query.filter_by(domain=domain).first()
                if not breach_record:
                    breach_record = Breach(domain=domain)
                    db.session.add(breach_record)

                # Update breach record with scan results
                breach_record.scan_status = 'completed'
                breach_record.last_updated = datetime.utcnow()
                breach_record.breach_data = breach_data

                if breach_data and breach_data.get('is_breached'):
                    breach_record.breach_status = 'breached'
                    breach_record.risk_score = breach_data.get('risk_score', 7.0)
                    breach_record.records_affected = breach_data.get('records_affected', 0)
                    breach_record.breach_name = breach_data.get('breach_name', f"{domain} Security Incident")
                    breach_record.data_types = breach_data.get('data_types', 'Email addresses, credentials')
                else:
                    breach_record.breach_status = 'not_breached'
                    breach_record.risk_score = 0.0

                # Update all contacts from this domain
                contacts = Contact.query.filter_by(domain=domain).all()
                contacts_updated = 0

                for contact in contacts:
                    if breach_data and breach_data.get('is_breached'):
                        contact.breach_status = 'breached'
                        contact.risk_score = breach_data.get('risk_score', 7.0)
                    else:
                        contact.breach_status = 'not_breached'
                        contact.risk_score = 0.0

                    contacts_updated += 1

                db.session.commit()

                result.update({
                    'success': True,
                    'breach_data': breach_data,
                    'contacts_updated': contacts_updated,
                    'breach_status': breach_record.breach_status
                })

                logger.info(f"Successfully scanned {domain}, updated {contacts_updated} contacts")

            else:
                error_msg = scan_response.get('error', 'Unknown FlawTrack API error')
                result['error'] = error_msg
                logger.error(f"FlawTrack scan failed for {domain}: {error_msg}")

                # Update breach record to show failed scan
                breach_record = Breach.query.filter_by(domain=domain).first()
                if not breach_record:
                    breach_record = Breach(domain=domain)
                    db.session.add(breach_record)

                breach_record.scan_status = 'failed'
                breach_record.scan_error = error_msg
                breach_record.scan_attempts = (breach_record.scan_attempts or 0) + 1
                breach_record.last_scan_attempt = datetime.utcnow()

                db.session.commit()

        return result

    except Exception as e:
        error_msg = f"Error scanning domain {domain}: {str(e)}"
        result['error'] = error_msg
        logger.error(error_msg)

        # Retry logic
        if self.request.retries < self.max_retries:
            retry_delay = 300 * (2 ** self.request.retries)  # Exponential backoff
            logger.info(f"Retrying {domain} scan in {retry_delay} seconds (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=retry_delay, exc=e)

        return result

def simulate_domain_scan(domain: str, upload_batch_id: str = None) -> Dict:
    """
    Simulate domain scan when FlawTrack is disabled (for testing)
    """
    logger.info(f"Simulating scan for domain: {domain}")

    # Import here to avoid circular imports
    from app import create_app
    from models.database import db, Contact, Breach
    import random

    app = create_app()
    with app.app_context():

        # Simulate scan result (random for testing)
        is_breached = random.choice([True, False])

        # Update or create Breach record
        breach_record = Breach.query.filter_by(domain=domain).first()
        if not breach_record:
            breach_record = Breach(domain=domain)
            db.session.add(breach_record)

        breach_record.scan_status = 'completed'
        breach_record.last_updated = datetime.utcnow()

        if is_breached:
            breach_record.breach_status = 'breached'
            breach_record.risk_score = random.uniform(6.0, 9.0)
            breach_record.records_affected = random.randint(1000, 50000)
            breach_record.breach_name = f"{domain} Simulated Breach"
            breach_record.data_types = "Email addresses, passwords"
        else:
            breach_record.breach_status = 'not_breached'
            breach_record.risk_score = 0.0

        # Update contacts
        contacts = Contact.query.filter_by(domain=domain).all()
        contacts_updated = 0

        for contact in contacts:
            if is_breached:
                contact.breach_status = 'breached'
                contact.risk_score = breach_record.risk_score
            else:
                contact.breach_status = 'not_breached'
                contact.risk_score = 0.0
            contacts_updated += 1

        db.session.commit()

        return {
            'domain': domain,
            'success': True,
            'scan_timestamp': datetime.utcnow().isoformat(),
            'batch_id': upload_batch_id,
            'breach_data': {
                'is_breached': is_breached,
                'risk_score': breach_record.risk_score,
                'breach_name': breach_record.breach_name if is_breached else None
            },
            'contacts_updated': contacts_updated,
            'breach_status': breach_record.breach_status,
            'simulated': True
        }

@celery_app.task
def cleanup_old_scan_results():
    """
    Cleanup old scan results and failed tasks
    Run this periodically to maintain database health
    """
    logger.info("Cleaning up old scan results...")

    try:
        from app import create_app
        from models.database import db, Breach

        app = create_app()
        with app.app_context():

            # Remove old failed scan records (older than 30 days)
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            old_failed_scans = Breach.query.filter(
                Breach.scan_status == 'failed',
                Breach.last_scan_attempt < cutoff_date
            ).all()

            for breach in old_failed_scans:
                db.session.delete(breach)

            db.session.commit()

            logger.info(f"Cleaned up {len(old_failed_scans)} old failed scan records")

    except Exception as e:
        logger.error(f"Error cleaning up old scan results: {str(e)}")

# Task for extracting unique domains from uploaded contacts
@celery_app.task
def extract_domains_from_upload(contact_data: List[Dict]) -> List[str]:
    """
    Extract unique domains from uploaded contact data

    Args:
        contact_data: List of contact dictionaries with email addresses

    Returns:
        List of unique domain names
    """
    domains = set()

    for contact in contact_data:
        email = contact.get('email', '').strip().lower()
        if email and '@' in email:
            domain = email.split('@')[1]
            domains.add(domain)

    unique_domains = list(domains)
    logger.info(f"Extracted {len(unique_domains)} unique domains from {len(contact_data)} contacts")

    return unique_domains