from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from models.database import db, EmailTemplate, EmailSequenceConfig, Settings, Client
from datetime import datetime
import json
import os
import re

# Create templates blueprint
templates_bp = Blueprint('templates', __name__, url_prefix='/templates')

def get_flawtrack_api():
    """Initialize FlawTrack API client"""
    try:
        from services.flawtrack_api import FlawTrackAPI
        api_token = os.getenv('FLAWTRACK_API_TOKEN')
        api_endpoint = os.getenv('FLAWTRACK_API_ENDPOINT')

        if api_token and api_endpoint:
            return FlawTrackAPI(api_token, api_endpoint)
        return None
    except ImportError:
        return None

def extract_domain_from_email(email):
    """Extract domain from email address"""
    if '@' in email:
        return email.split('@')[1]
    return email

def format_breach_data_for_template(breach_data):
    """Format breach data for email templates"""
    if not breach_data:
        # Return blank/empty values instead of 0 or "No breaches found"
        return {
            'breach_count': '',
            'breach_sources_list': '',
            'total_breached_accounts': '',
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

@templates_bp.route('/')
def templates():
    """Template management page"""
    templates = EmailTemplate.query.filter_by(is_active=True).all()
    sequences = EmailSequenceConfig.query.filter_by(is_active=True).all()
    return render_template('templates_management.html',
                         templates=templates,
                         sequences=sequences)

@templates_bp.route('/create', methods=['GET', 'POST'])
def create_template():
    """Create new email template"""
    if request.method == 'POST':
        try:
            sequence_order = request.form.get('sequence_order', 1)
            sequence_step = int(sequence_order) - 1
            print(f"DEBUG CREATE TEMPLATE: sequence_order={sequence_order}, sequence_step={sequence_step}")

            # Get client_id from form
            client_id = request.form.get('client_id')
            if client_id:
                client_id = int(client_id) if client_id.strip() else None

            template = EmailTemplate(
                name=request.form['name'],
                template_type=request.form['template_type'],
                sequence_step=sequence_step,  # Convert 1-based UI to 0-based sequence
                subject_line=request.form['subject_line'],
                email_body=request.form['email_body'],
                is_active=True,
                created_at=datetime.utcnow(),
                delay_amount=int(request.form.get('delay_amount', 0)),
                delay_unit=request.form.get('delay_unit', 'days'),
                target_industry=request.form.get('target_industry', 'general'),
                category=request.form.get('target_industry', 'general'),
                client_id=client_id,
                available_variables=json.loads(request.form.get('available_variables', '[]'))
            )

            db.session.add(template)
            db.session.commit()

            flash('Template created successfully!', 'success')
            return redirect(url_for('templates.templates'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating template: {str(e)}', 'error')
            print(f"Error creating template: {e}")

    # Get clients for dropdown
    clients = Client.query.filter_by(is_active=True).order_by(Client.company_name).all()
    return render_template('template_editor.html', template=None, clients=clients)

@templates_bp.route('/<int:template_id>/edit', methods=['GET', 'POST'])
def edit_template(template_id):
    """Edit existing email template"""
    template = EmailTemplate.query.get_or_404(template_id)

    if request.method == 'POST':
        try:
            sequence_order = request.form.get('sequence_order', 1)
            sequence_step = int(sequence_order) - 1

            # Get client_id from form
            client_id = request.form.get('client_id')
            if client_id:
                client_id = int(client_id) if client_id.strip() else None

            template.name = request.form['name']
            template.template_type = request.form['template_type']
            template.sequence_step = sequence_step
            template.subject_line = request.form['subject_line']
            template.email_body = request.form['email_body']
            template.delay_amount = int(request.form.get('delay_amount', 0))
            template.delay_unit = request.form.get('delay_unit', 'days')
            template.target_industry = request.form.get('target_industry', 'general')
            template.category = request.form.get('target_industry', 'general')
            template.client_id = client_id
            template.available_variables = json.loads(request.form.get('available_variables', '[]'))
            template.updated_at = datetime.utcnow()

            db.session.commit()
            flash('Template updated successfully!', 'success')
            return redirect(url_for('templates.templates'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating template: {str(e)}', 'error')

    # Get clients for dropdown
    clients = Client.query.filter_by(is_active=True).order_by(Client.company_name).all()
    return render_template('template_editor.html', template=template, clients=clients)

@templates_bp.route('/<int:template_id>/preview')
def preview_template(template_id):
    """Preview email template"""
    template = EmailTemplate.query.get_or_404(template_id)

    # Sample data for preview - use blank values when no data available
    sample_data = {
        'first_name': '',
        'last_name': '',
        'company': '',
        'domain': '',
        'title': '',
        'email': '',
        'sender_name': 'Emily Carter',
        'breach_count': '',
        'breach_sources_list': '',
        'total_breached_accounts': ''
    }

    return render_template('template_preview.html',
                         template=template,
                         sample_data=sample_data)

@templates_bp.route('/test-preview', methods=['POST'])
def test_preview():
    """Advanced template testing with real or sample data"""
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
        if use_real_data and test_email and ('breach' in template.name.lower() or template.template_type == 'breach'):
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
            'data_used': test_data,
            'template_name': template.name
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@templates_bp.route('/testing')
def testing_dashboard():
    """Template testing dashboard"""
    templates = EmailTemplate.query.filter_by(is_active=True).all()
    from models.database import Campaign
    campaigns = Campaign.query.all()

    return render_template('templates_management.html',
                         templates=templates,
                         campaigns=campaigns,
                         testing_mode=True)

@templates_bp.route('/<int:template_id>/editor')
def email_editor(template_id):
    """Interactive email editor with live preview"""
    template = EmailTemplate.query.get_or_404(template_id)

    # Available variables for templates
    available_variables = [
        'first_name', 'last_name', 'company', 'email', 'domain',
        'sender_name', 'breach_count', 'breach_sources_list',
        'total_breached_accounts', 'breach_sources'
    ]

    return render_template('email_editor.html',
                         template=template,
                         available_variables=available_variables)

@templates_bp.route('/api/live-preview', methods=['POST'])
def live_preview():
    """Live preview API for email editor"""
    try:
        subject = request.json.get('subject', '')
        body = request.json.get('body', '')
        test_email = request.json.get('test_email', '')
        use_real_data = request.json.get('use_real_data', False)
        template_type = request.json.get('template_type', '')
        template_id = request.json.get('template_id')  # Get template ID to fetch client data

        # Get client data from template if available
        client = None
        if template_id:
            template = EmailTemplate.query.get(template_id)
            if template and template.client_id:
                client = Client.query.get(template.client_id)

        # Test data defaults - include ALL variables with sample data
        test_data = {
            # Contact variables
            'first_name': 'John',
            'last_name': 'Smith',
            'email': test_email or 'john.smith@example.com',

            # Company variables
            'company': 'Acme Corp',
            'domain': 'acmecorp.com',
            'industry': 'Technology',
            'business_type': 'B2B Software',
            'company_size': '50-200 employees',

            # Client variables (use real client data if available, otherwise use defaults)
            'client_company_name': client.company_name if client else 'Your Company',
            'client_contact_name': client.contact_name if client else client.sender_name if client else 'Your Name',
            'client_sender_name': client.sender_name if client else 'Your Sender Name',
            'client_sender_email': client.sender_email if client else 'you@example.com',
            'client_phone': client.phone if client else '+1 (555) 000-0000',
            'client_website': client.website if client else 'https://yourwebsite.com',

            # Campaign variables
            'campaign_name': 'Q1 Outreach Campaign',

            # Legacy breach variables
            'sender_name': client.sender_name if client else 'Your Sender Name',
            'breach_count': '',
            'breach_sources_list': '',
            'total_breached_accounts': '',
            'breach_sources': []
        }

        # If using real data and template is breach-related
        if use_real_data and test_email and ('breach' in template_type.lower() or 'breach' in subject.lower()):
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
        preview_subject = subject
        preview_body = body

        for key, value in test_data.items():
            preview_subject = preview_subject.replace(f'{{{key}}}', str(value))
            preview_body = preview_body.replace(f'{{{key}}}', str(value))

        return jsonify({
            'success': True,
            'subject': preview_subject,
            'body': preview_body,
            'data_used': test_data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@templates_bp.route('/api/send-test', methods=['POST'])
def send_test_email():
    """Send test email to specified address"""
    try:
        subject = request.json.get('subject', '')
        body = request.json.get('body', '')
        sender_name = request.json.get('sender_name', 'Emily Carter')
        sender_email = request.json.get('sender_email', 'emily.carter@savety.ai')
        recipient_email = request.json.get('recipient_email', '')
        test_email = request.json.get('test_email', '')
        use_real_data = request.json.get('use_real_data', False)
        template_type = request.json.get('template_type', '')
        template_id = request.json.get('template_id')  # Get template ID to fetch client data

        if not recipient_email:
            return jsonify({
                'success': False,
                'error': 'Recipient email is required'
            }), 400

        # Get client data from template if available
        client = None
        if template_id:
            template = EmailTemplate.query.get(template_id)
            if template and template.client_id:
                client = Client.query.get(template.client_id)
                # Override sender info with client's data if available
                if client:
                    sender_name = client.sender_name
                    sender_email = client.sender_email

        # Test data defaults - include ALL variables with sample data
        test_data = {
            # Contact variables
            'first_name': 'John',
            'last_name': 'Smith',
            'email': test_email or 'john.smith@example.com',

            # Company variables
            'company': 'Acme Corp',
            'domain': 'acmecorp.com',
            'industry': 'Technology',
            'business_type': 'B2B Software',
            'company_size': '50-200 employees',

            # Client variables (use real client data if available, otherwise use defaults)
            'client_company_name': client.company_name if client else 'Your Company',
            'client_contact_name': client.contact_name if client else 'Your Name',
            'client_sender_name': client.sender_name if client else sender_name,
            'client_sender_email': client.sender_email if client else sender_email,
            'client_phone': client.phone if client else '+1 (555) 000-0000',
            'client_website': client.website if client else 'https://yourwebsite.com',

            # Campaign variables
            'campaign_name': 'Q1 Outreach Campaign',

            # Legacy variables
            'sender_name': sender_name,
            'breach_count': '',
            'breach_sources_list': '',
            'total_breached_accounts': '',
            'breach_sources': []
        }

        # If using real data and template is breach-related
        if use_real_data and test_email and ('breach' in template_type.lower() or 'breach' in subject.lower()):
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
        final_subject = subject
        final_body = body

        for key, value in test_data.items():
            final_subject = final_subject.replace(f'{{{key}}}', str(value))
            final_body = final_body.replace(f'{{{key}}}', str(value))

        # Send email using Brevo
        try:
            from services.email_service import create_email_service
            import os

            # Add test prefix to subject
            final_subject = f"[TEST] {final_subject}"

            # Try to find the client based on sender_email to use their Brevo API key
            client = Client.query.filter_by(sender_email=sender_email).first()

            if client and client.brevo_api_key:
                # Use client's Brevo API key
                brevo_api_key = client.brevo_api_key
                print(f"Using client {client.company_name}'s Brevo API key for test email")
            else:
                # Fallback to default API key
                brevo_api_key = os.getenv('BREVO_API_KEY')
                print(f"Using default Brevo API key for test email (sender: {sender_email})")

            # Create email service
            class Config:
                BREVO_API_KEY = brevo_api_key
                BREVO_SENDER_EMAIL = sender_email
                BREVO_SENDER_NAME = sender_name

            email_service = create_email_service(Config())
            success, result = email_service.send_single_email(
                to_email=recipient_email,
                subject=final_subject,
                html_content=final_body,
                from_email=sender_email,
                from_name=sender_name
            )

            if success:
                return jsonify({
                    'success': True,
                    'message': f'Test email sent successfully to {recipient_email}',
                    'subject': final_subject,
                    'data_used': test_data
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to send test email'
                }), 500

        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Email sending failed: {str(e)}'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@templates_bp.route('/api/variables')
def get_available_variables():
    """Get available template variables"""
    variables = {
        'contact': ['first_name', 'last_name', 'company', 'email', 'domain'],
        'sender': ['sender_name'],
        'breach': ['breach_count', 'breach_sources_list', 'total_breached_accounts', 'breach_sources']
    }

    return jsonify({
        'success': True,
        'variables': variables
    })

@templates_bp.route('/api/<int:template_id>/save', methods=['POST'])
def save_template_editor(template_id):
    """Save template from email editor"""
    try:
        template = EmailTemplate.query.get_or_404(template_id)

        # Get data from request
        data = request.get_json()
        subject = data.get('subject', '').strip()
        body = data.get('body', '').strip()

        if not subject or not body:
            return jsonify({
                'success': False,
                'error': 'Subject and body are required'
            }), 400

        # Update template
        template.subject_line = subject
        template.email_body = body
        template.email_body_html = body  # Keep HTML and text in sync
        template.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Template saved successfully!'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Failed to save template: {str(e)}'
        }), 500

@templates_bp.route('/<int:template_id>/delete', methods=['POST'])
def delete_template(template_id):
    """Delete email template"""
    try:
        print(f"==== DELETE_TEMPLATE CALLED at routes/templates.py line 458 ====")
        print(f"==== Attempting to DELETE template ID {template_id} ====")
        template = EmailTemplate.query.get_or_404(template_id)
        template_name = template.name
        print(f"==== Found template: {template_name} ====")

        # Check if template is being used in any emails
        from models.database import Email
        emails_using_template = Email.query.filter_by(template_id=template_id).count()
        print(f"==== Emails using template: {emails_using_template} ====")

        if emails_using_template > 0:
            print(f"==== Cannot delete - template in use ====")
            return jsonify({
                'success': False,
                'error': f'Cannot delete template "{template_name}" - it is being used by {emails_using_template} email(s)'
            })

        # Actual delete (not soft delete)
        print(f"==== Calling db.session.delete() for ACTUAL DELETE ====")
        db.session.delete(template)
        print(f"==== Calling db.session.commit() ====")
        db.session.commit()
        print(f"==== Template {template_id} DELETED successfully ====")

        return jsonify({
            'success': True,
            'message': f'Template "{template_name}" deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting template {template_id}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@templates_bp.route('/api/<int:template_id>')
def get_template_api(template_id):
    """Get template data as JSON"""
    template = EmailTemplate.query.get_or_404(template_id)
    return jsonify(template.to_dict())

@templates_bp.route('/api/list')
def list_templates_api():
    """List all templates as JSON"""
    templates = EmailTemplate.query.filter_by(is_active=True).all()
    return jsonify([template.to_dict() for template in templates])

@templates_bp.route('/api/<int:template_id>/delete', methods=['POST'])
def delete_template_api(template_id):
    """Delete email template via API (returns JSON)"""
    try:
        print(f"!!!!! API DELETE CALLED at routes/templates.py line 509 !!!!!")
        print(f"!!!!! This is the SOFT DELETE function !!!!!")
        template = EmailTemplate.query.get_or_404(template_id)
        template_name = template.name
        print(f"!!!!! Found template: {template_name} !!!!!")

        # Check if template is being used in any emails
        from models.database import Email
        emails_using_template = Email.query.filter_by(template_id=template_id).count()

        if emails_using_template > 0:
            return jsonify({
                'success': False,
                'error': f'Cannot delete template "{template_name}" - it is being used by {emails_using_template} email(s)'
            })

        # CHANGE TO ACTUAL DELETE INSTEAD OF SOFT DELETE
        print(f"!!!!! Doing ACTUAL DELETE (not soft delete) !!!!!")
        db.session.delete(template)
        db.session.commit()
        print(f"!!!!! Template {template_id} DELETED from database !!!!!")

        return jsonify({
            'success': True,
            'message': f'Template "{template_name}" deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting template {template_id}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@templates_bp.route('/sequences/<int:sequence_id>/delete', methods=['POST'])
def delete_followup_sequence(sequence_id):
    """Delete followup sequence"""
    try:
        sequence = EmailSequenceConfig.query.get_or_404(sequence_id)
        sequence_name = sequence.name

        # Check if sequence is being used in any campaigns
        from models.database import Campaign
        campaigns_using_sequence = Campaign.query.filter_by(sequence_id=sequence_id).count()

        if campaigns_using_sequence > 0:
            return jsonify({
                'success': False,
                'error': f'Cannot delete sequence "{sequence_name}" - it is being used by {campaigns_using_sequence} campaign(s)'
            })

        # Soft delete by setting active to False
        sequence.is_active = False
        sequence.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Follow-up sequence "{sequence_name}" deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting followup sequence {sequence_id}: {e}")
        return jsonify({'success': False, 'error': str(e)})