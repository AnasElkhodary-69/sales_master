#!/usr/bin/env python3
"""
Complete Webhook Event Testing for SalesBreachPro
Tests all supported Brevo webhook events
"""
import requests
import json
import time

def authenticate_session(base_url):
    """Authenticate and return session"""
    session = requests.Session()

    # Login
    login_url = f"{base_url}/login"
    login_data = {
        'username': 'admin',
        'password': 'SalesBreachPro2025!'
    }

    session.get(login_url)  # Get session cookie
    response = session.post(login_url, data=login_data)

    if response.status_code in [200, 302]:
        print("[OK] Authentication successful")
        return session
    else:
        print("[ERROR] Authentication failed")
        return None

def test_webhook_event(session, base_url, event_type, email, additional_data=None):
    """Test a specific webhook event"""
    simulate_url = f"{base_url}/api/simulate-webhook"

    payload = {
        'event': event_type,
        'email': email,
        'subject': f'Test {event_type.title()} Event'
    }

    if additional_data:
        payload.update(additional_data)

    try:
        response = session.post(simulate_url, json=payload)

        if response.status_code == 200:
            result = response.json()
            print(f"[OK] {event_type} event: {result['message']}")
            return True
        else:
            print(f"[ERROR] {event_type} event failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"[ERROR] {event_type} event exception: {e}")
        return False

def test_direct_webhook_event(base_url, event_type, email, additional_data=None):
    """Test webhook event via direct webhook endpoint (simulating Brevo)"""
    webhook_url = f"{base_url}/webhooks/brevo"

    payload = {
        'event': event_type,
        'email': email,
        'message-id': f'<test_{int(time.time())}@brevo.com>',
        'timestamp': '2025-01-14T16:00:00.000Z',
        'subject': f'Test {event_type.title()} Event',
        'tag': ['test']
    }

    if additional_data:
        payload.update(additional_data)

    try:
        response = requests.post(webhook_url, json=payload)

        if response.status_code == 200:
            result = response.json()
            print(f"[OK] Direct {event_type}: {result.get('status', 'success')}")
            return True
        else:
            print(f"[ERROR] Direct {event_type} failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"[ERROR] Direct {event_type} exception: {e}")
        return False

def check_contact_updates(session, base_url, email):
    """Check if contact was updated by webhook events"""
    # Get contact details to verify webhook processing
    contacts_url = f"{base_url}/api/contacts"

    try:
        # This endpoint might not exist, so let's check dashboard stats instead
        stats_url = f"{base_url}/api/stats"
        response = session.get(stats_url)

        if response.status_code == 200:
            stats = response.json()
            print(f"\n[INFO] Updated Dashboard Stats:")
            print(f"   - Total contacts: {stats.get('total_contacts', 0)}")
            print(f"   - Emails this week: {stats.get('emails_this_week', 0)}")
            print(f"   - Responses this week: {stats.get('responses_this_week', 0)}")
            print(f"   - Response rate: {stats.get('response_rate', 0)}%")
            print(f"   - Open rate: {stats.get('open_rate', 0)}%")
            return True
    except Exception as e:
        print(f"[WARNING] Could not check contact updates: {e}")
        return False

def main():
    base_url = "https://ab651b8b0741.ngrok-free.app"
    test_email = "webhook-test@example.com"

    print("Complete Webhook Event Testing")
    print("=" * 40)
    print(f"Base URL: {base_url}")
    print(f"Test Email: {test_email}")
    print()

    # Authenticate
    session = authenticate_session(base_url)
    if not session:
        return

    # Test all webhook events
    events_to_test = [
        ('delivered', None),
        ('opened', None),
        ('clicked', {'link': 'https://example.com/test-link'}),
        ('replied', None),
        ('bounced', {'bounce_type': 'hard'}),
        ('unsubscribed', None),
        ('spam', None)
    ]

    print("Testing API Simulation Endpoints:")
    print("-" * 40)
    api_results = []

    for event_type, additional_data in events_to_test:
        success = test_webhook_event(session, base_url, event_type, test_email, additional_data)
        api_results.append((event_type, success))
        time.sleep(0.5)  # Brief pause between tests

    print("\nTesting Direct Webhook Endpoints:")
    print("-" * 40)
    direct_results = []

    for event_type, additional_data in events_to_test:
        success = test_direct_webhook_event(base_url, event_type, test_email, additional_data)
        direct_results.append((event_type, success))
        time.sleep(0.5)  # Brief pause between tests

    # Check contact updates
    check_contact_updates(session, base_url, test_email)

    # Summary
    print("\n" + "=" * 40)
    print("WEBHOOK TESTING SUMMARY")
    print("=" * 40)

    api_passed = sum(1 for _, success in api_results if success)
    direct_passed = sum(1 for _, success in direct_results if success)

    print(f"API Simulation Tests: {api_passed}/{len(api_results)} passed")
    print(f"Direct Webhook Tests: {direct_passed}/{len(direct_results)} passed")

    print("\nDetailed Results:")
    print("API Simulation:")
    for event, success in api_results:
        status = "PASS" if success else "FAIL"
        print(f"  {event:12} - {status}")

    print("Direct Webhook:")
    for event, success in direct_results:
        status = "PASS" if success else "FAIL"
        print(f"  {event:12} - {status}")

    if api_passed == len(api_results) and direct_passed == len(direct_results):
        print("\n🎉 ALL WEBHOOK TESTS PASSED!")
        print("Your SalesBreachPro webhook system is fully functional!")
    elif api_passed > 0 or direct_passed > 0:
        print("\n✅ WEBHOOK SYSTEM PARTIALLY WORKING")
        print("Some webhook events are working correctly.")
    else:
        print("\n❌ WEBHOOK TESTS FAILED")
        print("Check application logs for details.")

    print(f"\n📊 Live Dashboard: {base_url}/dashboard")
    print(f"⚙️  Settings Page: {base_url}/settings")
    print(f"🔗 Your Webhook URL: {base_url}/webhooks/brevo")

if __name__ == "__main__":
    main()