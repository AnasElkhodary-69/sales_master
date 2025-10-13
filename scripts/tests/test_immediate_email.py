#!/usr/bin/env python
"""Test script to manually enroll a contact and test immediate email sending"""

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
from models.database import db, Contact, Campaign
from services.email_sequence_service import EmailSequenceService

def test_immediate_enrollment():
    """Test enrolling a contact and sending immediate email"""
    
    app = create_app()
    
    with app.app_context():
        # Get or create a test contact
        test_email = "ultimate@example.com"
        contact = Contact.query.filter_by(email=test_email).first()
        
        if not contact:
            contact = Contact(
                email=test_email,
                first_name="John",
                last_name="Doe",
                company="Test Company",
                domain="example.com",
                breach_status="unknown",
                is_active=True
            )
            db.session.add(contact)
            db.session.commit()
            print(f"[INFO] Created test contact: {contact.email}")
        else:
            print(f"[INFO] Using existing contact: {contact.email}")
        
        # Get the active campaign
        campaign = Campaign.query.filter_by(status='active').first()
        if not campaign:
            print("[ERROR] No active campaign found!")
            return False
        
        print(f"[INFO] Using campaign: {campaign.name}")
        
        # Test enrollment with immediate sending
        email_service = EmailSequenceService()
        
        try:
            result = email_service.enroll_contact_in_campaign(
                contact_id=contact.id,
                campaign_id=campaign.id,
                force_breach_check=False
            )
            
            print(f"[RESULT] Enrollment result: {result}")
            
            if result['success']:
                print(f"[SUCCESS] Contact enrolled successfully!")
                print(f"  - Breach status: {result['breach_status']}")
                print(f"  - Template type: {result['template_type']}")
                print(f"  - Emails scheduled: {result['emails_scheduled']}")
                
                # Check if email was sent
                from models.database import Email, EmailSequence
                
                # Check Email table for sent emails
                sent_emails = Email.query.filter_by(
                    contact_id=contact.id,
                    campaign_id=campaign.id
                ).all()
                
                print(f"[INFO] Found {len(sent_emails)} emails in Email table")
                for email in sent_emails:
                    print(f"  - Email ID {email.id}: {email.status} (sent_at: {email.sent_at})")
                
                # Check EmailSequence table
                sequences = EmailSequence.query.filter_by(
                    contact_id=contact.id,
                    campaign_id=campaign.id
                ).all()
                
                print(f"[INFO] Found {len(sequences)} sequences in EmailSequence table")
                for seq in sequences:
                    print(f"  - Sequence step {seq.sequence_step}: {seq.status} (sent_at: {seq.sent_at})")
                    
                return True
            else:
                print(f"[ERROR] Enrollment failed: {result.get('error')}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Exception during enrollment: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_immediate_enrollment()
    sys.exit(0 if success else 1)