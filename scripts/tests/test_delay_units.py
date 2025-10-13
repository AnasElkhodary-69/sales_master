#!/usr/bin/env python
"""Test the new flexible delay units system"""

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
from models.database import db, EmailTemplate, Contact, Campaign
from services.email_sequence_service import EmailSequenceService

def test_delay_units():
    """Test different delay units"""
    
    app = create_app()
    
    with app.app_context():
        print("=== TESTING FLEXIBLE DELAY UNITS ===")
        
        # Test the conversion functions
        email_service = EmailSequenceService()
        
        # Test various delay units
        test_cases = [
            (5, 'minutes'),
            (2, 'hours'),  
            (1, 'days'),
            (30, 'min'),
            (24, 'hr'),
            (7, 'day')
        ]
        
        print("Testing delay conversion:")
        for amount, unit in test_cases:
            delay = email_service._calculate_delay_timedelta(amount, unit)
            total_seconds = delay.total_seconds()
            print(f"  {amount} {unit} = {delay} ({total_seconds} seconds)")
        
        # Update an existing email template to use new delay system
        templates = EmailTemplate.query.limit(2).all()
        if templates:
            print(f"\nFound {len(templates)} templates to update:")
            
            # Update first template to use minutes
            template1 = templates[0]
            template1.delay_amount = 15
            template1.delay_unit = 'minutes'
            print(f"  Updated {template1.name}: {template1.delay_amount} {template1.delay_unit}")
            
            if len(templates) > 1:
                # Update second template to use hours
                template2 = templates[1]
                template2.delay_amount = 2  
                template2.delay_unit = 'hours'
                print(f"  Updated {template2.name}: {template2.delay_amount} {template2.delay_unit}")
            
            db.session.commit()
            
            # Test the _get_effective_delay method
            print("\nTesting effective delay calculation:")
            for template in templates:
                delay = email_service._get_effective_delay(template)
                delay_info = email_service._get_delay_info(template)
                print(f"  {template.name}: {delay} (from {delay_info['amount']} {delay_info['unit']})")
        
        else:
            print("No templates found to test with")
        
        print("\n=== TEST COMPLETE ===")

if __name__ == "__main__":
    test_delay_units()