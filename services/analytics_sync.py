"""
Analytics Sync Service - Syncs Brevo email statistics with dashboard
Pulls open rates, click rates, bounce rates from Brevo API
"""
import logging
from datetime import datetime, timedelta
from typing import Dict
from models.database import db, Campaign, Email, Contact
from services.brevo_modern_service import BrevoModernService

logger = logging.getLogger(__name__)

class AnalyticsSync:
    """Sync email analytics from Brevo to local dashboard"""
    
    def __init__(self):
        self.brevo_service = None
        logger.info("Analytics Sync Service initialized")
    
    def sync_campaign_analytics(self, campaign_id: int = None) -> Dict:
        """
        Sync analytics for a specific campaign or all campaigns
        Updates open rates, click rates, reply rates in database
        """
        try:
            # Initialize Brevo service if needed
            if not self.brevo_service:
                from config import Config
                self.brevo_service = BrevoModernService(Config)
            
            if campaign_id:
                campaigns = [Campaign.query.get(campaign_id)]
            else:
                # Sync all active campaigns
                campaigns = Campaign.query.filter_by(status='active').all()
            
            results = {
                'campaigns_synced': 0,
                'emails_updated': 0,
                'errors': []
            }
            
            for campaign in campaigns:
                if not campaign:
                    continue
                
                try:
                    # Get analytics from Brevo
                    analytics = self.brevo_service.get_advanced_analytics(
                        campaign_id=str(campaign.id),
                        days=30
                    )
                    
                    if analytics and not analytics.get('error'):
                        # Update campaign statistics
                        self._update_campaign_stats(campaign, analytics)
                        results['campaigns_synced'] += 1
                        
                        # Update individual email statistics
                        emails_updated = self._update_email_stats(campaign.id, analytics)
                        results['emails_updated'] += emails_updated
                        
                except Exception as e:
                    logger.error(f"Error syncing campaign {campaign.id}: {str(e)}")
                    results['errors'].append(f"Campaign {campaign.id}: {str(e)}")
            
            db.session.commit()
            logger.info(f"Analytics sync completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error in analytics sync: {str(e)}")
            db.session.rollback()
            return {'error': str(e), 'campaigns_synced': 0}
    
    def _update_campaign_stats(self, campaign: Campaign, analytics: Dict):
        """Update campaign-level statistics"""
        try:
            # Extract metrics from analytics
            basic_metrics = analytics.get('basic_metrics', {})
            advanced_metrics = analytics.get('advanced_metrics', {})
            
            # Update campaign fields
            if hasattr(campaign, 'emails_delivered'):
                campaign.emails_delivered = basic_metrics.get('delivered', 0)
            
            if hasattr(campaign, 'emails_opened'):
                campaign.emails_opened = basic_metrics.get('opened', 0)
            
            if hasattr(campaign, 'emails_clicked'):
                campaign.emails_clicked = basic_metrics.get('clicked', 0)
            
            if hasattr(campaign, 'emails_replied'):
                campaign.emails_replied = basic_metrics.get('replied', 0)
            
            if hasattr(campaign, 'emails_bounced'):
                campaign.emails_bounced = basic_metrics.get('bounced', 0)
            
            # Update rates
            if hasattr(campaign, 'open_rate'):
                campaign.open_rate = advanced_metrics.get('open_rate', 0)
            
            if hasattr(campaign, 'click_rate'):
                campaign.click_rate = advanced_metrics.get('click_rate', 0)
            
            if hasattr(campaign, 'reply_rate'):
                campaign.reply_rate = advanced_metrics.get('reply_rate', 0)
            
            # Update response count (replies)
            campaign.response_count = basic_metrics.get('replied', 0)
            
            # Update last sync time
            if hasattr(campaign, 'last_analytics_sync'):
                campaign.last_analytics_sync = datetime.utcnow()
            
            logger.info(f"Updated stats for campaign {campaign.name}: "
                       f"Delivered={basic_metrics.get('delivered', 0)}, "
                       f"Opens={basic_metrics.get('opened', 0)}, "
                       f"Clicks={basic_metrics.get('clicked', 0)}")
            
        except Exception as e:
            logger.error(f"Error updating campaign stats: {str(e)}")
    
    def _update_email_stats(self, campaign_id: int, analytics: Dict) -> int:
        """Update individual email statistics"""
        count = 0
        try:
            # Get email events from analytics
            events = analytics.get('events', [])
            
            for event in events:
                email_id = event.get('email_id')
                if not email_id:
                    continue
                
                email = Email.query.filter_by(
                    id=email_id,
                    campaign_id=campaign_id
                ).first()
                
                if email:
                    # Update based on event type
                    event_type = event.get('type', '').lower()
                    
                    if event_type == 'opened' and not email.opened_at:
                        email.opened_at = event.get('timestamp')
                        email.status = 'opened'
                        count += 1
                    
                    elif event_type == 'clicked' and not email.clicked_at:
                        email.clicked_at = event.get('timestamp')
                        email.status = 'clicked'
                        count += 1
                    
                    elif event_type == 'replied' and not email.replied_at:
                        email.replied_at = event.get('timestamp')
                        email.status = 'replied'
                        count += 1
                        
                        # Also mark contact as replied
                        self._mark_contact_replied(email.contact_id, campaign_id)
                    
                    elif event_type == 'bounced' and not email.bounced_at:
                        email.bounced_at = event.get('timestamp')
                        email.status = 'bounced'
                        count += 1
            
            return count
            
        except Exception as e:
            logger.error(f"Error updating email stats: {str(e)}")
            return 0
    
    def _mark_contact_replied(self, contact_id: int, campaign_id: int):
        """Mark contact as replied in campaign status"""
        try:
            from models.database import ContactCampaignStatus
            
            status = ContactCampaignStatus.query.filter_by(
                contact_id=contact_id,
                campaign_id=campaign_id
            ).first()
            
            if status and not status.replied_at:
                status.replied_at = datetime.utcnow()
                logger.info(f"Marked contact {contact_id} as replied in campaign {campaign_id}")
            
            # Also update contact
            contact = Contact.query.get(contact_id)
            if contact:
                if hasattr(contact, 'has_responded'):
                    contact.has_responded = True
                if hasattr(contact, 'responded_at'):
                    contact.responded_at = datetime.utcnow()
                    
        except Exception as e:
            logger.error(f"Error marking contact as replied: {str(e)}")
    
    def get_dashboard_metrics(self) -> Dict:
        """Get aggregated metrics for dashboard display"""
        try:
            # Calculate overall metrics
            total_campaigns = Campaign.query.count()
            active_campaigns = Campaign.query.filter_by(status='active').count()
            
            # Email metrics
            total_sent = db.session.query(db.func.sum(Campaign.sent_count)).scalar() or 0
            total_responses = db.session.query(db.func.sum(Campaign.response_count)).scalar() or 0
            
            # Calculate average rates
            campaigns_with_stats = Campaign.query.filter(Campaign.sent_count > 0).all()
            
            avg_open_rate = 0
            avg_click_rate = 0
            avg_response_rate = 0
            
            if campaigns_with_stats:
                open_rates = [c.open_rate for c in campaigns_with_stats if hasattr(c, 'open_rate') and c.open_rate]
                click_rates = [c.click_rate for c in campaigns_with_stats if hasattr(c, 'click_rate') and c.click_rate]
                
                if open_rates:
                    avg_open_rate = sum(open_rates) / len(open_rates)
                if click_rates:
                    avg_click_rate = sum(click_rates) / len(click_rates)
                if total_sent > 0:
                    avg_response_rate = (total_responses / total_sent) * 100
            
            return {
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'total_emails_sent': total_sent,
                'total_responses': total_responses,
                'average_open_rate': round(avg_open_rate, 1),
                'average_click_rate': round(avg_click_rate, 1),
                'average_response_rate': round(avg_response_rate, 1),
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {str(e)}")
            return {}

# Global analytics sync instance
analytics_sync = AnalyticsSync()

def sync_all_analytics():
    """Function to be called by scheduler or manually"""
    return analytics_sync.sync_campaign_analytics()

def get_dashboard_stats():
    """Get current dashboard statistics"""
    return analytics_sync.get_dashboard_metrics()