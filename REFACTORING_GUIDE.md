# Complete Refactoring Guide: Breach-Based → Industry-Based Email Marketing SaaS

## Overview

This guide provides step-by-step instructions to transform your breach-scanning email marketing platform into a clean, industry-based private SaaS service.

**Old Version:**
- Automated breach scanning via FlawTrack API
- Risk-based campaign targeting (high/medium/low risk)
- Auto-enrollment based on breach status
- Complex breach data management

**New Version:**
- Industry and business-type based targeting
- Manual campaign creation by admin
- Simple contact management
- Clean email marketing core

---

## Migration Steps

### STEP 1: Backup Everything

```bash
# Create full backup
cp -r "C:\Anas's PC\Moaz\Sales Master" "C:\Anas's PC\Moaz\Sales Master_BACKUP_$(date +%Y%m%d)"

# Backup database separately
cp "C:\Anas's PC\Moaz\Sales Master\data\app.db" "C:\Anas's PC\Moaz\Sales Master\data\app_backup_$(date +%Y%m%d).db"
```

### STEP 2: Run Database Migration

```bash
cd "C:\Anas's PC\Moaz\Sales Master"
python migrate_to_simplified_schema.py
```

This script will:
- Create automatic database backup
- Add industry-based columns to contacts and campaigns
- Remove breach-related tables (breaches, ab_tests, etc.)
- Clean up breach-related settings
- Preserve all existing contacts, campaigns, and emails

### STEP 3: Replace Database Models

```bash
# Backup old models
mv models/database.py models/database_OLD.py

# Use new simplified models
mv models/database_new.py models/database.py
```

### STEP 4: Delete Breach-Related Files

#### Services to DELETE:
```bash
rm services/flawtrack_api.py
rm services/flawtrack_monitor.py
rm services/background_scanner.py
rm services/simple_background_scanner.py
rm services/breach_email_automation.py
rm services/contact_upload_integration.py  # If it has breach scanning
```

#### Routes to DELETE:
```bash
rm routes/breach_checker.py
rm routes/flawtrack_admin.py
rm routes/scan_progress.py
rm routes/campaign_testing.py  # Has breach scan testing
```

#### Tasks to DELETE:
```bash
rm tasks/domain_scanning.py
rm -rf tasks/  # If no other tasks exist
```

#### Scripts to DELETE:
```bash
rm -rf scripts/tests/test_breach_scan.py
rm -rf scripts/utilities/add_breach_templates.py
```

#### Optional (Email Validation - Keep if you want validation):
```bash
# Delete these if you don't need email validation
rm services/zerobounce_validator.py
rm services/emaillistverify_validator.py
```

---

## Code Updates

### STEP 5: Update app.py

Remove breach-related imports and initialization:

**REMOVE these imports:**
```python
from routes.breach_checker import breach_checker_bp
from routes.flawtrack_admin import flawtrack_admin_bp
from routes.scan_progress import scan_progress_bp
from routes.campaign_testing import campaign_testing_bp
```

**REMOVE these blueprint registrations:**
```python
app.register_blueprint(breach_checker_bp)
app.register_blueprint(flawtrack_admin_bp)
app.register_blueprint(scan_progress_bp)
app.register_blueprint(campaign_testing_bp)
```

**REMOVE FlawTrack monitoring initialization:**
```python
# Remove this entire block
try:
    from services.flawtrack_monitor import start_monitoring
    monitoring_started = start_monitoring()
    ...
except Exception as e:
    ...
```

**UPDATE database imports to remove Breach:**
```python
# OLD:
from models.database import (
    db, Contact, Campaign, TemplateVariant, Breach, Email, ...
)

# NEW:
from models.database import (
    db, Contact, Campaign, TemplateVariant, Email, Response,
    EmailTemplate, EmailSequenceConfig, SequenceStep, EmailSequence,
    ContactCampaignStatus, Settings, WebhookEvent
)
```

### STEP 6: Update services/scheduler.py

Remove breach scanning and FlawTrack tasks:

**REMOVE these functions:**
```python
def _run_background_scanning():
    ...

def _cleanup_stuck_scans():
    ...
```

**REMOVE these scheduled jobs:**
```python
# Remove
scheduler.add_job(
    func=_run_background_scanning,
    ...
)

scheduler.add_job(
    func=_cleanup_stuck_scans,
    ...
)
```

**KEEP these jobs:**
- `_run_auto_enrollment()` - For industry-based auto-enrollment
- `_process_scheduled_emails()` - Email sending
- `_check_for_replies()` - Reply detection

### STEP 7: Update services/auto_enrollment.py

Remove breach status checking:

**FIND this code:**
```python
# Check breach status
if campaign.auto_enroll_breach_status:
    query = query.filter(Contact.breach_status == campaign.auto_enroll_breach_status)
```

**REPLACE with industry filtering:**
```python
# Filter by target industries
if campaign.target_industries:
    query = query.filter(Contact.industry.in_(campaign.target_industries))

# Filter by business types
if campaign.target_business_types:
    query = query.filter(Contact.business_type.in_(campaign.target_business_types))

# Filter by company sizes
if campaign.target_company_sizes:
    query = query.filter(Contact.company_size.in_(campaign.target_company_sizes))
```

### STEP 8: Update services/email_sequence_service.py

Remove FlawTrack breach checking:

**REMOVE this function:**
```python
def check_contact_breach_status(contact):
    """Check FlawTrack for breach data"""
    # Remove entire function
```

**REMOVE FlawTrack imports:**
```python
from services.flawtrack_api import FlawTrackAPI
```

**UPDATE enroll_contact_in_campaign():**

**REMOVE:**
```python
# Check breach status
breach_data = check_contact_breach_status(contact)
template_type = 'breached' if breach_data else 'proactive'
```

**REPLACE with:**
```python
# No breach checking needed - all templates are standard
```

**UPDATE schedule_email_sequence():**

**REMOVE template_type parameter:**
```python
# OLD
def schedule_email_sequence(contact_id, campaign_id, template_type='proactive'):

# NEW
def schedule_email_sequence(contact_id, campaign_id):
```

**REMOVE template_type from EmailSequence creation:**
```python
# OLD
email_seq = EmailSequence(
    contact_id=contact_id,
    campaign_id=campaign_id,
    sequence_step=step_num,
    template_type=template_type,  # REMOVE THIS
    scheduled_datetime=scheduled_time,
    status='scheduled'
)

# NEW
email_seq = EmailSequence(
    contact_id=contact_id,
    campaign_id=campaign_id,
    sequence_step=step_num,
    scheduled_datetime=scheduled_time,
    status='scheduled'
)
```

### STEP 9: Update services/email_processor.py

Remove breach data substitution:

**FIND this code:**
```python
# Add breach data if template requires it
if '{{breach_' in template_content or '{{risk_score}}' in template_content:
    breach_data = get_breach_data_for_contact(contact)
    variables.update(breach_data)
```

**REMOVE the entire block above**

**UPDATE substitute_variables() to use only these variables:**
```python
def substitute_variables(template_content, contact, campaign):
    """Substitute template variables with contact data"""
    variables = {
        '{{first_name}}': contact.first_name or '',
        '{{last_name}}': contact.last_name or '',
        '{{company}}': contact.company or '',
        '{{domain}}': contact.domain or '',
        '{{email}}': contact.email or '',
        '{{title}}': contact.title or '',
        '{{industry}}': contact.industry or '',
        '{{business_type}}': contact.business_type or '',
        '{{company_size}}': contact.company_size or '',
        '{{campaign_name}}': campaign.name or '',
        '{{sender_name}}': campaign.sender_name or 'Our Team'
    }

    for var, value in variables.items():
        template_content = template_content.replace(var, str(value))

    return template_content
```

### STEP 10: Update routes/contacts.py

Remove breach analysis and scanning:

**REMOVE these routes:**
```python
@contacts_bp.route('/contacts/breach-analysis', ...)
def breach_analysis():
    ...

@contacts_bp.route('/contacts/scan-domains', ...)
def scan_domains():
    ...
```

**UPDATE /contacts/upload/csv route:**

**REMOVE breach scanning code:**
```python
# REMOVE
from services.background_scanner import start_background_scan
...
# Start breach scan
task_id = start_background_scan(unique_domains)
```

**REMOVE FlawTrack API calls**

### STEP 11: Update routes/campaigns.py

Remove breach/risk targeting:

**UPDATE campaign creation form processing:**

**OLD:**
```python
# Get risk-based targeting
target_risk_levels = request.form.getlist('target_risk_levels')
campaign.target_risk_levels = target_risk_levels
```

**NEW:**
```python
# Get industry-based targeting
import json
target_industries = request.form.getlist('target_industries')
target_business_types = request.form.getlist('target_business_types')
target_company_sizes = request.form.getlist('target_company_sizes')

campaign.target_industries = json.dumps(target_industries) if target_industries else '[]'
campaign.target_business_types = json.dumps(target_business_types) if target_business_types else '[]'
campaign.target_company_sizes = json.dumps(target_company_sizes) if target_company_sizes else '[]'
```

**REMOVE auto-enrollment breach checking:**
```python
# OLD
campaign.auto_enroll_breach_status = request.form.get('auto_enroll_breach_status')

# REMOVE - no longer needed
```

### STEP 12: Update routes/templates.py

Remove breach template types and variables:

**UPDATE template creation:**

**REMOVE:**
```python
breach_template_type = request.form.get('breach_template_type')  # 'breached' or 'proactive'
risk_level = request.form.get('risk_level')  # high, medium, low
template.risk_level = risk_level
template.breach_template_type = breach_template_type
```

**ADD:**
```python
category = request.form.get('category')  # Sales Outreach, Partnership, etc.
target_industry = request.form.get('target_industry', '')  # Optional
template.category = category
template.target_industry = target_industry
```

**UPDATE available_variables:**
```python
# NEW list without breach variables
available_variables = [
    "{{first_name}}",
    "{{last_name}}",
    "{{company}}",
    "{{domain}}",
    "{{email}}",
    "{{title}}",
    "{{industry}}",
    "{{business_type}}",
    "{{company_size}}",
    "{{campaign_name}}",
    "{{sender_name}}"
]
template.available_variables = json.dumps(available_variables)
```

### STEP 13: Update routes/dashboard.py

Remove breach analytics:

**REMOVE these stats:**
```python
# Remove
breached_contacts = Contact.query.filter(Contact.breach_status == 'breached').count()
stats['breached_contacts'] = breached_contacts
```

**ADD industry stats:**
```python
# Get top industries
from sqlalchemy import func
top_industries = db.session.query(
    Contact.industry,
    func.count(Contact.id).label('count')
).filter(
    Contact.industry.isnot(None)
).group_by(
    Contact.industry
).order_by(
    func.count(Contact.id).desc()
).limit(5).all()

stats['top_industries'] = [
    {'industry': industry, 'count': count}
    for industry, count in top_industries
]
```

### STEP 14: Update routes/webhooks.py

No changes needed - webhook handling is independent of breach features.

### STEP 15: Update routes/api.py

**REMOVE these endpoints:**
```python
@api_bp.route('/api/breach-lookup/<domain>', ...)
@api_bp.route('/api/breach-analysis/scan-domains', ...)
@api_bp.route('/api/breach-analysis/domains', ...)
@api_bp.route('/api/flawtrack/status', ...)
@api_bp.route('/api/flawtrack/test-connection', ...)
```

### STEP 16: Clean Up Celery (Optional)

If you're not using Celery for anything else:

```bash
rm celery_app.py
rm start_celery_worker.py
```

**Update requirements.txt:**
```bash
# REMOVE these lines:
celery==5.3.4
redis==5.0.1
flower==2.0.1
```

---

## Frontend Updates

### STEP 17: Update Templates

#### templates/dashboard.html

**REMOVE breach metrics:**
```html
<!-- REMOVE -->
<div class="stat-card">
    <h3>Breached Contacts</h3>
    <div class="stat-number">{{ stats.breached_contacts }}</div>
</div>
```

**ADD industry metrics:**
```html
<div class="stat-card">
    <h3>Top Industries</h3>
    <ul>
        {% for industry in stats.top_industries %}
        <li>{{ industry.industry }}: {{ industry.count }}</li>
        {% endfor %}
    </ul>
</div>
```

#### templates/contacts.html

**REMOVE breach status column:**
```html
<!-- REMOVE -->
<th>Breach Status</th>
...
<td>{{ contact.breach_status }}</td>
```

**ADD industry columns:**
```html
<th>Industry</th>
<th>Business Type</th>
<th>Company Size</th>
...
<td>{{ contact.industry or 'N/A' }}</td>
<td>{{ contact.business_type or 'N/A' }}</td>
<td>{{ contact.company_size or 'N/A' }}</td>
```

**REMOVE breach analysis button:**
```html
<!-- REMOVE -->
<a href="/contacts/breach-analysis" class="btn btn-secondary">
    Breach Analysis
</a>
```

#### templates/new_campaign.html

**REMOVE risk-based targeting:**
```html
<!-- REMOVE -->
<label>Target Risk Levels:</label>
<select name="target_risk_levels" multiple>
    <option value="high">High Risk</option>
    <option value="medium">Medium Risk</option>
    <option value="low">Low Risk</option>
</select>
```

**ADD industry-based targeting:**
```html
<div class="form-group">
    <label>Target Industries:</label>
    <select name="target_industries" multiple class="form-control">
        <option value="Healthcare">Healthcare</option>
        <option value="Finance">Finance</option>
        <option value="Retail">Retail</option>
        <option value="Technology">Technology</option>
        <option value="Manufacturing">Manufacturing</option>
        <option value="Education">Education</option>
        <option value="Real Estate">Real Estate</option>
        <option value="Hospitality">Hospitality</option>
        <option value="Other">Other</option>
    </select>
</div>

<div class="form-group">
    <label>Target Business Types:</label>
    <select name="target_business_types" multiple class="form-control">
        <option value="B2B">B2B</option>
        <option value="B2C">B2C</option>
        <option value="Enterprise">Enterprise</option>
        <option value="SMB">Small & Medium Business</option>
    </select>
</div>

<div class="form-group">
    <label>Target Company Sizes:</label>
    <select name="target_company_sizes" multiple class="form-control">
        <option value="1-10">1-10 employees</option>
        <option value="11-50">11-50 employees</option>
        <option value="51-200">51-200 employees</option>
        <option value="201-1000">201-1000 employees</option>
        <option value="1000+">1000+ employees</option>
    </select>
</div>
```

**REMOVE auto-enrollment breach settings:**
```html
<!-- REMOVE -->
<label>Auto-Enroll Breach Status:</label>
<select name="auto_enroll_breach_status">
    <option value="">All</option>
    <option value="breached">Breached Only</option>
    <option value="not_breached">Not Breached</option>
</select>
```

#### templates/upload.html

**REMOVE breach scanning UI:**
```html
<!-- REMOVE -->
<div id="scan-progress" style="display:none;">
    <h3>Scanning Domains for Breaches...</h3>
    <div class="progress-bar"></div>
</div>
```

**UPDATE CSV format guidance:**
```html
<div class="csv-format">
    <h4>CSV Format:</h4>
    <ul>
        <li>email (required)</li>
        <li>first_name</li>
        <li>last_name</li>
        <li>company</li>
        <li>title</li>
        <li>phone</li>
        <li>industry (recommended)</li>
        <li>business_type (recommended)</li>
        <li>company_size (recommended)</li>
    </ul>
</div>
```

#### templates/template_editor.html

**REMOVE breach template type selection:**
```html
<!-- REMOVE -->
<label>Breach Template Type:</label>
<select name="breach_template_type">
    <option value="breached">Breached</option>
    <option value="proactive">Proactive</option>
</select>

<label>Risk Level:</label>
<select name="risk_level">
    <option value="high">High</option>
    <option value="medium">Medium</option>
    <option value="low">Low</option>
</select>
```

**ADD template categorization:**
```html
<div class="form-group">
    <label>Template Category:</label>
    <select name="category" class="form-control">
        <option value="Sales Outreach">Sales Outreach</option>
        <option value="Partnership">Partnership</option>
        <option value="Product Launch">Product Launch</option>
        <option value="Event Invitation">Event Invitation</option>
        <option value="Follow-up">Follow-up</option>
        <option value="General">General</option>
    </select>
</div>

<div class="form-group">
    <label>Target Industry (Optional):</label>
    <select name="target_industry" class="form-control">
        <option value="">All Industries</option>
        <option value="Healthcare">Healthcare</option>
        <option value="Finance">Finance</option>
        <option value="Retail">Retail</option>
        <option value="Technology">Technology</option>
        <option value="Manufacturing">Manufacturing</option>
    </select>
</div>
```

**UPDATE available variables list:**
```html
<div class="variables-help">
    <h4>Available Variables:</h4>
    <ul>
        <li>{{first_name}} - Contact's first name</li>
        <li>{{last_name}} - Contact's last name</li>
        <li>{{company}} - Company name</li>
        <li>{{domain}} - Company domain</li>
        <li>{{email}} - Contact email</li>
        <li>{{title}} - Job title</li>
        <li>{{industry}} - Industry</li>
        <li>{{business_type}} - Business type (B2B, B2C, etc.)</li>
        <li>{{company_size}} - Company size</li>
        <li>{{campaign_name}} - Campaign name</li>
        <li>{{sender_name}} - Sender name</li>
    </ul>
</div>
```

#### templates/settings.html

**REMOVE FlawTrack API settings:**
```html
<!-- REMOVE entire FlawTrack section -->
<div class="settings-section">
    <h3>FlawTrack API Configuration</h3>
    ...
</div>
```

**SIMPLIFY to only show:**
- Brevo API settings (email sending)
- IMAP settings (reply detection)
- General application settings

#### Delete these template files:
```bash
rm templates/breach_analysis.html
rm templates/breach_checker.html
rm templates/campaign_testing.html  # If exists
```

---

## Environment Variables

### STEP 18: Update env file

**REMOVE these variables:**
```bash
FLAWTRACK_API_TOKEN=...
FLAWTRACK_API_ENDPOINT=...
FLAWTRACK_SCANNING_ENABLED=...
ZEROBOUNCE_API_KEY=...
EMAILLISTVERIFY_API_KEY=...
```

**KEEP these variables:**
```bash
# Flask Configuration
SECRET_KEY=your-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-password

# Brevo Email Service
BREVO_API_KEY=your-brevo-api-key
SENDER_EMAIL=your-email@domain.com
SENDER_NAME=Your Name

# IMAP Reply Detection (Optional)
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=your-email@gmail.com
IMAP_PASSWORD=your-app-password

# Database
SQLALCHEMY_DATABASE_URI=sqlite:///data/app.db

# Session
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Strict
PERMANENT_SESSION_LIFETIME=86400
```

---

## Testing Checklist

### STEP 19: Test All Features

After completing the refactoring:

#### 1. Database & Models
- [ ] App starts without errors
- [ ] Database tables created correctly
- [ ] No breach-related tables exist
- [ ] Industry fields exist in contacts table
- [ ] Campaign targeting fields exist

#### 2. Contact Management
- [ ] Upload CSV with industry/business_type fields
- [ ] Create contacts manually
- [ ] Edit contact with industry information
- [ ] Search and filter contacts
- [ ] No breach status shown
- [ ] Delete contacts

#### 3. Campaign Management
- [ ] Create new campaign with industry targeting
- [ ] Select target industries
- [ ] Select target business types
- [ ] Select target company sizes
- [ ] Add contacts to campaign manually
- [ ] Auto-enrollment works (if enabled)
- [ ] Edit campaign settings
- [ ] Pause/resume campaign
- [ ] No risk/breach options shown

#### 4. Email Templates
- [ ] Create new template with category
- [ ] Use industry variables ({{industry}}, {{business_type}})
- [ ] Preview template with real data
- [ ] Edit template
- [ ] Delete template
- [ ] No breach variables shown

#### 5. Email Sending
- [ ] Scheduled emails are sent
- [ ] Variables are replaced correctly
- [ ] No breach data in emails
- [ ] Follow-up sequence works
- [ ] Reply stops sequence

#### 6. Dashboard
- [ ] Dashboard loads without errors
- [ ] Shows campaign statistics
- [ ] Shows industry distribution
- [ ] No breach metrics shown
- [ ] Hot prospects displayed

#### 7. Analytics
- [ ] Email analytics work
- [ ] Webhook events processed
- [ ] Open/click tracking works
- [ ] Response tracking works

#### 8. Settings
- [ ] Brevo API configuration works
- [ ] IMAP configuration works (if used)
- [ ] Test email sending works
- [ ] No FlawTrack settings shown

---

## File Deletion Summary

### Files to DELETE:

```
services/flawtrack_api.py
services/flawtrack_monitor.py
services/background_scanner.py
services/simple_background_scanner.py
services/breach_email_automation.py
services/zerobounce_validator.py (optional)
services/emaillistverify_validator.py (optional)
services/contact_upload_integration.py (if breach-related)

routes/breach_checker.py
routes/flawtrack_admin.py
routes/scan_progress.py
routes/campaign_testing.py

tasks/domain_scanning.py
tasks/__init__.py (if empty)

templates/breach_analysis.html
templates/breach_checker.html
templates/campaign_testing.html

scripts/tests/test_breach_scan.py
scripts/utilities/add_breach_templates.py

celery_app.py (if not using Celery)
start_celery_worker.py (if not using Celery)

models/database_OLD.py (after migration complete)
```

### Files to KEEP and UPDATE:

```
app.py - Remove breach blueprints
models/database.py - Use new simplified schema

services/scheduler.py - Remove scanning jobs
services/auto_enrollment.py - Use industry filtering
services/email_sequence_service.py - Remove breach checking
services/email_processor.py - Remove breach variables
services/email_service.py - Keep as is
services/brevo_modern_service.py - Keep as is
services/reply_detection_service.py - Keep as is
services/webhook_analytics.py - Keep as is

routes/dashboard.py - Update stats
routes/contacts.py - Remove breach routes
routes/campaigns.py - Update targeting
routes/templates.py - Update variables
routes/webhooks.py - Keep as is
routes/api.py - Remove breach endpoints

All other templates - Update UI
```

---

## New Features Available

After refactoring, your system will have:

### 1. Industry-Based Targeting
- Target campaigns by industry (Healthcare, Finance, etc.)
- Target by business type (B2B, B2C, Enterprise, SMB)
- Target by company size (1-10, 11-50, 51-200, 201-1000, 1000+)

### 2. Clean Contact Management
- Simple CSV upload
- Industry categorization
- Business type classification
- Company size tracking

### 3. Flexible Campaign Management
- Create campaigns for specific industries
- Manual contact assignment
- Optional auto-enrollment by industry
- Multiple targeting criteria

### 4. Template Categorization
- Templates by category (Sales, Partnership, etc.)
- Industry-specific templates
- Clean variable substitution
- No breach-related complexity

### 5. Core Email Marketing
- Email sequences and follow-ups
- Open/click tracking
- Reply detection
- Response analytics
- Hot prospect identification

---

## Support

If you encounter issues during migration:

1. **Database errors**: Restore from backup in `data/backups/`
2. **Import errors**: Check all breach-related imports are removed
3. **Template errors**: Ensure all breach variables are removed from templates
4. **Missing features**: Core email marketing features remain unchanged

---

## Post-Migration Cleanup

After successful migration and testing:

```bash
# Remove old database model
rm models/database_OLD.py

# Remove migration script (keep for reference if needed)
# rm migrate_to_simplified_schema.py

# Remove this guide (or keep for reference)
# rm REFACTORING_GUIDE.md

# Clean up old backups (after confirming everything works)
# rm -rf data/backups/app_before_migration_*
```

---

## Summary

Your refactored system will be:
- **Simpler**: No complex breach scanning
- **Faster**: No API rate limits or scanning delays
- **Cleaner**: Industry-based targeting is intuitive
- **Focused**: Pure email marketing without security complexity
- **Maintainable**: Fewer dependencies and moving parts

The core email marketing functionality (campaigns, sequences, tracking, analytics) remains fully intact and operational.
