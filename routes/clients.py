"""
Client Management Routes
Handles CRUD operations for client management in the SaaS platform
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from models.database import db, Client, Campaign
from datetime import datetime
from sqlalchemy import func

clients_bp = Blueprint('clients', __name__, url_prefix='/clients')


@clients_bp.route('/')
def list_clients():
    """List all clients"""
    clients = Client.query.order_by(Client.created_at.desc()).all()

    # Get campaign count for each client
    for client in clients:
        client.campaign_count = Campaign.query.filter_by(client_id=client.id).count()

    return render_template('clients/list.html', clients=clients)


@clients_bp.route('/create', methods=['GET', 'POST'])
def create_client():
    """Create a new client"""
    if request.method == 'POST':
        try:
            # Validate required fields
            company_name = request.form.get('company_name', '').strip()
            sender_email = request.form.get('sender_email', '').strip()
            sender_name = request.form.get('sender_name', '').strip()

            if not company_name or not sender_email or not sender_name:
                flash('Company name, sender email, and sender name are required.', 'error')
                return render_template('clients/create.html')

            # Check if company name already exists
            existing_company = Client.query.filter_by(company_name=company_name).first()
            if existing_company:
                flash(f'A client with company name "{company_name}" already exists.', 'error')
                return render_template('clients/create.html')

            # Check if sender email already exists
            existing_email = Client.query.filter_by(sender_email=sender_email).first()
            if existing_email:
                flash(f'A client with sender email "{sender_email}" already exists.', 'error')
                return render_template('clients/create.html')

            # Create new client
            client = Client(
                company_name=company_name,
                contact_name=request.form.get('contact_name', '').strip(),
                website=request.form.get('website', '').strip(),
                phone=request.form.get('phone', '').strip(),
                domain=request.form.get('domain', '').strip(),
                industry=request.form.get('industry', 'general'),
                sender_email=sender_email,
                sender_name=sender_name,
                reply_to_email=request.form.get('reply_to_email', '').strip() or sender_email,
                brevo_api_key=request.form.get('brevo_api_key', '').strip(),
                brevo_sender_id=request.form.get('brevo_sender_id', '').strip(),
                subscription_tier=request.form.get('subscription_tier', 'basic'),
                monthly_email_limit=int(request.form.get('monthly_email_limit', 1000)),
                notes=request.form.get('notes', '').strip()
            )

            db.session.add(client)
            db.session.commit()

            flash(f'Client "{client.company_name}" created successfully!', 'success')
            return redirect(url_for('clients.list_clients'))

        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating client: {str(e)}', 'error')

    return render_template('clients/create.html')


@clients_bp.route('/edit/<int:client_id>', methods=['GET', 'POST'])
def edit_client(client_id):
    """Edit an existing client"""
    client = Client.query.get_or_404(client_id)

    if request.method == 'POST':
        try:
            # Validate required fields
            company_name = request.form.get('company_name', '').strip()
            sender_email = request.form.get('sender_email', '').strip()
            sender_name = request.form.get('sender_name', '').strip()

            if not company_name or not sender_email or not sender_name:
                flash('Company name, sender email, and sender name are required.', 'error')
                return render_template('clients/edit.html', client=client)

            # Check if company name already exists (excluding current client)
            existing_company = Client.query.filter(
                Client.company_name == company_name,
                Client.id != client_id
            ).first()
            if existing_company:
                flash(f'A client with company name "{company_name}" already exists.', 'error')
                return render_template('clients/edit.html', client=client)

            # Check if sender email already exists (excluding current client)
            existing_email = Client.query.filter(
                Client.sender_email == sender_email,
                Client.id != client_id
            ).first()
            if existing_email:
                flash(f'A client with sender email "{sender_email}" already exists.', 'error')
                return render_template('clients/edit.html', client=client)

            # Update client
            client.company_name = company_name
            client.contact_name = request.form.get('contact_name', '').strip()
            client.website = request.form.get('website', '').strip()
            client.phone = request.form.get('phone', '').strip()
            client.domain = request.form.get('domain', '').strip()
            client.industry = request.form.get('industry', 'general')
            client.sender_email = sender_email
            client.sender_name = sender_name
            client.reply_to_email = request.form.get('reply_to_email', '').strip() or sender_email
            client.brevo_api_key = request.form.get('brevo_api_key', '').strip()
            client.brevo_sender_id = request.form.get('brevo_sender_id', '').strip()
            client.subscription_tier = request.form.get('subscription_tier', 'basic')
            client.monthly_email_limit = int(request.form.get('monthly_email_limit', 1000))
            client.notes = request.form.get('notes', '').strip()
            client.is_active = request.form.get('is_active') == 'on'
            client.updated_at = datetime.utcnow()

            db.session.commit()

            flash(f'Client "{client.company_name}" updated successfully!', 'success')
            return redirect(url_for('clients.list_clients'))

        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating client: {str(e)}', 'error')

    return render_template('clients/edit.html', client=client)


@clients_bp.route('/delete/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    """Delete a client"""
    try:
        client = Client.query.get_or_404(client_id)

        # Check if client has associated campaigns
        campaign_count = Campaign.query.filter_by(client_id=client_id).count()
        if campaign_count > 0:
            return jsonify({
                'success': False,
                'error': f'Cannot delete client "{client.company_name}" because it has {campaign_count} associated campaigns. Please delete or reassign the campaigns first.'
            })

        client_name = client.company_name
        db.session.delete(client)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Client "{client_name}" deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        })


@clients_bp.route('/view/<int:client_id>')
def view_client(client_id):
    """View client details"""
    client = Client.query.get_or_404(client_id)

    # Get associated campaigns
    campaigns = Campaign.query.filter_by(client_id=client_id).order_by(Campaign.created_at.desc()).all()

    return render_template('clients/view.html', client=client, campaigns=campaigns)


@clients_bp.route('/toggle/<int:client_id>', methods=['POST'])
def toggle_client(client_id):
    """Toggle client active status"""
    try:
        client = Client.query.get_or_404(client_id)
        client.is_active = not client.is_active
        client.updated_at = datetime.utcnow()
        db.session.commit()

        status = 'activated' if client.is_active else 'deactivated'
        return jsonify({
            'success': True,
            'message': f'Client "{client.company_name}" {status} successfully',
            'is_active': client.is_active
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        })


# API Endpoints

@clients_bp.route('/api/list')
def api_list_clients():
    """API endpoint to get all active clients (for campaign form dropdown)"""
    try:
        # Get only active clients
        clients = Client.query.filter_by(is_active=True).order_by(Client.company_name).all()

        return jsonify({
            'success': True,
            'clients': [client.to_dict() for client in clients]
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@clients_bp.route('/api/<int:client_id>')
def api_get_client(client_id):
    """API endpoint to get a specific client's details"""
    try:
        client = Client.query.get_or_404(client_id)

        return jsonify({
            'success': True,
            'client': client.to_dict()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@clients_bp.route('/api/stats')
def api_client_stats():
    """API endpoint to get client statistics"""
    try:
        total_clients = Client.query.count()
        active_clients = Client.query.filter_by(is_active=True).count()

        # Get email usage statistics
        total_limit = db.session.query(func.sum(Client.monthly_email_limit)).scalar() or 0
        total_sent = db.session.query(func.sum(Client.emails_sent_this_month)).scalar() or 0

        return jsonify({
            'success': True,
            'stats': {
                'total_clients': total_clients,
                'active_clients': active_clients,
                'inactive_clients': total_clients - active_clients,
                'total_monthly_limit': total_limit,
                'total_emails_sent': total_sent,
                'emails_remaining': total_limit - total_sent
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@clients_bp.route('/api/<int:client_id>/campaigns')
def api_get_client_campaigns(client_id):
    """API endpoint to get all campaigns for a specific client"""
    try:
        client = Client.query.get_or_404(client_id)

        # Get all campaigns for this client
        campaigns = Campaign.query.filter_by(client_id=client_id).order_by(Campaign.created_at.desc()).all()

        campaigns_data = []
        for campaign in campaigns:
            # Get emails sent for this campaign
            from models.database import Email, Response

            emails_sent = Email.query.filter_by(campaign_id=campaign.id).count()

            # Get response count - Response is linked to Email, not Campaign directly
            # So we need to count responses for emails in this campaign
            responses = db.session.query(Response).join(
                Email, Response.email_id == Email.id
            ).filter(Email.campaign_id == campaign.id).count()

            # Get contact count - use ContactCampaignStatus if available
            try:
                from models.database import ContactCampaignStatus
                contact_count = ContactCampaignStatus.query.filter_by(campaign_id=campaign.id).count()
            except:
                # Fallback: count unique contacts from emails
                contact_count = db.session.query(Email.contact_id).filter_by(
                    campaign_id=campaign.id
                ).distinct().count()

            campaigns_data.append({
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status,
                'created_at': campaign.created_at.isoformat() if campaign.created_at else None,
                'contact_count': contact_count,
                'emails_sent': emails_sent,
                'responses': responses
            })

        return jsonify({
            'success': True,
            'campaigns': campaigns_data,
            'client_name': client.company_name
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
