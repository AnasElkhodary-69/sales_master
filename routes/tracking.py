"""
Email tracking routes for SalesBreachPro
Handles email opens, clicks, unsubscribes, and webhook processing
"""
import json
import urllib.parse
from datetime import datetime
from flask import Blueprint, Response, redirect, request, render_template_string
from models.database import db, Email, Contact

# Create tracking blueprint
tracking_bp = Blueprint('tracking', __name__)


@tracking_bp.route('/track/open/<int:email_id>')
def track_email_open(email_id):
    """Track email opens via 1x1 pixel"""
    try:
        # Find email and update open status
        email = Email.query.get(email_id)
        if email and not email.opened_at:
            email.opened_at = datetime.utcnow()
            email.status = 'delivered'  # Mark as delivered if it was opened
            db.session.commit()
            
            # Check for behavioral triggers
            try:
                from services.breach_email_automation import create_breach_automation_service
                automation_service = create_breach_automation_service()
                
                # Check if this is multiple opens (3 or more)
                open_count = Email.query.filter_by(contact_id=email.contact_id).filter(Email.opened_at.isnot(None)).count()
                if open_count >= 3:
                    result = automation_service.process_behavioral_trigger(email_id, 'multiple_opens')
                    print(f"Multiple opens trigger: {result}")
                
                # Schedule background check for "opened but no click" trigger
                # This will be processed by the scheduler after 4 hours
                from datetime import datetime, timedelta
                trigger_time = datetime.utcnow() + timedelta(hours=4)
                
                # Log for potential background processing
                print(f"Email {email_id} opened - scheduling no-click check for {trigger_time}")
                
            except Exception as e:
                print(f"Error processing behavioral trigger: {e}")
        
        # Return 1x1 transparent pixel
        pixel_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        response = Response(pixel_data, mimetype='image/gif')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
        
    except Exception as e:
        print(f"Error tracking email open: {e}")
        # Return pixel anyway to avoid broken images
        pixel_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        return Response(pixel_data, mimetype='image/gif')


@tracking_bp.route('/track/click/<int:email_id>/<path:url>')
def track_email_click(email_id, url):
    """Track email clicks and redirect"""
    try:
        # Find email and update click status
        email = Email.query.get(email_id)
        if email:
            if not email.clicked_at:
                email.clicked_at = datetime.utcnow()
            if not email.opened_at:
                email.opened_at = datetime.utcnow()
            email.status = 'delivered'
            db.session.commit()
            
            # Process click behavioral trigger
            try:
                from services.breach_email_automation import create_breach_automation_service
                from datetime import datetime, timedelta
                automation_service = create_breach_automation_service()
                
                # Contact clicked - check for immediate response triggers
                contact = Contact.query.get(email.contact_id)
                if contact:
                    # High-value prospects get immediate priority follow-up
                    if contact.breach_status == 'high' or (contact.industry and contact.industry.lower() in ['healthcare', 'finance']):
                        result = automation_service.process_behavioral_trigger(email_id, 'clicked_no_response')
                        print(f"High-priority click trigger: {result}")
                    
                    # Schedule background check for "clicked but no response" after 48 hours
                    trigger_time = datetime.utcnow() + timedelta(hours=48)
                    print(f"Email {email_id} clicked - scheduling no-response check for {trigger_time}")
                
            except Exception as e:
                print(f"Error processing click trigger: {e}")
        
        # Decode and redirect to original URL
        decoded_url = urllib.parse.unquote(url)
        if not decoded_url.startswith(('http://', 'https://')):
            decoded_url = 'https://' + decoded_url
            
        return redirect(decoded_url)
        
    except Exception as e:
        print(f"Error tracking email click: {e}")
        # Fallback redirect
        return redirect('https://example.com')


@tracking_bp.route('/unsubscribe/<int:contact_id>')
def unsubscribe(contact_id):
    """Handle unsubscribe requests"""
    try:
        contact = Contact.query.get(contact_id)
        if contact:
            contact.unsubscribed = True
            contact.unsubscribed_at = datetime.utcnow()
            db.session.commit()
            
            return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Unsubscribed - SalesBreachPro</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            </head>
            <body>
                <div class="container mt-5">
                    <div class="row justify-content-center">
                        <div class="col-md-6 text-center">
                            <h2 class="text-success">✓ Successfully Unsubscribed</h2>
                            <p>You have been removed from our mailing list.</p>
                            <p class="text-muted">Email: {{ contact.email }}</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """, contact=contact)
        else:
            return "Contact not found", 404
            
    except Exception as e:
        print(f"Error processing unsubscribe: {e}")
        return "Error processing request", 500


@tracking_bp.route('/webhook/ses', methods=['POST'])
def ses_webhook():
    """Handle AWS SES SNS notifications for bounces, complaints, deliveries"""
    try:
        data = request.get_json()
        
        # Handle SNS subscription confirmation
        if data and data.get('Type') == 'SubscriptionConfirmation':
            # In production, you would confirm the subscription
            print("SNS Subscription confirmation received")
            return "OK"
        
        # Handle SNS notification
        if data and data.get('Type') == 'Notification':
            message = json.loads(data.get('Message', '{}'))
            
            # Extract email information
            if 'mail' in message:
                message_id = message['mail'].get('messageId')
                destination = message['mail'].get('destination', [])
                
                # Find email by message ID (you'd need to store this when sending)
                # For now, find by recipient email
                if destination:
                    recipient_email = destination[0]
                    email = Email.query.join(Contact).filter(Contact.email == recipient_email).order_by(Email.sent_at.desc()).first()
                    
                    if email:
                        # Handle bounce
                        if message.get('bounce'):
                            email.status = 'bounced'
                            email.bounced_at = datetime.utcnow()
                            bounce_type = message['bounce'].get('bounceType', 'unknown')
                            print(f"Email {email.id} bounced: {bounce_type}")
                        
                        # Handle complaint
                        elif message.get('complaint'):
                            email.status = 'complained'
                            email.complained_at = datetime.utcnow()
                            print(f"Email {email.id} complained")
                        
                        # Handle delivery
                        elif message.get('delivery'):
                            if email.status != 'delivered':
                                email.status = 'delivered'
                                email.delivered_at = datetime.utcnow()
                                print(f"Email {email.id} delivered")
                        
                        db.session.commit()
        
        return "OK"
        
    except Exception as e:
        print(f"Error processing SES webhook: {e}")
        return "Error", 500


@tracking_bp.route('/webhook/brevo', methods=['POST'])
def brevo_webhook():
    """Handle Brevo webhooks for advanced email tracking"""
    try:
        data = request.get_json()
        
        if not data:
            return "No data", 400
        
        event_type = data.get('event')
        email = data.get('email')
        message_id = data.get('message-id')
        
        print(f"Brevo webhook: {event_type} for {email}")
        
        if event_type and email:
            # Find the email record by recipient and message ID
            email_record = None
            
            # Try to find by Brevo message ID first (temporarily disabled due to database compatibility)
            # if message_id:
            #     try:
            #         email_record = Email.query.filter_by(brevo_message_id=message_id).first()
            #     except Exception as e:
            #         print(f"Brevo message ID query failed (using fallback): {e}")
            #         email_record = None
            
            # Fallback: find by recipient email (latest)
            if not email_record:
                contact = Contact.query.filter_by(email=email).first()
                if contact:
                    email_record = Email.query.filter_by(contact_id=contact.id).order_by(Email.sent_at.desc()).first()
            
            if email_record:
                # Update email status based on event
                if event_type == 'delivered':
                    email_record.delivered_at = datetime.utcnow()
                    email_record.status = 'delivered'
                elif event_type == 'opened':
                    if not email_record.opened_at:
                        email_record.opened_at = datetime.utcnow()
                        email_record.status = 'opened'
                        
                        # Process behavioral triggers for opens
                        try:
                            from services.breach_email_automation import create_breach_automation_service
                            automation_service = create_breach_automation_service()
                            
                            # Check for multiple opens (3 or more across all campaigns)
                            open_count = Email.query.filter_by(contact_id=email_record.contact_id).filter(Email.opened_at.isnot(None)).count()
                            if open_count >= 3:
                                result = automation_service.process_behavioral_trigger(email_record.id, 'multiple_opens')
                                print(f"Brevo webhook - Multiple opens trigger: {result}")
                            
                            # Check for high-engagement patterns (opened within 5 minutes)
                            email_age = (datetime.utcnow() - email_record.sent_at).total_seconds() / 60 if email_record.sent_at else 999
                            if email_age < 5:  # Opened within 5 minutes
                                result = automation_service.process_behavioral_trigger(email_record.id, 'immediate_open')
                                print(f"Brevo webhook - Immediate open trigger: {result}")
                                
                        except Exception as e:
                            print(f"Error processing open trigger: {e}")
                            
                elif event_type == 'click':
                    if not email_record.clicked_at:
                        email_record.clicked_at = datetime.utcnow()
                        email_record.status = 'clicked'
                        
                        # Process click behavioral triggers
                        try:
                            from services.breach_email_automation import create_breach_automation_service
                            automation_service = create_breach_automation_service()
                            
                            # Get contact for trigger decisions
                            contact = Contact.query.get(email_record.contact_id)
                            if contact:
                                # High-value prospects get priority follow-up
                                if (contact.breach_status == 'high' or 
                                    (contact.industry and contact.industry.lower() in ['healthcare', 'finance', 'government'])):
                                    result = automation_service.process_behavioral_trigger(email_record.id, 'clicked_no_response')
                                    print(f"Brevo webhook - High-priority click trigger: {result}")
                                
                                # Check for immediate clicks (within 2 minutes)
                                email_age = (datetime.utcnow() - email_record.sent_at).total_seconds() / 60 if email_record.sent_at else 999
                                if email_age < 2:  # Clicked within 2 minutes
                                    result = automation_service.process_behavioral_trigger(email_record.id, 'immediate_click')
                                    print(f"Brevo webhook - Immediate click trigger: {result}")
                                    
                        except Exception as e:
                            print(f"Error processing click trigger: {e}")
                elif event_type == 'bounce':
                    email_record.bounced_at = datetime.utcnow()
                    email_record.status = 'bounced'
                elif event_type == 'spam':
                    email_record.complained_at = datetime.utcnow()
                    email_record.status = 'complained'
                elif event_type == 'unsubscribe':
                    # Update contact unsubscribe status
                    contact = Contact.query.get(email_record.contact_id)
                    if contact:
                        contact.unsubscribed = True
                        contact.unsubscribed_at = datetime.utcnow()
                
                db.session.commit()
                print(f"Updated email {email_record.id} with {event_type} event")
        
        return "OK"
        
    except Exception as e:
        print(f"Error processing Brevo webhook: {e}")
        return "Error", 500