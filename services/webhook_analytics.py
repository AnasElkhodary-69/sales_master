"""
Webhook Analytics Service
Handles saving webhook events and generating statistics
"""
from models.database import db, WebhookEvent, Contact, Email, Campaign
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
import logging

logger = logging.getLogger(__name__)

class WebhookAnalyticsService:
    """Service for processing webhook events and generating analytics"""
    
    def save_webhook_event(self, contact, email, campaign, event_data):
        """
        Save a webhook event to the database for analytics
        
        Args:
            contact: Contact object
            email: Email object (can be None)
            campaign: Campaign object (can be None)
            event_data: Full webhook payload data
        """
        try:
            # Extract common fields from event data
            event_type = event_data.get('event', '').lower()
            provider_message_id = event_data.get('message-id', event_data.get('MessageId', ''))
            
            # Extract timestamp
            event_timestamp = datetime.utcnow()
            if 'timestamp' in event_data:
                try:
                    timestamp_str = event_data['timestamp']
                    if isinstance(timestamp_str, str):
                        event_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    elif isinstance(timestamp_str, (int, float)):
                        event_timestamp = datetime.fromtimestamp(timestamp_str)
                except:
                    pass  # Use current time if parsing fails
            
            # Create webhook event record
            webhook_event = WebhookEvent(
                contact_id=contact.id,
                email_id=email.id if email else None,
                campaign_id=campaign.id if campaign else None,
                event_type=event_type,
                provider='brevo',
                provider_message_id=provider_message_id,
                event_data=event_data,
                ip_address=event_data.get('ip', ''),
                user_agent=event_data.get('user_agent', ''),
                clicked_url=event_data.get('link', ''),
                bounce_reason=event_data.get('reason', ''),
                bounce_type=event_data.get('bounce_type', ''),
                event_timestamp=event_timestamp,
                processed_at=datetime.utcnow()
            )
            
            db.session.add(webhook_event)
            logger.info(f"Saved webhook event: {event_type} for contact {contact.email}")
            
            return webhook_event
            
        except Exception as e:
            logger.error(f"Error saving webhook event: {str(e)}")
            return None
    
    def get_email_analytics(self, days=30):
        """Get email analytics based on webhook events"""
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Get counts by event type
            event_counts = db.session.query(
                WebhookEvent.event_type,
                func.count(WebhookEvent.id).label('count')
            ).filter(
                WebhookEvent.event_timestamp >= since_date
            ).group_by(WebhookEvent.event_type).all()
            
            # Convert to dictionary
            analytics = {event_type: count for event_type, count in event_counts}
            
            # Calculate rates
            total_sent = analytics.get('delivered', 0)
            total_opened = analytics.get('opened', 0)
            total_clicked = analytics.get('clicked', 0)
            total_replied = analytics.get('replied', 0)
            total_bounced = analytics.get('bounced', 0)
            total_unsubscribed = analytics.get('unsubscribed', 0)
            total_spam = analytics.get('spam', 0)
            
            return {
                'period_days': days,
                'total_sent': total_sent,
                'total_delivered': total_sent,  # Assuming delivered events are tracked
                'total_opened': total_opened,
                'total_clicked': total_clicked,
                'total_replied': total_replied,
                'total_bounced': total_bounced,
                'total_unsubscribed': total_unsubscribed,
                'total_spam': total_spam,
                'open_rate': round((total_opened / total_sent * 100), 2) if total_sent > 0 else 0,
                'click_rate': round((total_clicked / total_sent * 100), 2) if total_sent > 0 else 0,
                'reply_rate': round((total_replied / total_sent * 100), 2) if total_sent > 0 else 0,
                'bounce_rate': round((total_bounced / total_sent * 100), 2) if total_sent > 0 else 0,
                'unsubscribe_rate': round((total_unsubscribed / total_sent * 100), 2) if total_sent > 0 else 0,
                'spam_rate': round((total_spam / total_sent * 100), 2) if total_sent > 0 else 0,
                'event_breakdown': analytics
            }
            
        except Exception as e:
            logger.error(f"Error getting email analytics: {str(e)}")
            return {
                'period_days': days,
                'total_sent': 0,
                'total_delivered': 0,
                'total_opened': 0,
                'total_clicked': 0,
                'total_replied': 0,
                'total_bounced': 0,
                'total_unsubscribed': 0,
                'total_spam': 0,
                'open_rate': 0,
                'click_rate': 0,
                'reply_rate': 0,
                'bounce_rate': 0,
                'unsubscribe_rate': 0,
                'spam_rate': 0,
                'event_breakdown': {}
            }
    
    def get_campaign_analytics(self, campaign_id, days=30):
        """Get analytics for a specific campaign"""
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Get events for this campaign
            event_counts = db.session.query(
                WebhookEvent.event_type,
                func.count(WebhookEvent.id).label('count')
            ).filter(
                and_(
                    WebhookEvent.campaign_id == campaign_id,
                    WebhookEvent.event_timestamp >= since_date
                )
            ).group_by(WebhookEvent.event_type).all()
            
            analytics = {event_type: count for event_type, count in event_counts}
            
            # Get unique contact engagement
            unique_opens = db.session.query(
                func.count(func.distinct(WebhookEvent.contact_id))
            ).filter(
                and_(
                    WebhookEvent.campaign_id == campaign_id,
                    WebhookEvent.event_type == 'opened',
                    WebhookEvent.event_timestamp >= since_date
                )
            ).scalar() or 0
            
            unique_clicks = db.session.query(
                func.count(func.distinct(WebhookEvent.contact_id))
            ).filter(
                and_(
                    WebhookEvent.campaign_id == campaign_id,
                    WebhookEvent.event_type == 'clicked',
                    WebhookEvent.event_timestamp >= since_date
                )
            ).scalar() or 0
            
            unique_replies = db.session.query(
                func.count(func.distinct(WebhookEvent.contact_id))
            ).filter(
                and_(
                    WebhookEvent.campaign_id == campaign_id,
                    WebhookEvent.event_type == 'replied',
                    WebhookEvent.event_timestamp >= since_date
                )
            ).scalar() or 0
            
            total_sent = analytics.get('delivered', 0)
            
            return {
                'campaign_id': campaign_id,
                'period_days': days,
                'total_sent': total_sent,
                'total_opened': analytics.get('opened', 0),
                'total_clicked': analytics.get('clicked', 0),
                'total_replied': analytics.get('replied', 0),
                'total_bounced': analytics.get('bounced', 0),
                'unique_opens': unique_opens,
                'unique_clicks': unique_clicks,
                'unique_replies': unique_replies,
                'open_rate': round((unique_opens / total_sent * 100), 2) if total_sent > 0 else 0,
                'click_rate': round((unique_clicks / total_sent * 100), 2) if total_sent > 0 else 0,
                'reply_rate': round((unique_replies / total_sent * 100), 2) if total_sent > 0 else 0,
                'event_breakdown': analytics
            }
            
        except Exception as e:
            logger.error(f"Error getting campaign analytics: {str(e)}")
            return {
                'campaign_id': campaign_id,
                'period_days': days,
                'total_sent': 0,
                'total_opened': 0,
                'total_clicked': 0,
                'total_replied': 0,
                'total_bounced': 0,
                'unique_opens': 0,
                'unique_clicks': 0,
                'unique_replies': 0,
                'open_rate': 0,
                'click_rate': 0,
                'reply_rate': 0,
                'event_breakdown': {}
            }
    
    def get_contact_timeline(self, contact_id, days=30):
        """Get event timeline for a specific contact"""
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            events = WebhookEvent.query.filter(
                and_(
                    WebhookEvent.contact_id == contact_id,
                    WebhookEvent.event_timestamp >= since_date
                )
            ).order_by(WebhookEvent.event_timestamp.desc()).all()
            
            return [event.to_dict() for event in events]
            
        except Exception as e:
            logger.error(f"Error getting contact timeline: {str(e)}")
            return []
    
    def get_daily_analytics(self, days=7):
        """Get day-by-day analytics for the dashboard"""
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Get daily event counts
            daily_stats = db.session.query(
                func.date(WebhookEvent.event_timestamp).label('date'),
                WebhookEvent.event_type,
                func.count(WebhookEvent.id).label('count')
            ).filter(
                WebhookEvent.event_timestamp >= since_date
            ).group_by(
                func.date(WebhookEvent.event_timestamp),
                WebhookEvent.event_type
            ).order_by(func.date(WebhookEvent.event_timestamp)).all()
            
            # Organize by date
            daily_data = {}
            for date, event_type, count in daily_stats:
                date_str = date.strftime('%Y-%m-%d')
                if date_str not in daily_data:
                    daily_data[date_str] = {}
                daily_data[date_str][event_type] = count
            
            return daily_data
            
        except Exception as e:
            logger.error(f"Error getting daily analytics: {str(e)}")
            return {}
    
    def get_top_clicked_links(self, days=30, limit=10):
        """Get most clicked links"""
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            clicked_links = db.session.query(
                WebhookEvent.clicked_url,
                func.count(WebhookEvent.id).label('clicks')
            ).filter(
                and_(
                    WebhookEvent.event_type == 'clicked',
                    WebhookEvent.clicked_url.isnot(None),
                    WebhookEvent.clicked_url != '',
                    WebhookEvent.event_timestamp >= since_date
                )
            ).group_by(
                WebhookEvent.clicked_url
            ).order_by(
                func.count(WebhookEvent.id).desc()
            ).limit(limit).all()
            
            return [{'url': url, 'clicks': clicks} for url, clicks in clicked_links]
            
        except Exception as e:
            logger.error(f"Error getting top clicked links: {str(e)}")
            return []

def create_webhook_analytics_service():
    """Factory function to create webhook analytics service"""
    return WebhookAnalyticsService()