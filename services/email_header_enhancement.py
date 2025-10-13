"""
Email Header Enhancement Service
Enhances outgoing emails with custom headers for better reply tracking
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Tuple
from models.database import db, Email, Settings

logger = logging.getLogger(__name__)

class EmailHeaderEnhancement:
    """
    Enhances emails with custom headers and tracking mechanisms
    """

    def __init__(self):
        self.domain = "marketing.savety.online"

    def generate_custom_headers(self, contact_id: int, campaign_id: int, email_id: int) -> Dict[str, str]:
        """
        Generate custom email headers for tracking
        """
        try:
            # Generate unique message ID
            message_id = f"salesbreachpro-{campaign_id}-{contact_id}-{email_id}-{int(datetime.now().timestamp())}@{self.domain}"

            # Generate tracking headers
            headers = {
                'Message-ID': f'<{message_id}>',
                'X-SalesBreachPro-Contact-ID': str(contact_id),
                'X-SalesBreachPro-Campaign-ID': str(campaign_id),
                'X-SalesBreachPro-Email-ID': str(email_id),
                'X-SalesBreachPro-Timestamp': datetime.now().isoformat(),
                'X-Auto-Response-Suppress': 'OOF, DR, RN, NRN',  # Suppress auto-responses
                'List-Unsubscribe': f'<https://{self.domain}/unsubscribe/{contact_id}>',
                'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
            }

            return headers

        except Exception as e:
            logger.error(f"Error generating custom headers: {e}")
            return {}

    def enhance_email_for_brevo(self, contact_id: int, campaign_id: int, email_id: int,
                               subject: str, html_content: str, text_content: str = None) -> Tuple[str, str, Dict]:
        """
        Enhance email content and headers for better tracking
        Returns: (enhanced_subject, enhanced_html, custom_headers)
        """
        try:
            # Generate custom headers
            custom_headers = self.generate_custom_headers(contact_id, campaign_id, email_id)

            # Enhance subject with tracking (invisible)
            enhanced_subject = subject

            # Add invisible tracking pixel to HTML content
            tracking_pixel = self.generate_tracking_pixel(contact_id, campaign_id, email_id)
            enhanced_html = html_content

            if tracking_pixel and '<body' in enhanced_html.lower():
                # Insert tracking pixel just after <body> tag
                body_pos = enhanced_html.lower().find('<body')
                body_end = enhanced_html.find('>', body_pos) + 1
                enhanced_html = (enhanced_html[:body_end] +
                               tracking_pixel +
                               enhanced_html[body_end:])

            # Add reply instructions at the bottom
            reply_instructions = self.generate_reply_instructions()
            if '</body>' in enhanced_html.lower():
                enhanced_html = enhanced_html.replace('</body>', f'{reply_instructions}</body>')

            return enhanced_subject, enhanced_html, custom_headers

        except Exception as e:
            logger.error(f"Error enhancing email: {e}")
            return subject, html_content, {}

    def generate_tracking_pixel(self, contact_id: int, campaign_id: int, email_id: int) -> str:
        """Generate invisible tracking pixel for open detection"""
        try:
            pixel_url = f"https://{self.domain}/track/open/{contact_id}/{campaign_id}/{email_id}.png"

            pixel_html = f'''
            <img src="{pixel_url}" width="1" height="1" style="display:none;" alt="" />
            '''

            return pixel_html

        except Exception as e:
            logger.error(f"Error generating tracking pixel: {e}")
            return ""

    def generate_reply_instructions(self) -> str:
        """Generate subtle reply instructions"""
        return '''
        <div style="margin-top: 40px; padding: 20px; border-top: 1px solid #eee; font-size: 11px; color: #888;">
            <p style="margin: 0; text-align: center;">
                Simply reply to this email if you'd like to discuss your security needs.
                <br>
                <small>This email was sent by Savety AI Security Solutions</small>
            </p>
        </div>
        '''

    def create_enhanced_brevo_payload(self, contact, campaign, template_variant, email_record) -> Dict:
        """
        Create enhanced Brevo API payload with custom headers and tracking
        """
        try:
            from services.custom_reply_handler import create_custom_reply_handler

            # Generate custom reply-to address
            reply_handler = create_custom_reply_handler()
            custom_reply_to = reply_handler.generate_reply_address(
                contact.id, campaign.id, email_record.id
            )

            # Enhance email content
            enhanced_subject, enhanced_html, custom_headers = self.enhance_email_for_brevo(
                contact.id, campaign.id, email_record.id,
                template_variant.subject_line,
                template_variant.email_body_html or template_variant.email_body
            )

            # Get sender information
            sender_email = Settings.get_setting('brevo_sender_email', 'emily.carter@savety.ai')
            sender_name = Settings.get_setting('brevo_sender_name', 'Security Team')

            # Create Brevo payload
            payload = {
                'sender': {
                    'name': sender_name,
                    'email': sender_email
                },
                'to': [{
                    'email': contact.email,
                    'name': f"{contact.first_name} {contact.last_name}".strip() or contact.email
                }],
                'replyTo': {
                    'email': custom_reply_to,
                    'name': sender_name
                },
                'subject': enhanced_subject,
                'htmlContent': enhanced_html,
                'headers': custom_headers,
                'tags': [
                    f'campaign-{campaign.id}',
                    f'contact-{contact.id}',
                    'salesbreachpro'
                ]
            }

            # Add text content if available
            if template_variant.email_body and template_variant.email_body != template_variant.email_body_html:
                payload['textContent'] = template_variant.email_body

            return payload

        except Exception as e:
            logger.error(f"Error creating enhanced Brevo payload: {e}")
            return {}

def create_email_header_enhancement():
    """Factory function to create email header enhancement service"""
    return EmailHeaderEnhancement()