"""
Initialize or migrate the database with all models
"""
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from models.database import db, Client, Campaign, Contact, Email, EmailTemplate, EmailSequenceConfig

def init_database():
    """Initialize the database with all tables"""
    # Create a minimal Flask app
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sales_master.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize database with app
    db.init_app(app)

    with app.app_context():
        print("Initializing database...")
        print("=" * 70)

        # Create all tables
        print("\nCreating all tables...")
        db.create_all()

        print("[OK] All tables created successfully!")
        print("\nTables created:")
        print("  - clients")
        print("  - campaigns")
        print("  - contacts")
        print("  - emails")
        print("  - email_templates")
        print("  - email_sequence_configs")
        print("  - sequence_steps")
        print("  - email_sequences")
        print("  - contact_campaign_status")
        print("  - responses")
        print("  - webhook_events")
        print("  - settings")
        print("  - template_variants")

        print("\n" + "=" * 70)
        print("Database initialization completed successfully!")

if __name__ == '__main__':
    init_database()
