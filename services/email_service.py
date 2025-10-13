"""
Email Service Factory for SalesBreachPro
Provides a unified interface to create Brevo email services
"""

def create_email_service(config):
    """Factory function to create modern Brevo email service"""
    # Use modern Brevo service (brevo-python SDK)
    from .brevo_modern_service import BrevoModernService
    return BrevoModernService(config)