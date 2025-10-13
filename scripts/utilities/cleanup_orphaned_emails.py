#!/usr/bin/env python
"""Clean up orphaned email records from the database"""

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

def cleanup_orphaned_emails():
    """Remove all orphaned email records"""
    
    app = create_app()
    
    with app.app_context():
        print("=== CLEANING UP ORPHANED EMAIL RECORDS ===")
        
        # Get all contact IDs that exist
        existing_contact_ids = [c.id for c in Contact.query.all()]
        print(f"Existing contacts: {len(existing_contact_ids)} - {existing_contact_ids}")
        
        # Find orphaned records
        all_emails = Email.query.all()
        all_sequences = EmailSequence.query.all()
        all_statuses = ContactCampaignStatus.query.all()
        
        orphaned_emails = [e for e in all_emails if e.contact_id not in existing_contact_ids]
        orphaned_sequences = [s for s in all_sequences if s.contact_id not in existing_contact_ids]
        orphaned_statuses = [s for s in all_statuses if s.contact_id not in existing_contact_ids]
        
        print(f"Found {len(orphaned_emails)} orphaned emails")
        print(f"Found {len(orphaned_sequences)} orphaned email sequences")
        print(f"Found {len(orphaned_statuses)} orphaned campaign statuses")
        
        if orphaned_emails or orphaned_sequences or orphaned_statuses:
            # Delete orphaned EmailSequence records
            if orphaned_sequences:
                orphaned_seq_ids = [s.id for s in orphaned_sequences]
                deleted_sequences = EmailSequence.query.filter(EmailSequence.id.in_(orphaned_seq_ids)).delete()
                print(f"Deleted {deleted_sequences} orphaned email sequences")
            
            # Delete orphaned Email records
            if orphaned_emails:
                orphaned_email_ids = [e.id for e in orphaned_emails]
                deleted_emails = Email.query.filter(Email.id.in_(orphaned_email_ids)).delete()
                print(f"Deleted {deleted_emails} orphaned emails")
            
            # Delete orphaned ContactCampaignStatus records
            if orphaned_statuses:
                orphaned_status_ids = [s.id for s in orphaned_statuses]
                deleted_statuses = ContactCampaignStatus.query.filter(ContactCampaignStatus.id.in_(orphaned_status_ids)).delete()
                print(f"Deleted {deleted_statuses} orphaned campaign statuses")
            
            # Commit the changes
            db.session.commit()
            print("All orphaned records deleted successfully!")
        else:
            print("No orphaned records found.")
        
        print("\n=== FINAL STATE ===")
        
        # Show final state
        remaining_contacts = Contact.query.all()
        remaining_emails = Email.query.all()
        remaining_sequences = EmailSequence.query.all()
        remaining_statuses = ContactCampaignStatus.query.all()
        
        print(f"Remaining Contacts: {len(remaining_contacts)}")
        print(f"Remaining Emails: {len(remaining_emails)}")
        print(f"Remaining Email Sequences: {len(remaining_sequences)}")
        print(f"Remaining Contact Campaign Statuses: {len(remaining_statuses)}")
        
        if remaining_contacts:
            print("Existing contacts:")
            for contact in remaining_contacts:
                print(f"  - {contact.email} (ID: {contact.id})")

if __name__ == "__main__":
    cleanup_orphaned_emails()