"""
Modern Brevo Email Service using brevo-python SDK for SalesBreachPro
Uses the latest official Brevo Python SDK
"""
import time
import logging
import html
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Import the modern Brevo SDK
import brevo_python
from brevo_python.rest import ApiException

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BrevoModernService:
    """Modern Brevo Email Service using brevo-python SDK"""
    
    def __init__(self, config):
        self.config = config
        
        # Get API key from environment variables first, then config, then database
        import os
        self.api_key = os.environ.get('BREVO_API_KEY') or getattr(config, 'BREVO_API_KEY', None)
        if not self.api_key:
            # Try to get from database settings as fallback
            try:
                from models.database import Settings
                self.api_key = Settings.get_setting('brevo_api_key', '')
            except:
                self.api_key = ''
        
        if not self.api_key:
            logger.warning("No Brevo API key found. Please configure it in settings.")
            return
            
        # Configure the API client
        configuration = brevo_python.Configuration()
        configuration.api_key['api-key'] = self.api_key
        
        # Create API client
        api_client = brevo_python.ApiClient(configuration)
        
        # Initialize API instances
        self.transactional_api = brevo_python.TransactionalEmailsApi(api_client)
        self.account_api = brevo_python.AccountApi(api_client)
        self.contacts_api = brevo_python.ContactsApi(api_client)
        self.campaigns_api = brevo_python.EmailCampaignsApi(api_client)
        self.senders_api = brevo_python.SendersApi(api_client)
        self.webhooks_api = brevo_python.WebhooksApi(api_client)
        self.process_api = brevo_python.ProcessApi(api_client)
        
        # Configurable settings - prioritize environment variables
        self.sender_email = os.environ.get('BREVO_SENDER_EMAIL') or getattr(config, 'BREVO_SENDER_EMAIL', '')
        self.sender_name = os.environ.get('BREVO_SENDER_NAME') or getattr(config, 'BREVO_SENDER_NAME', 'Security Team')

        # Fallback to database settings if not in environment or config
        if not self.sender_email:
            try:
                from models.database import Settings
                self.sender_email = Settings.get_setting('brevo_sender_email', 'emily.carter@savety.ai')
                self.sender_name = Settings.get_setting('brevo_sender_name', 'Security Team')
            except:
                self.sender_email = 'emily.carter@savety.ai'
                self.sender_name = 'Security Team'

        # Subject line configuration
        self.default_subject_prefix = os.environ.get('BREVO_SUBJECT_PREFIX', '[Security Alert]')
        self.company_name = os.environ.get('COMPANY_NAME', 'Savety')
        
        # Rate limiting
        self.last_send_time = 0
        self.min_send_interval = 1.0 / 5  # 5 emails per second max
        
        logger.info("Modern Brevo Email Service initialized successfully")

        # Initialize advanced features
        self.email_frequency_tracker = {}
        self.ab_test_campaigns = {}
        self.behavioral_triggers = {}
        
        # Industry-specific configurations
        self.industry_configs = {
            'healthcare': {
                'compliance_focus': 'HIPAA',
                'urgency_multiplier': 1.5,
                'max_daily_emails': 3,
                'regulatory_deadline': 60
            },
            'finance': {
                'compliance_focus': 'PCI DSS, SOX',
                'urgency_multiplier': 1.8,
                'max_daily_emails': 4,
                'regulatory_deadline': 30
            },
            'education': {
                'compliance_focus': 'FERPA',
                'urgency_multiplier': 1.2,
                'max_daily_emails': 2,
                'regulatory_deadline': 90
            },
            'default': {
                'compliance_focus': 'General Data Protection',
                'urgency_multiplier': 1.0,
                'max_daily_emails': 3,
                'regulatory_deadline': 72
            }
        }
    
    def generate_tracking_pixel(self, email_id: int, base_url: str = "http://localhost:5000") -> str:
        """Generate tracking pixel for email opens"""
        tracking_url = f"{base_url}/track/open/{email_id}"
        return f'<img src="{tracking_url}" width="1" height="1" alt="" style="display:none;">'
    
    def generate_unsubscribe_link(self, contact_id: int, base_url: str = "http://localhost:5000") -> str:
        """Generate unsubscribe link"""
        return f"{base_url}/unsubscribe/{contact_id}"

    def generate_subject(self, base_subject: str, contact: Dict = None, priority: str = 'normal') -> str:
        """Generate configurable email subject with variables"""
        try:
            # Start with base subject
            subject = base_subject

            # Add priority indicators
            if priority == 'critical':
                subject = f"🚨 URGENT: {subject}"
            elif priority == 'high':
                subject = f"⚠️ {subject}"

            # Add company context if available
            if contact and contact.get('company'):
                # Check if company is already in subject to avoid duplication
                if contact['company'].lower() not in subject.lower():
                    subject = f"{subject} - {contact['company']}"

            # Add prefix if configured and not already present
            if self.default_subject_prefix and not subject.startswith(self.default_subject_prefix):
                subject = f"{self.default_subject_prefix} {subject}"

            return subject

        except Exception as e:
            logger.error(f"Error generating subject: {str(e)}")
            return base_subject or f"{self.default_subject_prefix} Security Alert"
    
    def add_click_tracking(self, html_content: str, email_id: int, base_url: str = "http://localhost:5000") -> str:
        """Add click tracking to all links in HTML content"""
        try:
            import urllib.parse
            
            def replace_link(match):
                full_match = match.group(0)
                url = match.group(1)
                
                # Skip if it's already a tracking link or internal link
                if '/track/click/' in url or url.startswith('#') or url.startswith('mailto:'):
                    return full_match
                
                # Encode the URL for use in our tracking link
                encoded_url = urllib.parse.quote(url, safe='')
                tracking_url = f"{base_url}/track/click/{email_id}/{encoded_url}"
                
                return f'href="{tracking_url}"'
            
            # Replace href attributes
            pattern = r'href="([^"]*)"'
            tracked_content = re.sub(pattern, replace_link, html_content)
            
            return tracked_content
            
        except Exception as e:
            logger.error(f"Error adding click tracking: {str(e)}")
            return html_content
    
    def personalize_email_content(self, template: str, contact: Dict, breach_data: Optional[Dict] = None) -> str:
        """Personalize email content with contact data (industry-based targeting)"""
        try:
            # Contact personalization with industry-based fields
            replacements = {
                '{{first_name}}': contact.get('first_name', ''),
                '{{last_name}}': contact.get('last_name', ''),
                '{{full_name}}': f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                '{{email}}': contact.get('email', ''),
                '{{company}}': contact.get('company', ''),
                '{{domain}}': contact.get('domain', ''),
                '{{title}}': contact.get('title', ''),
                '{{industry}}': contact.get('industry', ''),
                '{{business_type}}': contact.get('business_type', ''),
                '{{company_size}}': contact.get('company_size', ''),
            }

            # Note: breach_data parameter kept for backward compatibility but not used
            if breach_data:
                logger.info("breach_data parameter is deprecated - system now uses industry-based targeting")

            # Apply replacements
            content = template
            for placeholder, value in replacements.items():
                content = content.replace(placeholder, value or '')

            return content

        except Exception as e:
            logger.error(f"Error personalizing email content: {str(e)}")
            return template
    
    def send_single_email(self,
                         to_email: str,
                         subject: str,
                         html_content: str,
                         text_content: Optional[str] = None,
                         from_email: Optional[str] = None,
                         from_name: Optional[str] = None,
                         email_id: Optional[int] = None,
                         contact_id: Optional[int] = None,
                         thread_message_id: Optional[str] = None,
                         sequence_step: Optional[int] = None) -> Tuple[bool, str]:
        """Send a single email via Brevo API"""
        
        try:
            if not self.api_key:
                return False, "Brevo API key not configured"
                
            # Rate limiting
            current_time = time.time()
            time_since_last = current_time - self.last_send_time
            if time_since_last < self.min_send_interval:
                time.sleep(self.min_send_interval - time_since_last)
            
            # Set sender info - use configurable variables
            sender_email = from_email or self.sender_email
            sender_name = from_name or self.sender_name
            
            # Handle email threading for follow-up emails
            threading_subject = subject
            if thread_message_id and sequence_step and sequence_step > 0:
                # Add "Re:" prefix for follow-up emails (if not already present)
                if not subject.lower().startswith('re:'):
                    threading_subject = f"Re: {subject}"
            
            # Generate plain text version if not provided, keep HTML as well
            if not text_content:
                text_content = self._html_to_plain_text(html_content)
            
            # Add unsubscribe link in plain text format
            if contact_id:
                unsubscribe_link = self.generate_unsubscribe_link(contact_id)
                text_content += f'\\n\\nUnsubscribe: {unsubscribe_link}'
            
            # Create the email using Brevo API format - HTML and TEXT with tracking enabled
            send_email_request = brevo_python.SendSmtpEmail(
                sender=brevo_python.SendSmtpEmailSender(name=sender_name, email=sender_email),
                to=[brevo_python.SendSmtpEmailTo(email=to_email)],
                subject=threading_subject,  # Use threading-aware subject
                html_content=html_content,  # Send HTML content
                text_content=text_content,  # Also send plain text version
                # Enable Brevo's built-in tracking
                tags=["salesbreachpro", "automated", f"campaign-{email_id}" if email_id else "manual"],
                # Enable open tracking and click tracking via Brevo
                # These will be handled by Brevo and sent to our webhook
            )
            
            # Add custom headers including threading headers
            headers = {}
            if email_id:
                headers["X-SalesBreachPro-Email-ID"] = str(email_id)
            
            # Add email threading headers for follow-up emails
            if thread_message_id and sequence_step and sequence_step > 0:
                headers["In-Reply-To"] = f"<{thread_message_id}>"
                headers["References"] = f"<{thread_message_id}>"
                logger.info(f"Adding threading headers - In-Reply-To: <{thread_message_id}>")
            
            # Generate unique Message-ID for this email (for future replies)
            import uuid
            current_message_id = f"{uuid.uuid4()}@{sender_email.split('@')[1] if '@' in sender_email else 'salesbreachpro.com'}"
            headers["Message-ID"] = f"<{current_message_id}>"
            
            if headers:
                send_email_request.headers = headers

            # Send the email via Brevo API
            api_response = self.transactional_api.send_transac_email(send_email_request)
            
            self.last_send_time = time.time()
            
            logger.info(f"Email sent successfully to {to_email} via Brevo API. Message ID: {api_response.message_id}")

            # Store message ID in database if email_id provided
            if email_id:
                try:
                    from models.database import db, Email
                    from datetime import datetime
                    email_record = Email.query.get(email_id)
                    if email_record:
                        email_record.brevo_message_id = api_response.message_id
                        # Store our custom Message-ID for threading purposes
                        email_record.thread_message_id = current_message_id
                        email_record.status = 'sent'
                        email_record.sent_at = datetime.utcnow()
                        db.session.commit()
                        logger.info(f"Stored Brevo message ID {api_response.message_id} and thread ID {current_message_id} for Email {email_id}")
                    else:
                        logger.warning(f"Email record {email_id} not found for message ID storage")
                except Exception as db_error:
                    logger.error(f"Error storing message ID in database: {str(db_error)}")

            # Return both message IDs for threading support
            return True, {"brevo_message_id": api_response.message_id, "thread_message_id": current_message_id}
            
        except ApiException as e:
            logger.error(f"Brevo API error for {to_email}: {str(e)}")
            return False, f"Brevo API error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error sending email to {to_email}: {str(e)}")
            return False, f"Unexpected error: {str(e)}"
    
    def send_campaign_emails(self, 
                           campaign_id: int,
                           emails_data: List[Dict],
                           batch_size: int = 10) -> Dict[str, int]:
        """Send batch of campaign emails via Brevo"""
        
        results = {
            'sent': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            from models.database import db, Email, Contact, Campaign
            
            # Process emails in batches
            for i in range(0, len(emails_data), batch_size):
                batch = emails_data[i:i + batch_size]
                
                for email_data in batch:
                    try:
                        # Send email
                        success, message = self.send_single_email(
                            to_email=email_data['contact']['email'],
                            subject=email_data['subject'],
                            html_content=email_data['html_content'],
                            text_content=email_data.get('text_content'),
                            from_email=email_data.get('from_email'),
                            from_name=email_data.get('from_name'),
                            email_id=email_data.get('email_id'),
                            contact_id=email_data['contact']['id']
                        )
                        
                        # Update database
                        if success:
                            # The message variable now contains the actual message ID from Brevo API
                            brevo_message_id = message if success else None
                            
                            # Update email status
                            email = Email.query.get(email_data['email_id'])
                            if email:
                                email.status = 'sent'
                                email.sent_at = datetime.utcnow()
                                if brevo_message_id:
                                    email.brevo_message_id = brevo_message_id
                                db.session.commit()
                            
                            results['sent'] += 1
                            
                            # Update contact last contacted
                            contact = Contact.query.get(email_data['contact']['id'])
                            if contact:
                                contact.last_contacted = datetime.utcnow()
                                db.session.commit()
                        else:
                            # Update email status to failed
                            email = Email.query.get(email_data['email_id'])
                            if email:
                                email.status = 'failed'
                                db.session.commit()
                            
                            results['failed'] += 1
                            results['errors'].append({
                                'email': email_data['contact']['email'],
                                'error': message
                            })
                        
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append({
                            'email': email_data['contact']['email'],
                            'error': str(e)
                        })
                        logger.error(f"Error processing email for {email_data['contact']['email']}: {str(e)}")
                
                # Small delay between batches
                if i + batch_size < len(emails_data):
                    time.sleep(1)
            
            # Update campaign statistics
            campaign = Campaign.query.get(campaign_id)
            if campaign:
                campaign.sent_count += results['sent']
                db.session.commit()
            
            logger.info(f"Campaign {campaign_id} batch completed: {results['sent']} sent, {results['failed']} failed")
            
        except Exception as e:
            logger.error(f"Error in send_campaign_emails: {str(e)}")
            results['errors'].append({'error': f"Batch processing error: {str(e)}"})
        
        return results
    
    def send_test_email(self, to_email: str) -> Tuple[bool, str]:
        """Send a test email to verify Brevo configuration"""
        
        html_content = """
        <html>
        <body>
            <h2>🎉 SalesBreachPro Email Test</h2>
            <p>Congratulations! Your Brevo integration is working correctly.</p>
            <p>This test email confirms that:</p>
            <ul>
                <li>✅ Brevo API connection is established</li>
                <li>✅ Authentication is successful</li>
                <li>✅ Email delivery is functional</li>
                <li>✅ Using modern brevo-python SDK</li>
            </ul>
            <p>You're ready to start sending campaign emails with advanced tracking!</p>
            <br>
            <p><strong>API Key Used:</strong> {api_key_preview}...</p>
            <br>
            <p><small>Sent from SalesBreachPro via Brevo API at {timestamp}</small></p>
        </body>
        </html>
        """.format(
            api_key_preview=self.api_key[:20] if self.api_key else "Not configured",
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        text_content = f"""
        SalesBreachPro Email Test
        
        Congratulations! Your Brevo integration is working correctly.
        
        This test email confirms that:
        - Brevo API connection is established
        - Authentication is successful  
        - Email delivery is functional
        - Using modern brevo-python SDK
        
        API Key Used: {self.api_key[:20] if self.api_key else "Not configured"}...
        
        You're ready to start sending campaign emails with advanced tracking!
        
        Sent from SalesBreachPro via Brevo API at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        return self.send_single_email(
            to_email=to_email,
            subject="✅ SalesBreachPro + Brevo API Test - Success!",
            html_content=html_content,
            text_content=text_content
        )
    
    def get_account_info(self) -> Dict:
        """Get Brevo account information"""
        try:
            if not self.api_key:
                return {'success': False, 'error': 'API key not configured'}
                
            account_info = self.account_api.get_account()
            return {
                'success': True,
                'account': {
                    'plan_type': account_info.plan[0].type if account_info.plan else 'Unknown',
                    'credits': account_info.plan[0].credits if account_info.plan else 0,
                    'credits_type': account_info.plan[0].credits_type if account_info.plan else 'Unknown',
                    'email': account_info.email,
                    'first_name': account_info.first_name,
                    'last_name': account_info.last_name,
                    'company_name': account_info.company_name
                }
            }
        except ApiException as e:
            logger.error(f"Error getting Brevo account info: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error getting account info: {str(e)}")
            return {'success': False, 'error': str(e)}


    # ===== ADVANCED EMAIL PIPELINE FEATURES =====

    def schedule_breach_sequence(self, contact: Dict, breach_data: Dict) -> Dict:
        """
        DEPRECATED: Breach-based sequencing has been replaced with industry-based targeting.
        This method is kept for backward compatibility but returns a deprecation notice.
        """
        logger.warning("schedule_breach_sequence is deprecated - use industry-based targeting instead")
        return {
            'success': False,
            'error': 'Breach-based sequencing is deprecated. Please use industry-based campaign targeting instead.',
            'deprecated': True
        }

    def schedule_breach_sequence_OLD_DISABLED(self, contact: Dict, breach_data: Dict) -> Dict:
        """OLD METHOD - Disabled breach-based sequence scheduling"""
        try:
            risk_score = float(breach_data.get('risk_score', 0))
            industry = contact.get('industry', 'default').lower()
            
            # Get industry-specific configuration
            industry_config = self.industry_configs.get(industry, self.industry_configs['default'])
            
            # Calculate urgency-adjusted timeline
            urgency_multiplier = industry_config['urgency_multiplier']
            
            if risk_score >= 8:
                # CRITICAL: Immediate sequence
                schedule = [
                    {
                        'delay_hours': 0,
                        'template_type': 'urgent_breach_alert',
                        'priority': 'critical',
                        'subject': f'🚨 CRITICAL: {breach_data.get("breach_name", "Security Breach")} Affects {contact.get("company", "Your Organization")}'
                    },
                    {
                        'delay_hours': int(2 / urgency_multiplier),
                        'template_type': 'immediate_action_required',
                        'priority': 'high',
                        'subject': f'Immediate Action Required: {contact.get("company")} Security Response'
                    },
                    {
                        'delay_hours': int(24 / urgency_multiplier),
                        'template_type': 'security_assessment_offer',
                        'priority': 'high',
                        'subject': f'Emergency Security Assessment - {contact.get("company")}'
                    }
                ]
            elif risk_score >= 6:
                # HIGH: Measured approach
                schedule = [
                    {
                        'delay_hours': 0,
                        'template_type': 'breach_notification',
                        'priority': 'high',
                        'subject': f'Security Alert: {breach_data.get("breach_name")} - {contact.get("company")}'
                    },
                    {
                        'delay_hours': int(48 / urgency_multiplier),
                        'template_type': 'security_consultation',
                        'priority': 'medium',
                        'subject': f'Security Consultation Available for {contact.get("company")}'
                    },
                    {
                        'delay_hours': int(168 / urgency_multiplier),  # 1 week
                        'template_type': 'compliance_reminder',
                        'priority': 'medium',
                        'subject': f'{industry_config["compliance_focus"]} Compliance Review - {contact.get("company")}'
                    }
                ]
            else:
                # MEDIUM/LOW: Educational approach
                schedule = [
                    {
                        'delay_hours': 0,
                        'template_type': 'security_awareness',
                        'priority': 'normal',
                        'subject': f'Security Update for {contact.get("company")}'
                    },
                    {
                        'delay_hours': int(72 / urgency_multiplier),  # 3 days
                        'template_type': 'preventive_security',
                        'priority': 'normal',
                        'subject': f'Strengthen {contact.get("company")} Security Posture'
                    }
                ]
            
            # Schedule each email in sequence
            scheduled_emails = []
            base_time = datetime.now()
            
            for step in schedule:
                send_time = base_time + timedelta(hours=step['delay_hours'])
                
                # Create personalized content
                personalized_content = self.create_dynamic_content(
                    step['template_type'], contact, breach_data, industry_config
                )
                
                # Schedule email
                scheduled_email = self.schedule_single_email(
                    contact=contact,
                    subject=step['subject'],
                    content=personalized_content,
                    send_time=send_time,
                    priority=step['priority']
                )
                
                scheduled_emails.append(scheduled_email)
                
                logger.info(f"Scheduled {step['template_type']} for {contact.get('email')} at {send_time}")
            
            return {
                'success': True,
                'emails_scheduled': len(scheduled_emails),
                'sequence_type': f'risk_score_{int(risk_score)}',
                'industry': industry,
                'urgency_multiplier': urgency_multiplier
            }
            
        except Exception as e:
            logger.error(f"Error scheduling breach sequence: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def create_dynamic_content(self, template_type: str, contact: Dict, breach_data: Dict, industry_config: Dict) -> str:
        """Create dynamic email content based on template type and context"""
        
        # Base template structures for different types
        templates = {
            'urgent_breach_alert': {
                'html': '''
                <div style="border-left: 5px solid #ff0000; padding: 20px; font-family: Arial, sans-serif;">
                    <h2 style="color: #ff0000;">🚨 CRITICAL SECURITY ALERT</h2>
                    <div style="background: #ffeeee; padding: 15px; margin: 15px 0; border-radius: 5px;">
                        <h3>Immediate Action Required for {{company}}</h3>
                        <p><strong>{{breach_name}}</strong> data breach has been detected affecting your organization.</p>
                        
                        <div style="background: white; padding: 10px; margin: 10px 0; border-radius: 3px;">
                            <p><strong>Risk Score:</strong> {{risk_score}}/10 (Critical)</p>
                            <p><strong>Records Affected:</strong> {{records_affected}}</p>
                            <p><strong>Data Types:</strong> {{data_types}}</p>
                            <p><strong>{{compliance_focus}} Impact:</strong> Immediate compliance review required</p>
                        </div>
                        
                        <p style="font-weight: bold; color: #ff0000;">
                            Your organization has {{regulatory_deadline}} days to respond to potential compliance violations.
                        </p>
                    </div>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="{{emergency_call_link}}" style="background: #ff0000; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                            🚨 EMERGENCY SECURITY CALL - AVAILABLE NOW
                        </a>
                    </div>
                    
                    <p style="font-size: 12px; color: #666;">
                        This is an automated security alert. Our team is standing by for immediate consultation.
                    </p>
                </div>
                '''
            },
            'breach_notification': {
                'html': '''
                <div style="border-left: 5px solid #ff6600; padding: 20px; font-family: Arial, sans-serif;">
                    <h2 style="color: #ff6600;">⚠️ Security Alert for {{company}}</h2>
                    
                    <p>Hello {{first_name}},</p>
                    <p>We've identified that {{company}} may be affected by the recent <strong>{{breach_name}}</strong> security incident.</p>
                    
                    <div style="background: #fff8e1; padding: 15px; margin: 15px 0; border-radius: 5px;">
                        <h4>Breach Details:</h4>
                        <ul>
                            <li><strong>Risk Level:</strong> {{risk_score}}/10</li>
                            <li><strong>Potential Records:</strong> {{records_affected}}</li>
                            <li><strong>Data Categories:</strong> {{data_types}}</li>
                        </ul>
                        
                        <p><strong>{{compliance_focus}} Consideration:</strong> 
                        We recommend reviewing your data protection protocols within {{regulatory_deadline}} days.</p>
                    </div>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="{{assessment_link}}" style="background: #0066cc; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px;">
                            Schedule Free Security Assessment
                        </a>
                    </div>
                </div>
                '''
            },
            'security_consultation': {
                'html': '''
                <div style="border-left: 5px solid #0066cc; padding: 20px; font-family: Arial, sans-serif;">
                    <h2 style="color: #0066cc;">Security Consultation Available for {{company}}</h2>
                    
                    <p>Hello {{first_name}},</p>
                    <p>Following up on the {{breach_name}} security alert, our cybersecurity experts are available to help {{company}} assess and strengthen your security posture.</p>
                    
                    <div style="background: #f0f8ff; padding: 15px; margin: 15px 0; border-radius: 5px;">
                        <h4>What We'll Cover:</h4>
                        <ul>
                            <li>Comprehensive security assessment</li>
                            <li>{{compliance_focus}} compliance review</li>
                            <li>Risk mitigation strategies</li>
                            <li>Employee security training recommendations</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="{{consultation_link}}" style="background: #0066cc; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px;">
                            Book Your Consultation
                        </a>
                    </div>
                </div>
                '''
            },
            'security_awareness': {
                'html': '''
                <div style="border-left: 5px solid #28a745; padding: 20px; font-family: Arial, sans-serif;">
                    <h2 style="color: #28a745;">Security Update for {{company}}</h2>
                    
                    <p>Hello {{first_name}},</p>
                    <p>We wanted to inform you about recent security developments that may be relevant to {{company}}.</p>
                    
                    <div style="background: #f8fff8; padding: 15px; margin: 15px 0; border-radius: 5px;">
                        <h4>Recent Security Insight:</h4>
                        <p>The {{breach_name}} incident highlights the importance of proactive security measures in the {{industry}} sector.</p>
                        
                        <p><strong>Key Takeaways:</strong></p>
                        <ul>
                            <li>Regular security audits can prevent 80% of breaches</li>
                            <li>{{compliance_focus}} compliance is increasingly scrutinized</li>
                            <li>Employee training reduces risk by 60%</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="{{security_guide_link}}" style="background: #28a745; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px;">
                            Download Security Best Practices Guide
                        </a>
                    </div>
                </div>
                '''
            }
        }
        
        # Get template
        template = templates.get(template_type, templates['breach_notification'])
        
        # Replace variables
        content = template['html']
        
        # Contact variables
        content = content.replace('{{company}}', contact.get('company', 'Your Organization'))
        content = content.replace('{{first_name}}', contact.get('first_name', 'there'))
        content = content.replace('{{email}}', contact.get('email', ''))
        
        # Breach variables
        content = content.replace('{{breach_name}}', breach_data.get('breach_name', 'Security Incident'))
        content = content.replace('{{risk_score}}', str(breach_data.get('risk_score', 'Unknown')))
        content = content.replace('{{records_affected}}', str(breach_data.get('records_affected', 'Multiple')))
        content = content.replace('{{data_types}}', breach_data.get('data_types', 'Various data types'))
        
        # Industry variables
        content = content.replace('{{compliance_focus}}', industry_config['compliance_focus'])
        content = content.replace('{{regulatory_deadline}}', str(industry_config['regulatory_deadline']))
        content = content.replace('{{industry}}', contact.get('industry', 'business'))
        
        # Action links (these would be generated based on contact ID)
        contact_id = contact.get('id', 'unknown')
        content = content.replace('{{emergency_call_link}}', f'https://app.com/emergency-call/{contact_id}')
        content = content.replace('{{assessment_link}}', f'https://app.com/assessment/{contact_id}')
        content = content.replace('{{consultation_link}}', f'https://app.com/consultation/{contact_id}')
        content = content.replace('{{security_guide_link}}', f'https://app.com/security-guide/{contact_id}')
        
        return content
    
    def schedule_single_email(self, contact: Dict, subject: str, content: str, send_time: datetime, priority: str) -> Dict:
        """Schedule a single email with advanced options"""
        try:
            # Check frequency limits
            if not self.check_frequency_limits(contact['email'], priority):
                logger.warning(f"Frequency limit reached for {contact['email']}, queuing for later")
                return {'queued': True, 'reason': 'frequency_limit'}
            
            # Create email with scheduling using Brevo API
            # Note: SendSmtpEmail is the Brevo SDK class name, not SMTP protocol
            email_request = brevo_python.SendSmtpEmail(
                sender=brevo_python.SendSmtpEmailSender(
                    name=self.sender_name,
                    email=self.sender_email
                ),
                to=[brevo_python.SendSmtpEmailTo(email=contact['email'])],
                subject=subject,
                html_content=content,
                scheduled_at=send_time.isoformat()
            )
            
            # Add priority headers
            if priority == 'critical':
                email_request.headers = {
                    'X-Priority': '1',
                    'X-MSMail-Priority': 'High',
                    'Importance': 'high'
                }

            # Send scheduled email via Brevo API
            response = self.transactional_api.send_transac_email(email_request)
            
            # Track in frequency counter
            self.track_email_frequency(contact['email'])
            
            return {
                'success': True,
                'message_id': response.message_id if hasattr(response, 'message_id') else None,
                'scheduled_for': send_time.isoformat(),
                'priority': priority
            }
            
        except Exception as e:
            logger.error(f"Error scheduling email: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def check_frequency_limits(self, email: str, priority: str) -> bool:
        """Check if email frequency limits allow sending"""
        today = datetime.now().date()
        email_key = f"{email}_{today}"
        
        # Get current count
        current_count = self.email_frequency_tracker.get(email_key, 0)
        
        # Set limits based on priority
        if priority == 'critical':
            daily_limit = 5  # Allow more for critical emails
        else:
            daily_limit = 3  # Standard limit
        
        return current_count < daily_limit
    
    def track_email_frequency(self, email: str):
        """Track email frequency for rate limiting"""
        today = datetime.now().date()
        email_key = f"{email}_{today}"
        
        self.email_frequency_tracker[email_key] = self.email_frequency_tracker.get(email_key, 0) + 1
    
    def setup_behavioral_triggers(self) -> Dict:
        """Setup behavioral email triggers"""
        try:
            triggers = {
                'email_opened_no_click': {
                    'condition': 'email_opened = true AND link_clicked = false',
                    'delay_hours': 4,
                    'template_type': 'simplified_cta',
                    'description': 'Send simplified CTA if email opened but no clicks'
                },
                'link_clicked_no_response': {
                    'condition': 'link_clicked = true AND no_reply_after = 48h',
                    'delay_hours': 48,
                    'template_type': 'calendar_reminder',
                    'description': 'Remind to book calendar if clicked but no response'
                },
                'multiple_opens': {
                    'condition': 'email_opened_count >= 3',
                    'delay_hours': 1,
                    'template_type': 'priority_contact',
                    'description': 'Offer priority contact for highly engaged prospects'
                }
            }
            
            # Store triggers for processing
            self.behavioral_triggers = triggers
            
            logger.info(f"Setup {len(triggers)} behavioral triggers")
            return {'success': True, 'triggers_count': len(triggers)}
            
        except Exception as e:
            logger.error(f"Error setting up behavioral triggers: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_advanced_analytics(self, campaign_id: str = None, days: int = 30) -> Dict:
        """Get advanced email analytics"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get email events
            events = self.transactional_api.get_email_event_report(
                limit=1000,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            )
            
            # Calculate advanced metrics
            analytics = {
                'basic_metrics': {
                    'total_sent': 0,
                    'delivered': 0,
                    'opened': 0,
                    'clicked': 0,
                    'replied': 0,
                    'bounced': 0
                },
                'advanced_metrics': {
                    'delivery_rate': 0,
                    'open_rate': 0,
                    'click_rate': 0,
                    'reply_rate': 0,
                    'engagement_score': 0
                },
                'industry_breakdown': {},
                'campaign_performance': {
                    'avg_response_time_hours': 0,
                    'conversion_rate': 0,
                    'engagement_by_industry': {}
                },
                'time_analysis': {
                    'best_send_hour': 0,
                    'best_send_day': '',
                    'response_time_distribution': {}
                }
            }
            
            # Process events if available
            if hasattr(events, 'events') and events.events:
                self.process_email_events(events.events, analytics)
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting advanced analytics: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def process_email_events(self, events: List, analytics: Dict):
        """Process email events for advanced analytics"""
        for event in events:
            event_type = event.get('event', '')
            
            if event_type == 'delivered':
                analytics['basic_metrics']['delivered'] += 1
            elif event_type == 'opened':
                analytics['basic_metrics']['opened'] += 1
            elif event_type == 'clicked':
                analytics['basic_metrics']['clicked'] += 1
            elif event_type == 'replied':
                analytics['basic_metrics']['replied'] += 1
            elif event_type == 'bounced':
                analytics['basic_metrics']['bounced'] += 1
        
        # Calculate rates
        delivered = analytics['basic_metrics']['delivered']
        if delivered > 0:
            analytics['advanced_metrics']['open_rate'] = (analytics['basic_metrics']['opened'] / delivered) * 100
            analytics['advanced_metrics']['click_rate'] = (analytics['basic_metrics']['clicked'] / delivered) * 100
            analytics['advanced_metrics']['reply_rate'] = (analytics['basic_metrics']['replied'] / delivered) * 100
    
    def _html_to_plain_text(self, html_content):
        """Convert HTML to properly formatted plain text"""
        if not html_content:
            return ""
        
        # Start with the HTML content
        text = html_content
        
        # Convert paragraph tags to double line breaks
        text = re.sub(r'<p[^>]*>\s*', '', text)  # Remove opening p tags
        text = re.sub(r'\s*</p>', '\n\n', text)  # Convert closing p tags to double newlines
        
        # Convert br tags to single line breaks
        text = re.sub(r'<br[^>]*/?>', '\n', text)
        
        # Convert list items to bullet points
        text = re.sub(r'<li[^>]*>', '• ', text)
        text = re.sub(r'</li>', '\n', text)
        
        # Remove other HTML tags
        text = re.sub(r'<[^<]+?>', '', text)
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Replace multiple newlines with double
        text = re.sub(r'[ \t]+', ' ', text)  # Replace multiple spaces/tabs with single space
        text = text.strip()  # Remove leading/trailing whitespace
        
        return text


def create_email_service(config):
    """Factory function to create modern Brevo email service"""
    return BrevoModernService(config)