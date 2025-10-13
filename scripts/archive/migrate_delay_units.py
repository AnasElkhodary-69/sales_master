#!/usr/bin/env python
"""Database migration to add flexible delay units (minutes, hours, days)"""

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
from models.database import db

def migrate_delay_units():
    """Add new columns for flexible delay units"""
    
    app = create_app()
    
    with app.app_context():
        print("=== ADDING DELAY UNIT COLUMNS ===")
        
        try:
            # Add columns to EmailTemplate table
            print("Adding columns to email_templates table...")
            db.engine.execute("""
                ALTER TABLE email_templates 
                ADD COLUMN delay_amount INTEGER DEFAULT 0
            """)
            
            db.engine.execute("""
                ALTER TABLE email_templates 
                ADD COLUMN delay_unit VARCHAR(10) DEFAULT 'days'
            """)
            
            # Add columns to email_sequence_steps table  
            print("Adding columns to email_sequence_steps table...")
            db.engine.execute("""
                ALTER TABLE email_sequence_steps 
                ADD COLUMN delay_amount INTEGER DEFAULT 0
            """)
            
            db.engine.execute("""
                ALTER TABLE email_sequence_steps 
                ADD COLUMN delay_unit VARCHAR(10) DEFAULT 'days'
            """)
            
            print("Migrating existing delay_days values...")
            
            # Migrate existing EmailTemplate delay_days to new format
            db.engine.execute("""
                UPDATE email_templates 
                SET delay_amount = delay_days, delay_unit = 'days'
                WHERE delay_days IS NOT NULL
            """)
            
            # Migrate existing EmailSequenceStep delay_days to new format
            db.engine.execute("""
                UPDATE email_sequence_steps 
                SET delay_amount = delay_days, delay_unit = 'days'
                WHERE delay_days IS NOT NULL
            """)
            
            print("✅ Migration completed successfully!")
            
            # Verify the changes
            print("\n=== VERIFICATION ===")
            
            result = db.engine.execute("SELECT name FROM PRAGMA_TABLE_INFO('email_templates') WHERE name LIKE 'delay_%'")
            template_columns = [row[0] for row in result]
            print(f"EmailTemplate delay columns: {template_columns}")
            
            result = db.engine.execute("SELECT name FROM PRAGMA_TABLE_INFO('email_sequence_steps') WHERE name LIKE 'delay_%'")  
            step_columns = [row[0] for row in result]
            print(f"EmailSequenceStep delay columns: {step_columns}")
            
            # Show some sample data
            result = db.engine.execute("SELECT id, delay_days, delay_amount, delay_unit FROM email_templates LIMIT 3")
            templates = list(result)
            print(f"Sample EmailTemplate data: {templates}")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            return False
            
        return True

if __name__ == "__main__":
    success = migrate_delay_units()
    sys.exit(0 if success else 1)