#!/usr/bin/env python3
"""
Manual Webhook Testing Script for SalesBreachPro
Tests individual webhook endpoints with authentication
"""
import requests
import json

def test_with_session(base_url):
    """Test webhook simulation using session authentication"""
    session = requests.Session()

    # Login first
    login_url = f"{base_url}/login"
    print(f"Attempting login at: {login_url}")

    # Get login page first to establish session
    response = session.get(login_url)
    print(f"Login page status: {response.status_code}")

    # Perform login
    login_data = {
        'username': 'admin',
        'password': 'SalesBreachPro2025!'
    }

    response = session.post(login_url, data=login_data)
    print(f"Login response status: {response.status_code}")

    if response.status_code == 302 or 'dashboard' in response.text.lower():
        print("[OK] Login successful")

        # Now test webhook simulation
        simulate_url = f"{base_url}/api/simulate-webhook"

        test_data = {
            'event': 'delivered',
            'email': 'test@example.com',
            'subject': 'Test Email Delivery'
        }

        response = session.post(simulate_url, json=test_data)
        print(f"Webhook simulation status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"[SUCCESS] Webhook simulation worked!")
            print(f"Result: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"[ERROR] Simulation failed: {response.text[:200]}")
            return False
    else:
        print("[ERROR] Login failed")
        return False

def test_direct_webhook(base_url):
    """Test the webhook endpoint directly"""
    webhook_url = f"{base_url}/webhooks/brevo"

    # Simulate a real Brevo webhook payload
    webhook_payload = {
        "event": "delivered",
        "email": "test@example.com",
        "message-id": "<test123@example.com>",
        "timestamp": "2025-01-14T12:58:00.000Z",
        "tag": ["test"],
        "subject": "Test Email"
    }

    print(f"Testing direct webhook at: {webhook_url}")

    try:
        response = requests.post(webhook_url, json=webhook_payload)
        print(f"Direct webhook status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"[SUCCESS] Direct webhook worked!")
            print(f"Result: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"[INFO] Response: {response.text[:200]}")
            return response.status_code == 200

    except Exception as e:
        print(f"[ERROR] Direct webhook failed: {e}")
        return False

if __name__ == "__main__":
    import sys

    base_url = "https://ab651b8b0741.ngrok-free.app"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    print("Manual Webhook Testing")
    print("=" * 30)
    print(f"Base URL: {base_url}")
    print()

    print("Test 1: Authenticated API simulation")
    auth_result = test_with_session(base_url)

    print("\nTest 2: Direct webhook endpoint")
    direct_result = test_direct_webhook(base_url)

    print("\nSummary:")
    print(f"Authenticated API: {'PASS' if auth_result else 'FAIL'}")
    print(f"Direct webhook: {'PASS' if direct_result else 'FAIL'}")

    if auth_result or direct_result:
        print("\n[SUCCESS] At least one webhook method is working!")
    else:
        print("\n[ERROR] Both webhook methods failed. Check application logs.")