"""
Contact Cleanup Utilities for SalesBreachPro
Functions to completely clean contact data for fresh campaign testing
"""
from models.database import db, Contact, Email, EmailSequence, Response, ContactCampaignStatus
from typing import List, Optional

def deep_clean_contact_campaign_data(contact_id: int, campaign_id: int) -> dict:
    """
    Completely remove all data for a contact in a specific campaign.
    This ensures when they're re-added, they start completely fresh.
    """
    try:
        contact = Contact.query.get(contact_id)
        if not contact:
            return {'success': False, 'error': 'Contact not found'}

        cleanup_results = {
            'success': True,
            'contact_email': contact.email,
            'sequences_deleted': 0,
            'emails_deleted': 0,
            'responses_deleted': 0,
            'campaign_status_deleted': False,
            'contact_fields_reset': False
        }

        print(f"Deep cleaning contact {contact.email} data for campaign {campaign_id}")

        # 1. Delete all EmailSequence records for this contact in this campaign
        sequences_deleted = EmailSequence.query.filter_by(
            campaign_id=campaign_id,
            contact_id=contact_id
        ).delete()
        cleanup_results['sequences_deleted'] = sequences_deleted
        print(f"  - Deleted {sequences_deleted} email sequences")

        # 2. Find and delete all Email records for this contact in this campaign
        emails = Email.query.filter_by(campaign_id=campaign_id, contact_id=contact_id).all()

        total_responses_deleted = 0
        for email in emails:
            # Delete any responses associated with this email first
            responses_deleted = Response.query.filter_by(email_id=email.id).delete()
            total_responses_deleted += responses_deleted

            # Delete the email record
            db.session.delete(email)

        cleanup_results['emails_deleted'] = len(emails)
        cleanup_results['responses_deleted'] = total_responses_deleted
        print(f"  - Deleted {len(emails)} email records")
        print(f"  - Deleted {total_responses_deleted} response records")

        # 3. Delete ContactCampaignStatus record if exists
        campaign_status = ContactCampaignStatus.query.filter_by(
            contact_id=contact_id,
            campaign_id=campaign_id
        ).first()

        if campaign_status:
            db.session.delete(campaign_status)
            cleanup_results['campaign_status_deleted'] = True
            print(f"  - Deleted campaign status record")

        # 4. Reset contact's campaign-related fields if this was their only campaign
        other_campaigns_count = Email.query.filter(
            Email.contact_id == contact_id,
            Email.campaign_id != campaign_id
        ).count()

        if other_campaigns_count == 0:
            # This contact is not in any other campaigns, safe to reset all tracking fields
            contact.last_contacted_at = None
            contact.last_contacted = None
            cleanup_results['contact_fields_reset'] = True
            print(f"  - Reset contact tracking fields (no other campaigns)")

        db.session.commit()
        print(f"✓ Deep cleanup completed for {contact.email}")

        return cleanup_results

    except Exception as e:
        db.session.rollback()
        print(f"✗ Error during deep cleanup: {e}")
        return {'success': False, 'error': str(e)}


def reset_contact_for_fresh_testing(contact_id: int, campaign_id: int) -> dict:
    """
    Prepare a contact for fresh testing by clearing all their campaign data.
    This is useful when you want to test sequences from the beginning.
    """
    try:
        contact = Contact.query.get(contact_id)
        if not contact:
            return {'success': False, 'error': 'Contact not found'}

        print(f"Resetting contact {contact.email} for fresh testing in campaign {campaign_id}")

        # First, do a deep clean
        cleanup_result = deep_clean_contact_campaign_data(contact_id, campaign_id)

        if not cleanup_result['success']:
            return cleanup_result

        # Additional reset for testing: clear any engagement history that might affect behavior
        # Note: We're being careful not to affect other campaigns

        reset_results = cleanup_result.copy()
        reset_results['fresh_testing_ready'] = True

        print(f"✓ Contact {contact.email} is now ready for fresh campaign testing")

        return reset_results

    except Exception as e:
        print(f"✗ Error preparing contact for fresh testing: {e}")
        return {'success': False, 'error': str(e)}


def bulk_clean_campaign_contacts(campaign_id: int, contact_ids: Optional[List[int]] = None) -> dict:
    """
    Clean multiple contacts from a campaign at once.
    If contact_ids is None, cleans ALL contacts from the campaign.
    """
    try:
        from models.database import Campaign

        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return {'success': False, 'error': 'Campaign not found'}

        if contact_ids is None:
            # Get all contacts in this campaign
            contact_emails = db.session.query(Email.contact_id).filter_by(campaign_id=campaign_id).distinct().all()
            contact_ids = [email.contact_id for email in contact_emails]

        results = {
            'success': True,
            'campaign_name': campaign.name,
            'contacts_processed': 0,
            'contacts_cleaned': 0,
            'errors': [],
            'details': []
        }

        for contact_id in contact_ids:
            try:
                cleanup_result = deep_clean_contact_campaign_data(contact_id, campaign_id)
                results['contacts_processed'] += 1

                if cleanup_result['success']:
                    results['contacts_cleaned'] += 1
                    results['details'].append({
                        'contact_id': contact_id,
                        'contact_email': cleanup_result.get('contact_email', 'unknown'),
                        'cleanup_summary': cleanup_result
                    })
                else:
                    results['errors'].append(f"Failed to clean contact {contact_id}: {cleanup_result.get('error', 'unknown error')}")

            except Exception as e:
                results['errors'].append(f"Error cleaning contact {contact_id}: {str(e)}")

        print(f"✓ Bulk cleanup completed: {results['contacts_cleaned']}/{results['contacts_processed']} contacts cleaned")

        return results

    except Exception as e:
        return {'success': False, 'error': str(e)}


def verify_contact_clean_state(contact_id: int, campaign_id: int) -> dict:
    """
    Verify that a contact has been completely cleaned from a campaign.
    Useful for debugging and confirmation.
    """
    try:
        contact = Contact.query.get(contact_id)
        if not contact:
            return {'success': False, 'error': 'Contact not found'}

        verification = {
            'contact_id': contact_id,
            'contact_email': contact.email,
            'campaign_id': campaign_id,
            'is_clean': True,
            'issues_found': [],
            'details': {}
        }

        # Check for any remaining EmailSequence records
        sequences_count = EmailSequence.query.filter_by(
            campaign_id=campaign_id,
            contact_id=contact_id
        ).count()
        verification['details']['sequences_remaining'] = sequences_count

        if sequences_count > 0:
            verification['is_clean'] = False
            verification['issues_found'].append(f"{sequences_count} email sequences still exist")

        # Check for any remaining Email records
        emails_count = Email.query.filter_by(
            campaign_id=campaign_id,
            contact_id=contact_id
        ).count()
        verification['details']['emails_remaining'] = emails_count

        if emails_count > 0:
            verification['is_clean'] = False
            verification['issues_found'].append(f"{emails_count} email records still exist")

        # Check for ContactCampaignStatus
        campaign_status_exists = ContactCampaignStatus.query.filter_by(
            contact_id=contact_id,
            campaign_id=campaign_id
        ).first() is not None
        verification['details']['campaign_status_exists'] = campaign_status_exists

        if campaign_status_exists:
            verification['is_clean'] = False
            verification['issues_found'].append("Campaign status record still exists")

        verification['success'] = True

        if verification['is_clean']:
            print(f"✓ Contact {contact.email} is completely clean for campaign {campaign_id}")
        else:
            print(f"⚠ Contact {contact.email} still has data in campaign {campaign_id}: {', '.join(verification['issues_found'])}")

        return verification

    except Exception as e:
        return {'success': False, 'error': str(e)}