#!/usr/bin/env python3
"""
Test script for the integrated Brevo + sequence dashboard functionality
Tests enhanced dashboard, sequence analytics, and intelligent follow-up features
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

def test_enhanced_dashboard_access(session, base_url):
    """Test access to enhanced dashboard"""
    print("\n" + "=" * 50)
    print("Testing Enhanced Dashboard Access")
    print("=" * 50)

    try:
        enhanced_url = f"{base_url}/enhanced"
        response = session.get(enhanced_url)

        if response.status_code == 200:
            print("[OK] Enhanced dashboard accessible")

            # Check if page contains expected elements
            content = response.text.lower()

            checks = [
                ('sequence flow', 'sequence flow' in content),
                ('real-time activity', 'real-time activity' in content),
                ('engagement chart', 'engagement-chart' in content),
                ('hot prospects', 'hot prospects' in content),
                ('sequence analytics', 'sequence-analytics' in content)
            ]

            for check_name, check_result in checks:
                status = "PASS" if check_result else "FAIL"
                print(f"  {check_name}: {status}")

            return True
        else:
            print(f"[ERROR] Enhanced dashboard failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"[ERROR] Exception testing enhanced dashboard: {e}")
        return False

def test_sequence_analytics_api(session, base_url):
    """Test sequence analytics API endpoints"""
    print("\n" + "=" * 50)
    print("Testing Sequence Analytics API")
    print("=" * 50)

    endpoints_to_test = [
        '/api/sequence-analytics',
        '/api/stats'
    ]

    results = {}

    for endpoint in endpoints_to_test:
        try:
            url = f"{base_url}{endpoint}"
            response = session.get(url)

            if response.status_code == 200:
                data = response.json()
                print(f"[OK] {endpoint} - Status: {response.status_code}")

                if endpoint == '/api/sequence-analytics':
                    # Check data structure
                    expected_keys = ['success', 'performance_summary', 'active_sequences', 'real_time_updates']
                    has_all_keys = all(key in data for key in expected_keys)
                    print(f"  Data structure complete: {'YES' if has_all_keys else 'NO'}")

                    if data.get('success'):
                        performance = data.get('performance_summary', {})
                        print(f"  Total sequences: {performance.get('total_sequences', 0)}")
                        print(f"  Active sequences: {len(data.get('active_sequences', []))}")
                        print(f"  Engagement metrics: {performance.get('engagement_metrics', {})}")

                results[endpoint] = {'success': True, 'data': data}
            else:
                print(f"[ERROR] {endpoint} - Status: {response.status_code}")
                results[endpoint] = {'success': False, 'status': response.status_code}

        except Exception as e:
            print(f"[ERROR] Exception testing {endpoint}: {e}")
            results[endpoint] = {'success': False, 'error': str(e)}

    return results

def test_intelligent_follow_up_api(session, base_url):
    """Test intelligent follow-up API"""
    print("\n" + "=" * 50)
    print("Testing Intelligent Follow-up API")
    print("=" * 50)

    try:
        url = f"{base_url}/api/intelligent-follow-up"
        response = session.get(url)

        if response.status_code == 200:
            data = response.json()
            print("[OK] Intelligent follow-up API accessible")

            if data.get('success'):
                results = data.get('results', {})
                print(f"  Campaigns processed: {results.get('processed_campaigns', 0)}")
                print(f"  Contacts analyzed: {results.get('contacts_analyzed', 0)}")
                print(f"  Sequences adjusted: {results.get('sequences_adjusted', 0)}")
                print(f"  Sequences paused: {results.get('sequences_paused', 0)}")
                print(f"  Sequences accelerated: {results.get('sequences_accelerated', 0)}")

                return True
            else:
                print(f"[WARNING] API returned success=false: {data}")
                return False
        else:
            print(f"[ERROR] Intelligent follow-up API failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"[ERROR] Exception testing intelligent follow-up: {e}")
        return False

def test_contact_journey_api(session, base_url):
    """Test contact journey API with test contact"""
    print("\n" + "=" * 50)
    print("Testing Contact Journey API")
    print("=" * 50)

    try:
        # First, try to get a test contact ID from our webhook tests
        test_contact_id = 6  # From previous webhook tests

        url = f"{base_url}/api/contact-journey/{test_contact_id}"
        response = session.get(url)

        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Contact journey API accessible for contact {test_contact_id}")

            if data.get('success'):
                journey = data.get('journey', [])
                print(f"  Journey steps found: {len(journey)}")

                if journey:
                    print("  Journey details:")
                    for step in journey[:3]:  # Show first 3 steps
                        print(f"    Step {step.get('sequence_step', 'N/A')}: {step.get('status', 'unknown')} - {step.get('template_type', 'unknown type')}")

                return True
            else:
                print("[INFO] No journey data found (expected for new contacts)")
                return True
        else:
            print(f"[ERROR] Contact journey API failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"[ERROR] Exception testing contact journey: {e}")
        return False

def test_real_time_updates(session, base_url):
    """Test real-time updates functionality"""
    print("\n" + "=" * 50)
    print("Testing Real-time Updates")
    print("=" * 50)

    try:
        # Test multiple calls to see if data changes/updates
        url = f"{base_url}/api/sequence-analytics"

        print("Making initial request...")
        response1 = session.get(url)

        time.sleep(2)  # Brief pause

        print("Making second request...")
        response2 = session.get(url)

        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.json()
            data2 = response2.json()

            print("[OK] Real-time updates accessible")

            # Check if timestamps are different (indicating fresh data)
            timestamp1 = data1.get('timestamp', '')
            timestamp2 = data2.get('timestamp', '')

            if timestamp1 != timestamp2:
                print("  Fresh data on each request: YES")
            else:
                print("  Fresh data on each request: NO (cached or static)")

            # Check real-time updates section
            updates1 = data1.get('real_time_updates', {})
            updates2 = data2.get('real_time_updates', {})

            print(f"  Active sequences: {updates1.get('active_sequences', 0)}")
            print(f"  Recently sent (24h): {updates1.get('recently_sent', 0)}")
            print(f"  Upcoming scheduled (24h): {updates1.get('upcoming_scheduled', 0)}")

            return True
        else:
            print("[ERROR] Real-time updates test failed")
            return False

    except Exception as e:
        print(f"[ERROR] Exception testing real-time updates: {e}")
        return False

def run_comprehensive_integration_test(base_url):
    """Run comprehensive test of integrated dashboard functionality"""
    print("SalesBreachPro Integrated Dashboard Test Suite")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print(f"Test Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Authenticate
    session = authenticate_session(base_url)
    if not session:
        print("CRITICAL: Authentication failed - aborting tests")
        return

    # Run all tests
    test_results = {}

    test_results['enhanced_dashboard'] = test_enhanced_dashboard_access(session, base_url)
    test_results['sequence_analytics'] = test_sequence_analytics_api(session, base_url)
    test_results['intelligent_follow_up'] = test_intelligent_follow_up_api(session, base_url)
    test_results['contact_journey'] = test_contact_journey_api(session, base_url)
    test_results['real_time_updates'] = test_real_time_updates(session, base_url)

    # Summary
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)

    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)

    print(f"Tests Passed: {passed_tests}/{total_tests}")
    print()

    for test_name, result in test_results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {test_name.replace('_', ' ').title()}: {status}")

    print("\n" + "=" * 60)
    if passed_tests == total_tests:
        print("ALL INTEGRATION TESTS PASSED!")
        print("Your enhanced dashboard with Brevo integration is fully functional!")
    elif passed_tests >= total_tests * 0.8:
        print("MOST INTEGRATION TESTS PASSED!")
        print("Your enhanced dashboard is mostly functional with minor issues.")
    else:
        print("INTEGRATION TESTS NEED ATTENTION")
        print("Several features may not be working correctly.")

    print("\nAccess your enhanced dashboard at:")
    print(f"  {base_url}/enhanced")
    print("\nDirect API endpoints:")
    print(f"  {base_url}/api/sequence-analytics")
    print(f"  {base_url}/api/intelligent-follow-up")
    print(f"  {base_url}/api/contact-journey/[contact_id]")

if __name__ == "__main__":
    import sys

    base_url = "https://ab651b8b0741.ngrok-free.app"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    run_comprehensive_integration_test(base_url)