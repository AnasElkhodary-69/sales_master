"""
EmailListVerify Email Validation Service
Integrates with EmailListVerify API for high-quality email validation
"""

import os
import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from models.database import db

logger = logging.getLogger(__name__)

class EmailListVerifyValidator:
    """EmailListVerify API integration for email validation"""

    def __init__(self):
        self.api_key = os.getenv('EMAILLISTVERIFY_API_KEY')
        self.enabled = os.getenv('EMAILLISTVERIFY_ENABLED', 'true').lower() == 'true'
        self.base_url = 'https://apps.emaillistverify.com/api/verifyEmail'
        self.timeout = 15

        if self.enabled and not self.api_key:
            logger.error("EmailListVerify enabled but no API key provided")
            self.enabled = False

    def validate_email(self, email: str) -> Dict:
        """
        Validate email using EmailListVerify API
        Returns standardized validation result
        """
        if not self.enabled:
            return self._fallback_validation(email)

        try:
            # Make API call to EmailListVerify
            response = requests.get(
                self.base_url,
                params={
                    'secret': self.api_key,
                    'email': email
                },
                timeout=self.timeout
            )

            logger.info(f"EmailListVerify API response for {email}: Status {response.status_code}, Content: {response.text[:500]}")

            if response.status_code == 200:
                # EmailListVerify returns plain text status, not JSON
                status_text = response.text.strip()
                data = {'Result': status_text, 'email': email}
                return self._process_emaillistverify_response(data)
            else:
                logger.error(f"EmailListVerify API error: {response.status_code} - {response.text}")
                return self._fallback_validation(email)

        except requests.exceptions.Timeout:
            logger.warning(f"EmailListVerify API timeout for {email}")
            return self._fallback_validation(email)
        except requests.exceptions.RequestException as e:
            logger.error(f"EmailListVerify API request failed for {email}: {str(e)}")
            return self._fallback_validation(email)
        except Exception as e:
            logger.error(f"EmailListVerify validation failed for {email}: {str(e)}")
            return self._fallback_validation(email)

    def _process_emaillistverify_response(self, data: Dict) -> Dict:
        """
        Process EmailListVerify API response into our standardized format
        """
        # Map EmailListVerify statuses to our status categories (matching ZeroBounce interface)
        status_mapping = {
            'ok': 'valid',                   # ✅ Valid email - ready for FlawTrack scanning
            'email_disabled': 'invalid',     # ❌ Will bounce - skip scanning
            'dead_server': 'invalid',        # ❌ Will bounce - skip scanning
            'invalid_mx': 'invalid',         # ❌ Will bounce - skip scanning
            'disposable': 'risky',           # ⚠️ Temporary email - don't scan but different from bounced
            'spamtrap': 'invalid',           # ❌ Dangerous - skip scanning
            'ok_for_all': 'valid',           # ✅ Catch-all - treat as valid for scanning
            'smtp_protocol': 'valid',        # ⚠️ No credits deducted - treat as valid
            'antispam_system': 'valid',      # ⚠️ No credits deducted - treat as valid
            'unknown': 'valid',              # ⚠️ No credits deducted - treat as valid
            'invalid_syntax': 'invalid'      # ❌ Invalid format - skip scanning
        }

        elv_status = data.get('Result', 'unknown')
        our_status = status_mapping.get(elv_status, 'valid')

        # Calculate confidence score
        score = self._calculate_score(data)

        return {
            'is_valid': our_status == 'valid',
            'status': our_status,
            'elv_status': elv_status,
            'score': score,
            'reason': data.get('Description', ''),
            'is_disposable': elv_status == 'disposable',
            'is_role_based': self._is_role_based_email(data.get('email', '').split('@')[0] if '@' in data.get('email', '') else ''),
            'mx_found': elv_status not in ['dead_server', 'invalid_mx'],
            'smtp_provider': '',
            'domain_age_days': 0,
            'validation_method': 'emaillistverify_api',
            'raw_response': data
        }

    def _calculate_score(self, data: Dict) -> int:
        """Calculate confidence score 0-100 based on EmailListVerify data"""

        # Base scores for each status
        base_scores = {
            'ok': 100,                    # Perfect deliverability
            'ok_for_all': 75,             # Catch-all domain
            'smtp_protocol': 60,          # Couldn't verify but no issue detected
            'antispam_system': 60,        # Couldn't verify due to anti-spam
            'unknown': 50,                # Unknown status
            'disposable': 25,             # Temporary email
            'email_disabled': 0,          # Will bounce
            'dead_server': 0,             # Will bounce
            'invalid_mx': 0,              # Will bounce
            'spamtrap': 0,                # Dangerous
            'invalid_syntax': 0           # Invalid format
        }

        elv_status = data.get('Result', 'unknown')
        score = base_scores.get(elv_status, 50)

        # Adjust based on additional factors
        email = data.get('email', '')
        if '@' in email:
            account = email.split('@')[0]
            domain = email.split('@')[1]

            # Role-based emails get lower scores
            if self._is_role_based_email(account):
                score -= 15

            # Free email providers get slightly lower scores
            free_providers = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com'}
            if domain.lower() in free_providers:
                score -= 5

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
            'status': 'valid' if is_valid_format else 'invalid',
            'elv_status': 'unknown',
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
        """Get remaining EmailListVerify credits (if available via API)"""
        # EmailListVerify doesn't provide a direct credits endpoint in their documentation
        # This method is kept for compatibility with the existing interface
        logger.info("EmailListVerify credit checking not implemented")
        return None

    def validate_api_key(self) -> bool:
        """Test if API key is valid"""
        if not self.enabled or not self.api_key:
            return False

        try:
            # Test with a simple validation call
            response = requests.get(
                self.base_url,
                params={
                    'secret': self.api_key,
                    'email': 'test@example.com'
                },
                timeout=self.timeout
            )

            # Check if we get a valid response (even for test email)
            return response.status_code == 200

        except Exception as e:
            logger.error(f"EmailListVerify API key validation failed: {str(e)}")
            return False

# Factory function for easy integration
def create_emaillistverify_validator():
    """Create EmailListVerify validator instance"""
    return EmailListVerifyValidator()