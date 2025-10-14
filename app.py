"""
SalesBreachPro Application Factory
Clean, modular Flask application setup
"""
import os
from flask import Flask
from dotenv import load_dotenv

# Import database models
from models.database import (
    db, Contact, Campaign, TemplateVariant, Email, Response,
    EmailTemplate, Settings, WebhookEvent, EmailSequenceConfig,
    SequenceStep, EmailSequence, ContactCampaignStatus
)

# Import blueprints
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.campaigns import campaigns_bp
from routes.contacts import contacts_bp
from routes.api import api_bp
from routes.analytics import analytics_bp
from routes.tracking import tracking_bp
from routes.sequences import sequences_bp
from routes.templates import templates_bp
from routes.webhooks import webhooks_bp
from routes.email_trigger import email_trigger_bp
from routes.enhanced_analytics import enhanced_analytics_bp

# Import service routes
from services.template_routes import register_template_routes


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Load environment variables from env file
    basedir = os.path.abspath(os.path.dirname(__file__))
    
    # Try .env first (standard), then env (custom)
    env_files = ['.env', 'env']
    loaded = False
    
    for env_filename in env_files:
        env_file = os.path.join(basedir, env_filename)
        if os.path.exists(env_file):
            load_dotenv(env_file)
            print(f"Loaded environment variables from: {env_file}")
            loaded = True
            break
    
    if not loaded:
        print(f"Warning: No environment file found (.env or env)")
    
    # Configuration - Use environment variables for security
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "data", "app.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # File upload configuration
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', '16777216'))  # 16MB default
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': -1,
        'echo': False
    }

    # Admin credentials from environment
    app.config['ADMIN_USERNAME'] = os.getenv('ADMIN_USERNAME', 'admin')
    app.config['ADMIN_PASSWORD'] = os.getenv('ADMIN_PASSWORD', 'SalesBreachPro2025!')

    # Secure session configuration
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    app.config['SESSION_COOKIE_HTTPONLY'] = os.getenv('SESSION_COOKIE_HTTPONLY', 'true').lower() == 'true'
    app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Strict')
    app.config['PERMANENT_SESSION_LIFETIME'] = int(os.getenv('PERMANENT_SESSION_LIFETIME', '86400'))
    
    # Initialize database
    db.init_app(app)
    
    # Register core blueprints with consistent URL patterns
    app.register_blueprint(auth_bp)                    # No prefix - root routes
    app.register_blueprint(dashboard_bp)               # No prefix - /dashboard, /settings
    app.register_blueprint(campaigns_bp)               # /campaigns/*
    app.register_blueprint(contacts_bp)                # /contacts/*
    app.register_blueprint(templates_bp)               # /templates/*
    app.register_blueprint(sequences_bp)               # /admin/sequences/*
    app.register_blueprint(analytics_bp)               # /analytics/*
    app.register_blueprint(tracking_bp)                # /track/*, /unsubscribe/*
    
    # Register API blueprints
    app.register_blueprint(api_bp)                     # /api/*
    app.register_blueprint(webhooks_bp)                # /webhooks/*
    app.register_blueprint(email_trigger_bp)           # /api/trigger-emails
    app.register_blueprint(enhanced_analytics_bp)      # /sequence-analytics, /api/sequence-*
    
    print("All blueprints registered successfully!")

    # Add BIMI logo route
    @app.route('/bimi-logo.svg')
    def bimi_logo():
        """Serve BIMI logo with correct content type"""
        from flask import send_file, Response
        import os

        logo_path = os.path.join(app.root_path, 'public_html', 'bimi-logo.svg')
        if os.path.exists(logo_path):
            with open(logo_path, 'r') as f:
                svg_content = f.read()
            return Response(svg_content, mimetype='image/svg+xml')
        else:
            return "BIMI logo not found", 404


    # Register service routes
    try:
        register_template_routes(app)
        print("Template service routes registered successfully!")
    except Exception as e:
        print(f"Warning: Could not register template routes: {e}")

    # Legacy route support for backward compatibility
    try:
        from services.contact_routes import init_contact_routes
        init_contact_routes(app)
        print("Legacy contact routes initialized successfully!")
    except Exception as e:
        print(f"Warning: Legacy contact routes not initialized: {e}")
    
    # Initialize database tables
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created successfully!")
        except Exception as e:
            print(f"Database error: {e}")
    
    # Initialize background scheduler for auto-enrollment
    try:
        from services.scheduler import init_scheduler
        init_scheduler(app, db)
        print("Background scheduler initialized successfully!")
    except Exception as e:
        print(f"Scheduler initialization warning: {e}")
        print("Auto-enrollment will not work automatically, but can be triggered manually")
    
    # Add error handlers for better production deployment
    @app.errorhandler(404)
    def not_found_error(error):
        return f"<h1>404 - Page Not Found</h1><p>The requested URL was not found on the server.</p>", 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return f"<h1>500 - Internal Server Error</h1><p>An internal server error occurred.</p>", 500

    # Add security and cache-busting headers
    @app.after_request
    def add_security_headers(response):
        """Add security headers and prevent caching of dynamic content"""
        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self';"
        )

        # Cache-busting headers for dynamic content
        if response.mimetype in ['text/html', 'text/css', 'application/javascript', 'application/json']:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            # Add a timestamp to force refresh
            import time
            response.headers['X-Timestamp'] = str(int(time.time()))
        return response

    return app


if __name__ == '__main__':
    print("Starting SalesBreachPro (modular version)...")
    app = create_app()
    if app:
        print("Application ready! Visit: http://localhost:5001")
        app.run(debug=False, host='0.0.0.0', port=5001)
    else:
        print("Failed to create application!")