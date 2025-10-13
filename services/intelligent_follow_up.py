"""
Intelligent Follow-up Service for SalesBreachPro
Automated follow-up decisions based on Brevo engagement tracking
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from models.database import db, EmailSequence, Contact, Campaign, Email, ContactCampaignStatus, EmailTemplate
from sqlalchemy import and_, or_

class IntelligentFollowUpService:
    """Service for automated follow-up decision making based on engagement"""

    def __init__(self):
        self.engagement_thresholds = {
            'high_engagement': {
                'open_rate_min': 50,
                'click_rate_min': 10,
                'reply_probability': 0.8
            },
            'medium_engagement': {
                'open_rate_min': 25,
                'click_rate_min': 5,
                'reply_probability': 0.5
            },
            'low_engagement': {
                'open_rate_min': 10,
                'click_rate_min': 1,
                'reply_probability': 0.2
            }
        }

        self.follow_up_strategies = {
            'aggressive': {'wait_hours': 24, 'max_attempts': 5},
            'moderate': {'wait_hours': 48, 'max_attempts': 3},
            'conservative': {'wait_hours': 72, 'max_attempts': 2}
        }

    def analyze_contact_engagement(self, contact_id: int, days: int = 30) -> Dict:
        """Analyze a contact's engagement patterns"""
        try:
            contact = Contact.query.get(contact_id)
            if not contact:
                return self._get_default_engagement()

            # Get recent emails for this contact
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            recent_emails = Email.query.filter(
                and_(
                    Email.contact_id == contact_id,
                    Email.sent_at >= cutoff_date
                )
            ).all()

            if not recent_emails:
                return self._get_default_engagement()

            # Calculate engagement metrics
            total_sent = len(recent_emails)
            total_opens = sum(1 for email in recent_emails if email.opened_at)
            total_clicks = sum(1 for email in recent_emails if email.clicked_at)
            total_replies = sum(1 for email in recent_emails if email.replied_at)
            total_bounces = sum(1 for email in recent_emails if email.bounced_at)

            # Calculate rates
            open_rate = (total_opens / total_sent * 100) if total_sent > 0 else 0
            click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0
            reply_rate = (total_replies / total_sent * 100) if total_sent > 0 else 0
            bounce_rate = (total_bounces / total_sent * 100) if total_sent > 0 else 0

            # Determine engagement level
            engagement_level = self._determine_engagement_level(open_rate, click_rate)

            # Calculate engagement score (0-100)
            engagement_score = min(100, (open_rate * 0.4) + (click_rate * 0.4) + (reply_rate * 0.2))

            # Analyze timing patterns
            timing_analysis = self._analyze_engagement_timing(recent_emails)

            # Determine if contact is still active
            last_activity = self._get_last_activity_date(recent_emails)
            days_since_activity = (datetime.utcnow() - last_activity).days if last_activity else None

            return {
                'contact_id': contact_id,
                'engagement_level': engagement_level,
                'engagement_score': round(engagement_score, 2),
                'metrics': {
                    'emails_sent': total_sent,
                    'open_rate': round(open_rate, 2),
                    'click_rate': round(click_rate, 2),
                    'reply_rate': round(reply_rate, 2),
                    'bounce_rate': round(bounce_rate, 2)
                },
                'timing_analysis': timing_analysis,
                'days_since_activity': days_since_activity,
                'is_responsive': engagement_score > 20 and days_since_activity is not None and days_since_activity < 14,
                'recommended_strategy': self._recommend_strategy(engagement_level, days_since_activity)
            }

        except Exception as e:
            print(f"Error analyzing contact engagement: {e}")
            return self._get_default_engagement()

    def recommend_follow_up_action(self, contact_id: int, campaign_id: int) -> Dict:
        """Recommend specific follow-up action for a contact in a campaign"""
        try:
            engagement = self.analyze_contact_engagement(contact_id)

            # Get current sequence status
            sequence_status = self._get_sequence_status(contact_id, campaign_id)

            # Get last interaction details
            last_email = Email.query.filter(
                and_(
                    Email.contact_id == contact_id,
                    Email.campaign_id == campaign_id
                )
            ).order_by(Email.sent_at.desc()).first()

            # Determine recommendation based on engagement and current status
            recommendation = self._generate_recommendation(
                engagement, sequence_status, last_email
            )

            return {
                'contact_id': contact_id,
                'campaign_id': campaign_id,
                'engagement_analysis': engagement,
                'sequence_status': sequence_status,
                'recommendation': recommendation,
                'confidence_score': self._calculate_confidence_score(engagement, sequence_status)
            }

        except Exception as e:
            print(f"Error recommending follow-up action: {e}")
            return {
                'contact_id': contact_id,
                'campaign_id': campaign_id,
                'recommendation': {
                    'action': 'continue',
                    'reason': 'Error occurred during analysis',
                    'next_step': 'manual_review'
                }
            }

    def process_intelligent_follow_ups(self, campaign_ids: Optional[List[int]] = None) -> Dict:
        """Process intelligent follow-ups for active campaigns"""
        try:
            # Get active campaigns
            query = Campaign.query.filter_by(status='active')
            if campaign_ids:
                query = query.filter(Campaign.id.in_(campaign_ids))

            campaigns = query.all()

            results = {
                'processed_campaigns': 0,
                'contacts_analyzed': 0,
                'sequences_adjusted': 0,
                'sequences_paused': 0,
                'sequences_accelerated': 0,
                'recommendations': []
            }

            for campaign in campaigns:
                campaign_results = self._process_campaign_follow_ups(campaign)

                results['processed_campaigns'] += 1
                results['contacts_analyzed'] += campaign_results['contacts_analyzed']
                results['sequences_adjusted'] += campaign_results['sequences_adjusted']
                results['sequences_paused'] += campaign_results['sequences_paused']
                results['sequences_accelerated'] += campaign_results['sequences_accelerated']
                results['recommendations'].extend(campaign_results['recommendations'])

            return results

        except Exception as e:
            print(f"Error processing intelligent follow-ups: {e}")
            return {
                'processed_campaigns': 0,
                'contacts_analyzed': 0,
                'sequences_adjusted': 0,
                'sequences_paused': 0,
                'sequences_accelerated': 0,
                'recommendations': [],
                'error': str(e)
            }

    def _process_campaign_follow_ups(self, campaign: Campaign) -> Dict:
        """Process follow-ups for a specific campaign"""
        try:
            # Get all active sequences for this campaign
            active_sequences = EmailSequence.query.filter(
                and_(
                    EmailSequence.campaign_id == campaign.id,
                    EmailSequence.status == 'scheduled'
                )
            ).all()

            results = {
                'contacts_analyzed': 0,
                'sequences_adjusted': 0,
                'sequences_paused': 0,
                'sequences_accelerated': 0,
                'recommendations': []
            }

            for sequence in active_sequences:
                try:
                    # Analyze this contact's engagement
                    recommendation = self.recommend_follow_up_action(
                        sequence.contact_id, campaign.id
                    )

                    results['contacts_analyzed'] += 1
                    results['recommendations'].append(recommendation)

                    # Apply automatic adjustments based on recommendation
                    if self._should_auto_apply(recommendation):
                        adjustment_result = self._apply_sequence_adjustment(sequence, recommendation)

                        if adjustment_result['action'] == 'pause':
                            results['sequences_paused'] += 1
                        elif adjustment_result['action'] == 'accelerate':
                            results['sequences_accelerated'] += 1

                        results['sequences_adjusted'] += 1

                except Exception as e:
                    print(f"Error processing sequence {sequence.id}: {e}")
                    continue

            return results

        except Exception as e:
            print(f"Error processing campaign follow-ups: {e}")
            return {
                'contacts_analyzed': 0,
                'sequences_adjusted': 0,
                'sequences_paused': 0,
                'sequences_accelerated': 0,
                'recommendations': []
            }

    def _determine_engagement_level(self, open_rate: float, click_rate: float) -> str:
        """Determine engagement level based on rates"""
        high = self.engagement_thresholds['high_engagement']
        medium = self.engagement_thresholds['medium_engagement']

        if open_rate >= high['open_rate_min'] and click_rate >= high['click_rate_min']:
            return 'high'
        elif open_rate >= medium['open_rate_min'] and click_rate >= medium['click_rate_min']:
            return 'medium'
        else:
            return 'low'

    def _analyze_engagement_timing(self, emails: List[Email]) -> Dict:
        """Analyze timing patterns in email engagement"""
        try:
            if not emails:
                return {'pattern': 'unknown', 'best_time': None}

            # Group by hour of day
            hour_engagement = {}

            for email in emails:
                if email.opened_at:
                    hour = email.opened_at.hour
                    hour_engagement[hour] = hour_engagement.get(hour, 0) + 1

            if not hour_engagement:
                return {'pattern': 'no_opens', 'best_time': None}

            # Find best engagement hour
            best_hour = max(hour_engagement.items(), key=lambda x: x[1])[0]

            # Determine pattern
            morning_opens = sum(count for hour, count in hour_engagement.items() if 6 <= hour <= 12)
            afternoon_opens = sum(count for hour, count in hour_engagement.items() if 12 <= hour <= 18)
            evening_opens = sum(count for hour, count in hour_engagement.items() if 18 <= hour <= 24)

            total_opens = sum(hour_engagement.values())

            if morning_opens / total_opens > 0.5:
                pattern = 'morning_person'
            elif afternoon_opens / total_opens > 0.5:
                pattern = 'afternoon_person'
            elif evening_opens / total_opens > 0.5:
                pattern = 'evening_person'
            else:
                pattern = 'mixed'

            return {
                'pattern': pattern,
                'best_time': best_hour,
                'hour_distribution': hour_engagement
            }

        except Exception as e:
            print(f"Error analyzing timing: {e}")
            return {'pattern': 'unknown', 'best_time': None}

    def _get_last_activity_date(self, emails: List[Email]) -> Optional[datetime]:
        """Get the date of last email activity"""
        try:
            activity_dates = []

            for email in emails:
                if email.opened_at:
                    activity_dates.append(email.opened_at)
                if email.clicked_at:
                    activity_dates.append(email.clicked_at)
                if email.replied_at:
                    activity_dates.append(email.replied_at)

            return max(activity_dates) if activity_dates else None

        except Exception as e:
            return None

    def _recommend_strategy(self, engagement_level: str, days_since_activity: Optional[int]) -> str:
        """Recommend follow-up strategy based on engagement"""
        if engagement_level == 'high':
            return 'aggressive'
        elif engagement_level == 'medium':
            if days_since_activity and days_since_activity < 7:
                return 'aggressive'
            else:
                return 'moderate'
        else:
            if days_since_activity and days_since_activity > 14:
                return 'conservative'
            else:
                return 'moderate'

    def _get_sequence_status(self, contact_id: int, campaign_id: int) -> Dict:
        """Get current sequence status for contact in campaign"""
        try:
            sequences = EmailSequence.query.filter(
                and_(
                    EmailSequence.contact_id == contact_id,
                    EmailSequence.campaign_id == campaign_id
                )
            ).order_by(EmailSequence.sequence_step).all()

            if not sequences:
                return {'status': 'no_sequence', 'current_step': 0, 'total_steps': 0}

            total_steps = len(sequences)
            current_step = 0
            last_sent = None

            for seq in sequences:
                if seq.status == 'sent':
                    current_step = seq.sequence_step
                    last_sent = seq.sent_at

            return {
                'status': 'active' if current_step < total_steps else 'completed',
                'current_step': current_step,
                'total_steps': total_steps,
                'last_sent': last_sent.isoformat() if last_sent else None,
                'sequences': [{'step': s.sequence_step, 'status': s.status} for s in sequences]
            }

        except Exception as e:
            print(f"Error getting sequence status: {e}")
            return {'status': 'error', 'current_step': 0, 'total_steps': 0}

    def _generate_recommendation(self, engagement: Dict, sequence_status: Dict, last_email: Optional[Email]) -> Dict:
        """Generate specific follow-up recommendation"""
        try:
            engagement_level = engagement['engagement_level']
            engagement_score = engagement['engagement_score']
            is_responsive = engagement['is_responsive']
            days_since_activity = engagement['days_since_activity']

            # Base recommendation logic
            if engagement_level == 'high' and is_responsive:
                action = 'accelerate'
                reason = 'High engagement detected - accelerate sequence'
                next_step = 'reduce_wait_time'
            elif engagement_level == 'low' and days_since_activity and days_since_activity > 14:
                action = 'pause'
                reason = 'Low engagement and no recent activity - pause sequence'
                next_step = 'review_manually'
            elif engagement_score == 0 and last_email and last_email.bounced_at:
                action = 'stop'
                reason = 'Email bounced - stop sequence'
                next_step = 'mark_invalid'
            elif last_email and last_email.replied_at:
                action = 'stop'
                reason = 'Contact replied - sequence completed successfully'
                next_step = 'move_to_nurture'
            else:
                action = 'continue'
                reason = 'Normal engagement pattern - continue sequence'
                next_step = 'send_next_email'

            # Calculate optimal timing
            optimal_timing = self._calculate_optimal_timing(engagement, sequence_status)

            return {
                'action': action,
                'reason': reason,
                'next_step': next_step,
                'optimal_timing': optimal_timing,
                'priority': self._calculate_priority(engagement, sequence_status)
            }

        except Exception as e:
            print(f"Error generating recommendation: {e}")
            return {
                'action': 'continue',
                'reason': 'Error in analysis - default to continue',
                'next_step': 'manual_review'
            }

    def _calculate_optimal_timing(self, engagement: Dict, sequence_status: Dict) -> Dict:
        """Calculate optimal timing for next follow-up"""
        try:
            timing_analysis = engagement.get('timing_analysis', {})
            best_hour = timing_analysis.get('best_time')
            engagement_level = engagement['engagement_level']

            # Base wait time from strategy
            strategy = self._recommend_strategy(engagement_level, engagement.get('days_since_activity'))
            base_wait_hours = self.follow_up_strategies[strategy]['wait_hours']

            # Adjust based on engagement
            if engagement_level == 'high':
                wait_hours = max(12, base_wait_hours * 0.5)  # Faster for high engagement
            elif engagement_level == 'low':
                wait_hours = base_wait_hours * 1.5  # Slower for low engagement
            else:
                wait_hours = base_wait_hours

            return {
                'wait_hours': wait_hours,
                'preferred_hour': best_hour,
                'strategy': strategy,
                'next_send_time': (datetime.utcnow() + timedelta(hours=wait_hours)).isoformat()
            }

        except Exception as e:
            return {'wait_hours': 48, 'preferred_hour': None, 'strategy': 'moderate'}

    def _calculate_confidence_score(self, engagement: Dict, sequence_status: Dict) -> float:
        """Calculate confidence score for the recommendation"""
        try:
            # Base confidence on data quality
            emails_sent = engagement.get('metrics', {}).get('emails_sent', 0)

            if emails_sent >= 5:
                base_confidence = 0.9
            elif emails_sent >= 3:
                base_confidence = 0.7
            elif emails_sent >= 1:
                base_confidence = 0.5
            else:
                base_confidence = 0.3

            # Adjust for engagement clarity
            engagement_score = engagement.get('engagement_score', 0)

            if engagement_score > 50 or engagement_score < 10:
                clarity_bonus = 0.1  # Clear high or low engagement
            else:
                clarity_bonus = 0  # Ambiguous engagement

            return min(1.0, base_confidence + clarity_bonus)

        except Exception as e:
            return 0.5

    def _calculate_priority(self, engagement: Dict, sequence_status: Dict) -> str:
        """Calculate priority level for the recommendation"""
        try:
            engagement_score = engagement.get('engagement_score', 0)
            is_responsive = engagement.get('is_responsive', False)

            if engagement_score > 60 or is_responsive:
                return 'high'
            elif engagement_score > 20:
                return 'medium'
            else:
                return 'low'

        except Exception as e:
            return 'medium'

    def _should_auto_apply(self, recommendation: Dict) -> bool:
        """Determine if recommendation should be automatically applied"""
        confidence = recommendation.get('confidence_score', 0)
        action = recommendation.get('recommendation', {}).get('action')

        # Only auto-apply high-confidence, non-destructive actions
        return (
            confidence >= 0.8 and
            action in ['accelerate', 'continue'] and
            recommendation.get('recommendation', {}).get('priority') == 'high'
        )

    def _apply_sequence_adjustment(self, sequence: EmailSequence, recommendation: Dict) -> Dict:
        """Apply automatic sequence adjustment"""
        try:
            action = recommendation.get('recommendation', {}).get('action')
            optimal_timing = recommendation.get('recommendation', {}).get('optimal_timing', {})

            if action == 'accelerate' and optimal_timing.get('wait_hours'):
                # Reduce the scheduled time
                new_time = datetime.utcnow() + timedelta(hours=optimal_timing['wait_hours'])
                sequence.scheduled_datetime = new_time
                db.session.commit()

                return {'action': 'accelerate', 'success': True, 'new_time': new_time}

            elif action == 'pause':
                # Mark sequence as paused (you might want a dedicated status)
                sequence.status = 'paused'
                db.session.commit()

                return {'action': 'pause', 'success': True}

            return {'action': 'none', 'success': False, 'reason': 'No applicable adjustment'}

        except Exception as e:
            print(f"Error applying sequence adjustment: {e}")
            return {'action': 'none', 'success': False, 'error': str(e)}

    def _get_default_engagement(self) -> Dict:
        """Return default engagement data"""
        return {
            'contact_id': None,
            'engagement_level': 'unknown',
            'engagement_score': 0,
            'metrics': {
                'emails_sent': 0,
                'open_rate': 0,
                'click_rate': 0,
                'reply_rate': 0,
                'bounce_rate': 0
            },
            'timing_analysis': {'pattern': 'unknown', 'best_time': None},
            'days_since_activity': None,
            'is_responsive': False,
            'recommended_strategy': 'moderate'
        }


def create_intelligent_follow_up_service() -> IntelligentFollowUpService:
    """Factory function to create intelligent follow-up service"""
    return IntelligentFollowUpService()