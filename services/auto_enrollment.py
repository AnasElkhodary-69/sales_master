"""
Auto-enrollment service for automatically adding new contacts to campaigns
based on their breach status and campaign settings.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import and_, or_

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoEnrollmentService:
    """Service for automatically enrolling new contacts into campaigns"""
    
    def __init__(self, db):
        self.db = db
    
    def process_auto_enrollment(self) -> Dict[str, int]:
        """
        Process auto-enrollment for all active campaigns with auto-enrollment enabled.
        Returns statistics about the enrollment process.
        """
        from models.database import Campaign, Contact, Email, EmailTemplate
        
        stats = {
            'campaigns_processed': 0,
            'contacts_enrolled': 0,
            'emails_queued': 0,
            'errors': 0
        }
        
        try:
            # Get all active campaigns with auto-enrollment enabled
            auto_campaigns = Campaign.query.filter(
                and_(
                    Campaign.active == True,
                    Campaign.auto_enroll == True,
                    Campaign.status.in_(['active', 'draft'])
                )
            ).all()
            
            logger.info(f"Found {len(auto_campaigns)} campaigns with auto-enrollment enabled")
            
            for campaign in auto_campaigns:
                try:
                    enrolled_count = self._process_campaign_enrollment(campaign)
                    stats['contacts_enrolled'] += enrolled_count
                    stats['campaigns_processed'] += 1
                    
                    # Update last enrollment check timestamp
                    campaign.last_enrollment_check = datetime.utcnow()
                    self.db.session.commit()
                    
                    logger.info(f"Campaign '{campaign.name}': enrolled {enrolled_count} new contacts")
                    
                except Exception as e:
                    logger.error(f"Error processing campaign {campaign.id}: {str(e)}")
                    stats['errors'] += 1
                    continue
            
            logger.info(f"Auto-enrollment completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error in auto-enrollment process: {str(e)}")
            stats['errors'] += 1
            return stats
    
    def _process_campaign_enrollment(self, campaign) -> int:
        """
        Process enrollment for a specific campaign.
        Returns the number of contacts enrolled.
        """
        from models.database import Contact, Email, EmailTemplate, ContactCampaignStatus
        
        # Build query to find eligible contacts
        query_filters = [
            Contact.is_active == True,
            Contact.breach_status != 'unassigned',  # Skip contacts that haven't been scanned yet
            Contact.blocked_at.is_(None)  # Exclude blocked contacts from auto-enrollment
        ]
        
        # Always check all active contacts (removed timestamp filtering that was preventing enrollment)
        logger.info(f"Campaign '{campaign.name}': checking all active contacts for enrollment eligibility")
        
        # Filter by breach status based on campaign settings
        if campaign.target_risk_levels:
            # Use target_risk_levels (new way)
            query_filters.append(Contact.breach_status.in_(campaign.target_risk_levels))
        elif campaign.auto_enroll_breach_status and campaign.auto_enroll_breach_status != 'all':
            # Use auto_enroll_breach_status (legacy way)
            query_filters.append(Contact.breach_status == campaign.auto_enroll_breach_status)
        
        # Find contacts that aren't already in this campaign
        enrolled_contact_ids = self.db.session.query(ContactCampaignStatus.contact_id).filter(
            ContactCampaignStatus.campaign_id == campaign.id
        ).subquery()
        
        query_filters.append(~Contact.id.in_(enrolled_contact_ids))
        
        # Get eligible contacts
        eligible_contacts = Contact.query.filter(and_(*query_filters)).all()
        
        logger.info(f"Campaign '{campaign.name}': found {len(eligible_contacts)} eligible contacts")
        
        if not eligible_contacts:
            return 0
        
        # Get the initial email template for this campaign
        template = EmailTemplate.query.get(campaign.template_id) if campaign.template_id else None
        if not template:
            logger.warning(f"Campaign '{campaign.name}': no template found, skipping enrollment")
            return 0
        
        enrolled_count = 0
        
        for contact in eligible_contacts:
            try:
                # Use standard enrollment method (advanced automation disabled to prevent duplicates)
                # The EmailSequenceService will handle all enrollment properly
                try:
                    self.enroll_contact_standard(contact, campaign, template)
                    enrolled_count += 1
                    logger.info(f"Successfully enrolled {contact.email} using EmailSequenceService")
                    
                except Exception as e:
                    logger.error(f"Failed to enroll {contact.email}: {str(e)}")
                    # Don't try to continue with failed enrollment
                
            except Exception as e:
                logger.error(f"Error enrolling contact {contact.email}: {str(e)}")
                continue
        
        # Update campaign stats
        campaign.total_contacts += enrolled_count
        
        try:
            self.db.session.commit()
            logger.info(f"Successfully enrolled {enrolled_count} contacts into campaign '{campaign.name}'")
        except Exception as e:
            logger.error(f"Error committing enrollment changes: {str(e)}")
            self.db.session.rollback()
            return 0
        
        return enrolled_count
    
    def enroll_single_contact(self, contact_id: int, campaign_id: int) -> bool:
        """
        Manually enroll a single contact into a specific campaign.
        Returns True if successful, False otherwise.
        """
        from models.database import Contact, Campaign, Email, EmailTemplate
        
        try:
            contact = Contact.query.get(contact_id)
            campaign = Campaign.query.get(campaign_id)
            
            if not contact or not campaign:
                logger.error(f"Contact {contact_id} or Campaign {campaign_id} not found")
                return False
            
            # Check if contact is already enrolled (use ContactCampaignStatus, not Email table)
            from models.database import ContactCampaignStatus
            existing_enrollment = ContactCampaignStatus.query.filter(
                and_(
                    ContactCampaignStatus.contact_id == contact_id,
                    ContactCampaignStatus.campaign_id == campaign_id
                )
            ).first()

            if existing_enrollment:
                logger.warning(f"Contact {contact.email} already enrolled in campaign '{campaign.name}'")
                return False
            
            # Get the initial template
            template = EmailTemplate.query.get(campaign.template_id) if campaign.template_id else None
            if not template:
                logger.error(f"No template found for campaign '{campaign.name}'")
                return False
            
            # Use the standard enrollment method to create all required records
            self.enroll_contact_standard(contact, campaign, template)
            
            # Update campaign stats
            campaign.total_contacts += 1
            
            self.db.session.commit()
            
            logger.info(f"Successfully enrolled contact {contact.email} into campaign '{campaign.name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error enrolling single contact: {str(e)}")
            self.db.session.rollback()
            return False
    
    def check_breach_status_campaigns(self, contact_id: int) -> int:
        """
        Check if a contact should be auto-enrolled in any campaigns based on their breach status.
        This is called when a contact's breach status is updated.
        Returns the number of campaigns the contact was enrolled in.
        """
        from models.database import Contact, Campaign
        
        try:
            contact = Contact.query.get(contact_id)
            if not contact:
                return 0
            
            # Find campaigns that auto-enroll contacts with this breach status
            matching_campaigns = Campaign.query.filter(
                and_(
                    Campaign.active == True,
                    Campaign.auto_enroll == True,
                    Campaign.status.in_(['active', 'draft'])
                )
            ).all()
            
            # Filter campaigns that match the contact's breach status
            relevant_campaigns = []
            for campaign in matching_campaigns:
                # Check if contact matches campaign's target risk levels
                if (campaign.target_risk_levels and 
                    contact.breach_status in campaign.target_risk_levels):
                    relevant_campaigns.append(campaign)
                # Or check auto_enroll_breach_status (legacy support)
                elif (campaign.auto_enroll_breach_status and
                      (campaign.auto_enroll_breach_status == contact.breach_status or 
                       campaign.auto_enroll_breach_status == 'all')):
                    relevant_campaigns.append(campaign)
            
            matching_campaigns = relevant_campaigns
            
            enrolled_count = 0
            for campaign in matching_campaigns:
                if self.enroll_single_contact(contact.id, campaign.id):
                    enrolled_count += 1
            
            logger.info(f"Auto-enrolled contact {contact.email} into {enrolled_count} campaigns based on breach status '{contact.breach_status}'")
            return enrolled_count
            
        except Exception as e:
            logger.error(f"Error checking breach status campaigns for contact {contact_id}: {str(e)}")
            return 0
    
    def get_contact_risk_score(self, contact) -> float:
        """Calculate risk score for a contact based on available data"""
        try:
            # Base score from breach status
            status_scores = {
                'high': 8.0,
                'medium': 6.0,
                'low': 4.0,
                'unknown': 5.0
            }
            
            base_score = status_scores.get(contact.breach_status, 5.0)
            
            # Adjust based on company size (if available)
            if hasattr(contact, 'company_size'):
                if contact.company_size and 'large' in contact.company_size.lower():
                    base_score += 1.0
                elif contact.company_size and 'small' in contact.company_size.lower():
                    base_score -= 0.5
            
            # Adjust based on industry risk
            high_risk_industries = ['healthcare', 'finance', 'government', 'education']
            if contact.industry and contact.industry.lower() in high_risk_industries:
                base_score += 0.5
            
            return min(10.0, base_score)
            
        except Exception as e:
            logger.error(f"Error calculating risk score for contact {contact.id}: {str(e)}")
            return 5.0
    
    def enroll_contact_standard(self, contact, campaign, template):
        """Standard enrollment method - uses EmailSequenceService for proper scheduling"""
        try:
            from services.email_sequence_service import EmailSequenceService
            
            # Use the email sequence service for proper enrollment with correct timing
            sequence_service = EmailSequenceService()
            
            # Map contact breach status to template type
            template_type = 'breached' if contact.breach_status in ['high', 'medium'] else 'proactive'
            
            # Enroll contact using the proper sequence service
            result = sequence_service.enroll_contact_in_campaign(
                contact_id=contact.id,
                campaign_id=campaign.id,
                force_breach_check=False  # Use existing breach status
            )
            
            if result['success']:
                logger.info(f"Standard enrollment successful for {contact.email}: {result['emails_scheduled']} emails scheduled")
            else:
                logger.error(f"Standard enrollment failed for {contact.email}: {result.get('error')}")
                raise Exception(result.get('error'))
            
        except Exception as e:
            logger.error(f"Error in standard enrollment for {contact.email}: {str(e)}")
            raise


def create_auto_enrollment_service(db):
    """Factory function to create auto-enrollment service"""
    return AutoEnrollmentService(db)