# SalesBreachPro - Complete System Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [PHP Proxy System](#php-proxy-system)
4. [Flask Application](#flask-application)
5. [Apache Configuration](#apache-configuration)
6. [Deployment Process](#deployment-process)
7. [File Structure](#file-structure)
8. [Troubleshooting](#troubleshooting)
9. [Security Configuration](#security-configuration)

## System Overview

**SalesBreachPro** is a Flask-based web application designed for cybersecurity marketing campaigns. The system is deployed on a cPanel shared hosting environment at `marketing.savety.online` using a sophisticated PHP proxy architecture.

### Key Components:
- **Frontend**: HTML templates with Bootstrap 5 and Font Awesome
- **Backend**: Python Flask application with SQLite database
- **Proxy Layer**: PHP-based request forwarding system
- **Web Server**: Apache with mod_rewrite
- **Application Server**: Gunicorn WSGI server
- **Domain**: `marketing.savety.online`

## Architecture

```
Internet → Cloudflare CDN → Apache Web Server → PHP Proxy → Gunicorn (Flask App)
    ↓              ↓                ↓             ↓              ↓
Port 443/80    Port 80/443    .htaccess    index.php    Port 5001 (localhost)
```

### Request Flow:
1. **User Request**: Browser sends request to `marketing.savety.online`
2. **Cloudflare**: CDN processes request and forwards to Apache
3. **Apache**: Processes `.htaccess` rules and routes to `index.php`
4. **PHP Proxy**: `index.php` forwards request to Flask on `127.0.0.1:5001`
5. **Flask Application**: Processes request and returns response
6. **Response Chain**: Response flows back through the same chain to user

## PHP Proxy System

### Core File: `/home/savetyonline/public_html/index.php`

```php
<?php
// Direct Flask Proxy with proper header forwarding
$request_uri = $_SERVER['REQUEST_URI'];
$flask_url = 'http://127.0.0.1:5001' . $request_uri;

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $flask_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false); // CRITICAL: Prevents redirect issues
curl_setopt($ch, CURLOPT_TIMEOUT, 30);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $_SERVER['REQUEST_METHOD']);

// Forward headers
$headers = [];
foreach (getallheaders() as $name => $value) {
    if (strtolower($name) !== 'host') {
        $headers[] = $name . ': ' . $value;
    }
}
if (!empty($headers)) {
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
}

// Forward POST data
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    curl_setopt($ch, CURLOPT_POSTFIELDS, file_get_contents('php://input'));
}

// Capture response headers
curl_setopt($ch, CURLOPT_HEADERFUNCTION, function($curl, $header) {
    $trimmed = trim($header);
    if (!empty($trimmed) && strpos($trimmed, 'HTTP/') !== 0) {
        header($trimmed);
    }
    return strlen($header);
});

$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$error = curl_error($ch);

curl_close($ch);

if ($error) {
    http_response_code(500);
    echo "Flask application is starting up...";
} else {
    http_response_code($http_code);
    echo $response;
}
?>
```

### Key Features:
- **Header Forwarding**: All request headers (except Host) are forwarded to Flask
- **Method Preservation**: HTTP method (GET, POST, etc.) is maintained
- **POST Data**: Request body is forwarded for POST requests
- **Response Headers**: Flask response headers are passed back to client
- **Error Handling**: Graceful handling of Flask connection errors
- **Critical Fix**: `CURLOPT_FOLLOWLOCATION = false` prevents 405 Method Not Allowed errors

### Why CURLOPT_FOLLOWLOCATION is Critical:
When set to `true`, cURL automatically follows redirects but changes POST requests to GET, causing Flask's authentication redirect (POST /login → 302 → GET /dashboard) to fail with "405 Method Not Allowed".

## Flask Application

### Application Factory Pattern: `/home/savetyonline/public_html/app.py`

```python
def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "data", "app.db")}'
    app.config['ADMIN_USERNAME'] = 'admin'
    app.config['ADMIN_PASSWORD'] = 'SalesBreachPro2025!'
    
    # Initialize database
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(campaigns_bp)
    # ... additional blueprints
    
    return app
```

### Blueprint Architecture:
- **auth_bp**: Authentication (login/logout) - `/routes/auth.py`
- **dashboard_bp**: Main dashboard - `/routes/dashboard.py`
- **campaigns_bp**: Campaign management - `/routes/campaigns.py`
- **contacts_bp**: Contact management - `/routes/contacts.py`
- **api_bp**: API endpoints - `/routes/api.py`
- **analytics_bp**: Analytics views - `/routes/analytics.py`
- **tracking_bp**: Email tracking - `/routes/tracking.py`
- **sequences_bp**: Email sequences - `/routes/sequences.py`

### Authentication System: `/home/savetyonline/public_html/routes/auth.py`

```python
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if (username == current_app.config['ADMIN_USERNAME'] and 
            password == current_app.config['ADMIN_PASSWORD']):
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect('/dashboard')  # Direct path to prevent proxy issues
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')
```

### Database Models:
Located in `/home/savetyonline/public_html/models/database.py`
- **Contact**: Customer contact information
- **Campaign**: Marketing campaigns
- **Breach**: Data breach information
- **Email**: Email messages
- **Response**: Email responses
- **EmailTemplate**: Reusable email templates
- **FollowUpSequence**: Automated email sequences
- **Settings**: Application configuration

## Apache Configuration

### `.htaccess` File: `/home/savetyonline/public_html/.htaccess`

```apache
DirectoryIndex index.php

RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ index.php [QSA,L]

# Security headers
Header always set X-Content-Type-Options nosniff
Header always set X-Frame-Options DENY
Header always set X-XSS-Protection "1; mode=block"

# File upload limits
LimitRequestBody 16777216

# Disable directory browsing
Options -Indexes

# Protect sensitive files
<FilesMatch "\.(env|py|wsgi|log|pid)$">
    Order allow,deny
    Deny from all
</FilesMatch>

# php -- BEGIN cPanel-generated handler
<IfModule mime_module>
  AddHandler application/x-httpd-ea-php80 .php .php8 .phtml
</IfModule>
# php -- END cPanel-generated handler
```

### Key Directives:
- **DirectoryIndex**: Sets `index.php` as default file
- **RewriteRule**: Routes all requests to `index.php` (catch-all)
- **Security Headers**: XSS protection, content type sniffing prevention
- **File Protection**: Blocks access to sensitive file types
- **Upload Limits**: 16MB request body limit

## Deployment Process

### 1. Environment Setup

**Server Requirements:**
- cPanel shared hosting with SSH access
- PHP 8.0+ with cURL extension
- Python 3.8+ with pip
- Apache with mod_rewrite enabled

**Directory Structure:**
```
/home/savetyonline/public_html/
├── index.php (PHP proxy)
├── .htaccess (Apache config)
├── wsgi.py (WSGI entry point)
├── app.py (Flask application factory)
├── data/ (SQLite database)
├── templates/ (Jinja2 templates)
├── static/ (CSS, JS, images)
├── routes/ (Flask blueprints)
├── models/ (Database models)
├── services/ (Business logic)
├── utils/ (Utilities)
├── venv/ (Python virtual environment)
└── marketing/ (backup/duplicate files)
```

### 2. Python Environment Setup

```bash
# Create virtual environment
cd /home/savetyonline/public_html/
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Dependencies include:
# Flask==2.3.3
# Flask-SQLAlchemy==3.0.5
# gunicorn==21.2.0
# python-dotenv==1.0.0
# requests==2.31.0
# APScheduler==3.10.4
```

### 3. WSGI Configuration

**File: `/home/savetyonline/public_html/wsgi.py`**
```python
from app import create_app

application = create_app()

if __name__ == "__main__":
    application.run()
```

### 4. Gunicorn Service Setup

**Start Command:**
```bash
/home/savetyonline/public_html/marketing/venv/bin/python -m gunicorn \
    --bind 127.0.0.1:5001 \
    --workers 1 \
    --timeout 120 \
    --log-file /home/savetyonline/public_html/flask.log \
    --pid /home/savetyonline/public_html/flask.pid \
    --daemon \
    wsgi:application
```

**Process Management:**
```bash
# Check running processes
ps aux | grep gunicorn

# Kill existing process
kill -9 $(cat /home/savetyonline/public_html/flask.pid)

# View logs
tail -f /home/savetyonline/public_html/flask.log
```

### 5. Database Initialization

```bash
cd /home/savetyonline/public_html/
source venv/bin/activate
python -c "from app import create_app; app = create_app(); app.app_context().push(); from models.database import db; db.create_all()"
```

## File Structure

```
/home/savetyonline/public_html/
├── app.py                     # Flask application factory
├── wsgi.py                    # WSGI entry point
├── index.php                  # PHP proxy (main entry point)
├── .htaccess                  # Apache configuration
├── requirements.txt           # Python dependencies
├── flask.log                  # Application logs
├── flask.pid                  # Gunicorn process ID
├── env                        # Environment variables
├── run_flask.py               # Flask application runner
├── create_default_sequence.py # Creates default email sequences  
├── add_breach_templates.py    # Adds default breach email templates
├── 
├── data/
│   └── app.db                 # SQLite database
├── 
├── models/
│   ├── __init__.py
│   └── database.py            # SQLAlchemy models
├── 
├── routes/                    # Flask blueprints
│   ├── __init__.py
│   ├── auth.py                # Authentication routes
│   ├── dashboard.py           # Dashboard routes  
│   ├── campaigns.py           # Campaign management
│   ├── contacts.py            # Contact management
│   ├── api.py                 # API endpoints
│   ├── analytics.py           # Analytics views
│   ├── tracking.py            # Email tracking
│   ├── sequences.py           # Email sequences
│   ├── webhooks.py            # Brevo webhook handlers
│   └── email_trigger.py       # Manual email testing
├── 
├── templates/                 # Jinja2 templates
│   ├── base.html              # Base template
│   ├── login.html             # Login page
│   ├── dashboard.html         # Dashboard
│   ├── campaigns.html         # Campaigns list
│   └── ...                    # Additional templates
├── 
├── static/                    # Static assets
│   ├── css/
│   ├── js/
│   └── images/
├── 
├── services/                  # Business logic
│   ├── __init__.py
│   ├── email_service.py       # Core email service functionality
│   ├── scheduler.py           # Background task scheduling (APScheduler)
│   ├── template_routes.py     # Template management (legacy)
│   ├── email_processor.py     # Email processing and delivery logic
│   ├── analytics_sync.py      # Analytics data synchronization
│   ├── email_sequence_service.py # Automated email sequences
│   ├── auto_enrollment.py     # Automated contact enrollment
│   ├── campaign_analytics.py  # Campaign performance analytics
│   └── contact_routes.py      # Legacy contact route handling
├── 
├── utils/                     # Utilities
│   ├── __init__.py
│   ├── decorators.py          # Custom decorators (login_required)
│   ├── pagination.py          # Pagination helper
│   └── database_seeder.py     # Data seeding utilities
├── 
├── venv/                      # Virtual environment
│   ├── bin/
│   ├── lib/
│   └── include/
└── 
└── marketing/                 # Backup directory (duplicate)
    └── [mirror of above structure]
```

## Troubleshooting

### Common Issues and Solutions

#### 1. "Flask application is starting up..." Error
**Symptoms**: PHP proxy shows startup message instead of Flask content
**Causes**:
- Gunicorn process not running
- Wrong port configuration
- Flask application crash

**Solutions**:
```bash
# Check if Gunicorn is running
ps aux | grep gunicorn

# Check logs for errors
tail -f /home/savetyonline/public_html/flask.log

# Restart Gunicorn
kill -9 $(cat flask.pid)
/home/savetyonline/public_html/marketing/venv/bin/python -m gunicorn --bind 127.0.0.1:5001 --workers 1 --timeout 120 --log-file /home/savetyonline/public_html/flask.log --pid /home/savetyonline/public_html/flask.pid --daemon wsgi:application
```

#### 2. "405 Method Not Allowed" After Login
**Symptoms**: Login form submits but returns 405 error
**Cause**: `CURLOPT_FOLLOWLOCATION` set to `true` in PHP proxy
**Solution**: Ensure `index.php` has `curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false);`

#### 3. Static Assets Not Loading
**Symptoms**: CSS/JS files return 404 errors
**Causes**:
- Wrong URL generation in templates
- .htaccess routing issues

**Solutions**:
- Verify `{{ url_for('static', filename='css/style.css') }}` in templates
- Check static file permissions
- Ensure static directory exists

#### 4. Database Connection Errors
**Symptoms**: SQLite database errors in logs
**Solutions**:
```bash
# Check database file exists
ls -la /home/savetyonline/public_html/data/app.db

# Check permissions
chmod 664 /home/savetyonline/public_html/data/app.db
chmod 775 /home/savetyonline/public_html/data/

# Recreate database
python -c "from app import create_app; app = create_app(); app.app_context().push(); from models.database import db; db.create_all()"
```

#### 5. Session/Cookie Issues
**Symptoms**: Login doesn't persist, frequent logouts
**Causes**:
- Missing session configuration
- Cookie domain issues

**Solutions**:
- Verify `SECRET_KEY` in Flask configuration
- Check cookie settings in browser dev tools
- Ensure HTTPS is properly configured

#### 6. Background Scheduler Issues
**Symptoms**: Automated emails not sending, sequences not processing
**Causes**:
- APScheduler service not initialized
- Background jobs failing silently
- Database connection issues in background tasks

**Solutions**:
```bash
# Check scheduler status in Flask logs
grep -i "scheduler" /home/savetyonline/public_html/flask.log

# Restart Flask to reinitialize scheduler
kill -9 $(cat flask.pid)
/home/savetyonline/public_html/marketing/venv/bin/python -m gunicorn --bind 127.0.0.1:5001 --workers 1 --timeout 120 --log-file /home/savetyonline/public_html/flask.log --pid /home/savetyonline/public_html/flask.pid --daemon wsgi:application
```

#### 7. Webhook Processing Errors
**Symptoms**: Email tracking data not updating, webhook events ignored
**Causes**:
- Brevo webhooks not configured
- Webhook endpoint not accessible
- Authentication issues with webhook payload

**Solutions**:
- Verify webhook URL in Brevo dashboard: `https://marketing.savety.online/webhooks/brevo`
- Check webhook logs: `grep -i "webhook" flask.log`
- Test webhook endpoint: `curl -X POST https://marketing.savety.online/webhooks/brevo`

#### 8. Email Service Configuration
**Symptoms**: Test emails failing, Brevo API errors
**Causes**:
- Invalid Brevo API key
- Sender email not verified
- API rate limits exceeded

**Solutions**:
- Test API connection via Settings page
- Verify sender domain in Brevo dashboard
- Check API key permissions and limits

### Debugging Tools

#### 1. Enable Debug Logging in PHP
Add to `index.php`:
```php
// Add after curl_exec
error_log("Flask URL: " . $flask_url);
error_log("HTTP Code: " . $http_code);
error_log("Response: " . substr($response, 0, 200));
```

#### 2. Flask Debug Mode
Temporarily enable in `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

#### 3. Monitor Real-time Logs
```bash
# Flask application logs
tail -f /home/savetyonline/public_html/flask.log

# Apache error logs
tail -f /home/savetyonline/logs/error_log

# Apache access logs
tail -f /home/savetyonline/logs/access_log
```

## Security Configuration

### 1. File Permissions
```bash
# Application files
chmod 644 *.php *.py *.html
chmod 755 directories
chmod 600 env flask.log flask.pid

# Executable files
chmod 755 run_flask.py manage.php
```

### 2. Sensitive File Protection
`.htaccess` rules protect:
- `.env` files (environment variables)
- `.py` files (source code)
- `.wsgi` files (WSGI configuration)
- `.log` files (application logs)
- `.pid` files (process IDs)

### 3. Security Headers
```apache
Header always set X-Content-Type-Options nosniff
Header always set X-Frame-Options DENY
Header always set X-XSS-Protection "1; mode=block"
```

### 4. Input Validation
- Flask-WTF for form validation
- SQLAlchemy ORM prevents SQL injection
- Session-based authentication
- CSRF protection on forms

### 5. Environment Variables
Sensitive data stored in `/home/savetyonline/public_html/env`:
```bash
SECRET_KEY=production-secret-key
DATABASE_URL=sqlite:///data/app.db
FLAWTRACK_API_TOKEN=your-api-token-here
```

## Performance Optimization

### 1. Caching Strategy
- Cloudflare CDN for static assets
- Flask response caching for dashboard data
- Database query optimization with SQLAlchemy

### 2. Resource Management
- Gunicorn single worker (shared hosting limitation)
- Connection pooling for database
- Efficient SQL queries with proper indexing

### 3. Monitoring
- Application logs in `flask.log`
- Process monitoring via PID file
- Error tracking through Flask logging

---

## Maintenance Commands

### Daily Operations
```bash
# Check application status
ps aux | grep gunicorn
curl -s http://127.0.0.1:5001/login | head -5

# View recent logs
tail -20 /home/savetyonline/public_html/flask.log

# Check scheduler status
grep -i "scheduler" /home/savetyonline/public_html/flask.log | tail -5

# Check webhook events
grep -i "webhook" /home/savetyonline/public_html/flask.log | tail -10

# Restart if needed
kill -9 $(cat flask.pid)
/home/savetyonline/public_html/marketing/venv/bin/python -m gunicorn --bind 127.0.0.1:5001 --workers 1 --timeout 120 --log-file /home/savetyonline/public_html/flask.log --pid /home/savetyonline/public_html/flask.pid --daemon wsgi:application
```

### Database Backup
```bash
# Backup database
cp data/app.db data/app.db.backup.$(date +%Y%m%d)

# List backups
ls -la data/app.db.backup.*
```

### System Health Check
```bash
# Disk usage
df -h /home/savetyonline/

# Memory usage
free -m

# Process list
ps aux | grep -E "(gunicorn|python|apache)"

# Check API endpoints
curl -s http://127.0.0.1:5001/api/stats | jq .
curl -s http://127.0.0.1:5001/api/automation-status | jq .

# Test email service configuration
curl -X GET http://127.0.0.1:5001/test-email

# Check database status
ls -la /home/savetyonline/public_html/data/app.db
sqlite3 /home/savetyonline/public_html/data/app.db "SELECT COUNT(*) FROM contacts;"
```

---

## Current Project Status & Features

### Application Features (As Implemented)
- **Dynamic Dashboard**: Real-time metrics showing email campaigns, response rates, and lead tracking
- **Contact Management**: Full CRUD operations for prospects with risk scoring and breach status tracking
- **Campaign Management**: Create, manage and monitor email outreach campaigns with templates
- **Breach Analysis Integration**: FlawTrack API integration for cybersecurity risk assessment
- **Email Service Integration**: Brevo API for reliable email delivery and tracking
- **Automated Email Sequences**: Background scheduler for automated follow-up campaigns
- **Webhook System**: Real-time email event tracking (opens, clicks, bounces, spam reports)
- **Email Templates**: Customizable templates with dynamic variable substitution
- **Analytics Dashboard**: Advanced metrics with industry breakdowns and risk analysis
- **Test Email System**: Built-in email testing functionality with template preview
- **Auto-enrollment**: Automated contact enrollment based on breach status

### Recently Added Components

#### New Route Files
- **webhooks.py** (`/routes/webhooks.py`): Handles Brevo webhook events for email tracking
- **email_trigger.py** (`/routes/email_trigger.py`): Manual email testing and triggering
- **sequences.py** (`/routes/sequences.py`): Email sequence management

#### New Service Files
- **email_processor.py** (`/services/email_processor.py`): Email processing and delivery logic
- **analytics_sync.py** (`/services/analytics_sync.py`): Analytics data synchronization
- **email_sequence_service.py** (`/services/email_sequence_service.py`): Automated email sequences
- **auto_enrollment.py** (`/services/auto_enrollment.py`): Automated contact enrollment
- **campaign_analytics.py** (`/services/campaign_analytics.py`): Campaign performance analytics
- **contact_routes.py** (`/services/contact_routes.py`): Legacy contact route handling
- **scheduler.py** (`/services/scheduler.py`): Background task scheduling with APScheduler
- **email_service.py** (`/services/email_service.py`): Core email service functionality

#### Updated Dependencies
The requirements.txt now includes:
- `schedule==1.2.0` - For task scheduling
- `brevo-python==1.2.0` - Brevo email service Python SDK
- `sib-api-v3-sdk==7.6.0` - SendinBlue/Brevo API SDK
- `APScheduler==3.10.4` - Advanced Python Scheduler (inferred from code)

### Database Schema Updates

The Contact model now includes extensive email tracking fields:
- `last_opened_at`, `last_clicked_at`, `last_contacted_at` - Email engagement timestamps
- `total_opens`, `total_clicks` - Engagement counters
- `email_status` - Email validity status (unknown, valid, bounced)
- `bounce_type` - Hard or soft bounce classification
- `is_subscribed`, `has_responded` - Subscription and response tracking
- `marked_as_spam`, `spam_reported_at` - Spam detection fields

## Updated Application Architecture

### Enhanced Request Flow
```
Internet → Cloudflare CDN → Apache Web Server → PHP Proxy → Gunicorn (Flask App)
    ↓              ↓                ↓             ↓              ↓
Port 443/80    Port 80/443    .htaccess    index.php    Port 5001 (localhost)
                                                            ↓
                                                    Background Services:
                                                    - Email Scheduler (APScheduler)
                                                    - Webhook Processors
                                                    - Auto-enrollment Service
                                                    - Analytics Sync
```

### Service Integration Architecture
```
SalesBreachPro Flask App
    ├── Brevo Email Service (API Integration)
    ├── FlawTrack Breach API (Risk Assessment)
    ├── Background Scheduler (APScheduler)
    ├── Webhook Event Processing
    └── Real-time Analytics Engine
```

---

**Documentation Version**: 2.0  
**Last Updated**: September 13, 2025  
**System Status**: Production Active - Enhanced with Automation  
**Contact**: SalesBreachPro Technical Team