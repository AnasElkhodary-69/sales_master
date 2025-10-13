"""
Webhook Management Service for SalesBreachPro
Handles dynamic webhook registration with Brevo API
"""
import os
import logging
from typing import Dict, List, Optional, Tuple
import brevo_python
from brevo_python.rest import ApiException

logger = logging.getLogger(__name__)

class WebhookManager:
    """Manages webhook registration and updates with Brevo"""

    def __init__(self, api_key: str = None):
        """Initialize webhook manager with Brevo API"""
        self.api_key = api_key or os.getenv('BREVO_API_KEY')
        if not self.api_key:
            # Try to get from database settings
            try:
                from models.database import Settings
                self.api_key = Settings.get_setting('brevo_api_key', '')
            except:
                self.api_key = ''

        if not self.api_key:
            logger.error("No Brevo API key found for webhook management")
            return

        # Configure API client
        configuration = brevo_python.Configuration()
        configuration.api_key['api-key'] = self.api_key
        api_client = brevo_python.ApiClient(configuration)

        # Initialize webhook API
        self.webhooks_api = brevo_python.WebhooksApi(api_client)

        logger.info("Webhook Manager initialized successfully")

    def get_webhook_url(self) -> str:
        """Get configured webhook URL from environment or settings"""
        # Try environment first
        webhook_url = os.getenv('BREVO_WEBHOOK_URL')

        if not webhook_url:
            # Try database settings
            try:
                from models.database import Settings
                webhook_url = Settings.get_setting('brevo_webhook_url', 'http://localhost:5000/webhooks/brevo')
            except:
                webhook_url = 'http://localhost:5000/webhooks/brevo'

        return webhook_url

    def get_webhook_secret(self) -> str:
        """Get webhook secret for signature verification"""
        secret = os.getenv('BREVO_WEBHOOK_SECRET')

        if not secret:
            try:
                from models.database import Settings
                secret = Settings.get_setting('brevo_webhook_secret', '')
            except:
                secret = ''

        return secret

    def list_existing_webhooks(self) -> List[Dict]:
        """List all existing webhooks in Brevo"""
        try:
            if not self.api_key:
                return []

            api_response = self.webhooks_api.get_webhooks()
            webhooks = []

            for webhook in api_response.webhooks:
                webhooks.append({
                    'id': webhook.id,
                    'description': webhook.description,
                    'url': webhook.url,
                    'events': webhook.events,
                    'type': webhook.type,
                    'created_at': webhook.created_at,
                    'modified_at': webhook.modified_at
                })

            logger.info(f"Found {len(webhooks)} existing webhooks")
            return webhooks

        except ApiException as e:
            logger.error(f"Error listing webhooks: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing webhooks: {e}")
            return []

    def create_transactional_webhook(self, webhook_url: str = None, description: str = "SalesBreachPro Transactional Events") -> Tuple[bool, str]:
        """Create a new transactional webhook for all email events"""
        try:
            if not self.api_key:
                return False, "No API key configured"

            webhook_url = webhook_url or self.get_webhook_url()

            # Define all transactional events we want to track (using correct Brevo event names)
            events = [
                'delivered', 'opened', 'click', 'hardBounce', 'softBounce',
                'spam', 'blocked', 'deferred', 'unsubscribed'
            ]

            # Create webhook request
            create_webhook = brevo_python.CreateWebhook(
                url=webhook_url,
                description=description,
                events=events,
                type='transactional'
            )

            # Create the webhook
            api_response = self.webhooks_api.create_webhook(create_webhook)

            logger.info(f"Created transactional webhook with ID: {api_response.id}")
            return True, f"Webhook created successfully with ID: {api_response.id}"

        except ApiException as e:
            error_msg = f"Brevo API error creating webhook: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error creating webhook: {e}"
            logger.error(error_msg)
            return False, error_msg

    def update_webhook_url(self, webhook_id: int, new_url: str) -> Tuple[bool, str]:
        """Update an existing webhook URL"""
        try:
            if not self.api_key:
                return False, "No API key configured"

            # Get existing webhook details
            existing_webhook = self.webhooks_api.get_webhook(webhook_id)

            # Update webhook request
            update_webhook = brevo_python.UpdateWebhook(
                url=new_url,
                description=existing_webhook.description,
                events=existing_webhook.events
            )

            # Update the webhook
            self.webhooks_api.update_webhook(webhook_id, update_webhook)

            logger.info(f"Updated webhook {webhook_id} with new URL: {new_url}")
            return True, f"Webhook {webhook_id} updated successfully"

        except ApiException as e:
            error_msg = f"Brevo API error updating webhook: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error updating webhook: {e}"
            logger.error(error_msg)
            return False, error_msg

    def delete_webhook(self, webhook_id: int) -> Tuple[bool, str]:
        """Delete a webhook"""
        try:
            if not self.api_key:
                return False, "No API key configured"

            self.webhooks_api.delete_webhook(webhook_id)

            logger.info(f"Deleted webhook {webhook_id}")
            return True, f"Webhook {webhook_id} deleted successfully"

        except ApiException as e:
            error_msg = f"Brevo API error deleting webhook: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error deleting webhook: {e}"
            logger.error(error_msg)
            return False, error_msg

    def setup_webhooks(self, force_recreate: bool = False) -> Dict:
        """Set up webhooks for the application"""
        results = {
            'success': True,
            'messages': [],
            'webhooks_created': 0,
            'webhooks_updated': 0,
            'errors': []
        }

        try:
            current_webhook_url = self.get_webhook_url()
            existing_webhooks = self.list_existing_webhooks()

            # Check if we already have a webhook for our URL
            matching_webhook = None
            for webhook in existing_webhooks:
                if webhook['url'] == current_webhook_url and webhook['type'] == 'transactional':
                    matching_webhook = webhook
                    break

            if matching_webhook and not force_recreate:
                results['messages'].append(f"Webhook already exists for {current_webhook_url}")
                logger.info(f"Webhook already configured for {current_webhook_url}")
            else:
                if matching_webhook and force_recreate:
                    # Delete existing webhook
                    success, message = self.delete_webhook(matching_webhook['id'])
                    if success:
                        results['messages'].append(f"Deleted existing webhook: {message}")
                    else:
                        results['errors'].append(f"Error deleting existing webhook: {message}")

                # Create new webhook
                success, message = self.create_transactional_webhook(current_webhook_url)
                if success:
                    results['webhooks_created'] += 1
                    results['messages'].append(f"Created new webhook: {message}")
                else:
                    results['success'] = False
                    results['errors'].append(f"Error creating webhook: {message}")

            # Update settings with current webhook URL
            try:
                from models.database import Settings
                Settings.set_setting('brevo_webhook_url', current_webhook_url, 'Current Brevo webhook URL')
                Settings.set_setting('brevo_webhook_secret', self.get_webhook_secret(), 'Brevo webhook secret for signature verification')
            except Exception as e:
                results['errors'].append(f"Error updating settings: {e}")

        except Exception as e:
            results['success'] = False
            results['errors'].append(f"Unexpected error in webhook setup: {e}")
            logger.error(f"Error in webhook setup: {e}")

        return results

    def test_webhook_connectivity(self) -> Dict:
        """Test webhook connectivity and configuration"""
        test_results = {
            'webhook_url': self.get_webhook_url(),
            'webhook_secret_configured': bool(self.get_webhook_secret()),
            'api_key_configured': bool(self.api_key),
            'existing_webhooks_count': 0,
            'connectivity_test': 'failed',
            'errors': []
        }

        try:
            # Test API connectivity
            existing_webhooks = self.list_existing_webhooks()
            test_results['existing_webhooks_count'] = len(existing_webhooks)
            test_results['connectivity_test'] = 'success'

            logger.info("Webhook connectivity test passed")

        except Exception as e:
            test_results['errors'].append(str(e))
            logger.error(f"Webhook connectivity test failed: {e}")

        return test_results

def create_webhook_manager() -> WebhookManager:
    """Factory function to create webhook manager"""
    return WebhookManager()