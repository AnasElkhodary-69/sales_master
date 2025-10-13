#!/usr/bin/env python3
"""
Simple database update to add template_variants table and required columns
"""

import sqlite3
import os

def update_database():
    """Add template_variants table and required columns to existing database"""

    db_path = 'data/app.db'

    if not os.path.exists(db_path):
        print(f"Database {db_path} not found!")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("=== UPDATING DATABASE FOR TEMPLATE VARIANTS ===")

        # 1. Create template_variants table
        print("\n1. Creating template_variants table...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS template_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            variant_name VARCHAR(50) NOT NULL,
            variant_label VARCHAR(100),
            subject_line VARCHAR(500) NOT NULL,
            email_body TEXT NOT NULL,
            email_body_html TEXT,
            is_default BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            weight INTEGER DEFAULT 50,
            emails_sent INTEGER DEFAULT 0,
            emails_delivered INTEGER DEFAULT 0,
            emails_opened INTEGER DEFAULT 0,
            emails_clicked INTEGER DEFAULT 0,
            emails_replied INTEGER DEFAULT 0,
            open_rate REAL DEFAULT 0.0,
            click_rate REAL DEFAULT 0.0,
            response_rate REAL DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES email_templates(id)
        )
        ''')

        # 2. Update emails table
        print("\n2. Updating emails table...")
        cursor.execute("PRAGMA table_info(emails)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'template_variant_id' not in columns:
            print("   Adding template_variant_id column...")
            cursor.execute('ALTER TABLE emails ADD COLUMN template_variant_id INTEGER')
        else:
            print("   template_variant_id column already exists")

        # 3. Update campaigns table
        print("\n3. Updating campaigns table...")
        cursor.execute("PRAGMA table_info(campaigns)")
        campaign_columns = [column[1] for column in cursor.fetchall()]

        if 'variant_testing_enabled' not in campaign_columns:
            print("   Adding variant_testing_enabled column...")
            cursor.execute('ALTER TABLE campaigns ADD COLUMN variant_testing_enabled BOOLEAN DEFAULT 0')

        if 'variant_split_strategy' not in campaign_columns:
            print("   Adding variant_split_strategy column...")
            cursor.execute('ALTER TABLE campaigns ADD COLUMN variant_split_strategy VARCHAR(20) DEFAULT "equal"')

        if 'variant_winner_declared' not in campaign_columns:
            print("   Adding variant_winner_declared column...")
            cursor.execute('ALTER TABLE campaigns ADD COLUMN variant_winner_declared BOOLEAN DEFAULT 0')

        if 'winning_variant_id' not in campaign_columns:
            print("   Adding winning_variant_id column...")
            cursor.execute('ALTER TABLE campaigns ADD COLUMN winning_variant_id INTEGER')

        # 4. Create indexes
        print("\n4. Creating indexes...")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_template_variants_template_id ON template_variants(template_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_template_variants_active ON template_variants(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_emails_template_variant_id ON emails(template_variant_id)')

        # Commit all changes
        conn.commit()
        print("\n✅ Database updated successfully!")

        # Show summary
        print(f"\n📊 UPDATE SUMMARY:")
        print(f"   • template_variants table created")
        print(f"   • emails table updated with template_variant_id")
        print(f"   • campaigns table updated with variant testing fields")
        print(f"   • Performance indexes created")

        return True

    except Exception as e:
        print(f"❌ Database update failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = update_database()
    if success:
        print("\n🎉 Database ready for template variant system!")
    else:
        print("\n💥 Database update failed")