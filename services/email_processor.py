"""
Email Processing Service - Full Implementation with Brevo Integration
Handles scheduling, sending, and tracking emails via Brevo API
"""
import logging
import os
from datetime import date, datetime
from typing import Dict
from models.database import db, EmailSequence, Contact, Campaign, Email, EmailTemplate

logger = logging.getLogger(__name__)

def process_email_queue() -> Dict:
    """
    Process scheduled emails and send them via Brevo API
    Creates Email records and sends actual emails through Brevo
    """
    try:
        # EMERGENCY: Check if email sending is disabled due to SMTP traffic alert
        if os.getenv('EMAIL_SENDING_DISABLED', 'false').lower() == 'true':
            logger.warning("🚨 EMAIL SENDING DISABLED - SMTP Traffic Alert Mode Active")
            return {
                'emails_sent': 0,
                'emails_failed': 0,
                'total_processed': 0,
                'status': 'DISABLED_SMTP_ALERT'
            }
        # Find all emails scheduled for now or earlier (using scheduled_datetime for precise timing)
        current_time = datetime.utcnow()
        scheduled_emails = EmailSequence.query.filter(
            EmailSequence.status == 'scheduled',
            EmailSequence.scheduled_datetime <= current_time
        ).all()

        if not scheduled_emails:
            logger.info("No emails scheduled for sending")
            return {
                'emails_sent': 0,
                'emails_failed': 0,
                'total_processed': 0
            }

        logger.info(f"Found {len(scheduled_emails)} emails to process")

        sent_count = 0
        failed_count = 0

        for email_seq in scheduled_emails:
            try:
                # Get contact and campaign info
                contact = Contact.query.get(email_seq.contact_id)
                campaign = Campaign.query.get(email_seq.campaign_id)

                if not contact or not campaign:
                    logger.error(f"Missing contact or campaign for email sequence {email_seq.id}")
                    email_seq.status = 'failed'
                    failed_count += 1
                    continue

                # Check if contact is unsubscribed (skip if they are)
                if contact.unsubscribed:
                    logger.info(f"Skipping email to {contact.email} - contact is unsubscribed")
                    email_seq.status = 'skipped_unsubscribed'
                    email_seq.skip_reason = 'Contact unsubscribed'
                    continue

                # Check if contact has replied (stop sequence if they have)
                # Check both contact-level and campaign-level reply status
                if getattr(contact, 'has_responded', False):
                    logger.info(f"Skipping email to {contact.email} - contact has responded globally")
                    email_seq.status = 'skipped_replied'
                    email_seq.skip_reason = 'Contact has responded'
                    continue

                from models.database import ContactCampaignStatus
                campaign_status = ContactCampaignStatus.query.filter_by(
                    contact_id=contact.id,
                    campaign_id=campaign.id
                ).first()

                if campaign_status and campaign_status.replied_at:
                    logger.info(f"Skipping email to {contact.email} - contact has replied to campaign {campaign.id}")
                    email_seq.status = 'skipped_replied'
                    email_seq.skip_reason = 'Contact replied to campaign'
                    continue

                # Check if contact email has bounced and if sequence should stop on bounce
                if contact.email_status == 'bounced':
                    # Get the campaign's template to check stop_on_bounce setting
                    from models.database import EmailTemplate, EmailSequenceConfig, ContactCampaignStatus
                    template = EmailTemplate.query.get(campaign.template_id) if campaign.template_id else None

                    # Check if we should stop on bounce (default: True if setting not found)
                    should_stop_on_bounce = True
                    if template and hasattr(template, 'sequence'):
                        should_stop_on_bounce = getattr(template.sequence, 'stop_on_bounce', True)
                    elif campaign.sequence_id:
                        sequence = EmailSequenceConfig.query.get(campaign.sequence_id)
                        if sequence:
                            should_stop_on_bounce = getattr(sequence, 'stop_on_bounce', True)

                    if should_stop_on_bounce:
                        logger.info(f"Skipping email to {contact.email} - email address has bounced and stop_on_bounce is enabled")
                        email_seq.status = 'skipped_bounced'
                        email_seq.skip_reason = 'Email address bounced'

                        # Update campaign status to mark sequence as stopped due to bounce
                        campaign_status = ContactCampaignStatus.query.filter_by(
                            contact_id=contact.id,
                            campaign_id=campaign.id
                        ).first()

                        if campaign_status and not campaign_status.sequence_completed_at:
                            campaign_status.sequence_completed_at = datetime.utcnow()
                            campaign_status.completion_reason = f'{contact.bounce_type or "unknown"}_bounce'
                            logger.info(f"Marked campaign sequence as completed due to bounce for {contact.email}")

                        continue

                # Check if contact is blocked (always skip blocked contacts)
                if contact.blocked_at:
                    logger.info(f"Skipping email to {contact.email} - contact is blocked since {contact.blocked_at}")
                    email_seq.status = 'skipped_blocked'
                    email_seq.skip_reason = f'Contact blocked: {contact.block_reason or "Email blocked by recipient server"}'

                    # Update campaign status to mark sequence as stopped due to blocking
                    from models.database import ContactCampaignStatus
                    campaign_status = ContactCampaignStatus.query.filter_by(
                        contact_id=contact.id,
                        campaign_id=campaign.id
                    ).first()

                    if campaign_status and not campaign_status.sequence_completed_at:
                        campaign_status.sequence_completed_at = datetime.utcnow()
                        campaign_status.completion_reason = 'blocked'
                        logger.info(f"Marked campaign sequence as completed due to blocking for {contact.email}")

                    continue

                # Check if this sequence has already been processed (avoid race conditions)
                if email_seq.status == 'sent':
                    logger.info(f"Email sequence {email_seq.id} already processed for {contact.email} step {email_seq.sequence_step}")
                    continue

                # Mark as processing to prevent duplicate processing
                email_seq.status = 'processing'
                db.session.commit()  # Commit immediately to prevent race conditions

                # Double-check if email already exists for this sequence
                existing_email = Email.query.filter_by(
                    contact_id=contact.id,
                    campaign_id=campaign.id,
                    email_type=f"step_{email_seq.sequence_step}"
                ).first()

                if existing_email:
                    logger.info(f"Email already exists for {contact.email} step {email_seq.sequence_step}")
                    email_seq.status = 'sent'
                    email_seq.email_id = existing_email.id
                    db.session.commit()
                    continue

                # Get the appropriate template for this sequence step
                template = get_template_for_sequence_step(
                    campaign,
                    email_seq.sequence_step,
                    email_seq.template_type
                )

                if not template:
                    logger.error(f"No template found for campaign {campaign.id} step {email_seq.sequence_step}")
                    email_seq.status = 'failed'
                    email_seq.error_message = 'No template found'
                    failed_count += 1
                    continue

                # Send the email via Brevo
                email_result = send_email_via_brevo(contact, campaign, template, email_seq)

                if email_result['success']:
                    try:
                        # Create Email record
                        email_record = Email(
                            contact_id=contact.id,
                            campaign_id=campaign.id,
                            template_id=template.id,
                            email_type=f"step_{email_seq.sequence_step}",
                            subject=email_result['subject'],
                            body=email_result['body'],
                            status='sent',
                            sent_at=datetime.utcnow(),
                            brevo_message_id=email_result.get('brevo_message_id'),
                            thread_message_id=email_result.get('thread_message_id')
                        )
                        db.session.add(email_record)
                        db.session.flush()  # Get the ID

                        # Update sequence record
                        email_seq.status = 'sent'
                        email_seq.sent_at = datetime.utcnow()
                        email_seq.email_id = email_record.id

                        # Commit immediately to prevent race conditions
                        db.session.commit()

                        sent_count += 1
                        logger.info(f"Successfully sent email to {contact.email} (step {email_seq.sequence_step})")

                    except Exception as db_error:
                        # Handle duplicate email constraint violation
                        if "UNIQUE constraint failed" in str(db_error):
                            logger.warning(f"Duplicate email prevented by constraint for {contact.email} step {email_seq.sequence_step}")
                            # Mark sequence as sent since email was actually sent (just duplicate record prevention)
                            db.session.rollback()  # Rollback the failed insert
                            email_seq.status = 'sent'
                            email_seq.sent_at = datetime.utcnow()
                            db.session.commit()
                            sent_count += 1  # Count as successful since email was sent
                        else:
                            # Other database errors
                            logger.error(f"Database error creating email record: {str(db_error)}")
                            db.session.rollback()
                            email_seq.status = 'failed'
                            email_seq.error_message = f"Database error: {str(db_error)}"
                            db.session.commit()
                            failed_count += 1

                else:
                    # Email sending failed
                    email_seq.status = 'failed'
                    email_seq.error_message = email_result.get('error', 'Unknown error')
                    db.session.commit()  # Commit failed status immediately
                    failed_count += 1
                    logger.error(f"Failed to send email to {contact.email}: {email_result.get('error')}")

            except Exception as e:
                logger.error(f"Error processing email sequence {email_seq.id}: {str(e)}")
                email_seq.status = 'failed'
                email_seq.error_message = str(e)
                db.session.commit()  # Commit failed status immediately
                failed_count += 1

        # Final commit for any remaining changes (shouldn't be needed with immediate commits)
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Final commit error: {str(e)}")
            db.session.rollback()

        result = {
            'emails_sent': sent_count,
            'emails_failed': failed_count,
            'total_processed': len(scheduled_emails)
        }

        logger.info(f"Email processing completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in email processing: {str(e)}")
        db.session.rollback()
        return {
            'emails_sent': 0,
            'emails_failed': 0,
            'total_processed': 0,
            'error': str(e)
        }


def get_template_for_sequence_step(campaign, sequence_step, template_type):
    """Get the appropriate email template for this sequence step"""
    try:
        # Map sequence step to template type
        step_types = {
            0: 'initial',
            1: 'follow_up',
            2: 'follow_up',
            3: 'follow_up',
            4: 'follow_up'
        }

        email_template_type = step_types.get(sequence_step, 'follow_up')

        # Find template based on template_type and sequence_step
        template = EmailTemplate.query.filter_by(
            template_type=email_template_type,
            sequence_step=sequence_step,
            active=True
        ).first()

        # Fallback to generic template if specific one not found
        if not template:
            template = EmailTemplate.query.filter_by(
                template_type=email_template_type,
                active=True
            ).first()

        return template

    except Exception as e:
        logger.error(f"Error getting template: {str(e)}")
        return None


def send_email_via_brevo(contact, campaign, template, email_seq):
    """Send email via Brevo API using client-specific credentials"""
    try:
        from services.brevo_modern_service import BrevoModernService
        from models.database import Client
        from flask import current_app

        # Get the client for this campaign
        client = None
        if campaign.client_id:
            client = Client.query.get(campaign.client_id)

        # Create client-specific configuration
        if client and client.brevo_api_key:
            # Use client's specific Brevo credentials
            class ClientConfig:
                BREVO_API_KEY = client.brevo_api_key
                BREVO_SENDER_EMAIL = client.sender_email
                BREVO_SENDER_NAME = client.sender_name

            email_service = BrevoModernService(ClientConfig())
            logger.info(f"Using client-specific credentials for {client.company_name}: {client.sender_email}")
        else:
            # Fallback to default/global credentials
            from services.email_service import create_email_service
            email_service = create_email_service(current_app.config)
            logger.warning(f"No client credentials found for campaign {campaign.id}, using default sender")

        # Prepare email content with variable substitution (including client variables)
        subject = substitute_variables(template.subject_line or template.subject, contact, campaign, client)
        body = substitute_variables(template.email_body or template.content, contact, campaign, client)

        # Send email with client-specific sender info
        if client:
            success, result_data = email_service.send_single_email(
                to_email=contact.email,
                subject=subject,
                html_content=body,
                text_content=body,  # Simple text version
                from_email=client.sender_email,
                from_name=client.sender_name,
                contact_id=contact.id
            )
        else:
            success, result_data = email_service.send_single_email(
                to_email=contact.email,
                subject=subject,
                html_content=body,
                text_content=body,  # Simple text version
                contact_id=contact.id
            )

        if success:
            return {
                'success': True,
                'subject': subject,
                'body': body,
                'brevo_message_id': result_data.get('brevo_message_id') if isinstance(result_data, dict) else None,
                'thread_message_id': result_data.get('thread_message_id') if isinstance(result_data, dict) else None
            }
        else:
            return {
                'success': False,
                'error': result_data if isinstance(result_data, str) else str(result_data)
            }

    except Exception as e:
        logger.error(f"Error sending email via Brevo: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def substitute_variables(text, contact, campaign, client=None):
    """Replace template variables with actual contact and client data"""
    if not text:
        return ""

    # Contact and campaign variables
    substitutions = {
        '{first_name}': contact.first_name or 'there',
        '{last_name}': contact.last_name or '',
        '{company}': contact.company or 'your organization',
        '{email}': contact.email,
        '{domain}': contact.domain or contact.email.split('@')[1] if '@' in contact.email else '',
        '{campaign_name}': campaign.name,
        '{industry}': contact.industry or 'your industry',
        '{business_type}': contact.business_type or '',
        '{company_size}': contact.company_size or ''
    }

    # Client-specific variables (for multi-tenant branding)
    if client:
        client_substitutions = {
            '{client_company_name}': client.company_name or '',
            '{client_contact_name}': client.contact_name or client.sender_name or '',
            '{client_sender_name}': client.sender_name or '',
            '{client_sender_email}': client.sender_email or '',
            '{client_phone}': client.phone or '',
            '{client_website}': client.website or ''
        }
        substitutions.update(client_substitutions)

    result = text
    for placeholder, value in substitutions.items():
        result = result.replace(placeholder, str(value))

    return result