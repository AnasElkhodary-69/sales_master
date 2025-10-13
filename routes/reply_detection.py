"""
Reply Detection Management Routes
Provides endpoints to manage and test alternative reply detection methods
"""
from flask import Blueprint, request, jsonify, render_template
from utils.decorators import login_required
from services.backup_reply_detection import get_backup_system
from services.reply_detection_service import create_reply_detection_service
from services.custom_reply_handler import create_custom_reply_handler
from models.database import db, Settings
import logging

logger = logging.getLogger(__name__)

reply_detection_bp = Blueprint('reply_detection', __name__, url_prefix='/admin/reply-detection')

@reply_detection_bp.route('/')
@login_required
def dashboard():
    """Reply detection management dashboard"""
    try:
        backup_system = get_backup_system()
        status = backup_system.get_detection_status()

        # Get configuration settings
        config = {
            'imap_server': Settings.get_setting('reply_detection_imap_server', ''),
            'email_address': Settings.get_setting('reply_detection_email', ''),
            'check_interval': Settings.get_setting('reply_detection_interval', '15'),
            'backup_enabled': Settings.get_setting('backup_reply_detection', 'true') == 'true'
        }

        return render_template('admin/reply_detection.html',
                             status=status,
                             config=config)

    except Exception as e:
        logger.error(f"Error loading reply detection dashboard: {e}")
        return render_template('admin/reply_detection.html',
                             status={'error': str(e)},
                             config={})

@reply_detection_bp.route('/api/manual-check', methods=['POST'])
@login_required
def manual_check():
    """Manually trigger reply detection check"""
    try:
        data = request.get_json() or {}
        contact_email = data.get('contact_email')

        backup_system = get_backup_system()
        results = backup_system.manual_reply_check(contact_email)

        return jsonify({
            'success': True,
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error in manual check: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@reply_detection_bp.route('/api/emergency-scan', methods=['POST'])
@login_required
def emergency_scan():
    """Run emergency reply scan"""
    try:
        backup_system = get_backup_system()
        results = backup_system.emergency_reply_scan()

        return jsonify({
            'success': True,
            'results': results,
            'message': 'Emergency scan completed'
        })

    except Exception as e:
        logger.error(f"Error in emergency scan: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@reply_detection_bp.route('/api/test-imap', methods=['POST'])
@login_required
def test_imap():
    """Test IMAP connection and reply detection"""
    try:
        service = create_reply_detection_service()
        results = service.check_for_replies()

        return jsonify({
            'success': True,
            'results': results,
            'message': 'IMAP test completed'
        })

    except Exception as e:
        logger.error(f"Error testing IMAP: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@reply_detection_bp.route('/api/test-custom-reply', methods=['POST'])
@login_required
def test_custom_reply():
    """Test custom reply address generation and parsing"""
    try:
        data = request.get_json() or {}
        contact_id = data.get('contact_id', 1)
        campaign_id = data.get('campaign_id', 1)
        email_id = data.get('email_id', 1)

        handler = create_custom_reply_handler()

        # Generate reply address
        reply_address = handler.generate_reply_address(contact_id, campaign_id, email_id)

        # Test decoding
        decoded = handler.decode_reply_address(reply_address)

        return jsonify({
            'success': True,
            'reply_address': reply_address,
            'decoded': decoded,
            'message': 'Custom reply test completed'
        })

    except Exception as e:
        logger.error(f"Error testing custom reply: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@reply_detection_bp.route('/api/status', methods=['GET'])
@login_required
def get_status():
    """Get current status of all reply detection methods"""
    try:
        backup_system = get_backup_system()
        status = backup_system.get_detection_status()

        return jsonify({
            'success': True,
            'status': status
        })

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@reply_detection_bp.route('/api/config', methods=['POST'])
@login_required
def update_config():
    """Update reply detection configuration"""
    try:
        data = request.get_json() or {}

        # Update IMAP settings
        if 'imap_server' in data:
            Settings.set_setting('reply_detection_imap_server', data['imap_server'])

        if 'email_address' in data:
            Settings.set_setting('reply_detection_email', data['email_address'])

        if 'email_password' in data:
            Settings.set_setting('reply_detection_password', data['email_password'])

        if 'check_interval' in data:
            Settings.set_setting('reply_detection_interval', str(data['check_interval']))

        if 'backup_enabled' in data:
            Settings.set_setting('backup_reply_detection', 'true' if data['backup_enabled'] else 'false')

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Configuration updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating config: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@reply_detection_bp.route('/webhooks/custom-reply', methods=['POST'])
def custom_reply_webhook():
    """
    Webhook endpoint for custom reply processing
    This would be called by your email provider when emails are received
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Process the custom reply
        from services.custom_reply_handler import handle_custom_reply_webhook
        result = handle_custom_reply_webhook(data)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in custom reply webhook: {e}")
        return jsonify({'error': str(e)}), 500

# Add this to your main app.py registration
def register_reply_detection_routes(app):
    """Register reply detection routes"""
    app.register_blueprint(reply_detection_bp)