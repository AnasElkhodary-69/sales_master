"""
Custom Reply-To Email Handler
Creates unique reply-to addresses that automatically detect replies
"""
import hashlib
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from models.database import db, Contact, Email, ContactCampaignStatus

logger = logging.getLogger(__name__)

class CustomReplyHandler:
    """
    Handles custom reply-to email addresses for reply detection
    Creates unique reply addresses that encode contact/campaign information
    """

    def __init__(self):
        # Base reply domain (configure this in your DNS)
        self.reply_domain = "replies.savety.ai"  # You need to configure this domain
        self.base_address = "replies"

    def generate_reply_address(self, contact_id: int, campaign_id: int, email_id: int) -> str:
        """
        Generate a unique reply-to address that encodes tracking information
        Format: replies+{encoded_data}@replies.savety.ai
        """
        try:
            # Create tracking data
            tracking_data = f"{contact_id}-{campaign_id}-{email_id}"

            # Create a hash for security (prevents address guessing)
            hash_key = f"salesbreachpro-{tracking_data}-{datetime.now().strftime('%Y%m')}"
            tracking_hash = hashlib.md5(hash_key.encode()).hexdigest()[:8]

            # Combine data with hash
            encoded_data = f"{contact_id}c{campaign_id}p{email_id}e{tracking_hash}"

            # Create reply address
            reply_address = f"{self.base_address}+{encoded_data}@{self.reply_domain}"

            logger.info(f"Generated reply address: {reply_address}")
            return reply_address

        except Exception as e:
            logger.error(f"Error generating reply address: {e}")
            return f"{self.base_address}@{self.reply_domain}"

    def decode_reply_address(self, reply_address: str) -> Optional[Dict]:
        """
        Decode tracking information from reply address
        Returns dict with contact_id, campaign_id, email_id if valid
        """
        try:
            # Extract the encoded part
            if '+' not in reply_address:
                return None

            encoded_part = reply_address.split('+')[1].split('@')[0]

            # Parse the encoded data: {contact_id}c{campaign_id}p{email_id}e{hash}
            import re
            pattern = r'(\d+)c(\d+)p(\d+)e([a-f0-9]{8})'
            match = re.match(pattern, encoded_part)

            if not match:
                return None

            contact_id = int(match.group(1))
            campaign_id = int(match.group(2))
            email_id = int(match.group(3))
            provided_hash = match.group(4)

            # Verify hash (security check)
            tracking_data = f"{contact_id}-{campaign_id}-{email_id}"
            expected_hash_key = f"salesbreachpro-{tracking_data}-{datetime.now().strftime('%Y%m')}"
            expected_hash = hashlib.md5(expected_hash_key.encode()).hexdigest()[:8]

            # Also check previous month's hash (in case email was sent last month)
            prev_month = datetime.now().replace(day=1) - datetime.timedelta(days=1)
            prev_hash_key = f"salesbreachpro-{tracking_data}-{prev_month.strftime('%Y%m')}"
            prev_hash = hashlib.md5(prev_hash_key.encode()).hexdigest()[:8]

            if provided_hash not in [expected_hash, prev_hash]:
                logger.warning(f"Invalid hash in reply address: {reply_address}")
                return None

            return {
                'contact_id': contact_id,
                'campaign_id': campaign_id,
                'email_id': email_id,
                'is_valid': True
            }

        except Exception as e:
            logger.error(f"Error decoding reply address: {e}")
            return None

    def process_reply_to_custom_address(self, to_address: str, from_address: str,
                                       subject: str, content: str) -> bool:
        """
        Process a reply sent to our custom reply address
        """
        try:
            # Decode the reply address
            tracking_info = self.decode_reply_address(to_address)

            if not tracking_info:
                logger.warning(f"Could not decode reply address: {to_address}")
                return False

            contact_id = tracking_info['contact_id']
            campaign_id = tracking_info['campaign_id']
            email_id = tracking_info['email_id']

            # Verify the sender matches our contact
            contact = Contact.query.get(contact_id)
            if not contact or contact.email.lower() != from_address.lower():
                logger.warning(f"Sender mismatch: expected {contact.email}, got {from_address}")
                return False

            # Process the reply
            return self._process_verified_reply(contact_id, campaign_id, email_id,
                                              subject, content, from_address)

        except Exception as e:
            logger.error(f"Error processing custom reply: {e}")
            return False

    def _process_verified_reply(self, contact_id: int, campaign_id: int, email_id: int,
                               subject: str, content: str, from_address: str) -> bool:
        """Process a verified reply and stop sequences"""
        try:
            logger.info(f"Processing verified reply from {from_address}")

            # Get contact and mark as responded
            contact = Contact.query.get(contact_id)
            if contact:
                contact.has_responded = True
                contact.responded_at = datetime.utcnow()

            # Update the original email record
            email_record = Email.query.get(email_id)
            if email_record:
                email_record.replied_at = datetime.utcnow()
                email_record.status = 'replied'

            # Mark campaign status as replied
            campaign_status = ContactCampaignStatus.query.filter_by(
                contact_id=contact_id,
                campaign_id=campaign_id
            ).first()

            if campaign_status and not campaign_status.replied_at:
                campaign_status.replied_at = datetime.utcnow()

                # Update campaign response count
                from models.database import Campaign
                campaign = Campaign.query.get(campaign_id)
                if campaign:
                    campaign.response_count = (campaign.response_count or 0) + 1

            # Stop future scheduled emails
            from models.database import EmailSequence
            future_sequences = EmailSequence.query.filter(
                EmailSequence.contact_id == contact_id,
                EmailSequence.campaign_id == campaign_id,
                EmailSequence.status == 'scheduled'
            ).all()

            for seq in future_sequences:
                seq.status = 'skipped_replied'
                seq.skip_reason = 'Contact replied - detected via custom reply address'

            # Store the reply content for analysis
            self._store_reply_content(contact_id, campaign_id, email_id, subject, content)

            db.session.commit()

            logger.info(f"Successfully processed reply from {from_address}")
            return True

        except Exception as e:
            logger.error(f"Error processing verified reply: {e}")
            db.session.rollback()
            return False

    def _store_reply_content(self, contact_id: int, campaign_id: int, email_id: int,
                            subject: str, content: str):
        """Store reply content for analysis"""
        try:
            from models.database import Response

            # Create a Response record
            response = Response(
                email_id=email_id,
                response_type='reply',
                sentiment='neutral',  # Could add sentiment analysis here
                content=content[:1000],  # Limit content length
                processed_at=datetime.utcnow()
            )

            db.session.add(response)
            logger.info(f"Stored reply content for email {email_id}")

        except Exception as e:
            logger.error(f"Error storing reply content: {e}")

def create_custom_reply_handler():
    """Factory function to create custom reply handler"""
    return CustomReplyHandler()

# Webhook endpoint for processing custom replies (add to routes)
def handle_custom_reply_webhook(request_data: Dict) -> Dict:
    """
    Handle webhook from email service when reply is received to custom address
    This would be called by your email provider when emails are received
    """
    try:
        handler = create_custom_reply_handler()

        to_address = request_data.get('to', '')
        from_address = request_data.get('from', '')
        subject = request_data.get('subject', '')
        content = request_data.get('content', '')

        if handler.process_reply_to_custom_address(to_address, from_address, subject, content):
            return {'status': 'success', 'message': 'Reply processed successfully'}
        else:
            return {'status': 'ignored', 'message': 'Reply not processed'}

    except Exception as e:
        logger.error(f"Error in custom reply webhook: {e}")
        return {'status': 'error', 'message': str(e)}