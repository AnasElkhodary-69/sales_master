"""
Email Sequence Service - Core workflow engine for the new configurable email system
Handles contact enrollment, sequence scheduling, and FlawTrack integration
"""
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
from flask import current_app
from models.database import (
    db, Contact, Campaign, EmailSequence, ContactCampaignStatus,
    EmailSequenceConfig, SequenceStep, EmailTemplate, Email
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailSequenceService:
    """Manages email sequences for contacts in campaigns"""
    
    def __init__(self):
        logger.info("Email Sequence Service initialized")
    
    def _calculate_delay_timedelta(self, delay_amount: int, delay_unit: str) -> timedelta:
        """Convert delay amount and unit to timedelta object"""
        if not delay_amount or delay_amount <= 0:
            return timedelta(0)
        
        unit = delay_unit.lower()
        if unit in ['minute', 'minutes', 'min']:
            return timedelta(minutes=delay_amount)
        elif unit in ['hour', 'hours', 'hr']:
            return timedelta(hours=delay_amount)
        elif unit in ['day', 'days']:
            return timedelta(days=delay_amount)
        else:
            # Default to days if unit is unrecognized
            logger.warning(f"Unrecognized delay unit '{delay_unit}', defaulting to days")
            return timedelta(days=delay_amount)
    
    def _get_effective_delay(self, template: EmailTemplate) -> timedelta:
        """Get the effective delay for a template, prioritizing new delay_amount/delay_unit"""
        # Use new delay system if available
        if hasattr(template, 'delay_amount') and hasattr(template, 'delay_unit'):
            if template.delay_amount and template.delay_amount > 0:
                return self._calculate_delay_timedelta(template.delay_amount, template.delay_unit)
        
        # Fall back to old delay_days system
        if template.delay_days and template.delay_days > 0:
            return timedelta(days=template.delay_days)
        
        # No delay
        return timedelta(0)
    
    def _get_delay_info(self, template: EmailTemplate) -> Dict:
        """Get delay information for display/logging purposes"""
        # Use new delay system if available
        if hasattr(template, 'delay_amount') and hasattr(template, 'delay_unit'):
            if template.delay_amount and template.delay_amount > 0:
                return {
                    'amount': template.delay_amount,
                    'unit': template.delay_unit
                }
        
        # Fall back to old delay_days system
        if template.delay_days and template.delay_days > 0:
            return {
                'amount': template.delay_days,
                'unit': 'days'
            }
        
        # No delay
        return {
            'amount': 0,
            'unit': 'days'
        }
    
    def enroll_contact_in_campaign(self, contact_id: int, campaign_id: int, 
                                 force_breach_check: bool = True) -> Dict:
        """
        Main entry point: Enroll contact and start their sequence
        
        Args:
            contact_id: ID of contact to enroll
            campaign_id: ID of campaign to enroll in
            force_breach_check: Whether to check FlawTrack for breach status
            
        Returns:
            Dict with enrollment results and scheduled emails count
        """
        try:
            # Get contact and campaign
            contact = Contact.query.get(contact_id)
            campaign = Campaign.query.get(campaign_id)
            
            if not contact or not campaign:
                return {
                    'success': False,
                    'error': f'Contact {contact_id} or Campaign {campaign_id} not found'
                }
            
            # Check if contact is already enrolled
            existing_status = ContactCampaignStatus.query.filter_by(
                contact_id=contact_id, 
                campaign_id=campaign_id
            ).first()
            
            if existing_status:
                return {
                    'success': False,
                    'error': f'Contact {contact.email} already enrolled in campaign {campaign.name}'
                }
            
            # Step 1: Check FlawTrack for breach status
            breach_status = self.check_contact_breach_status(contact, force_breach_check)
            
            # Step 2: Create contact campaign status record
            contact_status = ContactCampaignStatus(
                contact_id=contact_id,
                campaign_id=campaign_id,
                breach_status=breach_status['status'],
                current_sequence_step=0,
                flawtrack_checked_at=datetime.utcnow(),
                breach_data=breach_status.get('data')
            )
            db.session.add(contact_status)
            db.session.flush()
            
            # Step 3: Schedule email sequence (scheduler will handle sending all emails)
            # Use contact's breach_status directly to match template risk_level
            risk_level = breach_status['status']  # 'breached', 'unknown', or 'not_breached'
            scheduled_emails = self.schedule_email_sequence(
                contact_id, campaign_id, risk_level
            )
            
            # Note: All emails (including immediate ones) are handled by the scheduler
            # This prevents duplicate sending and ensures consistent processing
            
            # Step 4: Update campaign stats
            campaign.total_contacts = Campaign.query.get(campaign_id).total_contacts + 1
            
            db.session.commit()
            
            logger.info(f"Successfully enrolled {contact.email} in {campaign.name} with {len(scheduled_emails)} emails scheduled")
            
            return {
                'success': True,
                'contact_id': contact_id,
                'campaign_id': campaign_id,
                'breach_status': breach_status['status'],
                'template_type': risk_level,
                'emails_scheduled': len(scheduled_emails),
                'sequence_source': 'Template-based sequence'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error enrolling contact {contact_id} in campaign {campaign_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_contact_breach_status(self, contact: Contact, force_check: bool = True) -> Dict:
        """
        Check if contact's domain/email appears in breaches via FlawTrack
        
        Args:
            contact: Contact object to check
            force_check: Whether to force FlawTrack API call
            
        Returns:
            Dict with breach status and data
        """
        try:
            # If force_check is False and we have recent data, use cached result
            if not force_check and contact.breach_status:
                return {
                    'status': contact.breach_status,
                    'data': {'cached': True, 'source': 'existing_contact_data'}
                }
            
            # Try to use FlawTrack service if available
            try:
                from services.flawtrack_api import FlawTrackAPI
                from models.database import Settings
                
                # Get FlawTrack API credentials from settings
                api_key = Settings.get_setting('flawtrack_api_key', '')
                endpoint = Settings.get_setting('flawtrack_endpoint', '')
                
                if not api_key or not endpoint:
                    logger.warning("FlawTrack API not configured - add API key and endpoint in settings")
                    return {
                        'status': contact.breach_status or 'unknown',
                        'data': {'source': 'flawtrack_not_configured'}
                    }
                
                flawtrack = FlawTrackAPI(api_key, endpoint)
                domain = contact.domain or contact.email.split('@')[1]
                
                # Check domain for breaches
                breach_data = flawtrack.get_breach_data(domain)
                
                if breach_data:
                    # Process breach data and calculate risk
                    risk_score = flawtrack.calculate_risk_score(breach_data)
                    processed_data = flawtrack.process_breach_data(domain, breach_data, risk_score)
                    
                    # Cache the breach data
                    flawtrack.cache_breach_data(domain, processed_data)
                    
                    # Determine status based on risk score
                    if risk_score >= 6.0:
                        status = 'breached'
                    elif risk_score >= 3.0:
                        status = 'at_risk'
                    else:
                        status = 'breached'  # Any breach is considered breached
                    
                    return {
                        'status': status,
                        'data': {
                            'breach_data': processed_data,
                            'risk_score': risk_score,
                            'source': 'flawtrack_api',
                            'domain': domain
                        }
                    }
                else:
                    return {
                        'status': 'unknown',
                        'data': {'source': 'no_data_available'}
                    }
                    
            except ImportError:
                logger.warning("FlawTrack API not available, using contact's existing breach status")
            except Exception as e:
                logger.warning(f"FlawTrack API error: {str(e)}, using contact's existing breach status")
            
            # Fallback to contact's existing breach status
            fallback_status = contact.breach_status or 'unknown'
            
            # Map existing status to new system
            if fallback_status in ['high', 'medium']:
                return {
                    'status': 'breached',
                    'data': {'source': 'existing_contact_status', 'original': fallback_status}
                }
            elif fallback_status == 'low':
                return {
                    'status': 'clean', 
                    'data': {'source': 'existing_contact_status', 'original': fallback_status}
                }
            else:
                return {
                    'status': 'unknown',
                    'data': {'source': 'no_data_available'}
                }
                
        except Exception as e:
            logger.error(f"Error checking breach status for {contact.email}: {str(e)}")
            return {
                'status': 'unknown',
                'data': {'error': str(e)}
            }
    
    def schedule_email_sequence(self, contact_id: int, campaign_id: int, 
                              risk_level: str) -> List[Dict]:
        """
        Schedule all emails in the sequence for a contact
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID  
            risk_level: Contact's risk level ('breached', 'unknown', 'not_breached')
            
        Returns:
            List of scheduled email records
        """
        try:
            campaign = Campaign.query.get(campaign_id)
            
            # Get templates for this campaign sequence (based on risk_level)
            # Find templates that match the contact's risk_level and are active
            # Order by sequence_step to ensure correct template selection during sending
            templates = EmailTemplate.query.filter_by(
                active=True,
                risk_level=risk_level  # 'breached', 'unknown', or 'not_breached'
            ).order_by(EmailTemplate.sequence_step).all()
            
            # If no templates found for specific risk_level, try generic templates
            if not templates:
                templates = EmailTemplate.query.filter_by(
                    active=True,
                    risk_level='generic'
                ).order_by(EmailTemplate.sequence_step).all()
            
            # If still no templates, try any active templates
            if not templates:
                templates = EmailTemplate.query.filter_by(
                    active=True
                ).order_by(EmailTemplate.sequence_step).all()
            
            if not templates:
                logger.error(f"No active email templates found for risk level '{risk_level}'")
                return []
            
            # CRITICAL UNIQUENESS CHECK: Prevent duplicate sequences per contact-campaign
            existing_sequences = EmailSequence.query.filter_by(
                contact_id=contact_id,
                campaign_id=campaign_id
            ).all()
            
            if existing_sequences:
                logger.warning(f"DUPLICATE PREVENTION - Contact {contact_id} already has {len(existing_sequences)} EmailSequence records for campaign {campaign_id}")
                
                # Check if any sequences are still active (only scheduled/processing, not sent)
                active_sequences = [seq for seq in existing_sequences if seq.status in ['scheduled', 'processing']]
                if active_sequences:
                    logger.warning(f"ENROLLMENT BLOCKED - Contact {contact_id} has {len(active_sequences)} active sequences for campaign {campaign_id}. No re-enrollment allowed.")
                    return []
                else:
                    logger.info(f"All existing sequences for contact {contact_id} are completed/failed, allowing re-enrollment")
            
            # Check ContactCampaignStatus to prevent re-enrollment of active contacts
            contact_status = ContactCampaignStatus.query.filter_by(
                contact_id=contact_id,
                campaign_id=campaign_id
            ).first()
            
            if contact_status and contact_status.current_sequence_step > 0:
                logger.warning(f"ENROLLMENT BLOCKED - Contact {contact_id} is already enrolled in campaign {campaign_id} at step {contact_status.current_sequence_step}")
                return []
            
            scheduled_emails = []
            last_scheduled_datetime = datetime.utcnow()  # Start from now for the first email
            
            for i, template in enumerate(templates):
                # Use new flexible delay system
                delay = self._get_effective_delay(template)
                
                # SPECIAL CASE: First email (step 0) should be immediate for responsive engagement
                # Override delay for the first template to ensure immediate sending
                if i == 0:
                    delay = timedelta(0)  # First email is always immediate
                    logger.info(f"Step {i} ({template.name}): Overriding delay to 0 for immediate sending")
                
                # SEQUENTIAL TIMING: Each email is scheduled relative to the previous one
                scheduled_datetime = last_scheduled_datetime + delay
                scheduled_date = scheduled_datetime.date()
                
                # Check for duplicate before creating (prevent duplicate initial email)
                existing = EmailSequence.query.filter_by(
                    contact_id=contact_id,
                    campaign_id=campaign_id,
                    sequence_step=i
                ).first()
                
                if existing:
                    logger.warning(f"EmailSequence already exists for contact {contact_id}, campaign {campaign_id}, step {i}. Skipping duplicate.")
                    continue
                
                # Create email sequence record
                email_sequence = EmailSequence(
                    contact_id=contact_id,
                    campaign_id=campaign_id,
                    sequence_step=i,  # Step number based on template order
                    template_type=risk_level,  # Store risk_level in template_type field for compatibility
                    scheduled_date=scheduled_date,
                    scheduled_datetime=scheduled_datetime,  # Store precise datetime for flexible delays
                    status='scheduled'
                )
                
                db.session.add(email_sequence)
                
                # Get delay information for reporting
                delay_info = self._get_delay_info(template)
                
                # DEBUG LOGGING: Log exact scheduled time for each step
                logger.info(f"Step {i} ({template.name}): scheduled for {scheduled_datetime.isoformat()} "
                          f"(+{delay_info['amount']} {delay_info['unit']} from previous)")
                
                scheduled_emails.append({
                    'step': i,
                    'step_name': template.name,
                    'scheduled_date': scheduled_date.isoformat(),
                    'scheduled_datetime': scheduled_datetime.isoformat(),  # Add precise time to output
                    'delay_days': template.delay_days,  # Legacy field
                    'delay_amount': delay_info['amount'],
                    'delay_unit': delay_info['unit'],
                    'template_type': risk_level
                })
                
                # Update last_scheduled for next iteration
                last_scheduled_datetime = scheduled_datetime
            
            # Enhanced logging for debugging
            logger.info(f"Scheduled {len(scheduled_emails)} emails for contact {contact_id} in campaign {campaign_id}")
            logger.info(f"Email sequence timeline: {[e['scheduled_datetime'] for e in scheduled_emails]}")
            
            # Verify database entries were created correctly
            db_sequences = EmailSequence.query.filter_by(
                contact_id=contact_id,
                campaign_id=campaign_id
            ).order_by(EmailSequence.sequence_step).all()
            
            logger.info("=== SCHEDULED EMAIL SEQUENCE VERIFICATION ===")
            for seq in db_sequences:
                logger.info(f"  Step {seq.sequence_step}: {seq.scheduled_datetime} (status: {seq.status})")
            logger.info("============================================")
            
            return scheduled_emails
            
        except Exception as e:
            logger.error(f"Error scheduling email sequence: {str(e)}")
            return []
    
    def send_immediate_email(self, contact_id: int, campaign_id: int, template_type: str):
        """DISABLED: Send the first email immediately upon enrollment
        
        This method was causing duplication and timing issues.
        All emails now go through the email processor for consistent scheduling.
        """
        logger.info(f"Immediate email sending disabled - all emails handled by scheduler")
        return  # DISABLED to prevent duplication and timing issues
        
        # COMMENTED OUT - this code was causing the duplication and timing problems
        # try:
        #     from services.email_service import create_email_service
        #     from models.database import Email
        #     
        #     contact = Contact.query.get(contact_id)
        #     campaign = Campaign.query.get(campaign_id)
        #     
        #     # Get the first template (initial email) - use same logic as schedule method
        #     template = EmailTemplate.query.filter_by(
        #         active=True,
        #         breach_template_type=template_type
        #     ).order_by(EmailTemplate.delay_days).first()
        #     
        #     if not template:
        #         # Try generic template
        #         template = EmailTemplate.query.filter_by(
        #             active=True,
        #             risk_level='generic'
        #         ).order_by(EmailTemplate.delay_days).first()
        #     
        #     if not template:
        #         # Try any active template as fallback
        #         template = EmailTemplate.query.filter_by(
        #             active=True
        #         ).order_by(EmailTemplate.delay_days).first()
        #     
        #     if not template:
        #         logger.warning(f"No initial template found for immediate sending")
        #         return
        #     
        #     # Create email record
        #     email = Email(
        #         contact_id=contact_id,
        #         campaign_id=campaign_id,
        #         template_id=template.id,
        #         email_type='initial',
        #         subject=self.personalize_content(template.subject_line, contact),
        #         body=self.personalize_content(template.email_body, contact),
        #         status='sending'
        #     )
        #     db.session.add(email)
        #     db.session.flush()
        #     
        #     # Send via Brevo
        #     email_service = create_email_service(current_app)
        #     success, message_id = email_service.send_single_email(
        #         to_email=contact.email,
        #         subject=email.subject,
        #         html_content=email.body,
        #         text_content=email.body,  # Plain text version
        #         contact_id=contact.id
        #     )
        #     result = {'success': success, 'message_id': message_id}
        #     
        #     if result['success']:
        #         email.status = 'sent'
        #         email.sent_at = datetime.utcnow()
        #         email.brevo_message_id = result.get('message_id')
        #         
        #         # Update EmailSequence to mark as sent
        #         email_seq = EmailSequence.query.filter_by(
        #             contact_id=contact_id,
        #             campaign_id=campaign_id,
        #             sequence_step=0
        #         ).first()
        #         if email_seq:
        #             email_seq.status = 'sent'
        #             email_seq.sent_at = datetime.utcnow()
        #             email_seq.email_id = email.id
        #         
        #         logger.info(f"Immediately sent email to {contact.email} for campaign {campaign.name}")
        #     else:
        #         email.status = 'failed'
        #         logger.error(f"Failed to send immediate email: {result.get('error')}")
        #     
        #     db.session.commit()
        #     
        # except Exception as e:
        #     logger.error(f"Error sending immediate email: {str(e)}")
        #     db.session.rollback()
    
    def personalize_content(self, content: str, contact: Contact) -> str:
        """Replace template variables with contact data"""
        if not content:
            return content
        
        replacements = {
            '{{first_name}}': contact.first_name or 'there',
            '{{last_name}}': contact.last_name or '',
            '{{company}}': contact.company or 'your company',
            '{{email}}': contact.email,
            '{{domain}}': contact.domain or 'your domain'
        }
        
        for key, value in replacements.items():
            content = content.replace(key, value)
        
        return content
    
    def get_daily_scheduled_emails(self, target_date: date = None) -> List[Dict]:
        """
        Get all emails scheduled for a specific date
        
        Args:
            target_date: Date to get emails for (defaults to today)
            
        Returns:
            List of emails scheduled for the date
        """
        try:
            if target_date is None:
                target_date = datetime.utcnow().date()
            
            # Get all scheduled emails for the target date
            scheduled = EmailSequence.query.filter_by(
                scheduled_date=target_date,
                status='scheduled'
            ).all()
            
            emails_to_send = []
            for seq in scheduled:
                # Check if contact replied (stops sequence)
                contact_status = ContactCampaignStatus.query.filter_by(
                    contact_id=seq.contact_id,
                    campaign_id=seq.campaign_id
                ).first()
                
                if contact_status and contact_status.replied_at:
                    # Mark as skipped
                    seq.status = 'skipped_replied'
                    continue
                
                # Add to send list
                emails_to_send.append({
                    'sequence_id': seq.id,
                    'contact_id': seq.contact_id,
                    'campaign_id': seq.campaign_id,
                    'sequence_step': seq.sequence_step,
                    'template_type': seq.template_type,
                    'contact': Contact.query.get(seq.contact_id),
                    'campaign': Campaign.query.get(seq.campaign_id)
                })
            
            logger.info(f"Found {len(emails_to_send)} emails to send on {target_date}")
            return emails_to_send
            
        except Exception as e:
            logger.error(f"Error getting daily scheduled emails: {str(e)}")
            return []
    
    def send_scheduled_email(self, sequence_id: int) -> Dict:
        """
        Send a single scheduled email via Brevo
        
        Args:
            sequence_id: ID of the email sequence record
            
        Returns:
            Dict with send results
        """
        try:
            # Get sequence record
            sequence = EmailSequence.query.get(sequence_id)
            if not sequence:
                return {'success': False, 'error': f'Sequence {sequence_id} not found'}
            
            # Get contact and campaign
            contact = Contact.query.get(sequence.contact_id)
            campaign = Campaign.query.get(sequence.campaign_id)
            
            # Get appropriate template using risk_level (stored in template_type field)
            template = self.get_template_for_sequence(
                sequence.template_type,  # This now contains risk_level
                sequence.sequence_step,
                campaign_id=campaign.id
            )
            
            if not template:
                return {
                    'success': False, 
                    'error': f'No template found for {sequence.template_type} step {sequence.sequence_step}'
                }
            
            # Render template with contact data
            rendered = self.render_template_with_contact_data(template, contact, sequence)
            
            # Send via Brevo (or existing email service)
            send_result = self.send_via_brevo(contact, rendered, campaign)
            
            if send_result['success']:
                # Create Email record
                email = Email(
                    contact_id=contact.id,
                    campaign_id=campaign.id,
                    template_id=template.id,
                    email_type=f'step_{sequence.sequence_step}',
                    subject=rendered['subject'],
                    body=rendered['body'],
                    status='sent',
                    sent_at=datetime.utcnow()
                )
                db.session.add(email)
                db.session.flush()
                
                # Update sequence record
                sequence.sent_at = datetime.utcnow()
                sequence.status = 'sent'
                sequence.email_id = email.id
                
                # Update contact campaign status
                contact_status = ContactCampaignStatus.query.filter_by(
                    contact_id=contact.id,
                    campaign_id=campaign.id
                ).first()
                
                if contact_status:
                    contact_status.current_sequence_step = sequence.sequence_step
                    contact_status.updated_at = datetime.utcnow()
                
                db.session.commit()
                
                logger.info(f"Successfully sent email for sequence {sequence_id}")
                return {
                    'success': True,
                    'email_id': email.id,
                    'message_id': send_result.get('message_id')
                }
            else:
                # Mark as failed
                sequence.status = 'failed'
                db.session.commit()
                
                return {
                    'success': False,
                    'error': send_result.get('error', 'Unknown send error')
                }
                
        except Exception as e:
            logger.error(f"Error sending scheduled email {sequence_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_template_for_sequence(self, risk_level: str, sequence_step: int,
                                 campaign_id: int = None) -> Optional[EmailTemplate]:
        """Get appropriate template for sequence step and risk level"""
        try:
            # Try to find exact match using risk_level
            template = EmailTemplate.query.filter_by(
                risk_level=risk_level,
                sequence_step=sequence_step,
                active=True
            ).first()
            
            if template:
                return template
            
            # Fallback: try generic templates
                
            template = EmailTemplate.query.filter_by(
                risk_level='generic',
                sequence_step=sequence_step,
                active=True
            ).first()
            
            return template
            
        except Exception as e:
            logger.error(f"Error getting template: {str(e)}")
            return None
    
    def render_template_with_contact_data(self, template: EmailTemplate, 
                                        contact: Contact, sequence: EmailSequence) -> Dict:
        """Render template with contact and breach data"""
        try:
            # Get contact campaign status for breach data
            contact_status = ContactCampaignStatus.query.filter_by(
                contact_id=contact.id,
                campaign_id=sequence.campaign_id
            ).first()
            
            # Prepare template variables
            template_vars = {
                'first_name': contact.first_name or 'there',
                'last_name': contact.last_name or '',
                'company': contact.company or 'Your Organization',
                'industry': contact.industry or 'your industry',
                'email': contact.email,
            }
            
            # Add breach-specific variables if available
            if contact_status and contact_status.breach_data:
                breach_info = contact_status.breach_data
                
                # Get breach data from FlawTrack results
                if 'breach_data' in breach_info:
                    breach_data = breach_info['breach_data']
                    
                    # Get breach samples using FlawTrack API
                    try:
                        from services.flawtrack_api import FlawTrackAPI
                        import os
                        
                        # Get FlawTrack API instance
                        api_key = os.environ.get('FLAWTRACK_API_TOKEN', '')
                        endpoint = os.environ.get('FLAWTRACK_API_ENDPOINT', '')
                        
                        if api_key and endpoint:
                            flawtrack = FlawTrackAPI(api_key, endpoint)
                            breach_summary = flawtrack.get_breach_summary_for_email(contact.domain or breach_info.get('domain', ''))
                            breach_sample = breach_summary.get('template_vars', {}).get('breach_sample', 'Contact us for specific breach details')
                        else:
                            breach_sample = 'Contact us for specific breach details'
                            
                    except Exception as e:
                        logger.error(f"Error getting breach samples: {str(e)}")
                        breach_sample = 'Contact us for specific breach details'
                    
                    template_vars.update({
                        'breach_name': breach_data.get('breach_name', 'Recent Security Incident'),
                        'breach_year': str(breach_data.get('breach_year', 'Recently')),
                        'risk_score': str(breach_info.get('risk_score', 0)),
                        'records_affected': breach_data.get('records_affected', 'Multiple'),
                        'data_types': breach_data.get('data_types', 'Personal and business data'),
                        'domain': breach_info.get('domain', contact.domain or 'your domain'),
                        'breach_sample': breach_sample
                    })
                
                # Set risk level based on template type
                if sequence.template_type == 'breached':
                    template_vars['risk_level'] = 'HIGH'
                else:
                    template_vars['risk_level'] = 'MEDIUM'
            
            # Render subject and body
            subject = template.subject_line or template.subject or ''
            body = template.email_body or template.content or ''
            
            # Replace variables
            for var, value in template_vars.items():
                subject = subject.replace('{' + var + '}', str(value))
                body = body.replace('{' + var + '}', str(value))
            
            return {
                'subject': subject,
                'body': body,
                'html_body': template.email_body_html or body.replace('\\n', '<br>'),
                'template_vars': template_vars
            }
            
        except Exception as e:
            logger.error(f"Error rendering template: {str(e)}")
            return {
                'subject': f'Security consultation for {contact.company}',
                'body': f'Hi {contact.first_name}, we have an important security message for {contact.company}.',
                'html_body': f'Hi {contact.first_name}, we have an important security message for {contact.company}.'
            }
    
    def send_via_brevo(self, contact: Contact, rendered: Dict, campaign: Campaign) -> Dict:
        """Send email via Brevo API"""
        try:
            # Try to use existing email service
            from services.email_service import create_email_service
            from models.database import Settings
            
            class EmailConfig:
                BREVO_API_KEY = Settings.get_setting('brevo_api_key', '')
                DEFAULT_SENDER_EMAIL = campaign.sender_email or Settings.get_setting('sender_email', '')
                DEFAULT_SENDER_NAME = campaign.sender_name or Settings.get_setting('sender_name', '')
            
            if not EmailConfig.BREVO_API_KEY:
                logger.warning("No Brevo API key configured - simulating email send")
                return {
                    'success': True,
                    'message_id': f'simulated_{datetime.utcnow().timestamp()}',
                    'note': 'Email simulated - configure Brevo API key to send real emails'
                }
            
            email_service = create_email_service(EmailConfig())
            
            success, message = email_service.send_single_email(
                to_email=contact.email,
                subject=rendered['subject'],
                html_content=rendered['html_body'],
                from_email=EmailConfig.DEFAULT_SENDER_EMAIL,
                from_name=EmailConfig.DEFAULT_SENDER_NAME
            )
            
            if success:
                return {
                    'success': True,
                    'message_id': message if 'Message ID:' in str(message) else f'sent_{datetime.utcnow().timestamp()}'
                }
            else:
                return {
                    'success': False,
                    'error': str(message)
                }
                
        except Exception as e:
            logger.error(f"Error sending via Brevo: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def mark_contact_replied(self, contact_id: int, campaign_id: int, 
                           replied_at: datetime = None) -> bool:
        """
        Stop email sequence when contact replies
        
        Args:
            contact_id: Contact who replied
            campaign_id: Campaign they replied to
            replied_at: When they replied (defaults to now)
            
        Returns:
            True if sequence was stopped successfully
        """
        try:
            if replied_at is None:
                replied_at = datetime.utcnow()
            
            # Update contact campaign status
            contact_status = ContactCampaignStatus.query.filter_by(
                contact_id=contact_id,
                campaign_id=campaign_id
            ).first()
            
            if contact_status:
                contact_status.replied_at = replied_at
                contact_status.updated_at = datetime.utcnow()
            
            # Mark remaining scheduled emails as skipped
            remaining_emails = EmailSequence.query.filter_by(
                contact_id=contact_id,
                campaign_id=campaign_id,
                status='scheduled'
            ).all()
            
            for seq in remaining_emails:
                seq.status = 'skipped_replied'
            
            db.session.commit()
            
            logger.info(f"Stopped sequence for contact {contact_id} in campaign {campaign_id} - reply received")
            return True
            
        except Exception as e:
            logger.error(f"Error marking contact replied: {str(e)}")
            db.session.rollback()
            return False
    
    def get_sequence_status(self, contact_id: int, campaign_id: int) -> Dict:
        """Get current sequence status for a contact in a campaign"""
        try:
            contact_status = ContactCampaignStatus.query.filter_by(
                contact_id=contact_id,
                campaign_id=campaign_id
            ).first()
            
            if not contact_status:
                return {'enrolled': False}
            
            # Get all sequences for this contact/campaign
            sequences = EmailSequence.query.filter_by(
                contact_id=contact_id,
                campaign_id=campaign_id
            ).order_by(EmailSequence.sequence_step).all()
            
            return {
                'enrolled': True,
                'current_step': contact_status.current_sequence_step,
                'breach_status': contact_status.breach_status,
                'replied_at': contact_status.replied_at.isoformat() if contact_status.replied_at else None,
                'sequence_completed': contact_status.sequence_completed_at is not None,
                'total_sequences': len(sequences),
                'sequences': [seq.to_dict() for seq in sequences]
            }
            
        except Exception as e:
            logger.error(f"Error getting sequence status: {str(e)}")
            return {'enrolled': False, 'error': str(e)}


def create_email_sequence_service():
    """Factory function to create email sequence service"""
    return EmailSequenceService()