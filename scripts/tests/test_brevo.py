#!/usr/bin/env python
"""Test script to verify Brevo API integration"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
basedir = os.path.abspath(os.path.dirname(__file__))
env_file = os.path.join(basedir, 'env')
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"[OK] Loaded environment from: {env_file}")

# Add project directory to path
sys.path.insert(0, basedir)

def test_brevo_api():
    """Test the Brevo API with account verification"""
    
    # Get API credentials from environment
    api_key = os.environ.get('BREVO_API_KEY')
    sender_email = os.environ.get('BREVO_SENDER_EMAIL', 'emily.carter@savety.ai')
    sender_name = os.environ.get('BREVO_SENDER_NAME', 'Security Team')
    
    print(f"\n=== Brevo API Test ===")
    print(f"API Key: {api_key[:20]}..." if api_key else "No API key found!")
    print(f"Sender Email: {sender_email}")
    print(f"Sender Name: {sender_name}")
    
    if not api_key:
        print("[ERROR] Valid API key not found in environment!")
        return False
    
    try:
        # Import Brevo SDK
        import brevo_python
        from brevo_python.rest import ApiException
        
        # Configure API client
        configuration = brevo_python.Configuration()
        configuration.api_key['api-key'] = api_key
        
        # Create API client
        api_client = brevo_python.ApiClient(configuration)
        
        # Test account API
        account_api = brevo_python.AccountApi(api_client)
        
        print("\n[INFO] Testing API connection...")
        
        # Get account info
        account = account_api.get_account()
        
        print(f"\n[SUCCESS] API Connected!")
        print(f"Account Email: {account.email}")
        print(f"Company: {account.company_name}")
        print(f"Plan: {account.plan[0].type if account.plan else 'N/A'}")
        print(f"Credits Remaining: {account.plan[0].credits if account.plan else 'N/A'}")
        
        # Test transactional email API
        transactional_api = brevo_python.TransactionalEmailsApi(api_client)
        
        # Create test email (but don't send)
        send_smtp_email = brevo_python.SendSmtpEmail(
            to=[{"email": "test@example.com", "name": "Test User"}],
            sender={"email": sender_email, "name": sender_name},
            subject="Test Email - DO NOT SEND",
            html_content="<p>This is a test email content.</p>"
        )
        
        print(f"\n[SUCCESS] Email API configured correctly!")
        print(f"Ready to send emails from: {sender_email}")
        
        return True
        
    except ApiException as e:
        print(f"\n[ERROR] Brevo API Error: {e.status}")
        print(f"Reason: {e.reason}")
        if hasattr(e, 'body'):
            print(f"Details: {e.body}")
        return False
        
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_brevo_api()
    sys.exit(0 if success else 1)