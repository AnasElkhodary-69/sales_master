#!/usr/bin/env python3
"""
Comprehensive Realistic Data Seeder for SalesBreachPro
Creates realistic business data with actual metrics for testing
"""
import random
import uuid
from datetime import datetime, timedelta, date
from app import create_app
from models.database import (
    db, Contact, Campaign, Email, EmailTemplate, 
    ContactCampaignStatus, EmailSequence, Settings,
    EmailSequenceConfig, SequenceStep, Breach
)

class RealisticDataSeeder:
    """Seeds database with realistic business data"""
    
    def __init__(self):
        self.app = create_app()
        self.companies = [
            # Healthcare
            ("Regional Medical Center", "healthcare", "regionalmedical.com"),
            ("City Hospital", "healthcare", "cityhospital.org"),
            ("MediCare Solutions", "healthcare", "medicaresolutions.com"),
            ("Health First Clinic", "healthcare", "healthfirst.net"),
            
            # Financial Services
            ("First National Bank", "financial", "firstnationalbank.com"),
            ("Community Credit Union", "financial", "communitycu.org"),
            ("Investment Partners LLC", "financial", "investmentpartners.com"),
            ("Secure Finance Group", "financial", "securefinance.net"),
            
            # Technology
            ("TechStart Inc", "technology", "techstart.io"),
            ("Digital Solutions Corp", "technology", "digitalsolutions.com"),
            ("CloudTech Systems", "technology", "cloudtech.com"),
            ("DataFlow Technologies", "technology", "dataflow.tech"),
            
            # Legal
            ("Law Offices of Smith & Associates", "legal", "smithlaw.com"),
            ("Corporate Legal Services", "legal", "corporatelegal.net"),
            ("Justice Partners", "legal", "justicepartners.org"),
            
            # Government
            ("City Planning Department", "government", "cityplanning.gov"),
            ("County Health Services", "government", "countyhealth.gov"),
            ("State Education Board", "government", "stateeducation.gov"),
            
            # Manufacturing
            ("Industrial Manufacturing Co", "manufacturing", "industrialmfg.com"),
            ("Precision Parts Ltd", "manufacturing", "precisionparts.net"),
            ("Global Supply Chain", "manufacturing", "globalsupply.com"),
            
            # Education
            ("University Research Center", "education", "universityresearch.edu"),
            ("Academic Excellence Institute", "education", "academicexcellence.edu"),
            ("Student Services Corp", "education", "studentservices.org")
        ]
        
        # Realistic names for contacts
        self.first_names = [
            "John", "Sarah", "Michael", "Jennifer", "David", "Lisa", "Robert", "Michelle",
            "James", "Amanda", "Christopher", "Emily", "Daniel", "Jessica", "Matthew", "Ashley",
            "Anthony", "Stephanie", "Mark", "Rachel", "Steven", "Nicole", "Paul", "Samantha",
            "Andrew", "Elizabeth", "Kenneth", "Katherine", "Brian", "Amy"
        ]
        
        self.last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
            "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
            "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
            "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson"
        ]
        
        # Job titles by industry
        self.titles_by_industry = {
            "healthcare": ["Chief Medical Officer", "IT Director", "Hospital Administrator", "Compliance Officer", "Nursing Director"],
            "financial": ["Chief Financial Officer", "IT Security Manager", "Branch Manager", "Risk Management Director", "Compliance Officer"],
            "technology": ["Chief Technology Officer", "VP Engineering", "Security Architect", "DevOps Manager", "Technical Director"],
            "legal": ["Managing Partner", "IT Administrator", "Office Manager", "Paralegal Supervisor", "Document Manager"],
            "government": ["IT Director", "Department Head", "Program Manager", "Security Officer", "Systems Administrator"],
            "manufacturing": ["Operations Manager", "IT Manager", "Plant Director", "Quality Assurance Manager", "Safety Director"],
            "education": ["IT Director", "Dean of Students", "Research Director", "Administrative Manager", "Technology Coordinator"]
        }

    def seed_all(self):
        """Seed all data types"""
        print("Starting comprehensive realistic data seeding...")
        
        with self.app.app_context():
            # Clear existing data
            self.clear_existing_data()
            
            # Seed in dependency order
            print("1. Creating email sequence configurations...")
            self.create_sequence_configs()
            
            print("2. Creating email templates...")
            self.create_email_templates()
            
            print("3. Creating realistic contacts...")
            contacts = self.create_contacts()
            
            print("4. Creating breach data...")
            self.create_breach_data()
            
            print("5. Creating campaigns with real metrics...")
            campaigns = self.create_campaigns()
            
            print("6. Enrolling contacts in campaigns...")
            self.enroll_contacts_in_campaigns(contacts, campaigns)
            
            print("7. Creating email sequences and tracking...")
            self.create_email_sequences_and_tracking(contacts, campaigns)
            
            print("8. Creating application settings...")
            self.create_settings()
            
            db.session.commit()
            
        print("\n" + "="*50)
        print("REALISTIC DATA SEEDING COMPLETED!")
        print("="*50)
        self.print_summary()

    def clear_existing_data(self):
        """Clear existing data to start fresh"""
        print("Clearing existing data...")
        db.session.query(EmailSequence).delete()
        db.session.query(ContactCampaignStatus).delete()
        db.session.query(Email).delete()
        db.session.query(Contact).delete()
        db.session.query(Campaign).delete()
        db.session.query(EmailTemplate).delete()
        db.session.query(SequenceStep).delete()
        db.session.query(EmailSequenceConfig).delete()
        db.session.query(Breach).delete()
        db.session.commit()

    def create_sequence_configs(self):
        """Create realistic sequence configurations"""
        configs = [
            {
                'name': 'Aggressive Breach Response (5-email)',
                'description': 'Intensive follow-up for recently breached companies',
                'steps': [
                    (0, 0, 'Immediate Breach Alert'),
                    (1, 1, 'Security Assessment Offer'),
                    (2, 3, 'Case Study Share'),
                    (3, 7, 'Free Consultation'),
                    (4, 14, 'Final Value Proposition')
                ]
            },
            {
                'name': 'Proactive Security Outreach (4-email)',
                'description': 'Educational sequence for secure companies',
                'steps': [
                    (0, 0, 'Security Awareness Introduction'),
                    (1, 4, 'Industry Trends Report'),
                    (2, 9, 'Security Checklist'),
                    (3, 18, 'Partnership Proposal')
                ]
            },
            {
                'name': 'Quick Touch Base (3-email)',
                'description': 'Light follow-up sequence',
                'steps': [
                    (0, 0, 'Initial Contact'),
                    (1, 5, 'Value Proposition'),
                    (2, 12, 'Final Follow-up')
                ]
            }
        ]
        
        created_configs = []
        for config_data in configs:
            config = EmailSequenceConfig(
                name=config_data['name'],
                description=config_data['description'],
                is_active=True
            )
            db.session.add(config)
            db.session.flush()  # Get the ID
            
            # Add steps
            for step_data in config_data['steps']:
                step = SequenceStep(
                    sequence_config_id=config.id,
                    step_number=step_data[0],
                    delay_days=step_data[1],
                    step_name=step_data[2],
                    is_active=True
                )
                db.session.add(step)
            
            created_configs.append(config)
        
        return created_configs

    def create_email_templates(self):
        """Create realistic email templates"""
        templates = [
            # Breached company templates
            {
                'name': 'Immediate Breach Response',
                'risk_level': 'breached',
                'sequence_step': 0,
                'breach_template_type': 'breached',
                'subject_line': 'URGENT: {{company}} Data Breach - Immediate Security Assessment Available',
                'email_body': '''Dear {{first_name}},

I noticed that {{company}} recently experienced a cybersecurity incident. As someone who specializes in post-breach recovery and security hardening, I wanted to reach out immediately.

Data breaches can have lasting impacts beyond the initial incident:
- Customer trust erosion
- Regulatory compliance issues  
- Ongoing vulnerability exposure

I've helped companies in {{industry}} sector recover stronger from similar incidents. Would you be open to a brief 15-minute call to discuss immediate steps to strengthen your security posture?

Best regards,
Security Team'''
            },
            {
                'name': 'Security Assessment Follow-up',
                'risk_level': 'breached',
                'sequence_step': 1,
                'breach_template_type': 'breached',
                'subject_line': 'Free Security Assessment for {{company}} - Following Up',
                'email_body': '''Hi {{first_name}},

Following up on my previous email about {{company}}'s recent security incident.

I understand you're likely overwhelmed with breach response activities. That's exactly why I wanted to offer a complimentary security assessment to help identify any remaining vulnerabilities.

This assessment has helped similar {{industry}} organizations:
✓ Close security gaps missed during initial response
✓ Implement monitoring to prevent future incidents  
✓ Meet compliance requirements more effectively

Would next Tuesday or Wednesday work for a brief call?

Best,
Security Team'''
            },
            # Proactive templates for secure companies
            {
                'name': 'Proactive Security Introduction',
                'risk_level': 'proactive',
                'sequence_step': 0,
                'breach_template_type': 'proactive',
                'subject_line': '{{company}} - Staying Ahead of Cyber Threats in {{industry}}',
                'email_body': '''Hello {{first_name}},

I specialize in helping {{industry}} organizations proactively strengthen their cybersecurity before incidents occur.

While {{company}} hasn't experienced any recent breaches (which is great!), the threat landscape is constantly evolving. Companies in your sector face unique risks that generic security solutions often miss.

I'd love to share a recent industry report showing the latest {{industry}} security trends and threats we're seeing.

Would you be interested in a brief overview?

Regards,
Cybersecurity Specialist'''
            },
            {
                'name': 'Industry Security Report',
                'risk_level': 'proactive', 
                'sequence_step': 1,
                'breach_template_type': 'proactive',
                'subject_line': '{{industry}} Security Report - Key Findings for {{company}}',
                'email_body': '''Hi {{first_name}},

Thanks for your interest in the {{industry}} security landscape.

Key findings from our latest research:
• 67% of {{industry}} companies experienced attempted breaches in the last 12 months
• Most successful attacks target specific vulnerabilities common in your sector
• Companies with proactive security programs reduced incident impact by 80%

I've seen these patterns firsthand working with organizations similar to {{company}}.

Would you like to discuss how these trends specifically relate to your current security posture?

Best regards,
Security Research Team'''
            }
        ]
        
        created_templates = []
        for template_data in templates:
            template = EmailTemplate(
                name=template_data['name'],
                template_type='sequence',
                risk_level=template_data['risk_level'],
                sequence_step=template_data['sequence_step'],
                breach_template_type=template_data['breach_template_type'],
                subject_line=template_data['subject_line'],
                email_body=template_data['email_body'],
                active=True,
                created_by='system'
            )
            db.session.add(template)
            created_templates.append(template)
        
        return created_templates

    def create_contacts(self):
        """Create realistic contacts across industries"""
        contacts = []
        
        used_emails = set()
        for company_name, industry, domain in self.companies:
            # Create 2-4 contacts per company
            num_contacts = random.randint(2, 4)
            
            for i in range(num_contacts):
                # Ensure unique email addresses
                attempts = 0
                while attempts < 10:
                    first_name = random.choice(self.first_names)
                    last_name = random.choice(self.last_names) 
                    email = f"{first_name.lower()}.{last_name.lower()}@{domain}"
                    
                    if email not in used_emails:
                        used_emails.add(email)
                        break
                    attempts += 1
                
                if attempts >= 10:  # Skip if we can't find a unique email
                    continue
                title = random.choice(self.titles_by_industry[industry])
                
                # Determine breach status with realistic distribution
                breach_status_weights = [
                    ('breached', 25),  # 25% breached
                    ('not_breached', 60),  # 60% secure  
                    ('unknown', 15)  # 15% unknown
                ]
                breach_status = random.choices(
                    [status for status, weight in breach_status_weights],
                    weights=[weight for status, weight in breach_status_weights]
                )[0]
                
                # Create contact with realistic timing
                created_days_ago = random.randint(30, 180)
                created_at = datetime.utcnow() - timedelta(days=created_days_ago)
                
                contact = Contact(
                    lead_id=str(uuid.uuid4()),
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    company=company_name,
                    domain=domain,
                    title=title,
                    industry=industry,
                    breach_status=breach_status,
                    created_at=created_at,
                    is_active=True,
                    priority='high' if breach_status == 'breached' else 'medium',
                    risk_score=random.uniform(3.0, 9.5) if breach_status == 'breached' else random.uniform(0.5, 4.0)
                )
                
                db.session.add(contact)
                contacts.append(contact)
        
        print(f"Created {len(contacts)} realistic contacts")
        return contacts

    def create_breach_data(self):
        """Create breach records for breached companies"""
        breached_domains = [domain for _, _, domain in self.companies if random.random() < 0.3]
        
        breach_names = [
            "Data Exposure Incident", "Ransomware Attack", "Database Breach", 
            "Email System Compromise", "Network Intrusion", "Insider Threat Incident",
            "Third-Party Vendor Breach", "Phishing Campaign Success", "System Vulnerability Exploit"
        ]
        
        for domain in breached_domains:
            # Create 1-2 breaches per domain
            num_breaches = random.randint(1, 2)
            
            for i in range(num_breaches):
                breach_date = datetime.utcnow() - timedelta(days=random.randint(30, 365))
                
                breach = Breach(
                    domain=domain,
                    breach_name=random.choice(breach_names),
                    breach_year=breach_date.year,
                    breach_date=breach_date.date(),
                    records_affected=random.randint(1000, 500000),
                    severity=random.choice(['medium', 'high', 'high']),  # Weight towards high
                    risk_score=random.uniform(6.0, 9.5),
                    last_updated=datetime.utcnow()
                )
                db.session.add(breach)

    def create_campaigns(self):
        """Create realistic campaigns with various statuses"""
        campaigns_data = [
            {
                'name': 'Q4 Healthcare Security Initiative',
                'template_type': 'healthcare_security',
                'status': 'active',
                'description': 'Proactive security outreach to healthcare organizations',
                'target_risk_levels': ['breached', 'unknown'],
                'auto_enroll': True,
                'auto_enroll_breach_status': 'breached',
                'daily_limit': 25
            },
            {
                'name': 'Financial Services Compliance Campaign',
                'template_type': 'financial_compliance',
                'status': 'active', 
                'description': 'Regulatory compliance and security for financial institutions',
                'target_risk_levels': ['breached', 'not_breached'],
                'auto_enroll': True,
                'auto_enroll_breach_status': 'all',
                'daily_limit': 30
            },
            {
                'name': 'Technology Sector Breach Response',
                'template_type': 'tech_breach_response',
                'status': 'paused',
                'description': 'Immediate response services for recently breached tech companies',
                'target_risk_levels': ['breached'],
                'auto_enroll': False,
                'daily_limit': 15
            },
            {
                'name': 'Government Security Assessment',
                'template_type': 'government_security',
                'status': 'active',
                'description': 'Security assessments for government agencies',
                'target_risk_levels': ['unknown', 'not_breached'],
                'auto_enroll': True,
                'auto_enroll_breach_status': 'unknown',
                'daily_limit': 20
            },
            {
                'name': 'Manufacturing Cybersecurity Audit',
                'template_type': 'manufacturing_security',
                'status': 'completed',
                'description': 'Cybersecurity audits for manufacturing companies',
                'target_risk_levels': ['breached'],
                'auto_enroll': False,
                'daily_limit': 10
            }
        ]
        
        campaigns = []
        for campaign_data in campaigns_data:
            # Set realistic creation and scheduling dates
            created_days_ago = random.randint(45, 120)
            created_at = datetime.utcnow() - timedelta(days=created_days_ago)
            
            campaign = Campaign(
                name=campaign_data['name'],
                template_type=campaign_data['template_type'],
                status=campaign_data['status'],
                description=campaign_data['description'],
                created_at=created_at,
                scheduled_start=created_at + timedelta(days=random.randint(1, 7)),
                active=campaign_data['status'] == 'active',
                daily_limit=campaign_data['daily_limit'],
                auto_enroll=campaign_data['auto_enroll'],
                auto_enroll_breach_status=campaign_data.get('auto_enroll_breach_status', 'all'),
                sender_email='security@salesbreachpro.com',
                sender_name='SalesBreachPro Security Team'
            )
            
            db.session.add(campaign)
            campaigns.append(campaign)
        
        print(f"Created {len(campaigns)} realistic campaigns")
        return campaigns

    def enroll_contacts_in_campaigns(self, contacts, campaigns):
        """Enroll contacts in appropriate campaigns based on industry/breach status"""
        enrollments_created = 0
        
        for contact in contacts:
            # Each contact gets enrolled in 1-3 relevant campaigns
            num_campaigns = random.randint(1, 3)
            selected_campaigns = random.sample(campaigns, min(num_campaigns, len(campaigns)))
            
            for campaign in selected_campaigns:
                # Skip if not a good match
                if not self.should_enroll_contact(contact, campaign):
                    continue
                
                # Create campaign status record
                status = ContactCampaignStatus(
                    contact_id=contact.id,
                    campaign_id=campaign.id,
                    breach_status=contact.breach_status,
                    current_sequence_step=random.randint(0, 3),
                    flawtrack_checked_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(5, 45))
                )
                
                # Some contacts have replied (stop sequence)
                if random.random() < 0.15:  # 15% reply rate
                    status.replied_at = datetime.utcnow() - timedelta(days=random.randint(1, 20))
                
                # Some have completed sequences
                elif random.random() < 0.25:  # 25% completion rate
                    status.sequence_completed_at = datetime.utcnow() - timedelta(days=random.randint(1, 15))
                    status.current_sequence_step = 5
                
                db.session.add(status)
                enrollments_created += 1
        
        print(f"Created {enrollments_created} contact-campaign enrollments")

    def should_enroll_contact(self, contact, campaign):
        """Determine if contact should be enrolled in campaign"""
        # Industry matching
        if 'healthcare' in campaign.name.lower() and contact.industry != 'healthcare':
            return random.random() < 0.2  # 20% chance of cross-industry
        if 'financial' in campaign.name.lower() and contact.industry != 'financial':
            return random.random() < 0.2
        if 'technology' in campaign.name.lower() and contact.industry != 'technology':
            return random.random() < 0.3
        if 'government' in campaign.name.lower() and contact.industry != 'government':
            return random.random() < 0.1
        if 'manufacturing' in campaign.name.lower() and contact.industry != 'manufacturing':
            return random.random() < 0.2
        
        # Breach status matching
        if 'breach response' in campaign.name.lower() and contact.breach_status != 'breached':
            return False
        
        return True

    def create_email_sequences_and_tracking(self, contacts, campaigns):
        """Create realistic email sequences with tracking data"""
        emails_created = 0
        sequences_created = 0
        
        # Get enrolled contact-campaign pairs
        enrolled_pairs = db.session.query(ContactCampaignStatus).all()
        
        for enrollment in enrolled_pairs:
            contact = Contact.query.get(enrollment.contact_id)
            campaign = Campaign.query.get(enrollment.campaign_id)
            
            if not contact or not campaign:
                continue
            
            # Create email sequence records
            max_step = enrollment.current_sequence_step
            
            for step in range(max_step + 1):
                # Schedule date based on sequence timing
                days_offset = [0, 2, 5, 12, 26][min(step, 4)]
                scheduled_date = enrollment.created_at.date() + timedelta(days=days_offset)
                
                sequence = EmailSequence(
                    contact_id=contact.id,
                    campaign_id=campaign.id,
                    sequence_step=step,
                    template_type='breached' if contact.breach_status == 'breached' else 'proactive',
                    scheduled_date=scheduled_date,
                    status='sent' if step < max_step else 'scheduled',
                    created_at=enrollment.created_at
                )
                
                if sequence.status == 'sent':
                    sequence.sent_at = datetime.combine(scheduled_date, datetime.min.time()) + timedelta(hours=random.randint(9, 17))
                
                db.session.add(sequence)
                sequences_created += 1
                
                # Create email tracking record if sent
                if sequence.status == 'sent':
                    email = Email(
                        contact_id=contact.id,
                        campaign_id=campaign.id,
                        email_type=f'step_{step}',
                        subject=f'Security Discussion - Step {step + 1}',
                        body='Email content would be here...',
                        status=random.choices(
                            ['sent', 'delivered', 'opened', 'clicked'],
                            weights=[10, 30, 40, 20]
                        )[0],
                        sent_at=sequence.sent_at,
                        brevo_message_id=f'msg_{random.randint(100000, 999999)}'
                    )
                    
                    # Add realistic engagement timestamps
                    if email.status in ['delivered', 'opened', 'clicked']:
                        email.delivered_at = email.sent_at + timedelta(minutes=random.randint(1, 30))
                    
                    if email.status in ['opened', 'clicked']:
                        email.opened_at = email.delivered_at + timedelta(hours=random.randint(1, 48))
                        email.open_count = random.randint(1, 5)
                        
                        # Update contact engagement
                        contact.total_opens = (contact.total_opens or 0) + email.open_count
                        contact.last_opened_at = email.opened_at
                    
                    if email.status == 'clicked':
                        email.clicked_at = email.opened_at + timedelta(minutes=random.randint(5, 120))
                        email.click_count = random.randint(1, 3)
                        
                        # Update contact engagement
                        contact.total_clicks = (contact.total_clicks or 0) + email.click_count
                        contact.last_clicked_at = email.clicked_at
                    
                    # Some emails get replies
                    if random.random() < 0.12:  # 12% reply rate
                        email.replied_at = email.opened_at + timedelta(hours=random.randint(2, 72))
                        email.status = 'replied'
                        contact.has_responded = True
                        contact.responded_at = email.replied_at
                    
                    # Update contact last contacted
                    contact.last_contacted_at = email.sent_at
                    
                    db.session.add(email)
                    sequence.email_id = email.id
                    emails_created += 1
        
        print(f"Created {emails_created} emails with realistic tracking data")
        print(f"Created {sequences_created} sequence records")

    def create_settings(self):
        """Create application settings"""
        settings = [
            ('brevo_api_key', 'demo-brevo-key-here', 'Brevo API key for email sending'),
            ('flawtrack_api_key', 'demo-flawtrack-key-here', 'FlawTrack API key for breach data'),
            ('daily_email_limit', '100', 'Maximum emails to send per day'),
            ('auto_enrollment_enabled', 'true', 'Enable automatic contact enrollment'),
            ('webhook_secret', 'webhook-secret-key', 'Secret key for webhook verification')
        ]
        
        for key, value, description in settings:
            setting = Settings(
                key=key,
                value=value,
                description=description
            )
            db.session.add(setting)

    def print_summary(self):
        """Print summary of created data"""
        with self.app.app_context():
            contacts_count = Contact.query.count()
            campaigns_count = Campaign.query.count()
            emails_count = Email.query.count()
            enrollments_count = ContactCampaignStatus.query.count()
            
            # Campaign statistics
            active_campaigns = Campaign.query.filter_by(status='active').count()
            
            # Contact statistics by breach status
            breached_contacts = Contact.query.filter_by(breach_status='breached').count()
            secure_contacts = Contact.query.filter_by(breach_status='not_breached').count()
            unknown_contacts = Contact.query.filter_by(breach_status='unknown').count()
            
            # Email statistics
            sent_emails = Email.query.filter(Email.sent_at.isnot(None)).count()
            opened_emails = Email.query.filter(Email.opened_at.isnot(None)).count()
            clicked_emails = Email.query.filter(Email.clicked_at.isnot(None)).count()
            replied_emails = Email.query.filter(Email.replied_at.isnot(None)).count()
            
            print(f"Contacts Created: {contacts_count}")
            print(f"  - Breached: {breached_contacts}")
            print(f"  - Secure: {secure_contacts}")
            print(f"  - Unknown: {unknown_contacts}")
            print(f"\nCampaigns Created: {campaigns_count}")
            print(f"  - Active: {active_campaigns}")
            print(f"\nEmails Created: {emails_count}")
            print(f"  - Sent: {sent_emails}")
            print(f"  - Opened: {opened_emails}")
            print(f"  - Clicked: {clicked_emails}")
            print(f"  - Replied: {replied_emails}")
            print(f"\nCampaign Enrollments: {enrollments_count}")
            
            if sent_emails > 0:
                open_rate = (opened_emails / sent_emails) * 100
                click_rate = (clicked_emails / sent_emails) * 100
                reply_rate = (replied_emails / sent_emails) * 100
                
                print(f"\nEngagement Rates:")
                print(f"  - Open Rate: {open_rate:.1f}%")
                print(f"  - Click Rate: {click_rate:.1f}%")
                print(f"  - Reply Rate: {reply_rate:.1f}%")

if __name__ == '__main__':
    seeder = RealisticDataSeeder()
    seeder.seed_all()
    print("\nRealistic data seeding completed successfully!")
    print("Visit http://localhost:5000 to see your data in action!")