"""
API routes for monitoring domain scan progress
Provides real-time updates on background scanning tasks
"""

from flask import Blueprint, jsonify, request
from utils.decorators import login_required
from datetime import datetime, timedelta
import logging

# Try to import Celery - it's optional
try:
    from celery.result import AsyncResult
    from celery_app import celery_app
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    AsyncResult = None
    celery_app = None

logger = logging.getLogger(__name__)

# Create blueprint
scan_progress_bp = Blueprint('scan_progress', __name__, url_prefix='/api/scan')

@scan_progress_bp.route('/progress/<task_id>', methods=['GET'])
@login_required
def get_scan_progress(task_id):
    """Get progress of a specific scan task (supports both Celery and simple scanner)"""
    try:
        # Try Celery first (if available)
        if CELERY_AVAILABLE:
            try:
                task_result = AsyncResult(task_id, app=celery_app)

                if task_result.state == 'PENDING':
                    response = {
                        'state': task_result.state,
                        'status': 'Task is waiting to be processed...',
                        'progress': 0
                    }
                elif task_result.state == 'PROGRESS':
                    response = {
                        'state': task_result.state,
                        'status': 'Task is in progress...',
                        'progress': task_result.info.get('progress', 0),
                        'current_domain': task_result.info.get('current_domain', ''),
                        'completed': task_result.info.get('completed', 0),
                        'total': task_result.info.get('total', 0)
                    }
                elif task_result.state == 'SUCCESS':
                    response = {
                        'state': task_result.state,
                        'status': 'Task completed successfully!',
                        'progress': 100,
                        'result': task_result.info
                    }
                else:  # FAILURE
                    response = {
                        'state': task_result.state,
                        'status': 'Task failed',
                        'progress': 0,
                        'error': str(task_result.info)
                    }

                return jsonify(response)

            except Exception as celery_error:
                pass  # Fall through to simple scanner

        # Try simple scanner as fallback
        try:
            from services.simple_background_scanner import get_simple_scan_progress
            result = get_simple_scan_progress(task_id)

            if result:
                return jsonify(result)
            else:
                return jsonify({
                    'state': 'PENDING',
                    'status': 'Task not found in any scanner',
                    'progress': 0
                })

        except Exception as simple_error:
            logger.error(f"Simple scanner failed for task {task_id}: {simple_error}")
            return jsonify({
                'state': 'FAILURE',
                'status': 'Scanner not available',
                'progress': 0,
                'error': 'No scanning backend available'
            })

    except Exception as e:
        logger.error(f"Error getting scan progress for task {task_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@scan_progress_bp.route('/status', methods=['GET'])
@login_required
def get_scan_status():
    """Get overall scan status and statistics"""
    try:
        from models.database import db, Breach, Contact

        # Get scan statistics
        total_domains = db.session.query(Contact.domain).filter(
            Contact.domain.isnot(None)
        ).distinct().count()

        scanned_domains = Breach.query.filter(
            Breach.scan_status.in_(['completed', 'failed'])
        ).count()

        successful_scans = Breach.query.filter(
            Breach.scan_status == 'completed'
        ).count()

        failed_scans = Breach.query.filter(
            Breach.scan_status == 'failed'
        ).count()

        pending_scans = total_domains - scanned_domains

        # Get recent scan activity (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(hours=24)
        recent_scans = Breach.query.filter(
            Breach.last_updated >= yesterday
        ).count()

        # Get breach statistics
        breached_domains = Breach.query.filter(
            Breach.breach_status == 'breached'
        ).count()

        clean_domains = Breach.query.filter(
            Breach.breach_status == 'not_breached'
        ).count()

        response = {
            'scan_statistics': {
                'total_domains': total_domains,
                'scanned_domains': scanned_domains,
                'successful_scans': successful_scans,
                'failed_scans': failed_scans,
                'pending_scans': pending_scans,
                'recent_scans_24h': recent_scans
            },
            'breach_statistics': {
                'breached_domains': breached_domains,
                'clean_domains': clean_domains,
                'breach_rate': round((breached_domains / max(scanned_domains, 1)) * 100, 1)
            },
            'last_updated': datetime.utcnow().isoformat()
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting scan status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@scan_progress_bp.route('/domains', methods=['GET'])
@login_required
def get_domain_scan_results():
    """Get scan results for all domains"""
    try:
        from models.database import db, Breach, Contact

        # Get query parameters
        status_filter = request.args.get('status')  # 'completed', 'failed', 'pending'
        breach_filter = request.args.get('breach_status')  # 'breached', 'not_breached'
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        # Build query
        query = db.session.query(
            Breach.domain,
            Breach.scan_status,
            Breach.breach_status,
            Breach.risk_score,
            Breach.last_updated,
            Breach.scan_error,
            db.func.count(Contact.id).label('contact_count')
        ).outerjoin(
            Contact, Breach.domain == Contact.domain
        ).group_by(
            Breach.domain, Breach.scan_status, Breach.breach_status,
            Breach.risk_score, Breach.last_updated, Breach.scan_error
        )

        # Apply filters
        if status_filter:
            query = query.filter(Breach.scan_status == status_filter)

        if breach_filter:
            query = query.filter(Breach.breach_status == breach_filter)

        # Get results with pagination
        results = query.offset(offset).limit(limit).all()

        domains = []
        for result in results:
            domains.append({
                'domain': result.domain,
                'scan_status': result.scan_status,
                'breach_status': result.breach_status,
                'risk_score': result.risk_score,
                'contact_count': result.contact_count,
                'last_updated': result.last_updated.isoformat() if result.last_updated else None,
                'scan_error': result.scan_error
            })

        return jsonify({
            'domains': domains,
            'total_results': len(domains),
            'offset': offset,
            'limit': limit
        })

    except Exception as e:
        logger.error(f"Error getting domain scan results: {str(e)}")
        return jsonify({'error': str(e)}), 500

@scan_progress_bp.route('/start-batch', methods=['POST'])
@login_required
def start_domain_scan_batch():
    """Start a new domain scan batch"""
    try:
        data = request.get_json()
        domains = data.get('domains', [])
        batch_id = data.get('batch_id', f"batch_{int(datetime.utcnow().timestamp())}")

        if not domains:
            return jsonify({'error': 'No domains provided'}), 400

        # Try to use scanning service (handles fallback automatically)
        from services.contact_upload_integration import trigger_domain_scanning_after_upload

        # Prepare contact data format
        contacts_data = [{'email': f'test@{domain}', 'domain': domain} for domain in domains]

        result = trigger_domain_scanning_after_upload(contacts_data, batch_id)

        if result['success']:
            return jsonify({
                'success': True,
                'task_id': result.get('task_id'),
                'batch_id': batch_id,
                'domains_count': len(domains),
                'estimated_duration_minutes': len(domains) * 0.5 + (len(domains) - 1) * 0.5,
                'message': f'Started scanning {len(domains)} domains using {result.get("scanner_type", "unknown")} backend'
            })
        else:
            return jsonify({'error': result.get('error', 'Failed to start scanning')}), 500

    except Exception as e:
        logger.error(f"Error starting domain scan batch: {str(e)}")
        return jsonify({'error': str(e)}), 500

@scan_progress_bp.route('/retry-failed', methods=['POST'])
@login_required
def retry_failed_scans():
    """Retry all failed domain scans"""
    try:
        from models.database import db, Breach

        # Get all failed domains
        failed_breaches = Breach.query.filter(
            Breach.scan_status == 'failed'
        ).all()

        if not failed_breaches:
            return jsonify({
                'success': True,
                'message': 'No failed scans to retry',
                'domains_count': 0
            })

        domains = [breach.domain for breach in failed_breaches]
        batch_id = f"retry_batch_{int(datetime.utcnow().timestamp())}"

        # Reset scan status to pending
        for breach in failed_breaches:
            breach.scan_status = 'pending'
            breach.scan_error = None

        db.session.commit()

        # Use the integrated scanning service
        from services.contact_upload_integration import trigger_domain_scanning_after_upload

        # Prepare contact data format
        contacts_data = [{'email': f'retry@{domain}', 'domain': domain} for domain in domains]

        result = trigger_domain_scanning_after_upload(contacts_data, batch_id)

        if result['success']:
            logger.info(f"Started retry batch {batch_id} with {len(domains)} domains using {result.get('scanner_type')} backend")

            return jsonify({
                'success': True,
                'task_id': result.get('task_id'),
                'batch_id': batch_id,
                'domains_count': len(domains),
                'message': f'Retrying {len(domains)} failed domain scans using {result.get("scanner_type", "unknown")} backend'
            })
        else:
            return jsonify({'error': result.get('error', 'Failed to start retry scanning')}), 500

    except Exception as e:
        logger.error(f"Error retrying failed scans: {str(e)}")
        return jsonify({'error': str(e)}), 500

@scan_progress_bp.route('/cancel/<task_id>', methods=['POST'])
@login_required
def cancel_scan_task(task_id):
    """Cancel a running scan task"""
    try:
        cancelled = False

        # Try Celery cancellation first (if available)
        if CELERY_AVAILABLE:
            try:
                celery_app.control.revoke(task_id, terminate=True)
                cancelled = True
                logger.info(f"Cancelled Celery scan task: {task_id}")
            except Exception as celery_error:
                logger.warning(f"Could not cancel Celery task {task_id}: {celery_error}")

        # Simple scanner tasks cannot be cancelled once started (they run in threads)
        # but we can mark them as cancelled in progress tracking
        if not cancelled:
            try:
                from services.simple_background_scanner import get_simple_scanner
                scanner = get_simple_scanner()

                # Mark as cancelled in progress tracking
                if task_id in scanner.task_progress:
                    scanner.task_progress[task_id].update({
                        'state': 'REVOKED',
                        'status': 'Task was cancelled by user',
                        'progress': scanner.task_progress[task_id].get('progress', 0)
                    })
                    cancelled = True
                    logger.info(f"Marked simple scanner task as cancelled: {task_id}")
            except Exception as simple_error:
                logger.warning(f"Could not cancel simple scanner task {task_id}: {simple_error}")

        if cancelled:
            return jsonify({
                'success': True,
                'message': f'Task {task_id} has been cancelled'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Could not cancel task {task_id} - task may not exist or already completed'
            }), 404

    except Exception as e:
        logger.error(f"Error cancelling scan task {task_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500