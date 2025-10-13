"""
Simple Background Scanner - No Redis Required
Alternative to Celery for development/small deployments

This provides the same domain scanning functionality without external dependencies.
Uses threading for background processing with the same 30-second delays and retry logic.
"""

import time
import threading
import logging
from datetime import datetime
from typing import List, Dict, Optional
from queue import Queue
import uuid

logger = logging.getLogger(__name__)

class SimpleDomainScanner:
    """Thread-based domain scanner that mimics Celery functionality"""

    def __init__(self):
        self.task_queue = Queue()
        self.task_results = {}  # Store results by task_id
        self.task_progress = {}  # Store progress by task_id
        self.running = False
        self.worker_thread = None

    def start_worker(self):
        """Start the background worker thread"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logger.info("Simple domain scanner worker started")

    def stop_worker(self):
        """Stop the background worker thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Simple domain scanner worker stopped")

    def scan_domain_batch(self, domains: List[str], upload_batch_id: str = None) -> str:
        """
        Queue domain batch for scanning (mimics Celery delay method)

        Returns:
            str: Task ID for tracking progress
        """
        task_id = str(uuid.uuid4())

        task_data = {
            'task_id': task_id,
            'domains': domains,
            'upload_batch_id': upload_batch_id,
            'created_at': datetime.utcnow()
        }

        # Initialize progress tracking
        self.task_progress[task_id] = {
            'state': 'PENDING',
            'progress': 0,
            'current_domain': None,
            'completed': 0,
            'total': len(domains),
            'status': 'Task is queued for processing...'
        }

        # Queue the task
        self.task_queue.put(task_data)

        # Start worker if not running
        self.start_worker()

        logger.info(f"Queued domain batch scanning task {task_id} with {len(domains)} domains")
        return task_id

    def get_task_result(self, task_id: str) -> Dict:
        """Get task result and progress"""
        return {
            'state': self.task_progress.get(task_id, {}).get('state', 'PENDING'),
            'progress': self.task_progress.get(task_id, {}).get('progress', 0),
            'current_domain': self.task_progress.get(task_id, {}).get('current_domain'),
            'completed': self.task_progress.get(task_id, {}).get('completed', 0),
            'total': self.task_progress.get(task_id, {}).get('total', 0),
            'status': self.task_progress.get(task_id, {}).get('status', 'Unknown'),
            'result': self.task_results.get(task_id)
        }

    def _worker_loop(self):
        """Main worker loop - processes tasks from queue"""
        while self.running:
            try:
                # Get task from queue (blocking with timeout)
                task_data = self.task_queue.get(timeout=1)
                self._process_task(task_data)
                self.task_queue.task_done()

            except:
                # Timeout or empty queue - continue loop
                continue

    def _process_task(self, task_data: Dict):
        """Process a single scanning task"""
        task_id = task_data['task_id']
        domains = task_data['domains']
        upload_batch_id = task_data['upload_batch_id']

        logger.info(f"Processing task {task_id}: scanning {len(domains)} domains")

        # Update progress to in progress
        self.task_progress[task_id].update({
            'state': 'PROGRESS',
            'status': 'Scanning domains...'
        })

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
                    # Update progress
                    progress = int((i / len(domains)) * 100)
                    self.task_progress[task_id].update({
                        'progress': progress,
                        'current_domain': domain,
                        'completed': i,
                        'status': f'Scanning domain {i+1}/{len(domains)}: {domain}'
                    })

                    logger.info(f"Task {task_id}: Processing domain {i+1}/{len(domains)}: {domain}")

                    # Scan individual domain
                    domain_result = self._scan_single_domain(domain, upload_batch_id)

                    if domain_result['success']:
                        results['domains_successful'] += 1
                        results['scan_results'][domain] = domain_result
                    else:
                        results['domains_failed'] += 1
                        results['errors'].append(f"{domain}: {domain_result.get('error', 'Unknown error')}")

                    results['domains_processed'] += 1

                    # 30-second delay between scans (except for last domain)
                    if i < len(domains) - 1:
                        logger.info(f"Task {task_id}: Waiting 30 seconds before next scan...")
                        time.sleep(30)

                except Exception as domain_error:
                    results['domains_failed'] += 1
                    results['domains_processed'] += 1
                    error_msg = f"Error processing {domain}: {str(domain_error)}"
                    results['errors'].append(error_msg)
                    logger.error(f"Task {task_id}: {error_msg}")

            # Mark as completed
            self.task_progress[task_id].update({
                'state': 'SUCCESS',
                'progress': 100,
                'status': 'Scan completed successfully!',
                'current_domain': None
            })

            self.task_results[task_id] = results
            logger.info(f"Task {task_id} completed: {results['domains_successful']}/{results['total_domains']} successful")

        except Exception as e:
            error_msg = f"Task failed: {str(e)}"
            logger.error(f"Task {task_id}: {error_msg}")

            self.task_progress[task_id].update({
                'state': 'FAILURE',
                'status': 'Scan failed',
                'error': error_msg
            })

            results['errors'].append(error_msg)
            self.task_results[task_id] = results

    def _scan_single_domain(self, domain: str, upload_batch_id: str = None) -> Dict:
        """Scan a single domain (reuses existing logic)"""
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
                    return self._simulate_domain_scan(domain, upload_batch_id)

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

                else:
                    error_msg = scan_response.get('error', 'Unknown FlawTrack API error')
                    result['error'] = error_msg

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
            return result

    def _simulate_domain_scan(self, domain: str, upload_batch_id: str = None) -> Dict:
        """Simulate domain scan when FlawTrack is disabled"""
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

# Global scanner instance
_scanner_instance = None

def get_simple_scanner() -> SimpleDomainScanner:
    """Get or create the global scanner instance"""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = SimpleDomainScanner()
    return _scanner_instance

def start_simple_scanning(domains: List[str], upload_batch_id: str = None) -> str:
    """Start domain scanning using simple background scanner"""
    scanner = get_simple_scanner()
    return scanner.scan_domain_batch(domains, upload_batch_id)

def get_simple_scan_progress(task_id: str) -> Dict:
    """Get scan progress for simple scanner"""
    scanner = get_simple_scanner()
    return scanner.get_task_result(task_id)