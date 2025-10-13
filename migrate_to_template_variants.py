#!/usr/bin/env python3
"""
Migration script to transition from CampaignVariant to TemplateVariant system
This creates the template_variants table and migrates any existing data
"""

import sqlite3
from datetime import datetime
import os

def migrate_database():
    """Migrate database to use template_variants instead of campaign_variants"""

    # Use the existing database
    db_path = 'data/app.db'

    if not os.path.exists(db_path):
        print(f"Database {db_path} not found!")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("=== DATABASE MIGRATION: Campaign Variants → Template Variants ===")

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

        # 2. Check if campaign_variants table exists and has data
        print("\n2. Checking for existing campaign_variants data...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='campaign_variants'")
        campaign_variants_exists = cursor.fetchone() is not None

        if campaign_variants_exists:
            cursor.execute("SELECT COUNT(*) FROM campaign_variants")
            variant_count = cursor.fetchone()[0]
            print(f"   Found {variant_count} campaign variants to migrate")

            if variant_count > 0:
                # 3. Migrate data from campaign_variants to template_variants
                print("\n3. Migrating campaign variant data to template variants...")

                # Get all campaign variants with their associated template info
                cursor.execute('''
                SELECT cv.id, cv.campaign_id, cv.variant_name, cv.subject_line, cv.email_body,
                       cv.email_body_html, cv.is_default, cv.is_active, cv.emails_sent,
                       c.template_id, et.name as template_name
                FROM campaign_variants cv
                JOIN campaigns c ON cv.campaign_id = c.id
                LEFT JOIN email_templates et ON c.template_id = et.id
                WHERE c.template_id IS NOT NULL
                ''')

                campaign_variants = cursor.fetchall()

                for variant in campaign_variants:
                    cv_id, campaign_id, variant_name, subject_line, email_body, email_body_html, is_default, is_active, emails_sent, template_id, template_name = variant

                    # Create template variant
                    cursor.execute('''
                    INSERT INTO template_variants
                    (template_id, variant_name, variant_label, subject_line, email_body, email_body_html,
                     is_default, is_active, emails_sent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (template_id, variant_name, f"{template_name} - {variant_name}",
                          subject_line, email_body, email_body_html, is_default, is_active, emails_sent))

                    print(f"   Migrated variant '{variant_name}' for template '{template_name}'")

        else:
            print("   No campaign_variants table found - clean migration")

        # 4. Update Email model to use template_variant_id
        print("\n4. Checking emails table structure...")
        cursor.execute("PRAGMA table_info(emails)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'template_variant_id' not in columns:
            print("   Adding template_variant_id column to emails table...")
            cursor.execute('ALTER TABLE emails ADD COLUMN template_variant_id INTEGER')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_emails_template_variant_id ON emails(template_variant_id)')
        else:
            print("   template_variant_id column already exists")

        # 5. Create indexes for performance
        print("\n5. Creating indexes...")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_template_variants_template_id ON template_variants(template_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_template_variants_active ON template_variants(is_active)')

        # 6. Add campaign variant testing fields to campaigns table
        print("\n6. Updating campaigns table...")
        cursor.execute("PRAGMA table_info(campaigns)")
        campaign_columns = [column[1] for column in cursor.fetchall()]

        if 'variant_testing_enabled' not in campaign_columns:
            cursor.execute('ALTER TABLE campaigns ADD COLUMN variant_testing_enabled BOOLEAN DEFAULT 0')

        if 'variant_split_strategy' not in campaign_columns:
            cursor.execute('ALTER TABLE campaigns ADD COLUMN variant_split_strategy VARCHAR(20) DEFAULT "equal"')

        if 'variant_winner_declared' not in campaign_columns:
            cursor.execute('ALTER TABLE campaigns ADD COLUMN variant_winner_declared BOOLEAN DEFAULT 0')

        if 'winning_variant_id' not in campaign_columns:
            cursor.execute('ALTER TABLE campaigns ADD COLUMN winning_variant_id INTEGER')

        # Commit all changes
        conn.commit()
        print("\n✅ Migration completed successfully!")

        # 7. Show summary
        cursor.execute("SELECT COUNT(*) FROM template_variants")
        template_variant_count = cursor.fetchone()[0]

        print(f"\n📊 MIGRATION SUMMARY:")
        print(f"   • Template variants created: {template_variant_count}")
        print(f"   • Database schema updated")
        print(f"   • Indexes created for performance")

        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate_database()
    if success:
        print("\n🎉 Ready to test the new template variant system!")
    else:
        print("\n💥 Migration failed - please check the errors above")