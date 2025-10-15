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
            Contact.blocked_at.is_(None)  # Exclude blocked contacts from auto-enrollment
        ]

        # Always check all active contacts (removed timestamp filtering that was preventing enrollment)
        logger.info(f"Campaign '{campaign.name}': checking all active contacts for enrollment eligibility")

        # Filter by industry/business type based on campaign settings
        if campaign.target_industries:
            # Filter by target industries
            query_filters.append(Contact.industry.in_(campaign.target_industries))
        if campaign.target_business_types:
            # Filter by target business types
            query_filters.append(Contact.business_type.in_(campaign.target_business_types))
        if campaign.target_company_sizes:
            # Filter by target company sizes
            query_filters.append(Contact.company_size.in_(campaign.target_company_sizes))
        
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
    
    def check_industry_match_campaigns(self, contact_id: int) -> int:
        """
        Check if a contact should be auto-enrolled in any campaigns based on their industry/business profile.
        This is called when a contact's profile is updated.
        Returns the number of campaigns the contact was enrolled in.
        """
        from models.database import Contact, Campaign

        try:
            contact = Contact.query.get(contact_id)
            if not contact:
                return 0

            # Find campaigns that auto-enroll contacts
            matching_campaigns = Campaign.query.filter(
                and_(
                    Campaign.active == True,
                    Campaign.auto_enroll == True,
                    Campaign.status.in_(['active', 'draft'])
                )
            ).all()

            # Filter campaigns that match the contact's industry/business profile
            relevant_campaigns = []
            for campaign in matching_campaigns:
                match = False

                # Check industry match
                if campaign.target_industries and contact.industry:
                    if contact.industry in campaign.target_industries:
                        match = True

                # Check business type match
                if campaign.target_business_types and contact.business_type:
                    if contact.business_type in campaign.target_business_types:
                        match = True

                # Check company size match
                if campaign.target_company_sizes and contact.company_size:
                    if contact.company_size in campaign.target_company_sizes:
                        match = True

                if match:
                    relevant_campaigns.append(campaign)

            enrolled_count = 0
            for campaign in relevant_campaigns:
                if self.enroll_single_contact(contact.id, campaign.id):
                    enrolled_count += 1

            logger.info(f"Auto-enrolled contact {contact.email} into {enrolled_count} campaigns based on industry profile")
            return enrolled_count

        except Exception as e:
            logger.error(f"Error checking industry match campaigns for contact {contact_id}: {str(e)}")
            return 0
    
    def get_contact_priority_score(self, contact) -> float:
        """Calculate priority score for a contact based on industry and company profile"""
        try:
            base_score = 5.0

            # Adjust based on company size (if available)
            if hasattr(contact, 'company_size') and contact.company_size:
                if 'large' in contact.company_size.lower() or 'enterprise' in contact.company_size.lower():
                    base_score += 2.0
                elif '51-200' in contact.company_size or '201-500' in contact.company_size:
                    base_score += 1.0
                elif 'small' in contact.company_size.lower() or '1-10' in contact.company_size:
                    base_score -= 0.5

            # Adjust based on industry (high-value industries get priority)
            high_value_industries = ['technology', 'finance', 'healthcare', 'saas', 'enterprise software']
            if contact.industry and contact.industry.lower() in high_value_industries:
                base_score += 1.5

            return min(10.0, max(0.0, base_score))

        except Exception as e:
            logger.error(f"Error calculating priority score for contact {contact.id}: {str(e)}")
            return 5.0
    
    def enroll_contact_standard(self, contact, campaign, template):
        """Standard enrollment method - uses EmailSequenceService for proper scheduling"""
        try:
            from services.email_sequence_service import EmailSequenceService

            # Use the email sequence service for proper enrollment with correct timing
            sequence_service = EmailSequenceService()

            # Enroll contact using the proper sequence service
            result = sequence_service.enroll_contact_in_campaign(
                contact_id=contact.id,
                campaign_id=campaign.id,
                force_breach_check=False  # No breach checking in industry-based system
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