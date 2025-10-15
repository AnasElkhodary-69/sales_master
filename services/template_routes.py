from flask import render_template, request, jsonify, flash, redirect, url_for
from models.database import db, EmailTemplate, EmailSequenceConfig, Settings
from datetime import datetime
import json

def register_template_routes(app):
    
    @app.route('/templates')
    def templates():
        """Template management page"""
        templates = EmailTemplate.query.filter_by(active=True).all()
        sequences = EmailSequenceConfig.query.filter_by(is_active=True).all()
        return render_template('templates_management.html',
                             templates=templates,
                             sequences=sequences)
    
    @app.route('/templates/create', methods=['GET', 'POST'])
    def create_template():
        """Create new email template"""
        if request.method == 'POST':
            try:
                sequence_order = request.form.get('sequence_order', 1)
                sequence_step = int(sequence_order) - 1
                print(f"DEBUG CREATE TEMPLATE: sequence_order={sequence_order}, sequence_step={sequence_step}")
                
                template = EmailTemplate(
                    name=request.form['name'],
                    template_type=request.form['template_type'],
                    target_industry=request.form.get('target_industry', 'general'),  # Target industry for filtering
                    sequence_step=sequence_step,  # Convert 1-based UI to 0-based sequence
                    delay_amount=int(request.form.get('delay_amount', 0)),  # New flexible delay
                    delay_unit=request.form.get('delay_unit', 'days'),  # New delay unit
                    subject_line=request.form['subject_line'],
                    email_body=request.form['email_body'],
                    email_body_html=request.form.get('email_body_html', ''),
                    created_by=request.form.get('created_by', 'System')
                )
                
                db.session.add(template)
                db.session.commit()
                
                flash(f'Email template "{template.name}" created successfully!', 'success')
                return redirect(url_for('templates'))
                
            except Exception as e:
                flash(f'Error creating template: {str(e)}', 'error')
                
        return render_template('template_editor.html', template=None, action='create')
    
    @app.route('/templates/edit/<int:template_id>', methods=['GET', 'POST'])
    def edit_template(template_id):
        """Edit existing email template"""
        template = EmailTemplate.query.get_or_404(template_id)
        
        if request.method == 'POST':
            try:
                sequence_order = request.form.get('sequence_order', 1)
                sequence_step = int(sequence_order) - 1
                print(f"DEBUG EDIT TEMPLATE: template_id={template_id}, sequence_order={sequence_order}, sequence_step={sequence_step}")
                
                template.name = request.form['name']
                template.template_type = request.form['template_type']
                template.target_industry = request.form.get('target_industry', 'general')  # Target industry for filtering
                template.sequence_step = sequence_step  # Convert 1-based UI to 0-based sequence
                template.delay_amount = int(request.form.get('delay_amount', 0))  # New flexible delay
                template.delay_unit = request.form.get('delay_unit', 'days')  # New delay unit
                template.subject_line = request.form['subject_line']
                template.email_body = request.form['email_body']
                template.email_body_html = request.form.get('email_body_html', '')
                template.updated_at = datetime.utcnow()
                
                db.session.commit()
                
                flash(f'Template "{template.name}" updated successfully!', 'success')
                return redirect(url_for('templates'))
                
            except Exception as e:
                flash(f'Error updating template: {str(e)}', 'error')
                
        return render_template('template_editor.html', template=template, action='edit')
    
    @app.route('/templates/<int:template_id>/delete', methods=['POST'])
    def delete_template(template_id):
        """Delete email template"""
        try:
            print(f"DELETE TEMPLATE: Attempting to delete template ID {template_id}")
            template = EmailTemplate.query.get_or_404(template_id)
            template_name = template.name
            print(f"DELETE TEMPLATE: Found template '{template_name}' (ID: {template.id})")

            db.session.delete(template)
            print(f"DELETE TEMPLATE: Called db.session.delete()")

            db.session.flush()  # Force flush to see if there are any constraint errors
            print(f"DELETE TEMPLATE: Flushed session")

            db.session.commit()
            print(f"DELETE TEMPLATE: Committed successfully")

            # Verify deletion
            check = EmailTemplate.query.get(template_id)
            print(f"DELETE TEMPLATE: Post-commit verification - template still exists: {check is not None}")
            if check:
                print(f"DELETE TEMPLATE WARNING: Template was NOT deleted from database!")

            return jsonify({
                'success': True,
                'message': f'Template "{template_name}" deleted successfully'
            })

        except Exception as e:
            print(f"DELETE TEMPLATE ERROR: {str(e)}")
            import traceback
            print(f"DELETE TEMPLATE TRACEBACK: {traceback.format_exc()}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @app.route('/templates/toggle/<int:template_id>', methods=['POST'])
    def toggle_template(template_id):
        """Toggle template active status"""
        try:
            template = EmailTemplate.query.get_or_404(template_id)
            template.active = not template.active
            db.session.commit()
            
            status = 'activated' if template.active else 'deactivated'
            flash(f'Template "{template.name}" {status} successfully!', 'success')
            
        except Exception as e:
            flash(f'Error updating template: {str(e)}', 'error')
            
        return redirect(url_for('templates'))
    
    @app.route('/sequences/create', methods=['GET', 'POST'])
    def create_sequence():
        """Create new follow-up sequence"""
        print(f"create_sequence called with method: {request.method}")
        if request.method == 'POST':
            try:
                # Handle max_follow_ups with proper validation
                max_follow_ups_value = request.form.get('max_follow_ups', '5')
                if max_follow_ups_value is None:
                    max_follow_ups_value = '5'
                else:
                    max_follow_ups_value = str(max_follow_ups_value).strip()
                
                if not max_follow_ups_value or max_follow_ups_value == '':
                    max_follow_ups_value = '5'
                
                try:
                    max_follow_ups = int(max_follow_ups_value)
                except ValueError:
                    print(f"Invalid max_follow_ups value: '{max_follow_ups_value}', using default 5")
                    max_follow_ups = 5
                
                # Create sequence with all fields
                sequence = EmailSequenceConfig(
                    name=request.form['name'],
                    description=request.form.get('description', ''),
                    max_follow_ups=max_follow_ups,
                    stop_on_reply=request.form.get('stop_on_reply') == 'on',
                    stop_on_bounce=request.form.get('stop_on_bounce') == 'on',
                    target_industry=request.form.get('target_industry', 'general'),
                    created_by=request.form.get('created_by', 'System'),
                    is_active=True
                )
                
                db.session.add(sequence)
                db.session.commit()
                
                flash(f'Follow-up sequence "{sequence.name}" created successfully!', 'success')
                return redirect(url_for('templates'))
                
            except Exception as e:
                # More detailed error message for debugging
                print(f"Error creating sequence: {str(e)}")
                print(f"Form data: {dict(request.form)}")
                import traceback
                print(f"Full traceback: {traceback.format_exc()}")
                flash(f'Error creating sequence: {str(e)}', 'error')
        
        # GET request - render the form
        try:
            print("Rendering sequence_editor.html for GET request")
            return render_template('sequence_editor.html', sequence=None, action='create')
        except Exception as e:
            print(f"Error rendering template: {str(e)}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            raise
    
    @app.route('/sequences/edit/<int:sequence_id>', methods=['GET', 'POST'])
    def edit_sequence(sequence_id):
        """Edit existing follow-up sequence"""
        sequence = EmailSequenceConfig.query.get_or_404(sequence_id)
        
        if request.method == 'POST':
            try:
                # Handle max_follow_ups with proper validation
                max_follow_ups_value = request.form.get('max_follow_ups', '5').strip()
                if not max_follow_ups_value:
                    max_follow_ups_value = '5'
                max_follow_ups = int(max_follow_ups_value)
                
                # Update all sequence fields
                sequence.name = request.form['name']
                sequence.description = request.form.get('description', '')
                sequence.max_follow_ups = max_follow_ups
                sequence.stop_on_reply = request.form.get('stop_on_reply') == 'on'
                sequence.stop_on_bounce = request.form.get('stop_on_bounce') == 'on'
                sequence.target_industry = request.form.get('target_industry', 'general')
                sequence.updated_at = datetime.utcnow()
                
                db.session.commit()
                
                flash(f'Sequence "{sequence.name}" updated successfully!', 'success')
                return redirect(url_for('templates'))
                
            except Exception as e:
                flash(f'Error updating sequence: {str(e)}', 'error')
                
        return render_template('sequence_editor.html', sequence=sequence, action='edit')
    
    @app.route('/sequences/delete/<int:sequence_id>', methods=['POST'])
    def delete_sequence(sequence_id):
        """Delete follow-up sequence"""
        try:
            sequence = EmailSequenceConfig.query.get_or_404(sequence_id)
            sequence_name = sequence.name

            db.session.delete(sequence)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': f'Sequence "{sequence_name}" deleted successfully'
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @app.route('/templates/preview/<int:template_id>')
    def preview_template(template_id):
        """Preview email template with sample data"""
        template = EmailTemplate.query.get_or_404(template_id)
        
        # Sample data for preview
        sample_data = {
            'first_name': 'John',
            'last_name': 'Smith',
            'company': 'Acme Corp',
            'domain': 'acmecorp.com',
            'breach_name': 'Acme Corp Data Breach',
            'breach_year': '2023',
            'records_affected': '50,000',
            'breach_sample': 'Sample exposed credentials:\n• jo***h@acmecorp.com (LinkedIn)'
        }
        
        # Simple template variable replacement
        preview_subject = template.subject_line
        # Use HTML version if available, otherwise use plain text
        preview_body = template.email_body_html if template.email_body_html else template.email_body
        
        for key, value in sample_data.items():
            preview_subject = preview_subject.replace(f'{{{key}}}', str(value))
            preview_body = preview_body.replace(f'{{{key}}}', str(value))
        
        # Get email signature from settings
        email_signature = Settings.get_setting('email_signature', 'Best regards,<br>SalesBreachPro Team')
        
        return render_template('template_preview.html', 
                             template=template,
                             preview_subject=preview_subject,
                             preview_body=preview_body,
                             sample_data=sample_data,
                             email_signature=email_signature)
    
    @app.route('/api/templates/variables')
    def get_template_variables():
        """Get available template variables for UI helper"""
        variables = [
            {'name': 'first_name', 'description': 'Contact first name'},
            {'name': 'last_name', 'description': 'Contact last name'},
            {'name': 'company', 'description': 'Company name'},
            {'name': 'domain', 'description': 'Company domain'},
            {'name': 'title', 'description': 'Contact job title'},
            {'name': 'industry', 'description': 'Company industry'},
            {'name': 'breach_name', 'description': 'Name of security breach'},
            {'name': 'breach_year', 'description': 'Year of breach'},
            {'name': 'breach_date', 'description': 'Date of breach'},
            {'name': 'records_affected', 'description': 'Number of records affected'},
            {'name': 'risk_score', 'description': 'Risk score (0-10)'},
            {'name': 'severity', 'description': 'Breach severity level'}
        ]
        return jsonify(variables)
    
    @app.route('/api/templates')
    def get_templates():
        """Get templates filtered by risk level and/or template type"""
        risk_level = request.args.get('risk_level')
        breach_status = request.args.get('breach_status')  # Accept breach_status parameter
        template_type = request.args.get('template_type')
        
        query = EmailTemplate.query.filter_by(active=True)

        # Filter by template_type if provided
        if template_type:
            query = query.filter(EmailTemplate.template_type == template_type)

        # Filter by target_industry if breach_status or risk_level is provided (legacy support)
        filter_value = breach_status or risk_level
        if filter_value:
            query = query.filter(EmailTemplate.target_industry == filter_value)

        templates = query.all()

        template_list = []
        for template in templates:
            template_list.append({
                'id': template.id,
                'name': template.name,
                'template_type': template.template_type,
                'category': template.category,  # Replaced risk_level with category
                'target_industry': template.target_industry,
                'subject_line': template.subject_line,
                'delay_amount': template.delay_amount,
                'delay_unit': template.delay_unit,
                'active': template.active,
                'sequence_step': template.sequence_step,
                'usage_count': template.usage_count,
                'success_rate': template.success_rate,
                'created_at': template.created_at.isoformat() if template.created_at else None
            })
        
        return jsonify(template_list)