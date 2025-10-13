"""
A/B Testing Routes for SalesBreachPro
Comprehensive A/B testing system for email campaigns
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from utils.decorators import login_required
from models.database import db, ABTest, ABTestVariant, ABTestAssignment, Campaign, Contact, EmailTemplate
from datetime import datetime, timedelta
import random
import math
from scipy import stats

# Create A/B testing blueprint
ab_testing_bp = Blueprint('ab_testing', __name__, url_prefix='/ab-testing')

@ab_testing_bp.route('/')
@login_required
def ab_testing_dashboard():
    """A/B Testing dashboard"""
    # Get all A/B tests with basic stats
    ab_tests = ABTest.query.order_by(ABTest.created_at.desc()).all()

    # Dashboard stats
    total_tests = len(ab_tests)
    running_tests = len([t for t in ab_tests if t.status == 'running'])
    completed_tests = len([t for t in ab_tests if t.status == 'completed'])

    # Recent results
    recent_tests = ab_tests[:5]

    return render_template('ab_testing/dashboard.html',
                         ab_tests=ab_tests,
                         total_tests=total_tests,
                         running_tests=running_tests,
                         completed_tests=completed_tests,
                         recent_tests=recent_tests)

@ab_testing_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_ab_test():
    """Create new A/B test"""
    if request.method == 'POST':
        try:
            # Basic test info
            ab_test = ABTest(
                name=request.form['name'],
                description=request.form.get('description', ''),
                test_type=request.form['test_type'],
                campaign_id=int(request.form['campaign_id']),
                template_id=int(request.form.get('template_id')) if request.form.get('template_id') else None,
                traffic_split=float(request.form.get('traffic_split', 50.0)),
                sample_size=int(request.form.get('sample_size', 100)),
                primary_metric=request.form.get('primary_metric', 'open_rate'),
                created_by='admin'  # TODO: Get actual user
            )

            db.session.add(ab_test)
            db.session.flush()  # Get the ID

            # Create variants A and B
            variant_a = ABTestVariant(
                ab_test_id=ab_test.id,
                variant_name='A',
                subject_line=request.form.get('variant_a_subject', ''),
                email_body_html=request.form.get('variant_a_body', ''),
                sender_name=request.form.get('variant_a_sender_name', ''),
                sender_email=request.form.get('variant_a_sender_email', ''),
                cta_text=request.form.get('variant_a_cta', ''),
                send_time_offset=int(request.form.get('variant_a_time_offset', 0))
            )

            variant_b = ABTestVariant(
                ab_test_id=ab_test.id,
                variant_name='B',
                subject_line=request.form.get('variant_b_subject', ''),
                email_body_html=request.form.get('variant_b_body', ''),
                sender_name=request.form.get('variant_b_sender_name', ''),
                sender_email=request.form.get('variant_b_sender_email', ''),
                cta_text=request.form.get('variant_b_cta', ''),
                send_time_offset=int(request.form.get('variant_b_time_offset', 0))
            )

            db.session.add(variant_a)
            db.session.add(variant_b)
            db.session.commit()

            flash('A/B test created successfully!', 'success')
            return redirect(url_for('ab_testing.view_ab_test', test_id=ab_test.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating A/B test: {str(e)}', 'error')

    # GET request - show form
    campaigns = Campaign.query.filter_by(active=True).all()
    templates = EmailTemplate.query.filter_by(active=True).all()

    return render_template('ab_testing/create.html',
                         campaigns=campaigns,
                         templates=templates)

@ab_testing_bp.route('/<int:test_id>')
@login_required
def view_ab_test(test_id):
    """View A/B test details and results"""
    ab_test = ABTest.query.get_or_404(test_id)

    # Calculate current results
    update_ab_test_results(ab_test)

    # Get detailed variant data
    variants = ABTestVariant.query.filter_by(ab_test_id=test_id).all()
    assignments = ABTestAssignment.query.filter_by(ab_test_id=test_id).all()

    # Performance data for charts
    performance_data = {
        'variant_a': variants[0].to_dict() if len(variants) > 0 else {},
        'variant_b': variants[1].to_dict() if len(variants) > 1 else {},
        'total_assignments': len(assignments),
        'emails_sent': sum(a.email_sent for a in assignments),
        'statistical_significance': ab_test.statistical_significance
    }

    return render_template('ab_testing/view.html',
                         ab_test=ab_test,
                         variants=variants,
                         performance_data=performance_data)

@ab_testing_bp.route('/<int:test_id>/start', methods=['POST'])
@login_required
def start_ab_test(test_id):
    """Start an A/B test"""
    try:
        ab_test = ABTest.query.get_or_404(test_id)

        if ab_test.status != 'draft':
            return jsonify({
                'success': False,
                'error': 'Test can only be started from draft status'
            }), 400

        # Assign contacts to test variants
        contacts_assigned = assign_contacts_to_test(ab_test)

        # Update test status
        ab_test.status = 'running'
        ab_test.start_date = datetime.utcnow()
        ab_test.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'A/B test started successfully! {contacts_assigned} contacts assigned.',
            'contacts_assigned': contacts_assigned
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ab_testing_bp.route('/<int:test_id>/stop', methods=['POST'])
@login_required
def stop_ab_test(test_id):
    """Stop an A/B test"""
    try:
        ab_test = ABTest.query.get_or_404(test_id)

        # Calculate final results
        update_ab_test_results(ab_test)

        # Determine winner if statistically significant
        if ab_test.statistical_significance and ab_test.statistical_significance >= 95.0:
            variants = ABTestVariant.query.filter_by(ab_test_id=test_id).all()
            if len(variants) >= 2:
                metric = ab_test.primary_metric
                variant_a_score = getattr(variants[0], metric, 0)
                variant_b_score = getattr(variants[1], metric, 0)

                ab_test.winning_variant = 'A' if variant_a_score > variant_b_score else 'B'
                ab_test.winner_declared_at = datetime.utcnow()

        ab_test.status = 'completed'
        ab_test.end_date = datetime.utcnow()
        ab_test.updated_at = datetime.utcnow()

        db.session.commit()

        winner_message = f" Winner: Variant {ab_test.winning_variant}" if ab_test.winning_variant else ""

        return jsonify({
            'success': True,
            'message': f'A/B test completed successfully!{winner_message}',
            'winning_variant': ab_test.winning_variant,
            'statistical_significance': ab_test.statistical_significance
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ab_testing_bp.route('/api/tests/<int:test_id>/results')
@login_required
def get_ab_test_results(test_id):
    """Get A/B test results as JSON"""
    try:
        ab_test = ABTest.query.get_or_404(test_id)
        update_ab_test_results(ab_test)

        variants = ABTestVariant.query.filter_by(ab_test_id=test_id).all()

        results = {
            'test': ab_test.to_dict(),
            'variants': [v.to_dict() for v in variants],
            'statistical_significance': ab_test.statistical_significance,
            'winning_variant': ab_test.winning_variant
        }

        return jsonify(results)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== HELPER FUNCTIONS =====

def assign_contacts_to_test(ab_test):
    """Assign contacts to A/B test variants"""
    try:
        # Get eligible contacts from the campaign
        campaign = Campaign.query.get(ab_test.campaign_id)
        if not campaign:
            return 0

        # Get active contacts (limit by sample size)
        contacts = Contact.query.filter_by(
            is_active=True,
            unsubscribed=False
        ).limit(ab_test.sample_size).all()

        if not contacts:
            return 0

        # Get variants
        variants = ABTestVariant.query.filter_by(ab_test_id=ab_test.id).all()
        if len(variants) < 2:
            return 0

        variant_a, variant_b = variants[0], variants[1]

        # Calculate split sizes
        total_contacts = len(contacts)
        a_size = int(total_contacts * (ab_test.traffic_split / 100))
        b_size = total_contacts - a_size

        # Randomly assign contacts
        random.shuffle(contacts)

        assignments = []

        # Assign to variant A
        for i in range(a_size):
            if i < len(contacts):
                assignment = ABTestAssignment(
                    ab_test_id=ab_test.id,
                    contact_id=contacts[i].id,
                    variant_id=variant_a.id,
                    variant_name='A'
                )
                assignments.append(assignment)

        # Assign to variant B
        for i in range(a_size, total_contacts):
            if i < len(contacts):
                assignment = ABTestAssignment(
                    ab_test_id=ab_test.id,
                    contact_id=contacts[i].id,
                    variant_id=variant_b.id,
                    variant_name='B'
                )
                assignments.append(assignment)

        # Bulk insert assignments
        db.session.bulk_save_objects(assignments)
        db.session.commit()

        return len(assignments)

    except Exception as e:
        db.session.rollback()
        raise e

def update_ab_test_results(ab_test):
    """Update A/B test results and calculate statistical significance"""
    try:
        variants = ABTestVariant.query.filter_by(ab_test_id=ab_test.id).all()
        if len(variants) < 2:
            return

        variant_a, variant_b = variants[0], variants[1]

        # Update variant metrics from assignments
        for variant in variants:
            assignments = ABTestAssignment.query.filter_by(
                ab_test_id=ab_test.id,
                variant_id=variant.id
            ).all()

            variant.emails_sent = sum(1 for a in assignments if a.email_sent)
            variant.emails_delivered = sum(1 for a in assignments if a.delivered)
            variant.emails_opened = sum(1 for a in assignments if a.opened)
            variant.emails_clicked = sum(1 for a in assignments if a.clicked)
            variant.emails_replied = sum(1 for a in assignments if a.replied)
            variant.emails_bounced = sum(1 for a in assignments if a.bounced)
            variant.emails_unsubscribed = sum(1 for a in assignments if a.unsubscribed)

            # Calculate rates
            variant.calculate_rates()

        # Calculate statistical significance
        if ab_test.primary_metric == 'open_rate':
            sig = calculate_statistical_significance(
                variant_a.emails_opened, variant_a.emails_delivered,
                variant_b.emails_opened, variant_b.emails_delivered
            )
        elif ab_test.primary_metric == 'click_rate':
            sig = calculate_statistical_significance(
                variant_a.emails_clicked, variant_a.emails_delivered,
                variant_b.emails_clicked, variant_b.emails_delivered
            )
        elif ab_test.primary_metric == 'response_rate':
            sig = calculate_statistical_significance(
                variant_a.emails_replied, variant_a.emails_delivered,
                variant_b.emails_replied, variant_b.emails_delivered
            )
        else:
            sig = 0.0

        ab_test.statistical_significance = sig
        ab_test.updated_at = datetime.utcnow()

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        raise e

def calculate_statistical_significance(successes_a, trials_a, successes_b, trials_b):
    """Calculate statistical significance using z-test for proportions"""
    try:
        if trials_a == 0 or trials_b == 0:
            return 0.0

        # Calculate proportions
        p1 = successes_a / trials_a
        p2 = successes_b / trials_b

        # Combined proportion
        p_combined = (successes_a + successes_b) / (trials_a + trials_b)

        # Standard error
        se = math.sqrt(p_combined * (1 - p_combined) * (1/trials_a + 1/trials_b))

        if se == 0:
            return 0.0

        # Z-score
        z_score = abs(p1 - p2) / se

        # Convert to confidence level (two-tailed test)
        confidence = (1 - stats.norm.sf(abs(z_score)) * 2) * 100

        return round(confidence, 2)

    except Exception:
        return 0.0