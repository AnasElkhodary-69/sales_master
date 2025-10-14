"""
Campaign management routes for SalesBreachPro
Handles campaign creation, editing, management, and templates
"""
import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from utils.decorators import login_required
from models.database import (
    db, Campaign, TemplateVariant, Contact, EmailTemplate, EmailSequenceConfig,
    Email, Response, Settings, ContactCampaignStatus
)

# Create campaigns blueprint
campaigns_bp = Blueprint('campaigns', __name__, url_prefix='/campaigns')
print("CAMPAIGNS.PY LOADED - THIS IS THE UPDATED VERSION WITH TEMPLATE-BASED SEQUENCES")


@campaigns_bp.route('/api/campaigns')
@login_required
def api_campaigns():
    """API endpoint to get all campaigns for dropdowns"""
    try:
        campaigns = Campaign.query.order_by(Campaign.name).all()
        campaigns_data = []

        for campaign in campaigns:
            campaigns_data.append({
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status,
                'created_at': campaign.created_at.isoformat() if campaign.created_at else None
            })

        return jsonify(campaigns_data)

    except Exception as e:
        current_app.logger.error(f"Error fetching campaigns: {str(e)}")
        return jsonify({'error': 'Failed to fetch campaigns'}), 500


@campaigns_bp.route('/api/queue-status')
@login_required
def api_queue_status():
    """API endpoint to monitor email queue status"""
    try:
        from models.database import EmailSequence
        from datetime import datetime, timedelta

        current_time = datetime.utcnow()

        # Get queue statistics
        total_queued = EmailSequence.query.filter_by(status='scheduled').count()

        # Get emails due now
        due_now = EmailSequence.query.filter(
            EmailSequence.status == 'scheduled',
            EmailSequence.scheduled_datetime <= current_time
        ).count()

        # Get next 5 emails in queue
        next_emails = EmailSequence.query.filter(
            EmailSequence.status == 'scheduled'
        ).order_by(EmailSequence.scheduled_datetime.asc()).limit(5).all()

        next_queue = []
        for email_seq in next_emails:
            time_until = email_seq.scheduled_datetime - current_time if email_seq.scheduled_datetime else None
            next_queue.append({
                'contact_id': email_seq.contact_id,
                'campaign_id': email_seq.campaign_id,
                'sequence_step': email_seq.sequence_step,
                'scheduled_time': email_seq.scheduled_datetime.isoformat() if email_seq.scheduled_datetime else None,
                'time_until_seconds': time_until.total_seconds() if time_until else None,
                'status': 'due_now' if time_until and time_until.total_seconds() <= 0 else 'queued'
            })

        # Calculate estimated completion time
        if total_queued > 0:
            queue_delay_minutes = int(os.getenv('QUEUE_DELAY_MINUTES', 5))
            estimated_completion = current_time + timedelta(minutes=total_queued * queue_delay_minutes)
        else:
            estimated_completion = current_time

        return jsonify({
            'success': True,
            'queue_stats': {
                'total_queued': total_queued,
                'due_now': due_now,
                'estimated_completion': estimated_completion.isoformat(),
                'queue_delay_minutes': int(os.getenv('QUEUE_DELAY_MINUTES', 5))
            },
            'next_emails': next_queue
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching queue status: {str(e)}")
        return jsonify({'error': 'Failed to fetch queue status'}), 500


@campaigns_bp.route('/')
@login_required
def index():
    """Campaigns management page with real metrics"""
    try:
        # Get all campaigns from database with real metrics
        campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()

        # Calculate real metrics for each campaign
        campaigns_with_metrics = []
        for campaign in campaigns:
            # Get real contact count for this campaign
            contact_count = db.session.query(Contact).join(Email).filter(
                Email.campaign_id == campaign.id
            ).distinct().count()

            # Get real email counts
            emails = Email.query.filter_by(campaign_id=campaign.id).all()
            sent_count = sum(1 for email in emails if email.status in ['sent', 'delivered', 'opened', 'clicked', 'replied'])
            opened_count = sum(1 for email in emails if email.opened_at is not None)
            replied_count = sum(1 for email in emails if email.replied_at is not None)

            # Calculate response rate
            response_rate = (replied_count / sent_count * 100) if sent_count > 0 else 0
            open_rate = (opened_count / sent_count * 100) if sent_count > 0 else 0

            # Update campaign object with real metrics
            campaign.total_contacts = contact_count
            campaign.sent_count = sent_count
            campaign.response_count = replied_count
            campaign._response_rate = response_rate
            campaign._open_rate = open_rate

            campaigns_with_metrics.append(campaign)

        return render_template('campaigns.html', campaigns=campaigns_with_metrics)
    except Exception as e:
        print(f"Campaigns error: {e}")
        return render_template('campaigns.html', campaigns=[])


@campaigns_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_campaign():
    """Create new campaign"""
    print(f"NEW CAMPAIGN ROUTE: {request.method} request received")
    try:
        # Get contact statistics using breach_status
        total_contacts = Contact.query.count()
        breached_contacts = Contact.query.filter(Contact.breach_status == 'breached').count()
        secure_contacts = Contact.query.filter(Contact.breach_status == 'not_breached').count()
        unknown_contacts = Contact.query.filter(
            (Contact.breach_status == 'unknown') | (Contact.breach_status.is_(None))
        ).count()
        
        contact_stats = {
            'total_contacts': total_contacts,
            'breached': breached_contacts,
            'secure': secure_contacts,
            'unknown': unknown_contacts,
            # Legacy support for old templates
            'high_risk': breached_contacts,
            'medium_risk': 0,
            'low_risk': secure_contacts + unknown_contacts
        }
        
        if request.method == 'POST':
            print("=== CAMPAIGN CREATION SERVER DEBUG ===")
            print(f"POST request received for new campaign")
            print(f"Form data received: {dict(request.form)}")
            print(f"Request method: {request.method}")
            print(f"Request path: {request.path}")
            print("===========================================")
            try:
                # Handle target risk levels (multiple checkboxes)
                target_risk_levels = request.form.getlist('target_risk_levels')
                
                # Get template or sequence ID based on campaign type
                campaign_type = request.form.get('campaign_type')
                template_id = None
                selected_variant_id = None

                if campaign_type == 'single':
                    template_id = request.form.get('template_id')
                    selected_variant_id = request.form.get('selected_variant_id')
                    print(f"Single campaign: template_id={template_id}, selected_variant_id={selected_variant_id}")
                elif campaign_type == 'sequence':
                    # For sequences, use the first template (sequence_step = 0) of the target risk level
                    sequence_id = request.form.get('sequence_id')
                    
                    # Find the initial template for this risk level
                    initial_template = EmailTemplate.query.filter(
                        EmailTemplate.sequence_step == 0,
                        EmailTemplate.risk_level.in_(target_risk_levels)
                    ).first()
                    
                    if initial_template:
                        template_id = initial_template.id
                    else:
                        # Fallback to any template with sequence_step = 0
                        fallback_template = EmailTemplate.query.filter(EmailTemplate.sequence_step == 0).first()
                        if fallback_template:
                            template_id = fallback_template.id
                
                # Ensure template_id is always set
                if not template_id:
                    fallback_template = EmailTemplate.query.first()
                    if fallback_template:
                        template_id = fallback_template.id
                        print(f"WARNING: Using fallback template {template_id} for campaign")
                
                # Auto-enrollment settings
                auto_enroll = 'auto_enroll' in request.form
                auto_enroll_breach_status = request.form.get('auto_enroll_breach_status') if auto_enroll else None
                
                # Email approval workflow settings
                approval_mode = request.form.get('approval_mode', 'automatic')
                requires_approval = approval_mode in ['manual_approval', 'batch_approval']

                campaign = Campaign(
                    name=request.form['name'],
                    description=request.form.get('description', ''),
                    sender_name=request.form.get('sender_name'),
                    sender_email=request.form.get('sender_email'),
                    template_type=request.form.get('template_type', 'unknown'),
                    template_id=template_id if template_id else None,
                    target_risk_levels=target_risk_levels,
                    daily_limit=int(request.form.get('daily_limit', 50)),
                    status='active',  # Set to active when launched
                    auto_enroll=auto_enroll,
                    auto_enroll_breach_status=auto_enroll_breach_status,
                    # Email approval workflow fields
                    requires_approval=requires_approval,
                    approval_mode=approval_mode
                )
                
                db.session.add(campaign)
                db.session.flush()  # Get the campaign ID
                
                # Trigger auto-enrollment for the new campaign if auto_enroll is enabled
                emails_created = 0
                if auto_enroll:
                    from services.auto_enrollment import create_auto_enrollment_service
                    
                    # Commit first so the campaign exists for auto-enrollment
                    db.session.commit()
                    
                    # Trigger auto-enrollment for this specific campaign
                    auto_service = create_auto_enrollment_service(db)
                    result = auto_service._process_campaign_enrollment(campaign)
                    emails_created = result
                    
                    print(f"Auto-enrollment created {emails_created} emails for new campaign")
                    
                    # Immediately process emails for instant sending
                    if emails_created > 0:
                        from services.email_processor import EmailProcessor
                        email_processor = EmailProcessor()
                        send_result = email_processor.process_scheduled_emails()
                        print(f"Immediate email processing: {send_result}")
                else:
                    print("Auto-enrollment disabled for this campaign")
                
                db.session.commit()
                
                print(f"Campaign created with {emails_created} contacts enrolled")
                return redirect(url_for('campaigns.index'))
                
            except Exception as e:
                db.session.rollback()
                print(f"Campaign creation error: {str(e)}")
                return render_template('new_campaign.html', contact_stats=contact_stats, error="Error creating campaign")
        
        # Fetch actual templates and sequences from database
        print("DEBUG: Fetching templates and sequences from database")
        try:
            templates = EmailTemplate.query.filter_by(active=True).all()
            print(f"DEBUG: Successfully fetched {len(templates)} active templates")
            for template in templates:
                print(f"DEBUG: Template: {template.name} (risk: {template.risk_level}, breach_type: {getattr(template, 'breach_template_type', 'None')}, step: {template.sequence_step})")
        except Exception as e:
            print(f"DEBUG: Error fetching templates: {e}")
            import traceback
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
            templates = []
        
        # Create sequences from EmailTemplate objects grouped by breach_template_type
        sequences = []
        template_groups = {}
        
        # Group templates by risk_level (e.g., 'breached', 'unknown') 
        # Each risk level becomes its own sequence
        for template in templates:
            template_type = template.risk_level or template.breach_template_type or 'unknown'
            if template_type not in template_groups:
                template_groups[template_type] = []
            template_groups[template_type].append(template)
        
        # Create sequence objects for each group
        for template_type, template_list in template_groups.items():
            # Sort templates by sequence_step to ensure correct ordering
            sorted_templates = sorted(template_list, key=lambda t: t.sequence_step or 0)
            
            sequences.append({
                'id': template_type,  # Use template_type as unique ID
                'name': f'{template_type.title()} Email Sequence',
                'risk_level': template_type,
                'description': f'{len(sorted_templates)}-email sequence for {template_type} contacts',
                'template_count': len(sorted_templates),
                'templates': sorted_templates  # Include the actual templates
            })
        
        print(f"DEBUG: Found {len(templates)} templates, {len(template_groups)} groups, created {len(sequences)} sequences")
        for group_name, group_templates in template_groups.items():
            print(f"DEBUG: Group '{group_name}' has {len(group_templates)} templates")
        for i, seq in enumerate(sequences):
            print(f"DEBUG: Sequence {i}: {seq}")
        
        # If no templates exist in database, use demo templates as fallback
        if not templates:
            demo_templates = [
                {
                    'id': 1,
                    'name': 'Breach Response Template',
                    'template_type': 'breached',
                    'subject': 'URGENT: Your data may have been compromised',
                    'content': 'Dear {{name}}, We\'ve detected that your personal information may have been exposed in a recent data breach. Our security experts can help you protect your accounts immediately...'
                },
                {
                    'id': 2,
                    'name': 'Proactive Security Template',
                    'template_type': 'secure',
                    'subject': 'Strengthen Your Security - {{company}}',
                    'content': 'Hello {{name}}, We want to help {{company}} maintain its excellent security posture. Our experts can provide additional protection measures...'
                },
                {
                    'id': 3,
                    'name': 'Security Assessment Template',
                    'template_type': 'unknown',
                    'subject': 'Free Security Assessment for {{company}}',
                    'content': 'Hi {{name}}, We\'re offering complimentary security assessments to help businesses like {{company}} understand their cybersecurity status...'
                }
            ]
            templates = demo_templates
        else:
            # Convert SQLAlchemy objects to dict for template consistency
            templates = [template.to_dict() for template in templates]
        
        # If no sequences were created from templates, use demo sequences as fallback
        print(f"DEBUG: Checking if we need demo sequences: sequences={len(sequences)}")
        if not sequences:
            demo_sequences = [
                {
                    'id': 'breached',
                    'name': 'Breach Response Follow-up Sequence',
                    'risk_level': 'breached',
                    'description': '5-email sequence for breached contacts'
                },
                {
                    'id': 'unknown',
                    'name': 'Security Assessment Follow-up Sequence',
                    'risk_level': 'unknown',
                    'description': '3-email sequence for unknown status contacts'
                },
                {
                    'id': 'proactive',
                    'name': 'Proactive Security Follow-up Sequence',
                    'risk_level': 'proactive',
                    'description': '2-email sequence for proactive contacts'
                }
            ]
            sequences = demo_sequences
        
        # Debug logging
        print("DEBUG: Final sequences ready for template")
        for i, seq in enumerate(sequences):
            print(f"DEBUG: Sequence {i}: {seq.get('name', 'Unknown')} ({seq.get('template_count', 0)} templates)")
        
        print("DEBUG: About to render template")
        print(f"DEBUG: Templates count: {len(templates)}")
        print(f"DEBUG: Sequences count: {len(sequences)}")
        print(f"DEBUG: Contact stats: {contact_stats}")
        
        try:
            return render_template('new_campaign.html', 
                                 templates=templates, 
                                 sequences=sequences,
                                 contact_stats=contact_stats)
        except Exception as e:
            print(f"DEBUG: Template rendering error: {e}")
            import traceback
            traceback.print_exc()
            raise
        
    except Exception as e:
        print(f"New campaign error: {e}")
        # Still calculate contact stats even if other parts fail
        try:
            total_contacts = Contact.query.count()
            breached_contacts = Contact.query.filter(Contact.breach_status == 'breached').count()
            secure_contacts = Contact.query.filter(Contact.breach_status == 'not_breached').count()
            unknown_contacts = Contact.query.filter(
                (Contact.breach_status == 'unknown') | (Contact.breach_status.is_(None))
            ).count()
            
            contact_stats = {
                'total_contacts': total_contacts,
                'breached': breached_contacts,
                'secure': secure_contacts,
                'unknown': unknown_contacts,
                # Legacy support for old templates
                'high_risk': breached_contacts,
                'medium_risk': 0,
                'low_risk': secure_contacts + unknown_contacts
            }
        except:
            contact_stats = {'total_contacts': 0, 'breached': 0, 'secure': 0, 'unknown': 0, 'high_risk': 0, 'medium_risk': 0, 'low_risk': 0}
        
        # Use fallback demo data for templates and sequences
        demo_templates = [
            {
                'id': 1,
                'name': 'Breach Response Template',
                'template_type': 'breached',
                'subject': 'URGENT: Your data may have been compromised',
                'content': 'Dear {{name}}, We\'ve detected that your personal information may have been exposed in a recent data breach. Our security experts can help you protect your accounts immediately...'
            },
            {
                'id': 2,
                'name': 'Proactive Security Template',
                'template_type': 'secure',
                'subject': 'Strengthen Your Security - {{company}}',
                'content': 'Hello {{name}}, We want to help {{company}} maintain its excellent security posture. Our experts can provide additional protection measures...'
            },
            {
                'id': 3,
                'name': 'Security Assessment Template',
                'template_type': 'unknown',
                'subject': 'Free Security Assessment for {{company}}',
                'content': 'Hi {{name}}, We\'re offering complimentary security assessments to help businesses like {{company}} understand their cybersecurity status...'
            }
        ]
        
        demo_sequences = [
            {
                'id': 1,
                'name': 'Breach Response Follow-up Sequence',
                'risk_level': 'breached',
                'description': '5-email sequence for breached contacts'
            },
            {
                'id': 2,
                'name': 'Security Assessment Follow-up Sequence',
                'risk_level': 'unknown',
                'description': '3-email sequence for unknown status contacts'
            },
            {
                'id': 3,
                'name': 'Proactive Security Follow-up Sequence',
                'risk_level': 'secure',
                'description': '2-email sequence for secure contacts'
            }
        ]
        
        return render_template('new_campaign.html', 
                             templates=demo_templates, 
                             sequences=demo_sequences,
                             contact_stats=contact_stats,
                             error="Some features may be limited")


@campaigns_bp.route('/<int:campaign_id>')
@login_required
def view_campaign(campaign_id):
    """View campaign details with accurate Brevo tracking data"""
    try:
        from services.campaign_analytics import create_campaign_analytics
        
        campaign = Campaign.query.get_or_404(campaign_id)
        
        # Get comprehensive analytics
        analytics = create_campaign_analytics()
        metrics = analytics.get_campaign_metrics(campaign_id)
        email_timeline = analytics.get_email_timeline(campaign_id, limit=20)
        
        if 'error' in metrics:
            flash(f'Error loading campaign analytics: {metrics["error"]}', 'error')
            return redirect(url_for('campaigns.index'))
        
        # Get ALL campaign contacts with their sequence status
        from models.database import ContactCampaignStatus, EmailSequence

        # Use ContactCampaignStatus as the primary filter since that tracks enrollment
        # regardless of whether emails were actually sent
        contacts_query = db.session.query(
            Contact,
            ContactCampaignStatus,
            db.func.count(Email.id).label('emails_sent'),
            db.func.sum(db.case((Email.opened_at != None, 1), else_=0)).label('emails_opened'),
            db.func.sum(db.case((Email.replied_at != None, 1), else_=0)).label('emails_replied'),
            db.func.max(Email.sent_at).label('last_email_sent')
        ).join(
            ContactCampaignStatus,
            db.and_(
                ContactCampaignStatus.contact_id == Contact.id,
                ContactCampaignStatus.campaign_id == campaign_id
            )
        ).outerjoin(
            Email,
            db.and_(
                Email.contact_id == Contact.id,
                Email.campaign_id == campaign_id
            )
        ).group_by(Contact.id, ContactCampaignStatus.id).order_by(
            Contact.last_contacted.desc().nullslast()
        ).all()
        
        # Process contacts with sequence information
        contacts_with_status = []
        for result in contacts_query:
            contact, status, emails_sent, emails_opened, emails_replied, last_email_sent = result
            
            # Get current sequence step information
            current_sequence = None
            next_email_date = None
            sequence_status = "Not Enrolled"
            
            if status:
                # Check if contact is blocked (contact-level or email-level blocking)
                if contact.blocked_at:
                    sequence_status = "Blocked"
                elif status.replied_at:
                    sequence_status = "Replied"
                elif status.sequence_completed_at:
                    sequence_status = "Completed"
                else:
                    sequence_status = "Active"
                
                # Only get next scheduled email for Active sequences
                if sequence_status == "Active":
                    next_email = EmailSequence.query.filter_by(
                        contact_id=contact.id,
                        campaign_id=campaign_id,
                        status='scheduled'
                    ).order_by(EmailSequence.scheduled_date).first()

                    if next_email:
                        next_email_date = next_email.scheduled_datetime
                        current_sequence = f"Step {next_email.sequence_step - 1}" if next_email.sequence_step > 1 else "Initial"
                        next_step = f"Step {next_email.sequence_step}"
                    elif status.current_sequence_step:
                        current_sequence = f"Step {status.current_sequence_step}"
                        next_step = f"Step {status.current_sequence_step + 1}"
                    else:
                        next_step = "Step 1"
                else:
                    # For stopped sequences (Blocked, Replied, Completed), no next step
                    if status.current_sequence_step:
                        current_sequence = f"Step {status.current_sequence_step}"
                    else:
                        current_sequence = "Initial"

            contacts_with_status.append({
                'contact': contact,
                'sequence_status': sequence_status,
                'current_step': current_sequence or "Initial",
                'next_step': next_step if sequence_status == "Active" else None,
                'emails_sent': emails_sent or 0,
                'emails_opened': emails_opened or 0,
                'emails_replied': emails_replied or 0,
                'last_email_sent': last_email_sent,
                'next_email_date': next_email_date if sequence_status == "Active" else None,
                'breach_status': contact.breach_status or 'unknown',
                'status_obj': status
            })
        
        contacts = contacts_with_status
        
        # Create comprehensive performance object with Brevo data
        performance = {
            'sent_count': metrics['email_stats']['sent_count'],
            'delivered_count': metrics['email_stats']['delivered_count'],
            'opened_count': metrics['email_stats']['opened_count'],
            'clicked_count': metrics['email_stats']['clicked_count'],
            'replied_count': metrics['email_stats']['replied_count'],
            'bounced_count': metrics['email_stats']['bounced_count'],
            'blocked_count': metrics['email_stats']['blocked_count'],
            'pending_count': metrics['email_stats']['pending_count'],
            'total_contacts': metrics['contacts']['enrolled_contacts'],

            # Performance rates from Brevo webhooks
            'delivery_rate': metrics['performance']['delivery_rate'],
            'open_rate': metrics['performance']['open_rate'],
            'click_rate': metrics['performance']['click_rate'],
            'reply_rate': metrics['performance']['reply_rate'],
            'blocked_rate': metrics['performance']['blocked_rate'],
            'bounce_rate': metrics['performance']['bounce_rate'],
            
            # Sequence status
            'active_sequences': metrics['contacts']['active_sequences'],
            'stopped_sequences': metrics['contacts']['stopped_sequences'],
            'completed_sequences': metrics['contacts']['completed_sequences'],
            
            # Recent activity (24h)
            'recent_opens': metrics['recent_activity']['opens_24h'],
            'recent_clicks': metrics['recent_activity']['clicks_24h'],
            'recent_replies': metrics['recent_activity']['replies_24h']
        }
        
        # Campaign variants system deprecated - use template variants instead
        variants = []  # No more campaign variants

        # Legacy campaign variant system deprecated
        # Template variants are now managed at the template level, not campaign level
        pass

        return render_template('campaign_details.html',
                             campaign=campaign,
                             variants=variants,
                             metrics=metrics,
                             performance=performance,
                             contacts=contacts,
                             email_timeline=email_timeline,
                             # Legacy support for old templates
                             emails_sent=metrics['email_stats']['sent_count'],
                             responses=metrics['email_stats']['replied_count'])
    except Exception as e:
        print(f"View campaign error: {e}")
        flash(f'Error loading campaign: {str(e)}', 'error')
        return redirect(url_for('campaigns.index'))


@campaigns_bp.route('/<int:campaign_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_campaign(campaign_id):
    """Edit campaign"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        if request.method == 'POST':
            # Update campaign fields
            campaign.name = request.form.get('name')
            campaign.description = request.form.get('description', '')
            campaign.sender_name = request.form.get('sender_name')
            campaign.sender_email = request.form.get('sender_email')
            campaign.daily_limit = int(request.form.get('daily_limit', 50))
            campaign.target_risk_levels = request.form.getlist('target_risk_levels')
            
            # Auto-enrollment settings
            campaign.auto_enroll = 'auto_enroll' in request.form
            campaign.auto_enroll_breach_status = request.form.get('auto_enroll_breach_status') if campaign.auto_enroll else None

            # Email approval workflow settings
            approval_mode = request.form.get('approval_mode', 'automatic')
            campaign.requires_approval = approval_mode in ['manual_approval', 'batch_approval']
            campaign.approval_mode = approval_mode

            db.session.commit()
            flash('Campaign updated successfully!', 'success')
            return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))
        
        # Get contact statistics using breach_status
        total_contacts = Contact.query.count()
        breached_contacts = Contact.query.filter(Contact.breach_status == 'breached').count()
        secure_contacts = Contact.query.filter(Contact.breach_status == 'not_breached').count()
        unknown_contacts = Contact.query.filter(
            (Contact.breach_status == 'unknown') | (Contact.breach_status.is_(None))
        ).count()
        
        contact_stats = {
            'total_contacts': total_contacts,
            'breached': breached_contacts,
            'secure': secure_contacts,
            'unknown': unknown_contacts,
            # Legacy support for old templates
            'high_risk': breached_contacts,
            'medium_risk': 0,
            'low_risk': secure_contacts + unknown_contacts
        }
        
        return render_template('edit_campaign.html', campaign=campaign, contact_stats=contact_stats)
        
    except Exception as e:
        print(f"Edit campaign error: {e}")
        flash(f'Error editing campaign: {str(e)}', 'error')
        return redirect(url_for('campaigns.index'))


@campaigns_bp.route('/<int:campaign_id>/toggle', methods=['POST'])
@login_required
def toggle_campaign(campaign_id):
    """Toggle campaign active/paused status"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        # Toggle status
        if campaign.status == 'active':
            campaign.status = 'paused'
            message = f'Campaign "{campaign.name}" paused successfully'
        else:
            campaign.status = 'active'
            message = f'Campaign "{campaign.name}" activated successfully'
        
        db.session.commit()
        return jsonify({'success': True, 'message': message, 'new_status': campaign.status})
        
    except Exception as e:
        print(f"Toggle campaign error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/<int:campaign_id>/status', methods=['POST'])
@login_required
def update_campaign_status(campaign_id):
    """Update campaign status (pause/resume)"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['active', 'paused']:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400
            
        campaign.status = new_status
        db.session.commit()
        
        message = f'Campaign "{campaign.name}" {"paused" if new_status == "paused" else "activated"} successfully'
        return jsonify({'success': True, 'message': message, 'new_status': campaign.status})
        
    except Exception as e:
        db.session.rollback()
        print(f"Update campaign status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/<int:campaign_id>/duplicate', methods=['POST'])
@login_required
def duplicate_campaign(campaign_id):
    """Duplicate campaign"""
    try:
        original_campaign = Campaign.query.get_or_404(campaign_id)
        
        # Create new campaign with copied data
        new_campaign = Campaign(
            name=f"{original_campaign.name} (Copy)",
            description=original_campaign.description,
            sender_name=original_campaign.sender_name,
            sender_email=original_campaign.sender_email,
            template_type=original_campaign.template_type,
            template_id=original_campaign.template_id,
            target_risk_levels=original_campaign.target_risk_levels,
            daily_limit=original_campaign.daily_limit,
            status='draft',  # New campaigns start as draft
            auto_enroll=original_campaign.auto_enroll,
            auto_enroll_breach_status=original_campaign.auto_enroll_breach_status
        )
        
        db.session.add(new_campaign)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Campaign duplicated successfully', 'new_campaign_id': new_campaign.id})
        
    except Exception as e:
        db.session.rollback()
        print(f"Duplicate campaign error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/<int:campaign_id>/export', methods=['GET'])
@login_required
def export_campaign_results(campaign_id):
    """Export campaign results"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        # Get campaign data for export
        emails = Email.query.filter_by(campaign_id=campaign_id).all()
        contacts = Contact.query.join(Email).filter(Email.campaign_id == campaign_id).distinct().all()
        responses = Response.query.join(Email).filter(Email.campaign_id == campaign_id).all()
        
        # Create CSV data (simplified for now)
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Contact Email', 'Company', 'Risk Score', 'Email Status', 'Response Count'])
        
        # Write data
        for contact in contacts:
            contact_emails = [e for e in emails if e.contact_id == contact.id]
            contact_responses = [r for r in responses if any(e.id == r.email_id for e in contact_emails)]
            
            writer.writerow([
                contact.email,
                contact.company or '',
                contact.risk_score or 0,
                contact_emails[0].status if contact_emails else 'none',
                len(contact_responses)
            ])
        
        # Create response
        from flask import make_response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=campaign_{campaign.name}_results.csv'
        
        return response
        
    except Exception as e:
        print(f"Export campaign error: {e}")
        from flask import abort
        abort(500)


@campaigns_bp.route('/<int:campaign_id>/contacts/export', methods=['GET'])
@login_required
def export_campaign_contacts(campaign_id):
    """Export contacts enrolled in a specific campaign"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)

        # Get contacts enrolled in this campaign with their campaign-specific data
        contacts_query = db.session.query(Contact, ContactCampaignStatus).join(
            ContactCampaignStatus, Contact.id == ContactCampaignStatus.contact_id
        ).filter(ContactCampaignStatus.campaign_id == campaign_id)

        contacts_data = contacts_query.all()

        if not contacts_data:
            # If no contacts with campaign status, try getting just contacts from emails
            contacts_data = []
            emails_contacts = db.session.query(Contact).join(Email).filter(Email.campaign_id == campaign_id).distinct().all()
            for contact in emails_contacts:
                contacts_data.append((contact, None))  # None for campaign status

        # Create CSV data
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow([
            'Email', 'First Name', 'Last Name', 'Company', 'Title', 'Industry',
            'Breach Status', 'Risk Score', 'Added Date', 'Current Step', 'Sequence Status',
            'Emails Sent', 'Last Email Sent', 'Last Contacted', 'Replied', 'Reply Date', 'Unsubscribed'
        ])

        # Write contact data
        for contact, campaign_status in contacts_data:
            # Get email statistics for this contact in this campaign
            contact_emails = Email.query.filter_by(
                contact_id=contact.id,
                campaign_id=campaign_id
            ).all()

            emails_sent_count = len([e for e in contact_emails if e.status in ['sent', 'delivered', 'opened', 'clicked']])
            last_email_sent = max([e.sent_at for e in contact_emails if e.sent_at], default=None)

            writer.writerow([
                contact.email,
                contact.first_name or '',
                contact.last_name or '',
                contact.company or '',
                contact.title or '',
                contact.industry or '',
                contact.breach_status or '',
                contact.risk_score or 0,
                campaign_status.created_at.strftime('%Y-%m-%d %H:%M:%S') if campaign_status and campaign_status.created_at else '',
                campaign_status.current_sequence_step if campaign_status else 0,
                'Completed' if campaign_status and campaign_status.sequence_completed_at else 'Active',
                emails_sent_count,
                last_email_sent.strftime('%Y-%m-%d %H:%M:%S') if last_email_sent else '',
                contact.last_contacted.strftime('%Y-%m-%d %H:%M:%S') if contact.last_contacted else '',
                'Yes' if campaign_status and campaign_status.replied_at else 'No',
                campaign_status.replied_at.strftime('%Y-%m-%d %H:%M:%S') if campaign_status and campaign_status.replied_at else '',
                'Yes' if contact.unsubscribed else 'No'
            ])

        # Create response
        from flask import make_response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=campaign_{campaign.name.replace(" ", "_")}_contacts.csv'

        return response

    except Exception as e:
        import traceback
        print(f"Export campaign contacts error: {e}")
        print("Full traceback:")
        traceback.print_exc()
        from flask import abort
        abort(500)


@campaigns_bp.route('/api/<int:campaign_id>/stats', methods=['GET'])
@login_required
def get_campaign_stats(campaign_id):
    """Get real-time campaign statistics using Brevo webhook data"""
    try:
        from services.campaign_analytics import create_campaign_analytics
        
        analytics = create_campaign_analytics()
        metrics = analytics.get_campaign_metrics(campaign_id)
        
        if 'error' in metrics:
            return jsonify({'success': False, 'error': metrics['error']}), 404
        
        # Format for the frontend
        stats = {
            'sent_count': metrics['email_stats']['sent_count'],
            'total_contacts': metrics['contacts']['enrolled_contacts'],
            'delivered_count': metrics['email_stats']['delivered_count'],
            'opened_count': metrics['email_stats']['opened_count'],
            'clicked_count': metrics['email_stats']['clicked_count'],
            'replied_count': metrics['email_stats']['replied_count'],
            'bounced_count': metrics['email_stats']['bounced_count'],
            'pending_count': metrics['email_stats']['pending_count'],
            
            # Performance rates
            'delivery_rate': metrics['performance']['delivery_rate'],
            'open_rate': metrics['performance']['open_rate'],
            'click_rate': metrics['performance']['click_rate'],
            'reply_rate': metrics['performance']['reply_rate'],
            'bounce_rate': metrics['performance']['bounce_rate'],
            
            # Sequence info
            'active_sequences': metrics['contacts']['active_sequences'],
            'stopped_sequences': metrics['contacts']['stopped_sequences'],
            
            # Recent activity
            'recent_opens': metrics['recent_activity']['opens_24h'],
            'recent_clicks': metrics['recent_activity']['clicks_24h'],
            'recent_replies': metrics['recent_activity']['replies_24h']
        }
        
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        print(f"Get campaign stats error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@campaigns_bp.route('/api/<int:campaign_id>/timeline', methods=['GET'])
@login_required
def get_campaign_timeline(campaign_id):
    """Get email timeline for campaign dashboard"""
    try:
        from services.campaign_analytics import create_campaign_analytics
        
        # Get limit and offset from query parameters
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))

        analytics = create_campaign_analytics()
        timeline = analytics.get_email_timeline(campaign_id, limit=limit, offset=offset)
        
        return jsonify({
            'success': True,
            'timeline': timeline,
            'count': len(timeline),
            'limit': limit,
            'offset': offset,
            'has_more': len(timeline) == limit  # If we got exactly limit records, there might be more
        })
        
    except Exception as e:
        print(f"Get campaign timeline error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/<int:campaign_id>/contacts/add', methods=['POST'])
@login_required
def add_contacts_to_campaign(campaign_id):
    """Add contacts to campaign"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        data = request.get_json()
        contact_ids = data.get('contact_ids', [])
        
        if not contact_ids:
            return jsonify({'success': False, 'error': 'No contacts selected'}), 400
        
        # Get contacts that aren't already in this campaign
        existing_contact_ids = [email.contact_id for email in Email.query.filter_by(campaign_id=campaign_id).all()]
        new_contact_ids = [cid for cid in contact_ids if cid not in existing_contact_ids]
        
        if not new_contact_ids:
            return jsonify({'success': False, 'error': 'All selected contacts are already in this campaign'}), 400
        
        # Use auto-enrollment service to properly enroll contacts
        from services.auto_enrollment import create_auto_enrollment_service
        
        auto_service = create_auto_enrollment_service(db)
        contacts_enrolled = 0
        errors = []
        
        for contact_id in new_contact_ids:
            contact = Contact.query.get(contact_id)
            if contact:
                # Use the working enroll_single_contact method
                success = auto_service.enroll_single_contact(contact_id, campaign_id)
                
                if success:
                    contacts_enrolled += 1
                    print(f"Successfully enrolled contact {contact.email} into campaign")
                else:
                    errors.append(f"Failed to enroll contact {contact.email}")
        
        # Commit changes
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully added {contacts_enrolled} contacts to campaign',
            'contacts_added': contacts_enrolled,
            'errors': errors if errors else None
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Add contacts to campaign error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/api/<int:campaign_id>/analytics', methods=['GET'])
@login_required
def get_campaign_analytics_api(campaign_id):
    """API endpoint for real-time campaign analytics"""
    try:
        from services.campaign_analytics import create_campaign_analytics
        
        analytics = create_campaign_analytics()
        metrics = analytics.get_campaign_metrics(campaign_id)
        
        if 'error' in metrics:
            return jsonify({
                'success': False,
                'error': metrics['error']
            }), 404
        
        return jsonify({
            'success': True,
            'metrics': metrics
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/<int:campaign_id>/contacts/<int:contact_id>/remove', methods=['POST'])
@login_required
def remove_contact_from_campaign(campaign_id, contact_id):
    """Remove contact from campaign and clean up ALL associated data"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        contact = Contact.query.get_or_404(contact_id)

        print(f"Removing contact {contact.email} from campaign {campaign.name}")

        # 1. Delete all EmailSequence records for this contact in this campaign
        sequences_deleted = EmailSequence.query.filter_by(
            campaign_id=campaign_id,
            contact_id=contact_id
        ).delete()
        print(f"Deleted {sequences_deleted} email sequences")

        # 2. Find and delete all Email records for this contact in this campaign
        emails = Email.query.filter_by(campaign_id=campaign_id, contact_id=contact_id).all()
        emails_deleted = 0

        for email in emails:
            # Delete any responses associated with this email first
            responses_deleted = Response.query.filter_by(email_id=email.id).delete()
            print(f"Deleted {responses_deleted} responses for email {email.id}")

            # Delete the email record
            db.session.delete(email)
            emails_deleted += 1

        print(f"Deleted {emails_deleted} email records")

        # 3. Delete ContactCampaignStatus record if exists
        campaign_status = ContactCampaignStatus.query.filter_by(
            contact_id=contact_id,
            campaign_id=campaign_id
        ).first()

        if campaign_status:
            db.session.delete(campaign_status)
            print(f"Deleted campaign status for contact")

        # 4. Reset contact's campaign-related fields (optional - keeps contact clean)
        # You might want to reset last_contacted_at if this was the only campaign
        other_campaigns = Email.query.filter(
            Email.contact_id == contact_id,
            Email.campaign_id != campaign_id
        ).count()

        if other_campaigns == 0:
            # This contact is not in any other campaigns, reset tracking fields
            contact.last_contacted_at = None
            contact.last_contacted = None
            print(f"Reset contact tracking fields (no other campaigns)")

        db.session.commit()

        # Use the comprehensive cleanup utility for thorough cleaning
        from utils.contact_cleanup import deep_clean_contact_campaign_data, verify_contact_clean_state

        # Verify the cleanup was complete
        verification = verify_contact_clean_state(contact_id, campaign_id)

        if not verification['is_clean']:
            print(f"⚠ Warning: Cleanup may be incomplete: {verification['issues_found']}")

        # Get contact info for response
        contact_name = contact.email
        
        return jsonify({
            'success': True,
            'message': f'Successfully removed {contact_name} from campaign',
            'cleanup_verification': verification
        })

    except Exception as e:
        db.session.rollback()
        print(f"Remove contact from campaign error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/<int:campaign_id>/contacts/<int:contact_id>/deep-clean', methods=['POST'])
@login_required
def deep_clean_contact(campaign_id, contact_id):
    """Deep clean a contact's data from campaign for fresh testing"""
    try:
        from utils.contact_cleanup import reset_contact_for_fresh_testing

        result = reset_contact_for_fresh_testing(contact_id, campaign_id)

        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Contact {result.get("contact_email", contact_id)} has been completely cleaned and is ready for fresh testing',
                'cleanup_details': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400

    except Exception as e:
        print(f"Deep clean contact error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/<int:campaign_id>/contacts/bulk-clean', methods=['POST'])
@login_required
def bulk_clean_campaign_contacts_route(campaign_id):
    """Clean multiple contacts from campaign for fresh testing"""
    try:
        from utils.contact_cleanup import bulk_clean_campaign_contacts

        data = request.get_json()
        contact_ids = data.get('contact_ids') if data else None  # If None, cleans all contacts

        result = bulk_clean_campaign_contacts(campaign_id, contact_ids)

        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Cleaned {result["contacts_cleaned"]} contacts from campaign {result["campaign_name"]}',
                'results': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400

    except Exception as e:
        print(f"Bulk clean contacts error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/<int:campaign_id>/contacts/available', methods=['GET'])
@login_required
def get_available_contacts(campaign_id):
    """Get contacts that can be added to campaign"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        # Get contacts already in this campaign
        existing_contact_ids = [email.contact_id for email in Email.query.filter_by(campaign_id=campaign_id).all()]
        
        # Get available contacts - show ALL contacts for manual addition
        # This allows manual override of campaign targeting rules
        query = Contact.query

        # For manual addition, we show all contacts regardless of target_risk_levels
        # This gives users flexibility to manually add any contact they want

        # Optional: Filter out bounced contacts as they shouldn't be contacted
        # Uncomment the line below if you want to exclude bounced contacts:
        # query = query.filter(Contact.breach_status != 'bounced')

        # Exclude contacts already in campaign
        if existing_contact_ids:
            query = query.filter(~Contact.id.in_(existing_contact_ids))
        
        available_contacts = query.all()
        
        # Convert to dict for JSON response
        contacts_data = []
        for contact in available_contacts:
            contacts_data.append({
                'id': contact.id,
                'email': contact.email,
                'first_name': contact.first_name or '',
                'last_name': contact.last_name or '',
                'company': contact.company or '',
                'breach_status': contact.breach_status or 'unknown'
            })
        
        return jsonify({
            'success': True,
            'contacts': contacts_data,
            'total_available': len(contacts_data)
        })
        
    except Exception as e:
        print(f"Get available contacts error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/<int:campaign_id>/delete', methods=['POST', 'DELETE'])
@login_required
def delete_campaign(campaign_id):
    """Delete campaign"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        campaign_name = campaign.name
        
        # Delete associated records first (cascade should handle this, but be explicit)
        Email.query.filter_by(campaign_id=campaign_id).delete()
        
        # Delete EmailSequence records (new sequence system)
        from models.database import EmailSequence, ContactCampaignStatus
        EmailSequence.query.filter_by(campaign_id=campaign_id).delete()
        
        # Delete contact campaign status records
        ContactCampaignStatus.query.filter_by(campaign_id=campaign_id).delete()
        
        # Delete the campaign
        db.session.delete(campaign)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Campaign "{campaign_name}" deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Delete campaign error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== CAMPAIGN VARIANT MANAGEMENT ROUTES =====

@campaigns_bp.route('/<int:campaign_id>/variants/create', methods=['POST'])
@login_required
def create_variant(campaign_id):
    """Create a new variant for campaign"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        data = request.get_json()

        # TODO: Update to use TemplateVariant system instead
        # This functionality is now handled by the template variant system
        return jsonify({'success': False, 'error': 'Campaign variants deprecated - use template variants instead'}), 400

        # Legacy code (to be removed):
        # Get next variant letter
        # existing_variants = CampaignVariant.query.filter_by(campaign_id=campaign_id).all()
        # variant_letters = [v.variant_name for v in existing_variants]
        # next_letter = chr(ord('A') + len(variant_letters))

        # Legacy campaign variant functionality deprecated - all functionality moved to template variants
        return jsonify({'success': False, 'error': 'Campaign variants deprecated - use template variants instead'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/<int:campaign_id>/variants/<int:variant_id>/edit', methods=['POST'])
@login_required
def edit_variant(campaign_id, variant_id):
    """Edit campaign variant - deprecated"""
    return jsonify({'success': False, 'error': 'Campaign variants deprecated - use template variants instead'}), 400


@campaigns_bp.route('/<int:campaign_id>/variants/<int:variant_id>/set-default', methods=['POST'])
@login_required
def set_default_variant(campaign_id, variant_id):
    """Set variant as default - deprecated"""
    return jsonify({'success': False, 'error': 'Campaign variants deprecated - use template variants instead'}), 400


# ===== TEMPLATE VARIANT API ENDPOINTS =====

@campaigns_bp.route('/api/template/<int:template_id>/variants')
@login_required
def get_template_variants(template_id):
    """Get all variants for a specific template"""
    try:
        from models.database import TemplateVariant

        variants = TemplateVariant.query.filter_by(
            template_id=template_id,
            is_active=True
        ).order_by(TemplateVariant.is_default.desc(), TemplateVariant.variant_name).all()

        variants_data = []
        for variant in variants:
            variants_data.append({
                'id': variant.id,
                'template_id': variant.template_id,
                'variant_name': variant.variant_name,
                'variant_label': variant.variant_label,
                'subject_line': variant.subject_line,
                'email_body': variant.email_body,
                'email_body_html': variant.email_body_html,
                'is_default': variant.is_default,
                'is_active': variant.is_active,
                'weight': variant.weight,
                'emails_sent': variant.emails_sent,
                'open_rate': variant.open_rate,
                'click_rate': variant.click_rate,
                'response_rate': variant.response_rate
            })

        return jsonify(variants_data)

    except Exception as e:
        current_app.logger.error(f"Error fetching template variants: {str(e)}")
        return jsonify({'error': 'Failed to fetch template variants'}), 500


@campaigns_bp.route('/api/template/variant/<int:variant_id>')
@login_required
def get_template_variant(variant_id):
    """Get details of a specific template variant"""
    try:
        from models.database import TemplateVariant

        variant = TemplateVariant.query.get_or_404(variant_id)

        variant_data = {
            'id': variant.id,
            'template_id': variant.template_id,
            'variant_name': variant.variant_name,
            'variant_label': variant.variant_label,
            'subject_line': variant.subject_line,
            'email_body': variant.email_body,
            'email_body_html': variant.email_body_html,
            'is_default': variant.is_default,
            'is_active': variant.is_active,
            'weight': variant.weight,
            'emails_sent': variant.emails_sent,
            'emails_delivered': variant.emails_delivered,
            'emails_opened': variant.emails_opened,
            'emails_clicked': variant.emails_clicked,
            'emails_replied': variant.emails_replied,
            'open_rate': variant.open_rate,
            'click_rate': variant.click_rate,
            'response_rate': variant.response_rate,
            'created_at': variant.created_at.isoformat() if variant.created_at else None
        }

        return jsonify(variant_data)

    except Exception as e:
        current_app.logger.error(f"Error fetching template variant: {str(e)}")
        return jsonify({'error': 'Failed to fetch template variant'}), 500


# ===== EMAIL APPROVAL MANAGEMENT ROUTES =====

@campaigns_bp.route('/approvals')
@login_required
def pending_approvals():
    """View all emails pending approval"""
    try:
        # Get all emails awaiting approval
        pending_emails = Email.query.filter(
            Email.approval_status == 'awaiting_approval'
        ).join(Campaign).join(Contact).order_by(Email.created_at.desc()).all()

        return render_template('email_approvals.html', pending_emails=pending_emails)

    except Exception as e:
        current_app.logger.error(f"Error fetching pending approvals: {str(e)}")
        flash(f'Error loading approvals: {str(e)}', 'error')
        return redirect(url_for('campaigns.index'))


@campaigns_bp.route('/api/approve-email/<int:email_id>', methods=['POST'])
@login_required
def approve_email(email_id):
    """Approve a specific email for sending"""
    try:
        email = Email.query.get_or_404(email_id)

        # Handle JSON parsing more gracefully
        try:
            data = request.get_json() or {}
        except Exception:
            data = {}  # Fallback to empty dict if JSON parsing fails

        # Update approval status
        email.approval_status = 'approved'
        email.approved_by = 'admin'  # You can get from session in real app
        email.approved_at = datetime.utcnow()
        email.approval_notes = data.get('notes', '')
        email.status = 'approved'  # Change overall status

        db.session.commit()

        # Immediately try to send the approved email
        try:
            from services.email_processor import EmailProcessor
            processor = EmailProcessor()
            result = processor.send_approved_email(email_id)

            if result.get('success'):
                message = f'Email approved and sent to {email.contact.email}'
            else:
                message = f'Email approved but sending failed: {result.get("error", "Unknown error")}'

        except Exception as send_error:
            message = f'Email approved but sending failed: {str(send_error)}'

        return jsonify({
            'success': True,
            'message': message
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error approving email: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/api/reject-email/<int:email_id>', methods=['POST'])
@login_required
def reject_email(email_id):
    """Reject a specific email"""
    try:
        email = Email.query.get_or_404(email_id)
        data = request.get_json() or {}

        # Update approval status
        email.approval_status = 'rejected'
        email.approved_by = 'admin'  # You can get from session in real app
        email.approved_at = datetime.utcnow()
        email.approval_notes = data.get('notes', 'Email rejected')
        email.status = 'rejected'  # Change overall status

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Email rejected for {email.contact.email}'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting email: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/api/batch-approve', methods=['POST'])
@login_required
def batch_approve_emails():
    """Approve multiple emails at once"""
    try:
        data = request.get_json()
        email_ids = data.get('email_ids', [])

        if not email_ids:
            return jsonify({'success': False, 'error': 'No emails selected'}), 400

        # Update all selected emails
        emails = Email.query.filter(Email.id.in_(email_ids)).all()
        approved_count = 0
        sent_count = 0

        for email in emails:
            if email.approval_status == 'awaiting_approval':
                email.approval_status = 'approved'
                email.approved_by = 'admin'
                email.approved_at = datetime.utcnow()
                email.approval_notes = 'Batch approved'
                email.status = 'approved'
                approved_count += 1

        db.session.commit()

        # Try to send approved emails
        try:
            from services.email_processor import EmailProcessor
            processor = EmailProcessor()

            for email_id in email_ids:
                result = processor.send_approved_email(email_id)
                if result.get('success'):
                    sent_count += 1

        except Exception as send_error:
            current_app.logger.error(f"Error in batch sending: {str(send_error)}")

        return jsonify({
            'success': True,
            'message': f'Approved {approved_count} emails, sent {sent_count}'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in batch approval: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/api/email-preview/<int:email_id>', methods=['GET'])
@login_required
def preview_email(email_id):
    """Get full email content for preview"""
    try:
        email = Email.query.get_or_404(email_id)

        # Get email content - body or content field may contain HTML
        email_content = email.body or email.content or 'No content available'

        # Check if content contains HTML tags
        is_html = '<' in email_content and '>' in email_content

        return jsonify({
            'success': True,
            'email': {
                'id': email.id,
                'subject': email.subject,
                'body': email_content if not is_html else None,  # Plain text body
                'html_body': email_content if is_html else None,  # HTML body
                'contact_email': email.contact.email,
                'contact_name': f"{email.contact.first_name or ''} {email.contact.last_name or ''}".strip(),
                'contact_company': email.contact.company or '',
                'campaign_name': email.campaign.name,
                'email_type': email.email_type,
                'status': email.status,
                'approval_status': email.approval_status,
                'created_at': email.created_at.strftime('%Y-%m-%d %H:%M:%S') if email.created_at else None
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error previewing email: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/api/edit-email/<int:email_id>', methods=['POST'])
@login_required
def edit_email(email_id):
    """Edit individual email content before approval"""
    try:
        email = Email.query.get_or_404(email_id)

        # Only allow editing emails that are awaiting approval
        if email.approval_status != 'awaiting_approval':
            return jsonify({'success': False, 'error': 'Email is not awaiting approval'}), 400

        data = request.get_json()
        new_subject = data.get('subject', '').strip()
        new_body = data.get('body', '').strip()

        if not new_subject:
            return jsonify({'success': False, 'error': 'Subject cannot be empty'}), 400

        if not new_body:
            return jsonify({'success': False, 'error': 'Email body cannot be empty'}), 400

        # Update the email content
        email.subject = new_subject
        email.body = new_body
        email.content = new_body  # Keep both fields in sync
        email.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Email updated successfully'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error editing email: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500