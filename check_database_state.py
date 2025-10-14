#!/usr/bin/env python3
"""
Check the current database state after the workflow test
"""

import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.database import db, Contact, Campaign, Email, EmailTemplate, EmailSequenceConfig

def check_database_state():
    """Check the current state of the database"""
    print("=" * 60)
    print(f"DATABASE STATE CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    app = create_app()
    with app.app_context():
        # Check contacts
        contacts = Contact.query.all()
        print(f"\n📧 CONTACTS ({len(contacts)}):")
        for contact in contacts:
            print(f"  - {contact.email} (ID: {contact.id})")
            print(f"    Status: {contact.breach_status}")
            print(f"    Company: {contact.company}")
            print(f"    Created: {contact.created_at}")
            if contact.breach_count:
                print(f"    Breach Count: {contact.breach_count}")
            if contact.breach_details:
                print(f"    Breach Details: {contact.breach_details}")

        # Check campaigns
        campaigns = Campaign.query.all()
        print(f"\n🎯 CAMPAIGNS ({len(campaigns)}):")
        for campaign in campaigns:
            print(f"  - {campaign.name} (ID: {campaign.id})")
            print(f"    Type: {campaign.template_type}")
            print(f"    Status: {campaign.status}")
            print(f"    Target Risk: {campaign.target_risk_levels}")

        # Check templates
        templates = EmailTemplate.query.all()
        print(f"\n📝 TEMPLATES ({len(templates)}):")
        for template in templates:
            print(f"  - {template.name} (ID: {template.id})")
            print(f"    Type: {template.template_type}")
            print(f"    Risk: {template.risk_level}")
            print(f"    Subject: {template.subject_line}")

        # Check sequences
        sequences = EmailSequenceConfig.query.all()
        print(f"\n🔄 FOLLOW-UP SEQUENCES ({len(sequences)}):")
        for sequence in sequences:
            print(f"  - {sequence.name} (ID: {sequence.id})")
            print(f"    Risk Level: {sequence.risk_level}")
            print(f"    Active: {sequence.is_active}")
            print(f"    Max Follow-ups: {sequence.max_follow_ups}")
            if sequence.steps:
                print(f"    Steps ({len(sequence.steps)}):")
                for step in sequence.steps:
                    delay = step.get('delay_minutes', 0)
                    print(f"      Step {step.get('step', '?')}: {delay} minutes delay")

        # Check emails
        emails = Email.query.all()
        print(f"\n📬 EMAILS ({len(emails)}):")
        if emails:
            for email in emails:
                contact_email = email.contact.email if email.contact else "Unknown"
                print(f"  - To: {contact_email} (ID: {email.id})")
                print(f"    Status: {email.status}")
                print(f"    Subject: {email.subject}")
                print(f"    Scheduled: {email.scheduled_for}")
                print(f"    Created: {email.created_at}")
                if email.sent_at:
                    print(f"    Sent: {email.sent_at}")
        else:
            print("  No emails found in database")

        print("\n" + "=" * 60)
        print("END DATABASE STATE CHECK")
        print("=" * 60)

if __name__ == "__main__":
    check_database_state()