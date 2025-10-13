#!/usr/bin/env python
"""Check what tables exist in the database"""

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

def check_database_tables():
    """Check what tables exist"""
    
    app = create_app()
    
    with app.app_context():
        print("=== DATABASE TABLES ===")
        
        with db.engine.connect() as conn:
            # List all tables
            result = conn.execute(db.text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            print(f"All tables: {tables}")
            
            # Check email_templates structure
            if 'email_templates' in tables:
                print("\n=== EMAIL_TEMPLATES TABLE STRUCTURE ===")
                result = conn.execute(db.text("PRAGMA table_info(email_templates)"))
                for row in result:
                    print(f"  {row[1]} ({row[2]}) - {row}")
                    
                # Check if new columns exist
                result = conn.execute(db.text("SELECT delay_days, delay_amount, delay_unit FROM email_templates LIMIT 3"))
                templates = list(result)
                print(f"Sample data: {templates}")

if __name__ == "__main__":
    check_database_tables()