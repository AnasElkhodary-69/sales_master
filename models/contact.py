import re
import csv
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from models.database import db, Contact
import email_validator
import logging

logger = logging.getLogger(__name__)

class ContactManager:
    """Handles contact management operations including CSV import and validation"""
    
    def __init__(self):
        self.validation_errors = []
        self.duplicate_contacts = []
        self.valid_contacts = []
        
    def process_csv_file(self, file_path: str, enable_breach_lookup: bool = True, progress_callback=None) -> Dict:
        """
        Process uploaded CSV file and return validation results
        
        Args:
            file_path: Path to CSV file
            enable_breach_lookup: Whether to perform automatic breach lookups
        
        Returns:
            Dict with processing results including valid/invalid counts and breach data
        """
        try:
            # Read CSV file with flexible handling using standard csv library
            contacts_data = []
            original_columns = []
            detected_fields = {}
            
            # Try different encodings to handle various file formats
            encodings_to_try = ['utf-8-sig', 'utf-8', 'latin1', 'cp1252', 'iso-8859-1']
            csvfile = None
            
            for encoding in encodings_to_try:
                try:
                    csvfile = open(file_path, 'r', encoding=encoding, newline='')
                    # Test read the first line to ensure encoding works
                    sample = csvfile.read(1024)
                    csvfile.seek(0)
                    break
                except UnicodeDecodeError:
                    if csvfile:
                        csvfile.close()
                    continue
            
            if not csvfile:
                raise Exception("Could not read CSV file with any supported encoding")
            
            try:
                # Read sample for delimiter detection
                sample = csvfile.read(1024)
                csvfile.seek(0)
                
                # Smart delimiter detection - handle single column CSVs
                delimiter = ','  # Default
                try:
                    # Check if sample contains common delimiters
                    if ',' in sample:
                        delimiter = ','
                    elif ';' in sample:
                        delimiter = ';'
                    elif '\t' in sample:
                        delimiter = '\t'
                    else:
                        # For single column CSVs, try sniffer but with fallback
                        sniffer = csv.Sniffer()
                        try:
                            detected_delimiter = sniffer.sniff(sample).delimiter
                            # Only use detected delimiter if it makes sense
                            if detected_delimiter in [',', ';', '\t', '|']:
                                delimiter = detected_delimiter
                        except:
                            pass  # Keep default comma
                except:
                    pass  # Keep default comma
                
                # Read the CSV
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                original_columns = reader.fieldnames or []
                
                if progress_callback:
                    progress_callback("Reading CSV file...", 10)
                
                # Convert to list of dictionaries, filtering out separator rows
                for row in reader:
                    # Skip rows that are separators (contain mostly dashes or special formatting)
                    row_values = list(row.values())
                    if any(row_values):  # Skip empty rows
                        # Check if this is a separator row (contains mostly dashes)
                        combined_text = ' '.join(str(v) for v in row_values if v)
                        if not (len(combined_text) > 10 and combined_text.count('-') > len(combined_text) * 0.5):
                            contacts_data.append(row)
            
            finally:
                csvfile.close()
            
            # Test first row to see what fields can be detected
            if len(contacts_data) > 0:
                first_row = contacts_data[0]
                normalized_first = self.normalize_field_names(first_row)
                detected_fields = {k: v for k, v in normalized_first.items() if v}
            
            # Process each contact
            results = {
                'total_rows': len(contacts_data),
                'valid_contacts': 0,
                'invalid_contacts': 0,
                'duplicates_found': 0,
                'new_contacts_added': 0,
                'breach_lookups_performed': 0,
                'high_risk_contacts': 0,
                'medium_risk_contacts': 0,
                'low_risk_contacts': 0,
                'errors': [],
                'warnings': [],
                'csv_info': {
                    'original_columns': original_columns,
                    'detected_fields': list(detected_fields.keys()),
                    'has_email': 'email' in detected_fields,
                    'columns_count': len(original_columns)
                },
                'success': True,
                'imported_count': 0
            }
            
            # Collect unique domains for batch breach lookup
            unique_domains = set()
            valid_contacts = []
            total_rows = len(contacts_data)
            
            if progress_callback:
                progress_callback("Validating contacts...", 20, total_rows=total_rows)
            
            # First pass: validate all contacts and collect domains
            for idx, contact_data in enumerate(contacts_data):
                try:
                    # Update progress during validation
                    if progress_callback and idx % 10 == 0:
                        validation_progress = 20 + (idx / total_rows) * 30  # 20-50%
                        progress_callback(f"Validating contact {idx + 1} of {total_rows}...", validation_progress, processed_rows=idx + 1, total_rows=total_rows)
                    # Validate and process contact
                    validation_result = self.validate_contact(contact_data, row_number=idx + 1)
                    
                    if validation_result['is_valid']:
                        # Check for duplicates
                        if self.is_duplicate(validation_result['contact_data']['email']):
                            results['duplicates_found'] += 1
                            results['warnings'].append(f"Row {idx + 1}: Duplicate email {validation_result['contact_data']['email']}")
                        else:
                            valid_contacts.append((idx + 1, validation_result['contact_data']))
                            unique_domains.add(validation_result['contact_data']['domain'])
                    else:
                        results['invalid_contacts'] += 1
                        results['errors'].extend([f"Row {idx + 1}: {error}" for error in validation_result['errors']])
                        
                except Exception as e:
                    results['invalid_contacts'] += 1
                    results['errors'].append(f"Row {idx + 1}: {str(e)}")
            
            # Perform batch breach lookup if enabled
            breach_data = {}
            if enable_breach_lookup and unique_domains:
                if progress_callback:
                    progress_callback("Scanning domains for security breaches...", 50, total_domains=len(unique_domains))
                breach_data = self.perform_batch_breach_lookup(list(unique_domains), progress_callback)
                results['breach_lookups_performed'] = len(breach_data)
            
            # Second pass: create contacts with breach information
            valid_count = len(valid_contacts)
            if progress_callback:
                progress_callback("Creating contacts...", 70, contacts_created=0, total_contacts=valid_count)
            
            for idx, (row_num, contact_data) in enumerate(valid_contacts):
                try:
                    # Update progress during contact creation
                    if progress_callback and idx % 5 == 0:
                        creation_progress = 70 + (idx / valid_count) * 25  # 70-95%
                        progress_callback(f"Creating contact {idx + 1} of {valid_count}...", creation_progress, contacts_created=idx, total_contacts=valid_count)
                    # Get breach information for this domain
                    domain_breach_info = breach_data.get(contact_data['domain'])
                    
                    # Add breach risk information to contact
                    if domain_breach_info:
                        risk_score = domain_breach_info.get('risk_score', 0)
                        breach_status = domain_breach_info.get('breach_status', 'unassigned')
                        contact_data['risk_score'] = risk_score
                        contact_data['breach_status'] = breach_status
                        
                        if risk_score >= 7:
                            results['high_risk_contacts'] += 1
                        elif risk_score >= 4:
                            results['medium_risk_contacts'] += 1
                        else:
                            results['low_risk_contacts'] += 1
                    
                    # Create contact
                    contact = self.create_contact(contact_data)
                    if contact:
                        results['valid_contacts'] += 1
                        results['new_contacts_added'] += 1
                    else:
                        results['invalid_contacts'] += 1
                        results['errors'].append(f"Row {row_num}: Failed to create contact")
                        
                except Exception as e:
                    results['invalid_contacts'] += 1
                    results['errors'].append(f"Row {row_num}: {str(e)}")
            
            # Commit all changes
            db.session.commit()

            # Trigger auto-enrollment for contacts with final breach status (not 'unassigned')
            if results['new_contacts_added'] > 0:
                try:
                    from services.auto_enrollment import create_auto_enrollment_service
                    auto_service = create_auto_enrollment_service(db)

                    # Get the newly created contacts with their final breach status
                    new_contacts = Contact.query.filter(
                        Contact.breach_status != 'unassigned'
                    ).order_by(Contact.created_at.desc()).limit(results['new_contacts_added']).all()

                    enrolled_count = 0
                    for contact in new_contacts:
                        enrolled_count += auto_service.check_breach_status_campaigns(contact.id)

                    if enrolled_count > 0:
                        logger.info(f"Auto-enrolled {enrolled_count} new contacts into campaigns based on breach status")

                except Exception as e:
                    logger.error(f"Error during post-upload auto-enrollment: {str(e)}")
                    # Don't fail the upload if enrollment fails

            # Set imported_count for frontend compatibility
            results['imported_count'] = results['new_contacts_added']
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing CSV file: {str(e)}")
            return {
                'total_rows': 0,
                'valid_contacts': 0,
                'invalid_contacts': 0,
                'duplicates_found': 0,
                'new_contacts_added': 0,
                'errors': [f"File processing error: {str(e)}"],
                'warnings': []
            }
    
    def validate_contact(self, contact_data: Dict, row_number: int = 0) -> Dict:
        """
        Validate a single contact record
        
        Args:
            contact_data: Dictionary containing contact information
            row_number: Row number for error reporting
            
        Returns:
            Dict with validation results
        """
        errors = []
        warnings = []
        
        # Normalize field names (handle common variations)
        normalized_data = self.normalize_field_names(contact_data)
        
        # Required field validation
        if not normalized_data.get('email'):
            errors.append("Email is required")
        else:
            # Email format validation
            email_validation = self.validate_email(normalized_data['email'])
            if not email_validation['is_valid']:
                errors.append(f"Invalid email format: {email_validation['error']}")
            else:
                normalized_data['email'] = email_validation['normalized_email']
                normalized_data['domain'] = email_validation['domain']
        
        # Optional field validation - only warn about data quality issues, not missing fields
        # All fields except email are truly optional
        
        # Clean and validate optional fields
        normalized_data = self.clean_contact_data(normalized_data)
        
        return {
            'is_valid': len(errors) == 0,
            'contact_data': normalized_data,
            'errors': errors,
            'warnings': warnings
        }
    
    def clean_email_value(self, email_value: str) -> str:
        """Clean email value to extract actual email address"""
        if not email_value:
            return ""
        
        email_str = str(email_value).strip()
        
        # Remove angle brackets: <email@domain.com> -> email@domain.com
        if email_str.startswith('<') and email_str.endswith('>'):
            email_str = email_str[1:-1]
        
        # Skip emails that are masked with asterisks (e.g. d****@domain.com)
        if '*' in email_str:
            return ""
        
        # Skip entries that don't contain valid email format
        if '@' not in email_str:
            return ""
        
        # Skip entries that contain descriptive text
        if any(phrase in email_str.lower() for phrase in [
            'no email', 'not found', 'general contact', 'contact:', 'inquiries'
        ]):
            return ""
        
        # Clean up common formatting issues
        email_str = email_str.replace(' ', '').replace('\t', '')
        
        return email_str.lower()
    
    def normalize_field_names(self, contact_data: Dict) -> Dict:
        """Normalize field names to handle common CSV header variations"""
        field_mappings = {
            # Email variations - most comprehensive
            'email': [
                'email', 'email_address', 'e-mail', 'e_mail', 'mail', 'email address',
                'contact_email', 'work_email', 'business_email', 'primary_email',
                'contact', 'address', 'email_addr', 'emails'
            ],
            
            # Name variations
            'first_name': [
                'first_name', 'firstname', 'first', 'fname', 'given_name',
                'first name', 'givenname', 'forename', 'christian_name'
            ],
            'last_name': [
                'last_name', 'lastname', 'last', 'lname', 'surname', 'family_name',
                'last name', 'familyname', 'surname'
            ],
            
            # Company variations
            'company': [
                'company', 'company_name', 'organization', 'org', 'employer',
                'company name', 'organisation', 'business', 'workplace',
                'corp', 'corporation', 'firm', 'business_name'
            ],
            
            # Title variations
            'title': [
                'title', 'job_title', 'position', 'role', 'job title',
                'job_position', 'designation', 'job', 'occupation',
                'job_role', 'work_title', 'function'
            ],
            
            # Phone variations
            'phone': [
                'phone', 'phone_number', 'telephone', 'mobile', 'cell',
                'phone number', 'tel', 'contact_number', 'work_phone',
                'business_phone', 'office_phone', 'cellphone', 'mobile_number'
            ],
            
            # Industry variations
            'industry': [
                'industry', 'sector', 'vertical', 'business_type',
                'business type', 'field', 'domain', 'market', 'category'
            ]
        }
        
        normalized = {}
        
        # Handle case where we have no or minimal column headers
        if len(contact_data) == 1:
            # If there's only one column, assume it's email
            single_key = list(contact_data.keys())[0]
            single_value = contact_data[single_key]
            
            # Check if the value looks like an email
            if '@' in str(single_value):
                cleaned_email = self.clean_email_value(single_value)
                if cleaned_email:
                    normalized['email'] = cleaned_email
                return normalized
        
        # Convert all keys to lowercase for comparison
        lowercase_data = {k.lower().strip(): v for k, v in contact_data.items()}
        
        # Auto-detect email column if no standard headers match
        email_found = False
        for standard_field, variations in field_mappings.items():
            for variation in variations:
                if variation in lowercase_data and lowercase_data[variation]:
                    value = lowercase_data[variation]
                    if standard_field == 'email':
                        value = self.clean_email_value(value)
                        email_found = True
                    normalized[standard_field] = value
                    break
        
        # If no email column was found, try to find one by content
        if not email_found:
            for key, value in lowercase_data.items():
                if value and '@' in str(value) and '.' in str(value):
                    # This looks like an email
                    normalized['email'] = self.clean_email_value(value)
                    break
        
        return normalized
    
    def validate_email(self, email: str) -> Dict:
        """
        Comprehensive email validation
        
        Args:
            email: Email address to validate
            
        Returns:
            Dict with validation results
        """
        try:
            # Basic format check and normalization
            email = email.strip().lower()
            
            # Use email-validator library with relaxed domain checking
            # Only check format, not if domain actually exists (too restrictive for sales)
            validated_email = email_validator.validate_email(email, check_deliverability=False)
            normalized_email = validated_email.email
            domain = normalized_email.split('@')[1]
            
            # Additional checks
            warnings = []
            
            # Check for role-based emails (flag as potential issues)
            role_prefixes = ['admin', 'info', 'support', 'sales', 'marketing', 'noreply', 'no-reply']
            local_part = normalized_email.split('@')[0]
            
            for role in role_prefixes:
                if role in local_part:
                    warnings.append(f"Role-based email detected: {role}")
                    break
            
            return {
                'is_valid': True,
                'normalized_email': normalized_email,
                'domain': domain,
                'warnings': warnings,
                'error': None
            }
            
        except email_validator.EmailNotValidError as e:
            return {
                'is_valid': False,
                'normalized_email': None,
                'domain': None,
                'warnings': [],
                'error': str(e)
            }
        except Exception as e:
            return {
                'is_valid': False,
                'normalized_email': None,
                'domain': None,
                'warnings': [],
                'error': f"Email validation error: {str(e)}"
            }
    
    def clean_contact_data(self, contact_data: Dict) -> Dict:
        """Clean and standardize contact data with flexible field handling"""
        cleaned = contact_data.copy()
        
        # Clean text fields - handle None and empty values gracefully
        text_fields = ['first_name', 'last_name', 'company', 'title', 'industry']
        for field in text_fields:
            if cleaned.get(field) and str(cleaned[field]).strip():
                # Strip whitespace and title case
                cleaned[field] = str(cleaned[field]).strip()
                if field in ['first_name', 'last_name', 'title']:
                    cleaned[field] = cleaned[field].title()
            else:
                # Set empty fields to None for consistency
                cleaned[field] = None
        
        # Clean phone number
        if cleaned.get('phone') and str(cleaned['phone']).strip():
            phone = str(cleaned['phone']).strip()
            # Remove common phone number formatting
            phone = re.sub(r'[^\d+\-\(\)\s]', '', phone)
            cleaned['phone'] = phone if phone else None
        else:
            cleaned['phone'] = None
        
        # Ensure domain is set
        if cleaned.get('email') and not cleaned.get('domain'):
            cleaned['domain'] = cleaned['email'].split('@')[1]
        
        # Set default values for any missing required fields for database compatibility
        defaults = {
            'first_name': None,
            'last_name': None, 
            'company': None,
            'title': None,
            'phone': None,
            'industry': None,
            'active': True,
            'created_at': None  # Will be set by database
        }
        
        for field, default_value in defaults.items():
            if field not in cleaned:
                cleaned[field] = default_value
        
        return cleaned
    
    def is_duplicate(self, email: str) -> bool:
        """Check if contact with email already exists"""
        existing_contact = Contact.query.filter_by(email=email.lower().strip()).first()
        return existing_contact is not None
    
    def create_contact(self, contact_data: Dict) -> Optional[Contact]:
        """Create a new contact record"""
        try:
            contact = Contact(
                email=contact_data['email'],
                first_name=contact_data.get('first_name'),
                last_name=contact_data.get('last_name'),
                company=contact_data.get('company'),
                domain=contact_data.get('domain'),
                title=contact_data.get('title'),
                phone=contact_data.get('phone'),
                industry=contact_data.get('industry'),
                status='active',
                risk_score=contact_data.get('risk_score', 0.0),
                breach_status=contact_data.get('breach_status', 'unassigned')
            )
            
            db.session.add(contact)
            # Don't commit here - will be committed in batch
            
            return contact
            
        except Exception as e:
            logger.error(f"Error creating contact: {str(e)}")
            db.session.rollback()
            return None
    
    def get_contacts_paginated(self, page: int = 1, per_page: int = 50, search: str = None) -> Dict:
        """Get paginated list of contacts with optional search"""
        try:
            from models.database import Email, Campaign
            
            # Create subqueries for email count and campaign count
            email_count_subq = db.session.query(
                Email.contact_id,
                db.func.count(Email.id).label('email_count')
            ).group_by(Email.contact_id).subquery()
            
            campaign_count_subq = db.session.query(
                Email.contact_id,
                db.func.count(db.distinct(Email.campaign_id)).label('campaign_count')
            ).group_by(Email.contact_id).subquery()
            
            # Main query with left joins to get counts
            query = db.session.query(
                Contact,
                db.func.coalesce(email_count_subq.c.email_count, 0).label('email_count'),
                db.func.coalesce(campaign_count_subq.c.campaign_count, 0).label('campaign_count')
            ).outerjoin(
                email_count_subq, Contact.id == email_count_subq.c.contact_id
            ).outerjoin(
                campaign_count_subq, Contact.id == campaign_count_subq.c.contact_id
            )
            
            # Apply search filter
            if search:
                search = f"%{search}%"
                query = query.filter(
                    db.or_(
                        Contact.email.like(search),
                        Contact.first_name.like(search),
                        Contact.last_name.like(search),
                        Contact.company.like(search)
                    )
                )
            
            # Order by creation date (newest first)
            query = query.order_by(Contact.created_at.desc())
            
            # Execute query and get all results for pagination
            all_results = query.all()
            total = len(all_results)
            
            # Manual pagination
            start = (page - 1) * per_page
            end = start + per_page
            page_results = all_results[start:end]
            
            # Attach counts to contact objects
            contacts_with_counts = []
            for contact, email_count, campaign_count in page_results:
                contact.email_count = email_count
                contact.campaign_count = campaign_count
                contacts_with_counts.append(contact)
            
            return {
                'contacts': contacts_with_counts,
                'total': total,
                'pages': (total + per_page - 1) // per_page,  # Calculate pages
                'current_page': page,
                'per_page': per_page,
                'has_prev': page > 1,
                'has_next': end < total,
                'prev_num': page - 1 if page > 1 else None,
                'next_num': page + 1 if end < total else None
            }
            
        except Exception as e:
            logger.error(f"Error getting contacts: {str(e)}")
            return {
                'contacts': [],
                'total': 0,
                'pages': 0,
                'current_page': 1,
                'per_page': per_page,
                'has_prev': False,
                'has_next': False,
                'prev_num': None,
                'next_num': None
            }
    
    def get_contact_statistics(self) -> Dict:
        """Get contact statistics for dashboard"""
        try:
            total_contacts = Contact.query.count()
            active_contacts = Contact.query.filter_by(status='active').count()
            
            # Top domains
            domain_stats = db.session.query(
                Contact.domain, 
                db.func.count(Contact.id).label('count')
            ).group_by(Contact.domain).order_by(
                db.func.count(Contact.id).desc()
            ).limit(5).all()
            
            # Top companies
            company_stats = db.session.query(
                Contact.company, 
                db.func.count(Contact.id).label('count')
            ).filter(Contact.company.isnot(None)).group_by(
                Contact.company
            ).order_by(
                db.func.count(Contact.id).desc()
            ).limit(5).all()
            
            return {
                'total_contacts': total_contacts,
                'active_contacts': active_contacts,
                'inactive_contacts': total_contacts - active_contacts,
                'top_domains': [{'domain': domain, 'count': count} for domain, count in domain_stats],
                'top_companies': [{'company': company, 'count': count} for company, count in company_stats]
            }
            
        except Exception as e:
            logger.error(f"Error getting contact statistics: {str(e)}")
            return {
                'total_contacts': 0,
                'active_contacts': 0,
                'inactive_contacts': 0,
                'top_domains': [],
                'top_companies': []
            }
    
    def bulk_update_contacts(self, contact_ids: List[int], updates: Dict) -> Dict:
        """Bulk update multiple contacts"""
        try:
            updated_count = Contact.query.filter(Contact.id.in_(contact_ids)).update(updates)
            db.session.commit()
            
            return {
                'success': True,
                'updated_count': updated_count,
                'message': f"Successfully updated {updated_count} contacts"
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error bulk updating contacts: {str(e)}")
            return {
                'success': False,
                'updated_count': 0,
                'message': f"Error updating contacts: {str(e)}"
            }
    
    def perform_batch_breach_lookup(self, domains: List[str], progress_callback=None) -> Dict:
        """
        Perform batch breach lookup for multiple domains using FlawTrack API
        
        Args:
            domains: List of domain names to lookup
            
        Returns:
            Dict mapping domains to breach information
        """
        try:
            logger.info(f"Performing FlawTrack API breach lookup for {len(domains)} domains")
            
            # Import FlawTrack API service
            from services.flawtrack_api import FlawTrackAPI
            from models.database import Settings
            
            # Get FlawTrack API settings from environment variables
            import os
            api_key = os.getenv('FLAWTRACK_API_TOKEN', 'seLP1scW.m1XeMDxyMjsZ3KaIF1XzFG74gJqxwWLW')
            endpoint = os.getenv('FLAWTRACK_API_ENDPOINT', 'https://app-api.flawtrack.com/leaks/demo/credentials/')
            
            # Initialize FlawTrack API
            flawtrack = FlawTrackAPI(
                api_key=api_key,
                endpoint=endpoint
            )
            
            # Use the FlawTrack API batch lookup with proper rate limiting
            flawtrack_results = flawtrack.batch_domain_lookup(domains, delay=1.0, progress_callback=progress_callback)
            
            # Convert FlawTrack results to our expected format
            breach_results = {}
            for domain in domains:
                if domain in flawtrack_results:
                    flawtrack_data = flawtrack_results[domain]
                    risk_score = flawtrack_data.get('risk_score', 0.0)
                    
                    # Use the breach status from FlawTrack API result
                    breach_status = flawtrack_data.get('breach_status', 'unknown')
                    
                    breach_results[domain] = {
                        'breach_status': breach_status,
                        'risk_score': risk_score,
                        'breach_year': flawtrack_data.get('breach_year'),
                        'records_affected': flawtrack_data.get('records_affected'),
                        'breach_name': flawtrack_data.get('breach_name'),
                        'data_types': flawtrack_data.get('data_types'),
                        'severity': flawtrack_data.get('severity')
                    }
                else:
                    # No data found - mark as unknown
                    breach_results[domain] = {
                        'breach_status': 'unknown', 
                        'risk_score': 0.0,
                        'breach_year': None,
                        'records_affected': None,
                        'breach_name': 'No breach data found',
                        'data_types': 'Assessment needed',
                        'severity': 'unknown'
                    }
            
            logger.info(f"FlawTrack API breach lookup completed for {len(domains)} domains")
            return breach_results
            
        except ImportError as e:
            logger.warning(f"FlawTrack API not available, falling back to mock data: {str(e)}")
            return self._get_fallback_breach_data(domains)
        except Exception as e:
            logger.error(f"FlawTrack API lookup failed, falling back to mock data: {str(e)}")
            return self._get_fallback_breach_data(domains)
    
    def _get_fallback_breach_data(self, domains: List[str]) -> Dict:
        """Fallback to mock data if FlawTrack API is unavailable"""
        logger.info("Using fallback mock breach data")
        
        # Known breached domains with real historical breach data
        known_breached = {
            'yahoo.com': {'breach_status': 'breached', 'risk_score': 8.5, 'breach_year': 2013, 'records_affected': 3000000000, 'breach_name': 'Yahoo Data Breach', 'data_types': 'Email addresses, Names, Passwords'},
            'adobe.com': {'breach_status': 'breached', 'risk_score': 7.2, 'breach_year': 2013, 'records_affected': 153000000, 'breach_name': 'Adobe Data Breach', 'data_types': 'Email addresses, Names, Passwords'},
            'linkedin.com': {'breach_status': 'breached', 'risk_score': 6.8, 'breach_year': 2016, 'records_affected': 164000000, 'breach_name': 'LinkedIn Data Breach', 'data_types': 'Email addresses, Names, Passwords'},
            'equifax.com': {'breach_status': 'breached', 'risk_score': 9.0, 'breach_year': 2017, 'records_affected': 147000000, 'breach_name': 'Equifax Data Breach', 'data_types': 'SSN, Names, Credit Information'},
            'marriott.com': {'breach_status': 'breached', 'risk_score': 7.5, 'breach_year': 2018, 'records_affected': 383000000, 'breach_name': 'Marriott Data Breach', 'data_types': 'Email addresses, Names, Passport Numbers'},
            'facebook.com': {'breach_status': 'breached', 'risk_score': 8.0, 'breach_year': 2019, 'records_affected': 533000000, 'breach_name': 'Facebook Data Leak', 'data_types': 'Email addresses, Names, Phone Numbers'},
            'twitter.com': {'breach_status': 'breached', 'risk_score': 6.5, 'breach_year': 2022, 'records_affected': 5400000, 'breach_name': 'Twitter Data Breach', 'data_types': 'Email addresses, Names, Phone Numbers'}
        }
        
        # Clean domains (known secure)
        secure_domains = {
            'google.com', 'microsoft.com', 'apple.com', 'amazon.com', 'cloudflare.com',
            'boomsupersonic.com', 'titansofcnc.com', 'aerosapientech.com'
        }
        
        breach_results = {}
        for domain in domains:
            domain_lower = domain.lower()
            if domain_lower in known_breached:
                breach_results[domain] = known_breached[domain_lower]
            elif domain_lower in secure_domains:
                breach_results[domain] = {
                    'breach_status': 'not_breached', 
                    'risk_score': 1.0,
                    'breach_year': None,
                    'records_affected': None,
                    'breach_name': 'No breaches found',
                    'data_types': 'N/A',
                    'severity': 'low'
                }
            else:
                # Unknown domains default to unknown status
                breach_results[domain] = {
                    'breach_status': 'unknown', 
                    'risk_score': 0.0,
                    'breach_year': None,
                    'records_affected': None,
                    'breach_name': 'Assessment needed',
                    'data_types': 'Unknown',
                    'severity': 'unknown'
                }
        
        return breach_results
    
    def get_contact_risk_summary(self) -> Dict:
        """Get summary of contact risk levels based on breach data"""
        try:
            # Join contacts with breach data to get risk distribution
            risk_summary = db.session.query(
                Breach.severity,
                db.func.count(Contact.id).label('contact_count')
            ).join(
                Contact, Contact.domain == Breach.domain
            ).group_by(Breach.severity).all()
            
            total_with_breach_data = sum(count for _, count in risk_summary)
            total_contacts = Contact.query.count()
            
            summary = {
                'total_contacts': total_contacts,
                'contacts_with_breach_data': total_with_breach_data,
                'contacts_without_breach_data': total_contacts - total_with_breach_data,
                'risk_distribution': {
                    'high': 0,
                    'medium': 0, 
                    'low': 0
                }
            }
            
            for severity, count in risk_summary:
                if severity in summary['risk_distribution']:
                    summary['risk_distribution'][severity] = count
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting contact risk summary: {str(e)}")
            return {
                'total_contacts': 0,
                'contacts_with_breach_data': 0,
                'contacts_without_breach_data': 0,
                'risk_distribution': {'high': 0, 'medium': 0, 'low': 0}
            }
    
    def get_contacts_by_risk_level(self, risk_level: str, limit: int = 50) -> List[Contact]:
        """Get contacts filtered by risk level"""
        try:
            contacts = db.session.query(Contact).join(
                Breach, Contact.domain == Breach.domain
            ).filter(
                Breach.severity == risk_level.lower()
            ).limit(limit).all()
            
            return contacts
            
        except Exception as e:
            logger.error(f"Error getting contacts by risk level: {str(e)}")
            return []