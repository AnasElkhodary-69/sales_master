"""
Database Seeder - Creates realistic dummy data for immediate UI functionality
No placeholders - everything should work with real data from day 1
"""
from datetime import datetime, timedelta, date
from models.database import (
    db, EmailSequenceConfig, SequenceStep, EmailTemplate, Campaign, 
    Contact, EmailSequence, ContactCampaignStatus, Email, Settings
)
import random

class DatabaseSeeder:
    """Creates realistic dummy data for working system"""
    
    def __init__(self):
        self.sequence_configs = {}
        self.templates = {}
        self.campaigns = {}
        self.contacts = []
    
    def seed_all(self):
        """Seed all data for working system"""
        print("Starting database seeding...")
        
        self.create_sequence_configs()
        self.create_template_library()
        self.create_demo_campaigns() 
        self.create_sample_contacts()
        self.create_email_sequences()
        self.create_sample_settings()
        
        db.session.commit()
        print("Database seeding completed!")
        
        self.print_summary()
    
    def create_sequence_configs(self):
        """Create realistic sequence timing configurations"""
        print("Creating email sequence configurations...")
        
        configs = [
            {
                'name': 'Standard Follow-up Sequence',
                'description': 'Default 5-email sequence with proven timing - most popular choice',
                'steps': [
                    {'step_number': 0, 'delay_days': 0, 'step_name': 'Initial Outreach'},
                    {'step_number': 1, 'delay_days': 2, 'step_name': 'First Follow-up'},
                    {'step_number': 2, 'delay_days': 5, 'step_name': 'Second Follow-up'},
                    {'step_number': 3, 'delay_days': 12, 'step_name': 'Third Follow-up'},
                    {'step_number': 4, 'delay_days': 26, 'step_name': 'Final Follow-up'}
                ]
            },
            {
                'name': 'Aggressive Follow-up Sequence',
                'description': 'Fast-paced 7-email sequence for urgent campaigns and high-priority prospects',
                'steps': [
                    {'step_number': 0, 'delay_days': 0, 'step_name': 'Urgent Alert'},
                    {'step_number': 1, 'delay_days': 1, 'step_name': 'Quick Follow-up'},
                    {'step_number': 2, 'delay_days': 3, 'step_name': 'Persistence Push'},
                    {'step_number': 3, 'delay_days': 7, 'step_name': 'Week Check-in'},
                    {'step_number': 4, 'delay_days': 14, 'step_name': 'Final Push'},
                    {'step_number': 5, 'delay_days': 21, 'step_name': 'Closing Window'},
                    {'step_number': 6, 'delay_days': 30, 'step_name': 'Archive Notice'}
                ]
            },
            {
                'name': 'Gentle Nurture Sequence',
                'description': 'Relationship-building sequence with extended timing for long-term prospects',
                'steps': [
                    {'step_number': 0, 'delay_days': 0, 'step_name': 'Introduction'},
                    {'step_number': 1, 'delay_days': 7, 'step_name': 'Value Share'},
                    {'step_number': 2, 'delay_days': 14, 'step_name': 'Case Study'},
                    {'step_number': 3, 'delay_days': 30, 'step_name': 'Monthly Check-in'},
                    {'step_number': 4, 'delay_days': 60, 'step_name': 'Final Offer'}
                ]
            }
        ]
        
        for config_data in configs:
            config = EmailSequenceConfig(
                name=config_data['name'],
                description=config_data['description'],
                is_active=True
            )
            db.session.add(config)
            db.session.flush()  # Get ID
            
            for step_data in config_data['steps']:
                step = SequenceStep(
                    sequence_config_id=config.id,
                    step_number=step_data['step_number'],
                    delay_days=step_data['delay_days'],
                    step_name=step_data['step_name'],
                    is_active=True
                )
                db.session.add(step)
            
            self.sequence_configs[config_data['name']] = config
        
        print(f"   * Created {len(configs)} sequence configurations")
    
    def create_template_library(self):
        """Create complete template sets for both breached and proactive"""
        print("Creating email template library...")
        
        # Common template variables
        common_vars = ['{{first_name}}', '{{last_name}}', '{{company}}', '{{industry}}', '{{email}}']
        breach_vars = common_vars + ['{{breach_name}}', '{{breach_date}}', '{{risk_level}}', '{{records_affected}}', '{{data_types}}']
        
        # BREACHED EMAIL TEMPLATES
        breached_templates = [
            {
                'step': 0, 'name': 'Urgent Security Alert - Initial',
                'subject': 'URGENT: {{company}} data compromised in {{breach_name}} breach',
                'body': '''Hi {{first_name}},

We discovered that {{company}}'s data was exposed in the recent {{breach_name}} data breach affecting {{records_affected}} records.

This breach included:
- {{data_types}}
- Occurred: {{breach_date}}
- Risk Level: HIGH

We're offering a complimentary security assessment to help you:
* Identify vulnerable data
* Implement protective measures  
* Prevent future breaches

Book your free 15-minute consultation: https://calendly.com/security-team

Best regards,
Security Team
SalesBreachPro''',
                'variables': breach_vars
            },
            {
                'step': 1, 'name': 'Security Follow-up - Day 2',
                'subject': 'Did you see our security alert about {{company}}?',
                'body': '''Hi {{first_name}},

I wanted to make sure you saw my message about {{company}}'s data exposure in the {{breach_name}} breach.

Many companies in {{industry}} have been affected, and the attackers are likely targeting similar organizations.

I have a 15-minute window open today at 2 PM EST if you'd like to discuss immediate protective measures.

Quick call link: https://calendly.com/security-team/15min

Best regards,
Security Team''',
                'variables': breach_vars
            },
            {
                'step': 2, 'name': 'Security Consultation - Day 5',
                'subject': 'Quick question about {{company}}\'s data security',
                'body': '''Hi {{first_name}},

Just a quick question - have you had a chance to review {{company}}'s exposure in the {{breach_name}} incident?

I've helped over 200 companies in {{industry}} secure their data after similar breaches. The process typically takes just 2 weeks and includes:

* Immediate vulnerability assessment
* Custom security implementation plan
* Staff training and awareness program

Would you like me to send over some {{industry}} case studies showing the results?

Best regards,
Security Team''',
                'variables': breach_vars
            },
            {
                'step': 3, 'name': 'Final Security Offer - Day 12',
                'subject': 'Final follow-up: {{breach_name}} impact assessment',
                'body': '''Hi {{first_name}},

I know {{industry}} leaders are busy, but I wanted to reach out one more time about {{company}}'s exposure in the {{breach_name}} breach.

This is my final follow-up on this matter.

If you'd like to discuss how we can help {{company}} avoid similar incidents in the future, I'm available for a brief call this week.

Otherwise, I'll remove you from this specific security alert sequence.

Best regards,
Security Team''',
                'variables': breach_vars
            },
            {
                'step': 4, 'name': 'Archive Notice - Day 26',
                'subject': 'Archiving {{company}}\'s security file',
                'body': '''Hi {{first_name}},

I'm archiving {{company}}'s security consultation file since I haven't heard back.

If circumstances change and you'd like to discuss cybersecurity measures for {{company}} in the future, feel free to reach out anytime.

Wishing you and {{company}} continued success.

Best regards,
Security Team
SalesBreachPro''',
                'variables': breach_vars
            }
        ]
        
        # PROACTIVE EMAIL TEMPLATES
        proactive_templates = [
            {
                'step': 0, 'name': 'Free Security Assessment - Initial',
                'subject': 'Complimentary cybersecurity assessment for {{company}}',
                'body': '''Hi {{first_name}},

{{company}} is exactly the type of {{industry}} company that cyber attackers target most.

I'd like to offer you a complimentary security assessment to identify potential vulnerabilities before they become expensive problems.

This 15-minute review covers:
- Current security posture analysis
- Industry-specific threat identification
- Actionable improvement recommendations

Available times this week: https://calendly.com/security-team

Best regards,
Security Consultant
SalesBreachPro''',
                'variables': common_vars
            },
            {
                'step': 1, 'name': 'Security Value - Day 2',
                'subject': 'Strengthening {{company}}\'s security posture',
                'body': '''Hi {{first_name}},

I hope you had a chance to review my message about {{company}}'s cybersecurity assessment.

Last month, we helped a {{industry}} company similar to {{company}} identify 12 critical vulnerabilities before they were exploited. The assessment took just 15 minutes and saved them potentially hundreds of thousands in damages.

Would you like to see the specific vulnerabilities we typically find in {{industry}} organizations?

Quick call: https://calendly.com/security-team/15min

Best regards,
Security Consultant''',
                'variables': common_vars
            },
            {
                'step': 2, 'name': 'Security Consultation - Day 5',
                'subject': '15-minute security consultation for {{company}}?',
                'body': '''Hi {{first_name}},

I've been researching {{industry}} security trends and noticed that companies like {{company}} face some unique challenges:

- Increased targeting by cybercriminals
- Complex compliance requirements  
- Growing attack surface area

I'd love to share what I'm seeing and get your thoughts on {{company}}'s current security priorities.

Available for a quick 15-minute call this week?

Best regards,
Security Consultant''',
                'variables': common_vars
            },
            {
                'step': 3, 'name': 'Industry Insights - Day 12',
                'subject': 'Industry-specific security insights for {{company}}',
                'body': '''Hi {{first_name}},

I just finished a security analysis for another {{industry}} company and thought you might find the insights valuable for {{company}}.

Key findings that might interest you:
* 3 common vulnerabilities in {{industry}} systems
* Compliance shortcuts that create risk  
* Simple fixes that prevent 80% of attacks

Would you like me to send over the {{industry}} security benchmark report?

Best regards,
Security Consultant''',
                'variables': common_vars
            },
            {
                'step': 4, 'name': 'Final Offer - Day 26',
                'subject': 'Final opportunity: Complimentary security review for {{company}}',
                'body': '''Hi {{first_name}},

This is my final note about the complimentary security assessment for {{company}}.

I understand that security isn't always the top priority when you're focused on growing the business. But with cyber attacks increasing 400% this year in the {{industry}} sector, it's worth a conversation.

If you'd like to take advantage of this complimentary assessment, I'm available through Friday. After that, I'll be focusing on other {{industry}} companies.

Best regards,
Security Consultant
SalesBreachPro''',
                'variables': common_vars
            }
        ]
        
        # Create all templates
        template_count = 0
        for template_data in breached_templates + proactive_templates:
            template_type = 'breached' if template_data in breached_templates else 'proactive'
            
            template = EmailTemplate(
                name=template_data['name'],
                template_type='follow_up' if template_data['step'] > 0 else 'initial',
                risk_level='high' if template_type == 'breached' else 'generic',
                sequence_order=template_data['step'] + 1,
                delay_hours=0,  # Using new sequence system
                sequence_step=template_data['step'],
                breach_template_type=template_type,
                available_variables=template_data['variables'],
                subject_line=template_data['subject'],
                subject=template_data['subject'],
                email_body=template_data['body'],
                content=template_data['body'],
                email_body_html=template_data['body'].replace('\n', '<br>'),
                is_active=True,
                active=True,
                created_at=datetime.utcnow(),
                usage_count=random.randint(5, 50),
                success_rate=random.uniform(0.15, 0.35)
            )
            db.session.add(template)
            template_count += 1
        
        print(f"   * Created {template_count} email templates")
    
    def create_demo_campaigns(self):
        """Create working campaigns with real configuration"""
        print("Creating demo campaigns...")
        
        campaigns_data = [
            {
                'name': 'Q4 Healthcare Security Outreach',
                'description': 'Targeting healthcare organizations for HIPAA compliance and data protection',
                'sequence_config': 'Standard Follow-up Sequence',
                'daily_limit': 25,
                'active': True,
                'status': 'active',
                'auto_enroll': True,
                'target_risk_levels': ['high', 'medium']
            },
            {
                'name': 'Financial Services Data Protection',
                'description': 'SOX and PCI compliance focused campaign for banks and financial institutions',
                'sequence_config': 'Aggressive Follow-up Sequence',
                'daily_limit': 15,
                'active': True,
                'status': 'active',
                'auto_enroll': True,
                'target_risk_levels': ['high']
            },
            {
                'name': 'SMB General Security Awareness',
                'description': 'General cybersecurity education and consultation for small and medium businesses',
                'sequence_config': 'Gentle Nurture Sequence',
                'daily_limit': 50,
                'active': False,
                'status': 'draft',
                'auto_enroll': False,
                'target_risk_levels': ['medium', 'low']
            },
            {
                'name': 'Government Security Initiative',
                'description': 'Specialized security services for government agencies and contractors',
                'sequence_config': 'Standard Follow-up Sequence',
                'daily_limit': 10,
                'active': True,
                'status': 'active',
                'auto_enroll': True,
                'target_risk_levels': ['high', 'medium', 'low']
            }
        ]
        
        for camp_data in campaigns_data:
            sequence_config = self.sequence_configs[camp_data['sequence_config']]
            
            campaign = Campaign(
                name=camp_data['name'],
                description=camp_data['description'],
                template_type='high_risk',
                status=camp_data['status'],
                created_at=datetime.utcnow() - timedelta(days=random.randint(5, 60)),
                total_contacts=random.randint(50, 300),
                sent_count=random.randint(20, 150),
                response_count=random.randint(2, 15),
                active=camp_data['active'],
                daily_limit=camp_data['daily_limit'],
                sender_email='security@salesbreachpro.com',
                sender_name='Security Team',
                target_risk_levels=camp_data['target_risk_levels'],
                auto_enroll=camp_data['auto_enroll'],
                sequence_config_id=sequence_config.id,
                last_enrollment_check=datetime.utcnow() - timedelta(hours=random.randint(1, 24))
            )
            db.session.add(campaign)
            db.session.flush()
            self.campaigns[camp_data['name']] = campaign
        
        print(f"   * Created {len(campaigns_data)} demo campaigns")
    
    def create_sample_contacts(self):
        """Create realistic contacts with various industries"""
        print("Creating sample contacts...")
        
        contacts_data = [
            {'email': 'john.smith@regionalhospital.com', 'first_name': 'John', 'last_name': 'Smith', 
             'company': 'Regional Hospital', 'industry': 'Healthcare', 'title': 'IT Director', 'breach_status': 'high'},
            {'email': 'sarah.jones@techstartup.io', 'first_name': 'Sarah', 'last_name': 'Jones',
             'company': 'TechStartup Inc', 'industry': 'Technology', 'title': 'CTO', 'breach_status': 'medium'},
            {'email': 'mike.wilson@firstnationalbank.com', 'first_name': 'Mike', 'last_name': 'Wilson',
             'company': 'First National Bank', 'industry': 'Finance', 'title': 'Security Manager', 'breach_status': 'high'},
            {'email': 'lisa.davis@cityschools.edu', 'first_name': 'Lisa', 'last_name': 'Davis',
             'company': 'City School District', 'industry': 'Education', 'title': 'IT Administrator', 'breach_status': 'medium'},
            {'email': 'robert.brown@manufacturer.com', 'first_name': 'Robert', 'last_name': 'Brown',
             'company': 'ABC Manufacturing', 'industry': 'Manufacturing', 'title': 'Operations Manager', 'breach_status': 'low'},
            {'email': 'jennifer.martinez@lawfirm.com', 'first_name': 'Jennifer', 'last_name': 'Martinez',
             'company': 'Martinez & Associates Law', 'industry': 'Legal', 'title': 'Managing Partner', 'breach_status': 'medium'},
            {'email': 'david.taylor@retailstore.com', 'first_name': 'David', 'last_name': 'Taylor',
             'company': 'Taylor Retail Group', 'industry': 'Retail', 'title': 'Store Manager', 'breach_status': 'medium'},
            {'email': 'michelle.garcia@consultingfirm.com', 'first_name': 'Michelle', 'last_name': 'Garcia',
             'company': 'Garcia Consulting', 'industry': 'Consulting', 'title': 'Principal Consultant', 'breach_status': 'low'},
        ]
        
        for contact_data in contacts_data:
            domain = contact_data['email'].split('@')[1]
            contact = Contact(
                email=contact_data['email'],
                first_name=contact_data['first_name'],
                last_name=contact_data['last_name'],
                company=contact_data['company'],
                industry=contact_data['industry'],
                title=contact_data['title'],
                domain=domain,
                breach_status=contact_data['breach_status'],
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 90)),
                last_contacted=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                is_active=True
            )
            db.session.add(contact)
            self.contacts.append(contact)
        
        # Flush to get contact IDs
        db.session.flush()
        
        print(f"   * Created {len(contacts_data)} sample contacts")
    
    def create_email_sequences(self):
        """Create realistic email sequences showing contacts at different stages"""
        print("Creating email sequences...")
        
        sequence_count = 0
        email_count = 0
        
        # Create sequences for some contacts in campaigns
        for contact in self.contacts[:6]:  # First 6 contacts
            for campaign_name, campaign in list(self.campaigns.items())[:3]:  # First 3 campaigns
                
                # Skip some combinations to make it realistic
                if random.random() < 0.4:
                    continue
                
                # Determine breach status and template type
                template_type = 'breached' if contact.breach_status == 'high' else 'proactive'
                
                # Create contact campaign status
                status = ContactCampaignStatus(
                    contact_id=contact.id,
                    campaign_id=campaign.id,
                    breach_status='breached' if template_type == 'breached' else 'clean',
                    current_sequence_step=random.randint(0, 4),
                    flawtrack_checked_at=datetime.utcnow() - timedelta(days=random.randint(1, 7)),
                    breach_data={'status': template_type, 'checked': True} if template_type == 'breached' else None,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(5, 30))
                )
                db.session.add(status)
                db.session.flush()
                
                # Create email sequences for this contact
                sequence_config = self.sequence_configs[campaign.sequence_config_ref.name]
                steps = sequence_config.steps.order_by(SequenceStep.step_number).all()
                
                start_date = datetime.utcnow().date() - timedelta(days=random.randint(10, 60))
                
                for step in steps:
                    if step.step_number > status.current_sequence_step:
                        # Future emails
                        scheduled_date = start_date + timedelta(days=step.delay_days)
                        email_status = 'scheduled'
                        sent_at = None
                    else:
                        # Past emails
                        scheduled_date = start_date + timedelta(days=step.delay_days)
                        email_status = 'sent'
                        sent_at = datetime.combine(scheduled_date, datetime.min.time()) + timedelta(
                            hours=random.randint(9, 17), minutes=random.randint(0, 59)
                        )
                        
                        # Create actual email record
                        email = Email(
                            contact_id=contact.id,
                            campaign_id=campaign.id,
                            email_type=f'step_{step.step_number}',
                            subject=f'Security consultation for {contact.company} - Step {step.step_number}',
                            body='Sample email content',
                            status='sent',
                            sent_at=sent_at,
                            delivered_at=sent_at + timedelta(minutes=random.randint(1, 10)),
                            opened_at=sent_at + timedelta(hours=random.randint(1, 48)) if random.random() < 0.6 else None,
                            clicked_at=sent_at + timedelta(hours=random.randint(2, 72)) if random.random() < 0.2 else None
                        )
                        db.session.add(email)
                        db.session.flush()
                        email_count += 1
                    
                    # Create sequence record
                    sequence = EmailSequence(
                        contact_id=contact.id,
                        campaign_id=campaign.id,
                        sequence_step=step.step_number,
                        template_type=template_type,
                        scheduled_date=scheduled_date,
                        sent_at=sent_at,
                        status=email_status,
                        email_id=email.id if email_status == 'sent' else None
                    )
                    db.session.add(sequence)
                    sequence_count += 1
        
        print(f"   * Created {sequence_count} email sequences and {email_count} emails")
    
    def create_sample_settings(self):
        """Create sample application settings"""
        print("Creating application settings...")
        
        settings = [
            ('brevo_api_key', '', 'Brevo API key for email sending'),
            ('sender_email', 'security@salesbreachpro.com', 'Default sender email address'),
            ('sender_name', 'Security Team', 'Default sender name'),
            ('email_signature', 'Best regards,<br>Security Team<br>SalesBreachPro', 'HTML email signature'),
            ('daily_email_limit', '100', 'Maximum emails to send per day'),
            ('flawtrack_api_key', '', 'FlawTrack API key for breach checking')
        ]
        
        for key, value, description in settings:
            Settings.set_setting(key, value, description)
        
        print(f"   * Created {len(settings)} application settings")
    
    def print_summary(self):
        """Print a summary of what was created"""
        print("\n" + "="*60)
        print("DATABASE SEEDING SUMMARY")
        print("="*60)
        print(f"📅 Email Sequence Configurations: {len(self.sequence_configs)}")
        print(f"📝 Email Templates: {EmailTemplate.query.count()}")
        print(f"📈 Demo Campaigns: {len(self.campaigns)}")
        print(f"👥 Sample Contacts: {len(self.contacts)}")
        print(f"📧 Email Sequences: {EmailSequence.query.count()}")
        print(f"📨 Sample Emails: {Email.query.count()}")
        print(f"⚙️ Application Settings: {Settings.query.count()}")
        print("\n🚀 Ready for UI testing - everything should work with real data!")
        print("="*60)


def seed_database():
    """Main function to seed database"""
    seeder = DatabaseSeeder()
    seeder.seed_all()


if __name__ == "__main__":
    # Run seeder standalone
    from app import create_app
    app = create_app()
    with app.app_context():
        seed_database()