"""
Simplified Database Models for Industry-Based Email Marketing SaaS
Clean, focused on core email marketing without breach scanning
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func
import uuid

db = SQLAlchemy()

class Contact(db.Model):
    """Contact model for storing prospect information"""
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    company = db.Column(db.String(255), index=True)
    domain = db.Column(db.String(255), index=True)
    title = db.Column(db.String(255))
    phone = db.Column(db.String(50))

    # Industry-based classification (replaces breach-based targeting)
    industry = db.Column(db.String(100), index=True)  # e.g., Healthcare, Finance, Retail, Technology
    business_type = db.Column(db.String(100))  # e.g., B2B, B2C, Enterprise, SMB
    company_size = db.Column(db.String(50))  # e.g., 1-10, 11-50, 51-200, 201-1000, 1000+

    # Contact metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_contacted = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='active')  # active, inactive, bounced, unsubscribed
    is_active = db.Column(db.Boolean, default=True)
    unsubscribed = db.Column(db.Boolean, default=False)
    unsubscribed_at = db.Column(db.DateTime)

    # Lead management fields
    notes = db.Column(db.Text)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    tags = db.Column(db.String(500))  # Comma-separated tags
    next_action_date = db.Column(db.DateTime)

    # Email engagement tracking fields (updated by webhooks)
    last_opened_at = db.Column(db.DateTime)
    last_clicked_at = db.Column(db.DateTime)
    last_contacted_at = db.Column(db.DateTime)
    total_opens = db.Column(db.Integer, default=0)
    total_clicks = db.Column(db.Integer, default=0)
    email_status = db.Column(db.String(50), default='unknown')  # unknown, valid, bounced
    bounce_type = db.Column(db.String(50))  # hard, soft
    bounced_at = db.Column(db.DateTime)
    blocked_at = db.Column(db.DateTime)
    block_reason = db.Column(db.String(255))
    is_subscribed = db.Column(db.Boolean, default=True)
    has_responded = db.Column(db.Boolean, default=False)
    responded_at = db.Column(db.DateTime)
    marked_as_spam = db.Column(db.Boolean, default=False)
    spam_reported_at = db.Column(db.DateTime)

    # Optional: Email validation fields (if you want to keep validation)
    email_validation_status = db.Column(db.String(20))  # valid, risky, invalid
    email_validation_score = db.Column(db.Integer)  # 0-100 confidence score
    is_disposable = db.Column(db.Boolean, default=False)
    is_role_based = db.Column(db.Boolean, default=False)

    # Relationships with cascading deletion
    emails = db.relationship('Email', backref='contact', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Contact {self.email}>'

    @property
    def campaign_count(self):
        """Get the number of campaigns this contact is enrolled in"""
        if hasattr(self, '_campaign_count'):
            return self._campaign_count

        ContactCampaignStatus = db.Model.registry._class_registry['ContactCampaignStatus']
        return db.session.query(func.count(ContactCampaignStatus.campaign_id.distinct())).filter(
            ContactCampaignStatus.contact_id == self.id
        ).scalar() or 0

    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'company': self.company,
            'domain': self.domain,
            'title': self.title,
            'phone': self.phone,
            'industry': self.industry,
            'business_type': self.business_type,
            'company_size': self.company_size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_contacted': self.last_contacted.isoformat() if self.last_contacted else None,
            'status': self.status,
            'is_active': self.is_active,
            'unsubscribed': self.unsubscribed,
            'notes': self.notes,
            'priority': self.priority,
            'tags': self.tags.split(',') if self.tags else [],
            'campaign_count': self.campaign_count,
            'email_validation_status': self.email_validation_status,
            'is_disposable': self.is_disposable,
            'is_role_based': self.is_role_based
        }

    def is_valid_email(self):
        """Validate email address format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, self.email or ''))


class Campaign(db.Model):
    """Campaign model for email campaign management"""
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    # Industry-based targeting (replaces breach/risk targeting)
    target_industries = db.Column(db.JSON)  # ["Healthcare", "Finance", "Retail"]
    target_business_types = db.Column(db.JSON)  # ["B2B", "Enterprise"]
    target_company_sizes = db.Column(db.JSON)  # ["51-200", "201-1000"]

    # Campaign settings
    status = db.Column(db.String(50), default='draft')  # draft, active, paused, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    scheduled_start = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    daily_limit = db.Column(db.Integer, default=50)

    # Sender information
    sender_email = db.Column(db.String(255))
    sender_name = db.Column(db.String(255))

    # Template/Sequence configuration
    template_id = db.Column(db.Integer, db.ForeignKey('email_templates.id'))
    sequence_config_id = db.Column(db.Integer, db.ForeignKey('email_sequence_configs.id'))

    # Email approval workflow
    requires_approval = db.Column(db.Boolean, default=False)
    approval_mode = db.Column(db.String(20), default='automatic')  # automatic, manual_approval, batch_approval

    # Campaign metrics
    total_contacts = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    response_count = db.Column(db.Integer, default=0)
    bounce_count = db.Column(db.Integer, default=0)
    blocked_count = db.Column(db.Integer, default=0)

    # Auto-enrollment (simplified - no breach checking)
    auto_enroll = db.Column(db.Boolean, default=False)
    last_enrollment_check = db.Column(db.DateTime)

    # Relationships
    emails = db.relationship('Email', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Campaign {self.name}>'

    @property
    def response_rate(self):
        """Calculate response rate as percentage"""
        if self.sent_count == 0:
            return 0.0
        return round((self.response_count / self.sent_count) * 100, 2)

    @property
    def bounce_rate(self):
        """Calculate bounce rate as percentage"""
        if self.sent_count == 0:
            return 0.0
        return round((self.bounce_count / self.sent_count) * 100, 2)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'target_industries': self.target_industries,
            'target_business_types': self.target_business_types,
            'target_company_sizes': self.target_company_sizes,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'scheduled_start': self.scheduled_start.isoformat() if self.scheduled_start else None,
            'total_contacts': self.total_contacts,
            'sent_count': self.sent_count,
            'response_count': self.response_count,
            'response_rate': self.response_rate,
            'active': self.active,
            'auto_enroll': self.auto_enroll
        }


class Email(db.Model):
    """Email model for tracking sent emails and responses"""
    __tablename__ = 'emails'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('email_templates.id'))
    variant_id = db.Column(db.Integer)  # For A/B testing if you keep it
    email_type = db.Column(db.String(50), default='initial')  # initial, follow_up_1, follow_up_2, etc.
    subject = db.Column(db.String(500))
    body = db.Column(db.Text)
    content = db.Column(db.Text)  # Alias for body
    status = db.Column(db.String(50), default='pending')  # pending, sent, delivered, opened, clicked, replied, bounced, complained
    sent_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    opened_at = db.Column(db.DateTime)
    clicked_at = db.Column(db.DateTime)
    replied_at = db.Column(db.DateTime)
    bounced_at = db.Column(db.DateTime)
    blocked_at = db.Column(db.DateTime)
    complained_at = db.Column(db.DateTime)
    brevo_message_id = db.Column(db.String(255))
    thread_message_id = db.Column(db.String(255))

    # Additional tracking fields
    open_count = db.Column(db.Integer, default=0)
    click_count = db.Column(db.Integer, default=0)
    bounce_type = db.Column(db.String(50))
    block_reason = db.Column(db.String(255))
    clicked_links = db.Column(db.JSON)

    # Email approval tracking
    approval_status = db.Column(db.String(20), default='not_required')
    approved_by = db.Column(db.String(100))
    approved_at = db.Column(db.DateTime)
    approval_notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    responses = db.relationship('Response', backref='email', lazy='dynamic', cascade='all, delete-orphan')
    template = db.relationship('EmailTemplate', backref='emails')

    def __repr__(self):
        return f'<Email {self.id} - {self.subject[:30]}...>'

    def to_dict(self):
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'campaign_id': self.campaign_id,
            'email_type': self.email_type,
            'subject': self.subject,
            'body': self.body,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None,
            'open_count': self.open_count,
            'click_count': self.click_count
        }


class Response(db.Model):
    """Response model for tracking email responses"""
    __tablename__ = 'responses'

    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    response_type = db.Column(db.String(50))  # positive, negative, neutral, auto_reply
    sentiment = db.Column(db.String(50))  # positive, negative, neutral
    content = db.Column(db.Text)
    action_required = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    lead_score = db.Column(db.Integer)  # 0-10 scale

    def __repr__(self):
        return f'<Response {self.id} - {self.response_type}>'

    def to_dict(self):
        return {
            'id': self.id,
            'email_id': self.email_id,
            'response_type': self.response_type,
            'sentiment': self.sentiment,
            'content': self.content,
            'action_required': self.action_required,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'lead_score': self.lead_score
        }


class EmailTemplate(db.Model):
    """Email template model - simplified without breach types"""
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    template_type = db.Column(db.String(50), nullable=False)  # initial, follow_up

    # Removed: risk_level, breach_template_type
    # Now uses industry/purpose categorization
    category = db.Column(db.String(100))  # e.g., "Sales Outreach", "Partnership", "Product Launch"
    target_industry = db.Column(db.String(100))  # Optional: specific industry template

    sequence_order = db.Column(db.Integer, default=1)
    sequence_step = db.Column(db.Integer, default=0)  # 0=initial, 1=follow1, 2=follow2

    # Delay configuration
    delay_amount = db.Column(db.Integer, default=0)
    delay_unit = db.Column(db.String(10), default='days')  # minutes, hours, days

    # Email content
    subject_line = db.Column(db.String(500), nullable=False)
    subject = db.Column(db.String(500))  # Alias
    email_body = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text)  # Alias
    email_body_html = db.Column(db.Text)

    # Available variables (updated list without breach-specific variables)
    available_variables = db.Column(db.JSON)  # ["{{company}}", "{{first_name}}", "{{industry}}", etc.]

    # Template settings
    is_active = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))

    # Performance tracking
    usage_count = db.Column(db.Integer, default=0)
    success_rate = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f'<EmailTemplate {self.name} - {self.template_type}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'template_type': self.template_type,
            'category': self.category,
            'target_industry': self.target_industry,
            'sequence_order': self.sequence_order,
            'delay_amount': self.delay_amount,
            'delay_unit': self.delay_unit,
            'subject_line': self.subject_line,
            'email_body': self.email_body,
            'email_body_html': self.email_body_html,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'usage_count': self.usage_count,
            'success_rate': self.success_rate
        }


class TemplateVariant(db.Model):
    """Template variants for A/B testing (optional - keep if desired)"""
    __tablename__ = 'template_variants'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('email_templates.id'), nullable=False)
    variant_name = db.Column(db.String(50), nullable=False)
    variant_label = db.Column(db.String(100))
    subject_line = db.Column(db.String(500), nullable=False)
    email_body = db.Column(db.Text, nullable=False)
    email_body_html = db.Column(db.Text)
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    weight = db.Column(db.Integer, default=50)

    # Performance metrics
    emails_sent = db.Column(db.Integer, default=0)
    emails_delivered = db.Column(db.Integer, default=0)
    emails_opened = db.Column(db.Integer, default=0)
    emails_clicked = db.Column(db.Integer, default=0)
    emails_replied = db.Column(db.Integer, default=0)
    delivery_rate = db.Column(db.Float, default=0.0)
    open_rate = db.Column(db.Float, default=0.0)
    click_rate = db.Column(db.Float, default=0.0)
    response_rate = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template = db.relationship('EmailTemplate', backref='variants')

    def __repr__(self):
        return f'<TemplateVariant {self.variant_name} for Template {self.template_id}>'

    def calculate_rates(self):
        """Calculate performance rates"""
        if self.emails_sent > 0:
            self.delivery_rate = round((self.emails_delivered / self.emails_sent) * 100, 2)
            if self.emails_delivered > 0:
                self.open_rate = round((self.emails_opened / self.emails_delivered) * 100, 2)
                self.click_rate = round((self.emails_clicked / self.emails_delivered) * 100, 2)
                self.response_rate = round((self.emails_replied / self.emails_delivered) * 100, 2)


class Settings(db.Model):
    """Settings model for storing application configuration"""
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Setting {self.key}: {self.value}>'

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description
        }

    @staticmethod
    def get_setting(key, default=None):
        """Get a setting value by key"""
        setting = Settings.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set_setting(key, value, description=None):
        """Set a setting value by key"""
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
            if description:
                setting.description = description
        else:
            setting = Settings(key=key, value=value, description=description)
            db.session.add(setting)

        db.session.commit()
        return setting


# Sequence Management Models (Simplified)

class EmailSequenceConfig(db.Model):
    """Configuration for email sequence timing"""
    __tablename__ = 'email_sequence_configs'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    steps = db.relationship('SequenceStep', backref='sequence_config', lazy='dynamic', cascade='all, delete-orphan')
    campaigns = db.relationship('Campaign', backref='sequence_config_ref', lazy='dynamic')

    def __repr__(self):
        return f'<EmailSequenceConfig {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'steps': [step.to_dict() for step in self.steps.order_by(SequenceStep.step_number)]
        }


class SequenceStep(db.Model):
    """Individual steps in an email sequence"""
    __tablename__ = 'sequence_steps'

    id = db.Column(db.Integer, primary_key=True)
    sequence_config_id = db.Column(db.Integer, db.ForeignKey('email_sequence_configs.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    delay_days = db.Column(db.Integer, nullable=False)
    step_name = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<SequenceStep {self.step_number}: {self.step_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'step_number': self.step_number,
            'delay_days': self.delay_days,
            'step_name': self.step_name,
            'is_active': self.is_active
        }


class EmailSequence(db.Model):
    """Tracks scheduled emails for each contact (simplified - no breach type)"""
    __tablename__ = 'email_sequences'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    sequence_step = db.Column(db.Integer, nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_datetime = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, sent, skipped_replied, failed
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    skip_reason = db.Column(db.String(100))
    error_message = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint('campaign_id', 'contact_id', 'sequence_step',
                          name='unique_campaign_contact_step'),
    )

    contact = db.relationship('Contact', backref=db.backref('email_sequences', lazy='dynamic', cascade='all, delete-orphan'))
    campaign = db.relationship('Campaign', backref=db.backref('email_sequences', lazy='dynamic', cascade='all, delete-orphan'))
    sent_email = db.relationship('Email', backref='sequence_record')

    def __repr__(self):
        return f'<EmailSequence C{self.contact_id} Camp{self.campaign_id} Step{self.sequence_step}>'

    def to_dict(self):
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'campaign_id': self.campaign_id,
            'sequence_step': self.sequence_step,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'status': self.status
        }


class ContactCampaignStatus(db.Model):
    """Tracks contact progress through campaigns (simplified - no breach status)"""
    __tablename__ = 'contact_campaign_status'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    current_sequence_step = db.Column(db.Integer, default=0)
    replied_at = db.Column(db.DateTime)  # Stops sequence when set
    sequence_completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('contact_id', 'campaign_id'),)

    contact = db.relationship('Contact', backref=db.backref('campaign_statuses', lazy='dynamic', cascade='all, delete-orphan'))
    campaign = db.relationship('Campaign', backref=db.backref('contact_statuses', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<ContactCampaignStatus C{self.contact_id} Camp{self.campaign_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'campaign_id': self.campaign_id,
            'current_sequence_step': self.current_sequence_step,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None,
            'sequence_completed_at': self.sequence_completed_at.isoformat() if self.sequence_completed_at else None
        }


class WebhookEvent(db.Model):
    """Stores webhook events from email providers (kept for analytics)"""
    __tablename__ = 'webhook_events'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)

    event_type = db.Column(db.String(50), nullable=False, index=True)
    provider = db.Column(db.String(50), default='brevo')
    provider_message_id = db.Column(db.String(255), index=True)

    event_data = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    clicked_url = db.Column(db.Text)
    bounce_reason = db.Column(db.String(255))
    bounce_type = db.Column(db.String(50))

    event_timestamp = db.Column(db.DateTime, nullable=False, index=True)
    received_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    processed_at = db.Column(db.DateTime)

    contact = db.relationship('Contact', backref=db.backref('webhook_events', lazy='dynamic'))
    email = db.relationship('Email', backref=db.backref('webhook_events', lazy='dynamic'))
    campaign = db.relationship('Campaign', backref=db.backref('webhook_events', lazy='dynamic'))

    def __repr__(self):
        return f'<WebhookEvent {self.event_type} for {self.contact_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'email_id': self.email_id,
            'campaign_id': self.campaign_id,
            'event_type': self.event_type,
            'event_timestamp': self.event_timestamp.isoformat() if self.event_timestamp else None
        }


def init_db(app):
    """Initialize database with Flask app"""
    with app.app_context():
        db.create_all()


def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        total_contacts = Contact.query.count()
        active_campaigns = Campaign.query.filter_by(status='active').count()

        from datetime import timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        emails_this_week = Email.query.filter(Email.sent_at >= week_ago).count()

        responses_this_week = Email.query.filter(
            Email.sent_at >= week_ago,
            Email.replied_at.isnot(None)
        ).count()

        response_rate = round((responses_this_week / emails_this_week * 100), 2) if emails_this_week > 0 else 0

        hot_leads = db.session.query(Response).join(Email).filter(
            Response.action_required == True,
            Response.response_type == 'positive'
        ).count()

        delivered_count = Email.query.filter(Email.status == 'delivered').count()
        opened_count = Email.query.filter(Email.opened_at.isnot(None)).count()
        bounced_count = Email.query.filter(Email.status == 'bounced').count()

        total_sent = Email.query.filter(Email.sent_at.isnot(None)).count()

        delivery_rate = round((delivered_count / total_sent * 100), 2) if total_sent > 0 else 0
        open_rate = round((opened_count / delivered_count * 100), 2) if delivered_count > 0 else 0
        bounce_rate = round((bounced_count / total_sent * 100), 2) if total_sent > 0 else 0

        return {
            'total_contacts': total_contacts,
            'active_campaigns': active_campaigns,
            'emails_this_week': emails_this_week,
            'responses_this_week': responses_this_week,
            'response_rate': response_rate,
            'hot_leads': hot_leads,
            'delivered_count': delivered_count,
            'opened_count': opened_count,
            'bounced_count': bounced_count,
            'delivery_rate': delivery_rate,
            'open_rate': open_rate,
            'bounce_rate': bounce_rate
        }
    except Exception as e:
        return {
            'total_contacts': 0,
            'active_campaigns': 0,
            'emails_this_week': 0,
            'responses_this_week': 0,
            'response_rate': 0.0,
            'hot_leads': 0,
            'delivered_count': 0,
            'opened_count': 0,
            'bounced_count': 0,
            'delivery_rate': 0.0,
            'open_rate': 0.0,
            'bounce_rate': 0.0
        }
