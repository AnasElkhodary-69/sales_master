# Marketing Savety - Flask Application Deployment Guide

## 🌐 Current Production Deployment (marketing.savety.online)

### Architecture Overview
- **Server**: Ubuntu 20.04.6 LTS on Contabo VPS
- **Web Server**: Apache httpd (managed by cPanel EasyApache)
- **Application**: Flask Python 3.8.10
- **Database**: SQLite (data/app.db)
- **Domain**: marketing.savety.online
- **SSL**: Managed via cPanel

### Current Setup Details

**Application Location**: `/home/savetyonline/`

**Running Process**:
```bash
python3 -c "from app import create_app; app = create_app(); print('Starting Flask app on port 5001...'); app.run(host='127.0.0.1', port=5001, debug=False)"
```

**Apache Proxy Configuration**:
- SSL Config: `/etc/apache2/conf.d/userdata/ssl/2_4/savetyonline/marketing.savety.online.conf`
- Non-SSL Config: `/etc/apache2/conf.d/userdata/std/2_4/savetyonline/marketing.savety.online.conf`
- Proxies requests from port 80/443 to localhost:5001

### Apache Configuration Files

**SSL Configuration** (`/etc/apache2/conf.d/userdata/ssl/2_4/savetyonline/marketing.savety.online.conf`):
```apache
# marketing.savety.online HTTPS Python Flask app proxy configuration
# Proxy requests to the Flask app running on localhost:5001

# Enable proxy modules if not already enabled
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so

# Proxy all requests to Flask app
ProxyPreserveHost On
ProxyPass / http://127.0.0.1:5001/
ProxyPassReverse / http://127.0.0.1:5001/

# Static files served directly if they exist
RewriteEngine On
RewriteCond %{REQUEST_URI} ^/static/
RewriteCond %{DOCUMENT_ROOT}%{REQUEST_URI} -f
RewriteRule ^(.*)$ $1 [L]
```

**Non-SSL Configuration** (`/etc/apache2/conf.d/userdata/std/2_4/savetyonline/marketing.savety.online.conf`):
```apache
# marketing.savety.online Python Flask app proxy configuration
# Proxy requests to the Flask app running on localhost:5001

# Enable proxy modules if not already enabled
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so

# Proxy all requests to Flask app
ProxyPreserveHost On
ProxyPass / http://127.0.0.1:5001/
ProxyPassReverse / http://127.0.0.1:5001/

# Static files served directly if they exist
RewriteEngine On
RewriteCond %{REQUEST_URI} ^/static/
RewriteCond %{DOCUMENT_ROOT}%{REQUEST_URI} -f
RewriteRule ^(.*)$ $1 [L]
```

### Starting the Application

**Current Method** (manual start):
```bash
cd /home/savetyonline
python3 -c "from app import create_app; app = create_app(); print('Starting Flask app on port 5001...'); app.run(host='127.0.0.1', port=5001, debug=False)"
```

**Recommended Method** (background process):
```bash
cd /home/savetyonline
nohup python3 -c "from app import create_app; app = create_app(); print('Starting Flask app on port 5001...'); app.run(host='127.0.0.1', port=5001, debug=False)" > logs/app.log 2>&1 &
```

### Deployment Process

1. **Stop Current Application**:
   ```bash
   pkill -f "from app import create_app"
   ```

2. **Update Code**:
   ```bash
   cd /home/savetyonline
   git pull origin refactoring
   ```

3. **Start Application**:
   ```bash
   nohup python3 -c "from app import create_app; app = create_app(); print('Starting Flask app on port 5001...'); app.run(host='127.0.0.1', port=5001, debug=False)" > logs/app.log 2>&1 &
   ```

4. **Reload Apache** (if configuration changed):
   ```bash
   systemctl reload httpd
   ```

### Environment Configuration

The application uses environment variables from `.env` file:
```bash
# Located at /home/savetyonline/.env
# Contains database paths, API keys, and Flask configuration
```

### File Structure

```
/home/savetyonline/
├── app.py                 # Main Flask application
├── data/                  # SQLite database files
├── logs/                  # Application logs
├── models/                # Database models
├── routes/                # Flask routes
├── templates/             # Jinja2 templates
├── static/                # CSS, JS, images
├── .env                   # Environment variables
└── requirements.txt       # Python dependencies
```

### Key Services Integration

- **FlawTrack API**: Breach data integration
- **AWS SES**: Email delivery service
- **SQLite**: Local database storage
- **Celery**: Background task processing (if configured)

### Domain & SSL

- **Domain**: marketing.savety.online
- **SSL Certificate**: Managed automatically via cPanel
- **DNS**: Configured through domain registrar to point to server IP

This deployment setup provides a production-ready Flask application running behind Apache with SSL termination and proxy configuration managed through cPanel.