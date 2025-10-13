"""
Enhanced Analytics Routes for Detailed Email Workflow Tracking
Shows complete email sequence engagement with per-email breakdown
"""
from flask import Blueprint, render_template, request, jsonify
from utils.decorators import login_required
from models.database import (
    db, Contact, Campaign, Email, EmailSequence, EmailTemplate,
    ContactCampaignStatus, WebhookEvent
)
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_, distinct

# Create enhanced analytics blueprint
enhanced_analytics_bp = Blueprint('enhanced_analytics', __name__)


@enhanced_analytics_bp.route('/sequence-analytics')
@login_required
def sequence_analytics():
    """Enhanced dashboard showing complete email sequence tracking"""
    try:
        # Get overall workflow statistics
        stats = get_enhanced_workflow_stats()

        # Get active campaigns with detailed metrics
        campaigns = get_campaigns_with_sequence_metrics()

        # Get recent email engagement timeline
        engagement_timeline = get_recent_engagement_timeline()

        # Get sequence performance breakdown
        sequence_performance = get_sequence_step_performance()

        return render_template('sequence_analytics_modern.html',
                             stats=stats,
                             campaigns=campaigns,
                             engagement_timeline=engagement_timeline,
                             sequence_performance=sequence_performance)

    except Exception as e:
        print(f"Enhanced analytics error: {e}")
        return render_template('sequence_analytics_modern.html',
                             stats={},
                             campaigns=[],
                             engagement_timeline=[],
                             sequence_performance=[])


def get_enhanced_workflow_stats():
    """Get comprehensive workflow statistics"""
    try:
        # Date ranges
        today = datetime.utcnow()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Basic counts
        total_contacts = Contact.query.count()
        active_campaigns = Campaign.query.filter_by(status='active').count()

        # Email sequence statistics
        total_sequences = EmailSequence.query.count()
        sent_emails = Email.query.filter(Email.sent_at.isnot(None)).count()
        opened_emails = Email.query.filter(Email.opened_at.isnot(None)).count()
        clicked_emails = Email.query.filter(Email.clicked_at.isnot(None)).count()
        replied_emails = Email.query.filter(Email.replied_at.isnot(None)).count()

        # Recent activity (last 7 days)
        recent_sent = Email.query.filter(Email.sent_at >= week_ago).count()
        recent_opened = Email.query.filter(Email.opened_at >= week_ago).count()
        recent_clicked = Email.query.filter(Email.clicked_at >= week_ago).count()
        recent_replied = Email.query.filter(Email.replied_at >= week_ago).count()

        # Engagement rates
        open_rate = (opened_emails / sent_emails * 100) if sent_emails > 0 else 0
        click_rate = (clicked_emails / sent_emails * 100) if sent_emails > 0 else 0
        reply_rate = (replied_emails / sent_emails * 100) if sent_emails > 0 else 0

        # Sequence step breakdown
        step_breakdown = db.session.query(
            EmailSequence.sequence_step,
            func.count(EmailSequence.id).label('count')
        ).group_by(EmailSequence.sequence_step).all()

        sequence_step_counts = {step: count for step, count in step_breakdown}

        # Risk level breakdown
        risk_breakdown = db.session.query(
            Contact.breach_status,
            func.count(Contact.id).label('count')
        ).group_by(Contact.breach_status).all()

        risk_counts = {risk or 'unknown': count for risk, count in risk_breakdown}

        return {
            'overview': {
                'total_contacts': total_contacts,
                'active_campaigns': active_campaigns,
                'total_sequences': total_sequences,
                'sent_emails': sent_emails
            },
            'engagement': {
                'opened_emails': opened_emails,
                'clicked_emails': clicked_emails,
                'replied_emails': replied_emails,
                'open_rate': round(open_rate, 1),
                'click_rate': round(click_rate, 1),
                'reply_rate': round(reply_rate, 1)
            },
            'recent_activity': {
                'sent_week': recent_sent,
                'opened_week': recent_opened,
                'clicked_week': recent_clicked,
                'replied_week': recent_replied
            },
            'sequence_breakdown': sequence_step_counts,
            'risk_breakdown': risk_counts,
            'updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    except Exception as e:
        print(f"Error getting enhanced stats: {e}")
        return {}


def get_campaigns_with_sequence_metrics():
    """Get campaigns with detailed sequence metrics"""
    try:
        campaigns = Campaign.query.filter_by(status='active').all()
        campaign_data = []

        for campaign in campaigns:
            # Get all emails for this campaign
            emails = Email.query.filter_by(campaign_id=campaign.id).all()

            # Group emails by sequence step (email_type or sequence relationship)
            sequence_metrics = {}

            for email in emails:
                # Determine sequence step from EmailSequence or email_type
                sequence_step = 0  # Default to initial email

                # Try to get sequence step from EmailSequence table
                email_seq = EmailSequence.query.filter_by(
                    campaign_id=campaign.id,
                    contact_id=email.contact_id,
                    email_id=email.id
                ).first()

                if email_seq:
                    sequence_step = email_seq.sequence_step
                elif email.email_type:
                    # Parse email_type like 'initial', 'follow_up_1', 'follow_up_2'
                    if 'follow_up_' in email.email_type:
                        try:
                            sequence_step = int(email.email_type.split('_')[-1])
                        except:
                            sequence_step = 1
                    elif email.email_type == 'initial':
                        sequence_step = 0

                # Get step name
                step_name = get_sequence_step_name(sequence_step)

                if step_name not in sequence_metrics:
                    sequence_metrics[step_name] = {
                        'step': sequence_step,
                        'name': step_name,
                        'sent': 0,
                        'delivered': 0,
                        'opened': 0,
                        'clicked': 0,
                        'replied': 0,
                        'bounced': 0,
                        'emails': []
                    }

                metrics = sequence_metrics[step_name]
                metrics['sent'] += 1

                if email.delivered_at:
                    metrics['delivered'] += 1
                if email.opened_at:
                    metrics['opened'] += 1
                if email.clicked_at:
                    metrics['clicked'] += 1
                if email.replied_at:
                    metrics['replied'] += 1
                if email.bounced_at:
                    metrics['bounced'] += 1

                # Add email details
                metrics['emails'].append({
                    'id': email.id,
                    'contact_id': email.contact_id,
                    'subject': email.subject,
                    'sent_at': email.sent_at.isoformat() if email.sent_at else None,
                    'status': email.status,
                    'delivered': bool(email.delivered_at),
                    'opened': bool(email.opened_at),
                    'clicked': bool(email.clicked_at),
                    'replied': bool(email.replied_at)
                })

            # Calculate rates for each sequence step
            for step_name, metrics in sequence_metrics.items():
                if metrics['sent'] > 0:
                    metrics['delivery_rate'] = round((metrics['delivered'] / metrics['sent']) * 100, 1)
                    metrics['open_rate'] = round((metrics['opened'] / metrics['sent']) * 100, 1)
                    metrics['click_rate'] = round((metrics['clicked'] / metrics['sent']) * 100, 1)
                    metrics['reply_rate'] = round((metrics['replied'] / metrics['sent']) * 100, 1)
                else:
                    metrics['delivery_rate'] = 0
                    metrics['open_rate'] = 0
                    metrics['click_rate'] = 0
                    metrics['reply_rate'] = 0

            # Sort sequence steps
            sorted_sequence = sorted(sequence_metrics.values(), key=lambda x: x['step'])

            campaign_data.append({
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status,
                'total_contacts': len(set(email.contact_id for email in emails)),
                'total_emails': len(emails),
                'sequence_metrics': sorted_sequence,
                'created_at': campaign.created_at.isoformat() if campaign.created_at else None
            })

        return campaign_data

    except Exception as e:
        print(f"Error getting campaign metrics: {e}")
        return []


def get_sequence_step_name(step):
    """Convert sequence step number to readable name"""
    step_names = {
        0: "Initial Email",
        1: "Follow-up 1",
        2: "Follow-up 2",
        3: "Follow-up 3",
        4: "Follow-up 4",
        5: "Follow-up 5"
    }
    return step_names.get(step, f"Follow-up {step}")


def get_recent_engagement_timeline():
    """Get recent email engagement events for timeline view"""
    try:
        # Get recent emails with engagement events
        week_ago = datetime.utcnow() - timedelta(days=7)

        # Get emails with any engagement in the last week
        recent_emails = Email.query.filter(
            or_(
                Email.sent_at >= week_ago,
                Email.opened_at >= week_ago,
                Email.clicked_at >= week_ago,
                Email.replied_at >= week_ago
            )
        ).order_by(Email.sent_at.desc()).limit(50).all()

        timeline_events = []

        for email in recent_emails:
            contact = Contact.query.get(email.contact_id)
            contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email

            # Get sequence info
            sequence_step = get_email_sequence_step(email)
            step_name = get_sequence_step_name(sequence_step)

            # Add engagement events
            if email.sent_at and email.sent_at >= week_ago:
                timeline_events.append({
                    'type': 'sent',
                    'timestamp': email.sent_at,
                    'contact_name': contact_name,
                    'contact_email': contact.email,
                    'email_id': email.id,
                    'subject': email.subject,
                    'sequence_step': step_name,
                    'description': f"Sent {step_name.lower()} to {contact_name}"
                })

            if email.opened_at and email.opened_at >= week_ago:
                timeline_events.append({
                    'type': 'opened',
                    'timestamp': email.opened_at,
                    'contact_name': contact_name,
                    'contact_email': contact.email,
                    'email_id': email.id,
                    'subject': email.subject,
                    'sequence_step': step_name,
                    'description': f"{contact_name} opened {step_name.lower()}"
                })

            if email.clicked_at and email.clicked_at >= week_ago:
                timeline_events.append({
                    'type': 'clicked',
                    'timestamp': email.clicked_at,
                    'contact_name': contact_name,
                    'contact_email': contact.email,
                    'email_id': email.id,
                    'subject': email.subject,
                    'sequence_step': step_name,
                    'description': f"{contact_name} clicked link in {step_name.lower()}"
                })

            if email.replied_at and email.replied_at >= week_ago:
                timeline_events.append({
                    'type': 'replied',
                    'timestamp': email.replied_at,
                    'contact_name': contact_name,
                    'contact_email': contact.email,
                    'email_id': email.id,
                    'subject': email.subject,
                    'sequence_step': step_name,
                    'description': f"{contact_name} replied to {step_name.lower()}"
                })

        # Sort by timestamp (most recent first)
        timeline_events.sort(key=lambda x: x['timestamp'], reverse=True)

        return timeline_events[:30]  # Limit to 30 most recent events

    except Exception as e:
        print(f"Error getting engagement timeline: {e}")
        return []


def get_email_sequence_step(email):
    """Get the sequence step for an email"""
    try:
        # Try to get from EmailSequence first
        email_seq = EmailSequence.query.filter_by(email_id=email.id).first()
        if email_seq:
            return email_seq.sequence_step

        # Fallback to email_type parsing
        if email.email_type:
            if 'follow_up_' in email.email_type:
                try:
                    return int(email.email_type.split('_')[-1])
                except:
                    return 1
            elif email.email_type == 'initial':
                return 0

        return 0  # Default to initial email

    except Exception as e:
        print(f"Error getting sequence step: {e}")
        return 0


def get_sequence_step_performance():
    """Get performance metrics for each sequence step"""
    try:
        # Get all emails grouped by sequence step
        step_performance = {}

        emails = Email.query.filter(Email.sent_at.isnot(None)).all()

        for email in emails:
            step = get_email_sequence_step(email)
            step_name = get_sequence_step_name(step)

            if step_name not in step_performance:
                step_performance[step_name] = {
                    'step': step,
                    'name': step_name,
                    'sent': 0,
                    'delivered': 0,
                    'opened': 0,
                    'clicked': 0,
                    'replied': 0,
                    'bounced': 0
                }

            metrics = step_performance[step_name]
            metrics['sent'] += 1

            if email.delivered_at:
                metrics['delivered'] += 1
            if email.opened_at:
                metrics['opened'] += 1
            if email.clicked_at:
                metrics['clicked'] += 1
            if email.replied_at:
                metrics['replied'] += 1
            if email.bounced_at:
                metrics['bounced'] += 1

        # Calculate rates
        for step_name, metrics in step_performance.items():
            if metrics['sent'] > 0:
                metrics['delivery_rate'] = round((metrics['delivered'] / metrics['sent']) * 100, 1)
                metrics['open_rate'] = round((metrics['opened'] / metrics['sent']) * 100, 1)
                metrics['click_rate'] = round((metrics['clicked'] / metrics['sent']) * 100, 1)
                metrics['reply_rate'] = round((metrics['replied'] / metrics['sent']) * 100, 1)
                metrics['bounce_rate'] = round((metrics['bounced'] / metrics['sent']) * 100, 1)
            else:
                metrics['delivery_rate'] = 0
                metrics['open_rate'] = 0
                metrics['click_rate'] = 0
                metrics['reply_rate'] = 0
                metrics['bounce_rate'] = 0

        # Sort by sequence step
        sorted_performance = sorted(step_performance.values(), key=lambda x: x['step'])

        return sorted_performance

    except Exception as e:
        print(f"Error getting sequence performance: {e}")
        return []


@enhanced_analytics_bp.route('/api/sequence-timeline/<int:campaign_id>')
@login_required
def api_sequence_timeline(campaign_id):
    """Get detailed timeline for a specific campaign"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)

        # Get all emails for this campaign
        emails = Email.query.filter_by(campaign_id=campaign_id).order_by(Email.sent_at.desc()).all()

        timeline_data = []

        for email in emails:
            contact = Contact.query.get(email.contact_id)
            sequence_step = get_email_sequence_step(email)
            step_name = get_sequence_step_name(sequence_step)

            email_data = {
                'email_id': email.id,
                'contact_id': email.contact_id,
                'contact_name': f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email,
                'contact_email': contact.email,
                'sequence_step': sequence_step,
                'step_name': step_name,
                'subject': email.subject,
                'status': email.status,
                'events': []
            }

            # Add all engagement events
            if email.sent_at:
                email_data['events'].append({
                    'type': 'sent',
                    'timestamp': email.sent_at.isoformat(),
                    'description': f"Email sent"
                })

            if email.delivered_at:
                email_data['events'].append({
                    'type': 'delivered',
                    'timestamp': email.delivered_at.isoformat(),
                    'description': f"Email delivered"
                })

            if email.opened_at:
                email_data['events'].append({
                    'type': 'opened',
                    'timestamp': email.opened_at.isoformat(),
                    'description': f"Email opened"
                })

            if email.clicked_at:
                email_data['events'].append({
                    'type': 'clicked',
                    'timestamp': email.clicked_at.isoformat(),
                    'description': f"Link clicked"
                })

            if email.replied_at:
                email_data['events'].append({
                    'type': 'replied',
                    'timestamp': email.replied_at.isoformat(),
                    'description': f"Email replied"
                })

            if email.bounced_at:
                email_data['events'].append({
                    'type': 'bounced',
                    'timestamp': email.bounced_at.isoformat(),
                    'description': f"Email bounced"
                })

            # Sort events by timestamp
            email_data['events'].sort(key=lambda x: x['timestamp'])

            timeline_data.append(email_data)

        return jsonify({
            'success': True,
            'campaign': {
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status
            },
            'timeline': timeline_data
        })

    except Exception as e:
        print(f"Error getting sequence timeline: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_analytics_bp.route('/api/contact-sequence-details/<int:contact_id>')
@login_required
def api_contact_sequence_details(contact_id):
    """Get detailed sequence information for a specific contact"""
    try:
        contact = Contact.query.get_or_404(contact_id)

        # Get all emails for this contact
        emails = Email.query.filter_by(contact_id=contact_id).order_by(Email.sent_at.asc()).all()

        sequence_data = []

        for email in emails:
            sequence_step = get_email_sequence_step(email)
            step_name = get_sequence_step_name(sequence_step)

            campaign = Campaign.query.get(email.campaign_id)

            sequence_data.append({
                'email_id': email.id,
                'campaign_id': email.campaign_id,
                'campaign_name': campaign.name if campaign else 'Unknown',
                'sequence_step': sequence_step,
                'step_name': step_name,
                'subject': email.subject,
                'status': email.status,
                'sent_at': email.sent_at.isoformat() if email.sent_at else None,
                'delivered_at': email.delivered_at.isoformat() if email.delivered_at else None,
                'opened_at': email.opened_at.isoformat() if email.opened_at else None,
                'clicked_at': email.clicked_at.isoformat() if email.clicked_at else None,
                'replied_at': email.replied_at.isoformat() if email.replied_at else None,
                'engagement_score': calculate_email_engagement_score(email)
            })

        return jsonify({
            'success': True,
            'contact': {
                'id': contact.id,
                'name': f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email,
                'email': contact.email,
                'company': contact.company,
                'breach_status': contact.breach_status
            },
            'sequences': sequence_data
        })

    except Exception as e:
        print(f"Error getting contact sequence details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def calculate_email_engagement_score(email):
    """Calculate engagement score for an email (0-100)"""
    score = 0

    if email.delivered_at:
        score += 20  # Delivered

    if email.opened_at:
        score += 30  # Opened

    if email.clicked_at:
        score += 40  # Clicked

    if email.replied_at:
        score += 10  # Replied (bonus on top of other engagement)

    return min(score, 100)  # Cap at 100


@enhanced_analytics_bp.route('/api/realtime-stats')
@login_required
def api_realtime_stats():
    """Get real-time statistics for dashboard updates"""
    try:
        stats = get_enhanced_workflow_stats()
        return jsonify(stats)

    except Exception as e:
        print(f"Error getting real-time stats: {e}")
        return jsonify({'error': str(e)}), 500