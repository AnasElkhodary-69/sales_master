"""
FlawTrack Administration Routes
Comprehensive management interface for FlawTrack API configuration and monitoring
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from utils.decorators import login_required
from utils.flawtrack_config import (
    get_flawtrack_api, get_api_config, validate_configuration,
    is_api_configured
)
from services.flawtrack_monitor import get_monitor, perform_health_check
from models.database import db, Contact, Breach
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

# Create FlawTrack admin blueprint
flawtrack_admin_bp = Blueprint('flawtrack_admin', __name__, url_prefix='/admin/flawtrack')

@flawtrack_admin_bp.route('/')
@login_required
def index():
    """FlawTrack management dashboard"""
    try:
        # Get current configuration
        config = get_api_config()
        validation = validate_configuration()

        # Get monitoring info
        monitor = get_monitor()
        monitor_info = monitor.get_monitoring_info()

        # Get recent health status
        current_status = monitor.get_current_status()

        # Get availability stats
        availability_stats = monitor.get_availability_stats(24)

        # Get scan statistics from database
        scan_stats = get_scan_statistics()

        return render_template('admin/flawtrack_management.html',
                             config=config,
                             validation=validation,
                             monitor_info=monitor_info,
                             current_status=current_status,
                             availability_stats=availability_stats,
                             scan_stats=scan_stats)

    except Exception as e:
        logger.error(f"Error loading FlawTrack management page: {str(e)}")
        flash(f'Error loading FlawTrack management: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))

@flawtrack_admin_bp.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    """FlawTrack configuration management"""
    if request.method == 'POST':
        try:
            action = request.json.get('action')

            if action == 'update_settings':
                # Update environment settings (this would typically write to .env file)
                settings = request.json.get('settings', {})

                # For now, just update runtime environment
                for key, value in settings.items():
                    if key.startswith('FLAWTRACK_'):
                        os.environ[key] = str(value)

                return jsonify({
                    'success': True,
                    'message': 'Settings updated successfully (restart required for full effect)'
                })

            else:
                return jsonify({
                    'success': False,
                    'error': 'Unknown action'
                })

        except Exception as e:
            logger.error(f"Config update error: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            })

    # GET request - return current config
    config = get_api_config()
    validation = validate_configuration()

    return jsonify({
        'success': True,
        'config': config,
        'validation': validation
    })

@flawtrack_admin_bp.route('/scan-manager')
@login_required
def scan_manager():
    """Advanced scan management interface"""
    try:
        # Get pending domains (domains without recent scan results)
        pending_domains = get_pending_domains()

        # Get recent scan results
        recent_scans = get_recent_scans()

        # Get failed scans that need retry
        failed_scans = get_failed_scans()

        return render_template('admin/flawtrack_scan_manager.html',
                             pending_domains=pending_domains,
                             recent_scans=recent_scans,
                             failed_scans=failed_scans)

    except Exception as e:
        logger.error(f"Error loading scan manager: {str(e)}")
        flash(f'Error loading scan manager: {str(e)}', 'error')
        return redirect(url_for('flawtrack_admin.index'))

@flawtrack_admin_bp.route('/start-scan', methods=['POST'])
@login_required
def start_scan():
    """Start a new FlawTrack scan"""
    try:
        data = request.get_json()
        domains = data.get('domains', [])
        scan_type = data.get('scan_type', 'domain')
        data_source = data.get('data_source', 'unified')

        if not domains:
            return jsonify({
                'success': False,
                'error': 'No domains provided'
            })

        # Get FlawTrack API instance
        api = get_flawtrack_api()
        if not api:
            return jsonify({
                'success': False,
                'error': 'FlawTrack API not configured'
            })

        # Start background scan task
        from services.background_scanner import get_simple_scanner
        scanner = get_simple_scanner()

        # Prepare domains for scanning
        domain_contacts = {}
        for domain in domains:
            contacts = Contact.query.filter_by(domain=domain).all()
            domain_contacts[domain] = [contact.id for contact in contacts]

        task_id = scanner.start_scan(
            domains=set(domains),
            domain_to_contacts=domain_contacts,
            scan_options={
                'search_type': scan_type,
                'data_source': data_source
            }
        )

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'Started scanning {len(domains)} domains',
            'scan_type': scan_type,
            'data_source': data_source
        })

    except Exception as e:
        logger.error(f"Error starting scan: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@flawtrack_admin_bp.route('/scan-results')
@login_required
def scan_results():
    """Get scan results with pagination and filtering - HTML page or JSON API"""
    try:
        # Check if this is an AJAX request (JSON expected)
        is_json_request = request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json'

        if not is_json_request:
            # Return HTML page with summary statistics for initial load
            stats = get_scan_statistics()
            return render_template('admin/scan_results.html',
                                 total_results=stats['scanned_domains'],
                                 breached_count=stats['breached_count'],
                                 clean_count=stats['not_breached_count'],
                                 unknown_count=stats['unknown_count'])

        # JSON API for AJAX requests
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status_filter = request.args.get('status')  # 'breached', 'not_breached', 'unknown'
        domain_filter = request.args.get('domain', '')

        # Build query
        query = db.session.query(Breach).order_by(Breach.last_updated.desc())

        if status_filter and status_filter != 'all':
            query = query.filter(Breach.breach_status == status_filter)

        if domain_filter:
            query = query.filter(Breach.domain.ilike(f'%{domain_filter}%'))

        # Apply pagination
        results = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        # Format results
        scan_results = []
        for breach in results.items:
            # Get contact count for this domain
            contact_count = Contact.query.filter_by(domain=breach.domain).count()

            scan_results.append({
                'domain': breach.domain,
                'breach_status': breach.breach_status,
                'records_affected': breach.records_affected or 0,
                'breach_year': breach.breach_year,
                'risk_score': breach.risk_score or 0,
                'last_updated': breach.last_updated.isoformat() if breach.last_updated else None,
                'scan_status': breach.scan_status,
                'scan_error': breach.scan_error,
                'contact_count': contact_count
            })

        return jsonify({
            'success': True,
            'results': scan_results,
            'pagination': {
                'page': page,
                'pages': results.pages,
                'per_page': per_page,
                'total': results.total,
                'has_next': results.has_next,
                'has_prev': results.has_prev
            }
        })

    except Exception as e:
        logger.error(f"Error getting scan results: {str(e)}")
        if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
            return jsonify({
                'success': False,
                'error': str(e)
            })
        else:
            flash(f'Error loading scan results: {str(e)}', 'error')
            return redirect(url_for('flawtrack_admin.index'))

@flawtrack_admin_bp.route('/export-results')
@login_required
def export_results():
    """Export scan results to CSV"""
    try:
        import csv
        import io
        from flask import make_response

        status_filter = request.args.get('status')

        # Get all results (no pagination for export)
        query = db.session.query(Breach)
        if status_filter:
            query = query.filter(Breach.breach_status == status_filter)

        results = query.all()

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Domain', 'Breach Status', 'Records Affected', 'Breach Year',
            'Risk Score', 'Last Updated', 'Scan Status', 'Scan Error', 'Contact Count'
        ])

        # Write data
        for breach in results:
            contact_count = Contact.query.filter_by(domain=breach.domain).count()
            writer.writerow([
                breach.domain,
                breach.breach_status,
                breach.records_affected or 0,
                breach.breach_year or '',
                breach.risk_score or 0,
                breach.last_updated.isoformat() if breach.last_updated else '',
                breach.scan_status or '',
                breach.scan_error or '',
                contact_count
            ])

        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=flawtrack_results_{status_filter or "all"}.csv'

        return response

    except Exception as e:
        logger.error(f"Error exporting results: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Helper functions
def get_scan_statistics():
    """Get comprehensive scan statistics"""
    try:
        total_domains = db.session.query(Contact.domain).filter(
            Contact.domain.isnot(None)
        ).distinct().count()

        total_breaches = Breach.query.count()

        breached_count = Breach.query.filter(
            Breach.breach_status == 'breached'
        ).count()

        not_breached_count = Breach.query.filter(
            Breach.breach_status == 'not_breached'
        ).count()

        unknown_count = Breach.query.filter(
            Breach.breach_status == 'unknown'
        ).count()

        failed_scans = Breach.query.filter(
            Breach.scan_status == 'failed'
        ).count()

        return {
            'total_domains': total_domains,
            'scanned_domains': total_breaches,
            'pending_domains': total_domains - total_breaches,
            'breached_count': breached_count,
            'not_breached_count': not_breached_count,
            'unknown_count': unknown_count,
            'failed_scans': failed_scans,
            'scan_coverage': round((total_breaches / max(total_domains, 1)) * 100, 1),
            'breach_rate': round((breached_count / max(total_breaches, 1)) * 100, 1)
        }

    except Exception as e:
        logger.error(f"Error getting scan statistics: {str(e)}")
        return {
            'total_domains': 0,
            'scanned_domains': 0,
            'pending_domains': 0,
            'breached_count': 0,
            'not_breached_count': 0,
            'unknown_count': 0,
            'failed_scans': 0,
            'scan_coverage': 0,
            'breach_rate': 0
        }

def get_pending_domains(limit=100):
    """Get domains that haven't been scanned recently"""
    try:
        # Get all unique domains from contacts
        contact_domains = db.session.query(Contact.domain).filter(
            Contact.domain.isnot(None)
        ).distinct().all()

        # Get domains that have been scanned
        scanned_domains = db.session.query(Breach.domain).distinct().all()
        scanned_domain_set = {d[0] for d in scanned_domains}

        # Find pending domains
        pending = []
        for domain_tuple in contact_domains:
            domain = domain_tuple[0]
            if domain not in scanned_domain_set:
                contact_count = Contact.query.filter_by(domain=domain).count()
                pending.append({
                    'domain': domain,
                    'contact_count': contact_count
                })

        return pending[:limit]

    except Exception as e:
        logger.error(f"Error getting pending domains: {str(e)}")
        return []

def get_recent_scans(limit=50):
    """Get recent scan results"""
    try:
        results = Breach.query.order_by(
            Breach.last_updated.desc()
        ).limit(limit).all()

        recent_scans = []
        for breach in results:
            recent_scans.append({
                'domain': breach.domain,
                'breach_status': breach.breach_status,
                'records_affected': breach.records_affected or 0,
                'last_updated': breach.last_updated.isoformat() if breach.last_updated else None,
                'scan_status': breach.scan_status
            })

        return recent_scans

    except Exception as e:
        logger.error(f"Error getting recent scans: {str(e)}")
        return []

def get_failed_scans(limit=50):
    """Get failed scans that need retry"""
    try:
        results = Breach.query.filter(
            Breach.scan_status == 'failed'
        ).order_by(
            Breach.last_updated.desc()
        ).limit(limit).all()

        failed_scans = []
        for breach in results:
            failed_scans.append({
                'domain': breach.domain,
                'scan_error': breach.scan_error,
                'last_updated': breach.last_updated.isoformat() if breach.last_updated else None,
                'scan_attempts': getattr(breach, 'scan_attempts', 0)
            })

        return failed_scans

    except Exception as e:
        logger.error(f"Error getting failed scans: {str(e)}")
        return []

@flawtrack_admin_bp.route('/search', methods=['POST'])
@login_required
def search():
    """Search for company/domain breach data using FlawTrack API"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        source = data.get('source', 'unified')

        if not query:
            return jsonify({
                'success': False,
                'error': 'Query parameter is required'
            })

        # Get FlawTrack API instance
        api = get_flawtrack_api()
        if not api:
            return jsonify({
                'success': False,
                'error': 'FlawTrack API not configured'
            })

        # Determine if query is email or domain
        is_email = '@' in query
        search_query = query.lower()

        # Prepare search parameters based on the new API
        search_params = {
            'search_type': 'service' if is_email else 'domain',
            'data_source': source
        }

        # For email, extract domain for domain search
        if is_email:
            domain = query.split('@')[1]
            raw_data = api.get_breach_data(domain, search_params['search_type'])
        else:
            # Direct domain search
            raw_data = api.get_breach_data(query, search_params['search_type'])

        # Process and format results
        formatted_results = []
        target_domain = domain if is_email else query

        if raw_data is not None:
            # Process the raw data using the API's built-in processor
            risk_score = api.calculate_risk_score(raw_data) if raw_data else 0.0
            processed_data = api.process_breach_data(target_domain, raw_data, risk_score)

            # Check if there's any breach data
            if raw_data and len(raw_data) > 0:
                # Create a comprehensive result object
                result = {
                    'domain': target_domain,
                    'email': query if is_email else None,
                    'breach_status': processed_data.get('breach_status', 'breached'),
                    'records_affected': processed_data.get('records_affected', len(raw_data)),
                    'breach_year': processed_data.get('breach_year'),
                    'breach_name': processed_data.get('breach_name', f'Credential breach ({len(raw_data)} records)'),
                    'risk_score': processed_data.get('risk_score', risk_score),
                    'severity': processed_data.get('severity', api.get_severity_category(risk_score)),
                    'data_types': processed_data.get('data_types', 'Email addresses, passwords'),
                    'breach_details': f'Found {len(raw_data)} compromised credentials in FlawTrack database',
                    'recommendations': 'Immediately change passwords for affected accounts and enable 2FA',
                    'last_updated': datetime.now().isoformat(),
                    'data_source': source.title(),
                    'raw_records': raw_data  # Include ALL raw records for detailed view
                }

                # Extract additional details from raw data
                if raw_data:
                    services = set()
                    sources = set()

                    for record in raw_data:
                        # Extract service names
                        service = (record.get('service_name') or
                                 record.get('url') or
                                 record.get('host') or '')
                        if service:
                            services.add(service)

                        # Extract sources
                        source_info = record.get('source')
                        if source_info:
                            sources.add(source_info)

                    if services:
                        result['breach_details'] += f'. Affected services: {", ".join(list(services)[:3])}'
                    if sources:
                        result['data_source'] += f' (Sources: {", ".join(list(sources)[:2])})'

                formatted_results.append(result)
            else:
                # No breach data found
                result = {
                    'domain': target_domain,
                    'email': query if is_email else None,
                    'breach_status': 'not_breached',
                    'records_affected': 0,
                    'breach_year': None,
                    'breach_name': None,
                    'risk_score': 0,
                    'severity': 'Low',
                    'data_types': 'None detected',
                    'breach_details': 'No breach data found in FlawTrack security databases',
                    'recommendations': 'Continue monitoring for security threats and maintain good password practices',
                    'last_updated': datetime.now().isoformat(),
                    'data_source': source.title()
                }
                formatted_results.append(result)

        else:
            # API call failed or returned None
            return jsonify({
                'success': False,
                'error': 'FlawTrack API call failed or returned no data. Check API configuration and connectivity.'
            })

        # Cache the results in our database for future reference
        if formatted_results:
            try:
                api.cache_breach_data(
                    target_domain,
                    formatted_results[0]
                )
            except Exception as cache_error:
                logger.warning(f"Failed to cache search results: {cache_error}")

        return jsonify({
            'success': True,
            'results': formatted_results,
            'query': query,
            'search_type': 'email' if is_email else 'domain',
            'source': source,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error performing FlawTrack search: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Search failed: {str(e)}'
        })