#!/usr/bin/env python3
"""
Manual Contact Cleanup Demonstration
Shows the complete contact cleanup process working
"""
from models.database import db, Contact, Email, EmailSequence, Response, ContactCampaignStatus, Campaign
from utils.contact_cleanup import deep_clean_contact_campaign_data, verify_contact_clean_state
from app import create_app

def demo_contact_cleanup():
    """Demonstrate the complete contact cleanup process"""
    app = create_app()

    with app.app_context():
        try:
            print("Contact Cleanup Demonstration")
            print("=" * 40)

            # Find a test contact and campaign
            contact = Contact.query.filter_by(email='webhook-test@example.com').first()
            if not contact:
                contact = Contact.query.first()

            campaign = Campaign.query.first()

            if not contact or not campaign:
                print("[ERROR] No test contact or campaign found")
                return

            print(f"Test Contact: {contact.email} (ID: {contact.id})")
            print(f"Test Campaign: {campaign.name} (ID: {campaign.id})")
            print()

            # Step 1: Show current state
            print("Step 1: Current State Analysis")
            print("-" * 30)

            sequences_count = EmailSequence.query.filter_by(
                contact_id=contact.id,
                campaign_id=campaign.id
            ).count()

            emails_count = Email.query.filter_by(
                contact_id=contact.id,
                campaign_id=campaign.id
            ).count()

            campaign_status = ContactCampaignStatus.query.filter_by(
                contact_id=contact.id,
                campaign_id=campaign.id
            ).first()

            print(f"Current sequences: {sequences_count}")
            print(f"Current emails: {emails_count}")
            print(f"Campaign status exists: {campaign_status is not None}")

            # Step 2: Perform deep clean
            print("\nStep 2: Performing Deep Clean")
            print("-" * 30)

            cleanup_result = deep_clean_contact_campaign_data(contact.id, campaign.id)

            if cleanup_result['success']:
                print("[OK] Deep clean completed successfully!")
                print(f"  - Sequences deleted: {cleanup_result['sequences_deleted']}")
                print(f"  - Emails deleted: {cleanup_result['emails_deleted']}")
                print(f"  - Responses deleted: {cleanup_result['responses_deleted']}")
                print(f"  - Campaign status deleted: {cleanup_result['campaign_status_deleted']}")
                print(f"  - Contact fields reset: {cleanup_result['contact_fields_reset']}")
            else:
                print(f"[ERROR] Deep clean failed: {cleanup_result['error']}")
                return

            # Step 3: Verify cleanup
            print("\nStep 3: Verifying Complete Cleanup")
            print("-" * 30)

            verification = verify_contact_clean_state(contact.id, campaign.id)

            if verification['success']:
                if verification['is_clean']:
                    print("[OK] Contact is completely clean!")
                    print("✓ Ready for fresh sequence testing")
                else:
                    print(f"[WARNING] Cleanup incomplete: {verification['issues_found']}")
                    print(f"Details: {verification['details']}")
            else:
                print(f"[ERROR] Verification failed: {verification['error']}")

            print("\n" + "=" * 40)
            print("CLEANUP DEMONSTRATION COMPLETE")
            print("=" * 40)

            if verification.get('is_clean', False):
                print("SUCCESS: Contact is now in a completely fresh state.")
                print("When re-added to the campaign, they will start from Step 0")
                print("with no previous email history or tracking data.")
                print("\nTEST PROCESS:")
                print("1. Remove contact from campaign (web UI)")
                print("2. Use 'Deep Clean' button for thorough cleanup")
                print("3. Re-add contact to campaign")
                print("4. Contact will start fresh sequence from beginning")
            else:
                print("The contact cleanup process needs attention.")

        except Exception as e:
            print(f"[ERROR] Demo failed: {e}")

if __name__ == "__main__":
    demo_contact_cleanup()