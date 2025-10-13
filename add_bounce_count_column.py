#!/usr/bin/env python3
"""
Migration script to add bounce_count column to campaigns table
"""
import sqlite3
import os

def add_bounce_count_column():
    db_path = '/home/savetyonline/data/app.db'

    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return False

    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if bounce_count column already exists
        cursor.execute("PRAGMA table_info(campaigns)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'bounce_count' in columns:
            print("✅ bounce_count column already exists")
            conn.close()
            return True

        # Add the new column
        cursor.execute("ALTER TABLE campaigns ADD COLUMN bounce_count INTEGER DEFAULT 0")

        # Commit the changes
        conn.commit()

        print("✅ Successfully added bounce_count column to campaigns table")

        # Verify the column was added
        cursor.execute("PRAGMA table_info(campaigns)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'bounce_count' in columns:
            print("✅ Column verified successfully")

            # Show some stats
            cursor.execute("SELECT COUNT(*) FROM campaigns")
            count = cursor.fetchone()[0]
            print(f"📊 Found {count} existing campaigns - they will default to bounce_count=0")

        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"❌ SQLite error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Starting database migration to add bounce_count...")
    success = add_bounce_count_column()

    if success:
        print("✅ Migration completed successfully!")
        print("🚀 Bounce counting is now enabled for campaigns")
    else:
        print("❌ Migration failed!")