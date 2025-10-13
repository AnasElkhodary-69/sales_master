#!/usr/bin/env python
"""Test the complete email flow with flexible delay units"""

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
from models.database import db, Contact, Campaign, EmailTemplate
from services.email_sequence_service import EmailSequenceService

def test_flexible_delay_flow():
    """Test enrollment with flexible delay scheduling"""
    
    app = create_app()
    
    with app.app_context():
        print("=== TESTING FLEXIBLE DELAY EMAIL FLOW ===")
        
        # Clean up any existing test contact
        test_email = "delay_test@example.com"
        existing_contact = Contact.query.filter_by(email=test_email).first()
        if existing_contact:
            db.session.delete(existing_contact)
            db.session.commit()
        
        # Create a test contact
        contact = Contact(
            email=test_email,
            first_name="Delay",
            last_name="Test",
            company="Test Company",
            domain="example.com", 
            breach_status="unknown",
            is_active=True
        )
        db.session.add(contact)
        db.session.commit()
        print(f"[INFO] Created test contact: {contact.email} (ID: {contact.id})")
        
        # Set up different delays for templates (already done in previous test)
        templates = EmailTemplate.query.filter_by(active=True).limit(4).all()
        if len(templates) >= 4:
            # Set up a variety of delay units
            templates[0].delay_amount = 0
            templates[0].delay_unit = 'minutes'  # Immediate
            
            templates[1].delay_amount = 30
            templates[1].delay_unit = 'minutes'  # 30 minutes later
            
            templates[2].delay_amount = 2  
            templates[2].delay_unit = 'hours'    # 2 hours later
            
            templates[3].delay_amount = 1
            templates[3].delay_unit = 'days'     # 1 day later
            
            db.session.commit()
            
            print("Updated template delays:")
            for i, template in enumerate(templates):
                print(f"  Template {i+1} ({template.name}): {template.delay_amount} {template.delay_unit}")
        
        # Get active campaign
        campaign = Campaign.query.filter_by(status='active').first()
        if not campaign:
            print("[ERROR] No active campaign found!")
            return False
        
        print(f"[INFO] Using campaign: {campaign.name}")
        
        # Test enrollment with flexible delays
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
                
                # Check scheduled emails details
                from models.database import EmailSequence
                sequences = EmailSequence.query.filter_by(contact_id=contact.id).all()
                
                print(f"[DETAILS] Email sequences scheduled:")
                for seq in sequences:
                    template = EmailTemplate.query.get(seq.template_id) if hasattr(seq, 'template_id') else None
                    delay_info = ""
                    if template and hasattr(template, 'delay_amount') and hasattr(template, 'delay_unit'):
                        delay_info = f" (delay: {template.delay_amount} {template.delay_unit})"
                    
                    print(f"  - Step {seq.sequence_step}: {seq.status}, scheduled for {seq.scheduled_date}{delay_info}")
                
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
    success = test_flexible_delay_flow()
    sys.exit(0 if success else 1)