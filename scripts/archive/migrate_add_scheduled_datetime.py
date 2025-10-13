#!/usr/bin/env python
"""Migration to add scheduled_datetime field to EmailSequence table for flexible delay support"""

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
from sqlalchemy import text

def migrate_add_scheduled_datetime():
    """Add scheduled_datetime field to EmailSequence table"""
    
    app = create_app()
    
    with app.app_context():
        print("=== ADDING SCHEDULED_DATETIME TO EMAIL_SEQUENCES TABLE ===")
        
        try:
            # Check if the column already exists (SQLite compatible)
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(email_sequences)"))
                columns = [row[1] for row in result.fetchall()]
                
                if 'scheduled_datetime' in columns:
                    print("scheduled_datetime column already exists!")
                    return
                
                print("Adding scheduled_datetime column...")
                
                # Add the new column
                conn.execute(text("""
                    ALTER TABLE email_sequences 
                    ADD COLUMN scheduled_datetime DATETIME
                """))
                
                # Populate scheduled_datetime from existing scheduled_date
                # Set time to 00:00:00 for existing records
                conn.execute(text("""
                    UPDATE email_sequences 
                    SET scheduled_datetime = DATETIME(scheduled_date || ' 00:00:00')
                    WHERE scheduled_datetime IS NULL
                """))
                
                conn.commit()
                
                print("[OK] scheduled_datetime column added successfully")
                print("[OK] Existing records migrated (set to 00:00:00 of scheduled_date)")
                
        except Exception as e:
            print(f"Error during migration: {str(e)}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    migrate_add_scheduled_datetime()