#!/usr/bin/env python3
"""Debug script to analyze email sequences and approval workflow"""

import os
import sys
sys.path.append('/home/savetyonline')

from app import create_app, db
from models.database import Email, Contact, Campaign, ContactCampaignStatus, EmailSequence
from datetime import datetime

def debug_sequences():
    app = create_app()
    with app.app_context():
        print("=== PENDING APPROVAL EMAILS ===")
        pending_emails = Email.query.filter_by(approval_status='awaiting_approval').all()
        print(f"Found {len(pending_emails)} pending approval emails:")
        for email in pending_emails:
            print(f"  Email ID: {email.id}")
            print(f"  Contact: {email.contact.email}")
            print(f"  Campaign: {email.campaign.name}")
            print(f"  Subject: {email.subject[:50]}...")
            print(f"  Status: {email.status}")
            print(f"  Approval Status: {email.approval_status}")
            print(f"  Created: {email.created_at}")
            print("  ---")

        print("\n=== ALL EMAILS FOR NON-BREACHED CAMPAIGN ===")
        non_breached_campaign = Campaign.query.filter_by(name='Non-Breached Campaign').first()
        if non_breached_campaign:
            all_emails = Email.query.filter_by(campaign_id=non_breached_campaign.id).all()
            print(f"Found {len(all_emails)} total emails for Non-Breached Campaign:")
            for email in all_emails:
                # Find corresponding sequence
                sequence = EmailSequence.query.filter_by(email_id=email.id).first()
                step = sequence.sequence_step if sequence else "Unknown"
                print(f"  Email ID: {email.id}, Step: {step}")
                print(f"  Contact: {email.contact.email}")
                print(f"  Subject: {email.subject[:50]}...")
                print(f"  Status: {email.status}")
                print(f"  Approval Status: {email.approval_status}")
                print(f"  Created: {email.created_at}")
                print("  ---")

        print("\n=== EMAIL SEQUENCES FOR NON-BREACHED CAMPAIGN ===")
        if non_breached_campaign:
            sequences = EmailSequence.query.filter_by(campaign_id=non_breached_campaign.id).order_by(EmailSequence.sequence_step).all()
            print(f"Found {len(sequences)} email sequences:")
            for seq in sequences:
                print(f"  Sequence ID: {seq.id}")
                print(f"  Contact: {seq.contact_id}")
                print(f"  Step: {seq.sequence_step}")
                print(f"  Status: {seq.status}")
                print(f"  Email ID: {seq.email_id}")
                if seq.email_id:
                    email = Email.query.get(seq.email_id)
                    if email:
                        print(f"  Email Status: {email.status}")
                        print(f"  Email Approval: {email.approval_status}")
                    else:
                        print(f"  Email: NOT FOUND")
                print(f"  Scheduled: {seq.scheduled_datetime}")
                print("  ---")

        print("\n=== CAMPAIGN STATUS ===")
        statuses = ContactCampaignStatus.query.all()
        for status in statuses:
            campaign = Campaign.query.get(status.campaign_id)
            contact = Contact.query.get(status.contact_id)
            print(f"Contact {contact.email if contact else status.contact_id}, Campaign {campaign.name if campaign else status.campaign_id}:")
            print(f"  Current Step: {status.current_step}")
            print(f"  Last Step: {status.last_step_completed}")
            print(f"  Status: {status.status}")
            print("  ---")

if __name__ == '__main__':
    debug_sequences()