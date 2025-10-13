#!/usr/bin/env python
"""Clean up unknown email records from Real-Time Email Activity"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
basedir = os.path.abspath(os.path.dirname(__file__))
env_file = os.path.join(basedir, 'env')
if os.path.exists(env_file):
    load_dotenv(env_file)

# Add project directory to path
sys.path.insert(0, basedir)

from app import create_app
from models.database import db, Contact, Email, EmailSequence, ContactCampaignStatus

def cleanup_unknown_emails():
    """Remove unknown email records"""
    
    app = create_app()
    
    with app.app_context():
        print("=== CLEANING UP UNKNOWN EMAIL RECORDS ===")
        
        # Check current state
        all_contacts = Contact.query.all()
        all_emails = Email.query.all()
        all_sequences = EmailSequence.query.all()
        all_statuses = ContactCampaignStatus.query.all()
        
        print(f"Current state:")
        print(f"  Contacts: {len(all_contacts)}")
        print(f"  Emails: {len(all_emails)}")
        print(f"  Email Sequences: {len(all_sequences)}")
        print(f"  Contact Campaign Statuses: {len(all_statuses)}")
        
        if all_contacts:
            print("  Existing contacts:")
            for contact in all_contacts:
                print(f"    - {contact.email} (ID: {contact.id})")
        
        if all_emails:
            print("  Existing emails:")
            for email in all_emails:
                contact_email = "UNKNOWN"
                if email.contact_id:
                    contact = Contact.query.get(email.contact_id)
                    if contact:
                        contact_email = contact.email
                    else:
                        contact_email = f"MISSING_CONTACT_{email.contact_id}"
                
                print(f"    - Email ID {email.id}: {email.status} to {contact_email} (sent_at: {email.sent_at})")
        
        # Find and delete all email-related records (since we want a clean slate)
        deleted_sequences = 0
        deleted_emails = 0
        deleted_statuses = 0
        deleted_contacts = 0
        
        if all_sequences:
            deleted_sequences = len(all_sequences)
            EmailSequence.query.delete()
            print(f"Deleted {deleted_sequences} email sequences")
        
        if all_emails:
            deleted_emails = len(all_emails)
            Email.query.delete()
            print(f"Deleted {deleted_emails} emails")
        
        if all_statuses:
            deleted_statuses = len(all_statuses)
            ContactCampaignStatus.query.delete()
            print(f"Deleted {deleted_statuses} contact campaign statuses")
        
        if all_contacts:
            deleted_contacts = len(all_contacts)
            Contact.query.delete()
            print(f"Deleted {deleted_contacts} contacts")
        
        # Commit the changes
        db.session.commit()
        
        print("\n=== FINAL STATE ===")
        
        # Verify cleanup
        remaining_contacts = Contact.query.all()
        remaining_emails = Email.query.all()
        remaining_sequences = EmailSequence.query.all()
        remaining_statuses = ContactCampaignStatus.query.all()
        
        print(f"Remaining records:")
        print(f"  Contacts: {len(remaining_contacts)}")
        print(f"  Emails: {len(remaining_emails)}")
        print(f"  Email Sequences: {len(remaining_sequences)}")
        print(f"  Contact Campaign Statuses: {len(remaining_statuses)}")
        
        if len(remaining_contacts) == 0 and len(remaining_emails) == 0 and len(remaining_sequences) == 0 and len(remaining_statuses) == 0:
            print("Real-Time Email Activity is now completely clean!")
        else:
            print("Some records still remain:")
            for contact in remaining_contacts:
                print(f"  - Contact: {contact.email}")
            for email in remaining_emails:
                print(f"  - Email: ID {email.id}")

if __name__ == "__main__":
    cleanup_unknown_emails()