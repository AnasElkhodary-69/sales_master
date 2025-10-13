#!/usr/bin/env python3
"""
Ngrok Webhook Setup Helper for SalesBreachPro
Automates ngrok tunnel creation and webhook registration
"""
import os
import sys
import time
import subprocess
import requests
import json
from models.database import db, Settings
from services.webhook_manager import create_webhook_manager

def check_ngrok_installed():
    """Check if ngrok is installed and accessible"""
    try:
        result = subprocess.run(['ngrok', 'version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] Ngrok found: {result.stdout.strip()}")
            return True
        else:
            print("[ERROR] Ngrok not found in PATH")
            return False
    except FileNotFoundError:
        print("[ERROR] Ngrok not installed. Please install from https://ngrok.com/download")
        return False

def get_ngrok_tunnels():
    """Get active ngrok tunnels"""
    try:
        response = requests.get('http://127.0.0.1:4040/api/tunnels')
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except requests.exceptions.RequestException:
        return None

def start_ngrok_tunnel(port=5000):
    """Start ngrok tunnel for the specified port"""
    print(f"[INFO] Starting ngrok tunnel for port {port}...")

    # Check if ngrok is already running
    tunnels = get_ngrok_tunnels()
    if tunnels:
        for tunnel in tunnels.get('tunnels', []):
            if tunnel['config']['addr'] == f'http://localhost:{port}':
                print(f"[OK] Ngrok tunnel already running: {tunnel['public_url']}")
                return tunnel['public_url']

    # Start new ngrok process
    try:
        # Start ngrok in the background
        process = subprocess.Popen(
            ['ngrok', 'http', str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for ngrok to start
        print("[INFO] Waiting for ngrok to start...")
        time.sleep(3)

        # Get tunnel URL
        tunnels = get_ngrok_tunnels()
        if tunnels and tunnels.get('tunnels'):
            tunnel_url = tunnels['tunnels'][0]['public_url']
            print(f"[OK] Ngrok tunnel started: {tunnel_url}")
            return tunnel_url
        else:
            print("[ERROR] Failed to get ngrok tunnel URL")
            return None

    except Exception as e:
        print(f"[ERROR] Error starting ngrok: {e}")
        return None

def update_webhook_settings(webhook_url):
    """Update webhook URL in application settings"""
    try:
        # Initialize database if needed
        from app import create_app
        app = create_app()

        with app.app_context():
            # Update webhook URL in database
            Settings.set_setting('brevo_webhook_url', webhook_url, 'Ngrok webhook URL for testing')
            print(f"[OK] Updated webhook URL in settings: {webhook_url}")

            # Update environment variable for this session
            os.environ['BREVO_WEBHOOK_URL'] = webhook_url
            print("[OK] Updated environment variable")

        return True
    except Exception as e:
        print(f"[ERROR] Error updating webhook settings: {e}")
        return False

def register_webhook_with_brevo(webhook_url):
    """Register webhook with Brevo API"""
    try:
        from app import create_app
        app = create_app()

        with app.app_context():
            # Check if Brevo API key is configured
            brevo_api_key = Settings.get_setting('brevo_api_key', '')
            if not brevo_api_key:
                print("[WARNING] No Brevo API key found in settings.")
                print("   Please configure your Brevo API key in the settings page first.")
                return False

            webhook_manager = create_webhook_manager()

            # Setup webhooks with the new URL
            webhook_url_with_endpoint = f"{webhook_url}/webhooks/brevo"
            print(f"[INFO] Registering webhook with Brevo: {webhook_url_with_endpoint}")
            print(f"[INFO] Using API key: {brevo_api_key[:8]}...")

            # Update the webhook URL in settings first
            Settings.set_setting('brevo_webhook_url', webhook_url_with_endpoint, 'Ngrok webhook URL with endpoint')

            # Setup webhooks
            results = webhook_manager.setup_webhooks(force_recreate=True)

            if results['success']:
                print("[SUCCESS] Webhook registered successfully with Brevo!")
                for message in results['messages']:
                    print(f"   -> {message}")
            else:
                print("[ERROR] Failed to register webhook with Brevo:")
                for error in results['errors']:
                    print(f"   -> {error}")
                print("[INFO] You can manually register the webhook in Brevo dashboard:")
                print(f"   URL: {webhook_url_with_endpoint}")
                print("   Events: delivered, opened, clicked, replied, bounced, complaint, unsubscribed")

            return results['success']

    except Exception as e:
        print(f"[ERROR] Error registering webhook: {e}")
        print("[INFO] You can manually register the webhook later through the settings page")
        return False

def main():
    """Main setup function"""
    print("SalesBreachPro Ngrok Webhook Setup")
    print("=" * 40)

    # Check if ngrok is installed
    if not check_ngrok_installed():
        sys.exit(1)

    # Get port from command line or use default
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}")
            sys.exit(1)

    # Start ngrok tunnel
    tunnel_url = start_ngrok_tunnel(port)
    if not tunnel_url:
        print("[ERROR] Failed to start ngrok tunnel")
        sys.exit(1)

    # Update webhook settings
    if not update_webhook_settings(tunnel_url):
        print("[ERROR] Failed to update webhook settings")
        sys.exit(1)

    # Register webhook with Brevo
    if not register_webhook_with_brevo(tunnel_url):
        print("[ERROR] Failed to register webhook with Brevo")
        print("[INFO] You can manually register it later through the settings page")

    print("\nSetup Complete!")
    print(f"Your webhook URL: {tunnel_url}/webhooks/brevo")
    print(f"Access your app at: {tunnel_url}")
    print("\nNext steps:")
    print("1. Test your webhook by sending an email through the app")
    print("2. Check webhook events in the dashboard")
    print("3. Use the settings page to manage webhook configuration")
    print("\nNOTE: Keep this terminal open to maintain the ngrok tunnel!")

if __name__ == "__main__":
    main()