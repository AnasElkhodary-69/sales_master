#!/usr/bin/env python3
"""Initialize the database for SalesBreachPro"""

from app import create_app
from models.database import init_db

if __name__ == '__main__':
    print("Initializing database...")
    app = create_app()
    init_db(app)
    print("Database initialized successfully!")