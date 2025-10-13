#!/usr/bin/env python3
"""
Migration script to add WebhookEvent table to existing database
"""
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app import create_app
from models.database import db, WebhookEvent

def migrate_add_webhook_events():
    """Add WebhookEvent table to database"""
    try:
        app = create_app()
        
        with app.app_context():
            # Check if table already exists
            try:
                from sqlalchemy import text
                result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='webhook_events'"))
                if result.fetchone():
                    print("+ webhook_events table already exists")
                    return True
            except Exception as e:
                print(f"Error checking table existence: {e}")
            
            # Create the webhook_events table
            try:
                db.create_all()
                print("+ Successfully created webhook_events table")
                
                # Verify the table was created
                result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='webhook_events'"))
                if result.fetchone():
                    print("+ webhook_events table verified")
                    
                    # Show table structure
                    result = db.session.execute(text("PRAGMA table_info(webhook_events)"))
                    columns = result.fetchall()
                    print(f"+ Table has {len(columns)} columns:")
                    for col in columns:
                        print(f"  - {col[1]} ({col[2]})")
                    
                    return True
                else:
                    print("- Failed to verify webhook_events table creation")
                    return False
                    
            except Exception as e:
                print(f"- Error creating webhook_events table: {e}")
                return False
                
    except Exception as e:
        print(f"- Migration failed: {e}")
        return False

if __name__ == '__main__':
    print("Adding WebhookEvent table to database...")
    print("=" * 50)
    
    success = migrate_add_webhook_events()
    
    if success:
        print("=" * 50)
        print("+ Migration completed successfully!")
        print("The webhook_events table has been added to your database.")
        print("You can now collect detailed webhook analytics from Brevo.")
        sys.exit(0)
    else:
        print("=" * 50)
        print("- Migration failed!")
        print("Please check the error messages above and try again.")
        sys.exit(1)