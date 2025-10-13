#!/usr/bin/env python3
"""
Register the ngrok webhook URL with Brevo API
This script will set up the webhook to receive real-time email events
"""

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
from services.webhook_manager import create_webhook_manager

def main():
    print("=" * 60)
    print("BREVO WEBHOOK REGISTRATION")
    print("=" * 60)

    # Create Flask app context
    app = create_app()

    with app.app_context():
        # Create webhook manager
        webhook_manager = create_webhook_manager()

        # Get current webhook URL
        current_url = webhook_manager.get_webhook_url()
        print(f"Current webhook URL: {current_url}")

        if "localhost" in current_url:
            print("ERROR: Webhook URL is still set to localhost!")
            print("Please update the BREVO_WEBHOOK_URL in your .env file to use ngrok URL")
            return

        print(f"Checking existing webhooks...")

        # List existing webhooks
        existing_webhooks = webhook_manager.list_existing_webhooks()
        print(f"Found {len(existing_webhooks)} existing webhooks:")

        for webhook in existing_webhooks:
            print(f"  - ID: {webhook['id']} | URL: {webhook['url']} | Type: {webhook['type']}")
            print(f"    Events: {', '.join(webhook['events'])}")

        print("\nSetting up webhooks...")

        # Setup webhooks (this will create or update as needed)
        results = webhook_manager.setup_webhooks(force_recreate=True)

        print("\nResults:")
        if results['success']:
            print("SUCCESS: Webhook setup completed successfully!")
            for message in results['messages']:
                print(f"  + {message}")

            if results['webhooks_created']:
                print(f"  Created {results['webhooks_created']} new webhook(s)")
            if results['webhooks_updated']:
                print(f"  Updated {results['webhooks_updated']} webhook(s)")

        else:
            print("ERROR: Webhook setup failed!")
            for error in results['errors']:
                print(f"  - {error}")

        print("\nTesting webhook connectivity...")
        test_results = webhook_manager.test_webhook_connectivity()

        print(f"  Webhook URL: {test_results['webhook_url']}")
        print(f"  API Key Configured: {'Yes' if test_results['api_key_configured'] else 'No'}")
        print(f"  Webhook Secret: {'Yes' if test_results['webhook_secret_configured'] else 'No'}")
        print(f"  Existing Webhooks: {test_results['existing_webhooks_count']}")
        print(f"  Connectivity: {test_results['connectivity_test']}")

        if test_results['errors']:
            print("  Errors:")
            for error in test_results['errors']:
                print(f"    * {error}")

        print("\n" + "=" * 60)
        print("Webhook registration complete!")
        print("Your Brevo webhooks should now be sending events to your ngrok URL.")
        print("Check your app logs to see incoming webhook events.")
        print("=" * 60)

if __name__ == "__main__":
    main()