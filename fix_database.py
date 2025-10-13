#!/usr/bin/env python3
"""
Database migration script to add the missing variant_id column to emails table
"""
import os
import sqlite3
import sys

def main():
    # Path to the database
    db_path = 'data/app.db'

    if not os.path.exists(db_path):
        print(f"Error: Database file {db_path} not found")
        sys.exit(1)

    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if variant_id column already exists
        cursor.execute("PRAGMA table_info(emails)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Current emails table columns: {columns}")

        if 'variant_id' in columns:
            print("variant_id column already exists in emails table")
        else:
            print("Adding variant_id column to emails table...")

            # Add the variant_id column
            cursor.execute("ALTER TABLE emails ADD COLUMN variant_id INTEGER")

            print("Successfully added variant_id column to emails table")

        # Check if campaign_variants table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='campaign_variants'")
        if cursor.fetchone():
            print("campaign_variants table already exists")
        else:
            print("Creating campaign_variants table...")

            # Create the campaign_variants table
            cursor.execute('''
                CREATE TABLE campaign_variants (
                    id INTEGER PRIMARY KEY,
                    campaign_id INTEGER NOT NULL,
                    variant_name VARCHAR(50) NOT NULL,
                    subject_line VARCHAR(500) NOT NULL,
                    email_body_html TEXT NOT NULL,
                    sender_name VARCHAR(255),
                    sender_email VARCHAR(255),
                    is_default BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    emails_sent INTEGER DEFAULT 0,
                    emails_delivered INTEGER DEFAULT 0,
                    emails_opened INTEGER DEFAULT 0,
                    emails_clicked INTEGER DEFAULT 0,
                    emails_replied INTEGER DEFAULT 0,
                    emails_bounced INTEGER DEFAULT 0,
                    emails_unsubscribed INTEGER DEFAULT 0,
                    delivery_rate REAL DEFAULT 0.0,
                    open_rate REAL DEFAULT 0.0,
                    click_rate REAL DEFAULT 0.0,
                    response_rate REAL DEFAULT 0.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            ''')

            print("Successfully created campaign_variants table")

        # Commit changes and close connection
        conn.commit()
        conn.close()

        print("Database migration completed successfully!")

    except Exception as e:
        print(f"Error during database migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()