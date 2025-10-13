"""
Analytics routes for SalesBreachPro
Handles email analytics, response tracking, and performance metrics
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template
from utils.decorators import login_required
from models.database import db, Email, Contact, Campaign, Response

# Create analytics blueprint
analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@analytics_bp.route('/emails-week')
@login_required
def emails_week():
    """Analytics page for emails sent this week"""
    try:
        # Get emails from the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Query emails with joins for contact and campaign info
        emails = db.session.query(Email, Contact, Campaign).join(
            Contact, Email.contact_id == Contact.id
        ).outerjoin(
            Campaign, Email.campaign_id == Campaign.id
        ).filter(Email.sent_at >= week_ago).order_by(Email.sent_at.desc()).all()
        
        # Calculate daily stats for the week
        daily_stats = {}
        for i in range(7):
            day = datetime.utcnow() - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_count = Email.query.filter(
                Email.sent_at >= day_start,
                Email.sent_at < day_end
            ).count()
            
            daily_stats[day_start.strftime('%A')] = day_count
        
        # Calculate overall stats using webhook-based timestamps
        total_sent = len(emails)
        delivered = sum(1 for e, c, camp in emails if e.delivered_at is not None)
        opened = sum(1 for e, c, camp in emails if e.opened_at is not None)
        clicked = sum(1 for e, c, camp in emails if e.clicked_at is not None)
        replied = sum(1 for e, c, camp in emails if e.replied_at is not None)
        
        stats = {
            'total_sent': total_sent,
            'delivered': delivered,
            'opened': opened,
            'clicked': clicked,
            'replied': replied,
            'delivery_rate': round((delivered / total_sent * 100), 2) if total_sent > 0 else 0,
            'open_rate': round((opened / delivered * 100), 2) if delivered > 0 else 0,
            'click_rate': round((clicked / opened * 100), 2) if opened > 0 else 0,
            'reply_rate': round((replied / delivered * 100), 2) if delivered > 0 else 0
        }
        
        return render_template('analytics_emails_week.html',
                             emails=emails,
                             stats=stats,
                             daily_stats=daily_stats,
                             week_ago=week_ago)
        
    except Exception as e:
        print(f"Email analytics error: {str(e)}")
        return render_template('analytics_emails_week.html',
                             emails=[],
                             stats={'total_sent': 0, 'delivered': 0, 'opened': 0, 'clicked': 0, 'replied': 0},
                             daily_stats={},
                             week_ago=datetime.utcnow() - timedelta(days=7))


@analytics_bp.route('/responses')
@login_required
def responses():
    """Analytics page for email responses"""
    try:
        # Get responses from the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Query responses with related data
        responses = db.session.query(Response, Email, Contact, Campaign).join(
            Email, Response.email_id == Email.id
        ).join(
            Contact, Response.contact_id == Contact.id
        ).outerjoin(
            Campaign, Email.campaign_id == Campaign.id
        ).filter(Response.created_at >= week_ago).order_by(Response.created_at.desc()).all()
        
        # Group responses by type
        response_types = {
            'positive': [],
            'negative': [],
            'neutral': [],
            'inquiry': []
        }
        
        for resp, email, contact, campaign in responses:
            response_types.get(resp.response_type, []).append({
                'response': resp,
                'email': email,
                'contact': contact,
                'campaign': campaign
            })
        
        # Calculate response stats
        total_responses = len(responses)
        positive_count = len(response_types['positive'])
        negative_count = len(response_types['negative'])
        neutral_count = len(response_types['neutral'])
        inquiry_count = len(response_types['inquiry'])
        
        # Calculate response rate
        total_emails_week = Email.query.filter(Email.sent_at >= week_ago).count()
        response_rate = round((total_responses / total_emails_week * 100), 2) if total_emails_week > 0 else 0
        
        stats = {
            'total_responses': total_responses,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'inquiry_count': inquiry_count,
            'response_rate': response_rate,
            'positive_rate': round((positive_count / total_responses * 100), 2) if total_responses > 0 else 0
        }
        
        return render_template('analytics_responses.html',
                             responses=responses,
                             response_types=response_types,
                             stats=stats,
                             week_ago=week_ago)
        
    except Exception as e:
        print(f"Response analytics error: {str(e)}")
        return render_template('analytics_responses.html',
                             responses=[],
                             response_types={'positive': [], 'negative': [], 'neutral': [], 'inquiry': []},
                             stats={'total_responses': 0, 'positive_count': 0, 'response_rate': 0},
                             week_ago=datetime.utcnow() - timedelta(days=7))