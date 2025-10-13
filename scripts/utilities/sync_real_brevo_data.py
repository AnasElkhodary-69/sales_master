#!/usr/bin/env python
"""
Sync Real Brevo Data - Get actual tracking events from Brevo API
"""

import os
import sys
import requests
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

def sync_real_brevo_data():
    """Fetch actual tracking data from Brevo API"""
    app = create_app()

    with app.app_context():
        print("=== SYNCING REAL BREVO TRACKING DATA ===")

        # Get Brevo API credentials
        api_key = os.environ.get('BREVO_API_KEY')
        if not api_key:
            print("ERROR: BREVO_API_KEY not found in environment variables")
            return

        print(f"Using Brevo API Key: {api_key[:10]}...")

        # Get all emails with Brevo message IDs
        emails = Email.query.filter(Email.brevo_message_id.isnot(None)).all()

        if not emails:
            print("No emails found with Brevo message IDs")
            return

        print(f"Found {len(emails)} emails to sync with Brevo")

        headers = {
            'Accept': 'application/json',
            'api-key': api_key
        }

        for email in emails:
            print(f"\n--- Syncing Email {email.id} ---")
            print(f"Brevo Message ID: {email.brevo_message_id}")
            print(f"Sent to: {email.contact.email if email.contact else 'Unknown'}")

            try:
                # Get email events from Brevo API
                # Use the email events endpoint
                url = f"https://api.brevo.com/v3/emailCampaigns/{email.brevo_message_id}/events"

                # Alternative approach - get account activity
                activity_url = "https://api.brevo.com/v3/emailCampaigns"

                # Try to get campaign statistics first
                response = requests.get(activity_url, headers=headers)

                if response.status_code == 200:
                    print("Successfully connected to Brevo API")
                    campaigns = response.json()
                    print(f"Found {len(campaigns.get('campaigns', []))} campaigns")
                else:
                    print(f"Brevo API Error: {response.status_code} - {response.text}")

                # Try to get email statistics using different approach
                stats_url = f"https://api.brevo.com/v3/smtp/statistics/events"
                params = {
                    'limit': 50,
                    'offset': 0,
                    'startDate': (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d'),
                    'endDate': datetime.utcnow().strftime('%Y-%m-%d'),
                    'email': email.contact.email if email.contact else None
                }

                response = requests.get(stats_url, headers=headers, params=params)

                if response.status_code == 200:
                    events_data = response.json()
                    events = events_data.get('events', [])

                    print(f"Found {len(events)} events for this email address")

                    # Process events for this specific email
                    for event in events:
                        if event.get('messageId') == email.brevo_message_id:
                            event_type = event.get('event', '').lower()
                            event_date = event.get('date')

                            print(f"Real Brevo Event: {event_type} at {event_date}")

                            # Update database with real data
                            if event_type == 'delivered':
                                email.delivered_at = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                email.status = 'delivered'
                            elif event_type == 'opened':
                                email.opened_at = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                email.open_count = (email.open_count or 0) + 1
                                email.status = 'opened'
                            elif event_type == 'clicked':
                                email.clicked_at = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                email.click_count = (email.click_count or 0) + 1
                                email.status = 'clicked'
                            elif event_type == 'replied':
                                email.replied_at = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                email.status = 'replied'
                            elif event_type == 'bounced':
                                email.bounced_at = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                email.status = 'bounced'

                    if not any(event.get('messageId') == email.brevo_message_id for event in events):
                        print("No specific events found for this message ID")
                else:
                    print(f"Error getting events: {response.status_code} - {response.text}")

            except Exception as e:
                print(f"Error syncing email {email.id}: {e}")

        # Commit real data to database
        db.session.commit()
        print("\n=== SYNC COMPLETE ===")
        print("Updated database with real Brevo tracking data")

        # Show final results
        print("\n=== FINAL REAL TRACKING STATUS ===")
        for email in emails:
            print(f"Email {email.id}: {email.status}")
            print(f"  Delivered: {email.delivered_at}")
            print(f"  Opened: {email.opened_at} (count: {email.open_count or 0})")
            print(f"  Clicked: {email.clicked_at} (count: {email.click_count or 0})")
            print(f"  Replied: {email.replied_at}")

if __name__ == "__main__":
    sync_real_brevo_data()