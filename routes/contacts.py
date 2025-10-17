"""
Contact management routes for SalesBreachPro
Handles contact listing, upload, management, and breach analysis
"""
import os
import csv
import io
import re
import socket
import tempfile
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from utils.decorators import login_required
from utils.pagination import SimplePagination, MockPagination
from models.database import db, Contact, Email, Campaign
from services.emaillistverify_validator import create_emaillistverify_validator

# Create contacts blueprint
contacts_bp = Blueprint('contacts', __name__, url_prefix='/contacts')

def validate_email_domain(domain):
    """
    Validate email domain for format and basic reachability
    
    Args:
        domain (str): The domain part of an email address
        
    Returns:
        bool: True if domain is valid, False otherwise
    """
    # Basic domain format validation
    if not domain or len(domain) < 3:
        return False
    
    # Check for invalid characters
    if not re.match(r'^[a-zA-Z0-9.-]+$', domain):
        return False
    
    # Domain should not start or end with dot or dash
    if domain.startswith('.') or domain.endswith('.') or domain.startswith('-') or domain.endswith('-'):
        return False
    
    # Should have at least one dot for TLD
    if '.' not in domain:
        return False
    
    # Check for consecutive dots or dashes
    if '..' in domain or '--' in domain:
        return False
    
    # Validate TLD (should be at least 2 characters)
    tld = domain.split('.')[-1]
    if len(tld) < 2 or not tld.isalpha():
        return False
    
    # Common invalid domains to reject
    invalid_domains = {
        'test.com', 'example.com', 'example.org', 'example.net',
        'test.test', 'invalid.invalid', 'fake.fake', 'dummy.dummy',
        'localhost', '127.0.0.1'
    }
    
    if domain.lower() in invalid_domains:
        return False
    
    # Optional: Basic DNS check (commented out to avoid blocking valid new domains)
    # This can be enabled if you want stricter validation but may slow down imports
    """
    try:
        # Check if domain has MX record (mail server)
        import dns.resolver
        mx_records = dns.resolver.resolve(domain, 'MX')
        return len(mx_records) > 0
    except:
        # If DNS lookup fails, still allow the domain (might be temporary issue)
        pass
    """
    
    return True


@contacts_bp.route('/')
@login_required
def index():
    """Contacts management page"""
    print("=== CONTACTS ROUTE DEBUG START ===")
    # Temporarily removed try/catch to see actual errors
    page = request.args.get('page', 1, type=int)
    per_page = 50
    search = request.args.get('search', '')
    filter_type = request.args.get('filter', 'all')
    status_filter = request.args.get('status', '')
    sort_order = request.args.get('sort', '')

    # Build base query
    query = Contact.query

    # Apply search filter
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            Contact.email.ilike(search_term) |
            Contact.first_name.ilike(search_term) |
            Contact.last_name.ilike(search_term) |
            Contact.company.ilike(search_term)
        )

    # Apply activity filter
    if filter_type == 'active':
        query = query.filter(
            Contact.is_active == True,
            Contact.blocked_at.is_(None)
        )
    elif filter_type == 'recent':
        # Recent contacts (added in last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        query = query.filter(Contact.created_at >= thirty_days_ago)
    elif filter_type == 'blocked':
        # Blocked contacts - show only contacts that have been blocked
        query = query.filter(Contact.blocked_at.isnot(None))
    # 'all' filter shows everything (no additional filter)

    # Apply status filter (breach_status or email_status)
    if status_filter and status_filter != 'all':
        if status_filter == 'blocked':
            # Blocked contacts are identified by email_status
            query = query.filter(Contact.email_status == 'blocked')
        else:
            # Other statuses are identified by breach_status
            query = query.filter(Contact.breach_status == status_filter)

    # Apply sorting
    if sort_order == 'date_asc':
        query = query.order_by(Contact.created_at.asc())
    elif sort_order == 'date_desc':
        query = query.order_by(Contact.created_at.desc())
    else:
        # Default sorting: newest first
        query = query.order_by(Contact.created_at.desc())

    # Get total count for this filtered query
    total = query.count()
    print(f"=== TOTAL CONTACTS FOUND: {total} ===")
    
    # Apply pagination - only get the contact IDs first for better performance
    contact_ids_query = query.with_entities(Contact.id).offset((page-1) * per_page).limit(per_page)
    contact_ids = [id[0] for id in contact_ids_query.all()]
    print(f"=== CONTACT IDS RETRIEVED: {len(contact_ids)} ===")

    # Get contacts with email counts and campaign counts in a single optimized query
    if contact_ids:
        # Import here to avoid circular imports
        from models.database import ContactCampaignStatus

        contacts_with_counts = db.session.query(
            Contact,
            db.func.count(db.distinct(Email.id)).label('email_count'),
            db.func.count(db.distinct(ContactCampaignStatus.campaign_id)).label('campaign_count')
        ).outerjoin(Email, Contact.id == Email.contact_id
        ).outerjoin(ContactCampaignStatus, Contact.id == ContactCampaignStatus.contact_id
        ).filter(Contact.id.in_(contact_ids)
        ).group_by(Contact.id).all()

        # Create a dictionary for fast lookup
        contacts_dict = {}
        for contact, email_count, campaign_count in contacts_with_counts:
            contact.email_count = email_count or 0
            contact._campaign_count = campaign_count or 0  # Cache the campaign count
            contacts_dict[contact.id] = contact

        # Preserve the sort order from contact_ids
        contacts = []
        for contact_id in contact_ids:
            if contact_id in contacts_dict:
                contacts.append(contacts_dict[contact_id])
    else:
        contacts = []

    print(f"=== CONTACTS WITH EMAIL COUNTS: {len(contacts)} ===")

    pagination = SimplePagination(contacts, total, page, per_page)

    # Calculate additional statistics efficiently with separate simple queries (SQLAlchemy version compatibility)
    total_contacts = Contact.query.count()
    active_count = Contact.query.filter(
        Contact.is_active == True,
        Contact.blocked_at.is_(None)
    ).count()
    blocked_count = Contact.query.filter(Contact.email_status == 'blocked').count()
    companies_count = db.session.query(Contact.company).filter(
        Contact.company.isnot(None),
        Contact.is_active == True,
        Contact.blocked_at.is_(None)
    ).distinct().count()

    # Count contacts in active campaigns separately (more complex join)
    in_campaigns_count = db.session.query(Contact.id).join(Email).join(Campaign).filter(Campaign.status == 'active').distinct().count()
    
    print(f"=== RENDERING TEMPLATE WITH {len(contacts)} CONTACTS ===")
    
    return render_template('contacts.html',
                         contacts=pagination.items,
                         pagination=pagination,
                         total_contacts=total_contacts,
                         active_count=active_count,
                         blocked_count=blocked_count,
                         companies_count=companies_count,
                         in_campaigns_count=in_campaigns_count,
                         search_query=search,
                         current_filter=filter_type,
                         current_status=status_filter)


@contacts_bp.route('/breach-analysis')
@login_required
def breach_analysis():
    """Breach analysis page"""
    try:
        # Get domain statistics
        total_domains = db.session.query(Contact.domain).filter(Contact.domain.isnot(None)).distinct().count()
        
        # Get real breach data from contacts
        domain_stats = db.session.query(
            Contact.domain,
            Contact.breach_status,
            db.func.count(Contact.id).label('contacts_count'),
            db.func.avg(Contact.risk_score).label('avg_risk_score'),
            db.func.max(Contact.company).label('company_example')
        ).filter(
            Contact.domain.isnot(None)
        ).group_by(
            Contact.domain, Contact.breach_status
        ).all()
        
        # Convert to breach analysis format
        domain_breaches = {}
        for domain, breach_status, count, avg_risk, company in domain_stats:
            if domain not in domain_breaches:
                domain_breaches[domain] = {
                    'domain': domain,
                    'company': company or domain.split('.')[0].title(),
                    'contacts_count': 0,
                    'breach_status': 'unassigned',
                    'risk_score': 0.0,
                }
            
            domain_breaches[domain]['contacts_count'] += count
            if breach_status == 'breached':
                domain_breaches[domain]['breach_status'] = 'breached'
                domain_breaches[domain]['risk_score'] = avg_risk or 0.0
            elif breach_status == 'not_breached' and domain_breaches[domain]['breach_status'] != 'breached':
                domain_breaches[domain]['breach_status'] = 'not_breached'
                domain_breaches[domain]['risk_score'] = avg_risk or 0.0
        
        # Convert to list with binary breach status
        sample_breaches = []
        for domain_data in domain_breaches.values():
            # Use binary status instead of risk levels
            domain_data['breach_display'] = domain_data['breach_status']
            sample_breaches.append(domain_data)
        
        # Sort breached domains first, then by risk score
        sample_breaches.sort(key=lambda x: (
            0 if x['breach_status'] == 'breached' else 
            1 if x['breach_status'] == 'not_breached' else 2,
            -x['risk_score']
        ))
        
        # Calculate breach summary statistics using binary status
        breached_contacts = Contact.query.filter_by(breach_status='breached').count()
        secure_contacts = Contact.query.filter_by(breach_status='not_breached').count() 
        unknown_contacts = Contact.query.filter_by(breach_status='unknown').count()
        
        breach_summary = {
            'total_domains': total_domains,
            'total_contacts': Contact.query.count(),
            'breached_contacts': breached_contacts,
            'secure_contacts': secure_contacts,
            'unknown_contacts': unknown_contacts,
            'breached_domains': len([b for b in sample_breaches if b['breach_status'] == 'breached']),
            'secure_domains': len([b for b in sample_breaches if b['breach_status'] == 'not_breached']),
            'unknown_domains': len([b for b in sample_breaches if b['breach_status'] == 'unknown'])
        }
        
        # Calculate risk summary for the template
        total_contacts = Contact.query.count()
        breached_contacts = Contact.query.filter_by(breach_status='breached').count()
        secure_contacts = Contact.query.filter_by(breach_status='not_breached').count()
        unknown_contacts = Contact.query.filter_by(breach_status='unknown').count()
        high_risk_contacts = Contact.query.filter(Contact.risk_score >= 7).count()
        medium_risk_contacts = Contact.query.filter(Contact.risk_score >= 4, Contact.risk_score < 7).count()
        low_risk_contacts = Contact.query.filter(Contact.risk_score > 0, Contact.risk_score < 4).count()
        
        risk_summary = {
            'total_contacts': total_contacts,
            'breached_contacts': breached_contacts,
            'secure_contacts': secure_contacts,
            'unknown_contacts': unknown_contacts,
            'high_risk_contacts': high_risk_contacts,
            'medium_risk_contacts': medium_risk_contacts,
            'low_risk_contacts': low_risk_contacts,
            'contacts_with_breach_data': breached_contacts + secure_contacts,
            'contacts_without_breach_data': unknown_contacts,
            'risk_distribution': {
                'high': high_risk_contacts,
                'medium': medium_risk_contacts,
                'low': low_risk_contacts
            }
        }
        
        return render_template('breach_analysis.html', 
                             total_domains=total_domains,
                             breaches=sample_breaches,
                             breach_summary=breach_summary,
                             risk_summary=risk_summary)
        
    except Exception as e:
        print(f"Breach analysis error: {e}")
        return render_template('breach_analysis.html', 
                             total_domains=0,
                             breaches=[],
                             breach_summary={'total_domains': 0, 'breached_domains': 0, 'high_risk': 0, 'medium_risk': 0, 'low_risk': 0, 'clean_domains': 0, 'unknown_domains': 0},
                             risk_summary={
                                 'total_contacts': 0, 
                                 'breached_contacts': 0, 
                                 'secure_contacts': 0, 
                                 'unknown_contacts': 0, 
                                 'high_risk_contacts': 0, 
                                 'medium_risk_contacts': 0, 
                                 'low_risk_contacts': 0,
                                 'contacts_with_breach_data': 0,
                                 'contacts_without_breach_data': 0,
                                 'risk_distribution': {'high': 0, 'medium': 0, 'low': 0}
                             })


@contacts_bp.route('/upload')
@login_required
def upload_page():
    """Contact upload page"""
    try:
        # Get current contact statistics
        total_contacts = Contact.query.count()
        active_contacts = Contact.query.filter_by(is_active=True).count()
        
        stats = {
            'total_contacts': total_contacts,
            'active_contacts': active_contacts
        }
        
        return render_template('upload.html', stats=stats)
        
    except Exception as e:
        current_app.logger.error(f"Upload page error: {str(e)}")
        # Provide default stats in case of error
        stats = {
            'total_contacts': 0,
            'active_contacts': 0
        }
        return render_template('upload.html', stats=stats)


@contacts_bp.route('/leads')
@login_required 
def leads():
    """Leads management page"""
    try:
        from datetime import datetime, timedelta
        
        # Calculate lead scores for contacts
        def calculate_lead_score(contact):
            """Calculate lead score from 0-100 based on engagement and profile"""
            score = 0
            
            # Base score from risk score (0-40 points)
            if hasattr(contact, 'risk_score') and contact.risk_score:
                score += min(contact.risk_score * 4, 40)
            
            # Get email engagement data
            email_count = Email.query.filter_by(contact_id=contact.id).count()
            
            # Get last opened email
            last_opened_email = Email.query.filter_by(contact_id=contact.id).filter(
                Email.opened_at.isnot(None)
            ).order_by(Email.opened_at.desc()).first()
            
            # Get response data
            response_count = db.session.query(Email).join(
                'responses'  # This assumes responses relationship exists
            ).filter(Email.contact_id == contact.id).count()
            
            last_response_email = db.session.query(Email).join(
                'responses'
            ).filter(Email.contact_id == contact.id).order_by(
                Email.replied_at.desc()
            ).first()
            
            # Email engagement (0-30 points)
            if email_count:
                score += min(email_count * 2, 15)  # Up to 15 points for email count
                
                if last_opened_email and last_opened_email.opened_at:
                    days_since_open = (datetime.utcnow() - last_opened_email.opened_at).days
                    if days_since_open <= 7:
                        score += 15  # Recent opens get max points
                    elif days_since_open <= 30:
                        score += 10
                    else:
                        score += 5
            
            # Response engagement (0-30 points)  
            if response_count:
                score += min(response_count * 10, 20)  # Up to 20 points for responses
                
                if last_response_email and last_response_email.replied_at:
                    days_since_response = (datetime.utcnow() - last_response_email.replied_at).days
                    if days_since_response <= 7:
                        score += 10  # Recent responses get max points
                    elif days_since_response <= 30:
                        score += 5
            
            return min(score, 100)
        
        # Get all contacts and calculate their lead scores
        contacts = Contact.query.filter_by(is_active=True).all()
        leads_data = []
        
        for contact in contacts:
            lead_score = calculate_lead_score(contact)
            
            if lead_score > 0:  # Only include contacts with some engagement
                # Get last activity date
                last_email = Email.query.filter_by(contact_id=contact.id).order_by(
                    Email.sent_at.desc()
                ).first()
                
                last_activity = last_email.sent_at if last_email else contact.created_at
                
                leads_data.append({
                    'contact': contact,
                    'lead_score': lead_score,
                    'last_activity': last_activity,
                    'emails_sent': Email.query.filter_by(contact_id=contact.id).count(),
                    'responses': db.session.query(Email).join('responses').filter(
                        Email.contact_id == contact.id
                    ).count()
                })
        
        # Sort by lead score descending
        leads_data.sort(key=lambda x: x['lead_score'], reverse=True)
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = 25
        
        total = len(leads_data)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_leads = leads_data[start:end]
        
        pagination = SimplePagination(paginated_leads, total, page, per_page)
        
        # Calculate summary stats
        hot_leads = len([l for l in leads_data if l['lead_score'] >= 70])
        warm_leads = len([l for l in leads_data if 40 <= l['lead_score'] < 70])
        cold_leads = len([l for l in leads_data if l['lead_score'] < 40])
        
        stats = {
            'total_leads': total,
            'hot_leads': hot_leads,
            'warm_leads': warm_leads, 
            'cold_leads': cold_leads
        }
        
        return render_template('leads.html',
                             leads=pagination.items,
                             pagination=pagination,
                             stats=stats)
                             
    except Exception as e:
        print(f"Leads error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return render_template('leads.html', leads=[], pagination=MockPagination(), stats={})


@contacts_bp.route('/emails/<status>')
@login_required
def email_management(status):
    """Email management page with status filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Build base query - join Email with Contact and Campaign
        from models.database import Campaign
        query = Email.query.join(Contact).join(Campaign)
        
        # Apply status filter
        valid_statuses = ['sent', 'pending', 'delivered', 'opened', 'clicked', 'replied', 'bounced', 'failed']

        if status == 'delivered':
            # For delivered, filter by delivered_at field (Brevo webhook confirmation)
            query = query.filter(Email.delivered_at.isnot(None))
            print(f"DEBUG: Filtering for delivered emails. Query count: {query.count()}")
        elif status == 'opened':
            # For opened, filter by opened_at field (Brevo webhook confirmation)
            query = query.filter(Email.opened_at.isnot(None))
        elif status == 'bounced':
            # For bounced, filter by bounced_at field (Brevo webhook confirmation)
            query = query.filter(Email.bounced_at.isnot(None))
        elif status == 'replied':
            # For replied, filter by replied_at field (Brevo webhook confirmation)
            query = query.filter(Email.replied_at.isnot(None))
        elif status in valid_statuses:
            query = query.filter(Email.status == status)
        elif status == 'all':
            # No filter for 'all'
            pass
        else:
            # Invalid status, default to 'all'
            status = 'all'
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        query_results = query.order_by(Email.sent_at.desc()).offset((page-1) * per_page).limit(per_page).all()

        # Convert query results to the format expected by template
        emails = []
        for result in query_results:
            if isinstance(result, tuple):
                # If query returns (Email, Contact, Campaign) tuple
                if len(result) == 3:
                    email_obj, contact_obj, campaign_obj = result
                    emails.append({
                        'email': email_obj,
                        'contact': contact_obj,
                        'campaign': campaign_obj
                    })
                else:
                    # If query returns (Email, Contact) tuple
                    email_obj, contact_obj = result
                    emails.append({
                        'email': email_obj,
                        'contact': contact_obj,
                        'campaign': email_obj.campaign
                    })
            else:
                # If query returns Email objects with joined contact and campaign
                emails.append({
                    'email': result,
                    'contact': result.contact,
                    'campaign': result.campaign
                })

        pagination = SimplePagination(emails, total, page, per_page)
        
        # Calculate status counts for the filter buttons
        status_counts = {}
        for s in valid_statuses + ['all']:
            if s == 'all':
                status_counts[s] = Email.query.count()
            elif s == 'delivered':
                status_counts[s] = Email.query.filter(Email.delivered_at.isnot(None)).count()
            elif s == 'opened':
                status_counts[s] = Email.query.filter(Email.opened_at.isnot(None)).count()
            elif s == 'bounced':
                status_counts[s] = Email.query.filter(Email.bounced_at.isnot(None)).count()
            elif s == 'replied':
                status_counts[s] = Email.query.filter(Email.replied_at.isnot(None)).count()
            else:
                status_counts[s] = Email.query.filter(Email.status == s).count()
        
        # Create config for template
        config = {
            'title': f'{status.title()} Emails' if status != 'all' else 'All Emails',
            'icon': 'fa-envelope',
            'color': 'primary',
            'description': f'Manage and review {status} emails' if status != 'all' else 'Manage and review all emails'
        }

        return render_template('email_management.html',
                             emails=pagination.items,
                             pagination=pagination,
                             status=status,
                             current_status=status,
                             status_counts=status_counts,
                             config=config)
                             
    except Exception as e:
        import traceback
        print(f"Email management error: {e}")
        print(f"Email management traceback: {traceback.format_exc()}")
        # Create config for template
        config = {
            'title': f'{status.title()} Emails' if status != 'all' else 'All Emails',
            'icon': 'fa-envelope',
            'color': 'primary',
            'description': f'Manage and review {status} emails' if status != 'all' else 'Manage and review all emails'
        }

        return render_template('email_management.html',
                             emails=[],
                             pagination=MockPagination(),
                             current_status=status,
                             status_counts={},
                             config=config)


@contacts_bp.route('/upload/csv', methods=['POST'])
@login_required
def upload_csv():
    """Optimized CSV upload with batch processing and campaign selection"""
    try:
        # Get campaign selections (support multiple campaigns)
        campaign_ids = request.form.getlist('campaign_ids')  # Multiple campaigns from upload.html

        # DEBUG: Detailed campaign_ids logging
        print(f"\n=== CSV UPLOAD DEBUG START ===")
        print(f"campaign_ids = {campaign_ids} (type: {type(campaign_ids).__name__})")
        print(f"campaign_ids count: {len(campaign_ids)}")
        print(f"All form keys: {list(request.form.keys())}")
        print(f"=== END CAMPAIGN DEBUG ===\n")

        current_app.logger.info(f"Optimized upload started with {len(campaign_ids)} campaign(s): {campaign_ids}")
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.csv'):
            return jsonify({'success': False, 'message': 'File must be a CSV'}), 400
        
        # Read CSV content with multiple encoding support
        file_bytes = file.read()
        csv_content = None

        # Try multiple encodings commonly used for CSV files
        encodings_to_try = ['utf-8-sig', 'utf-8', 'windows-1252', 'iso-8859-1', 'cp1252']

        for encoding in encodings_to_try:
            try:
                csv_content = file_bytes.decode(encoding)
                current_app.logger.info(f"Successfully decoded CSV with encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue

        if csv_content is None:
            return jsonify({
                'success': False,
                'message': 'Unable to read CSV file. Please ensure it is saved in UTF-8 or Windows (ANSI) encoding.'
            }), 400

        csv_reader = csv.DictReader(io.StringIO(csv_content))

        # STEP 1: Parse CSV and extract basic email info (NO validation yet)
        parsed_rows = []
        error_rows = []
        email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

        for row_index, row in enumerate(csv_reader):
            # Find email in any column
            email = None
            for key, value in row.items():
                if value and email_regex.match(str(value).strip()):
                    email = str(value).strip().lower()
                    break

            if not email:
                error_rows.append(f"Row {row_index + 1}: No valid email found")
                continue

            # Extract domain
            domain = email.split('@')[1] if '@' in email else None

            parsed_rows.append({
                'email': email,
                'domain': domain,
                'row': row  # Keep original row for field extraction later
            })

        if not parsed_rows:
            return jsonify({
                'success': False,
                'message': 'No valid emails found in CSV'
            }), 400

        # Check contact limit for large uploads
        if len(parsed_rows) > 1000:
            current_app.logger.warning(f"Large upload attempted: {len(parsed_rows)} contacts")
            return jsonify({
                'success': False,
                'message': f'Upload too large: {len(parsed_rows)} contacts. Maximum 1000 contacts per upload.'
            }), 400

        # STEP 2: Check for duplicates FIRST (before expensive email validation)
        all_emails = [row['email'] for row in parsed_rows]
        existing_emails = set()

        # Query existing emails in chunks to avoid database query limits
        chunk_size = 100
        for i in range(0, len(all_emails), chunk_size):
            email_chunk = all_emails[i:i + chunk_size]
            chunk_existing = db.session.query(Contact.email).filter(Contact.email.in_(email_chunk)).all()
            existing_emails.update(email[0] for email in chunk_existing)

        # Filter to only new (non-duplicate) emails
        new_emails_data = [row for row in parsed_rows if row['email'] not in existing_emails]
        skipped_contacts = len(parsed_rows) - len(new_emails_data)

        current_app.logger.info(f"Found {len(new_emails_data)} new emails to validate (skipped {skipped_contacts} duplicates)")

        if not new_emails_data:
            return jsonify({
                'success': True,
                'message': f'All {len(parsed_rows)} contact(s) already exist in database',
                'summary': {
                    'total_rows_processed': len(parsed_rows),
                    'contacts_created': 0,
                    'duplicates_skipped': skipped_contacts,
                    'contacts_updated': 0,
                    'errors': len(error_rows),
                    'job_id': None
                },
                'validation_stats': {
                    'valid_emails': 0,
                    'risky_emails': 0,
                    'invalid_emails': 0,
                    'validation_errors': 0
                }
            }), 200

        # STEP 3: Initialize email validator (only needed for non-duplicates)
        try:
            email_validator = create_emaillistverify_validator()
            current_app.logger.info("EmailListVerify email validator initialized for contact upload")
        except Exception as e:
            current_app.logger.warning(f"Could not initialize EmailListVerify validator: {e}")
            email_validator = None

        # Track validation statistics
        validation_stats = {
            'valid_emails': 0,
            'risky_emails': 0,
            'invalid_emails': 0,
            'validation_errors': 0
        }

        # STEP 4: Validate and process only non-duplicate contacts
        rows_to_process = []

        for row_data in new_emails_data:
            email = row_data['email']
            domain = row_data['domain']
            row = row_data['row']

            # Validate email with EmailListVerify (only new emails!)
            validation_result = None
            breach_status = 'unassigned'  # Default status

            if email_validator:
                try:
                    validation_result = email_validator.validate_email(email)

                    # Set breach_status based on validation result
                    if validation_result['status'] == 'valid':
                        breach_status = 'unassigned'  # Will be scanned by FlawTrack
                        validation_stats['valid_emails'] += 1
                    elif validation_result['status'] == 'risky':
                        breach_status = 'risky'  # Added but not scanned
                        validation_stats['risky_emails'] += 1
                    else:  # 'invalid'
                        breach_status = 'bounced'  # Added but not scanned
                        validation_stats['invalid_emails'] += 1

                    current_app.logger.debug(f"Email {email} validated: {validation_result['status']} -> {breach_status}")

                except Exception as e:
                    current_app.logger.warning(f"Email validation failed for {email}: {e}")
                    validation_stats['validation_errors'] += 1
                    # Keep default breach_status = 'unassigned'
            else:
                # No validator available, count as validation error but continue
                validation_stats['validation_errors'] += 1

            # Prepare contact data
            contact_data = {
                'email': email,
                'domain': domain,
                'created_at': datetime.utcnow(),
                'is_active': True
            }

            # Note: Email validation data is collected but not stored in Contact model
            # Validation is used only for filtering risky/invalid emails during upload

            # Extract optional fields efficiently
            for key, value in row.items():
                if not value or not key:
                    continue

                key_lower = key.lower().strip()
                value_clean = str(value).strip()

                if value_clean.lower() == email:
                    continue

                # Map fields
                if any(x in key_lower for x in ['first', 'fname']):
                    contact_data['first_name'] = value_clean.title()
                elif any(x in key_lower for x in ['last', 'lname']):
                    contact_data['last_name'] = value_clean.title()
                elif 'name' in key_lower and 'first' not in key_lower:
                    if ' ' in value_clean:
                        parts = value_clean.split(' ', 1)
                        contact_data['first_name'] = parts[0].title()
                        contact_data['last_name'] = parts[1].title()
                    else:
                        contact_data['first_name'] = value_clean.title()
                elif any(x in key_lower for x in ['company', 'org']):
                    contact_data['company'] = value_clean.title()
                elif any(x in key_lower for x in ['title', 'position']):
                    contact_data['title'] = value_clean.title()
                elif any(x in key_lower for x in ['phone', 'tel']):
                    contact_data['phone'] = value_clean
                elif 'industry' in key_lower:
                    contact_data['industry'] = value_clean.title()

            rows_to_process.append(contact_data)

        current_app.logger.info(f"Processing {len(rows_to_process)} validated contacts for upload")

        # STEP 5: Batch insert all new contacts
        new_contacts = []
        for contact_data in rows_to_process:
            new_contacts.append(Contact(**contact_data))
        
        # 3. Batch insert all new contacts in smaller chunks to avoid memory issues
        new_contact_ids = []
        if new_contacts:
            # Process in batches of 50 to avoid memory/timeout issues
            batch_size = 50
            for i in range(0, len(new_contacts), batch_size):
                batch = new_contacts[i:i + batch_size]
                try:
                    db.session.bulk_save_objects(batch)
                    db.session.commit()

                    # Get the inserted contact IDs for this batch
                    batch_contact_ids = [
                        contact.id for contact in
                        Contact.query.filter(Contact.email.in_([c.email for c in batch])).all()
                    ]
                    new_contact_ids.extend(batch_contact_ids)

                except Exception as batch_error:
                    current_app.logger.error(f"Batch insert failed for batch {i//batch_size + 1}: {batch_error}")
                    db.session.rollback()
                    # Continue with next batch instead of failing completely
                    continue
        
        contacts_created = len(new_contact_ids)  # Use actual inserted contacts, not attempted

        # STEP 6: Enroll contacts in selected campaigns (if any)
        enrolled_count = 0
        enrollment_by_campaign = {}

        # DEBUG: Enrollment section start
        print(f"\n=== ENROLLMENT DEBUG START ===")
        print(f"new_contact_ids = {new_contact_ids[:5] if len(new_contact_ids) > 5 else new_contact_ids} (showing first 5 of {len(new_contact_ids)} total)")
        print(f"campaign_ids = {campaign_ids} (count: {len(campaign_ids)})")
        print(f"Enrollment IF condition: new_contact_ids={len(new_contact_ids) > 0} AND campaign_ids={len(campaign_ids) > 0}")

        if new_contact_ids and campaign_ids:
            print(f"[OK] ENTERING enrollment block")
            from services.auto_enrollment import create_auto_enrollment_service
            auto_service = create_auto_enrollment_service(db)
            print(f"[OK] Created auto_service")

            # Loop through each selected campaign
            for campaign_id_str in campaign_ids:
                try:
                    campaign_id_int = int(campaign_id_str)
                    print(f"\n[OK] Processing campaign ID: {campaign_id_int}")

                    campaign_enrolled = 0
                    for idx, contact_id in enumerate(new_contact_ids):
                        try:
                            print(f"  Enrolling contact {idx+1}/{len(new_contact_ids)}: contact_id={contact_id}, campaign_id={campaign_id_int}")
                            success = auto_service.enroll_single_contact(contact_id, campaign_id_int)
                            print(f"  Result: success={success}")
                            if success:
                                enrolled_count += 1
                                campaign_enrolled += 1
                        except Exception as enroll_error:
                            print(f"  ERROR enrolling contact {contact_id}: {enroll_error}")
                            current_app.logger.warning(f"Failed to enroll contact {contact_id} in campaign {campaign_id_int}: {enroll_error}")

                    enrollment_by_campaign[campaign_id_int] = campaign_enrolled
                    print(f"[OK] Campaign {campaign_id_int} enrollment complete: {campaign_enrolled}/{len(new_contact_ids)} contacts enrolled")

                except (ValueError, TypeError) as e:
                    print(f"[ERROR] Invalid campaign ID '{campaign_id_str}': {e}")
                    current_app.logger.warning(f"Invalid campaign ID: {campaign_id_str}: {e}")

            print(f"[OK] All enrollments complete: total_enrolled={enrolled_count} across {len(campaign_ids)} campaign(s)")
            current_app.logger.info(f"Enrolled {enrolled_count} total enrollments across {len(campaign_ids)} campaigns: {enrollment_by_campaign}")
        else:
            print(f"[SKIP] Enrollment block - condition not met (contacts: {len(new_contact_ids)}, campaigns: {len(campaign_ids)})")

        print(f"Final enrolled_count = {enrolled_count}")
        print(f"=== ENROLLMENT DEBUG END ===\n")

        # Background scanning removed - FlawTrack/breach detection no longer used
        scan_job_id = None
        unique_domains = set(c.domain for c in new_contacts if c.domain)
        
        # 5. Return success response
        message_parts = []
        if contacts_created > 0:
            message_parts.append(f"✅ {contacts_created} new contact{'s' if contacts_created != 1 else ''} imported")
        if skipped_contacts > 0:
            message_parts.append(f"⚠️ {skipped_contacts} duplicate{'s' if skipped_contacts != 1 else ''} skipped")
        if len(error_rows) > 0:
            message_parts.append(f"❌ {len(error_rows)} error{'s' if len(error_rows) != 1 else ''}")

        # Add validation statistics to message
        total_validated = validation_stats['valid_emails'] + validation_stats['risky_emails'] + validation_stats['invalid_emails']
        if total_validated > 0:
            message_parts.append(f"📧 Email validation: {validation_stats['valid_emails']} valid, {validation_stats['risky_emails']} risky, {validation_stats['invalid_emails']} invalid")

        success_message = " | ".join(message_parts) if message_parts else "No changes made"
        
        return jsonify({
            'success': True,
            'message': success_message,
            'summary': {
                'total_rows_processed': len(rows_to_process),
                'contacts_created': contacts_created,
                'duplicates_skipped': skipped_contacts,
                'errors': len(error_rows),
                'domains_found': len(unique_domains)
            },
            'email_validation': {
                'valid_emails': validation_stats['valid_emails'],
                'risky_emails': validation_stats['risky_emails'],
                'invalid_emails': validation_stats['invalid_emails'],
                'validation_errors': validation_stats['validation_errors'],
                'total_validated': validation_stats['valid_emails'] + validation_stats['risky_emails'] + validation_stats['invalid_emails'],
                'validator_enabled': email_validator is not None
            },
            'scan_results': {
                'domains_to_scan': len(unique_domains),
                'scan_job_id': None,
                'scanning_in_background': False
            },
            'error_details': error_rows[:10] if error_rows else []  # Show first 10 errors
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Optimized upload failed: {str(e)}")
        current_app.logger.error(f"Full traceback: {error_details}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Upload failed: {str(e)}',
            'debug_info': str(e) if current_app.debug else None
        }), 500

def process_csv_with_progress(file_path, upload_id):
    """Process CSV file with progress updates"""
    try:
        from models.contact import ContactManager
        
        # Update progress
        upload_progress[upload_id]['status'] = 'processing'
        upload_progress[upload_id]['message'] = 'Reading CSV file...'
        upload_progress[upload_id]['progress'] = 5
        
        # Use ContactManager for processing with FlawTrack integration
        contact_manager = ContactManager()
        
        # Process the CSV file
        result = contact_manager.process_csv_file(
            file_path, 
            enable_breach_lookup=True,
            progress_callback=lambda msg, progress, **kwargs: update_progress(upload_id, msg, progress, **kwargs)
        )
        
        # Update final progress
        upload_progress[upload_id]['status'] = 'completed'
        upload_progress[upload_id]['progress'] = 100
        upload_progress[upload_id]['message'] = 'Upload completed successfully!'
        upload_progress[upload_id]['result'] = result
        
        # Clean up temp file
        os.unlink(file_path)
        
    except Exception as e:
        upload_progress[upload_id]['status'] = 'error'
        upload_progress[upload_id]['message'] = f'Error: {str(e)}'
        upload_progress[upload_id]['progress'] = 0
        
        # Clean up temp file
        try:
            os.unlink(file_path)
        except:
            pass

def update_progress(upload_id, message, progress, **kwargs):
    """Update progress information"""
    if upload_id in upload_progress:
        upload_progress[upload_id]['message'] = message
        upload_progress[upload_id]['progress'] = progress
        
        # Update additional info if provided
        for key, value in kwargs.items():
            if key in upload_progress[upload_id]:
                upload_progress[upload_id][key] = value

@contacts_bp.route('/upload/progress/<upload_id>')
@login_required  
def get_upload_progress(upload_id):
    """Get upload progress for a specific upload ID"""
    if upload_id in upload_progress:
        return jsonify(upload_progress[upload_id])
    else:
        return jsonify({'error': 'Upload not found'}), 404

@contacts_bp.route('/upload/cleanup/<upload_id>', methods=['POST'])
@login_required
def cleanup_upload_progress(upload_id):
    """Clean up upload progress data"""
    if upload_id in upload_progress:
        del upload_progress[upload_id]
    return jsonify({'success': True})

@contacts_bp.route('/api/list')
@login_required
def api_contacts_list():
    """API endpoint for contact list with pagination and search"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        search = request.args.get('search', '')
        
        # Limit per_page to reasonable values
        per_page = min(per_page, 100)
        
        # Build query
        query = Contact.query
        
        # Apply search filter if provided
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                db.or_(
                    Contact.email.ilike(search_filter),
                    Contact.first_name.ilike(search_filter),
                    Contact.last_name.ilike(search_filter),
                    Contact.company.ilike(search_filter),
                    Contact.domain.ilike(search_filter)
                )
            )
        
        # Get paginated results
        contacts = query.order_by(Contact.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Convert contacts to dictionaries
        contacts_data = [contact.to_dict() for contact in contacts.items]
        
        return jsonify({
            'contacts': contacts_data,
            'pagination': {
                'total': contacts.total,
                'pages': contacts.pages,
                'current_page': contacts.page,
                'per_page': contacts.per_page,
                'has_prev': contacts.has_prev,
                'has_next': contacts.has_next,
                'prev_num': contacts.prev_num,
                'next_num': contacts.next_num
            }
        })
        
    except Exception as e:
        print(f"Error in api_contacts_list: {e}")
        return jsonify({'error': 'Failed to fetch contacts'}), 500


@contacts_bp.route('/api/<int:contact_id>/campaigns')
@login_required
def get_contact_campaigns(contact_id):
    """Get all campaigns for a specific contact"""
    try:
        from models.database import ContactCampaignStatus

        # Get contact
        contact = Contact.query.get_or_404(contact_id)

        # Get all campaigns for this contact via ContactCampaignStatus
        campaign_statuses = ContactCampaignStatus.query.filter_by(contact_id=contact_id).all()

        campaigns = []
        for status in campaign_statuses:
            campaign = Campaign.query.get(status.campaign_id)
            if campaign:
                campaigns.append({
                    'id': campaign.id,
                    'name': campaign.name,
                    'status': campaign.status,
                    'created_at': campaign.created_at.isoformat() if campaign.created_at else None,
                    'contact_status': {
                        'replied_at': status.replied_at.isoformat() if status.replied_at else None,
                        'sequence_completed_at': status.sequence_completed_at.isoformat() if status.sequence_completed_at else None,
                        'completion_reason': status.completion_reason
                    }
                })

        return jsonify({
            'success': True,
            'contact_id': contact_id,
            'contact_email': contact.email,
            'campaigns': campaigns,
            'total': len(campaigns)
        })

    except Exception as e:
        print(f"Error in get_contact_campaigns: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to load campaigns', 'details': str(e)}), 500


@contacts_bp.route('/api/bulk-assign-campaign', methods=['POST'])
@login_required
def bulk_assign_campaign():
    """Assign multiple contacts to multiple campaigns"""
    try:
        data = request.get_json()

        contact_ids = data.get('contact_ids', [])
        campaign_ids = data.get('campaign_ids', [])

        if not contact_ids:
            return jsonify({'success': False, 'message': 'No contacts selected'}), 400

        if not campaign_ids:
            return jsonify({'success': False, 'message': 'No campaigns selected'}), 400

        # Import required models
        from models.database import ContactCampaignStatus
        from services.campaign_service import schedule_campaign_emails

        # Track overall results
        total_assigned = 0
        total_skipped = 0
        total_errors = []
        total_already_enrolled = []
        campaign_results = []

        # Process each campaign
        for campaign_id in campaign_ids:
            try:
                # Get campaign
                campaign = Campaign.query.get(campaign_id)
                if not campaign:
                    total_errors.append(f'Campaign ID {campaign_id} not found')
                    continue

                # Track results for this specific campaign
                campaign_assigned = 0
                campaign_skipped = 0
                campaign_errors = []
                campaign_already_enrolled = []

                # Process each contact for this campaign
                for contact_id in contact_ids:
                    try:
                        contact = Contact.query.get(contact_id)
                        if not contact:
                            campaign_skipped += 1
                            campaign_errors.append(f'Contact ID {contact_id} not found')
                            continue

                        # Check if contact is already in this campaign
                        existing = ContactCampaignStatus.query.filter_by(
                            contact_id=contact_id,
                            campaign_id=campaign_id
                        ).first()

                        if existing:
                            campaign_skipped += 1
                            # Add to already_enrolled list with contact details
                            contact_name = f"{contact.first_name} {contact.last_name}" if contact.first_name or contact.last_name else contact.email
                            campaign_already_enrolled.append(f'{contact_name.strip()} ({contact.email})')
                            continue

                        # Create ContactCampaignStatus
                        contact_status = ContactCampaignStatus(
                            contact_id=contact_id,
                            campaign_id=campaign_id,
                            added_at=datetime.utcnow()
                        )
                        db.session.add(contact_status)

                        # Schedule emails for this contact
                        schedule_campaign_emails(campaign, [contact])

                        campaign_assigned += 1

                    except Exception as contact_error:
                        campaign_skipped += 1
                        campaign_errors.append(f'Contact ID {contact_id}: {str(contact_error)}')
                        print(f"Error assigning contact {contact_id} to campaign {campaign_id}: {contact_error}")
                        continue

                # Update totals
                total_assigned += campaign_assigned
                total_skipped += campaign_skipped
                total_errors.extend(campaign_errors)
                total_already_enrolled.extend(campaign_already_enrolled)

                # Store results for this campaign
                campaign_results.append({
                    'campaign_id': campaign_id,
                    'campaign_name': campaign.name,
                    'assigned': campaign_assigned,
                    'skipped': campaign_skipped,
                    'already_enrolled': len(campaign_already_enrolled)
                })

            except Exception as campaign_error:
                total_errors.append(f'Campaign {campaign_id}: {str(campaign_error)}')
                print(f"Error processing campaign {campaign_id}: {campaign_error}")
                continue

        # Commit all changes
        try:
            db.session.commit()
        except Exception as commit_error:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Failed to save changes: {str(commit_error)}'
            }), 500

        # Build response message
        message_parts = []
        if total_assigned > 0:
            campaign_count = len([r for r in campaign_results if r['assigned'] > 0])
            message_parts.append(f'Successfully assigned {total_assigned} enrollment(s) across {campaign_count} campaign(s)')

        if total_already_enrolled:
            message_parts.append(f'{len(total_already_enrolled)} contact-campaign pair(s) already enrolled')

        if total_errors:
            message_parts.append(f'{len(total_errors)} error(s) occurred')

        message = '. '.join(message_parts) if message_parts else 'No changes made'

        return jsonify({
            'success': True,
            'message': message,
            'assigned_count': total_assigned,
            'skipped_count': total_skipped,
            'campaign_results': campaign_results,
            'already_enrolled': total_already_enrolled[:10],  # Return first 10 already enrolled
            'errors': total_errors[:5]  # Return first 5 errors only
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error in bulk_assign_campaign: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': 'Failed to assign contacts to campaigns', 'error': str(e)}), 500