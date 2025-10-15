"""
Campaign Analytics Service
Provides accurate real-time campaign metrics using webhook data from Brevo
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from models.database import db, Campaign, Email, Contact, ContactCampaignStatus, EmailSequence

logger = logging.getLogger(__name__)

class CampaignAnalytics:
    """Service for generating accurate campaign analytics from Brevo webhook data"""
    
    def __init__(self):
        pass
    
    def get_campaign_metrics(self, campaign_id: int) -> Dict:
        """
        Get comprehensive campaign metrics with real-time data from webhooks
        Returns detailed analytics for campaign dashboard
        """
        try:
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                return {'error': 'Campaign not found'}
            
            # Get all emails for this campaign with contact information
            emails_with_contacts = db.session.query(Email, Contact).join(
                Contact, Email.contact_id == Contact.id
            ).filter(Email.campaign_id == campaign_id).all()

            emails = [email for email, contact in emails_with_contacts]

            # Basic counts
            total_emails = len(emails)
            sent_count = sum(1 for email in emails if email.status in ['sent', 'delivered', 'opened', 'clicked', 'replied'])
            pending_count = sum(1 for email in emails if email.status == 'pending')
            delivered_count = sum(1 for email in emails if email.delivered_at is not None)
            opened_count = sum(1 for email in emails if email.opened_at is not None)
            clicked_count = sum(1 for email in emails if email.clicked_at is not None)
            replied_count = sum(1 for email in emails if email.replied_at is not None)
            bounced_count = sum(1 for email in emails if email.bounced_at is not None)
            # Count blocked emails: either email is blocked OR the contact is blocked
            blocked_count = sum(1 for email, contact in emails_with_contacts
                              if email.blocked_at is not None or contact.blocked_at is not None)
            
            # Calculate rates (avoid division by zero)
            delivery_rate = (delivered_count / sent_count * 100) if sent_count > 0 else 0
            open_rate = (opened_count / delivered_count * 100) if delivered_count > 0 else 0
            click_rate = (clicked_count / delivered_count * 100) if delivered_count > 0 else 0
            reply_rate = (replied_count / delivered_count * 100) if delivered_count > 0 else 0
            bounce_rate = (bounced_count / sent_count * 100) if sent_count > 0 else 0
            blocked_rate = (blocked_count / sent_count * 100) if sent_count > 0 else 0
            
            # Get contact engagement stats
            enrolled_contacts = Contact.query.join(Email).filter(Email.campaign_id == campaign_id).distinct().count()
            
            # Get sequence completion stats
            contact_statuses = ContactCampaignStatus.query.filter_by(campaign_id=campaign_id).all()
            active_sequences = sum(1 for status in contact_statuses if not status.replied_at and not status.sequence_completed_at)
            stopped_sequences = sum(1 for status in contact_statuses if status.replied_at is not None)
            completed_sequences = sum(1 for status in contact_statuses if status.sequence_completed_at is not None)
            
            # Recent activity (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(hours=24)
            recent_opens = sum(1 for email in emails if email.opened_at and email.opened_at > yesterday)
            recent_clicks = sum(1 for email in emails if email.clicked_at and email.clicked_at > yesterday)
            recent_replies = sum(1 for email in emails if email.replied_at and email.replied_at > yesterday)
            
            return {
                'campaign_id': campaign_id,
                'campaign_name': campaign.name,
                'campaign_status': campaign.status,
                'created_at': campaign.created_at,
                
                # Email Statistics
                'email_stats': {
                    'total_emails': total_emails,
                    'sent_count': sent_count,
                    'delivered_count': delivered_count,
                    'opened_count': opened_count,
                    'clicked_count': clicked_count,
                    'replied_count': replied_count,
                    'bounced_count': bounced_count,
                    'blocked_count': blocked_count,
                    'pending_count': pending_count
                },
                
                # Performance Rates
                'performance': {
                    'delivery_rate': round(delivery_rate, 2),
                    'open_rate': round(open_rate, 2),
                    'click_rate': round(click_rate, 2),
                    'reply_rate': round(reply_rate, 2),
                    'bounce_rate': round(bounce_rate, 2),
                    'blocked_rate': round(blocked_rate, 2)
                },
                
                # Contact Statistics
                'contacts': {
                    'enrolled_contacts': enrolled_contacts,
                    'active_sequences': active_sequences,
                    'stopped_sequences': stopped_sequences,
                    'completed_sequences': completed_sequences
                },
                
                # Recent Activity
                'recent_activity': {
                    'opens_24h': recent_opens,
                    'clicks_24h': recent_clicks,
                    'replies_24h': recent_replies
                },
                
                # Campaign Settings
                'settings': {
                    'daily_limit': campaign.daily_limit,
                    'auto_enroll': campaign.auto_enroll,
                    'target_industries': campaign.target_industries if hasattr(campaign, 'target_industries') else [],
                    'target_business_types': campaign.target_business_types if hasattr(campaign, 'target_business_types') else [],
                    'target_company_sizes': campaign.target_company_sizes if hasattr(campaign, 'target_company_sizes') else [],
                    'template_id': campaign.template_id
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating campaign metrics for {campaign_id}: {str(e)}")
            return {'error': str(e)}
    
    def get_email_timeline(self, campaign_id: int, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get recent email activity timeline for campaign with pagination"""
        try:
            emails = Email.query.filter_by(campaign_id=campaign_id).order_by(
                Email.sent_at.desc().nullslast(),
                Email.id.desc()
            ).offset(offset).limit(limit).all()
            
            timeline = []
            for email in emails:
                contact = Contact.query.get(email.contact_id) if email.contact_id else None
                
                # Determine the latest event - check for blocked status first
                latest_event = 'pending'
                latest_time = None

                # Check for blocked status from either email or contact (highest priority)
                if email.blocked_at or (contact and contact.blocked_at):
                    latest_event = 'blocked'
                    latest_time = email.blocked_at or contact.blocked_at
                elif email.replied_at:
                    latest_event = 'replied'
                    latest_time = email.replied_at
                elif email.clicked_at:
                    latest_event = 'clicked'
                    latest_time = email.clicked_at
                elif email.opened_at:
                    latest_event = 'opened'
                    latest_time = email.opened_at
                elif email.bounced_at:
                    latest_event = 'bounced'
                    latest_time = email.bounced_at
                elif email.delivered_at:
                    latest_event = 'delivered'
                    latest_time = email.delivered_at
                elif email.sent_at:
                    latest_event = 'sent'
                    latest_time = email.sent_at
                
                timeline.append({
                    'email_id': email.id,
                    'contact_email': contact.email if contact else 'Unknown',
                    'contact_name': f"{contact.first_name} {contact.last_name}".strip() if contact else 'Unknown',
                    'contact_company': contact.company if contact else '',
                    'subject': email.subject,
                    'status': email.status,
                    'latest_event': latest_event,
                    'latest_time': latest_time,
                    'sent_at': email.sent_at,
                    'delivered_at': email.delivered_at,
                    'opened_at': email.opened_at,
                    'clicked_at': email.clicked_at,
                    'replied_at': email.replied_at,
                    'bounced_at': email.bounced_at,
                    'blocked_at': email.blocked_at or (contact.blocked_at if contact else None),
                    'block_reason': email.block_reason or (contact.block_reason if contact else None),
                    'open_count': email.open_count or 0,
                    'click_count': email.click_count or 0,
                    'bounce_type': email.bounce_type
                })
            
            return timeline
            
        except Exception as e:
            logger.error(f"Error generating email timeline for campaign {campaign_id}: {str(e)}")
            return []
    
    def get_campaign_summary(self, campaign_id: int) -> Dict:
        """Get a quick summary for campaign list view"""
        try:
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                return {'error': 'Campaign not found'}
            
            emails = Email.query.filter_by(campaign_id=campaign_id).all()
            
            # Quick stats
            total_emails = len(emails)
            delivered_count = sum(1 for email in emails if email.delivered_at is not None)
            replied_count = sum(1 for email in emails if email.replied_at is not None)
            
            # Most recent activity
            latest_activity = None
            if emails:
                latest_email = max(emails, key=lambda e: e.sent_at or datetime.min)
                if latest_email.sent_at:
                    latest_activity = latest_email.sent_at
            
            return {
                'id': campaign_id,
                'name': campaign.name,
                'status': campaign.status,
                'total_emails': total_emails,
                'delivered_count': delivered_count,
                'replied_count': replied_count,
                'reply_rate': round((replied_count / delivered_count * 100) if delivered_count > 0 else 0, 1),
                'latest_activity': latest_activity,
                'created_at': campaign.created_at
            }
            
        except Exception as e:
            logger.error(f"Error generating campaign summary for {campaign_id}: {str(e)}")
            return {'error': str(e)}

def create_campaign_analytics():
    """Factory function to create campaign analytics service"""
    return CampaignAnalytics()