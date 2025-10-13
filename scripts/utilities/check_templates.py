#!/usr/bin/env python
"""Check what email templates exist in the database"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
basedir = os.path.abspath(os.path.dirname(__file__))
env_file = os.path.join(basedir, 'env')
if os.path.exists(env_file):
    load_dotenv(env_file)

# Add project directory to path
sys.path.insert(0, basedir)

from app import create_app
from models.database import db, EmailTemplate, Campaign

def check_templates():
    """Check what email templates exist"""
    
    app = create_app()
    
    with app.app_context():
        # Get all email templates
        templates = EmailTemplate.query.all()
        print(f"Found {len(templates)} email templates:")
        
        for template in templates:
            print(f"  - ID {template.id}: {template.name}")
            print(f"    Type: {template.breach_template_type}")
            print(f"    Risk Level: {template.risk_level}")
            print(f"    Sequence Step: {template.sequence_step}")
            print(f"    Active: {template.active}")
            print(f"    Subject: {template.subject_line}")
            print(f"    Body preview: {template.email_body[:100]}...")
            print()
        
        # Get all campaigns and their templates
        campaigns = Campaign.query.all()
        print(f"Found {len(campaigns)} campaigns:")
        
        for campaign in campaigns:
            print(f"  - ID {campaign.id}: {campaign.name}")
            print(f"    Status: {campaign.status}")
            print(f"    Template ID: {campaign.template_id}")
            if campaign.template_id:
                template = EmailTemplate.query.get(campaign.template_id)
                if template:
                    print(f"    Template: {template.name} ({template.breach_template_type})")
                else:
                    print("    Template: NOT FOUND")
            print()

if __name__ == "__main__":
    check_templates()