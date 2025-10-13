#!/usr/bin/env python3
"""
New Template Variant System Design
This shows how the variant system should work with your existing templates and sequences
"""

# New database model to add to database.py
template_variant_model = '''
class TemplateVariant(db.Model):
    """Template variants for A/B testing different versions of the same template"""
    __tablename__ = 'template_variants'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('email_templates.id'), nullable=False)
    variant_name = db.Column(db.String(50), nullable=False)  # 'A', 'B', 'C', 'Original'
    variant_label = db.Column(db.String(100))  # 'Friendly Subject', 'Direct Subject', etc.

    # Email content for this variant
    subject_line = db.Column(db.String(500), nullable=False)
    email_body = db.Column(db.Text, nullable=False)
    email_body_html = db.Column(db.Text)

    # Variant settings
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    weight = db.Column(db.Integer, default=50)  # For traffic distribution (50% = equal split)

    # Performance tracking
    emails_sent = db.Column(db.Integer, default=0)
    emails_delivered = db.Column(db.Integer, default=0)
    emails_opened = db.Column(db.Integer, default=0)
    emails_clicked = db.Column(db.Integer, default=0)
    emails_replied = db.Column(db.Integer, default=0)

    # Calculated rates (updated periodically)
    open_rate = db.Column(db.Float, default=0.0)
    click_rate = db.Column(db.Float, default=0.0)
    response_rate = db.Column(db.Float, default=0.0)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    template = db.relationship('EmailTemplate', backref='variants')

    def __repr__(self):
        return f'<TemplateVariant {self.variant_name} for Template {self.template_id}>'
'''

# Updated Campaign model additions
campaign_model_additions = '''
# Add these fields to Campaign model:
variant_testing_enabled = db.Column(db.Boolean, default=False)
variant_split_strategy = db.Column(db.String(20), default='equal')  # 'equal', 'weighted', 'manual'
variant_winner_declared = db.Column(db.Boolean, default=False)
winning_variant_id = db.Column(db.Integer, db.ForeignKey('template_variants.id'))
'''

# Updated Email model additions
email_model_additions = '''
# Add these fields to Email model (variant_id already exists):
template_variant_id = db.Column(db.Integer, db.ForeignKey('template_variants.id'))

# Relationships
template_variant = db.relationship('TemplateVariant')
'''

print("=== NEW TEMPLATE VARIANT SYSTEM DESIGN ===")
print("\n1. TEMPLATE VARIANTS MODEL:")
print(template_variant_model)

print("\n2. CAMPAIGN MODEL ADDITIONS:")
print(campaign_model_additions)

print("\n3. EMAIL MODEL ADDITIONS:")
print(email_model_additions)

print("""
=== WORKFLOW INTEGRATION ===

NEW CAMPAIGN CREATION FLOW:
1. Choose Campaign Type: Single Email or Sequence
2. Choose Target: Risk levels/breach status
3. Choose Content:

   FOR SINGLE EMAIL:
   - Select Template
   - IF template has variants: Choose which variants to test (A, B, or both)
   - Set traffic split (50/50, 70/30, etc.)

   FOR SEQUENCE:
   - Select Sequence
   - FOR EACH step in sequence:
     - IF template has variants: Choose which variants to test
     - Set traffic split for each step

4. Launch Campaign

SENDING LOGIC:
- When sending email, randomly select variant based on weights
- Track which variant was sent in email.template_variant_id
- Update variant performance metrics

RESULTS:
- View A/B test results per template
- Declare winners at template level
- Apply winning variants to future campaigns
""")