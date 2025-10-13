#!/usr/bin/env python3
"""
WSGI Configuration for SalesBreachPro
Production deployment entry point
"""

import os
import sys
from pathlib import Path

# Add the project directory to Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Import the Flask application factory
from app import create_app

# Create the application instance
application = create_app()

# For debugging in production (remove in final deployment)
if __name__ == "__main__":
    print("Starting SalesBreachPro via WSGI...")
    print(f"Project root: {project_root}")
    print("Available routes:")
    
    with application.app_context():
        for rule in application.url_map.iter_rules():
            methods = ','.join(rule.methods - {'HEAD', 'OPTIONS'})
            print(f"  {rule.rule} [{methods}] -> {rule.endpoint}")
    
    application.run(host='0.0.0.0', port=8000, debug=False)