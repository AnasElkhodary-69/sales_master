"""
Manual Email Trigger Route - For testing email sending immediately
"""
from flask import Blueprint, jsonify, request
from utils.decorators import login_required
from models.database import db, Campaign, EmailSequence
from datetime import date
import logging

logger = logging.getLogger(__name__)

email_trigger_bp = Blueprint('email_trigger', __name__)

@email_trigger_bp.route('/api/trigger-emails', methods=['POST'])
@login_required
def trigger_emails():
    """
    Manually trigger email processing for testing
    This will process all scheduled emails immediately
    """
    try:
        # Get campaign ID if specified
        campaign_id = request.json.get('campaign_id') if request.json else None
        
        # Show what emails are scheduled
        query = EmailSequence.query.filter(
            EmailSequence.status == 'scheduled',
            EmailSequence.scheduled_date <= date.today()
        )
        
        if campaign_id:
            query = query.filter(EmailSequence.campaign_id == campaign_id)
        
        scheduled_count = query.count()
        
        logger.info(f"Manual email trigger initiated. Found {scheduled_count} emails to process")

        # Process the email queue using original function
        from services.email_processor import process_email_queue
        results = process_email_queue()

        # Add scheduled count to results
        results['scheduled_count'] = scheduled_count
        
        return jsonify({
            'success': True,
            'message': f'Email processing triggered successfully',
            'results': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error triggering emails: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@email_trigger_bp.route('/api/check-scheduled-emails', methods=['GET'])
@login_required
def check_scheduled_emails():
    """
    Check what emails are currently scheduled to be sent
    """
    try:
        # Get scheduled emails
        scheduled = EmailSequence.query.filter(
            EmailSequence.status == 'scheduled',
            EmailSequence.scheduled_date <= date.today()
        ).all()
        
        emails_by_campaign = {}
        
        for email in scheduled:
            campaign = Campaign.query.get(email.campaign_id)
            campaign_name = campaign.name if campaign else f"Campaign {email.campaign_id}"
            
            if campaign_name not in emails_by_campaign:
                emails_by_campaign[campaign_name] = []
            
            emails_by_campaign[campaign_name].append({
                'contact_id': email.contact_id,
                'sequence_step': email.sequence_step,
                'template_type': email.template_type,
                'scheduled_date': email.scheduled_date.isoformat() if email.scheduled_date else None
            })
        
        return jsonify({
            'success': True,
            'total_scheduled': len(scheduled),
            'by_campaign': emails_by_campaign,
            'message': f'{len(scheduled)} emails are ready to be sent'
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking scheduled emails: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500