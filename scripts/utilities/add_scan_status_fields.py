#!/usr/bin/env python3
"""
Database migration script to add FlawTrack scanning status fields to contacts table
"""

import os
import sys
from datetime import datetime
from app import create_app
from models.database import db

def migrate_database():
    """Add new scanning status fields to breaches table (domain-level tracking)"""
    
    app = create_app()
    
    with app.app_context():
        try:
            # Check if columns already exist by trying to query them
            try:
                db.session.execute("SELECT scan_status FROM breaches LIMIT 1")
                print("✅ Scanning status columns already exist - skipping migration")
                return
            except Exception:
                # Columns don't exist, need to add them
                pass
            
            print("🔄 Adding scanning status columns to breaches table...")
            
            # Add the new columns to breaches table (domain-level scanning)
            from sqlalchemy import text
            
            alter_commands = [
                "ALTER TABLE breaches ADD COLUMN scan_status VARCHAR(20) DEFAULT 'not_scanned'",
                "ALTER TABLE breaches ADD COLUMN scan_attempts INTEGER DEFAULT 0", 
                "ALTER TABLE breaches ADD COLUMN last_scan_attempt DATETIME",
                "ALTER TABLE breaches ADD COLUMN scan_error TEXT"
            ]
            
            for command in alter_commands:
                try:
                    db.session.execute(text(command))
                    print(f"  ✓ {command}")
                except Exception as e:
                    if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                        print(f"  ⚠️ Column already exists: {command}")
                    else:
                        raise e
            
            db.session.commit()
            
            print("✅ Database migration completed successfully!")
            print("\nNew fields added to breaches table (domain-level scanning):")
            print("  - scan_status: Tracks scanning progress (not_scanned, scanning, completed, failed)")
            print("  - scan_attempts: Number of scan retry attempts for this domain")
            print("  - last_scan_attempt: Timestamp of last scan attempt for this domain")
            print("  - scan_error: Error message if domain scan failed")
            print("\nNote: Scanning is done per domain, so 1000 emails from same domain = 1 scan")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            sys.exit(1)

if __name__ == "__main__":
    migrate_database()