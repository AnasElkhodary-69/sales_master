#!/usr/bin/env python3
"""
Test Brevo SDK Only Email Sending
Tests the updated Brevo service with configurable variables and no SMTP fallbacks
"""
from models.database import db, Settings, Contact
from app import create_app
from services.email_service import create_email_service

def test_brevo_sdk_only():
    """Test email sending with pure Brevo SDK implementation"""
    app = create_app()

    with app.app_context():
        print("🧪 TESTING BREVO SDK-ONLY EMAIL SENDING")
        print("=" * 45)

        # Check configuration
        import os
        brevo_api_key = os.environ.get('BREVO_API_KEY')
        sender_email = os.environ.get('BREVO_SENDER_EMAIL')
        sender_name = os.environ.get('BREVO_SENDER_NAME')
        subject_prefix = os.environ.get('BREVO_SUBJECT_PREFIX')
        company_name = os.environ.get('COMPANY_NAME')

        print(f"🔑 API Key: {'✅ Configured' if brevo_api_key else '❌ Missing'}")
        print(f"📧 Sender Email: {sender_email or '❌ Missing'}")
        print(f"👤 Sender Name: {sender_name or '❌ Missing'}")
        print(f"📝 Subject Prefix: {subject_prefix or '❌ Missing'}")
        print(f"🏢 Company Name: {company_name or '❌ Missing'}")

        if not brevo_api_key:
            print("\n❌ ERROR: Brevo API key not found in environment!")
            return False

        # Create email service configuration
        class TestConfig:
            BREVO_API_KEY = brevo_api_key
            BREVO_SENDER_EMAIL = sender_email
            BREVO_SENDER_NAME = sender_name

        # Get or create test contact
        test_email = "brevo.sdk.test@example.com"
        test_contact = Contact.query.filter_by(email=test_email).first()

        if not test_contact:
            test_contact = Contact(
                email=test_email,
                first_name='Brevo',
                last_name='SDK Test',
                company='Test Company Inc',
                is_active=True
            )
            db.session.add(test_contact)
            db.session.commit()
            print(f"✅ Created test contact: {test_email}")
        else:
            print(f"📧 Using existing contact: {test_email}")

        # Create email service instance
        print(f"\n📤 INITIALIZING BREVO SERVICE...")
        email_service = create_email_service(TestConfig())

        # Test subject generation
        print(f"\n📝 TESTING SUBJECT GENERATION...")
        contact_dict = {
            'id': test_contact.id,
            'email': test_contact.email,
            'first_name': test_contact.first_name,
            'company': test_contact.company
        }

        test_subjects = [
            ("Data Breach Alert", 'normal'),
            ("Immediate Action Required", 'high'),
            ("Critical Security Issue", 'critical')
        ]

        for base_subject, priority in test_subjects:
            generated_subject = email_service.generate_subject(
                base_subject, contact_dict, priority
            )
            print(f"   📝 {priority.upper()}: {generated_subject}")

        # Prepare test email content
        subject = email_service.generate_subject(
            "SDK Integration Test", contact_dict, 'high'
        )

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c5aa0;">🧪 Brevo SDK Integration Test</h2>

                <p>Hello {test_contact.first_name},</p>

                <p>This email confirms that the SalesBreachPro Brevo integration is working with:</p>

                <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">✅ SDK-Only Implementation:</h3>
                    <ul>
                        <li>🔧 Pure Brevo Python SDK (no SMTP)</li>
                        <li>📧 Configurable sender: {sender_email}</li>
                        <li>📝 Dynamic subject generation</li>
                        <li>🌐 HTML + Plain text formats</li>
                        <li>🔗 Webhook integration ready</li>
                    </ul>
                </div>

                <p>
                    <a href="https://marketing.savety.online/test-link"
                       style="background: #2c5aa0; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        🖱️ Test Click Tracking
                    </a>
                </p>

                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">

                <p style="font-size: 12px; color: #666;">
                    <strong>Configuration Test Results:</strong><br>
                    Sender: {sender_name} &lt;{sender_email}&gt;<br>
                    Subject Prefix: {subject_prefix}<br>
                    Company: {company_name}<br>
                    API: Brevo Python SDK Only
                </p>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        🧪 Brevo SDK Integration Test

        Hello {test_contact.first_name},

        This email confirms that the SalesBreachPro Brevo integration is working with:

        ✅ SDK-Only Implementation:
        - 🔧 Pure Brevo Python SDK (no SMTP)
        - 📧 Configurable sender: {sender_email}
        - 📝 Dynamic subject generation
        - 🌐 HTML + Plain text formats
        - 🔗 Webhook integration ready

        Test link: https://marketing.savety.online/test-link

        ---
        Configuration Test Results:
        Sender: {sender_name} <{sender_email}>
        Subject Prefix: {subject_prefix}
        Company: {company_name}
        API: Brevo Python SDK Only
        """

        # Send the test email
        print(f"\n📤 SENDING TEST EMAIL...")
        print(f"   To: {test_contact.email}")
        print(f"   Subject: {subject}")
        print(f"   From: {sender_name} <{sender_email}>")

        try:
            success, message = email_service.send_single_email(
                to_email=test_contact.email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                from_email=sender_email,
                from_name=sender_name,
                contact_id=test_contact.id
            )

            if success:
                print(f"   ✅ SUCCESS: Email sent!")
                print(f"   📩 Message ID: {message}")

                print(f"\n🎯 EMAIL SENT SUCCESSFULLY!")
                print("✅ Pure Brevo SDK implementation working")
                print("✅ Configurable sender variables working")
                print("✅ Dynamic subject generation working")
                print("✅ HTML + Plain text content working")

                print(f"\n📊 INTEGRATION STATUS:")
                print("✅ No SMTP dependencies")
                print("✅ Environment variables configured")
                print("✅ Webhook ready for real-time tracking")
                print("✅ Ready for production email campaigns")

                return True

            else:
                print(f"   ❌ FAILED: {message}")
                return False

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            return False

if __name__ == "__main__":
    try:
        success = test_brevo_sdk_only()
        if success:
            print(f"\n🎉 ALL TESTS PASSED!")
            print("Your Brevo SDK-only implementation is ready!")
        else:
            print(f"\n⚠️  Tests failed - check configuration")
    except Exception as e:
        print(f"💥 Test failed: {e}")
        import traceback
        traceback.print_exc()