#!/usr/bin/env python3
"""
Webhook Functionality Test Script for SalesBreachPro
Tests webhook registration, email sending, and event tracking
"""
import requests
import json
import time
from datetime import datetime

def test_webhook_connectivity(base_url):
    """Test if webhook endpoint is accessible"""
    print("=" * 50)
    print("1. Testing Webhook Connectivity")
    print("=" * 50)

    webhook_url = f"{base_url}/webhooks/brevo"

    try:
        # Test webhook endpoint accessibility
        response = requests.get(webhook_url)
        print(f"[INFO] Webhook endpoint: {webhook_url}")
        print(f"[INFO] Response status: {response.status_code}")

        if response.status_code == 405:  # Method Not Allowed is expected for GET on POST endpoint
            print("[OK] Webhook endpoint is accessible (405 Method Not Allowed is expected)")
            return True
        else:
            print(f"[WARNING] Unexpected response: {response.status_code}")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to reach webhook endpoint: {e}")
        return False

def test_brevo_webhook_registration(base_url):
    """Test Brevo webhook registration through settings"""
    print("\n" + "=" * 50)
    print("2. Testing Brevo Webhook Registration")
    print("=" * 50)

    try:
        # Test webhook setup endpoint
        setup_url = f"{base_url}/settings"

        print(f"[INFO] You can test webhook registration at: {setup_url}")
        print("[INFO] Look for 'Webhook Configuration' section")
        print("[INFO] Click 'Setup Webhooks' to register with Brevo")

        # Test connectivity endpoint
        test_url = f"{base_url}/api/automation-status"
        response = requests.get(test_url)

        if response.status_code == 200:
            data = response.json()
            print(f"[INFO] Automation status check successful")
            print(f"[INFO] Brevo service: {data.get('brevo_service', 'unknown')}")
            print(f"[INFO] Webhooks: {data.get('webhooks', 'unknown')}")
            return True
        else:
            print(f"[WARNING] Automation status check failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to test webhook registration: {e}")
        return False

def simulate_webhook_events(base_url, test_email="test@example.com"):
    """Simulate various webhook events for testing"""
    print("\n" + "=" * 50)
    print("3. Testing Webhook Event Simulation")
    print("=" * 50)

    simulate_url = f"{base_url}/api/simulate-webhook"

    # Test events to simulate
    test_events = [
        {
            'event': 'delivered',
            'email': test_email,
            'subject': 'Test Delivery Event'
        },
        {
            'event': 'opened',
            'email': test_email,
            'subject': 'Test Open Event'
        },
        {
            'event': 'clicked',
            'email': test_email,
            'link': 'https://example.com/test-link',
            'subject': 'Test Click Event'
        },
        {
            'event': 'replied',
            'email': test_email,
            'subject': 'Test Reply Event'
        }
    ]

    results = []

    for event_data in test_events:
        try:
            print(f"\n[INFO] Simulating {event_data['event']} event for {test_email}")

            response = requests.post(simulate_url, json=event_data)

            if response.status_code == 200:
                result = response.json()
                print(f"[OK] {event_data['event']} event simulated successfully")
                results.append({'event': event_data['event'], 'success': True})
            else:
                print(f"[ERROR] Failed to simulate {event_data['event']}: {response.status_code}")
                results.append({'event': event_data['event'], 'success': False})

            time.sleep(1)  # Brief pause between events

        except Exception as e:
            print(f"[ERROR] Exception simulating {event_data['event']}: {e}")
            results.append({'event': event_data['event'], 'success': False})

    # Summary
    successful_events = sum(1 for r in results if r['success'])
    print(f"\n[SUMMARY] Successfully simulated {successful_events}/{len(test_events)} events")

    return results

def test_email_sending(base_url, recipient_email):
    """Test email sending functionality"""
    print("\n" + "=" * 50)
    print("4. Testing Email Sending")
    print("=" * 50)

    test_email_url = f"{base_url}/test-email"

    print(f"[INFO] You can test email sending at: {test_email_url}")
    print(f"[INFO] Enter recipient: {recipient_email}")
    print("[INFO] This will test the full email sending + webhook tracking flow")

    # Test if the endpoint is accessible
    try:
        response = requests.get(test_email_url)
        if response.status_code == 200:
            print("[OK] Test email page is accessible")
            return True
        else:
            print(f"[WARNING] Test email page returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to access test email page: {e}")
        return False

def check_webhook_logs(base_url):
    """Check for webhook event logs"""
    print("\n" + "=" * 50)
    print("5. Checking Webhook Event Processing")
    print("=" * 50)

    try:
        # Check dashboard for recent activity
        dashboard_url = f"{base_url}/api/stats"
        response = requests.get(dashboard_url)

        if response.status_code == 200:
            stats = response.json()
            print("[INFO] Dashboard statistics:")
            print(f"   - Total contacts: {stats.get('total_contacts', 0)}")
            print(f"   - Emails this week: {stats.get('emails_this_week', 0)}")
            print(f"   - Responses this week: {stats.get('responses_this_week', 0)}")
            print(f"   - Response rate: {stats.get('response_rate', 0)}%")
            print(f"   - Delivery rate: {stats.get('delivery_rate', 0)}%")
            print(f"   - Open rate: {stats.get('open_rate', 0)}%")
            return True
        else:
            print(f"[WARNING] Failed to get dashboard stats: {response.status_code}")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to check webhook logs: {e}")
        return False

def run_comprehensive_test(base_url, recipient_email="test@example.com"):
    """Run comprehensive webhook functionality test"""
    print("SalesBreachPro Webhook Functionality Test")
    print("=" * 50)
    print(f"Base URL: {base_url}")
    print(f"Test Email: {recipient_email}")
    print(f"Test Time: {datetime.now().isoformat()}")

    results = {}

    # Run all tests
    results['connectivity'] = test_webhook_connectivity(base_url)
    results['registration'] = test_brevo_webhook_registration(base_url)
    results['simulation'] = simulate_webhook_events(base_url, recipient_email)
    results['email_sending'] = test_email_sending(base_url, recipient_email)
    results['logs'] = check_webhook_logs(base_url)

    # Final summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)

    if results['connectivity']:
        print("[OK] Webhook connectivity test passed")
    else:
        print("[FAIL] Webhook connectivity test failed")

    if results['registration']:
        print("[OK] Brevo registration endpoints accessible")
    else:
        print("[FAIL] Brevo registration test failed")

    simulation_success = sum(1 for r in results['simulation'] if r['success']) if results['simulation'] else 0
    print(f"[INFO] Webhook simulation: {simulation_success}/4 events successful")

    if results['email_sending']:
        print("[OK] Email sending interface accessible")
    else:
        print("[FAIL] Email sending test failed")

    if results['logs']:
        print("[OK] Dashboard and statistics accessible")
    else:
        print("[FAIL] Dashboard access failed")

    print("\n" + "=" * 50)
    print("MANUAL TESTING STEPS")
    print("=" * 50)
    print(f"1. Visit: {base_url}/settings")
    print("   - Configure Brevo API key")
    print("   - Test webhook connectivity")
    print("   - Setup webhooks with Brevo")
    print(f"\n2. Visit: {base_url}/test-email")
    print(f"   - Send test email to: {recipient_email}")
    print("   - Check email delivery")
    print("   - Open email to trigger webhook")
    print(f"\n3. Visit: {base_url}/dashboard")
    print("   - Monitor real-time statistics")
    print("   - Check email engagement metrics")
    print(f"\n4. Check webhook events at: {base_url}/webhooks/brevo")
    print("   - Brevo will POST events here")
    print("   - Monitor console logs for webhook activity")

if __name__ == "__main__":
    import sys

    # Get base URL from command line or use default ngrok URL
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "https://ab651b8b0741.ngrok-free.app"  # Current ngrok URL

    # Get test email from command line or use default
    if len(sys.argv) > 2:
        test_email = sys.argv[2]
    else:
        test_email = "test@example.com"

    run_comprehensive_test(base_url, test_email)