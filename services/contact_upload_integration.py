"""
Contact Upload Integration with Celery Domain Scanning
Handles automatic domain scanning after contact uploads
"""

import logging
from datetime import datetime
from typing import List, Dict, Set
from models.database import db, Contact

logger = logging.getLogger(__name__)

def trigger_domain_scanning_after_upload(uploaded_contacts: List[Dict], upload_batch_id: str = None) -> Dict:
    """
    Trigger domain scanning for newly uploaded contacts
    Automatically chooses between Celery (if available) or simple background scanner

    Args:
        uploaded_contacts: List of contact data dictionaries
        upload_batch_id: Optional batch identifier for tracking

    Returns:
        Dict with scanning task information
    """
    try:
        # Extract unique domains from uploaded contacts
        domains = extract_unique_domains_from_contacts(uploaded_contacts)

        if not domains:
            logger.info("No domains found in uploaded contacts")
            return {
                'success': True,
                'message': 'No domains to scan',
                'domains_count': 0,
                'task_id': None
            }

        # Filter out domains that were recently scanned successfully
        domains_to_scan = filter_domains_needing_scan(domains)

        if not domains_to_scan:
            logger.info(f"All {len(domains)} domains were recently scanned")
            return {
                'success': True,
                'message': f'All {len(domains)} domains already scanned recently',
                'domains_count': 0,
                'task_id': None
            }

        # Create batch ID if not provided
        if not upload_batch_id:
            upload_batch_id = f"upload_{int(datetime.utcnow().timestamp())}"

        # Try to use Celery first, fall back to simple scanner
        task_id = None
        scanner_type = "unknown"

        try:
            # Try Celery first
            try:
                from tasks.domain_scanning import scan_domain_batch
                task = scan_domain_batch.delay(domains_to_scan, upload_batch_id)
                task_id = task.id
                scanner_type = "celery"
                logger.info(f"Started Celery domain scanning for {len(domains_to_scan)} domains, task ID: {task_id}")
            except ImportError as import_error:
                raise Exception(f"Celery not available: {import_error}")

        except Exception as celery_error:
            # Fall back to simple background scanner
            logger.warning(f"Celery not available ({celery_error}), using simple background scanner")

            try:
                from services.simple_background_scanner import start_simple_scanning
                task_id = start_simple_scanning(domains_to_scan, upload_batch_id)
                scanner_type = "simple"
                logger.info(f"Started simple domain scanning for {len(domains_to_scan)} domains, task ID: {task_id}")

            except Exception as simple_error:
                logger.error(f"Both Celery and simple scanner failed: {simple_error}")
                return {
                    'success': False,
                    'error': f'Failed to start scanning: {simple_error}',
                    'domains_count': 0,
                    'task_id': None
                }

        return {
            'success': True,
            'message': f'Started scanning {len(domains_to_scan)} domains using {scanner_type} backend',
            'domains_count': len(domains_to_scan),
            'total_domains': len(domains),
            'already_scanned': len(domains) - len(domains_to_scan),
            'task_id': task_id,
            'batch_id': upload_batch_id,
            'estimated_duration_minutes': estimate_scan_duration(len(domains_to_scan)),
            'scanner_type': scanner_type
        }

    except Exception as e:
        logger.error(f"Error triggering domain scanning: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'domains_count': 0,
            'task_id': None
        }

def extract_unique_domains_from_contacts(contacts: List[Dict]) -> List[str]:
    """
    Extract unique domains from contact data

    Args:
        contacts: List of contact dictionaries

    Returns:
        List of unique domain names
    """
    domains = set()

    for contact in contacts:
        email = contact.get('email', '').strip().lower()
        if email and '@' in email:
            domain = email.split('@')[1]
            domains.add(domain)

    return sorted(list(domains))

def filter_domains_needing_scan(domains: List[str]) -> List[str]:
    """
    Filter domains that need scanning (haven't been scanned recently)

    Args:
        domains: List of domain names

    Returns:
        List of domains that need scanning
    """
    try:
        from models.database import Breach
        from datetime import timedelta

        # Consider domains scanned recently if completed within last 24 hours
        recent_scan_threshold = datetime.utcnow() - timedelta(hours=24)

        # Get domains that were scanned recently and successfully
        recently_scanned = db.session.query(Breach.domain).filter(
            Breach.domain.in_(domains),
            Breach.scan_status == 'completed',
            Breach.last_updated >= recent_scan_threshold
        ).all()

        recently_scanned_domains = {row[0] for row in recently_scanned}

        # Return domains that need scanning
        domains_to_scan = [domain for domain in domains if domain not in recently_scanned_domains]

        logger.info(f"Filtered {len(domains)} domains: {len(domains_to_scan)} need scanning, {len(recently_scanned_domains)} recently scanned")

        return domains_to_scan

    except Exception as e:
        logger.error(f"Error filtering domains: {str(e)}")
        # If filtering fails, scan all domains to be safe
        return domains

def estimate_scan_duration(domain_count: int) -> float:
    """
    Estimate scanning duration in minutes

    Args:
        domain_count: Number of domains to scan

    Returns:
        Estimated duration in minutes
    """
    if domain_count == 0:
        return 0

    # Each domain takes ~30 seconds to scan + 30 seconds delay between scans
    # First domain: 30 seconds
    # Subsequent domains: 30 seconds scan + 30 seconds delay = 60 seconds each

    if domain_count == 1:
        return 0.5  # 30 seconds
    else:
        return 0.5 + (domain_count - 1) * 1.0  # 30s + (n-1) * 60s

def get_upload_scan_status(upload_batch_id: str) -> Dict:
    """
    Get scan status for a specific upload batch

    Args:
        upload_batch_id: Batch identifier

    Returns:
        Dict with scan status information
    """
    try:
        from models.database import Breach
        from celery.result import AsyncResult
        from celery_app import celery_app

        # Get domains associated with this batch
        batch_domains = db.session.query(Breach.domain).filter(
            Breach.batch_id == upload_batch_id
        ).all()

        if not batch_domains:
            return {
                'success': False,
                'message': 'Upload batch not found',
                'batch_id': upload_batch_id
            }

        domains = [row[0] for row in batch_domains]

        # Get scan results for these domains
        scan_results = db.session.query(Breach).filter(
            Breach.domain.in_(domains)
        ).all()

        # Calculate statistics
        total_domains = len(domains)
        completed_scans = len([r for r in scan_results if r.scan_status == 'completed'])
        failed_scans = len([r for r in scan_results if r.scan_status == 'failed'])
        pending_scans = total_domains - completed_scans - failed_scans

        # Calculate breach statistics
        breached_domains = len([r for r in scan_results if r.breach_status == 'breached'])
        clean_domains = len([r for r in scan_results if r.breach_status == 'not_breached'])

        return {
            'success': True,
            'batch_id': upload_batch_id,
            'total_domains': total_domains,
            'completed_scans': completed_scans,
            'failed_scans': failed_scans,
            'pending_scans': pending_scans,
            'progress_percentage': int((completed_scans + failed_scans) / total_domains * 100) if total_domains > 0 else 100,
            'breach_statistics': {
                'breached_domains': breached_domains,
                'clean_domains': clean_domains,
                'breach_rate': round(breached_domains / max(completed_scans, 1) * 100, 1)
            },
            'is_complete': pending_scans == 0
        }

    except Exception as e:
        logger.error(f"Error getting upload scan status: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'batch_id': upload_batch_id
        }

def update_contact_upload_with_scanning_info(upload_response: Dict, scan_info: Dict) -> Dict:
    """
    Combine upload response with scanning information

    Args:
        upload_response: Original upload response
        scan_info: Domain scanning information

    Returns:
        Combined response with scanning details
    """
    if scan_info['success']:
        upload_response['domain_scanning'] = {
            'enabled': True,
            'task_id': scan_info.get('task_id'),
            'batch_id': scan_info.get('batch_id'),
            'domains_count': scan_info.get('domains_count', 0),
            'estimated_duration_minutes': scan_info.get('estimated_duration_minutes', 0),
            'message': scan_info.get('message', 'Domain scanning started')
        }
    else:
        upload_response['domain_scanning'] = {
            'enabled': False,
            'error': scan_info.get('error', 'Unknown error'),
            'message': 'Domain scanning failed to start'
        }

    return upload_response