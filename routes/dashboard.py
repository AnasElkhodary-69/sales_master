"""
Dashboard and settings routes for SalesBreachPro
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from utils.decorators import login_required
from models.database import Campaign, Settings, get_dashboard_stats, EmailTemplate, Contact, Email, db
from services.email_service import create_email_service
from services.webhook_analytics import create_webhook_analytics_service
from datetime import datetime, timedelta
import re

# Create dashboard blueprint
dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Main dashboard route"""
    try:
        # Get dashboard statistics
        stats = get_dashboard_stats()
        
        # Get active campaigns
        campaigns = Campaign.query.filter_by(status='active').limit(5).all()
        
        # Get hot prospects (placeholder for now)
        hot_prospects = []

        return render_template('dashboard.html', 
                             stats=stats, 
                             campaigns=campaigns,
                             hot_prospects=hot_prospects)
    except Exception as e:
        print(f"Dashboard error: {e}")
        # Return basic dashboard on error with all required fields
        return render_template('dashboard.html', 
                             stats={
                                 'total_contacts': 0,
                                 'active_campaigns': 0,
                                 'emails_this_week': 0,
                                 'responses_this_week': 0,
                                 'response_rate': 0.0,
                                 'hot_leads': 0,
                                 'delivered_count': 0,
                                 'opened_count': 0,
                                 'bounced_count': 0,
                                 'delivery_rate': 0.0,
                                 'open_rate': 0.0,
                                 'bounce_rate': 0.0
                             }, 
                             campaigns=[],
                             hot_prospects=[])


@dashboard_bp.route('/enhanced')
@login_required
def enhanced_dashboard():
    """Enhanced dashboard with sequence flow visualization"""
    try:
        # Get basic stats for compatibility
        stats = get_dashboard_stats()

        # Get campaigns
        campaigns = Campaign.query.order_by(Campaign.created_at.desc()).limit(5).all()

        # Get hot prospects (contacts with recent high engagement)
        hot_prospects = []
        try:
            from services.intelligent_follow_up import create_intelligent_follow_up_service

            # Get recently engaged contacts
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            recent_emails = Email.query.filter(
                or_(
                    Email.opened_at >= recent_cutoff,
                    Email.clicked_at >= recent_cutoff
                )
            ).distinct(Email.contact_id).limit(10).all()

            follow_up_service = create_intelligent_follow_up_service()

            for email in recent_emails:
                contact = Contact.query.get(email.contact_id)
                if contact:
                    engagement = follow_up_service.analyze_contact_engagement(contact.id, days=7)

                    if engagement['engagement_score'] > 30:  # High engagement threshold
                        activity_type = 'clicked' if email.clicked_at else 'opened'
                        activity_time = email.clicked_at or email.opened_at

                        hot_prospects.append({
                            'email': contact.email,
                            'activity': f'{activity_type.title()} email {activity_time.strftime("%m/%d %I:%M %p")}',
                            'engagement_score': engagement['engagement_score'],
                            'contact_id': contact.id
                        })

            # Sort by engagement score
            hot_prospects.sort(key=lambda x: x['engagement_score'], reverse=True)

        except Exception as e:
            print(f"Error loading hot prospects: {e}")
            hot_prospects = []

        return render_template('dashboard_enhanced.html',
                             stats=stats,
                             campaigns=campaigns,
                             hot_prospects=hot_prospects)

    except Exception as e:
        print(f"Enhanced dashboard error: {e}")
        return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/api/intelligent-follow-up')
@login_required
def api_intelligent_follow_up():
    """Process intelligent follow-up recommendations"""
    try:
        from services.intelligent_follow_up import create_intelligent_follow_up_service

        campaign_ids = request.args.get('campaign_ids')
        if campaign_ids:
            campaign_ids = [int(id.strip()) for id in campaign_ids.split(',') if id.strip().isdigit()]

        follow_up_service = create_intelligent_follow_up_service()
        results = follow_up_service.process_intelligent_follow_ups(campaign_ids)

        return jsonify({
            'success': True,
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        print(f"Error processing intelligent follow-up: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to process intelligent follow-up',
            'results': {
                'processed_campaigns': 0,
                'contacts_analyzed': 0,
                'sequences_adjusted': 0,
                'sequences_paused': 0,
                'sequences_accelerated': 0,
                'recommendations': []
            }
        }), 500


@dashboard_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Settings management page"""
    if request.method == 'POST':
        config_type = request.form.get('config_type', 'email_signature')
        
        if config_type == 'email':
            # Handle email configuration
            try:
                brevo_api_key = request.form.get('brevo_api_key', '').strip()
                sender_email = request.form.get('sender_email', '').strip()
                sender_name = request.form.get('sender_name', 'SalesBreachPro Team').strip()
                
                # Save email configuration
                Settings.set_setting('brevo_api_key', brevo_api_key, 'Brevo API key')
                Settings.set_setting('sender_email', sender_email, 'Default sender email')
                Settings.set_setting('sender_name', sender_name, 'Default sender name')
                
                flash('Brevo email configuration updated successfully!', 'success')
            except Exception as e:
                print(f"Email config update error: {e}")
                flash('Error updating email configuration. Please try again.', 'error')
                
        elif config_type == 'imap_reply':
            # Handle IMAP Reply Detection configuration
            try:
                imap_server = request.form.get('imap_server', '').strip()
                reply_email = request.form.get('reply_email', '').strip()
                reply_password = request.form.get('reply_password', '').strip()
                check_interval = request.form.get('check_interval', '15').strip()
                enable_imap = request.form.get('enable_imap') == 'on'
                auto_stop_sequences = request.form.get('auto_stop_sequences') == 'on'
                log_detection = request.form.get('log_detection') == 'on'

                # Save IMAP configuration
                Settings.set_setting('reply_detection_imap_server', imap_server, 'IMAP server for reply detection')
                Settings.set_setting('reply_detection_email', reply_email, 'Email address to monitor for replies')
                Settings.set_setting('reply_detection_password', reply_password, 'Email password for reply detection')
                Settings.set_setting('reply_detection_interval', check_interval, 'Reply check interval in minutes')
                Settings.set_setting('reply_detection_enabled', 'true' if enable_imap else 'false', 'Enable IMAP reply detection')
                Settings.set_setting('reply_detection_auto_stop', 'true' if auto_stop_sequences else 'false', 'Auto-stop sequences on reply')
                Settings.set_setting('reply_detection_logging', 'true' if log_detection else 'false', 'Log reply detection events')

                flash('IMAP Reply Detection configuration updated successfully!', 'success')
            except Exception as e:
                print(f"IMAP config update error: {e}")
                flash('Error updating IMAP configuration. Please try again.', 'error')

        elif config_type == 'test_imap':
            # Handle IMAP connection test
            try:
                imap_server = request.form.get('imap_server', '').strip()
                reply_email = request.form.get('reply_email', '').strip()
                reply_password = request.form.get('reply_password', '').strip()

                if not all([imap_server, reply_email, reply_password]):
                    return jsonify({'success': False, 'error': 'All IMAP fields are required'})

                # Test IMAP connection
                from services.reply_detection_service import create_reply_detection_service
                service = create_reply_detection_service()

                # Temporarily override settings for test
                service.imap_server = imap_server
                service.email_address = reply_email
                service.email_password = reply_password

                test_result = service.check_for_replies()

                if test_result.get('errors', 0) == 0:
                    return jsonify({
                        'success': True,
                        'message': f'IMAP connection successful! Checked {test_result.get("emails_checked", 0)} emails.',
                        'results': test_result
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'IMAP connection failed. Check credentials and server settings.'
                    })

            except Exception as e:
                print(f"IMAP connection test error: {e}")
                return jsonify({'success': False, 'error': str(e)})

        elif config_type == 'webhook':
            # Handle webhook configuration
            try:
                webhook_url = request.form.get('webhook_url', '').strip()
                webhook_secret = request.form.get('webhook_secret', '').strip()

                # Save webhook configuration
                Settings.set_setting('brevo_webhook_url', webhook_url, 'Brevo webhook URL')
                Settings.set_setting('brevo_webhook_secret', webhook_secret, 'Brevo webhook secret')

                flash('Webhook configuration updated successfully!', 'success')
            except Exception as e:
                print(f"Webhook config update error: {e}")
                flash('Error updating webhook configuration. Please try again.', 'error')

        elif config_type == 'setup_webhooks':
            # Handle webhook setup/registration with Brevo
            try:
                from services.webhook_manager import create_webhook_manager

                webhook_manager = create_webhook_manager()
                force_recreate = request.form.get('force_recreate') == 'true'

                results = webhook_manager.setup_webhooks(force_recreate=force_recreate)

                if results['success']:
                    message = f"Webhooks configured successfully! {', '.join(results['messages'])}"
                    return jsonify({'success': True, 'message': message, 'results': results})
                else:
                    error_msg = f"Webhook setup failed: {', '.join(results['errors'])}"
                    return jsonify({'success': False, 'error': error_msg, 'results': results})

            except Exception as e:
                print(f"Webhook setup error: {e}")
                return jsonify({'success': False, 'error': str(e)})

        elif config_type == 'test_webhook':
            # Handle webhook connectivity test
            try:
                from services.webhook_manager import create_webhook_manager

                webhook_manager = create_webhook_manager()
                test_results = webhook_manager.test_webhook_connectivity()

                if test_results['connectivity_test'] == 'success':
                    return jsonify({
                        'success': True,
                        'message': f'Webhook connectivity test passed! Found {test_results["existing_webhooks_count"]} existing webhooks.',
                        'results': test_results
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Webhook connectivity test failed: {", ".join(test_results["errors"])}',
                        'results': test_results
                    })

            except Exception as e:
                print(f"Webhook test error: {e}")
                return jsonify({'success': False, 'error': str(e)})

        elif config_type == 'test_connection':
            # Handle connection test
            try:
                brevo_api_key = request.form.get('brevo_api_key', '').strip()
                sender_email = request.form.get('sender_email', '').strip()
                sender_name = request.form.get('sender_name', 'SalesBreachPro Team').strip()

                if not brevo_api_key:
                    return jsonify({'success': False, 'error': 'Brevo API key is required'})

                # Create test email service
                class TestConfig:
                    BREVO_API_KEY = brevo_api_key
                    DEFAULT_SENDER_EMAIL = sender_email
                    DEFAULT_SENDER_NAME = sender_name

                # Test Brevo API connection
                email_service = create_email_service(TestConfig())
                account_info = email_service.get_account_info()

                if account_info['success']:
                    return jsonify({'success': True, 'message': f'Brevo API connection successful! Account: {account_info["account"]["email"]}'})
                else:
                    return jsonify({'success': False, 'error': f'Brevo API connection failed: {account_info["error"]}'})

            except Exception as e:
                print(f"Connection test error: {e}")
                return jsonify({'success': False, 'error': str(e)})
        else:
            # Handle email signature (existing functionality)
            try:
                email_signature_plain = request.form.get('email_signature', '').strip()
                email_signature_html = request.form.get('email_signature_html', '').strip()
                
                if email_signature_plain:
                    # Store both versions
                    Settings.set_setting('email_signature_plain', email_signature_plain, 'Plain text email signature')
                    Settings.set_setting('email_signature', email_signature_html, 'HTML email signature for templates')
                    flash('Email signature updated successfully!', 'success')
                else:
                    flash('Email signature cannot be empty.', 'error')
            except Exception as e:
                print(f"Settings update error: {e}")
                flash('Error updating settings. Please try again.', 'error')
        
        return redirect(url_for('dashboard.settings'))
    
    # GET request - show settings form
    try:
        current_signature_html = Settings.get_setting('email_signature', 'Best regards,<br>SalesBreachPro Team')
        current_signature_plain = Settings.get_setting('email_signature_plain', 'Best regards,\nSalesBreachPro Team')
        
        # Get email configuration
        email_config = {
            'brevo_api_key': Settings.get_setting('brevo_api_key', ''),
            'sender_email': Settings.get_setting('sender_email', ''),
            'sender_name': Settings.get_setting('sender_name', 'SalesBreachPro Team')
        }

        # Get webhook configuration
        webhook_config = {
            'webhook_url': Settings.get_setting('brevo_webhook_url', 'http://localhost:5000/webhooks/brevo'),
            'webhook_secret': Settings.get_setting('brevo_webhook_secret', ''),
            'webhook_configured': bool(Settings.get_setting('brevo_webhook_url', ''))
        }

        # Get IMAP configuration
        imap_config = {
            'imap_server': Settings.get_setting('reply_detection_imap_server', 'imap.gmail.com'),
            'reply_email': Settings.get_setting('reply_detection_email', ''),
            'reply_password': Settings.get_setting('reply_detection_password', ''),
            'check_interval': Settings.get_setting('reply_detection_interval', '15'),
            'enabled': Settings.get_setting('reply_detection_enabled', 'false'),
            'auto_stop': Settings.get_setting('reply_detection_auto_stop', 'true'),
            'log_detection': Settings.get_setting('reply_detection_logging', 'true')
        }

        # Get existing webhooks for display
        existing_webhooks = []
        try:
            from services.webhook_manager import create_webhook_manager
            webhook_manager = create_webhook_manager()
            existing_webhooks = webhook_manager.list_existing_webhooks()
        except Exception as e:
            print(f"Error loading existing webhooks: {e}")

        return render_template('settings.html',
                             email_signature=current_signature_html,
                             email_signature_plain=current_signature_plain,
                             email_config=email_config,
                             webhook_config=webhook_config,
                             imap_config=imap_config,
                             existing_webhooks=existing_webhooks)
    except Exception as e:
        print(f"Settings error: {e}")
        return render_template('settings.html',
                             email_signature='Best regards,<br>SalesBreachPro Team',
                             email_signature_plain='Best regards,\nSalesBreachPro Team',
                             email_config={
                                 'brevo_api_key': '',
                                 'sender_email': '',
                                 'sender_name': 'SalesBreachPro Team'
                             },
                             webhook_config={
                                 'webhook_url': 'http://localhost:5000/webhooks/brevo',
                                 'webhook_secret': '',
                                 'webhook_configured': False
                             },
                             imap_config={
                                 'imap_server': 'imap.gmail.com',
                                 'reply_email': '',
                                 'reply_password': '',
                                 'check_interval': '15',
                                 'enabled': 'false',
                                 'auto_stop': 'true',
                                 'log_detection': 'true'
                             },
                             existing_webhooks=[])


@dashboard_bp.route('/api/sequence-analytics')
@login_required
def api_sequence_analytics():
    """Get detailed sequence analytics for dashboard"""
    try:
        from services.sequence_analytics import create_sequence_analytics_service

        analytics_service = create_sequence_analytics_service()

        # Get overall performance summary
        performance_summary = analytics_service.get_sequence_performance_summary()

        # Get active sequences with tracking
        active_sequences = analytics_service.get_active_sequences_with_tracking()

        # Get real-time updates
        real_time_updates = analytics_service.get_real_time_sequence_updates()

        return jsonify({
            'success': True,
            'performance_summary': performance_summary,
            'active_sequences': active_sequences,
            'real_time_updates': real_time_updates,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        print(f"Error getting sequence analytics: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get sequence analytics',
            'performance_summary': {
                'total_sequences': 0,
                'completed_sequences': 0,
                'completion_rate': 0,
                'emails_sent': 0,
                'engagement_metrics': {
                    'opens': 0, 'clicks': 0, 'replies': 0, 'bounces': 0,
                    'open_rate': 0, 'click_rate': 0, 'reply_rate': 0, 'bounce_rate': 0
                }
            },
            'active_sequences': [],
            'real_time_updates': {
                'recently_sent': 0, 'upcoming_scheduled': 0, 'recently_stopped': 0, 'active_sequences': 0
            }
        }), 500


@dashboard_bp.route('/api/sequence-flow/<int:campaign_id>')
@login_required
def api_sequence_flow(campaign_id):
    """Get sequence flow visualization data"""
    try:
        from services.sequence_analytics import create_sequence_analytics_service

        analytics_service = create_sequence_analytics_service()
        flow_data = analytics_service.get_sequence_flow_visualization(campaign_id)

        return jsonify({
            'success': True,
            'flow_data': flow_data
        })

    except Exception as e:
        print(f"Error getting sequence flow: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get sequence flow data'
        }), 500


@dashboard_bp.route('/api/contact-journey/<int:contact_id>')
@login_required
def api_contact_journey(contact_id):
    """Get detailed contact sequence journey"""
    try:
        from services.sequence_analytics import create_sequence_analytics_service

        analytics_service = create_sequence_analytics_service()
        journey = analytics_service.get_contact_sequence_journey(contact_id)

        return jsonify({
            'success': True,
            'journey': journey
        })

    except Exception as e:
        print(f"Error getting contact journey: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get contact journey'
        }), 500


@dashboard_bp.route('/api/stats')
def api_stats():
    """API endpoint for real-time dashboard statistics"""
    try:
        # Get basic stats
        stats = get_dashboard_stats()
        
        # Add advanced analytics
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Get recent email performance (avoid column issues in new database)
        try:
            recent_emails = Email.query.filter(Email.sent_at >= week_ago).all()
        except Exception as e:
            print(f"Email query error (using fallback): {e}")
            recent_emails = Email.query.all()  # Get all emails as fallback
        
        advanced_stats = {
            'recent_performance': {
                'emails_sent_week': len([e for e in recent_emails if e.sent_at]),
                'emails_opened_week': len([e for e in recent_emails if e.opened_at]),
                'emails_clicked_week': len([e for e in recent_emails if e.clicked_at]),
                'emails_bounced_week': len([e for e in recent_emails if e.bounced_at])
            },
            'behavioral_triggers': {
                'active_sequences': 0,  # Would track automation sequences
                'triggers_fired_week': 0,  # Would track behavioral triggers
                'follow_ups_scheduled': 0  # Would track scheduled follow-ups
            },
            'industry_breakdown': {},  # Would break down by industry
            'risk_level_distribution': {}  # Would show risk level stats
        }
        
        # Get industry breakdown
        try:
            industry_stats = db.session.query(
                Contact.industry,
                db.func.count(Contact.id).label('count')
            ).group_by(Contact.industry).all()

            for industry, count in industry_stats:
                advanced_stats['industry_breakdown'][industry or 'Unknown'] = count
        except Exception as e:
            print(f"Industry stats error: {e}")
            advanced_stats['industry_breakdown'] = {}

        # Business type distribution (replacing risk level)
        try:
            business_stats = db.session.query(
                Contact.business_type,
                db.func.count(Contact.id).label('count')
            ).group_by(Contact.business_type).all()

            for business_type, count in business_stats:
                advanced_stats['business_type_distribution'] = advanced_stats.get('business_type_distribution', {})
                advanced_stats['business_type_distribution'][business_type or 'Unknown'] = count
        except Exception as e:
            print(f"Business type stats error: {e}")
            advanced_stats['business_type_distribution'] = {}
        
        # Get enhanced webhook-based analytics
        try:
            analytics_service = create_webhook_analytics_service()
            webhook_analytics = analytics_service.get_email_analytics(days=30)
            
            # Add webhook analytics to advanced stats
            advanced_stats['webhook_analytics'] = {
                'enhanced_open_rate': webhook_analytics.get('open_rate', 0),
                'enhanced_click_rate': webhook_analytics.get('click_rate', 0),
                'enhanced_reply_rate': webhook_analytics.get('reply_rate', 0),
                'enhanced_bounce_rate': webhook_analytics.get('bounce_rate', 0),
                'total_webhook_events': sum(webhook_analytics.get('event_breakdown', {}).values()),
                'event_breakdown': webhook_analytics.get('event_breakdown', {}),
                'period_days': 30
            }
        except Exception as e:
            print(f"Webhook analytics error: {e}")
            advanced_stats['webhook_analytics'] = {
                'enhanced_open_rate': 0,
                'enhanced_click_rate': 0,
                'enhanced_reply_rate': 0,
                'enhanced_bounce_rate': 0,
                'total_webhook_events': 0,
                'event_breakdown': {},
                'period_days': 30
            }
        
        # Combine with basic stats
        stats.update(advanced_stats)
        
        return jsonify(stats)
        
    except Exception as e:
        print(f"API stats error: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/webhook-dashboard-stats')
@login_required
def api_webhook_dashboard_stats():
    """Get comprehensive webhook-based statistics for dashboard"""
    try:
        analytics_service = create_webhook_analytics_service()
        
        # Get analytics for different periods
        analytics_7d = analytics_service.get_email_analytics(days=7)
        analytics_30d = analytics_service.get_email_analytics(days=30)
        daily_analytics = analytics_service.get_daily_analytics(days=7)
        top_links = analytics_service.get_top_clicked_links(days=30, limit=5)
        
        return jsonify({
            'last_7_days': analytics_7d,
            'last_30_days': analytics_30d,
            'daily_breakdown': daily_analytics,
            'top_clicked_links': top_links,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        print(f"Error getting webhook dashboard stats: {e}")
        return jsonify({'error': 'Failed to fetch webhook analytics'}), 500

@dashboard_bp.route('/analytics')
@login_required
def analytics():
    """Advanced analytics dashboard"""
    try:
        # Basic automation stats (breach automation removed)
        automation_stats = {'automation_metrics': {}}
        
        # Get campaign performance over time
        campaigns = Campaign.query.filter(
            Campaign.created_at >= datetime.utcnow() - timedelta(days=30)
        ).all()
        
        # Get email performance trends
        emails_by_day = db.session.query(
            db.func.date(Email.sent_at).label('date'),
            db.func.count(Email.id).label('sent'),
            db.func.count(Email.opened_at).label('opened'),
            db.func.count(Email.clicked_at).label('clicked')
        ).filter(
            Email.sent_at >= datetime.utcnow() - timedelta(days=30)
        ).group_by(db.func.date(Email.sent_at)).all()
        
        return render_template('analytics.html',
                             automation_stats=automation_stats,
                             campaigns=campaigns,
                             email_trends=emails_by_day)
        
    except Exception as e:
        print(f"Analytics error: {e}")
        return render_template('analytics.html',
                             automation_stats={'automation_metrics': {}},
                             campaigns=[],
                             email_trends=[])


@dashboard_bp.route('/api/automation-status')
def automation_status():
    """Get current automation system status"""
    try:
        status = {
            'brevo_service': 'unknown',
            'automation_service': 'unknown',
            'auto_enrollment': 'unknown',
            'webhooks': 'unknown'
        }
        
        # Test Brevo service
        try:
            brevo_api_key = Settings.get_setting('brevo_api_key', '')
            if brevo_api_key:
                class TestConfig:
                    BREVO_API_KEY = brevo_api_key
                    DEFAULT_SENDER_EMAIL = Settings.get_setting('sender_email', '')
                    DEFAULT_SENDER_NAME = Settings.get_setting('sender_name', '')
                
                email_service = create_email_service(TestConfig())
                account_info = email_service.get_account_info()
                status['brevo_service'] = 'active' if account_info['success'] else 'error'
            else:
                status['brevo_service'] = 'not_configured'
        except Exception:
            status['brevo_service'] = 'error'
        
        # Automation service status (breach automation removed)
        status['automation_service'] = 'removed'
        
        # Test auto-enrollment
        try:
            from services.auto_enrollment import create_auto_enrollment_service
            auto_service = create_auto_enrollment_service(db)
            status['auto_enrollment'] = 'active'
        except Exception:
            status['auto_enrollment'] = 'error'
        
        # Check webhook endpoints
        status['webhooks'] = 'active'  # Assume active if routes are registered
        
        return jsonify(status)
        
    except Exception as e:
        print(f"Automation status error: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/test-email', methods=['GET', 'POST'])
@login_required
def test_email():
    """Test email sending functionality"""
    if request.method == 'POST':
        try:
            # Get form data
            recipient_email = request.form.get('recipient_email')
            template_id = request.form.get('template_id')
            sender_name = request.form.get('sender_name', 'SalesBreachPro Team')
            sender_email = request.form.get('sender_email', 'test@salesbreachpro.com')
            
            # Validate email
            if not recipient_email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', recipient_email):
                return jsonify({'success': False, 'error': 'Invalid recipient email address'})
            
            # Get template
            template = None
            if template_id:
                template = EmailTemplate.query.get(template_id)
            
            if not template:
                # Use default test template
                subject = "Test Email from SalesBreachPro"
                content = """
                <h2>Test Email</h2>
                <p>This is a test email from your SalesBreachPro system.</p>
                <p>If you received this email, your email configuration is working correctly!</p>
                <br>
                <p>Best regards,<br>
                {sender_name}</p>
                """.format(sender_name=sender_name)
            else:
                # Use selected template with sample data
                subject = template.subject_line or "Test Email"
                content = template.email_body_html or template.email_body or "Test email content"
                
                # Replace template variables with sample data
                sample_contact = Contact.query.first()
                if sample_contact:
                    content = content.replace('{{name}}', sample_contact.first_name or 'John')
                    content = content.replace('{{company}}', sample_contact.company or 'Test Company')
                    content = content.replace('{{email}}', sample_contact.email or recipient_email)
                else:
                    content = content.replace('{{name}}', 'John')
                    content = content.replace('{{company}}', 'Test Company')
                    content = content.replace('{{email}}', recipient_email)
            
            # Send actual email using the email service
            try:
                # Get email configuration from settings
                brevo_api_key = Settings.get_setting('brevo_api_key', '')
                
                # Create email config from settings
                class EmailConfig:
                    BREVO_API_KEY = brevo_api_key
                    DEFAULT_SENDER_EMAIL = sender_email
                    DEFAULT_SENDER_NAME = sender_name
                
                email_service = create_email_service(EmailConfig())
                
                # Send the email
                success, message = email_service.send_single_email(
                    to_email=recipient_email,
                    subject=subject,
                    html_content=content,
                    from_email=sender_email,
                    from_name=sender_name
                )
                
                if success:
                    return jsonify({
                        'success': True, 
                        'message': f'Test email sent successfully to {recipient_email}!',
                        'details': {
                            'sender': f'{sender_name} <{sender_email}>',
                            'recipient': recipient_email,
                            'subject': subject
                        }
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to send email: {message}'
                    })
                    
            except Exception as e:
                # Fallback to simulation if email service fails
                print(f"EMAIL SERVICE ERROR: {e}")
                print(f"FALLBACK - TEST EMAIL SIMULATED:")
                print(f"From: {sender_name} <{sender_email}>")
                print(f"To: {recipient_email}")
                print(f"Subject: {subject}")
                print(f"Content: {content}")
                
                return jsonify({
                    'success': True, 
                    'message': f'Test email simulated (email service not configured). Check console for details.',
                    'details': {
                        'sender': f'{sender_name} <{sender_email}>',
                        'recipient': recipient_email,
                        'subject': subject,
                        'note': 'Email was simulated - configure SMTP to send real emails'
                    }
                })
            
        except Exception as e:
            print(f"Test email error: {e}")
            return jsonify({'success': False, 'error': f'Error sending test email: {str(e)}'})
    
    # GET request - show test email form
    try:
        # Get available templates
        templates = EmailTemplate.query.filter_by(active=True).all()
        
        # If no templates, use demo templates
        if not templates:
            demo_templates = [
                {
                    'id': 'demo_1',
                    'name': 'Breach Response Template',
                    'subject_line': 'URGENT: Your data may have been compromised',
                    'template_type': 'breached'
                },
                {
                    'id': 'demo_2', 
                    'name': 'Security Assessment Template',
                    'subject_line': 'Free Security Assessment for {{company}}',
                    'template_type': 'unknown'
                },
                {
                    'id': 'demo_3',
                    'name': 'Proactive Security Template', 
                    'subject_line': 'Strengthen Your Security - {{company}}',
                    'template_type': 'secure'
                }
            ]
            templates = demo_templates
        
        return render_template('test_email.html', templates=templates)
        
    except Exception as e:
        print(f"Test email page error: {e}")
        return render_template('test_email.html', templates=[])