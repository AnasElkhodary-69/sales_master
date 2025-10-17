"""
Brevo Webhook Handler for Email Events
Handles replies, opens, clicks, bounces to update sequence status
Enhanced with comprehensive event logging and analytics
"""
from flask import Blueprint, request, jsonify
from models.database import db, ContactCampaignStatus, Email, Campaign, Contact, WebhookEvent
from services.webhook_analytics import create_webhook_analytics_service
from datetime import datetime
import logging
import json
import hashlib
import hmac

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/webhooks/brevo', methods=['POST'])
def handle_brevo_webhook():
    """
    Handle incoming webhooks from Brevo for email events
    Events: delivered, opened, clicked, replied, bounced, spam, unsubscribed
    """
    try:
        # Get the webhook data
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Log the incoming webhook for debugging
        logger.info(f"Received Brevo webhook: {data.get('event', 'unknown')}")
        
        # Verify webhook signature if secret is configured
        webhook_secret = None
        try:
            from models.database import Settings
            webhook_secret = Settings.get_setting('brevo_webhook_secret', '')
        except:
            pass
        
        if webhook_secret:
            signature = request.headers.get('X-Brevo-Signature', '')
            if not verify_webhook_signature(request.data, signature, webhook_secret):
                logger.warning("Invalid webhook signature")
                return jsonify({'error': 'Invalid signature'}), 401
        
        # Process the event
        event_type = data.get('event', '').lower()
        email_address = data.get('email', '').strip()

        # Handle multiple possible message ID field names
        message_id = (
            data.get('message-id') or
            data.get('MessageId') or
            data.get('message_id') or
            data.get('messageId') or
            ''
        ).strip()

        # Debug: Log webhook data for all events
        logger.info(f"Webhook event '{event_type}' data: {data}")
        
        # Find the contact and their campaign status
        original_webhook_email = email_address  # Keep original email from webhook
        contact = Contact.query.filter_by(email=email_address).first()

        # If contact not found by email (anonymous/missing email), try message-ID lookup
        email_record = None
        if not contact and message_id:
            logger.info(f"Contact lookup by email failed for '{email_address}' - trying message-ID: {message_id}")
            email_record = Email.query.filter_by(brevo_message_id=message_id).first()
            if email_record:
                contact = Contact.query.get(email_record.contact_id)
                if contact:
                    logger.warning(f"⚠️ Email mismatch detected! Webhook email '{original_webhook_email}' != Contact email '{contact.email}'")
                    logger.info(f"Found contact {contact.email} via message-ID lookup, but webhook email was {original_webhook_email}")
                    # DO NOT update email_address - keep the original webhook email for proper tracking

        if not contact:
            logger.warning(f"❌ Contact not found for email: '{email_address}' and message-ID: {message_id}")
            return jsonify({'status': 'ignored', 'reason': 'contact not found'}), 200

        # If there's an email mismatch, we should be very careful about processing this event
        # This typically happens when an email was forwarded or there's a data integrity issue
        email_mismatch = (original_webhook_email != contact.email)
        if email_mismatch:
            logger.warning(f"🚨 EMAIL MISMATCH: Processing {event_type} event for webhook email '{original_webhook_email}' but found contact '{contact.email}'")
            # For now, we'll still process it but with extra logging
            # In future, we might want to create a separate contact for the webhook email
        
        # Find the email record if message ID is provided (if not already found above)
        campaign = None
        if message_id and not email_record:
            email_record = Email.query.filter_by(brevo_message_id=message_id).first()

        if email_record:
            campaign = Campaign.query.get(email_record.campaign_id)
        
        # Initialize analytics service
        analytics_service = create_webhook_analytics_service()
        
        # Save webhook event for analytics
        webhook_event = analytics_service.save_webhook_event(
            contact=contact,
            email=email_record,
            campaign=campaign,
            event_data=data
        )
        
        # Log successful event processing
        if email_mismatch:
            logger.info(f"📧 Processing {event_type.upper()} event for webhook email '{original_webhook_email}' (matched to contact: {contact.email})")
        else:
            logger.info(f"📧 Processing {event_type.upper()} event for contact: {contact.email}")

        # Process based on event type (existing logic)
        if event_type == 'replied' or event_type == 'reply':
            handle_reply_event(contact, data)
        elif event_type == 'opened' or event_type == 'open' or event_type == 'unique_opened':
            handle_open_event(contact, data)
        elif event_type == 'clicked' or event_type == 'click':
            handle_click_event(contact, data)
        elif 'bounce' in event_type:
            handle_bounce_event(contact, data)
        elif event_type == 'unsubscribed' or event_type == 'unsubscribe':
            handle_unsubscribe_event(contact, data)
        elif event_type == 'spam' or event_type == 'complaint':
            handle_spam_event(contact, data)
        elif event_type == 'delivered' or event_type == 'delivery':
            handle_delivery_event(contact, data)
        elif event_type == 'blocked' or event_type == 'block':
            handle_blocked_event(contact, data)
        elif event_type == 'request' or event_type == 'sent':
            logger.info(f"📤 Email sent confirmation for {contact.email}")
        else:
            logger.info(f"❓ Unhandled event type: {event_type}")
        
        # Commit all database changes including webhook event
        db.session.commit()
        
        response_data = {
            'status': 'success', 
            'event': event_type,
            'contact_email': email_address,
            'webhook_event_id': webhook_event.id if webhook_event else None
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error processing Brevo webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

def verify_webhook_signature(payload, signature, secret):
    """Verify the webhook signature from Brevo"""
    expected_sig = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_sig, signature)

def handle_reply_event(contact, data):
    """
    Handle reply event - STOP the sequence immediately
    This is the most important event for sequence management

    IMPORTANT: Only stops sequences for the specific campaign where reply was detected,
    NOT globally for all campaigns. This allows the same contact to be in multiple campaigns.
    """
    logger.info(f"Processing REPLY event for contact: {contact.email}")

    # Find the specific email that was replied to (if message-id provided)
    replied_campaign_id = None
    if 'message-id' in data:
        email = Email.query.filter_by(brevo_message_id=data['message-id']).first()
        if email:
            email.replied_at = datetime.utcnow()
            email.status = 'replied'
            replied_campaign_id = email.campaign_id
            logger.info(f"Reply detected for email in campaign {replied_campaign_id}")

    # If we found the specific campaign, only stop that campaign's sequence
    if replied_campaign_id:
        campaign_status = ContactCampaignStatus.query.filter_by(
            contact_id=contact.id,
            campaign_id=replied_campaign_id,
            replied_at=None  # Not already marked as replied
        ).first()

        if campaign_status:
            # Mark as replied - this stops the sequence for THIS campaign only
            campaign_status.replied_at = datetime.utcnow()
            logger.info(f"Stopped sequence for contact {contact.email} in campaign {replied_campaign_id}")

            # Update campaign response count
            campaign = Campaign.query.get(replied_campaign_id)
            if campaign:
                campaign.response_count = (campaign.response_count or 0) + 1

            # Mark all future scheduled emails for THIS campaign as skipped
            from models.database import EmailSequence
            future_emails = EmailSequence.query.filter(
                EmailSequence.contact_id == contact.id,
                EmailSequence.campaign_id == replied_campaign_id,
                EmailSequence.status == 'scheduled'
            ).all()

            for seq in future_emails:
                seq.status = 'skipped_replied'
                seq.skip_reason = 'Contact replied to campaign'
                logger.info(f"Skipped future email step {seq.sequence_step} for contact {contact.email} in campaign {replied_campaign_id}")
    else:
        # If no message-id provided or email not found, we don't know which campaign
        # So we stop ALL active sequences as a fallback (old behavior)
        logger.warning(f"No message-id provided for reply from {contact.email}, stopping all active sequences")
        active_statuses = ContactCampaignStatus.query.filter_by(
            contact_id=contact.id,
            replied_at=None  # Not already marked as replied
        ).all()

        for status in active_statuses:
            # Mark as replied - this stops the sequence
            status.replied_at = datetime.utcnow()
            logger.info(f"Marked contact {contact.email} as replied in campaign {status.campaign_id}")

            # Update campaign response count
            campaign = Campaign.query.get(status.campaign_id)
            if campaign:
                campaign.response_count = (campaign.response_count or 0) + 1

    # DO NOT set global has_responded flag - we want campaign-specific tracking only
    # This allows the same contact to be in multiple campaigns
    # contact.has_responded = True  # REMOVED - campaign-specific only
    # contact.responded_at = datetime.utcnow()  # REMOVED - campaign-specific only

def handle_open_event(contact, data):
    """Handle email open event"""
    logger.info(f"Processing OPEN event for contact: {contact.email}")
    
    # Update contact engagement
    contact.last_opened_at = datetime.utcnow()
    contact.total_opens = (contact.total_opens or 0) + 1
    
    # Find and update the specific email
    if 'message-id' in data:
        email = Email.query.filter_by(brevo_message_id=data['message-id']).first()
        if email:
            if not email.opened_at:  # First open
                email.opened_at = datetime.utcnow()
            email.open_count = (email.open_count or 0) + 1
            email.status = 'opened'

def handle_click_event(contact, data):
    """Handle link click event"""
    logger.info(f"Processing CLICK event for contact: {contact.email}")
    
    clicked_url = data.get('link', '')
    
    # Update contact engagement
    contact.last_clicked_at = datetime.utcnow()
    contact.total_clicks = (contact.total_clicks or 0) + 1
    
    # Find and update the specific email
    if 'message-id' in data:
        email = Email.query.filter_by(brevo_message_id=data['message-id']).first()
        if email:
            if not email.clicked_at:  # First click
                email.clicked_at = datetime.utcnow()
            email.click_count = (email.click_count or 0) + 1
            email.status = 'clicked'
            
            # Store clicked links
            clicked_links = email.clicked_links or []
            if clicked_url and clicked_url not in clicked_links:
                clicked_links.append(clicked_url)
                email.clicked_links = clicked_links

def handle_bounce_event(contact, data):
    """
    Handle email bounce event - STOP sequences based on bounce type and settings
    Enhanced to work like reply detection with campaign statistics
    """
    logger.info(f"Processing BOUNCE event for contact: {contact.email}")

    # Determine bounce type from event type or bounce_type field
    bounce_type = data.get('bounce_type', '')
    event_type = data.get('event', '').lower()

    # If no explicit bounce_type, infer from event type
    if not bounce_type:
        if 'soft_bounce' in event_type or 'soft' in event_type:
            bounce_type = 'soft'
        elif 'hard_bounce' in event_type or 'hard' in event_type:
            bounce_type = 'hard'
        else:
            bounce_type = 'hard'  # Default to hard bounce

    logger.info(f"Bounce event: {event_type} -> bounce_type: {bounce_type}")

    # Mark contact as bounced
    contact.email_status = 'bounced'
    contact.bounce_type = bounce_type
    contact.bounced_at = datetime.utcnow()

    # Find all active campaign statuses for this contact
    active_statuses = ContactCampaignStatus.query.filter_by(
        contact_id=contact.id,
        replied_at=None,  # Not already stopped by reply
        sequence_completed_at=None  # Not already completed
    ).all()

    sequences_stopped = 0

    for status in active_statuses:
        # Check if this campaign should stop on bounce
        should_stop = False

        # For hard bounces, always stop if it's a hard bounce
        if bounce_type == 'hard':
            should_stop = True
        else:
            # For soft bounces, check the campaign's stop_on_bounce setting
            from models.database import Campaign, EmailSequenceConfig
            campaign = Campaign.query.get(status.campaign_id)
            if campaign and campaign.sequence_id:
                sequence = EmailSequenceConfig.query.get(campaign.sequence_id)
                if sequence:
                    should_stop = getattr(sequence, 'stop_on_bounce', True)

        if should_stop:
            # Mark campaign as stopped due to bounce
            status.sequence_completed_at = datetime.utcnow()
            status.completion_reason = f'{bounce_type}_bounce'
            sequences_stopped += 1

            # Update campaign bounce count (similar to response count)
            from models.database import Campaign
            campaign = Campaign.query.get(status.campaign_id)
            if campaign:
                campaign.bounce_count = (campaign.bounce_count or 0) + 1

            logger.info(f"Stopped sequence for {contact.email} in campaign {status.campaign_id} due to {bounce_type} bounce")

    # Update the specific email record that bounced
    if 'message-id' in data:
        email = Email.query.filter_by(brevo_message_id=data['message-id']).first()
        if email:
            email.bounced_at = datetime.utcnow()
            email.bounce_type = bounce_type
            email.status = 'bounced'

    # Stop future scheduled emails for this contact (like reply detection does)
    from models.database import EmailSequence
    future_sequences = EmailSequence.query.filter(
        EmailSequence.contact_id == contact.id,
        EmailSequence.status == 'scheduled'
    ).all()

    for seq in future_sequences:
        # Check if this sequence should stop on bounce
        should_stop = False

        if bounce_type == 'hard':
            should_stop = True
        else:
            # Check the campaign's stop_on_bounce setting
            from models.database import Campaign, EmailSequenceConfig
            campaign = Campaign.query.get(seq.campaign_id)
            if campaign and campaign.sequence_id:
                sequence = EmailSequenceConfig.query.get(campaign.sequence_id)
                if sequence:
                    should_stop = getattr(sequence, 'stop_on_bounce', True)

        if should_stop:
            seq.status = f'skipped_{bounce_type}_bounce'
            seq.skip_reason = f'Email {bounce_type} bounce detected'

    logger.info(f"Successfully processed {bounce_type} bounce for {contact.email}, stopped {sequences_stopped} sequences")

def handle_unsubscribe_event(contact, data):
    """Handle unsubscribe event - stop all sequences"""
    logger.info(f"Processing UNSUBSCRIBE event for contact: {contact.email}")
    
    # Mark contact as unsubscribed
    contact.is_subscribed = False
    contact.unsubscribed_at = datetime.utcnow()
    
    # Stop all active sequences
    active_statuses = ContactCampaignStatus.query.filter_by(
        contact_id=contact.id,
        sequence_completed_at=None
    ).all()
    
    for status in active_statuses:
        status.sequence_completed_at = datetime.utcnow()
        status.completion_reason = 'unsubscribed'
        logger.info(f"Stopped sequence for unsubscribed contact {contact.email} in campaign {status.campaign_id}")

def handle_spam_event(contact, data):
    """Handle spam complaint - stop all sequences and mark contact"""
    logger.info(f"Processing SPAM event for contact: {contact.email}")
    
    # Mark contact as spam reporter
    contact.marked_as_spam = True
    contact.spam_reported_at = datetime.utcnow()
    contact.is_subscribed = False
    
    # Stop all active sequences immediately
    active_statuses = ContactCampaignStatus.query.filter_by(
        contact_id=contact.id,
        sequence_completed_at=None
    ).all()
    
    for status in active_statuses:
        status.sequence_completed_at = datetime.utcnow()
        status.completion_reason = 'spam_complaint'
        logger.info(f"Stopped sequence for spam reporter {contact.email} in campaign {status.campaign_id}")

def handle_delivery_event(contact, data):
    """Handle successful delivery event"""
    logger.info(f"Processing DELIVERY event for contact: {contact.email}")

    # Update email record
    if 'message-id' in data:
        email = Email.query.filter_by(brevo_message_id=data['message-id']).first()
        if email:
            email.delivered_at = datetime.utcnow()
            email.status = 'delivered'

    # Update contact last contacted time
    contact.last_contacted_at = datetime.utcnow()

def handle_blocked_event(contact, data):
    """
    Handle blocked event - contact's email provider blocked the email
    Similar to bounce but different reason (spam filters, reputation, etc.)
    """
    logger.info(f"Processing BLOCKED event for contact: {contact.email}")

    # Get block reason if available
    block_reason = data.get('reason', 'Email blocked by recipient server')

    # Mark contact as blocked
    contact.email_status = 'blocked'
    contact.blocked_at = datetime.utcnow()
    contact.block_reason = block_reason

    # Find all active campaign statuses for this contact
    active_statuses = ContactCampaignStatus.query.filter_by(
        contact_id=contact.id,
        replied_at=None,  # Not already stopped by reply
        sequence_completed_at=None  # Not already completed
    ).all()

    sequences_stopped = 0

    for status in active_statuses:
        # Stop the sequence - blocked emails should stop sequences like hard bounces
        status.sequence_completed_at = datetime.utcnow()
        status.completion_reason = 'blocked'
        sequences_stopped += 1

        # Update campaign blocked count
        from models.database import Campaign
        campaign = Campaign.query.get(status.campaign_id)
        if campaign:
            campaign.blocked_count = (campaign.blocked_count or 0) + 1

        logger.info(f"Stopped sequence for {contact.email} in campaign {status.campaign_id} due to blocked email")

    # Update the specific email record that was blocked
    email_updated = False
    if 'message-id' in data:
        email = Email.query.filter_by(brevo_message_id=data['message-id']).first()
        if email:
            email.blocked_at = datetime.utcnow()
            email.block_reason = block_reason
            email.status = 'blocked'
            email_updated = True

    # If no specific email found, update the most recent sent email for this contact
    if not email_updated:
        recent_email = Email.query.filter_by(contact_id=contact.id).filter(
            Email.status.in_(['sent', 'delivered', 'opened', 'clicked'])
        ).order_by(Email.sent_at.desc()).first()

        if recent_email:
            recent_email.blocked_at = datetime.utcnow()
            recent_email.block_reason = block_reason
            recent_email.status = 'blocked'
            logger.info(f"Updated most recent email (ID: {recent_email.id}) for blocked contact {contact.email}")

    # Stop future scheduled emails for this contact
    from models.database import EmailSequence
    future_sequences = EmailSequence.query.filter(
        EmailSequence.contact_id == contact.id,
        EmailSequence.status == 'scheduled'
    ).all()

    for seq in future_sequences:
        seq.status = 'skipped_blocked'
        seq.skip_reason = f'Email blocked: {block_reason}'

    logger.info(f"Successfully processed blocked event for {contact.email}, stopped {sequences_stopped} sequences")

# Additional endpoint to manually check reply status
@webhooks_bp.route('/api/check-replies', methods=['POST'])
def check_replies():
    """Manually check and update reply status for a contact"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        contact = Contact.query.filter_by(email=email).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Simulate reply detection (in production, this would check email server)
        handle_reply_event(contact, {'email': email})
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Marked {email} as replied',
            'sequences_stopped': True
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking replies: {str(e)}")
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/api/simulate-webhook', methods=['POST'])
def simulate_webhook():
    """Simulate a Brevo webhook event for testing purposes"""
    try:
        data = request.get_json()
        event_type = data.get('event', 'delivered')
        email_address = data.get('email', '')
        message_id = data.get('message_id', f'test_{int(datetime.now().timestamp())}')
        
        if not email_address:
            return jsonify({'error': 'Email address required'}), 400
        
        # Create simulated webhook payload
        webhook_data = {
            'event': event_type,
            'email': email_address,
            'message-id': message_id,
            'timestamp': datetime.utcnow().isoformat(),
            'tag': ['campaign'],
            'subject': data.get('subject', 'Test Email')
        }
        
        # Add event-specific data
        if event_type == 'clicked':
            webhook_data['link'] = data.get('link', 'https://example.com')
        elif 'bounce' in event_type:
            webhook_data['bounce_type'] = data.get('bounce_type', 'hard')
        elif event_type == 'blocked':
            webhook_data['reason'] = data.get('reason', 'Blocked by spam filter')
        
        # Process the simulated webhook
        contact = Contact.query.filter_by(email=email_address).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Process based on event type
        if event_type == 'delivered':
            handle_delivery_event(contact, webhook_data)
        elif event_type == 'opened':
            handle_open_event(contact, webhook_data)
        elif event_type == 'clicked':
            handle_click_event(contact, webhook_data)
        elif event_type == 'replied':
            handle_reply_event(contact, webhook_data)
        elif 'bounce' in event_type:
            handle_bounce_event(contact, webhook_data)
        elif event_type == 'blocked':
            handle_blocked_event(contact, webhook_data)
        elif event_type == 'unsubscribed':
            handle_unsubscribe_event(contact, webhook_data)
        elif event_type == 'spam':
            handle_spam_event(contact, webhook_data)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Simulated {event_type} event for {email_address}',
            'webhook_data': webhook_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error simulating webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/api/webhook-analytics', methods=['GET'])
def get_webhook_analytics():
    """Get email analytics based on webhook events"""
    try:
        days = request.args.get('days', 30, type=int)
        analytics_service = create_webhook_analytics_service()
        analytics = analytics_service.get_email_analytics(days=days)
        
        return jsonify(analytics), 200
        
    except Exception as e:
        logger.error(f"Error getting webhook analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/api/campaign-analytics/<int:campaign_id>', methods=['GET'])
def get_campaign_webhook_analytics(campaign_id):
    """Get webhook analytics for a specific campaign"""
    try:
        days = request.args.get('days', 30, type=int)
        analytics_service = create_webhook_analytics_service()
        analytics = analytics_service.get_campaign_analytics(campaign_id=campaign_id, days=days)
        
        return jsonify(analytics), 200
        
    except Exception as e:
        logger.error(f"Error getting campaign analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/api/contact-timeline/<int:contact_id>', methods=['GET'])
def get_contact_webhook_timeline(contact_id):
    """Get webhook event timeline for a specific contact"""
    try:
        days = request.args.get('days', 30, type=int)
        analytics_service = create_webhook_analytics_service()
        timeline = analytics_service.get_contact_timeline(contact_id=contact_id, days=days)
        
        return jsonify({
            'contact_id': contact_id,
            'timeline': timeline,
            'total_events': len(timeline)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting contact timeline: {str(e)}")
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/api/daily-analytics', methods=['GET'])
def get_daily_webhook_analytics():
    """Get day-by-day analytics for dashboard charts"""
    try:
        days = request.args.get('days', 7, type=int)
        analytics_service = create_webhook_analytics_service()
        daily_data = analytics_service.get_daily_analytics(days=days)
        
        return jsonify({
            'period_days': days,
            'daily_data': daily_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting daily analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/api/top-links', methods=['GET'])
def get_top_clicked_links():
    """Get most clicked links from webhook events"""
    try:
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 10, type=int)
        analytics_service = create_webhook_analytics_service()
        top_links = analytics_service.get_top_clicked_links(days=days, limit=limit)
        
        return jsonify({
            'period_days': days,
            'top_links': top_links
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting top links: {str(e)}")
        return jsonify({'error': str(e)}), 500