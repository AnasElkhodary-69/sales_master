"""
Background job scheduler for auto-enrollment and other periodic tasks
"""
import threading
import time
import logging
from datetime import datetime, timedelta
from flask import current_app

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskScheduler:
    """Simple background task scheduler"""
    
    def __init__(self, app=None, db=None):
        self.app = app
        self.db = db
        self.running = False
        self.thread = None
        
    def init_app(self, app, db):
        """Initialize with Flask app and database"""
        self.app = app
        self.db = db
        
    def start(self):
        """Start the background scheduler"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        logger.info("Background scheduler started")
    
    def stop(self):
        """Stop the background scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Background scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        logger.info("Scheduler loop started")
        
        # Track last run times for different tasks
        last_auto_enrollment = datetime.min
        last_email_processing = datetime.min
        last_reply_detection = datetime.min
        last_scan_cleanup = datetime.min
        last_background_scan = datetime.min
        
        while self.running:
            try:
                current_time = datetime.utcnow()
                
                # Run auto-enrollment every hour
                if current_time - last_auto_enrollment > timedelta(hours=1):
                    self._run_auto_enrollment()
                    last_auto_enrollment = current_time
                
                # Process scheduled emails every minute for flexible delay support
                if current_time - last_email_processing > timedelta(minutes=1):
                    self._process_scheduled_emails()
                    last_email_processing = current_time

                # Check for email replies based on user setting (default 5 minutes)
                reply_interval = self._get_reply_detection_interval()
                if current_time - last_reply_detection > timedelta(minutes=reply_interval):
                    self._check_for_replies()
                    last_reply_detection = current_time

                # Clean up stuck scans every 10 minutes
                if current_time - last_scan_cleanup > timedelta(minutes=10):
                    self._cleanup_stuck_scans()
                    last_scan_cleanup = current_time

                # Run background scanning every 5 minutes for unassigned contacts
                if current_time - last_background_scan > timedelta(minutes=5):
                    self._run_background_scanning()
                    last_background_scan = current_time
                
                # Sleep for 1 minute before checking again
                time.sleep(60)  # 1 minute
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _run_auto_enrollment(self):
        """Run auto-enrollment process"""
        try:
            if not self.app or not self.db:
                logger.error("App or DB not initialized")
                return
                
            with self.app.app_context():
                from services.auto_enrollment import create_auto_enrollment_service
                
                auto_service = create_auto_enrollment_service(self.db)
                stats = auto_service.process_auto_enrollment()
                
                logger.info(f"Auto-enrollment completed: {stats}")
                
        except Exception as e:
            logger.error(f"Error running auto-enrollment: {str(e)}")
    
    def _process_scheduled_emails(self):
        """Process scheduled emails with all business rules"""
        try:
            if not self.app or not self.db:
                logger.error("App or DB not initialized for email processing")
                return

            with self.app.app_context():
                from services.email_processor import process_email_queue

                results = process_email_queue()

                if results.get('emails_sent', 0) > 0 or results.get('emails_failed', 0) > 0:
                    logger.info(f"Email processing completed: {results}")

        except Exception as e:
            logger.error(f"Error processing emails: {str(e)}")

    def _check_for_replies(self):
        """Check for email replies using IMAP"""
        try:
            if not self.app or not self.db:
                logger.error("App or DB not initialized for reply detection")
                return

            with self.app.app_context():
                from services.reply_detection_service import create_reply_detection_service

                reply_service = create_reply_detection_service()
                results = reply_service.check_for_replies()

                if results.get('replies_found', 0) > 0:
                    logger.info(f"Reply detection completed: {results}")
                    logger.info(f"Found {results['replies_found']} new replies, stopped {results.get('sequences_stopped', 0)} sequences")

        except Exception as e:
            logger.error(f"Error checking for replies: {str(e)}")

    def _get_reply_detection_interval(self):
        """Get reply detection interval from settings (default 5 minutes)"""
        try:
            if not self.app or not self.db:
                return 5  # Default to 5 minutes

            with self.app.app_context():
                from models.database import Settings
                interval = Settings.get_setting('reply_detection_interval', '5')
                return int(interval)
        except Exception as e:
            logger.error(f"Error getting reply detection interval: {str(e)}")
            return 5  # Default to 5 minutes

    def _cleanup_stuck_scans(self):
        """Clean up scan records that have been stuck in 'scanning' status for too long"""
        try:
            if not self.app or not self.db:
                logger.error("App or DB not initialized for scan cleanup")
                return

            with self.app.app_context():
                from models.database import db, Breach

                # Find scans stuck in 'scanning' for more than 5 minutes
                stuck_threshold = datetime.utcnow() - timedelta(minutes=5)

                stuck_scans = Breach.query.filter(
                    Breach.scan_status == 'scanning',
                    Breach.last_scan_attempt < stuck_threshold
                ).all()

                if stuck_scans:
                    logger.info(f"Found {len(stuck_scans)} stuck scans to clean up")

                    for breach in stuck_scans:
                        breach.scan_status = 'failed'
                        breach.scan_error = f"Scan timeout after 5+ minutes - automatically reset for retry"
                        logger.warning(f"Reset stuck scan for domain: {breach.domain}")

                    db.session.commit()
                    logger.info(f"Cleaned up {len(stuck_scans)} stuck scans")

        except Exception as e:
            logger.error(f"Error cleaning up stuck scans: {str(e)}")

    def _run_background_scanning(self):
        """Run background scanning for unassigned contacts"""
        try:
            if not self.app or not self.db:
                logger.error("App or DB not initialized for background scanning")
                return

            with self.app.app_context():
                from models.database import db, Contact
                from services.background_scanner import BackgroundScanner

                # Find contacts that need scanning
                unassigned_contacts = Contact.query.filter_by(breach_status='unassigned').all()

                if unassigned_contacts:
                    logger.info(f"Found {len(unassigned_contacts)} unassigned contacts to scan")

                    contact_ids = [contact.id for contact in unassigned_contacts]

                    # Create background scanner and trigger scan
                    scanner = BackgroundScanner()
                    job_id = scanner.start_background_scan(contact_ids)

                    logger.info(f"Started background scan job {job_id} for {len(contact_ids)} contacts")
                else:
                    logger.debug("No unassigned contacts found for background scanning")

        except Exception as e:
            logger.error(f"Error running background scanning: {str(e)}")

# Global scheduler instance
scheduler = TaskScheduler()

def init_scheduler(app, db):
    """Initialize and start the scheduler"""
    try:
        scheduler.init_app(app, db)
        scheduler.start()
        logger.info("Scheduler initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {str(e)}")

def stop_scheduler():
    """Stop the scheduler"""
    scheduler.stop()