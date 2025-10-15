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
        
    def process_csv_file(self, file_path: str, progress_callback=None) -> Dict:
        """
        Process uploaded CSV file and return validation results

        Args:
            file_path: Path to CSV file

        Returns:
            Dict with processing results including valid/invalid counts
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
            
            # Validate and create contacts
            valid_contacts = []
            total_rows = len(contacts_data)

            if progress_callback:
                progress_callback("Validating contacts...", 20, total_rows=total_rows)

            # Validate all contacts
            for idx, contact_data in enumerate(contacts_data):
                try:
                    # Update progress during validation
                    if progress_callback and idx % 10 == 0:
                        validation_progress = 20 + (idx / total_rows) * 40  # 20-60%
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
                    else:
                        results['invalid_contacts'] += 1
                        results['errors'].extend([f"Row {idx + 1}: {error}" for error in validation_result['errors']])

                except Exception as e:
                    results['invalid_contacts'] += 1
                    results['errors'].append(f"Row {idx + 1}: {str(e)}")

            # Create contacts
            valid_count = len(valid_contacts)
            if progress_callback:
                progress_callback("Creating contacts...", 70, contacts_created=0, total_contacts=valid_count)

            for idx, (row_num, contact_data) in enumerate(valid_contacts):
                try:
                    # Update progress during contact creation
                    if progress_callback and idx % 5 == 0:
                        creation_progress = 70 + (idx / valid_count) * 25  # 70-95%
                        progress_callback(f"Creating contact {idx + 1} of {valid_count}...", creation_progress, contacts_created=idx, total_contacts=valid_count)

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
                business_type=contact_data.get('business_type'),
                company_size=contact_data.get('company_size'),
                status='active'
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
    
