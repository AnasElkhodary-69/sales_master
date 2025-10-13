"""
Enhanced Sequence Analytics Service for SalesBreachPro
Integrates Brevo tracking data with sequence flow management
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from models.database import db, EmailSequence, Contact, Campaign, Email, ContactCampaignStatus
from sqlalchemy import func, and_, or_

class SequenceAnalyticsService:
    """Service for advanced sequence analytics and flow management"""

    def get_sequence_performance_summary(self, days: int = 30) -> Dict:
        """Get overall sequence performance metrics"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Get sequence statistics
            total_sequences = EmailSequence.query.filter(
                EmailSequence.created_at >= cutoff_date
            ).count()

            completed_sequences = EmailSequence.query.filter(
                and_(
                    EmailSequence.created_at >= cutoff_date,
                    EmailSequence.status == 'sent'
                )
            ).count()

            # Get engagement metrics from emails
            sequence_emails = db.session.query(Email).join(EmailSequence).filter(
                EmailSequence.created_at >= cutoff_date
            ).all()

            total_opens = sum(1 for email in sequence_emails if email.opened_at)
            total_clicks = sum(1 for email in sequence_emails if email.clicked_at)
            total_replies = sum(1 for email in sequence_emails if email.replied_at)
            total_bounces = sum(1 for email in sequence_emails if email.bounced_at)
            total_sent = len([e for e in sequence_emails if e.sent_at])

            # Calculate rates
            open_rate = (total_opens / total_sent * 100) if total_sent > 0 else 0
            click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0
            reply_rate = (total_replies / total_sent * 100) if total_sent > 0 else 0
            bounce_rate = (total_bounces / total_sent * 100) if total_sent > 0 else 0

            return {
                'total_sequences': total_sequences,
                'completed_sequences': completed_sequences,
                'completion_rate': (completed_sequences / total_sequences * 100) if total_sequences > 0 else 0,
                'emails_sent': total_sent,
                'engagement_metrics': {
                    'opens': total_opens,
                    'clicks': total_clicks,
                    'replies': total_replies,
                    'bounces': total_bounces,
                    'open_rate': round(open_rate, 2),
                    'click_rate': round(click_rate, 2),
                    'reply_rate': round(reply_rate, 2),
                    'bounce_rate': round(bounce_rate, 2)
                }
            }

        except Exception as e:
            print(f"Error getting sequence performance summary: {e}")
            return self._get_default_summary()

    def get_active_sequences_with_tracking(self) -> List[Dict]:
        """Get active sequences with detailed tracking information"""
        try:
            # Get active campaigns with sequence data
            active_campaigns = Campaign.query.filter_by(status='active').all()

            sequences_data = []

            for campaign in active_campaigns:
                # Get sequence statistics for this campaign
                sequence_stats = self._get_campaign_sequence_stats(campaign.id)

                # Get recent activity
                recent_activity = self._get_campaign_recent_activity(campaign.id)

                # Get next scheduled emails
                next_emails = self._get_next_scheduled_emails(campaign.id)

                sequences_data.append({
                    'campaign': {
                        'id': campaign.id,
                        'name': campaign.name,
                        'template_type': campaign.template_type,
                        'status': campaign.status,
                        'created_at': campaign.created_at.isoformat() if campaign.created_at else None
                    },
                    'sequence_stats': sequence_stats,
                    'recent_activity': recent_activity,
                    'next_emails': next_emails
                })

            return sequences_data

        except Exception as e:
            print(f"Error getting active sequences: {e}")
            return []

    def get_sequence_flow_visualization(self, campaign_id: int) -> Dict:
        """Get data for sequence flow visualization"""
        try:
            # Get all sequences for this campaign grouped by step
            sequences_by_step = db.session.query(
                EmailSequence.sequence_step,
                func.count(EmailSequence.id).label('total'),
                func.count(EmailSequence.sent_at).label('sent'),
                func.count(
                    func.case([(EmailSequence.status == 'scheduled', 1)], else_=None)
                ).label('scheduled'),
                func.count(
                    func.case([(EmailSequence.status == 'skipped_replied', 1)], else_=None)
                ).label('skipped')
            ).filter(
                EmailSequence.campaign_id == campaign_id
            ).group_by(EmailSequence.sequence_step).all()

            # Get engagement data for each step
            engagement_by_step = {}

            for step, total, sent, scheduled, skipped in sequences_by_step:
                # Get emails for this step
                step_emails = db.session.query(Email).join(EmailSequence).filter(
                    and_(
                        EmailSequence.campaign_id == campaign_id,
                        EmailSequence.sequence_step == step
                    )
                ).all()

                opens = sum(1 for email in step_emails if email.opened_at)
                clicks = sum(1 for email in step_emails if email.clicked_at)
                replies = sum(1 for email in step_emails if email.replied_at)
                bounces = sum(1 for email in step_emails if email.bounced_at)

                engagement_by_step[step] = {
                    'step': step,
                    'total_contacts': total,
                    'emails_sent': sent,
                    'emails_scheduled': scheduled,
                    'emails_skipped': skipped,
                    'engagement': {
                        'opens': opens,
                        'clicks': clicks,
                        'replies': replies,
                        'bounces': bounces,
                        'open_rate': (opens / sent * 100) if sent > 0 else 0,
                        'click_rate': (clicks / sent * 100) if sent > 0 else 0,
                        'reply_rate': (replies / sent * 100) if sent > 0 else 0,
                        'bounce_rate': (bounces / sent * 100) if sent > 0 else 0
                    }
                }

            return {
                'campaign_id': campaign_id,
                'flow_data': engagement_by_step,
                'total_contacts': sum(data['total_contacts'] for data in engagement_by_step.values()),
                'total_sent': sum(data['emails_sent'] for data in engagement_by_step.values())
            }

        except Exception as e:
            print(f"Error getting sequence flow visualization: {e}")
            return {'campaign_id': campaign_id, 'flow_data': {}, 'total_contacts': 0, 'total_sent': 0}

    def get_contact_sequence_journey(self, contact_id: int) -> List[Dict]:
        """Get detailed sequence journey for a specific contact"""
        try:
            contact = Contact.query.get(contact_id)
            if not contact:
                return []

            # Get all sequences for this contact
            sequences = EmailSequence.query.filter_by(contact_id=contact_id).order_by(
                EmailSequence.campaign_id, EmailSequence.sequence_step
            ).all()

            journey = []

            for sequence in sequences:
                email_data = None
                if sequence.email_id:
                    email = Email.query.get(sequence.email_id)
                    if email:
                        email_data = {
                            'subject': email.subject,
                            'sent_at': email.sent_at.isoformat() if email.sent_at else None,
                            'opened_at': email.opened_at.isoformat() if email.opened_at else None,
                            'clicked_at': email.clicked_at.isoformat() if email.clicked_at else None,
                            'replied_at': email.replied_at.isoformat() if email.replied_at else None,
                            'bounced_at': email.bounced_at.isoformat() if email.bounced_at else None,
                            'status': email.status,
                            'open_count': email.open_count or 0,
                            'click_count': email.click_count or 0
                        }

                journey.append({
                    'sequence_id': sequence.id,
                    'campaign_id': sequence.campaign_id,
                    'campaign_name': sequence.campaign.name if sequence.campaign else 'Unknown',
                    'sequence_step': sequence.sequence_step,
                    'template_type': sequence.template_type,
                    'scheduled_date': sequence.scheduled_date.isoformat() if sequence.scheduled_date else None,
                    'scheduled_datetime': sequence.scheduled_datetime.isoformat() if sequence.scheduled_datetime else None,
                    'sent_at': sequence.sent_at.isoformat() if sequence.sent_at else None,
                    'status': sequence.status,
                    'skip_reason': sequence.skip_reason,
                    'email': email_data
                })

            return journey

        except Exception as e:
            print(f"Error getting contact sequence journey: {e}")
            return []

    def get_real_time_sequence_updates(self, campaign_ids: List[int] = None) -> Dict:
        """Get real-time updates for sequence monitoring"""
        try:
            # Filter by specific campaigns if provided
            base_query = EmailSequence.query

            if campaign_ids:
                base_query = base_query.filter(EmailSequence.campaign_id.in_(campaign_ids))

            # Get recent activity (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)

            # Recently sent emails
            recently_sent = base_query.filter(
                and_(
                    EmailSequence.sent_at >= recent_cutoff,
                    EmailSequence.status == 'sent'
                )
            ).count()

            # Scheduled for next 24 hours
            next_24h_cutoff = datetime.utcnow() + timedelta(hours=24)
            upcoming_scheduled = base_query.filter(
                and_(
                    EmailSequence.status == 'scheduled',
                    EmailSequence.scheduled_datetime <= next_24h_cutoff,
                    EmailSequence.scheduled_datetime >= datetime.utcnow()
                )
            ).count()

            # Recently stopped sequences (due to replies)
            recently_stopped = base_query.filter(
                and_(
                    EmailSequence.status == 'skipped_replied',
                    EmailSequence.sent_at >= recent_cutoff
                )
            ).count()

            return {
                'timestamp': datetime.utcnow().isoformat(),
                'recently_sent': recently_sent,
                'upcoming_scheduled': upcoming_scheduled,
                'recently_stopped': recently_stopped,
                'active_sequences': base_query.filter(EmailSequence.status == 'scheduled').count()
            }

        except Exception as e:
            print(f"Error getting real-time sequence updates: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'recently_sent': 0,
                'upcoming_scheduled': 0,
                'recently_stopped': 0,
                'active_sequences': 0
            }

    def _get_campaign_sequence_stats(self, campaign_id: int) -> Dict:
        """Get sequence statistics for a specific campaign"""
        try:
            sequences = EmailSequence.query.filter_by(campaign_id=campaign_id).all()

            total_sequences = len(sequences)
            sent_sequences = sum(1 for s in sequences if s.status == 'sent')
            scheduled_sequences = sum(1 for s in sequences if s.status == 'scheduled')
            skipped_sequences = sum(1 for s in sequences if s.status.startswith('skipped'))

            return {
                'total': total_sequences,
                'sent': sent_sequences,
                'scheduled': scheduled_sequences,
                'skipped': skipped_sequences,
                'completion_rate': (sent_sequences / total_sequences * 100) if total_sequences > 0 else 0
            }

        except Exception as e:
            print(f"Error getting campaign sequence stats: {e}")
            return {'total': 0, 'sent': 0, 'scheduled': 0, 'skipped': 0, 'completion_rate': 0}

    def _get_campaign_recent_activity(self, campaign_id: int, hours: int = 24) -> List[Dict]:
        """Get recent activity for a campaign"""
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            # Get recent email activities
            recent_emails = db.session.query(Email).join(EmailSequence).filter(
                and_(
                    EmailSequence.campaign_id == campaign_id,
                    or_(
                        Email.sent_at >= cutoff,
                        Email.opened_at >= cutoff,
                        Email.clicked_at >= cutoff,
                        Email.replied_at >= cutoff
                    )
                )
            ).order_by(Email.sent_at.desc()).limit(10).all()

            activities = []

            for email in recent_emails:
                contact = Contact.query.get(email.contact_id)

                # Determine most recent activity
                activity_type = 'sent'
                activity_time = email.sent_at

                if email.replied_at and (not activity_time or email.replied_at > activity_time):
                    activity_type = 'replied'
                    activity_time = email.replied_at
                elif email.clicked_at and (not activity_time or email.clicked_at > activity_time):
                    activity_type = 'clicked'
                    activity_time = email.clicked_at
                elif email.opened_at and (not activity_time or email.opened_at > activity_time):
                    activity_type = 'opened'
                    activity_time = email.opened_at

                activities.append({
                    'contact_email': contact.email if contact else 'Unknown',
                    'activity_type': activity_type,
                    'activity_time': activity_time.isoformat() if activity_time else None,
                    'subject': email.subject,
                    'email_id': email.id
                })

            return activities

        except Exception as e:
            print(f"Error getting campaign recent activity: {e}")
            return []

    def _get_next_scheduled_emails(self, campaign_id: int, limit: int = 10) -> List[Dict]:
        """Get next scheduled emails for a campaign"""
        try:
            upcoming = EmailSequence.query.filter(
                and_(
                    EmailSequence.campaign_id == campaign_id,
                    EmailSequence.status == 'scheduled',
                    EmailSequence.scheduled_datetime >= datetime.utcnow()
                )
            ).order_by(EmailSequence.scheduled_datetime).limit(limit).all()

            next_emails = []

            for sequence in upcoming:
                contact = Contact.query.get(sequence.contact_id)

                next_emails.append({
                    'sequence_id': sequence.id,
                    'contact_email': contact.email if contact else 'Unknown',
                    'sequence_step': sequence.sequence_step,
                    'template_type': sequence.template_type,
                    'scheduled_datetime': sequence.scheduled_datetime.isoformat() if sequence.scheduled_datetime else None,
                    'time_until_send': self._calculate_time_until(sequence.scheduled_datetime) if sequence.scheduled_datetime else None
                })

            return next_emails

        except Exception as e:
            print(f"Error getting next scheduled emails: {e}")
            return []

    def _calculate_time_until(self, target_datetime: datetime) -> str:
        """Calculate human-readable time until target datetime"""
        try:
            delta = target_datetime - datetime.utcnow()

            if delta.days > 0:
                return f"{delta.days} day{'s' if delta.days != 1 else ''}"
            elif delta.seconds > 3600:
                hours = delta.seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''}"
            elif delta.seconds > 60:
                minutes = delta.seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''}"
            else:
                return "Less than 1 minute"

        except Exception as e:
            return "Unknown"

    def _get_default_summary(self) -> Dict:
        """Return default summary when there's an error"""
        return {
            'total_sequences': 0,
            'completed_sequences': 0,
            'completion_rate': 0,
            'emails_sent': 0,
            'engagement_metrics': {
                'opens': 0,
                'clicks': 0,
                'replies': 0,
                'bounces': 0,
                'open_rate': 0,
                'click_rate': 0,
                'reply_rate': 0,
                'bounce_rate': 0
            }
        }


def create_sequence_analytics_service() -> SequenceAnalyticsService:
    """Factory function to create sequence analytics service"""
    return SequenceAnalyticsService()