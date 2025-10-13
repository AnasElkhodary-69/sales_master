# SalesBreachPro - Server Deployment Guide

## Routing Consolidation Complete ✅

The application routing has been completely consolidated and standardized for server deployment.

## Deployment Options

### 1. Simple Development Server
```bash
python start.py
# Access at: http://localhost:5000
```

### 2. WSGI Production Server
```bash
python wsgi.py
# Access at: http://localhost:8000
```

### 3. Apache/cPanel Deployment
Upload `app.wsgi` and configure Apache to use it as the WSGI entry point.

## Route Structure

### Core Application Routes
| Route Pattern | Blueprint | Description |
|---------------|-----------|-------------|
| `/` | auth | Login/authentication |
| `/dashboard` | dashboard | Main dashboard |
| `/campaigns/*` | campaigns | Campaign management |
| `/contacts/*` | contacts | Contact management |
| `/templates/*` | templates | Email templates |
| `/admin/*` | sequences | Admin functions |

### API Routes
| Route Pattern | Description |
|---------------|-------------|
| `/api/*` | Main API endpoints |
| `/api/scan/*` | Domain scanning API |
| `/webhooks/*` | Webhook handlers |
| `/track/*` | Email tracking |

### Legacy Support
Legacy routes are automatically redirected to new endpoints for backward compatibility.

## Server Configuration

### Apache .htaccess (if needed)
```apache
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ app.wsgi/$1 [QSA,L]
```

### Environment Variables
Ensure these are set in production:
```bash
FLASK_ENV=production
SECRET_KEY=your-secure-secret-key
DATABASE_URL=sqlite:///data/app.db
BREVO_API_KEY=your-brevo-api-key
FLAWTRACK_API_TOKEN=your-flawtrack-token
```

## Database Setup
```bash
# Initialize database
python init_db.py

# Ensure data directory exists and is writable
mkdir -p data
chmod 755 data
```

## File Permissions
```bash
# Make scripts executable
chmod +x start.py
chmod +x wsgi.py
chmod +x app.wsgi

# Set proper permissions for web server
chmod 644 *.py
chmod 755 data/
chmod 644 data/app.db
```

## Deployment Checklist

### Pre-deployment
- [ ] Update `.env` file with production values
- [ ] Set `SECRET_KEY` to a secure random value
- [ ] Configure `BREVO_API_KEY` for email service
- [ ] Set `FLAWTRACK_API_TOKEN` for breach detection
- [ ] Ensure `data/` directory exists and is writable

### Post-deployment
- [ ] Test main routes: `/`, `/dashboard`, `/campaigns`
- [ ] Verify API endpoints: `/api/contact-stats`
- [ ] Check webhook functionality: `/webhooks/brevo`
- [ ] Test email tracking: `/track/open/1`
- [ ] Confirm database connectivity

### Troubleshooting

#### Common Issues
1. **404 errors**: Check route registration in `app.py`
2. **Database errors**: Verify `data/app.db` exists and is writable
3. **Import errors**: Check Python path in WSGI configuration
4. **Template errors**: Ensure `templates/` directory is accessible

#### Debug Mode
```bash
# Enable debug output in WSGI
python app.wsgi
# Check route listing and error details
```

#### Log Files
- Application logs: Check server error logs
- WSGI errors: `wsgi_error.log` in application directory
- Database errors: SQLite error messages in logs

## Performance Optimization

### Production Settings
- Disable Flask debug mode
- Use proper WSGI server (Gunicorn, uWSGI)
- Enable gzip compression
- Configure proper caching headers

### Database Optimization
- Regular database maintenance
- Monitor database size
- Consider PostgreSQL for high-traffic deployments

## Security Considerations

### Production Security
- Set strong `SECRET_KEY`
- Use HTTPS in production
- Secure database file permissions
- Regular security updates
- Monitor for suspicious activity

### API Security
- Rate limiting on API endpoints
- Input validation and sanitization
- Proper error handling without information disclosure

## Monitoring

### Health Checks
- Monitor application startup time
- Check database connectivity
- Verify email service integration
- Test webhook endpoints

### Key Metrics
- Response times for main routes
- Database query performance
- Email delivery rates
- API endpoint usage

## Scaling Considerations

### Horizontal Scaling
- Use external database (PostgreSQL)
- Implement Redis for caching
- Load balancer configuration
- Session management

### Background Tasks
- Configure Celery for heavy operations
- Redis for task queuing
- Separate worker processes

---

## Quick Start Commands

```bash
# Local development
python start.py

# Production testing
python wsgi.py

# Check routes
python -c "from app import create_app; app = create_app(); [print(rule) for rule in app.url_map.iter_rules()]"

# Initialize database
python init_db.py
```

All routing conflicts have been resolved and the application is ready for production deployment!