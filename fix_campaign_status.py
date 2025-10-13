#!/usr/bin/env python3
"""Fix campaign status tracking for approval workflow"""

import os
import sys
sys.path.append('/home/savetyonline')

from app import create_app, db
from models.database import Email, Contact, Campaign, ContactCampaignStatus, EmailSequence

def fix_campaign_status():
    app = create_app()
    with app.app_context():
        print("=== CHECKING CAMPAIGN STATUS ===")

        # Get Non-Breached Campaign
        campaign = Campaign.query.filter_by(name='Non-Breached Campaign').first()
        if not campaign:
            print("Non-Breached Campaign not found!")
            return

        # Get Contact 1
        contact = Contact.query.get(1)
        if not contact:
            print("Contact 1 not found!")
            return

        print(f"Campaign: {campaign.name} (ID: {campaign.id})")
        print(f"Contact: {contact.email} (ID: {contact.id})")

        # Check current status
        status = ContactCampaignStatus.query.filter_by(
            contact_id=contact.id,
            campaign_id=campaign.id
        ).first()

        if status:
            print(f"Current Status - Current Step: {status.current_sequence_step}")
            print(f"Current Status - Breach Status: {status.breach_status}")
            print(f"Current Status - Replied At: {status.replied_at}")
            print(f"Current Status - Completed At: {status.sequence_completed_at}")
        else:
            print("No ContactCampaignStatus found - creating one...")
            status = ContactCampaignStatus(
                contact_id=contact.id,
                campaign_id=campaign.id,
                current_sequence_step=0,
                breach_status='not_breached'
            )
            db.session.add(status)

        # Check what emails have been sent
        sent_emails = Email.query.filter_by(
            contact_id=contact.id,
            campaign_id=campaign.id
        ).filter(Email.status.in_(['delivered', 'sent'])).all()

        print(f"\nFound {len(sent_emails)} sent/delivered emails:")
        max_step_sent = -1
        for email in sent_emails:
            # Find the sequence step for this email
            sequence = EmailSequence.query.filter_by(email_id=email.id).first()
            if sequence:
                step = sequence.sequence_step
                print(f"  Email ID {email.id}: Step {step}, Status: {email.status}")
                max_step_sent = max(max_step_sent, step)
            else:
                print(f"  Email ID {email.id}: No sequence found, Status: {email.status}")

        print(f"\nHighest step sent: {max_step_sent}")

        # Update the campaign status to reflect reality
        if max_step_sent >= 0:
            new_current_step = max_step_sent + 1  # Next step to process
            status.current_sequence_step = new_current_step
            print(f"\nUpdating campaign status:")
            print(f"  New current step: {new_current_step}")
            print(f"  Highest step sent: {max_step_sent}")

            db.session.commit()
            print("Campaign status updated successfully!")
        else:
            print("No emails sent yet, keeping current status")

if __name__ == '__main__':
    fix_campaign_status()