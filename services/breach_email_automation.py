"""
Advanced Breach Email Automation Service
Integrates with the current pipeline to provide intelligent, automated breach response emails
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from services.email_service import create_email_service
from models.database import db, Contact, Campaign, Email, EmailTemplate, Breach

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BreachEmailAutomation:
    """Advanced breach response email automation service"""
    
    def __init__(self):
        # Initialize email service
        class AutoConfig:
            def __init__(self):
                from models.database import Settings
                self.BREVO_API_KEY = Settings.get_setting('brevo_api_key', '')
                self.DEFAULT_SENDER_EMAIL = Settings.get_setting('sender_email', '')
                self.DEFAULT_SENDER_NAME = Settings.get_setting('sender_name', 'Security Team')
        
        self.email_service = create_email_service(AutoConfig())
        logger.info("Breach Email Automation Service initialized")
    
    def process_new_breach_contact(self, contact_id: int, breach_data: Dict) -> Dict:
        """Process a newly added contact with breach data using advanced automation"""
        try:
            # Get contact details
            contact = Contact.query.get(contact_id)
            if not contact:
                return {'success': False, 'error': 'Contact not found'}
            
            # Convert contact to dict for email service
            contact_dict = {
                'id': contact.id,
                'email': contact.email,
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'company': contact.company,
                'industry': contact.industry,
                'title': contact.title
            }
            
            # Get or create breach data
            if not breach_data:
                breach_data = self.get_breach_data_for_contact(contact)
            
            # Schedule intelligent email sequence
            result = self.email_service.schedule_breach_sequence(contact_dict, breach_data)
            
            if result['success']:
                # Update contact with automation info
                contact.last_contacted = datetime.utcnow()
                contact.breach_status = breach_data.get('severity', 'medium')
                
                # Create campaign record for tracking
                campaign_name = f"Auto Breach Response - {contact.company} - {breach_data.get('breach_name', 'Security Alert')}"
                campaign = self.create_automation_campaign(campaign_name, contact, breach_data, result)
                
                db.session.commit()
                
                logger.info(f"Successfully processed breach contact {contact.email} with {result['emails_scheduled']} emails scheduled")
                
                return {
                    'success': True,
                    'contact_id': contact_id,
                    'campaign_id': campaign.id if campaign else None,
                    'emails_scheduled': result['emails_scheduled'],
                    'sequence_type': result['sequence_type'],
                    'industry': result['industry']
                }
            else:
                return {'success': False, 'error': result.get('error', 'Unknown error')}
                
        except Exception as e:
            logger.error(f"Error processing breach contact {contact_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_breach_data_for_contact(self, contact: Contact) -> Dict:
        """Get breach data for a contact from the database"""
        try:
            # Look for breach data by domain
            domain = contact.domain or contact.email.split('@')[1] if '@' in contact.email else None
            
            if domain:
                breach = Breach.query.filter_by(domain=domain).first()
                if breach:
                    return {
                        'breach_name': breach.breach_name,
                        'risk_score': breach.risk_score,
                        'severity': breach.severity,
                        'records_affected': breach.records_affected,
                        'data_types': breach.data_types,
                        'breach_year': breach.breach_year
                    }
            
            # Default breach data if no specific breach found
            return {
                'breach_name': 'Security Vulnerability Assessment Required',
                'risk_score': 6.0,
                'severity': 'medium',
                'records_affected': 'Multiple',
                'data_types': 'Potential business data exposure',
                'breach_year': datetime.now().year
            }
            
        except Exception as e:
            logger.error(f"Error getting breach data for contact {contact.id}: {str(e)}")
            return {
                'breach_name': 'Security Alert',
                'risk_score': 5.0,
                'severity': 'medium',
                'records_affected': 'Unknown',
                'data_types': 'Various data types',
                'breach_year': datetime.now().year
            }
    
    def create_automation_campaign(self, name: str, contact: Contact, breach_data: Dict, automation_result: Dict) -> Optional[Campaign]:
        """Create a campaign record for the automated breach response"""
        try:
            campaign = Campaign(
                name=name,
                template_type='breach_automation',
                status='active',
                created_at=datetime.utcnow(),
                total_contacts=1,
                sent_count=0,  # Will be updated as emails are sent
                response_count=0,
                active=True,
                description=f"Automated breach response for {contact.company} - Risk Level: {breach_data.get('risk_score', 'Unknown')}",
                sender_email=self.email_service.default_from_email,
                sender_name=self.email_service.default_from_name,
                auto_enroll=False,  # This is a one-time automation
                target_risk_levels=[breach_data.get('severity', 'medium')]
            )
            
            db.session.add(campaign)
            db.session.flush()  # Get the ID
            
            return campaign
            
        except Exception as e:
            logger.error(f"Error creating automation campaign: {str(e)}")
            return None
    
    def process_behavioral_trigger(self, email_id: int, event_type: str) -> Dict:
        """Process behavioral triggers when contacts interact with emails"""
        try:
            # Get email record
            email = Email.query.get(email_id)
            if not email:
                return {'success': False, 'error': 'Email not found'}
            
            contact = Contact.query.get(email.contact_id)
            if not contact:
                return {'success': False, 'error': 'Contact not found'}
            
            # Convert contact to dict
            contact_dict = {
                'id': contact.id,
                'email': contact.email,
                'first_name': contact.first_name,
                'company': contact.company,
                'industry': contact.industry
            }
            
            # Determine trigger action based on event
            trigger_actions = {
                'opened_no_click': {
                    'delay_hours': 4,
                    'template_type': 'simplified_cta',
                    'subject': f'Quick Security Question for {contact.company}',
                    'priority': 'medium'
                },
                'clicked_no_response': {
                    'delay_hours': 24,
                    'template_type': 'calendar_reminder',
                    'subject': f'Let\'s Schedule That Security Call - {contact.company}',
                    'priority': 'high'
                },
                'multiple_opens': {
                    'delay_hours': 1,
                    'template_type': 'priority_contact',
                    'subject': f'Priority Security Consultation - {contact.company}',
                    'priority': 'high'
                }
            }
            
            if event_type not in trigger_actions:
                return {'success': False, 'error': f'Unknown trigger type: {event_type}'}
            
            action = trigger_actions[event_type]
            
            # Create follow-up content
            follow_up_content = self.create_follow_up_content(action['template_type'], contact_dict)
            
            # Schedule follow-up email
            send_time = datetime.now() + timedelta(hours=action['delay_hours'])
            
            result = self.email_service.schedule_single_email(
                contact=contact_dict,
                subject=action['subject'],
                content=follow_up_content,
                send_time=send_time,
                priority=action['priority']
            )
            
            if result['success']:
                logger.info(f"Scheduled behavioral trigger {event_type} for {contact.email}")
                return {
                    'success': True,
                    'trigger_type': event_type,
                    'scheduled_for': send_time.isoformat(),
                    'message_id': result.get('message_id')
                }
            else:
                return {'success': False, 'error': result.get('error')}
                
        except Exception as e:
            logger.error(f"Error processing behavioral trigger: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def create_follow_up_content(self, template_type: str, contact: Dict) -> str:
        """Create follow-up email content based on template type"""
        
        follow_up_templates = {
            'simplified_cta': '''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #0066cc;">Quick Question for {company}</h2>
                
                <p>Hi {first_name},</p>
                <p>I noticed you viewed our security alert about {company}. Do you have 15 minutes this week for a quick security discussion?</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://app.com/quick-call/{contact_id}" 
                       style="background: #0066cc; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Yes, Let's Talk (15 minutes)
                    </a>
                </div>
                
                <p>Or simply reply to this email with a time that works for you.</p>
                
                <p>Best regards,<br>Security Team</p>
            </div>
            ''',
            'calendar_reminder': '''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #ff6600;">Let's Schedule That Security Call</h2>
                
                <p>Hi {first_name},</p>
                <p>Thanks for your interest in {company}'s security consultation. Let's get that call scheduled!</p>
                
                <div style="background: #fff8e1; padding: 20px; margin: 20px 0; border-radius: 5px;">
                    <h3>Available This Week:</h3>
                    <ul>
                        <li>Tuesday 2:00 PM - 4:00 PM</li>
                        <li>Wednesday 10:00 AM - 12:00 PM</li>
                        <li>Thursday 1:00 PM - 3:00 PM</li>
                        <li>Friday 9:00 AM - 11:00 AM</li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://app.com/schedule/{contact_id}" 
                       style="background: #ff6600; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Choose Your Time
                    </a>
                </div>
                
                <p>Looking forward to helping {company} strengthen its security posture!</p>
            </div>
            ''',
            'priority_contact': '''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #ff0000;">Priority Security Consultation for {company}</h2>
                
                <p>Hi {first_name},</p>
                <p>I can see you're actively reviewing our security information for {company}. Given your level of interest, I'd like to offer you priority access to our security team.</p>
                
                <div style="background: #ffeeee; padding: 20px; margin: 20px 0; border-radius: 5px; border-left: 5px solid #ff0000;">
                    <h3>🚨 Priority Benefits:</h3>
                    <ul>
                        <li>Immediate consultation (today if needed)</li>
                        <li>Direct line to our senior security expert</li>
                        <li>Expedited security assessment</li>
                        <li>Complimentary follow-up review</li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://app.com/priority-contact/{contact_id}" 
                       style="background: #ff0000; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        🚨 Contact Security Expert Now
                    </a>
                </div>
                
                <p>Or call directly: <strong>+1-XXX-XXX-XXXX</strong> (mention priority code: {company})</p>
            </div>
            '''
        }
        
        template = follow_up_templates.get(template_type, follow_up_templates['simplified_cta'])
        
        # Replace variables
        content = template.format(
            company=contact.get('company', 'Your Organization'),
            first_name=contact.get('first_name', 'there'),
            contact_id=contact.get('id', 'unknown')
        )
        
        return content
    
    def get_automation_analytics(self, days: int = 30) -> Dict:
        """Get analytics for automated breach response campaigns"""
        try:
            # Get advanced analytics from email service
            analytics = self.email_service.get_advanced_analytics(days=days)
            
            # Add automation-specific metrics
            automation_metrics = {
                'automated_sequences_sent': 0,
                'critical_alerts_sent': 0,
                'behavioral_triggers_fired': 0,
                'automation_conversion_rate': 0,
                'avg_sequence_completion_rate': 0
            }
            
            # Get automation campaigns
            automation_campaigns = Campaign.query.filter_by(template_type='breach_automation').filter(
                Campaign.created_at >= datetime.now() - timedelta(days=days)
            ).all()
            
            automation_metrics['automated_sequences_sent'] = len(automation_campaigns)
            
            # Combine analytics
            analytics['automation_metrics'] = automation_metrics
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting automation analytics: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def setup_automation_webhooks(self) -> Dict:
        """Setup webhooks for real-time behavioral triggers"""
        try:
            # Setup behavioral triggers in email service
            result = self.email_service.setup_behavioral_triggers()
            
            if result['success']:
                logger.info("Automation webhooks and triggers setup successfully")
                return {
                    'success': True,
                    'triggers_setup': result['triggers_count'],
                    'webhook_url': '/webhook/brevo'
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error setting up automation webhooks: {str(e)}")
            return {'success': False, 'error': str(e)}


# Factory function
def create_breach_automation_service():
    """Factory function to create breach email automation service"""
    return BreachEmailAutomation()