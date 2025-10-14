"""
Email Sequence Management Routes
Admin interface for configuring email sequences, templates, and timing
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from utils.decorators import login_required
from models.database import (
    db, EmailSequenceConfig, SequenceStep, EmailTemplate, Campaign,
    Contact, EmailSequence, ContactCampaignStatus, Settings, Email
)
from services.email_sequence_service import EmailSequenceService
from datetime import datetime
import json

# Create sequences blueprint
sequences_bp = Blueprint('sequences', __name__)

@sequences_bp.route('/admin/sequences')
@login_required
def sequence_configs():
    """Main sequence configuration page"""
    try:
        configs = EmailSequenceConfig.query.filter_by(is_active=True).all()
        return render_template('admin/sequences.html', configs=configs)
    except Exception as e:
        print(f"Sequence configs error: {e}")
        return render_template('admin/sequences.html', configs=[])

@sequences_bp.route('/admin/sequences/new', methods=['GET', 'POST'])
@login_required
def new_sequence_config():
    """Create new sequence configuration"""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            
            if not name:
                flash('Sequence name is required', 'error')
                return redirect(url_for('sequences.new_sequence_config'))
            
            # Create sequence config
            config = EmailSequenceConfig(
                name=name,
                description=description,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(config)
            db.session.flush()  # Get the ID
            
            # Parse and create sequence steps
            steps_data = request.form.get('steps_json', '[]')
            try:
                steps = json.loads(steps_data)
                for step_data in steps:
                    step = SequenceStep(
                        sequence_config_id=config.id,
                        step_number=int(step_data['step_number']),
                        delay_days=int(step_data['delay_days']),
                        step_name=step_data.get('step_name', f"Step {step_data['step_number']}")
                    )
                    db.session.add(step)
                
                db.session.commit()
                flash(f'Email sequence "{name}" created successfully!', 'success')
                return redirect(url_for('sequences.sequence_configs'))
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                db.session.rollback()
                flash('Invalid step configuration. Please check your input.', 'error')
                return redirect(url_for('sequences.new_sequence_config'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating sequence config: {e}")
            flash('Error creating sequence configuration. Please try again.', 'error')
    
    # GET request - show form
    return render_template('admin/new_sequence.html')

@sequences_bp.route('/admin/sequences/<int:config_id>')
@login_required
def view_sequence_config(config_id):
    """View/edit sequence configuration"""
    try:
        config = EmailSequenceConfig.query.get_or_404(config_id)
        steps = config.steps.order_by(SequenceStep.step_number).all()
        
        # Get campaigns using this config
        campaigns = Campaign.query.filter_by(sequence_config_id=config_id).all()
        
        return render_template('admin/view_sequence.html', 
                             config=config, 
                             steps=steps, 
                             campaigns=campaigns)
    except Exception as e:
        print(f"Error viewing sequence config: {e}")
        flash('Sequence configuration not found.', 'error')
        return redirect(url_for('sequences.sequence_configs'))

@sequences_bp.route('/admin/sequences/<int:config_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_sequence_config(config_id):
    """Edit sequence configuration"""
    config = EmailSequenceConfig.query.get_or_404(config_id)
    
    if request.method == 'POST':
        try:
            config.name = request.form.get('name', '').strip()
            config.description = request.form.get('description', '').strip()
            config.updated_at = datetime.utcnow()
            
            if not config.name:
                flash('Sequence name is required', 'error')
                return redirect(url_for('sequences.edit_sequence_config', config_id=config_id))
            
            # Update steps - first delete existing ones
            SequenceStep.query.filter_by(sequence_config_id=config_id).delete()
            
            # Parse and create new steps
            steps_data = request.form.get('steps_json', '[]')
            try:
                steps = json.loads(steps_data)
                for step_data in steps:
                    step = SequenceStep(
                        sequence_config_id=config.id,
                        step_number=int(step_data['step_number']),
                        delay_days=int(step_data['delay_days']),
                        step_name=step_data.get('step_name', f"Step {step_data['step_number']}")
                    )
                    db.session.add(step)
                
                db.session.commit()
                flash(f'Email sequence "{config.name}" updated successfully!', 'success')
                return redirect(url_for('sequences.view_sequence_config', config_id=config_id))
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                db.session.rollback()
                flash('Invalid step configuration. Please check your input.', 'error')
                
        except Exception as e:
            db.session.rollback()
            print(f"Error updating sequence config: {e}")
            flash('Error updating sequence configuration. Please try again.', 'error')
    
    # GET request - show edit form
    steps = config.steps.order_by(SequenceStep.step_number).all()
    return render_template('admin/edit_sequence.html', config=config, steps=steps)

# Admin template routes removed - use /templates instead
# Templates are now managed through routes/templates.py

@sequences_bp.route('/api/sequences/<int:config_id>/stats')
def sequence_stats(config_id):
    """Get statistics for a sequence configuration"""
    try:
        config = EmailSequenceConfig.query.get_or_404(config_id)
        
        # Get campaigns using this config
        campaigns = Campaign.query.filter_by(sequence_config_id=config_id).all()
        
        # Get email sequences using this config
        sequences = EmailSequence.query.join(Campaign).filter(
            Campaign.sequence_config_id == config_id
        ).all()
        
        stats = {
            'total_campaigns': len(campaigns),
            'total_sequences': len(sequences),
            'active_sequences': len([s for s in sequences if not s.completed]),
            'completed_sequences': len([s for s in sequences if s.completed]),
            'emails_sent': sum(len(s.emails.all()) for s in sequences),
            'response_rate': 0.0  # Would calculate based on replies
        }
        
        return jsonify(stats)
        
    except Exception as e:
        print(f"Error getting sequence stats: {e}")
        return jsonify({'error': str(e)}), 500

@sequences_bp.route('/admin/sequences/<int:config_id>/test', methods=['POST'])
@login_required
def test_sequence(config_id):
    """Test sequence configuration with a contact"""
    try:
        config = EmailSequenceConfig.query.get_or_404(config_id)
        contact_id = request.form.get('contact_id')
        
        if not contact_id:
            return jsonify({'success': False, 'error': 'Contact ID is required'})
        
        contact = Contact.query.get(contact_id)
        if not contact:
            return jsonify({'success': False, 'error': 'Contact not found'})
        
        # Create test campaign (or use existing)
        test_campaign = Campaign.query.filter_by(
            name="Test Sequence Campaign",
            sequence_config_id=config_id
        ).first()
        
        if not test_campaign:
            test_campaign = Campaign(
                name="Test Sequence Campaign",
                description="Temporary campaign for testing sequences",
                status='draft',
                sequence_config_id=config_id,
                template_type='proactive',
                created_at=datetime.utcnow()
            )
            db.session.add(test_campaign)
            db.session.flush()
        
        # Use sequence service to enroll contact
        sequence_service = EmailSequenceService(db)
        result = sequence_service.enroll_contact_in_campaign(
            contact_id=contact.id,
            campaign_id=test_campaign.id,
            force_breach_check=False  # Skip FlawTrack for testing
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Successfully enrolled {contact.email} in test sequence',
                'details': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error during enrollment')
            })
    
    except Exception as e:
        print(f"Error testing sequence: {e}")
        return jsonify({'success': False, 'error': str(e)})

@sequences_bp.route('/admin/sequences/<int:config_id>/delete', methods=['POST'])
@login_required
def delete_sequence_config(config_id):
    """Delete sequence configuration (soft delete)"""
    try:
        config = EmailSequenceConfig.query.get_or_404(config_id)
        
        # Check if any campaigns are using this config
        campaigns_count = Campaign.query.filter_by(sequence_config_id=config_id).count()
        
        if campaigns_count > 0:
            return jsonify({
                'success': False, 
                'error': f'Cannot delete sequence config - it is being used by {campaigns_count} campaign(s)'
            })
        
        # Soft delete
        config.is_active = False
        config.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Sequence configuration "{config.name}" deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting sequence config: {e}")
        return jsonify({'success': False, 'error': str(e)})