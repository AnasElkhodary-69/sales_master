#!/usr/bin/env python
"""Test script to verify FlawTrack API integration and breach scanning"""

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

from services.flawtrack_api import FlawTrackAPI

def test_flawtrack_api():
    """Test the FlawTrack API with a known domain"""
    
    # Get API credentials from environment
    api_key = os.environ.get('FLAWTRACK_API_TOKEN')
    endpoint = os.environ.get('FLAWTRACK_API_ENDPOINT', 'https://app-api.flawtrack.com/leaks/demo/credentials/')
    
    print(f"\n=== FlawTrack API Test ===")
    print(f"API Key: {api_key[:10]}..." if api_key else "No API key found!")
    print(f"Endpoint: {endpoint}")
    
    if not api_key or api_key.startswith('your-'):
        print("[ERROR] Valid API key not found in environment!")
        return False
    
    # Initialize API client
    api = FlawTrackAPI(api_key, endpoint)
    
    # Test domains
    test_domains = [
        'gmail.com',
        'yahoo.com', 
        'microsoft.com',
        'facebook.com',
        'example.com'
    ]
    
    print(f"\n=== Testing {len(test_domains)} domains ===\n")
    
    for domain in test_domains:
        print(f"Testing {domain}...")
        
        try:
            # Get breach data
            breach_data = api.get_breach_data(domain)
            
            if breach_data is None:
                print(f"  [FAIL] API request failed for {domain}")
            elif isinstance(breach_data, list) and len(breach_data) > 0:
                print(f"  [BREACHED] Found {len(breach_data)} credential records")
                # Show first record as example
                if breach_data:
                    first_record = breach_data[0]
                    print(f"    Sample: {first_record.get('email', 'N/A')} - {first_record.get('password', 'N/A')[:20]}...")
            elif breach_data == []:
                print(f"  [SECURE] No breaches found")
            else:
                print(f"  [WARNING] Unexpected response: {breach_data}")
                
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
    
    print("\n=== Test Complete ===")
    return True

if __name__ == "__main__":
    success = test_flawtrack_api()
    sys.exit(0 if success else 1)