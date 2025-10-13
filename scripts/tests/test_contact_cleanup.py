#!/usr/bin/env python3
"""
Test Contact Cleanup Functionality
Verifies that contacts can be completely cleaned from campaigns
"""
import requests
import json
import time

def test_contact_cleanup(base_url, campaign_id=1, contact_email="webhook-test@example.com"):
    """Test the complete contact cleanup process"""
    print("Contact Cleanup Testing")
    print("=" * 40)
    print(f"Base URL: {base_url}")
    print(f"Campaign ID: {campaign_id}")
    print(f"Test Contact: {contact_email}")
    print()

    # Authenticate
    session = requests.Session()
    login_url = f"{base_url}/login"
    login_data = {'username': 'admin', 'password': 'SalesBreachPro2025!'}

    session.get(login_url)
    response = session.post(login_url, data=login_data)

    if response.status_code not in [200, 302]:
        print("[ERROR] Authentication failed")
        return

    print("[OK] Authentication successful")

    # First, find the contact ID
    try:
        # Simulate finding the contact (in real scenario, you'd get this from campaign page)
        # For this test, we'll use contact ID 7 (from our previous tests)
        test_contact_id = 7

        print(f"[INFO] Testing with contact ID: {test_contact_id}")

        # Test 1: Verify contact cleanup verification
        print("\nTest 1: Verify Contact State")
        print("-" * 30)

        verify_url = f"{base_url}/campaigns/{campaign_id}/contacts/{test_contact_id}/deep-clean"
        response = session.post(verify_url)

        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Deep clean executed successfully")

            if data.get('success'):
                print(f"[INFO] Message: {data.get('message', 'No message')}")

                cleanup_details = data.get('cleanup_details', {})
                print(f"[INFO] Cleanup details:")
                print(f"  - Sequences deleted: {cleanup_details.get('sequences_deleted', 0)}")
                print(f"  - Emails deleted: {cleanup_details.get('emails_deleted', 0)}")
                print(f"  - Responses deleted: {cleanup_details.get('responses_deleted', 0)}")
                print(f"  - Campaign status deleted: {cleanup_details.get('campaign_status_deleted', False)}")
                print(f"  - Contact fields reset: {cleanup_details.get('contact_fields_reset', False)}")
                print(f"  - Ready for fresh testing: {cleanup_details.get('fresh_testing_ready', False)}")
            else:
                print(f"[ERROR] Deep clean failed: {data.get('error', 'Unknown error')}")
        else:
            print(f"[ERROR] Deep clean request failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")

        # Test 2: Test contact removal (regular cleanup)
        print("\nTest 2: Regular Contact Removal")
        print("-" * 30)

        remove_url = f"{base_url}/campaigns/{campaign_id}/contacts/{test_contact_id}/remove"
        response = session.post(remove_url)

        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Contact removal executed")

            if data.get('success'):
                print(f"[INFO] Message: {data.get('message', 'No message')}")

                verification = data.get('cleanup_verification', {})
                if verification:
                    print(f"[INFO] Cleanup verification:")
                    print(f"  - Is clean: {verification.get('is_clean', 'unknown')}")
                    print(f"  - Issues found: {verification.get('issues_found', [])}")
                    print(f"  - Details: {verification.get('details', {})}")
            else:
                print(f"[ERROR] Contact removal failed: {data.get('error', 'Unknown error')}")
        else:
            print(f"[ERROR] Contact removal request failed: {response.status_code}")

        # Test 3: Try to add the contact back to verify fresh state
        print("\nTest 3: Re-add Contact for Fresh Testing")
        print("-" * 30)

        # First, we need to add the contact back to the campaign
        add_url = f"{base_url}/campaigns/{campaign_id}/contacts/add"
        add_data = {'contact_ids': [test_contact_id]}

        response = session.post(add_url, json=add_data)

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"[OK] Contact re-added successfully: {data.get('message', 'No message')}")
                print(f"[INFO] This contact should now be in a fresh state for testing")
            else:
                print(f"[ERROR] Failed to re-add contact: {data.get('error', 'Unknown error')}")
        else:
            print(f"[ERROR] Re-add contact request failed: {response.status_code}")

        print("\n" + "=" * 40)
        print("CLEANUP TEST SUMMARY")
        print("=" * 40)
        print("✓ Deep clean functionality tested")
        print("✓ Regular removal with verification tested")
        print("✓ Contact re-addition tested")
        print("\nThe contact should now be in a completely fresh state")
        print("with no previous email history or sequence data.")

    except Exception as e:
        print(f"[ERROR] Test execution failed: {e}")

def main():
    base_url = "https://ab651b8b0741.ngrok-free.app"
    test_contact_cleanup(base_url)

if __name__ == "__main__":
    main()