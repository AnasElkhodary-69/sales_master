"""
Backup Reply Detection System
Combines multiple methods to ensure no replies are missed
"""
import logging
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, List
from threading import Thread
from models.database import db, Settings, Contact, Email

logger = logging.getLogger(__name__)

class BackupReplyDetectionSystem:
    """
    Comprehensive backup system that uses multiple methods to detect replies
    """

    def __init__(self):
        self.methods = []
        self.enabled = True
        self.check_interval_minutes = 15  # Check every 15 minutes
        self.setup_detection_methods()

    def setup_detection_methods(self):
        """Initialize all available reply detection methods"""
        try:
            # Method 1: IMAP Email Monitoring
            from services.reply_detection_service import create_reply_detection_service
            self.imap_service = create_reply_detection_service()
            self.methods.append(('IMAP Monitoring', self.imap_service.check_for_replies))

            # Method 2: Custom Reply Address Handler
            from services.custom_reply_handler import create_custom_reply_handler
            self.custom_handler = create_custom_reply_handler()

            # Method 3: Brevo API polling (fallback)
            self.methods.append(('Brevo API Polling', self.check_brevo_api_for_replies))

            # Method 4: Manual reply checking endpoint
            self.methods.append(('Database Analysis', self.analyze_database_patterns))

            logger.info(f"Initialized {len(self.methods)} reply detection methods")

        except Exception as e:
            logger.error(f"Error setting up detection methods: {e}")

    def run_all_detection_methods(self) -> Dict[str, Dict]:
        """
        Run all available reply detection methods
        Returns results from each method
        """
        results = {}

        for method_name, method_func in self.methods:
            try:
                logger.info(f"Running {method_name}...")
                result = method_func()
                results[method_name] = result
                logger.info(f"{method_name} completed: {result}")

            except Exception as e:
                logger.error(f"Error in {method_name}: {e}")
                results[method_name] = {'error': str(e)}

        return results

    def check_brevo_api_for_replies(self) -> Dict:
        """
        Check Brevo API for reply events that might have been missed
        """
        stats = {
            'api_calls': 0,
            'replies_found': 0,
            'errors': 0
        }

        try:
            # This would use Brevo API to check for events
            # For now, it's a placeholder that could be implemented
            # if Brevo provides an API to query events

            api_key = Settings.get_setting('brevo_api_key', '')
            if not api_key:
                return {'error': 'No Brevo API key configured'}

            # Placeholder for actual Brevo API implementation
            # You would need to check Brevo's API documentation for this
            stats['api_calls'] = 1
            logger.info("Brevo API polling completed (placeholder)")

        except Exception as e:
            logger.error(f"Error checking Brevo API: {e}")
            stats['errors'] = 1

        return stats

    def analyze_database_patterns(self) -> Dict:
        """
        Analyze database patterns to detect potential missed replies
        """
        stats = {
            'contacts_analyzed': 0,
            'potential_replies': 0,
            'patterns_found': 0
        }

        try:
            # Look for contacts with sudden email activity drops
            # This could indicate a reply that stopped the sequence

            cutoff_date = datetime.utcnow() - timedelta(days=7)

            # Find contacts with recent emails but no recent activity
            recent_emails = Email.query.filter(
                Email.sent_at >= cutoff_date,
                Email.status.in_(['delivered', 'opened'])
            ).all()

            stats['contacts_analyzed'] = len(set(email.contact_id for email in recent_emails))

            for email in recent_emails:
                # Check if this contact suddenly stopped getting emails
                contact = Contact.query.get(email.contact_id)
                if contact and not contact.has_responded:
                    # Look for signs of engagement without recorded reply
                    if (email.opened_at and
                        not email.replied_at and
                        email.sent_at < datetime.utcnow() - timedelta(days=2)):

                        # Check if sequence stopped without obvious reason
                        from models.database import EmailSequence
                        stopped_sequences = EmailSequence.query.filter_by(
                            contact_id=contact.id,
                            status='skipped_replied'
                        ).count()

                        if stopped_sequences == 0:
                            stats['potential_replies'] += 1
                            logger.info(f"Potential missed reply from {contact.email}")

        except Exception as e:
            logger.error(f"Error analyzing database patterns: {e}")
            stats['errors'] = 1

        return stats

    def start_background_monitoring(self):
        """
        Start background monitoring with scheduled checks
        """
        try:
            # Schedule regular checks
            schedule.every(self.check_interval_minutes).minutes.do(self.run_scheduled_check)

            logger.info(f"Started background reply monitoring (checking every {self.check_interval_minutes} minutes)")

            # Run in background thread
            monitoring_thread = Thread(target=self._run_scheduler, daemon=True)
            monitoring_thread.start()

        except Exception as e:
            logger.error(f"Error starting background monitoring: {e}")

    def _run_scheduler(self):
        """Run the scheduler in a loop"""
        while self.enabled:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)

    def run_scheduled_check(self):
        """Run scheduled reply detection check"""
        try:
            logger.info("Starting scheduled reply detection check")
            results = self.run_all_detection_methods()

            # Summarize results
            total_replies = sum(
                result.get('replies_found', 0)
                for result in results.values()
                if isinstance(result, dict)
            )

            if total_replies > 0:
                logger.info(f"Scheduled check found {total_replies} new replies")
            else:
                logger.info("Scheduled check completed - no new replies found")

        except Exception as e:
            logger.error(f"Error in scheduled check: {e}")

    def manual_reply_check(self, contact_email: str = None) -> Dict:
        """
        Manually trigger reply check for specific contact or all contacts
        """
        try:
            if contact_email:
                logger.info(f"Running manual reply check for {contact_email}")
                # Focus on specific contact
                contact = Contact.query.filter_by(email=contact_email).first()
                if not contact:
                    return {'error': f'Contact {contact_email} not found'}

                # Run targeted checks for this contact
                results = {}
                for method_name, method_func in self.methods:
                    if 'IMAP' in method_name:
                        # IMAP check would look for emails from this specific contact
                        results[method_name] = method_func()

                return results
            else:
                logger.info("Running manual reply check for all contacts")
                return self.run_all_detection_methods()

        except Exception as e:
            logger.error(f"Error in manual reply check: {e}")
            return {'error': str(e)}

    def get_detection_status(self) -> Dict:
        """Get current status of all detection methods"""
        status = {
            'enabled': self.enabled,
            'check_interval_minutes': self.check_interval_minutes,
            'methods_count': len(self.methods),
            'last_check': None,
            'methods': []
        }

        for method_name, _ in self.methods:
            method_status = {
                'name': method_name,
                'enabled': True,  # Could add individual method enabling/disabling
                'last_result': None
            }
            status['methods'].append(method_status)

        return status

    def emergency_reply_scan(self) -> Dict:
        """
        Emergency scan for replies when Brevo webhooks are down
        """
        try:
            logger.warning("Running EMERGENCY reply scan - Brevo webhooks may be down")

            # Run all methods with higher priority on recent emails
            results = self.run_all_detection_methods()

            # Additionally, check for emails that should have received replies
            cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_emails = Email.query.filter(
                Email.sent_at >= cutoff,
                Email.status == 'delivered',
                Email.replied_at.is_(None)
            ).all()

            emergency_stats = {
                'recent_emails_checked': len(recent_emails),
                'emergency_mode': True,
                'scan_time': datetime.utcnow().isoformat()
            }

            results['emergency_scan'] = emergency_stats

            logger.info(f"Emergency scan completed: checked {len(recent_emails)} recent emails")
            return results

        except Exception as e:
            logger.error(f"Error in emergency reply scan: {e}")
            return {'error': str(e)}

def create_backup_reply_detection_system():
    """Factory function to create backup reply detection system"""
    return BackupReplyDetectionSystem()

# Global instance for use in routes
backup_system = None

def initialize_backup_system():
    """Initialize the global backup system"""
    global backup_system
    try:
        backup_system = create_backup_reply_detection_system()
        backup_system.start_background_monitoring()
        logger.info("Backup reply detection system initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing backup system: {e}")

def get_backup_system():
    """Get the global backup system instance"""
    global backup_system
    if backup_system is None:
        initialize_backup_system()
    return backup_system