"""
Background scanning service for processing contact uploads without blocking the user interface.
Handles breach scanning in the background with progress tracking.
"""
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from flask import current_app
from models.database import db, Contact
from services.flawtrack_api import FlawTrackAPI
from models.database import Settings
import logging
import os

logger = logging.getLogger(__name__)

class BackgroundScanner:
    """Background scanning service for contact breach analysis"""
    
    def __init__(self):
        self.active_jobs = {}
        self.job_results = {}
        self.cleanup_interval = 3600  # Clean up completed jobs after 1 hour
        
    def start_background_scan(self, contact_ids: List[int], campaign_preferences: Dict = None, job_id: str = None) -> str:
        """
        Start a background scan job for the given contact IDs
        
        Args:
            contact_ids: List of contact IDs to scan
            campaign_preferences: Dict with breached_campaign_id and/or secure_campaign_id
            job_id: Optional job ID, will generate one if not provided
            
        Returns:
            str: Job ID for tracking progress
        """
        from flask import current_app
        
        if job_id is None:
            job_id = str(uuid.uuid4())
        
        # Initialize job tracking
        self.active_jobs[job_id] = {
            'status': 'starting',
            'progress': 0,
            'total_contacts': len(contact_ids),
            'scanned_contacts': 0,
            'current_domain': '',
            'message': 'Initializing scan...',
            'started_at': datetime.utcnow(),
            'contact_ids': contact_ids,
            'campaign_preferences': campaign_preferences or {},
            'results': {
                'domains_scanned': 0,
                'breached_domains': 0,
                'secure_domains': 0,
                'unknown_domains': 0,
                'contacts_updated': 0
            }
        }
        
        # Get current app for the thread
        app = current_app._get_current_object()
        
        # Start background thread with app reference
        thread = threading.Thread(target=self._run_scan_job, args=(job_id, app))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started background scan job {job_id} for {len(contact_ids)} contacts")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get current status of a background job"""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id].copy()
            # Calculate elapsed time
            elapsed = (datetime.utcnow() - job['started_at']).total_seconds()
            job['elapsed_seconds'] = int(elapsed)
            return job
        elif job_id in self.job_results:
            return self.job_results[job_id]
        else:
            return None
    
    def cleanup_old_jobs(self):
        """Clean up old completed jobs"""
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.cleanup_interval)
        
        # Clean up completed jobs
        jobs_to_remove = []
        for job_id, job_data in self.job_results.items():
            if job_data.get('completed_at', datetime.utcnow()) < cutoff_time:
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.job_results[job_id]
            logger.info(f"Cleaned up old job {job_id}")
    
    def _run_scan_job(self, job_id: str, app):
        """Run the actual scanning job in background thread"""
        job = self.active_jobs[job_id]

        try:
            logger.info(f"Background scanner: Starting scan job {job_id}")
            # Check if FlawTrack scanning is disabled
            scanning_enabled = os.environ.get('FLAWTRACK_SCANNING_ENABLED', 'true').lower() == 'true'
            
            if not scanning_enabled:
                # Skip scanning entirely - only update contacts that were supposed to be scanned
                job['status'] = 'running'
                job['message'] = 'FlawTrack scanning disabled - setting scannable contacts to unknown status...'
                job['progress'] = 10

                contact_ids = job['contact_ids']

                with app.app_context():
                    # Only update contacts with 'unassigned' status (those that should be scanned)
                    # Leave risky/bounced contacts from email validation alone
                    updated_count = db.session.query(Contact).filter(
                        Contact.id.in_(contact_ids),
                        Contact.breach_status == 'unassigned'  # Only update contacts marked for scanning
                    ).update(
                        {Contact.breach_status: 'unknown'},
                        synchronize_session=False
                    )

                    # Get total contacts for reporting
                    total_contacts = db.session.query(Contact).filter(Contact.id.in_(contact_ids)).count()
                    skipped_contacts = total_contacts - updated_count

                    db.session.commit()
                    
                    job['status'] = 'completed'
                    job['progress'] = 100
                    job['message'] = f'Scanning disabled - {updated_count} scannable contacts set to unknown, {skipped_contacts} risky/bounced contacts preserved'
                    job['results']['contacts_updated'] = updated_count
                    job['results']['unknown_domains'] = len(set(
                        Contact.query.filter(Contact.id.in_(contact_ids)).with_entities(Contact.domain).distinct().all()
                    ))
                    
                    logger.info(f"FlawTrack scanning disabled - set {updated_count} contacts to unknown status")
                    
                    # Trigger auto-enrollment with campaign preferences
                    domain_to_contacts = {}
                    contacts = Contact.query.filter(Contact.id.in_(contact_ids)).all()
                    for contact in contacts:
                        if contact.domain not in domain_to_contacts:
                            domain_to_contacts[contact.domain] = []
                        domain_to_contacts[contact.domain].append(contact)
                    
                    self._trigger_auto_enrollment(job_id, domain_to_contacts)
                    
                self._move_job_to_results(job_id)
                return
            
            # Original scanning logic continues...
            # Update job status
            job['status'] = 'running'
            job['message'] = 'Loading contacts...'
            job['progress'] = 5
            
            # Get contacts and extract unique domains
            contact_ids = job['contact_ids']
            
            # Load contacts from database with app context
            logger.info(f"Background scanner: Loading contacts for job {job_id}")
            with app.app_context():
                logger.info(f"Background scanner: In app context for job {job_id}")
                contacts = Contact.query.filter(Contact.id.in_(contact_ids)).all()
                logger.info(f"Background scanner: Loaded {len(contacts)} contacts for job {job_id}")
                
                # Extract unique domains
                unique_domains = set()
                domain_to_contacts = {}
                
                for contact in contacts:
                    if contact.domain:
                        unique_domains.add(contact.domain)
                        if contact.domain not in domain_to_contacts:
                            domain_to_contacts[contact.domain] = []
                        domain_to_contacts[contact.domain].append(contact)
                
                total_domains = len(unique_domains)
                job['results']['total_domains'] = total_domains
                
                if total_domains == 0:
                    job['status'] = 'completed'
                    job['message'] = 'No domains to scan'
                    job['progress'] = 100
                    self._move_job_to_results(job_id)
                    return
                
                # Initialize FlawTrack API
                job['message'] = 'Initializing breach scanner...'
                job['progress'] = 10
                
                # Get API key from environment variables first, then fall back to Settings
                api_key = os.environ.get('FLAWTRACK_API_TOKEN') or Settings.get_setting('flawtrack_api_key', '')
                endpoint = os.environ.get('FLAWTRACK_API_ENDPOINT') or Settings.get_setting('flawtrack_endpoint', 'https://app-api.flawtrack.com/leaks/demo/credentials/')
                
                # Determine if we're in demo mode
                # Use real API if valid key is available, otherwise demo mode
                demo_mode = not api_key or api_key.startswith('your-') or api_key == 'your-flawtrack-api-key-here'
                
                if demo_mode:
                    job['message'] = 'Running in demo mode - using simulated data'
                    self._run_demo_scan(job_id, unique_domains, domain_to_contacts, app)
                else:
                    job['message'] = 'Connecting to FlawTrack API...'
                    self._run_real_scan(job_id, unique_domains, domain_to_contacts, api_key, endpoint, app)
                    
        except Exception as e:
            logger.error(f"Background scan job {job_id} failed: {str(e)}")
            job['status'] = 'error'
            job['message'] = f'Scan failed: {str(e)}'
            job['progress'] = 0
            self._move_job_to_results(job_id)
    
    def _run_demo_scan(self, job_id: str, domains: set, domain_to_contacts: dict, app):
        """Run a demo scan with simulated data"""
        job = self.active_jobs[job_id]
        total_domains = len(domains)
        
        with app.app_context():
            for i, domain in enumerate(domains, 1):
                # Update progress
                progress = 10 + (i / total_domains) * 80  # 10-90% range
                job['progress'] = int(progress)
                job['current_domain'] = domain
                job['message'] = f'Scanning {domain} for breaches... ({i}/{total_domains})'
                
                # Simulate scanning delay
                time.sleep(0.2)  # Short delay for demo
                
                # Generate demo breach data
                breach_data = self._generate_demo_breach_data(domain)
                
                # Update contacts for this domain
                contacts_in_domain = domain_to_contacts.get(domain, [])
                for contact in contacts_in_domain:
                    old_status = contact.breach_status
                    contact.breach_status = breach_data['breach_status']

                    # If breach status changed, trigger auto-enrollment
                    if old_status != contact.breach_status:
                        try:
                            from services.auto_enrollment import AutoEnrollmentService
                            auto_service = AutoEnrollmentService(db)
                            enrolled_campaigns = auto_service.check_breach_status_campaigns(contact.id)
                            if enrolled_campaigns > 0:
                                logger.info(f"Demo mode: Auto-enrolled {contact.email} into {enrolled_campaigns} campaigns")
                        except Exception as e:
                            logger.error(f"Demo mode: Failed to auto-enroll {contact.email}: {str(e)}")
                
                # Update job results
                if breach_data['breach_status'] == 'breached':
                    job['results']['breached_domains'] += 1
                elif breach_data['breach_status'] == 'not_breached':
                    job['results']['secure_domains'] += 1
                else:
                    job['results']['unknown_domains'] += 1
                
                job['results']['domains_scanned'] += 1
                job['results']['contacts_updated'] += len(contacts_in_domain)
            
            # Commit all changes
            db.session.commit()
            
            # Complete the job
            job['status'] = 'completed'
            job['progress'] = 100
            job['message'] = f'Scan completed! {total_domains} domains processed in demo mode'
            
            # Trigger auto-enrollment
            self._trigger_auto_enrollment(job_id, domain_to_contacts)
            
            self._move_job_to_results(job_id)
    
    def _run_real_scan(self, job_id: str, domains: set, domain_to_contacts: dict, api_key: str, endpoint: str, app):
        """Run a real scan using FlawTrack API"""
        job = self.active_jobs[job_id]
        total_domains = len(domains)
        
        with app.app_context():
            try:
                flawtrack = FlawTrackAPI(api_key, endpoint)
                
                for i, domain in enumerate(domains, 1):
                    # Update progress
                    progress = 10 + (i / total_domains) * 80  # 10-90% range
                    job['progress'] = int(progress)
                    job['current_domain'] = domain
                    job['message'] = f'Scanning {domain} for breaches... ({i}/{total_domains})'
                    
                    # Check domain scanning status and handle retries
                    from models.database import Breach
                    from datetime import datetime, timedelta
                    
                    existing_breach = Breach.query.filter_by(domain=domain).first()
                    
                    # Check if scan completed successfully in last 24 hours
                    recent_successful_scan = (existing_breach and 
                                            existing_breach.scan_status == 'completed' and
                                            existing_breach.last_updated and 
                                            (datetime.utcnow() - existing_breach.last_updated) < timedelta(hours=24))
                    
                    # Check if we should retry failed scans (max 3 attempts, wait 1 hour between attempts)
                    should_retry = (existing_breach and 
                                  existing_breach.scan_status == 'failed' and
                                  existing_breach.scan_attempts < 3 and
                                  (not existing_breach.last_scan_attempt or 
                                   (datetime.utcnow() - existing_breach.last_scan_attempt) > timedelta(hours=1)))
                    
                    if recent_successful_scan:
                        # Use cached data from recent scan
                        logger.info(f"Using cached breach data for {domain} (last updated: {existing_breach.last_updated})")
                        if existing_breach.records_affected and existing_breach.records_affected > 0:
                            processed_data = {
                                'domain': domain,
                                'breach_status': 'breached',
                                'records_affected': existing_breach.records_affected,
                                'breach_year': existing_breach.breach_year
                            }
                        else:
                            processed_data = {
                                'domain': domain, 
                                'breach_status': 'not_breached',
                                'records_affected': 0
                            }
                    elif not existing_breach or should_retry or existing_breach.scan_status in ['not_scanned', 'failed']:
                        # Need to scan: new domain, retry failed scan, or never scanned
                        
                        # Create or update breach record to mark as scanning
                        if not existing_breach:
                            existing_breach = Breach(domain=domain)
                            db.session.add(existing_breach)
                        
                        existing_breach.scan_status = 'scanning'
                        existing_breach.last_scan_attempt = datetime.utcnow()
                        existing_breach.scan_attempts = (existing_breach.scan_attempts or 0) + 1
                        db.session.commit()
                        
                        logger.info(f"Scanning {domain} for breaches (attempt {existing_breach.scan_attempts})...")
                        
                        # Get fresh breach data from API
                        breach_data = flawtrack.get_breach_data(domain)
                        
                        if breach_data is not None:
                            # Process the breach data
                            processed_data = flawtrack.process_breach_data(domain, breach_data)
                            
                            # Mark scan as completed
                            existing_breach.scan_status = 'completed'
                            existing_breach.scan_error = None
                            existing_breach.last_updated = datetime.utcnow()
                            
                            # Cache breach data in database
                            flawtrack.cache_breach_data(domain, processed_data)
                            
                            logger.info(f"Successfully scanned {domain} - Status: {processed_data['breach_status']}")
                        else:
                            # API failed - mark as failed for retry
                            existing_breach.scan_status = 'failed'
                            existing_breach.scan_error = f"FlawTrack API failed on attempt {existing_breach.scan_attempts}"
                            db.session.commit()
                            
                            logger.warning(f"Scan failed for {domain} (attempt {existing_breach.scan_attempts})")
                            
                            processed_data = {
                                'domain': domain,
                                'breach_status': 'unknown',
                                'records_affected': 0
                            }
                    else:
                        # Use cached data from previous scan (domain already scanned successfully)
                        logger.info(f"Using cached breach data for {domain} (scan status: {existing_breach.scan_status}, last scanned: {existing_breach.last_scan_attempt})")

                        # If domain was successfully scanned before, use cached breach status
                        if existing_breach.scan_status == 'completed' and existing_breach.breach_status:
                            if existing_breach.records_affected and existing_breach.records_affected > 0:
                                processed_data = {
                                    'domain': domain,
                                    'breach_status': existing_breach.breach_status,
                                    'records_affected': existing_breach.records_affected,
                                    'breach_year': existing_breach.breach_year
                                }
                            else:
                                processed_data = {
                                    'domain': domain,
                                    'breach_status': existing_breach.breach_status,
                                    'records_affected': 0
                                }
                        else:
                            # Domain scan failed too many times or other issue - mark as unknown
                            processed_data = {
                                'domain': domain,
                                'breach_status': 'unknown',
                                'records_affected': 0
                            }
                    
                    # Update contacts based on scan results
                    # Leave contacts with 'risky' or 'bounced' status from email validation alone
                    contact_ids_for_domain = [c.id for c in domain_to_contacts.get(domain, [])]

                    if contact_ids_for_domain:
                        # Only update contacts when scan was successful
                        # When scan fails (unknown status), leave valid emails as 'unassigned' for retry
                        if processed_data['breach_status'] in ['breached', 'not_breached']:
                            # Successful scan - update only unassigned contacts
                            updated_count = db.session.query(Contact).filter(
                                Contact.id.in_(contact_ids_for_domain),
                                Contact.breach_status == 'unassigned'  # Only update contacts marked for scanning
                            ).update(
                                {Contact.breach_status: processed_data['breach_status']},
                                synchronize_session=False
                            )
                        else:
                            # Failed scan (unknown status) - don't update any contacts
                            # Leave valid emails as 'unassigned' for future retry
                            updated_count = 0

                        # Log which contacts were updated vs skipped
                        all_contacts_for_domain = Contact.query.filter(Contact.id.in_(contact_ids_for_domain)).all()
                        scannable_contacts = len([c for c in all_contacts_for_domain if c.breach_status == 'unassigned'])
                        preserved_contacts = len([c for c in all_contacts_for_domain if c.breach_status in ['risky', 'bounced']])

                        if processed_data['breach_status'] in ['breached', 'not_breached']:
                            logger.info(f"Domain {domain}: Scan successful - updated {updated_count} contacts to {processed_data['breach_status']}, preserved {preserved_contacts} risky/bounced contacts")
                        else:
                            logger.info(f"Domain {domain}: Scan failed - left {scannable_contacts} contacts as 'unassigned' for retry, preserved {preserved_contacts} risky/bounced contacts")
                        
                        # Log individual contact updates for verification and trigger auto-enrollment
                        updated_contacts = Contact.query.filter(Contact.id.in_(contact_ids_for_domain)).all()
                        for contact in updated_contacts:
                            logger.info(f"Verified contact {contact.email} -> {contact.breach_status}")

                            # Trigger auto-enrollment check for this contact
                            try:
                                from services.auto_enrollment import AutoEnrollmentService
                                auto_service = AutoEnrollmentService(db)
                                enrolled_campaigns = auto_service.check_breach_status_campaigns(contact.id)
                                if enrolled_campaigns > 0:
                                    logger.info(f"Auto-enrolled {contact.email} into {enrolled_campaigns} campaigns")
                            except Exception as e:
                                logger.error(f"Failed to auto-enroll {contact.email}: {str(e)}")
                        
                    # Update job results
                    if processed_data['breach_status'] == 'breached':
                        job['results']['breached_domains'] += 1
                    elif processed_data['breach_status'] == 'not_breached':
                        job['results']['secure_domains'] += 1
                    else:
                        job['results']['unknown_domains'] += 1
                    
                    job['results']['contacts_updated'] += len(contact_ids_for_domain)
                    
                    job['results']['domains_scanned'] += 1
                    
                    # Rate limiting for real API - 2 seconds between requests
                    if i < total_domains:
                        job['message'] = f'Waiting 2 seconds before next domain... ({i}/{total_domains} completed)'
                        logger.info(f"Rate limiting: waiting 2 seconds before scanning next domain...")
                        time.sleep(2)  # 2-second delay between requests
                
                # Commit all changes with explicit flush and refresh
                logger.info(f"Committing database changes for {len(domain_to_contacts)} domains")
                db.session.flush()  # Ensure all changes are written to database
                db.session.commit()
                
                # Force SQLite to sync changes by closing and reopening connection
                db.session.close()
                db.session.remove()
                
                logger.info("Database changes committed and session refreshed")
                
                # Complete the job
                job['status'] = 'completed'
                job['progress'] = 100
                job['message'] = f'Scan completed! {total_domains} domains processed'
                
                # Trigger auto-enrollment
                self._trigger_auto_enrollment(job_id, domain_to_contacts)
                
                self._move_job_to_results(job_id)
                
            except Exception as e:
                logger.error(f"Real scan failed for job {job_id}: {str(e)}")
                job['status'] = 'error'
                job['message'] = f'API scan failed: {str(e)}'
                self._move_job_to_results(job_id)
    
    def _generate_demo_breach_data(self, domain: str) -> Dict:
        """Generate demo breach data for testing"""
        domain_lower = domain.lower()
        
        # Demo patterns for different breach statuses
        if any(pattern in domain_lower for pattern in ['test', 'demo', 'example']):
            return {
                'breach_status': 'breached'
            }
        elif any(pattern in domain_lower for pattern in ['secure', 'safe', 'bank', 'gmail', 'outlook', 'yahoo']):
            return {
                'breach_status': 'not_breached'
            }
        else:
            # Random assignment for realistic demo
            import random
            rand = random.random()
            if rand < 0.3:  # 30% breached
                return {
                    'breach_status': 'breached'
                }
            elif rand < 0.8:  # 50% secure
                return {
                    'breach_status': 'not_breached'
                }
            else:  # 20% unknown (didn't scan)
                return {
                    'breach_status': 'unknown'
                }
    
    def _trigger_auto_enrollment(self, job_id: str, domain_to_contacts: dict):
        """Trigger auto-enrollment for scanned contacts with campaign preferences"""
        job = self.active_jobs[job_id]
        campaign_preferences = job.get('campaign_preferences', {})
        
        try:
            job['message'] = 'Processing auto-enrollment...'
            
            enrolled_count = 0
            breached_enrolled = 0
            secure_enrolled = 0
            
            # Process each contact based on their breach status and campaign preferences
            for contacts_list in domain_to_contacts.values():
                for contact in contacts_list:
                    campaign_id = None
                    
                    # Determine which campaign to enroll based on breach status
                    if contact.breach_status == 'breached' and campaign_preferences.get('breached_campaign_id'):
                        campaign_id = campaign_preferences['breached_campaign_id']
                        breached_enrolled += 1
                    elif contact.breach_status in ['not_breached', 'unknown'] and campaign_preferences.get('secure_campaign_id'):
                        campaign_id = campaign_preferences['secure_campaign_id']
                        secure_enrolled += 1
                    
                    # Enroll contact in campaign using EmailSequenceService
                    if campaign_id:
                        try:
                            from models.database import Campaign, Email
                            from services.email_sequence_service import EmailSequenceService
                            
                            # Check if contact is already enrolled in this campaign
                            existing_enrollment = Email.query.filter_by(
                                contact_id=contact.id,
                                campaign_id=campaign_id
                            ).first()
                            
                            if not existing_enrollment:
                                # Use EmailSequenceService for proper enrollment and immediate email sending
                                email_service = EmailSequenceService()
                                result = email_service.enroll_contact_in_campaign(
                                    contact_id=contact.id,
                                    campaign_id=campaign_id,
                                    force_breach_check=False  # Already scanned
                                )
                                
                                if result['success']:
                                    enrolled_count += 1
                                    logger.info(f"Contact {contact.id} enrolled in campaign {campaign_id}: {result}")
                                else:
                                    logger.warning(f"Failed to enroll contact {contact.id}: {result.get('error')}")
                                
                        except Exception as e:
                            logger.warning(f"Failed to enroll contact {contact.id} in campaign {campaign_id}: {str(e)}")
            
            # Commit all enrollments
            if enrolled_count > 0:
                db.session.commit()
                job['message'] = f'Auto-enrolled {enrolled_count} contacts ({breached_enrolled} breached, {secure_enrolled} secure)'
                logger.info(f"Campaign auto-enrollment: {enrolled_count} contacts enrolled from background scan")
            
        except Exception as e:
            logger.warning(f"Auto-enrollment failed in background scan {job_id}: {str(e)}")
            # Don't fail the job if auto-enrollment fails
    
    def _move_job_to_results(self, job_id: str):
        """Move completed job from active to results"""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            job['completed_at'] = datetime.utcnow()
            self.job_results[job_id] = job
            del self.active_jobs[job_id]


# Global instance
background_scanner = BackgroundScanner()

def get_background_scanner() -> BackgroundScanner:
    """Get the global background scanner instance"""
    return background_scanner

def start_contact_scan(contact_ids: List[int], campaign_preferences: Dict = None) -> str:
    """Convenience function to start a background scan with campaign preferences"""
    return background_scanner.start_background_scan(contact_ids, campaign_preferences)

def get_scan_status(job_id: str) -> Optional[Dict]:
    """Convenience function to get scan status"""
    return background_scanner.get_job_status(job_id)