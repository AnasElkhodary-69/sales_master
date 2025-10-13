"""
Independent Reply Detection Service
Monitors email inbox for replies without relying on Brevo webhooks
"""
import imaplib
import email
import logging
import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from email.header import decode_header
from models.database import db, Contact, Email, ContactCampaignStatus, Settings

logger = logging.getLogger(__name__)

class ReplyDetectionService:
    """Service to detect email replies independently of Brevo webhooks"""

    def __init__(self):
        # Email server configuration
        self.imap_server = None
        self.email_address = None
        self.email_password = None
        self.load_email_config()

    def load_email_config(self):
        """Load email configuration from settings or environment"""
        try:
            # Try to get from database settings first
            self.imap_server = Settings.get_setting('reply_detection_imap_server', 'imap.gmail.com')
            self.email_address = Settings.get_setting('reply_detection_email', '')
            self.email_password = Settings.get_setting('reply_detection_password', '')

            # Fallback to environment variables
            import os
            if not self.email_address:
                self.email_address = os.getenv('REPLY_DETECTION_EMAIL', '')
            if not self.email_password:
                self.email_password = os.getenv('REPLY_DETECTION_PASSWORD', '')
            if not self.imap_server:
                self.imap_server = os.getenv('REPLY_DETECTION_IMAP_SERVER', 'imap.gmail.com')

        except Exception as e:
            logger.error(f"Error loading email config: {e}")

    def check_for_replies(self) -> Dict[str, int]:
        """
        Check email inbox for new replies and process them
        Returns statistics about replies found
        """
        stats = {
            'emails_checked': 0,
            'replies_found': 0,
            'sequences_stopped': 0,
            'errors': 0
        }

        if not self.email_address or not self.email_password:
            logger.warning("Email credentials not configured for reply detection")
            return stats

        try:
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_address, self.email_password)
            mail.select('INBOX')

            # Search for emails from the last 24 hours (read or unread)
            # This ensures we catch replies even if they were accidentally opened
            since_date = (datetime.now() - timedelta(hours=24)).strftime("%d-%b-%Y")
            search_criteria = f'(SINCE {since_date})'

            # Get email IDs
            status, email_ids = mail.search(None, search_criteria)

            if status == 'OK':
                email_list = email_ids[0].split()
                stats['emails_checked'] = len(email_list)

                for email_id in email_list:
                    try:
                        # Fetch email headers first to check date
                        status, email_data = mail.fetch(email_id, '(RFC822)')

                        if status == 'OK':
                            # Parse email
                            raw_email = email_data[0][1]
                            parsed_email = email.message_from_bytes(raw_email)

                            # Check if this is a reply to our email
                            reply_info = self.analyze_email_for_reply(parsed_email)

                            if reply_info:
                                # Check if this reply was already processed
                                if not self.is_reply_already_processed(reply_info):
                                    # Process the reply
                                    if self.process_reply(reply_info):
                                        stats['replies_found'] += 1
                                        stats['sequences_stopped'] += 1
                                        logger.info(f"✅ Processed new reply from {reply_info['contact_email']}")
                                else:
                                    logger.info(f"⏭️ Reply from {reply_info['contact_email']} already processed, skipping")

                    except Exception as e:
                        logger.error(f"Error processing email {email_id}: {e}")
                        stats['errors'] += 1

            mail.logout()

        except Exception as e:
            logger.error(f"Error checking for replies: {e}")
            stats['errors'] += 1

        return stats

    def is_reply_already_processed(self, reply_info: Dict) -> bool:
        """
        Check if this reply has already been processed by checking if the contact
        has already been marked as replied in the database
        """
        try:
            contact_id = reply_info['contact_id']
            contact = Contact.query.get(contact_id)

            # If contact is already marked as responded, this reply was likely already processed
            if contact and contact.has_responded:
                return True

            # Also check if there are any recent emails marked as replied for this contact
            from datetime import datetime, timedelta
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)

            recent_replied_emails = Email.query.filter(
                Email.contact_id == contact_id,
                Email.replied_at >= recent_cutoff
            ).first()

            return recent_replied_emails is not None

        except Exception as e:
            logger.error(f"Error checking if reply already processed: {e}")
            return False  # If error, process anyway to be safe

    def analyze_email_for_reply(self, parsed_email) -> Optional[Dict]:
        """
        Analyze an email to determine if it's a reply to our outreach
        Returns reply information if found, None otherwise
        """
        try:
            # Get sender email
            from_header = parsed_email.get('From', '')
            sender_email = self.extract_email_address(from_header)

            if not sender_email:
                return None

            # Check if this sender is in our contacts
            contact = Contact.query.filter_by(email=sender_email).first()
            if not contact:
                return None

            # Look for reply indicators
            subject = self.decode_header_value(parsed_email.get('Subject', ''))
            in_reply_to = parsed_email.get('In-Reply-To', '')
            references = parsed_email.get('References', '')

            # Check for "Re:" in subject or our custom message IDs
            is_reply = (
                subject.lower().startswith('re:') or
                self.contains_our_message_id(in_reply_to) or
                self.contains_our_message_id(references) or
                self.subject_matches_our_templates(subject)
            )

            if is_reply:
                return {
                    'contact_email': sender_email,
                    'contact_id': contact.id,
                    'subject': subject,
                    'message_id': parsed_email.get('Message-ID', ''),
                    'in_reply_to': in_reply_to,
                    'reply_content': self.extract_email_content(parsed_email),
                    'received_date': datetime.now()
                }

            return None

        except Exception as e:
            logger.error(f"Error analyzing email: {e}")
            return None

    def extract_email_address(self, from_header: str) -> str:
        """Extract email address from From header"""
        try:
            # Use regex to extract email from "Name <email@domain.com>" format
            email_pattern = r'<([^>]+)>|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            match = re.search(email_pattern, from_header)

            if match:
                return match.group(1) or match.group(2)

            return from_header.strip()

        except Exception:
            return ''

    def decode_header_value(self, header_value: str) -> str:
        """Decode email header value"""
        try:
            decoded_parts = decode_header(header_value)
            decoded_string = ''

            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    decoded_string += part.decode(encoding or 'utf-8')
                else:
                    decoded_string += part

            return decoded_string

        except Exception:
            return header_value

    def contains_our_message_id(self, header_value: str) -> bool:
        """Check if header contains our custom message IDs"""
        if not header_value:
            return False

        # Look for our custom message ID patterns
        # Our system generates message IDs like: salesbreachpro-{campaign_id}-{contact_id}-{timestamp}
        our_patterns = [
            'salesbreachpro-',
            'savety.ai',
            'marketing.savety.online'
        ]

        header_lower = header_value.lower()
        return any(pattern in header_lower for pattern in our_patterns)

    def subject_matches_our_templates(self, subject: str) -> bool:
        """Check if subject line matches our email templates"""
        try:
            from models.database import EmailTemplate

            # Get common phrases from our templates
            templates = EmailTemplate.query.all()
            our_subjects = [template.subject_line.lower() for template in templates if template.subject_line]

            subject_lower = subject.lower().replace('re:', '').strip()

            # Check for partial matches
            for template_subject in our_subjects:
                # Remove common template variables for comparison
                clean_template = re.sub(r'\{\{[^}]+\}\}', '', template_subject).strip()
                if clean_template and clean_template in subject_lower:
                    return True

            # Check for common security-related keywords we use
            security_keywords = [
                'security alert', 'data breach', 'compromised', 'vulnerability',
                'urgent', 'security assessment', 'breach notification'
            ]

            return any(keyword in subject_lower for keyword in security_keywords)

        except Exception as e:
            logger.error(f"Error checking subject match: {e}")
            return False

    def extract_email_content(self, parsed_email) -> str:
        """Extract readable content from email"""
        try:
            content = ""

            # Handle multipart emails
            if parsed_email.is_multipart():
                for part in parsed_email.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))

                    # Skip attachments
                    if "attachment" in content_disposition:
                        continue

                    # Get text content
                    if content_type == "text/plain":
                        body = part.get_payload(decode=True)
                        if body:
                            content += body.decode('utf-8', errors='ignore')
                    elif content_type == "text/html" and not content:
                        # Fallback to HTML if no plain text
                        body = part.get_payload(decode=True)
                        if body:
                            content += body.decode('utf-8', errors='ignore')
            else:
                # Simple email
                body = parsed_email.get_payload(decode=True)
                if body:
                    content = body.decode('utf-8', errors='ignore')

            # Clean up content (remove excessive whitespace, etc.)
            content = re.sub(r'\n\s*\n', '\n\n', content.strip())
            return content[:1000]  # Limit to first 1000 characters

        except Exception as e:
            logger.error(f"Error extracting email content: {e}")
            return ""

    def process_reply(self, reply_info: Dict) -> bool:
        """
        Process a detected reply - stop sequences and update records
        """
        try:
            contact_id = reply_info['contact_id']
            contact_email = reply_info['contact_email']

            logger.info(f"Processing reply from {contact_email}")

            # Get contact
            contact = Contact.query.get(contact_id)
            if not contact:
                return False

            # Mark contact as responded
            contact.has_responded = True
            contact.responded_at = reply_info['received_date']

            # Find all active campaign statuses for this contact
            active_statuses = ContactCampaignStatus.query.filter_by(
                contact_id=contact_id,
                replied_at=None
            ).all()

            sequences_stopped = 0

            for status in active_statuses:
                # Mark as replied
                status.replied_at = reply_info['received_date']
                sequences_stopped += 1

                # Update campaign response count
                from models.database import Campaign
                campaign = Campaign.query.get(status.campaign_id)
                if campaign:
                    campaign.response_count = (campaign.response_count or 0) + 1

                logger.info(f"Stopped sequence for {contact_email} in campaign {status.campaign_id}")

            # Try to find and update the original email record
            # Look for recent emails to this contact
            recent_emails = Email.query.filter_by(contact_id=contact_id).filter(
                Email.sent_at >= datetime.now() - timedelta(days=30)
            ).all()

            for email_record in recent_emails:
                if not email_record.replied_at:
                    email_record.replied_at = reply_info['received_date']
                    email_record.status = 'replied'
                    break  # Only mark the most recent email

            # Stop future scheduled emails
            from models.database import EmailSequence
            future_sequences = EmailSequence.query.filter(
                EmailSequence.contact_id == contact_id,
                EmailSequence.status == 'scheduled'
            ).all()

            for seq in future_sequences:
                seq.status = 'skipped_replied'
                seq.skip_reason = 'Contact replied - detected via IMAP'

            db.session.commit()

            logger.info(f"Successfully processed reply from {contact_email}, stopped {sequences_stopped} sequences")
            return True

        except Exception as e:
            logger.error(f"Error processing reply: {e}")
            db.session.rollback()
            return False

def create_reply_detection_service():
    """Factory function to create reply detection service"""
    return ReplyDetectionService()

# Background task function that can be called by scheduler
def check_replies_background_task():
    """Background task to check for replies"""
    try:
        service = create_reply_detection_service()
        stats = service.check_for_replies()

        logger.info(f"Reply detection completed: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Error in reply detection background task: {e}")
        return {'error': str(e)}