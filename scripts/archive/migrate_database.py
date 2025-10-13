#!/usr/bin/env python
"""
Database migration script to add new columns and constraints
Run this once to update your existing database schema
"""
import sqlite3
import os

def migrate_database():
    """Add missing columns and constraints to existing database"""
    
    # Get database path
    db_path = os.path.join('data', 'app.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("Starting database migration...")
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(email_sequences)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add skip_reason column if it doesn't exist
        if 'skip_reason' not in columns:
            print("Adding skip_reason column...")
            cursor.execute("ALTER TABLE email_sequences ADD COLUMN skip_reason VARCHAR(100)")
            print("[OK] skip_reason column added")
        else:
            print("[OK] skip_reason column already exists")
        
        # Add error_message column if it doesn't exist
        if 'error_message' not in columns:
            print("Adding error_message column...")
            cursor.execute("ALTER TABLE email_sequences ADD COLUMN error_message TEXT")
            print("[OK] error_message column added")
        else:
            print("[OK] error_message column already exists")
        
        # Clean up any existing duplicates before adding unique constraint
        print("Cleaning up duplicate EmailSequence records...")
        cursor.execute("""
            DELETE FROM email_sequences 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM email_sequences 
                GROUP BY campaign_id, contact_id, sequence_step
            )
        """)
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            print(f"[OK] Removed {deleted_count} duplicate records")
        else:
            print("[OK] No duplicates found")
        
        # Check if unique constraint already exists
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='email_sequences'")
        table_sql = cursor.fetchone()[0]
        
        if 'unique_campaign_contact_step' not in table_sql:
            print("Adding unique constraint...")
            # SQLite doesn't support adding constraints to existing tables directly
            # We need to recreate the table with the constraint
            
            # Create new table with constraint
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_sequences_new (
                    id INTEGER PRIMARY KEY,
                    contact_id INTEGER NOT NULL REFERENCES contacts(id),
                    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
                    sequence_step INTEGER NOT NULL,
                    template_type VARCHAR(20) NOT NULL,
                    scheduled_date DATE NOT NULL,
                    scheduled_datetime DATETIME,
                    sent_at DATETIME,
                    status VARCHAR(20) DEFAULT 'scheduled',
                    email_id INTEGER REFERENCES emails(id),
                    created_at DATETIME,
                    skip_reason VARCHAR(100),
                    error_message TEXT,
                    UNIQUE(campaign_id, contact_id, sequence_step)
                )
            """)
            
            # Copy data to new table
            cursor.execute("""
                INSERT INTO email_sequences_new 
                SELECT * FROM email_sequences
            """)
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE email_sequences")
            cursor.execute("ALTER TABLE email_sequences_new RENAME TO email_sequences")
            print("[OK] Unique constraint added")
        else:
            print("[OK] Unique constraint already exists")
        
        # Commit changes
        conn.commit()
        print("\n[SUCCESS] Database migration completed successfully!")
        
        # Show current email sequences for verification
        cursor.execute("SELECT COUNT(*) FROM email_sequences")
        count = cursor.fetchone()[0]
        print(f"Total EmailSequence records: {count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def clean_test_data():
    """Optional: Clean all test data to start fresh"""
    response = input("\nDo you want to clean all test email data? (y/n): ").lower()
    if response != 'y':
        print("Skipping data cleanup")
        return
    
    db_path = os.path.join('data', 'app.db')
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("Cleaning test data...")
        cursor.execute("DELETE FROM email_sequences")
        seq_count = cursor.rowcount
        cursor.execute("DELETE FROM emails")
        email_count = cursor.rowcount
        cursor.execute("DELETE FROM contact_campaign_status")
        status_count = cursor.rowcount
        
        conn.commit()
        print(f"[OK] Deleted {seq_count} email sequences")
        print(f"[OK] Deleted {email_count} emails")
        print(f"[OK] Deleted {status_count} contact campaign statuses")
        
        conn.close()
        
    except Exception as e:
        print(f"Error cleaning data: {str(e)}")

if __name__ == "__main__":
    print("=== SalesBreachPro Database Migration ===\n")
    
    if migrate_database():
        clean_test_data()
        print("\n*** Database is ready for testing!")
        print("You can now restart the application and test the email sequences.")
    else:
        print("\n[WARNING] Migration failed. Please check the error above.")