"""
Breach Checker Routes
Simple breach checking interface for emails and domains
"""
from flask import Blueprint, render_template, request, jsonify
from utils.decorators import login_required
from models.database import Breach
import logging

logger = logging.getLogger(__name__)

# Create breach checker blueprint
breach_checker_bp = Blueprint('breach_checker', __name__)

@breach_checker_bp.route('/breach-checker')
@login_required
def index():
    """Breach checker main page"""
    return render_template('breach_checker.html')

@breach_checker_bp.route('/api/breach-lookup/<domain>')
@login_required
def breach_lookup(domain):
    """API endpoint to lookup breach data for a domain"""
    try:
        # Look up breach data for the domain
        breach = Breach.query.filter_by(domain=domain).first()

        if breach:
            return jsonify({
                'success': True,
                'domain': domain,
                'breach_data': {
                    'records_affected': breach.records_affected or 0,
                    'breach_year': breach.breach_year,
                    'breach_name': breach.breach_name,
                    'severity': breach.severity,
                    'last_updated': breach.last_updated.isoformat() if breach.last_updated else None,
                    'breach_status': breach.breach_status,
                    'scan_status': breach.scan_status
                }
            })
        else:
            # Domain not in database - could mean not scanned yet or clean
            return jsonify({
                'success': True,
                'domain': domain,
                'breach_data': {
                    'records_affected': 0,
                    'breach_year': None,
                    'breach_name': None,
                    'severity': 'unknown',
                    'last_updated': None,
                    'breach_status': 'unknown',
                    'scan_status': 'not_scanned'
                }
            })

    except Exception as e:
        logger.error(f"Error looking up breach data for {domain}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500