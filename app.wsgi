#!/usr/bin/env python3
"""
Apache WSGI Configuration for SalesBreachPro
Compatible with cPanel and shared hosting environments
"""

import sys
import os

# Get the directory containing this WSGI file (auto-detects deployment location)
app_dir = os.path.dirname(os.path.abspath(__file__))

# Virtual environment path (if using virtual environment)
venv_dir = os.path.join(app_dir, "venv", "lib", "python3.8", "site-packages")

# Add paths to Python path
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)
    
# Add virtual environment if it exists
if os.path.exists(venv_dir):
    sys.path.insert(0, venv_dir)

# Change to application directory
os.chdir(app_dir)

# Set production environment variables
os.environ['FLASK_ENV'] = 'production'
if 'SECRET_KEY' not in os.environ:
    os.environ['SECRET_KEY'] = 'marketing-savety-prod-2024-secure-key-change-me'
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'sqlite:///data/app.db'

def application(environ, start_response):
    """WSGI application callable for Apache mod_wsgi"""
    try:
        # Import and create Flask app
        from app import create_app
        flask_app = create_app()
        
        # Configure for production
        flask_app.config['ENV'] = 'production'
        flask_app.config['DEBUG'] = False
        
        return flask_app(environ, start_response)
        
    except Exception as e:
        # Log error to file
        import logging
        import traceback
        
        error_log = os.path.join(app_dir, 'wsgi_error.log')
        logging.basicConfig(filename=error_log, level=logging.ERROR)
        logging.error(f"WSGI Error: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        
        # Return error response
        status = '500 Internal Server Error'
        response_headers = [('Content-type', 'text/html; charset=utf-8')]
        start_response(status, response_headers)
        
        error_html = f"""
        <html>
        <head><title>SalesBreachPro Error</title></head>
        <body>
            <h1>Application Error</h1>
            <p>SalesBreachPro failed to start. Please check the server logs.</p>
            <p><strong>Error:</strong> {str(e)}</p>
            <p><strong>App Directory:</strong> {app_dir}</p>
            <p><strong>Python Path:</strong> {sys.path[:3]}</p>
        </body>
        </html>
        """
        return [error_html.encode('utf-8')]

# For testing and development
if __name__ == "__main__":
    print("Testing WSGI application...")
    print(f"App directory: {app_dir}")
    print(f"Python version: {sys.version}")
    
    try:
        from app import create_app
        app = create_app()
        print("Flask app created successfully!")
        print("Available routes:")
        
        with app.app_context():
            for rule in app.url_map.iter_rules():
                methods = ','.join(rule.methods - {'HEAD', 'OPTIONS'})
                print(f"  {rule.rule} [{methods}]")
        
        app.run(debug=False, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Error creating Flask app: {e}")
        import traceback
        traceback.print_exc()