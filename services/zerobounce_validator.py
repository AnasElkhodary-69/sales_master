"""
ZeroBounce Email Validation Service
Integrates with ZeroBounce API for high-quality email validation
"""

import os
import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from models.database import db

logger = logging.getLogger(__name__)

class ZeroBounceValidator:
    """ZeroBounce API integration for email validation"""

    def __init__(self):
        self.api_key = os.getenv('ZEROBOUNCE_API_KEY')
        self.enabled = os.getenv('ZEROBOUNCE_ENABLED', 'false').lower() == 'true'
        self.base_url = 'https://api.zerobounce.net/v2'
        self.timeout = 10

        if self.enabled and not self.api_key:
            logger.error("ZeroBounce enabled but no API key provided")
            self.enabled = False

    def validate_email(self, email: str) -> Dict:
        """
        Validate email using ZeroBounce API
        Returns standardized validation result
        """
        if not self.enabled:
            return self._fallback_validation(email)

        try:
            # Make API call to ZeroBounce
            response = requests.get(
                f"{self.base_url}/validate",
                params={
                    'api_key': self.api_key,
                    'email': email,
                    'ip_address': ''  # Optional IP address
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return self._process_zerobounce_response(data)
            else:
                logger.error(f"ZeroBounce API error: {response.status_code} - {response.text}")
                return self._fallback_validation(email)

        except requests.exceptions.Timeout:
            logger.warning(f"ZeroBounce API timeout for {email}")
            return self._fallback_validation(email)
        except requests.exceptions.RequestException as e:
            logger.error(f"ZeroBounce API request failed for {email}: {str(e)}")
            return self._fallback_validation(email)
        except Exception as e:
            logger.error(f"ZeroBounce validation failed for {email}: {str(e)}")
            return self._fallback_validation(email)

    def _process_zerobounce_response(self, data: Dict) -> Dict:
        """
        Process ZeroBounce API response into our standardized format
        """
        # Map ZeroBounce statuses to our simplified categories
        status_mapping = {
            'valid': 'valid',           # ✅ Safe to send
            'invalid': 'invalid',       # ❌ Will bounce
            'catch-all': 'risky',       # ⚠️ Uncertain delivery
            'unknown': 'risky',         # ⚠️ Uncertain delivery
            'spamtrap': 'invalid',      # ❌ Dangerous to send
            'abuse': 'invalid',         # ❌ Dangerous to send
            'do_not_mail': 'risky'      # ⚠️ Problematic but not bounced
        }

        zerobounce_status = data.get('status', 'unknown')
        our_status = status_mapping.get(zerobounce_status, 'risky')

        # Calculate confidence score
        score = self._calculate_score(data)

        return {
            'is_valid': zerobounce_status in ['valid', 'catch-all'],
            'status': our_status,
            'zerobounce_status': zerobounce_status,
            'score': score,
            'reason': data.get('sub_status', ''),
            'is_disposable': data.get('free_email', False),
            'is_role_based': self._is_role_based_email(data.get('account', '')),
            'mx_found': data.get('mx_found', True),
            'smtp_provider': data.get('smtp_provider', ''),
            'domain_age_days': data.get('domain_age_days', 0),
            'validation_method': 'zerobounce_api',
            'raw_response': data
        }

    def _calculate_score(self, data: Dict) -> int:
        """Calculate confidence score 0-100 based on ZeroBounce data"""

        # Base scores for each status
        base_scores = {
            'valid': 100,
            'catch-all': 70,
            'unknown': 50,
            'invalid': 0,
            'spamtrap': 0,
            'abuse': 0,
            'do_not_mail': 0
        }

        score = base_scores.get(data.get('status'), 50)

        # Adjust based on additional factors
        if data.get('free_email'):
            score -= 5  # Slightly lower for free emails

        if not data.get('mx_found'):
            score = min(score, 20)  # Very low if no MX record

        # Role-based emails get lower scores
        if self._is_role_based_email(data.get('account', '')):
            score -= 15

        # Very new domains might be risky
        domain_age = data.get('domain_age_days', 1000)
        if domain_age and isinstance(domain_age, (int, float)) and domain_age < 30:
            score -= 10

        return max(0, min(100, score))

    def _is_role_based_email(self, account: str) -> bool:
        """Check if email account is role-based"""
        role_prefixes = {
            'admin', 'administrator', 'info', 'support', 'help',
            'contact', 'sales', 'marketing', 'noreply', 'no-reply',
            'webmaster', 'postmaster', 'hostmaster', 'abuse'
        }
        return account.lower() in role_prefixes

    def _fallback_validation(self, email: str) -> Dict:
        """
        Fallback validation when API is unavailable
        Uses basic regex and format checking
        """
        import re

        # Basic email regex
        email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

        is_valid_format = bool(email_regex.match(email))
        account = email.split('@')[0] if '@' in email else ''

        # Basic role-based detection
        is_role_based = self._is_role_based_email(account)

        return {
            'is_valid': is_valid_format,
            'status': 'risky' if is_valid_format else 'invalid',
            'zerobounce_status': 'unknown',
            'score': 60 if is_valid_format else 0,
            'reason': 'api_unavailable' if is_valid_format else 'invalid_format',
            'is_disposable': False,
            'is_role_based': is_role_based,
            'mx_found': True,  # Assume true in fallback
            'smtp_provider': '',
            'domain_age_days': 0,
            'validation_method': 'fallback_regex',
            'raw_response': {'email': email, 'fallback': True}
        }

    def get_account_credits(self) -> Optional[int]:
        """Get remaining ZeroBounce credits"""
        if not self.enabled:
            return None

        try:
            response = requests.get(
                f"{self.base_url}/getcredits",
                params={'api_key': self.api_key},
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                credits = data.get('Credits', 0)
                logger.info(f"ZeroBounce credits remaining: {credits}")
                return credits
            else:
                logger.error(f"Failed to get ZeroBounce credits: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting ZeroBounce credits: {str(e)}")
            return None

    def validate_api_key(self) -> bool:
        """Test if API key is valid"""
        if not self.enabled or not self.api_key:
            return False

        try:
            # Test with a simple validation call
            response = requests.get(
                f"{self.base_url}/validate",
                params={
                    'api_key': self.api_key,
                    'email': 'test@example.com'
                },
                timeout=self.timeout
            )

            # Check if we get a valid response (even for test email)
            return response.status_code == 200

        except Exception as e:
            logger.error(f"ZeroBounce API key validation failed: {str(e)}")
            return False

# Factory function for easy integration
def create_zerobounce_validator():
    """Create ZeroBounce validator instance"""
    return ZeroBounceValidator()