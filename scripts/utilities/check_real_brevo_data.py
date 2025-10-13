#!/usr/bin/env python
"""
Check Real Brevo Data - Get actual tracking data from Brevo API
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
basedir = os.path.abspath(os.path.dirname(__file__))
env_file = os.path.join(basedir, 'env')
if os.path.exists(env_file):
    load_dotenv(env_file)

# Add project directory to path
sys.path.insert(0, basedir)

from models.database import db, Email
from app import create_app

def get_real_brevo_data():
    """Get actual tracking data from Brevo API"""
    app = create_app()

    with app.app_context():
        print("=== CHECKING REAL BREVO TRACKING DATA ===")

        try:
            from services.brevo_modern_service import BrevoModernService
            from config import Config

            # Initialize Brevo service
            brevo_service = BrevoModernService(Config)

            # Get all emails with Brevo message IDs
            emails = Email.query.filter(Email.brevo_message_id.isnot(None)).all()

            if not emails:
                print("No emails found with Brevo message IDs")
                return

            print(f"Found {len(emails)} emails with Brevo tracking IDs")

            for email in emails:
                print(f"\n--- Email {email.id} ---")
                print(f"Brevo Message ID: {email.brevo_message_id}")
                print(f"Sent to: {email.contact.email if email.contact else 'Unknown'}")
                print(f"Sent at: {email.sent_at}")
                print(f"Subject: {email.subject}")

                # Get email statistics from Brevo
                try:
                    # Try to get email events from Brevo
                    email_stats = brevo_service.get_email_events(email.brevo_message_id)

                    if email_stats:
                        print("Real Brevo Events:")
                        for event in email_stats:
                            event_type = event.get('event', 'unknown')
                            timestamp = event.get('date', 'unknown')
                            print(f"  - {event_type}: {timestamp}")
                    else:
                        print("No events found in Brevo for this email")

                except Exception as e:
                    print(f"Error getting Brevo data for this email: {e}")

                # Show current database status for comparison
                print("Current Database Status:")
                print(f"  Status: {email.status}")
                print(f"  Delivered: {email.delivered_at}")
                print(f"  Opened: {email.opened_at}")
                print(f"  Clicked: {email.clicked_at}")
                print(f"  Replied: {email.replied_at}")

        except Exception as e:
            print(f"Error accessing Brevo service: {e}")
            print("\nTrying alternative approach - check Brevo webhook events...")

            # Alternative: Check if we have webhook data stored
            emails = Email.query.all()
            print(f"\nFound {len(emails)} total emails in database:")
            for email in emails:
                print(f"\nEmail {email.id}:")
                print(f"  To: {email.contact.email if email.contact else 'Unknown'}")
                print(f"  Status: {email.status}")
                print(f"  Sent: {email.sent_at}")
                print(f"  Delivered: {email.delivered_at}")
                print(f"  Opened: {email.opened_at} (count: {email.open_count or 0})")
                print(f"  Clicked: {email.clicked_at} (count: {email.click_count or 0})")
                print(f"  Replied: {email.replied_at}")
                print(f"  Brevo Message ID: {email.brevo_message_id}")

if __name__ == "__main__":
    get_real_brevo_data()