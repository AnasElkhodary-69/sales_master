#!/usr/bin/env python
"""Clean up test emails from the database"""

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

def cleanup_test_emails():
    """Remove all test emails and related data"""
    
    app = create_app()
    
    with app.app_context():
        print("=== BEFORE CLEANUP ===")
        
        # Show current state
        all_contacts = Contact.query.all()
        all_emails = Email.query.all()
        all_sequences = EmailSequence.query.all()
        all_statuses = ContactCampaignStatus.query.all()
        
        print(f"Contacts: {len(all_contacts)}")
        for contact in all_contacts:
            print(f"  - {contact.email} (ID: {contact.id})")
        
        print(f"Emails: {len(all_emails)}")
        for email in all_emails:
            print(f"  - Email ID {email.id}: {email.status} to contact {email.contact_id} (sent_at: {email.sent_at})")
        
        print(f"Email Sequences: {len(all_sequences)}")
        for seq in all_sequences:
            print(f"  - Sequence ID {seq.id}: Step {seq.sequence_step}, {seq.status} for contact {seq.contact_id}")
        
        print(f"Contact Campaign Statuses: {len(all_statuses)}")
        for status in all_statuses:
            print(f"  - Status ID {status.id}: Contact {status.contact_id}, Campaign {status.campaign_id}")
        
        # Identify test contacts (those with test domains)
        test_domains = ['example.com', 'test.com', 'demo.com']
        test_contacts = Contact.query.filter(
            Contact.email.like('%@example.com') |
            Contact.email.like('%@test.com') |
            Contact.email.like('%@demo.com') |
            Contact.email.like('%test%') |
            Contact.email.like('%demo%')
        ).all()
        
        print(f"\n=== FOUND {len(test_contacts)} TEST CONTACTS TO DELETE ===")
        for contact in test_contacts:
            print(f"  - {contact.email} (ID: {contact.id})")
        
        if test_contacts:
            test_contact_ids = [c.id for c in test_contacts]
            
            # Delete associated records first (foreign key constraints)
            print("\n=== DELETING ASSOCIATED RECORDS ===")
            
            # Delete EmailSequence records
            deleted_sequences = EmailSequence.query.filter(EmailSequence.contact_id.in_(test_contact_ids)).delete()
            print(f"Deleted {deleted_sequences} email sequences")
            
            # Delete Email records
            deleted_emails = Email.query.filter(Email.contact_id.in_(test_contact_ids)).delete()
            print(f"Deleted {deleted_emails} emails")
            
            # Delete ContactCampaignStatus records
            deleted_statuses = ContactCampaignStatus.query.filter(ContactCampaignStatus.contact_id.in_(test_contact_ids)).delete()
            print(f"Deleted {deleted_statuses} contact campaign statuses")
            
            # Delete Contact records
            deleted_contacts = Contact.query.filter(Contact.id.in_(test_contact_ids)).delete()
            print(f"Deleted {deleted_contacts} test contacts")
            
            # Commit the changes
            db.session.commit()
            print("\n✅ All test data deleted successfully!")
        else:
            print("\n✅ No test contacts found to delete.")
        
        print("\n=== AFTER CLEANUP ===")
        
        # Show final state
        remaining_contacts = Contact.query.all()
        remaining_emails = Email.query.all()
        remaining_sequences = EmailSequence.query.all()
        remaining_statuses = ContactCampaignStatus.query.all()
        
        print(f"Remaining Contacts: {len(remaining_contacts)}")
        for contact in remaining_contacts:
            print(f"  - {contact.email} (ID: {contact.id})")
        
        print(f"Remaining Emails: {len(remaining_emails)}")
        for email in remaining_emails:
            print(f"  - Email ID {email.id}: {email.status} to contact {email.contact_id}")
        
        print(f"Remaining Email Sequences: {len(remaining_sequences)}")
        print(f"Remaining Contact Campaign Statuses: {len(remaining_statuses)}")

if __name__ == "__main__":
    cleanup_test_emails()