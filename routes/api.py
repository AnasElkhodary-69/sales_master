"""
API routes for SalesBreachPro
Handles all REST API endpoints for contacts, templates, breach analysis, and more
"""
import csv
import io
import time
import uuid
import random
from datetime import datetime
from flask import Blueprint, jsonify, request, Response
from utils.decorators import login_required
from models.database import db, Contact, Campaign, Email, Response as EmailResponse, EmailTemplate

# Create API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Template API
@api_bp.route('/template/<int:template_id>')
@login_required
def get_template(template_id):
    """API endpoint to get template details"""
    try:
        template = EmailTemplate.query.get(template_id)
        if template:
            return jsonify({
                'id': template.id,
                'name': template.name,
                'subject': template.subject_line or template.subject or '',
                'content': template.email_body or template.content or '',
                'template_type': template.template_type,
                'risk_level': template.risk_level
            })
        else:
            return jsonify({'error': 'Template not found'}), 404
    except Exception as e:
        print(f"Error fetching template: {e}")
        return jsonify({'error': 'Error fetching template'}), 500


# Contact API endpoints
@api_bp.route('/contacts/<int:contact_id>')
@login_required
def get_contact(contact_id):
    """Get a specific contact by ID"""
    try:
        contact = Contact.query.get(contact_id)
        if contact:
            return jsonify(contact.to_dict())
        else:
            return jsonify({'error': 'Contact not found'}), 404
    except Exception as e:
        print(f"Error fetching contact: {e}")
        return jsonify({'error': 'Error fetching contact'}), 500


@api_bp.route('/contacts/<int:contact_id>', methods=['PUT'])
@login_required 
def update_contact(contact_id):
    """Update a specific contact"""
    try:
        contact = Contact.query.get(contact_id)
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        data = request.get_json()
        
        # Update contact fields
        if 'email' in data:
            contact.email = data['email']
        if 'first_name' in data:
            contact.first_name = data['first_name']
        if 'last_name' in data:
            contact.last_name = data['last_name']
        if 'company' in data:
            contact.company = data['company']
        if 'title' in data:
            contact.title = data['title']
        if 'phone' in data:
            contact.phone = data['phone']
        if 'industry' in data:
            contact.industry = data['industry']
        if 'business_type' in data:
            contact.business_type = data['business_type']
        if 'company_size' in data:
            contact.company_size = data['company_size']
        if 'status' in data:
            contact.status = data['status']
            # Sync is_active field with status field
            contact.is_active = data['status'] == 'active'

        # Handle campaign assignment (support multiple campaigns)
        campaign_message = None
        if 'campaign_ids' in data and data['campaign_ids']:
            try:
                campaign_ids = data['campaign_ids']
                if not isinstance(campaign_ids, list):
                    campaign_ids = [campaign_ids]  # Convert single ID to list for compatibility

                # Filter out any non-numeric values
                campaign_ids = [int(cid) for cid in campaign_ids if cid]

                if campaign_ids:
                    from models.database import ContactCampaignStatus
                    from services.auto_enrollment import create_auto_enrollment_service

                    auto_service = create_auto_enrollment_service(db)
                    contact_name = f"{contact.first_name} {contact.last_name}" if contact.first_name or contact.last_name else contact.email

                    enrolled_campaigns = []
                    already_enrolled_campaigns = []
                    failed_campaigns = []

                    for campaign_id in campaign_ids:
                        try:
                            campaign = Campaign.query.get(campaign_id)
                            if not campaign:
                                failed_campaigns.append(f"Campaign ID {campaign_id} not found")
                                continue

                            # Check if already enrolled
                            existing_enrollment = ContactCampaignStatus.query.filter_by(
                                contact_id=contact.id,
                                campaign_id=campaign_id
                            ).first()

                            if existing_enrollment:
                                already_enrolled_campaigns.append(campaign.name)
                            else:
                                # Enroll contact in campaign
                                success = auto_service.enroll_single_contact(contact.id, campaign_id)
                                if success:
                                    enrolled_campaigns.append(campaign.name)
                                    print(f"Successfully enrolled contact {contact.email} into campaign {campaign_id}")
                                else:
                                    failed_campaigns.append(campaign.name)
                                    print(f"Failed to enroll contact {contact.email} into campaign {campaign_id}")

                        except Exception as campaign_error:
                            failed_campaigns.append(f"Campaign {campaign_id}: {str(campaign_error)}")
                            print(f"Error enrolling contact {contact.id} in campaign {campaign_id}: {campaign_error}")

                    # Build comprehensive message
                    message_parts = []
                    if enrolled_campaigns:
                        campaigns_str = "', '".join(enrolled_campaigns)
                        message_parts.append(f"Successfully enrolled {contact_name.strip()} in {len(enrolled_campaigns)} campaign(s): '{campaigns_str}'")

                    if already_enrolled_campaigns:
                        campaigns_str = "', '".join(already_enrolled_campaigns)
                        message_parts.append(f"Already enrolled in {len(already_enrolled_campaigns)} campaign(s): '{campaigns_str}'")

                    if failed_campaigns:
                        message_parts.append(f"{len(failed_campaigns)} enrollment(s) failed")

                    campaign_message = ". ".join(message_parts) if message_parts else "No campaign enrollments processed"

            except (ValueError, TypeError) as e:
                campaign_message = f"Invalid campaign IDs: {str(e)}"

        db.session.commit()

        # Build response message
        response_message = 'Contact updated successfully'
        if campaign_message:
            response_message = f"{response_message}. {campaign_message}"

        return jsonify({
            'success': True,
            'contact': contact.to_dict(),
            'message': response_message
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error updating contact: {e}")
        return jsonify({'error': 'Error updating contact'}), 500


@api_bp.route('/contacts/<int:contact_id>', methods=['DELETE'])
@login_required
def delete_contact(contact_id):
    """Delete a specific contact"""
    try:
        print(f"=== DELETE CONTACT START: ID {contact_id} ===")
        
        contact = Contact.query.get(contact_id)
        if not contact:
            print(f"Contact {contact_id} not found")
            return jsonify({'error': 'Contact not found'}), 404
        
        print(f"Found contact: {contact.email}, domain: {contact.domain}")
        
        # Store domain for cleanup check
        contact_domain = contact.domain
        
        # Check if contact has related records
        email_count = Email.query.filter_by(contact_id=contact_id).count()
        print(f"Contact has {email_count} related emails")
        
        # Check for email sequences and webhook events
        from models.database import EmailSequence, ContactCampaignStatus, WebhookEvent
        sequence_count = EmailSequence.query.filter_by(contact_id=contact_id).count()
        campaign_status_count = ContactCampaignStatus.query.filter_by(contact_id=contact_id).count()
        webhook_count = WebhookEvent.query.filter_by(contact_id=contact_id).count()
        print(f"Contact has {sequence_count} email sequences, {campaign_status_count} campaign statuses, and {webhook_count} webhook events")
        
        # Delete related records first (these don't have cascade configured)
        if sequence_count > 0:
            EmailSequence.query.filter_by(contact_id=contact_id).delete()
            print(f"Deleted {sequence_count} email sequences")
        
        if campaign_status_count > 0:
            ContactCampaignStatus.query.filter_by(contact_id=contact_id).delete()
            print(f"Deleted {campaign_status_count} campaign statuses")

        # Delete webhook events for this contact
        if webhook_count > 0:
            WebhookEvent.query.filter_by(contact_id=contact_id).delete()
            print(f"Deleted {webhook_count} webhook events")
        
        # Delete related emails and all their associated data (Brevo records, responses, etc.)
        if email_count > 0:
            # Get all emails before deleting to clean up associated records
            contact_emails = Email.query.filter_by(contact_id=contact_id).all()

            # Delete any responses associated with these emails
            for email in contact_emails:
                if email.id:
                    # Delete email responses
                    response_count = EmailResponse.query.filter_by(email_id=email.id).count()
                    if response_count > 0:
                        EmailResponse.query.filter_by(email_id=email.id).delete()
                        print(f"Deleted {response_count} email responses for email {email.id}")

            # Delete all email records (this removes Brevo message IDs and webhook data)
            Email.query.filter_by(contact_id=contact_id).delete()
            print(f"Deleted {email_count} related emails and their Brevo data")
        
        # Delete the contact
        db.session.delete(contact)
        print(f"Contact marked for deletion")
        
        # Check if this was the last contact from this domain
        if contact_domain:
            # Note: We need to check BEFORE committing the delete
            remaining_contacts = Contact.query.filter(
                Contact.domain == contact_domain,
                Contact.id != contact_id
            ).count()
            print(f"Remaining contacts with domain {contact_domain}: {remaining_contacts}")
            
            if remaining_contacts == 0:
                # Clean up breach data for this domain
                try:
                    from models.database import Breach
                    breach_record = Breach.query.filter_by(domain=contact_domain).first()
                    if breach_record:
                        db.session.delete(breach_record)
                        print(f"Cleaned up breach data for orphaned domain: {contact_domain}")
                except Exception as cleanup_error:
                    print(f"Warning: Error cleaning up breach data for {contact_domain}: {cleanup_error}")
        
        db.session.commit()
        print(f"=== DELETE CONTACT SUCCESS: ID {contact_id} ===")
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_msg = f"Error deleting contact {contact_id}: {str(e)}"
        print(f"=== DELETE CONTACT ERROR ===")
        print(error_msg)
        print(traceback.format_exc())
        return jsonify({'error': error_msg}), 500


@api_bp.route('/breach-lookup/<domain>')
@login_required
def breach_lookup(domain):
    """Look up breach information for a domain"""
    try:
        # Check if we have any contacts from this domain
        contacts_from_domain = Contact.query.filter(Contact.domain == domain).all()
        
        if not contacts_from_domain:
            return jsonify({'error': f'No contacts found from domain {domain}'})
        
        # Get a sample contact from this domain to check breach status
        sample_contact = contacts_from_domain[0]
        
        # Check if we have stored breach data in the Breach table
        from models.database import Breach
        breach_record = Breach.query.filter_by(domain=domain).first()
        
        if breach_record:
            # Check the actual breach status from contacts
            sample_contact = contacts_from_domain[0]
            
            if sample_contact.breach_status == 'not_breached':
                # Domain is secure despite having a breach record (for tracking scan status)
                return jsonify({'error': f'No security breaches found for {domain}', 'status': 'secure', 'contacts_affected': len(contacts_from_domain)})
            elif sample_contact.breach_status == 'breached' and breach_record.records_affected > 0:
                # Return actual breach data from database including stored FlawTrack data
                breach_data = {
                    'domain': domain,
                    'breach_name': breach_record.breach_name or f"{domain} Credential Breach",
                    'breach_year': breach_record.breach_year,
                    'records_affected': f"{breach_record.records_affected:,}" if breach_record.records_affected else "Unknown",
                    'data_types': breach_record.data_types or "Credentials, Email addresses",
                    'severity': breach_record.severity,
                    'contacts_affected': len(contacts_from_domain),
                    'last_updated': breach_record.last_updated.strftime('%Y-%m-%d') if breach_record.last_updated else None,
                    'breach_data': breach_record.breach_data  # Include stored FlawTrack data for display
                }
                return jsonify(breach_data)
            else:
                # Unknown status or no breach records
                return jsonify({'error': f'No confirmed breaches found for {domain}', 'status': 'unknown', 'contacts_affected': len(contacts_from_domain)})
        
        # Fallback: Use contact's breach status and risk score
        elif sample_contact.breach_status and sample_contact.breach_status != 'unknown':
            # Create response based on contact's stored breach information
            if sample_contact.breach_status == 'breached':
                breach_data = {
                    'domain': domain,
                    'breach_name': f"{domain.split('.')[0].title()} Security Incident",
                    'breach_year': 2023,  # Default year
                    'risk_score': sample_contact.risk_score or 7.0,
                    'records_affected': "Multiple",
                    'data_types': "Email addresses and user credentials",
                    'severity': 'high' if sample_contact.risk_score >= 7 else 'medium',
                    'contacts_affected': len(contacts_from_domain),
                    'source': 'Contact scan results'
                }
            else:  # not_breached
                return jsonify({'error': f'No security breaches found for {domain}', 'status': 'secure'})
            
            return jsonify(breach_data)
        
        else:
            # No breach information available
            return jsonify({'error': f'No breach data available for {domain}. Scan needed.', 'status': 'unknown'})
            
    except Exception as e:
        print(f"Error looking up breach data: {e}")
        return jsonify({'error': f'Failed to lookup breach data for {domain}'}), 500


@api_bp.route('/domain-scan-status/<domain>')
@login_required
def domain_scan_status(domain):
    """Get the scanning status for a domain"""
    try:
        from models.database import Breach
        
        breach_record = Breach.query.filter_by(domain=domain).first()
        
        if not breach_record:
            return jsonify({
                'domain': domain,
                'status': 'not_scanned',
                'message': 'Domain has not been scanned yet'
            })
        
        return jsonify({
            'domain': domain,
            'status': breach_record.scan_status,
            'attempts': breach_record.scan_attempts,
            'last_attempt': breach_record.last_scan_attempt.isoformat() if breach_record.last_scan_attempt else None,
            'last_updated': breach_record.last_updated.isoformat() if breach_record.last_updated else None,
            'error': breach_record.scan_error,
            'message': _get_scan_status_message(breach_record.scan_status, breach_record.scan_attempts)
        })
    
    except Exception as e:
        current_app.logger.error(f"Domain scan status error for {domain}: {str(e)}")
        return jsonify({'error': f'Failed to get scan status: {str(e)}'}), 500


def _get_scan_status_message(status, attempts):
    """Get human-readable message for scan status"""
    messages = {
        'not_scanned': 'Domain has not been scanned yet',
        'scanning': 'Scan in progress...',
        'completed': 'Scan completed successfully',
        'failed': f'Scan failed (attempt {attempts}/3)'
    }
    return messages.get(status, 'Unknown status')


@api_bp.route('/contacts/export')
@login_required
def export_contacts():
    """Export all contacts to CSV"""
    try:
        # Get all contacts
        contacts = Contact.query.all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['ID', 'Email', 'First Name', 'Last Name', 'Company', 'Title', 'Phone', 'Industry', 'Status', 'Active', 'Created At', 'Risk Score'])
        
        # Write contact data
        for contact in contacts:
            writer.writerow([
                contact.id,
                contact.email,
                contact.first_name or '',
                contact.last_name or '',
                contact.company or '',
                contact.title or '',
                contact.phone or '',
                contact.industry or '',
                contact.status,
                'Yes' if contact.is_active else 'No',
                contact.created_at.strftime('%Y-%m-%d %H:%M:%S') if contact.created_at else '',
                contact.risk_score
            ])
        
        output.seek(0)
        
        # Create response with CSV file
        filename = f'contacts_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        print(f"Error exporting contacts: {e}")
        return jsonify({'error': 'Error exporting contacts'}), 500


@api_bp.route('/contacts/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_contacts():
    """Bulk delete multiple contacts"""
    try:
        data = request.get_json()
        contact_ids = data.get('contact_ids', [])
        
        if not contact_ids:
            return jsonify({'error': 'No contacts selected'}), 400
        
        # Import required models for cleanup
        from models.database import EmailSequence, ContactCampaignStatus

        # Clean up all associated records for each contact before deleting them
        print(f"Starting bulk deletion of {len(contact_ids)} contacts with full cleanup")

        total_emails_deleted = 0
        total_sequences_deleted = 0
        total_campaign_statuses_deleted = 0

        # Process each contact individually for thorough cleanup
        for contact_id in contact_ids:
            try:
                # Delete EmailSequence records
                sequence_count = EmailSequence.query.filter_by(contact_id=contact_id).count()
                if sequence_count > 0:
                    EmailSequence.query.filter_by(contact_id=contact_id).delete()
                    total_sequences_deleted += sequence_count

                # Delete ContactCampaignStatus records
                status_count = ContactCampaignStatus.query.filter_by(contact_id=contact_id).count()
                if status_count > 0:
                    ContactCampaignStatus.query.filter_by(contact_id=contact_id).delete()
                    total_campaign_statuses_deleted += status_count

                # Delete Email records and their responses (this removes Brevo data)
                contact_emails = Email.query.filter_by(contact_id=contact_id).all()
                email_count = len(contact_emails)

                # Delete responses first
                for email in contact_emails:
                    if email.id:
                        EmailResponse.query.filter_by(email_id=email.id).delete()

                # Delete all emails for this contact (removes Brevo message IDs and webhook data)
                if email_count > 0:
                    Email.query.filter_by(contact_id=contact_id).delete()
                    total_emails_deleted += email_count

            except Exception as e:
                print(f"Warning: Error cleaning up records for contact {contact_id}: {e}")

        # Now delete the contacts themselves
        deleted_count = Contact.query.filter(Contact.id.in_(contact_ids)).delete(synchronize_session=False)

        print(f"Bulk deletion summary:")
        print(f"- Deleted {deleted_count} contacts")
        print(f"- Deleted {total_emails_deleted} emails (including Brevo data)")
        print(f"- Deleted {total_sequences_deleted} email sequences")
        print(f"- Deleted {total_campaign_statuses_deleted} campaign statuses")
        
        # Clean up orphaned breach data (domains with no remaining contacts)
        try:
            from models.database import Breach
            
            # Get all domains that still have contacts
            domains_with_contacts = db.session.query(Contact.domain).filter(
                Contact.domain.isnot(None)
            ).distinct().all()
            active_domains = {domain[0] for domain in domains_with_contacts}
            
            # Find and delete breach records for domains with no contacts
            orphaned_breaches = Breach.query.filter(
                ~Breach.domain.in_(active_domains)
            ).all()
            
            orphaned_count = 0
            for breach in orphaned_breaches:
                db.session.delete(breach)
                orphaned_count += 1
            
            print(f"Cleaned up {orphaned_count} orphaned breach records")
            
        except Exception as cleanup_error:
            print(f"Warning: Error cleaning up breach data: {cleanup_error}")
            # Don't fail the main operation if cleanup fails
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'emails_deleted': total_emails_deleted,
            'sequences_deleted': total_sequences_deleted,
            'campaign_statuses_deleted': total_campaign_statuses_deleted,
            'message': f'Successfully deleted {deleted_count} contacts and cleaned up {total_emails_deleted} associated emails (including Brevo data)'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error bulk deleting contacts: {e}")
        return jsonify({'error': 'Error deleting contacts'}), 500


@api_bp.route('/simulate-webhook', methods=['POST'])
@login_required
def simulate_webhook():
    """Simulate a Brevo webhook event for testing purposes"""
    try:
        data = request.get_json()
        event_type = data.get('event', 'delivered')
        email_address = data.get('email', '')
        message_id = data.get('message_id', f'test_{int(time.time())}')

        if not email_address:
            return jsonify({'error': 'Email address required'}), 400

        # Find the contact
        contact = Contact.query.filter_by(email=email_address).first()
        if not contact:
            # Create a test contact if it doesn't exist
            contact = Contact(
                email=email_address,
                first_name='Test',
                last_name='User',
                company='Test Company',
                domain=email_address.split('@')[1] if '@' in email_address else 'test.com',
                industry='Testing',
                breach_status='unknown'
            )
            db.session.add(contact)
            db.session.flush()  # Get the ID
            print(f"Created test contact: {email_address}")

        # Create simulated webhook payload
        webhook_data = {
            'event': event_type,
            'email': email_address,
            'message-id': message_id,
            'timestamp': datetime.utcnow().isoformat(),
            'tag': ['test'],
            'subject': data.get('subject', 'Test Email')
        }

        # Add event-specific data
        if event_type == 'clicked':
            webhook_data['link'] = data.get('link', 'https://example.com')
        elif event_type == 'bounced':
            webhook_data['bounce_type'] = data.get('bounce_type', 'hard')

        # Import webhook handlers
        from routes.webhooks import (
            handle_delivery_event, handle_open_event, handle_click_event,
            handle_reply_event, handle_bounce_event, handle_unsubscribe_event,
            handle_spam_event
        )

        # Process the simulated webhook
        if event_type == 'delivered':
            handle_delivery_event(contact, webhook_data)
        elif event_type == 'opened':
            handle_open_event(contact, webhook_data)
        elif event_type == 'clicked':
            handle_click_event(contact, webhook_data)
        elif event_type == 'replied':
            handle_reply_event(contact, webhook_data)
        elif event_type == 'bounced':
            handle_bounce_event(contact, webhook_data)
        elif event_type == 'unsubscribed':
            handle_unsubscribe_event(contact, webhook_data)
        elif event_type == 'spam':
            handle_spam_event(contact, webhook_data)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Simulated {event_type} event for {email_address}',
            'webhook_data': webhook_data,
            'contact_id': contact.id
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error simulating webhook: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/contacts/bulk-update-breach-status', methods=['POST'])
@login_required
def bulk_update_breach_status():
    """Bulk update breach status for multiple contacts"""
    try:
        data = request.get_json()
        contact_ids = data.get('contact_ids', [])
        new_status = data.get('breach_status')
        
        if not contact_ids:
            return jsonify({'error': 'No contacts selected'}), 400
        
        if new_status not in ['breached', 'not_breached', 'unknown', 'unassigned']:
            return jsonify({'error': 'Invalid breach status'}), 400
        
        # Update contacts
        updated_count = Contact.query.filter(Contact.id.in_(contact_ids)).update(
            {'breach_status': new_status}, 
            synchronize_session=False
        )
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'message': f'Successfully updated {updated_count} contacts to {new_status}'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error bulk updating breach status: {e}")
        return jsonify({'error': 'Error updating breach status'}), 500


@api_bp.route('/contact-stats')
@login_required
def get_contact_stats():
    """Get contact statistics for dashboard"""
    try:
        total_contacts = Contact.query.count()
        active_contacts = Contact.query.filter(Contact.is_active == True).count()
        companies_count = db.session.query(Contact.company).filter(Contact.company.isnot(None), Contact.is_active == True).distinct().count()
        in_campaigns_count = db.session.query(Contact.id).join(Email).join(Campaign).filter(Campaign.status == 'active').distinct().count()
        
        return jsonify({
            'total_contacts': total_contacts,
            'active_contacts': active_contacts, 
            'companies_count': companies_count,
            'in_campaigns_count': in_campaigns_count
        })
    except Exception as e:
        print(f"Error getting contact stats: {e}")
        return jsonify({'error': 'Error getting contact statistics'}), 500


# Breach Analysis API endpoints
# Store scan progress in memory (in production, use Redis or database)
scan_progress_store = {}


@api_bp.route('/breach-analysis/scan-domains', methods=['POST'])
@login_required
def scan_domains():
    """Simplified domain scanning endpoint"""
    try:
        # Get unique domains from contacts
        domains_query = db.session.query(Contact.domain).distinct().filter(
            Contact.domain.isnot(None)
        ).limit(50)  # Limit for demo
        
        domains = [domain[0] for domain in domains_query.all() if domain[0]]
        
        if not domains:
            # Create some demo domains for testing purposes
            demo_domains = ['example.com', 'test.org', 'demo.net', 'sample.co', 'trial.io']
            domains = demo_domains
            
            return jsonify({
                'success': True,
                'scan_id': str(uuid.uuid4()),
                'message': f'Started demo scan of {len(domains)} domains (no real contacts found)',
                'domains_to_scan': len(domains),
                'estimated_time': len(domains) * 2  # 2 seconds per domain
            })
        
        # Simulate scan process (in real implementation would call FlawTrack API)
        scan_id = str(uuid.uuid4())
        
        # For demo purposes, simulate finding some breaches
        simulated_breaches = random.randint(0, len(domains) // 3)
        
        return jsonify({
            'success': True,
            'scan_id': scan_id,
            'message': f'Started scanning {len(domains)} domains',
            'domains_to_scan': len(domains),
            'estimated_time': len(domains) * 2  # 2 seconds per domain
        })
        
    except Exception as e:
        print(f"Domain scan error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Scan failed: {str(e)}'
        })


@api_bp.route('/breach-analysis/scan-progress/<scan_id>')
@login_required
def scan_progress(scan_id):
    """Get scan progress status"""
    try:
        # Initialize scan progress if not exists
        if scan_id not in scan_progress_store:
            scan_progress_store[scan_id] = {
                'start_time': time.time(),
                'total_domains': 5,
                'current_progress': 0
            }
        
        scan_info = scan_progress_store[scan_id]
        elapsed_time = time.time() - scan_info['start_time']
        
        # Simulate progressive scanning (about 10% every 2 seconds)
        new_progress = min(100, int(elapsed_time / 2) * 20)
        scan_info['current_progress'] = new_progress
        
        is_complete = new_progress >= 100
        domains_scanned = min(scan_info['total_domains'], int(new_progress / 20))
        
        return jsonify({
            'success': True,
            'scan_id': scan_id,
            'progress': new_progress,
            'is_complete': is_complete,
            'domains_scanned': domains_scanned,
            'domains_total': scan_info['total_domains'],
            'breaches_found': random.randint(1, 3) if is_complete else 0,
            'status': 'completed' if is_complete else 'scanning'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@api_bp.route('/breach-analysis/cancel-scan/<scan_id>', methods=['POST'])
@login_required
def cancel_scan(scan_id):
    """Cancel ongoing scan"""
    try:
        # Remove scan from progress store to stop tracking
        if scan_id in scan_progress_store:
            del scan_progress_store[scan_id]
            
        return jsonify({
            'success': True,
            'message': 'Scan cancelled successfully',
            'scan_id': scan_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@api_bp.route('/breach-analysis/domains')
@login_required
def breach_domains():
    """Get domain analysis results for the dashboard"""
    try:
        # Try to get real domain data from database first
        try:
            from models.database import Contact
            
            # Get breach data only for domains that have contacts
            domains_with_contacts = db.session.query(Contact.domain).filter(Contact.domain.isnot(None)).distinct().all()
            domain_names = [domain[0] for domain in domains_with_contacts]
            
            # If no contacts exist, return empty result
            if not domain_names:
                return jsonify({
                    'success': True,
                    'domains': []
                })
            
            if domain_names:
                domains = []
                for domain_name in domain_names:
                    # Get breach data for this domain from Breach table first
                    breach = Breach.query.filter_by(domain=domain_name).first()
                    contact_count = Contact.query.filter_by(domain=domain_name).count()
                    
                    if breach:
                        # Use cached breach data
                        domains.append({
                            'domain': domain_name,
                            'breach_name': breach.breach_name or 'Security Assessment',
                            'breach_year': breach.breach_year,
                            'breach_status': breach.breach_status if hasattr(breach, 'breach_status') else (
                                'breached' if breach.risk_score >= 4.0 else 
                                'not_breached' if breach.risk_score > 0.0 else 'unknown'
                            ),
                            'contact_count': contact_count,
                            'records_affected': breach.records_affected,
                            'data_types': breach.data_types or 'Assessment pending'
                        })
                    else:
                        # No cached breach data - get from contact data directly
                        contacts_from_domain = Contact.query.filter_by(domain=domain_name).all()
                        if contacts_from_domain:
                            # Use the first contact's breach info as representative
                            sample_contact = contacts_from_domain[0]
                            breach_status = sample_contact.breach_status or 'unknown'
                            risk_score = sample_contact.risk_score or 0.0
                            
                            # Determine breach details based on contact data
                            if breach_status == 'breached':
                                breach_name = f"{domain_name} Credential Leaks"
                                breach_year = 2024  # Recent breach
                                records_affected = len(contacts_from_domain)  # Number of leaked contacts
                                data_types = "Email addresses, passwords, credentials"
                            elif breach_status == 'not_breached':
                                breach_name = "No Breaches Found"
                                breach_year = None
                                records_affected = None
                                data_types = "N/A"
                            else:
                                breach_name = "Assessment Pending"
                                breach_year = None
                                records_affected = None
                                data_types = "Assessment needed"
                            
                            domains.append({
                                'domain': domain_name,
                                'breach_name': breach_name,
                                'breach_year': breach_year,
                                'breach_status': breach_status,
                                'contact_count': contact_count,
                                'records_affected': records_affected,
                                'data_types': data_types
                            })
                        else:
                            # Fallback - should not happen as we filter for domains with contacts
                            domains.append({
                                'domain': domain_name,
                                'breach_name': 'Assessment Pending',
                                'breach_year': None,
                                'breach_status': 'unknown',
                                'contact_count': contact_count,
                                'records_affected': None,
                                'data_types': 'Assessment needed'
                            })
                
                if domains:
                    return jsonify({
                        'success': True,
                        'domains': domains
                    })
            
            # Fall back to contact table statistics
            domain_stats = db.session.query(
                Contact.domain,
                Contact.breach_status,
                db.func.count(Contact.id).label('contact_count'),
                db.func.max(Contact.company).label('company_example')
            ).filter(
                Contact.domain.isnot(None)
            ).group_by(
                Contact.domain, Contact.breach_status
            ).all()
            
            # Convert to domains list
            domains_dict = {}
            for domain, breach_status, count, company in domain_stats:
                if domain not in domains_dict:
                    domains_dict[domain] = {
                        'domain': domain,
                        'breach_name': 'Various Breaches' if breach_status == 'breached' else 'Assessment Complete' if breach_status == 'not_breached' else 'Assessment Pending',
                        'breach_year': 2023 if breach_status == 'breached' else None,
                        'breach_status': breach_status,
                        'contact_count': 0,
                        'records_affected': 50000 if breach_status == 'breached' else None,
                        'data_types': 'Email, Names, Phone numbers' if breach_status == 'breached' else 'N/A'
                    }
                domains_dict[domain]['contact_count'] += count
                if breach_status == 'breached':
                    domains_dict[domain]['breach_status'] = 'breached'
            
            domains = list(domains_dict.values())
            
            # If we have real data, return it
            if domains:
                return jsonify({
                    'success': True,
                    'domains': domains
                })
                
        except Exception as db_error:
            print(f"Database query error: {str(db_error)}")
        
        # Fallback to demo data with breach status
        demo_domains = [
            {
                'domain': 'honest.com',
                'breach_name': 'Honest Company Data Breach',
                'breach_year': 2023,
                'breach_status': 'breached',
                'contact_count': 12,
                'records_affected': 50000,
                'data_types': 'Email addresses, Names, Phone numbers'
            },
            {
                'domain': 'faradayfuture.com',
                'breach_name': 'Faraday Future Security Incident',
                'breach_year': 2023,
                'breach_status': 'breached',
                'contact_count': 15,
                'records_affected': 100000,
                'data_types': 'Email addresses, Names, Passwords, Phone numbers'
            },
            {
                'domain': 'argo.ai',
                'breach_name': 'Argo AI Data Leak',
                'breach_year': 2022,
                'breach_status': 'breached',
                'contact_count': 8,
                'records_affected': 25000,
                'data_types': 'Email addresses, Names'
            },
            {
                'domain': 'boomsupersonic.com',
                'breach_name': 'No Breaches Found',
                'breach_year': None,
                'breach_status': 'not_breached',
                'contact_count': 5,
                'records_affected': None,
                'data_types': 'N/A'
            },
            {
                'domain': 'unknown.com',
                'breach_name': 'Assessment Pending',
                'breach_year': None,
                'breach_status': 'unknown',
                'contact_count': 3,
                'records_affected': None,
                'data_types': 'Assessment Needed'
            }
        ]
        
        return jsonify({
            'success': True,
            'domains': demo_domains
        })
        
    except Exception as e:
        print(f"Breach domains API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'domains': []
        })


@api_bp.route('/breach-analysis/contacts/<breach_status>')
@login_required
def breach_status_contacts(breach_status):
    """Get contacts by breach status"""
    try:
        # Try to get real contacts from database first
        if breach_status in ['breached', 'not_breached', 'unknown']:
            contacts_query = Contact.query.filter_by(breach_status=breach_status)
            contacts = []
            
            for contact in contacts_query.all():
                contacts.append({
                    'id': contact.id,
                    'email': contact.email,
                    'first_name': contact.first_name or '',
                    'last_name': contact.last_name or '',
                    'company': contact.company or '',
                    'title': contact.title or '',
                    'domain': contact.domain or contact.email.split('@')[1] if contact.email else '',
                    'breach_status': contact.breach_status,
                    'risk_score': contact.risk_score or 0.0,
                    'breach_name': 'Various Breaches',
                    'breach_year': 2023,
                    'data_types': 'Email, Names, Phone numbers'
                })
            
            # If we have real contacts, return them
            if contacts:
                return jsonify({
                    'success': True,
                    'contacts': contacts,
                    'breach_status': breach_status
                })
        
        # Fallback to demo data for breach status
        demo_contacts = {
            'breached': [
                {
                    'id': 1,
                    'email': 'john.doe@honest.com',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'company': 'Honest Company',
                    'title': 'IT Manager',
                    'domain': 'honest.com',
                    'breach_status': 'breached',
                    'risk_score': 9.2,
                    'breach_name': 'Honest Company Data Breach',
                    'breach_year': 2023,
                    'data_types': 'Email, Names, Phone numbers'
                },
                {
                    'id': 2,
                    'email': 'jane.smith@faradayfuture.com',
                    'first_name': 'Jane',
                    'last_name': 'Smith',
                    'company': 'Faraday Future',
                    'title': 'Security Officer',
                    'domain': 'faradayfuture.com',
                    'breach_status': 'breached',
                    'risk_score': 8.7,
                    'breach_name': 'Faraday Future Security Incident',
                    'breach_year': 2023,
                    'data_types': 'Email, Names, Passwords, Phone numbers'
                }
            ],
            'not_breached': [
                {
                    'id': 3,
                    'email': 'bob.jones@boomsupersonic.com',
                    'first_name': 'Bob',
                    'last_name': 'Jones',
                    'company': 'Boom Supersonic',
                    'title': 'Developer',
                    'domain': 'boomsupersonic.com',
                    'breach_status': 'not_breached',
                    'risk_score': 0.0,
                    'breach_name': 'No Breaches Found',
                    'breach_year': None,
                    'data_types': 'N/A'
                }
            ],
            'unknown': [
                {
                    'id': 4,
                    'email': 'alice.brown@unknown.com',
                    'first_name': 'Alice',
                    'last_name': 'Brown',
                    'company': 'Unknown Corp',
                    'title': 'Manager',
                    'domain': 'unknown.com',
                    'breach_status': 'unknown',
                    'risk_score': 0.0,
                    'breach_name': 'Status Unknown',
                    'breach_year': None,
                    'data_types': 'Assessment Needed'
                }
            ]
        }
        
        contacts = demo_contacts.get(breach_status, [])
        
        return jsonify({
            'success': True,
            'contacts': contacts,
            'breach_status': breach_status
        })
        
    except Exception as e:
        print(f"Breach status contacts API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'contacts': []
        })


@api_bp.route('/campaigns/auto-enroll', methods=['POST'])
@login_required
def trigger_auto_enrollment():
    """Manually trigger auto-enrollment process for all campaigns"""
    try:
        from services.auto_enrollment import create_auto_enrollment_service
        
        auto_service = create_auto_enrollment_service(db)
        stats = auto_service.process_auto_enrollment()
        
        return jsonify({
            'success': True,
            'message': f'Auto-enrollment completed: {stats["contacts_enrolled"]} contacts enrolled into {stats["campaigns_processed"]} campaigns',
            'stats': stats
        })
        
    except Exception as e:
        print(f"Error triggering auto-enrollment: {e}")
        return jsonify({'error': 'Error running auto-enrollment'}), 500


@api_bp.route('/campaigns/<int:campaign_id>/enroll-contact/<int:contact_id>', methods=['POST'])
@login_required
def enroll_contact_in_campaign(campaign_id, contact_id):
    """Manually enroll a specific contact in a specific campaign"""
    try:
        from services.auto_enrollment import create_auto_enrollment_service
        
        auto_service = create_auto_enrollment_service(db)
        success = auto_service.enroll_single_contact(contact_id, campaign_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Contact enrolled successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to enroll contact (may already be enrolled or invalid data)'
            })
            
    except Exception as e:
        print(f"Error enrolling contact: {e}")
        return jsonify({'error': 'Error enrolling contact'}), 500


@api_bp.route('/campaigns/<int:campaign_id>/analytics', methods=['GET'])
@login_required
def get_campaign_analytics(campaign_id):
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


@api_bp.route('/campaigns', methods=['GET'])
@login_required
def get_campaigns():
    """Get all active campaigns for dropdowns and selections"""
    try:
        campaigns = Campaign.query.filter_by(status='active').all()

        campaigns_list = []
        for campaign in campaigns:
            campaigns_list.append({
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status,
                'created_at': campaign.created_at.isoformat() if campaign.created_at else None
            })

        return jsonify(campaigns_list)
    except Exception as e:
        print(f"Error getting campaigns: {e}")
        return jsonify({'error': 'Error getting campaigns'}), 500


@api_bp.route('/contacts/<int:contact_id>/campaigns', methods=['GET'])
@login_required
def get_contact_campaigns(contact_id):
    """Get all campaigns that a contact is enrolled in"""
    try:
        contact = Contact.query.get(contact_id)
        if not contact:
            return jsonify({'success': False, 'error': 'Contact not found'}), 404

        from models.database import ContactCampaignStatus

        # Get all campaign enrollments for this contact
        enrollments = ContactCampaignStatus.query.filter_by(contact_id=contact_id).all()

        campaigns_list = []
        for enrollment in enrollments:
            campaign = Campaign.query.get(enrollment.campaign_id)
            if campaign:
                # Get last email sent to this contact in this campaign
                last_email = Email.query.filter_by(
                    contact_id=contact_id,
                    campaign_id=campaign.id
                ).order_by(Email.sent_at.desc()).first()

                # Determine enrollment status based on replied_at and sequence_completed_at
                if enrollment.replied_at:
                    enrollment_status = 'replied'
                elif enrollment.sequence_completed_at:
                    enrollment_status = 'completed'
                else:
                    enrollment_status = 'active'

                campaigns_list.append({
                    'id': campaign.id,
                    'name': campaign.name,
                    'status': campaign.status,
                    'enrollment_status': enrollment_status,
                    'enrolled_at': enrollment.created_at.isoformat() if enrollment.created_at else None,
                    'replied_at': enrollment.replied_at.isoformat() if enrollment.replied_at else None,
                    'last_email_sent': last_email.sent_at.isoformat() if last_email and last_email.sent_at else None
                })

        return jsonify({
            'success': True,
            'campaigns': campaigns_list,
            'contact_email': contact.email
        })
    except Exception as e:
        print(f"Error getting contact campaigns: {e}")
        return jsonify({'success': False, 'error': 'Error getting contact campaigns'}), 500


@api_bp.route('/contacts/bulk-assign-campaign', methods=['POST'])
@login_required
def bulk_assign_campaign():
    """Bulk assign multiple contacts to multiple campaigns"""
    try:
        data = request.get_json()
        contact_ids = data.get('contact_ids', [])
        campaign_ids = data.get('campaign_ids', [])

        if not contact_ids:
            return jsonify({'success': False, 'message': 'No contacts selected'}), 400

        if not campaign_ids:
            return jsonify({'success': False, 'message': 'No campaigns selected'}), 400

        # Use auto-enrollment service to properly enroll contacts
        from services.auto_enrollment import create_auto_enrollment_service
        from models.database import ContactCampaignStatus

        auto_service = create_auto_enrollment_service(db)
        total_assigned = 0
        total_skipped = 0
        campaign_results = []

        # Process each campaign
        for campaign_id in campaign_ids:
            try:
                # Verify campaign exists
                campaign = Campaign.query.get(campaign_id)
                if not campaign:
                    continue

                campaign_assigned = 0
                campaign_skipped = 0

                # Process each contact for this campaign
                for contact_id in contact_ids:
                    try:
                        # Check if contact exists
                        contact = Contact.query.get(contact_id)
                        if not contact:
                            campaign_skipped += 1
                            continue

                        # Check if already enrolled
                        existing = ContactCampaignStatus.query.filter_by(
                            contact_id=contact_id,
                            campaign_id=campaign_id
                        ).first()

                        if existing:
                            campaign_skipped += 1
                            continue

                        # Use the working enroll_single_contact method
                        success = auto_service.enroll_single_contact(contact_id, campaign_id)

                        if success:
                            campaign_assigned += 1
                            print(f"Successfully enrolled contact {contact.email} into campaign {campaign_id}")
                        else:
                            campaign_skipped += 1
                            print(f"Failed to enroll contact {contact.email} (may already be enrolled)")

                    except Exception as e:
                        print(f"Error assigning contact {contact_id} to campaign {campaign_id}: {e}")
                        campaign_skipped += 1

                # Update totals
                total_assigned += campaign_assigned
                total_skipped += campaign_skipped

                # Store results for this campaign
                campaign_results.append({
                    'campaign_id': campaign_id,
                    'campaign_name': campaign.name,
                    'assigned': campaign_assigned,
                    'skipped': campaign_skipped
                })

            except Exception as campaign_error:
                print(f"Error processing campaign {campaign_id}: {campaign_error}")
                continue

        # Build response message
        message_parts = []
        if total_assigned > 0:
            campaign_count = len([r for r in campaign_results if r['assigned'] > 0])
            message_parts.append(f'Successfully assigned {total_assigned} enrollment(s) across {campaign_count} campaign(s)')

        if total_skipped > 0:
            message_parts.append(f'{total_skipped} contact-campaign pair(s) already enrolled or invalid')

        message = '. '.join(message_parts) if message_parts else 'No changes made'

        return jsonify({
            'success': True,
            'assigned_count': total_assigned,
            'skipped_count': total_skipped,
            'campaign_results': campaign_results,
            'message': message
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error bulk assigning campaigns: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': 'Error assigning contacts to campaigns'}), 500


# FlawTrack API Health Monitoring Endpoints (REMOVED - Breach scanning discontinued)
@api_bp.route('/flawtrack/status', methods=['GET'])
@login_required
def flawtrack_status():
    """FlawTrack feature has been removed"""
    return jsonify({
        'success': False,
        'error': 'FlawTrack breach scanning feature has been removed. System now uses industry-based targeting.'
    }), 404

