#!/usr/bin/env python
"""Test script to verify the complete flow: Upload -> Scan -> Auto-enroll -> Immediate email"""

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
from services.background_scanner import BackgroundScanner
import json

def test_complete_flow():
    """Test the complete flow with a test contact"""
    
    app = create_app()
    
    with app.app_context():
        # Clean up any existing test contact
        test_email = "testflow@example.com"
        existing_contact = Contact.query.filter_by(email=test_email).first()
        if existing_contact:
            db.session.delete(existing_contact)
            db.session.commit()
        
        # 1. Create a test contact (simulates upload)
        contact = Contact(
            email=test_email,
            first_name="Flow",
            last_name="Test",
            company="Test Company",
            domain="example.com",
            breach_status="unknown",
            is_active=True
        )
        db.session.add(contact)
        db.session.commit()
        print(f"[STEP 1] Created test contact: {contact.email} (ID: {contact.id})")
        
        # 2. Get active campaigns for auto-enrollment preferences
        campaigns = Campaign.query.filter_by(status='active').all()
        if len(campaigns) < 1:
            print("[ERROR] Need at least 1 active campaign for testing")
            return False
        
        # Set up campaign preferences (simulates user selection)
        campaign_preferences = {
            'breached_campaign_id': campaigns[0].id,
            'secure_campaign_id': campaigns[0].id if len(campaigns) == 1 else campaigns[1].id if len(campaigns) > 1 else campaigns[0].id
        }
        print(f"[INFO] Using campaign preferences: {campaign_preferences}")
        
        # 3. Trigger background scanning with auto-enrollment
        scanner = BackgroundScanner()
        
        # Start background scan with our contact
        job_id = scanner.start_background_scan(
            contact_ids=[contact.id],
            campaign_preferences=campaign_preferences
        )
        
        print(f"[STEP 2] Started background scan job: {job_id}")
        
        # Wait for the job to process (simulate background processing)
        import time
        max_wait = 30
        wait_time = 0
        
        while wait_time < max_wait:
            # Check if job is complete
            if job_id in scanner.results:
                result = scanner.results[job_id]
                print(f"[STEP 3] Background scan completed: {result.get('message', 'No message')}")
                break
            elif job_id in scanner.active_jobs:
                job = scanner.active_jobs[job_id]
                print(f"[INFO] Job status: {job.get('status', 'unknown')} - {job.get('message', 'Processing...')}")
            
            time.sleep(2)
            wait_time += 2
        
        if wait_time >= max_wait:
            print("[ERROR] Job didn't complete within 30 seconds")
            return False
        
        # 4. Check final results
        # Refresh contact from database
        contact = Contact.query.get(contact.id)
        print(f"[STEP 4] Final contact breach status: {contact.breach_status}")
        
        # Check if emails were sent
        from models.database import Email, EmailSequence
        
        # Check Email table
        emails = Email.query.filter_by(contact_id=contact.id).all()
        print(f"[RESULT] Found {len(emails)} emails in Email table")
        for email in emails:
            print(f"  - Email ID {email.id}: {email.status} (sent_at: {email.sent_at})")
        
        # Check EmailSequence table
        sequences = EmailSequence.query.filter_by(contact_id=contact.id).all()
        print(f"[RESULT] Found {len(sequences)} sequences in EmailSequence table")
        for seq in sequences:
            print(f"  - Sequence step {seq.sequence_step}: {seq.status} (sent_at: {seq.sent_at})")
        
        # Success criteria: At least one email should be sent (not pending)
        sent_emails = [e for e in emails if e.status == 'sent']
        sent_sequences = [s for s in sequences if s.status == 'sent']
        
        if sent_emails or sent_sequences:
            print("[SUCCESS] Complete flow working! Emails were sent immediately after auto-enrollment.")
            return True
        else:
            print("[ERROR] No emails were sent. Flow incomplete.")
            return False

if __name__ == "__main__":
    success = test_complete_flow()
    sys.exit(0 if success else 1)