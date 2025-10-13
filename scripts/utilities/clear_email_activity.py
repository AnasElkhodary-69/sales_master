#!/usr/bin/env python3
"""
Clear Email Activity Data Script for SalesBreachPro
Removes all email tracking data to start fresh
"""
from models.database import db, Email, EmailSequence, ContactCampaignStatus
from app import create_app

def clear_email_activity():
    """Clear all email activity data"""
    app = create_app()

    with app.app_context():
        try:
            print("Clearing email activity data...")

            # Clear email tracking data but keep the email records
            emails_updated = db.session.query(Email).update({
                'delivered_at': None,
                'opened_at': None,
                'clicked_at': None,
                'replied_at': None,
                'bounced_at': None,
                'open_count': 0,
                'click_count': 0
            })

            print(f"Cleared activity data from {emails_updated} email records")

            # Reset email sequences status if needed (optional)
            # sequences_updated = db.session.query(EmailSequence).filter(
            #     EmailSequence.status.in_(['skipped_replied', 'skipped_unsubscribed'])
            # ).update({'status': 'scheduled'})
            # print(f"Reset {sequences_updated} email sequences")

            db.session.commit()
            print("[OK] Email activity data cleared successfully!")

        except Exception as e:
            print(f"[ERROR] Error clearing email activity: {e}")
            db.session.rollback()

if __name__ == "__main__":
    clear_email_activity()