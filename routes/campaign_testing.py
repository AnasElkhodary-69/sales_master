"""
Campaign Testing Routes
Allows testing campaigns before sending to real contacts
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from utils.decorators import login_required
from models.database import db, Contact, EmailTemplate, Campaign
from services.flawtrack_api import FlawTrackAPI
import os
import re

# Create testing blueprint
testing_bp = Blueprint('testing', __name__, url_prefix='/testing')

def get_flawtrack_api():
    """Initialize FlawTrack API client"""
    api_token = os.getenv('FLAWTRACK_API_TOKEN')
    api_endpoint = os.getenv('FLAWTRACK_API_ENDPOINT')

    if api_token and api_endpoint:
        return FlawTrackAPI(api_token, api_endpoint)
    return None

def extract_domain_from_email(email):
    """Extract domain from email address"""
    if '@' in email:
        return email.split('@')[1]
    return email

def format_breach_data_for_template(breach_data):
    """Format breach data for email templates"""
    if not breach_data:
        return {
            'breach_count': 0,
            'breach_sources_list': '<li>No breaches found</li>',
            'total_breached_accounts': 0,
            'breach_sources': []
        }

    # Extract unique sources
    sources = set()
    total_accounts = len(breach_data)

    for record in breach_data:
        service = record.get('service_name', 'Unknown Service')
        sources.add(service)

    # Format as HTML list
    sources_html = '\n'.join([f'<li>{source}</li>' for source in sorted(sources)])

    return {
        'breach_count': len(sources),
        'breach_sources_list': sources_html,
        'total_breached_accounts': total_accounts,
        'breach_sources': list(sources)
    }

@testing_bp.route('/')
@login_required
def index():
    """Campaign testing dashboard"""
    templates = EmailTemplate.query.all()
    campaigns = Campaign.query.all()

    return render_template('testing/dashboard.html',
                         templates=templates,
                         campaigns=campaigns)

@testing_bp.route('/template/<int:template_id>')
@login_required
def test_template(template_id):
    """Test a specific email template"""
    template = EmailTemplate.query.get_or_404(template_id)

    return render_template('testing/template_test.html', template=template)

@testing_bp.route('/preview', methods=['POST'])
@login_required
def preview_email():
    """Preview email with real or test data"""
    try:
        template_id = request.json.get('template_id')
        test_email = request.json.get('test_email', '')
        use_real_data = request.json.get('use_real_data', False)

        template = EmailTemplate.query.get_or_404(template_id)

        # Test data defaults
        test_data = {
            'first_name': 'John',
            'last_name': 'Smith',
            'company': 'Test Company Inc',
            'email': test_email or 'test@example.com',
            'sender_name': 'Emily Carter',
            'breach_count': 0,
            'breach_sources_list': '<li>No breaches found</li>',
            'total_breached_accounts': 0
        }

        # If using real data and template is breach-related
        if use_real_data and test_email and ('breach' in template.name.lower()):
            domain = extract_domain_from_email(test_email)

            # Get real breach data
            flawtrack = get_flawtrack_api()
            if flawtrack:
                breach_data = flawtrack.get_breach_data(domain)
                breach_info = format_breach_data_for_template(breach_data)
                test_data.update(breach_info)

                # Extract company name from domain
                company_name = domain.replace('.com', '').replace('.ca', '').replace('.org', '').title()
                test_data['company'] = company_name

        # Replace template variables
        subject = template.subject_line
        body = template.email_body_html or template.email_body

        for key, value in test_data.items():
            subject = subject.replace(f'{{{key}}}', str(value))
            body = body.replace(f'{{{key}}}', str(value))

        return jsonify({
            'success': True,
            'subject': subject,
            'body': body,
            'data_used': test_data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@testing_bp.route('/campaign/<int:campaign_id>')
@login_required
def test_campaign(campaign_id):
    """Test an entire campaign sequence"""
    campaign = Campaign.query.get_or_404(campaign_id)

    # Get campaign templates/sequences
    templates = EmailTemplate.query.filter_by(template_type='initial').all()

    return render_template('testing/campaign_test.html',
                         campaign=campaign,
                         templates=templates)

@testing_bp.route('/breach-scan')
@login_required
def breach_scan_test():
    """Test breach scanning functionality"""
    return render_template('testing/breach_scan.html')

@testing_bp.route('/api/breach-scan', methods=['POST'])
@login_required
def api_breach_scan():
    """API endpoint for testing breach scans"""
    try:
        email = request.json.get('email', '')
        if not email:
            return jsonify({'success': False, 'error': 'Email required'}), 400

        domain = extract_domain_from_email(email)

        flawtrack = get_flawtrack_api()
        if not flawtrack:
            return jsonify({
                'success': False,
                'error': 'FlawTrack API not configured'
            }), 500

        # Perform breach scan
        breach_data = flawtrack.get_breach_data(domain)
        breach_info = format_breach_data_for_template(breach_data)

        return jsonify({
            'success': True,
            'domain': domain,
            'breach_info': breach_info,
            'raw_data_count': len(breach_data) if breach_data else 0
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500