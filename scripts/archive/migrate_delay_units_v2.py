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
            with db.engine.connect() as conn:
                try:
                    conn.execute(db.text("ALTER TABLE email_templates ADD COLUMN delay_amount INTEGER DEFAULT 0"))
                    print("  - Added delay_amount column to email_templates")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        print("  - delay_amount column already exists in email_templates")
                    else:
                        raise e
                
                try:
                    conn.execute(db.text("ALTER TABLE email_templates ADD COLUMN delay_unit VARCHAR(10) DEFAULT 'days'"))
                    print("  - Added delay_unit column to email_templates")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        print("  - delay_unit column already exists in email_templates")
                    else:
                        raise e
                
                # Add columns to email_sequence_steps table  
                print("Adding columns to email_sequence_steps table...")
                try:
                    conn.execute(db.text("ALTER TABLE email_sequence_steps ADD COLUMN delay_amount INTEGER DEFAULT 0"))
                    print("  - Added delay_amount column to email_sequence_steps")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        print("  - delay_amount column already exists in email_sequence_steps")
                    else:
                        raise e
                
                try:
                    conn.execute(db.text("ALTER TABLE email_sequence_steps ADD COLUMN delay_unit VARCHAR(10) DEFAULT 'days'"))
                    print("  - Added delay_unit column to email_sequence_steps")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        print("  - delay_unit column already exists in email_sequence_steps")
                    else:
                        raise e
                
                print("Migrating existing delay_days values...")
                
                # Migrate existing EmailTemplate delay_days to new format
                conn.execute(db.text("""
                    UPDATE email_templates 
                    SET delay_amount = delay_days, delay_unit = 'days'
                    WHERE delay_days IS NOT NULL AND (delay_amount IS NULL OR delay_amount = 0)
                """))
                print("  - Migrated email_templates delay_days values")
                
                # Migrate existing EmailSequenceStep delay_days to new format  
                conn.execute(db.text("""
                    UPDATE email_sequence_steps 
                    SET delay_amount = delay_days, delay_unit = 'days'
                    WHERE delay_days IS NOT NULL AND (delay_amount IS NULL OR delay_amount = 0)
                """))
                print("  - Migrated email_sequence_steps delay_days values")
                
                conn.commit()
            
            print("Migration completed successfully!")
            
            # Verify the changes
            print("\n=== VERIFICATION ===")
            
            with db.engine.connect() as conn:
                result = conn.execute(db.text("PRAGMA table_info(email_templates)"))
                template_columns = [row[1] for row in result if 'delay' in row[1]]
                print(f"EmailTemplate delay columns: {template_columns}")
                
                result = conn.execute(db.text("PRAGMA table_info(email_sequence_steps)"))
                step_columns = [row[1] for row in result if 'delay' in row[1]]
                print(f"EmailSequenceStep delay columns: {step_columns}")
                
                # Show some sample data if templates exist
                result = conn.execute(db.text("SELECT COUNT(*) FROM email_templates"))
                template_count = result.scalar()
                if template_count > 0:
                    result = conn.execute(db.text("SELECT id, delay_days, delay_amount, delay_unit FROM email_templates LIMIT 3"))
                    templates = list(result)
                    print(f"Sample EmailTemplate data: {templates}")
                else:
                    print("No email templates found in database")
            
        except Exception as e:
            print(f"Migration failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
        return True

if __name__ == "__main__":
    success = migrate_delay_units()
    sys.exit(0 if success else 1)