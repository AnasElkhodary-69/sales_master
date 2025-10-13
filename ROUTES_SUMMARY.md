# SalesBreachPro Routes Summary

## Blueprint Organization

### Core Application Routes
| Blueprint | Prefix | Description |
|-----------|--------|-------------|
| `auth_bp` | None | Authentication routes |
| `dashboard_bp` | None | Dashboard and settings |

### Feature-Specific Routes
| Blueprint | Prefix | Description |
|-----------|--------|-------------|
| `campaigns_bp` | `/campaigns` | Campaign management |
| `contacts_bp` | `/contacts` | Contact management |
| `templates_bp` | `/templates` | Email template management |
| `sequences_bp` | None | Admin sequence management |
| `analytics_bp` | `/analytics` | Analytics and reporting |
| `tracking_bp` | None | Email tracking and unsubscribe |

### API Routes
| Blueprint | Prefix | Description |
|-----------|--------|-------------|
| `api_bp` | `/api` | Main API endpoints |
| `scan_progress_bp` | `/api/scan` | Domain scanning API |
| `webhooks_bp` | `/webhooks` | Webhook handlers |
| `email_trigger_bp` | None | Email trigger API |

## Route Mapping

### Authentication (`auth_bp`)
- `GET /` → Redirect to dashboard
- `GET /login` → Login page
- `POST /login` → Process login
- `GET /logout` → Logout

### Dashboard (`dashboard_bp`)
- `GET /dashboard` → Main dashboard
- `GET /enhanced` → Enhanced dashboard
- `GET /settings` → Settings page
- `GET /analytics` → Analytics overview
- `GET /test-email` → Email testing

### Campaigns (`campaigns_bp` - `/campaigns`)
- `GET /` → Campaign list
- `GET /new` → New campaign form
- `POST /new` → Create campaign
- `GET /<id>` → Campaign details
- `GET /<id>/edit` → Edit campaign
- `POST /<id>/edit` → Update campaign
- `POST /<id>/toggle` → Toggle campaign status
- `POST /<id>/delete` → Delete campaign

### Contacts (`contacts_bp` - `/contacts`)
- `GET /` → Contact list
- `GET /upload` → Upload contacts page
- `POST /upload/csv` → Process CSV upload
- `GET /breach-analysis` → Breach analysis page
- `GET /leads` → Leads management
- `GET /emails/<status>` → Email status view

### Templates (`templates_bp` - `/templates`)
- `GET /` → Template list
- `GET /create` → Create template form
- `POST /create` → Save new template
- `GET /<id>/edit` → Edit template
- `POST /<id>/edit` → Update template
- `GET /<id>/preview` → Preview template
- `POST /<id>/delete` → Delete template

### Sequences (`sequences_bp`)
- `GET /admin/sequences` → Sequence management
- `GET /admin/sequences/new` → New sequence form
- `GET /admin/templates` → Template management
- `GET /admin/templates/new` → New template form

### API Endpoints (`api_bp` - `/api`)
- `GET /template/<id>` → Get template data
- `GET /contacts/<id>` → Get contact data
- `PUT /contacts/<id>` → Update contact
- `DELETE /contacts/<id>` → Delete contact
- `GET /breach-lookup/<domain>` → Domain breach lookup
- `GET /contact-stats` → Contact statistics
- `POST /campaigns/auto-enroll` → Auto-enroll contacts

### Tracking (`tracking_bp`)
- `GET /track/open/<email_id>` → Track email open
- `GET /track/click/<email_id>/<url>` → Track link click
- `GET /unsubscribe/<contact_id>` → Unsubscribe page

### Webhooks (`webhooks_bp` - `/webhooks`)
- `POST /brevo` → Brevo webhook handler

## Deployment Notes

### URL Structure for Production
All routes are designed to work with or without a subdirectory prefix.

### Error Handling
- 404 errors show custom error page
- 500 errors roll back database and show error page

### Security Considerations
- All POST routes should be protected with CSRF tokens
- Authentication required for admin routes
- Rate limiting on API endpoints

### Legacy Route Support
Some old-style routes are maintained for backward compatibility but will be deprecated in future versions.