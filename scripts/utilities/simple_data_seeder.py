#!/usr/bin/env python3
"""
Simple Data Seeder - Creates realistic business data for testing
Works with current database schema
"""
import random
import uuid
from datetime import datetime, timedelta
from app import create_app
from models.database import db, Contact, Campaign, Email, ContactCampaignStatus

class SimpleDataSeeder:
    """Creates realistic business data that works with current schema"""
    
    def __init__(self):
        self.app = create_app()

    def seed_all(self):
        """Seed realistic data"""
        print("Creating realistic business data...")
        
        with self.app.app_context():
            # Clear existing data
            print("Clearing existing data...")
            db.session.query(Email).delete()
            db.session.query(ContactCampaignStatus).delete()
            db.session.query(Contact).delete()
            db.session.query(Campaign).delete()
            db.session.commit()
            
            # Create contacts
            contacts = self.create_contacts()
            
            # Create campaigns
            campaigns = self.create_campaigns()
            
            # Create enrollments and emails
            self.create_enrollments_and_emails(contacts, campaigns)
            
            db.session.commit()
            
        print("\n" + "="*50)
        print("REALISTIC DATA CREATED!")
        print("="*50)
        self.print_summary()

    def create_contacts(self):
        """Create realistic contacts"""
        companies = [
            ("Regional Medical Center", "healthcare", "regionalmedical.com", "breached"),
            ("City Hospital", "healthcare", "cityhospital.org", "not_breached"),
            ("First National Bank", "financial", "firstnationalbank.com", "breached"),
            ("Community Credit Union", "financial", "communitycu.org", "not_breached"),
            ("TechStart Inc", "technology", "techstart.io", "breached"),
            ("Digital Solutions Corp", "technology", "digitalsolutions.com", "not_breached"),
            ("Law Offices Smith & Associates", "legal", "smithlaw.com", "unknown"),
            ("Corporate Legal Services", "legal", "corporatelegal.net", "breached"),
            ("City Planning Department", "government", "cityplanning.gov", "not_breached"),
            ("State Education Board", "government", "stateeducation.gov", "unknown"),
            ("Industrial Manufacturing Co", "manufacturing", "industrialmfg.com", "breached"),
            ("Precision Parts Ltd", "manufacturing", "precisionparts.net", "not_breached"),
            ("University Research Center", "education", "universityresearch.edu", "unknown"),
            ("Global Supply Chain", "manufacturing", "globalsupply.com", "breached"),
            ("Academic Excellence Institute", "education", "academicexcellence.edu", "not_breached")
        ]
        
        names = [
            ("John", "Smith", "CEO"), ("Sarah", "Johnson", "IT Director"), 
            ("Michael", "Williams", "CISO"), ("Jennifer", "Brown", "CTO"),
            ("David", "Jones", "VP Operations"), ("Lisa", "Garcia", "Security Manager"),
            ("Robert", "Miller", "IT Manager"), ("Michelle", "Davis", "Compliance Officer"),
            ("James", "Rodriguez", "System Admin"), ("Amanda", "Martinez", "Risk Manager"),
            ("Christopher", "Hernandez", "Network Admin"), ("Emily", "Lopez", "Data Manager"),
            ("Daniel", "Gonzalez", "Operations Manager"), ("Jessica", "Wilson", "IT Analyst"),
            ("Matthew", "Anderson", "Security Analyst"), ("Ashley", "Thomas", "Admin Manager")
        ]
        
        contacts = []
        contact_id = 1
        
        for company_name, industry, domain, breach_status in companies:
            # Create 2-3 contacts per company
            num_contacts = random.randint(2, 3)
            used_names = []
            
            for i in range(num_contacts):
                # Get unique name for this company
                available_names = [n for n in names if n not in used_names]
                if not available_names:
                    break
                    
                first_name, last_name, title = random.choice(available_names)
                used_names.append((first_name, last_name, title))
                
                email = f"{first_name.lower()}.{last_name.lower()}{contact_id}@{domain}"
                contact_id += 1
                
                created_days_ago = random.randint(10, 90)
                
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
                    created_at=datetime.utcnow() - timedelta(days=created_days_ago),
                    is_active=True,
                    priority='high' if breach_status == 'breached' else 'medium',
                    risk_score=random.uniform(6.0, 9.0) if breach_status == 'breached' else random.uniform(1.0, 5.0)
                )
                
                db.session.add(contact)
                contacts.append(contact)
        
        db.session.flush()
        print(f"Created {len(contacts)} contacts")
        return contacts

    def create_campaigns(self):
        """Create realistic campaigns"""
        campaigns_data = [
            ("Healthcare Security Initiative", "healthcare_security", "active", True, "breached"),
            ("Financial Compliance Campaign", "financial_compliance", "active", True, "all"),
            ("Technology Breach Response", "tech_breach_response", "active", False, "breached"),
            ("Government Security Assessment", "government_security", "paused", True, "unknown"),
            ("Manufacturing Security Audit", "manufacturing_security", "completed", False, "breached")
        ]
        
        campaigns = []
        for name, template_type, status, auto_enroll, breach_filter in campaigns_data:
            created_days_ago = random.randint(30, 90)
            
            campaign = Campaign(
                name=name,
                template_type=template_type,
                status=status,
                description=f"Automated security outreach for {template_type}",
                created_at=datetime.utcnow() - timedelta(days=created_days_ago),
                scheduled_start=datetime.utcnow() - timedelta(days=created_days_ago - 5),
                active=status == 'active',
                daily_limit=random.randint(15, 30),
                auto_enroll=auto_enroll,
                auto_enroll_breach_status=breach_filter,
                sender_email='security@salesbreachpro.com',
                sender_name='Security Team'
            )
            
            db.session.add(campaign)
            campaigns.append(campaign)
        
        db.session.flush()
        print(f"Created {len(campaigns)} campaigns")
        return campaigns

    def create_enrollments_and_emails(self, contacts, campaigns):
        """Create contact enrollments and email tracking data"""
        enrollments_created = 0
        emails_created = 0
        
        for contact in contacts:
            # Each contact enrolled in 1-2 relevant campaigns
            num_campaigns = random.randint(1, 2)
            selected_campaigns = random.sample(campaigns, min(num_campaigns, len(campaigns)))
            
            for campaign in selected_campaigns:
                # Skip if not a good match
                if not self.should_enroll(contact, campaign):
                    continue
                
                # Create enrollment status
                enrollment_days_ago = random.randint(5, 30)
                current_step = random.randint(0, 4)
                
                status = ContactCampaignStatus(
                    contact_id=contact.id,
                    campaign_id=campaign.id,
                    breach_status=contact.breach_status,
                    current_sequence_step=current_step,
                    created_at=datetime.utcnow() - timedelta(days=enrollment_days_ago)
                )
                
                # Some contacts replied (15% reply rate)
                if random.random() < 0.15:
                    status.replied_at = datetime.utcnow() - timedelta(days=random.randint(1, 15))
                
                # Some completed sequences (20% completion rate)
                elif random.random() < 0.20:
                    status.sequence_completed_at = datetime.utcnow() - timedelta(days=random.randint(1, 10))
                    status.current_sequence_step = 5
                
                db.session.add(status)
                enrollments_created += 1
                
                # Create emails for each sequence step up to current step
                for step in range(current_step + 1):
                    email_sent_days_ago = enrollment_days_ago - (step * 3)  # 3 days between emails
                    if email_sent_days_ago < 0:
                        continue
                    
                    sent_at = datetime.utcnow() - timedelta(days=email_sent_days_ago)
                    
                    # Determine email status with realistic distribution
                    status_weights = [
                        ('sent', 10),
                        ('delivered', 25),
                        ('opened', 45),
                        ('clicked', 15),
                        ('replied', 5)
                    ]
                    email_status = random.choices(
                        [s for s, w in status_weights],
                        weights=[w for s, w in status_weights]
                    )[0]
                    
                    email = Email(
                        contact_id=contact.id,
                        campaign_id=campaign.id,
                        email_type=f'sequence_step_{step}',
                        subject=f'Security Discussion - Step {step + 1}',
                        body='Professional security outreach email content...',
                        status=email_status,
                        sent_at=sent_at,
                        brevo_message_id=f'brevo_{random.randint(100000, 999999)}'
                    )
                    
                    # Add realistic engagement timestamps
                    if email_status in ['delivered', 'opened', 'clicked', 'replied']:
                        email.delivered_at = sent_at + timedelta(minutes=random.randint(5, 60))
                    
                    if email_status in ['opened', 'clicked', 'replied']:
                        email.opened_at = email.delivered_at + timedelta(hours=random.randint(1, 24))
                        email.open_count = random.randint(1, 4)
                        
                        # Update contact engagement
                        contact.total_opens = (contact.total_opens or 0) + email.open_count
                        contact.last_opened_at = email.opened_at
                    
                    if email_status in ['clicked', 'replied']:
                        email.clicked_at = email.opened_at + timedelta(minutes=random.randint(10, 180))
                        email.click_count = random.randint(1, 2)
                        
                        contact.total_clicks = (contact.total_clicks or 0) + email.click_count
                        contact.last_clicked_at = email.clicked_at
                    
                    if email_status == 'replied':
                        email.replied_at = email.clicked_at + timedelta(hours=random.randint(2, 48))
                        contact.has_responded = True
                        contact.responded_at = email.replied_at
                    
                    # Update contact last contacted
                    contact.last_contacted_at = sent_at
                    
                    db.session.add(email)
                    emails_created += 1
        
        print(f"Created {enrollments_created} enrollments")
        print(f"Created {emails_created} emails with tracking")

    def should_enroll(self, contact, campaign):
        """Check if contact should be enrolled in campaign"""
        # Industry matching with some cross-pollination
        if 'healthcare' in campaign.name.lower() and contact.industry != 'healthcare':
            return random.random() < 0.3
        if 'financial' in campaign.name.lower() and contact.industry != 'financial':
            return random.random() < 0.3
        if 'technology' in campaign.name.lower() and contact.industry != 'technology':
            return random.random() < 0.4
        if 'government' in campaign.name.lower() and contact.industry != 'government':
            return random.random() < 0.2
        if 'manufacturing' in campaign.name.lower() and contact.industry != 'manufacturing':
            return random.random() < 0.3
        
        # Breach status filtering
        if campaign.auto_enroll_breach_status != 'all':
            if campaign.auto_enroll_breach_status == 'breached' and contact.breach_status != 'breached':
                return False
            if campaign.auto_enroll_breach_status == 'unknown' and contact.breach_status != 'unknown':
                return False
        
        return True

    def print_summary(self):
        """Print summary of created data"""
        with self.app.app_context():
            contacts_count = Contact.query.count()
            campaigns_count = Campaign.query.count()
            emails_count = Email.query.count()
            enrollments_count = ContactCampaignStatus.query.count()
            
            # Contact stats by breach status
            breached = Contact.query.filter_by(breach_status='breached').count()
            secure = Contact.query.filter_by(breach_status='not_breached').count()
            unknown = Contact.query.filter_by(breach_status='unknown').count()
            
            # Campaign stats
            active_campaigns = Campaign.query.filter_by(status='active').count()
            
            # Email stats
            sent_emails = Email.query.filter(Email.sent_at.isnot(None)).count()
            opened_emails = Email.query.filter(Email.opened_at.isnot(None)).count()
            clicked_emails = Email.query.filter(Email.clicked_at.isnot(None)).count()
            replied_emails = Email.query.filter(Email.replied_at.isnot(None)).count()
            
            print(f"\nCONTACTS: {contacts_count} total")
            print(f"  • {breached} Breached")
            print(f"  • {secure} Secure") 
            print(f"  • {unknown} Unknown")
            
            print(f"\nCAMPAIGNS: {campaigns_count} total")
            print(f"  • {active_campaigns} Active")
            
            print(f"\nEMAILS: {emails_count} total")
            print(f"  • {sent_emails} Sent")
            print(f"  • {opened_emails} Opened")
            print(f"  • {clicked_emails} Clicked")
            print(f"  • {replied_emails} Replied")
            
            print(f"\nENROLLMENTS: {enrollments_count} contact-campaign pairs")
            
            if sent_emails > 0:
                open_rate = (opened_emails / sent_emails) * 100
                click_rate = (clicked_emails / sent_emails) * 100
                reply_rate = (replied_emails / sent_emails) * 100
                
                print(f"\nPERFORMANCE RATES:")
                print(f"  • Open Rate: {open_rate:.1f}%")
                print(f"  • Click Rate: {click_rate:.1f}%") 
                print(f"  • Reply Rate: {reply_rate:.1f}%")

if __name__ == '__main__':
    seeder = SimpleDataSeeder()
    seeder.seed_all()
    print("\n✅ Realistic data created successfully!")
    print("🚀 Visit http://localhost:5000 to see your campaigns with real data!")