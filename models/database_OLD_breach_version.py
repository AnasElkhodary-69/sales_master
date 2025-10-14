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
    industry = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_contacted = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='active')
    risk_score = db.Column(db.Float, default=0.0)  # Risk score from breach analysis
    breach_status = db.Column(db.String(20), default='unassigned')  # unassigned, breached, not_breached, unknown
    is_active = db.Column(db.Boolean, default=True)
    unsubscribed = db.Column(db.Boolean, default=False)
    unsubscribed_at = db.Column(db.DateTime)
    # Additional fields for lead management
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

    # Email validation fields (ZeroBounce integration)
    email_validation_status = db.Column(db.String(20))  # valid, risky, invalid
    email_validation_score = db.Column(db.Integer)  # 0-100 confidence score
    email_validation_method = db.Column(db.String(50))  # zerobounce_api, fallback_regex
    is_disposable = db.Column(db.Boolean, default=False)  # Disposable/temporary email
    is_role_based = db.Column(db.Boolean, default=False)  # Role-based email (admin@, info@, etc.)

    # Relationships with cascading deletion
    emails = db.relationship('Email', backref='contact', lazy='dynamic', cascade='all, delete-orphan')
    # Note: email_sequences and campaign_statuses relationships are defined in their respective models with backref
    # Responses are linked to emails, not directly to contacts, so they cascade through emails

    def __repr__(self):
        return f'<Contact {self.email}>'
    
    def get_domain_scan_status(self):
        """Get the scanning status for this contact's domain"""
        if not self.domain:
            return {'status': 'no_domain', 'message': 'No domain'}
        
        breach = Breach.query.filter_by(domain=self.domain).first()
        if not breach:
            return {'status': 'not_scanned', 'message': 'Not scanned'}
        
        status_messages = {
            'not_scanned': 'Not scanned',
            'scanning': 'Scanning in progress...',
            'completed': 'Scan completed',
            'failed': f'Scan failed ({breach.scan_attempts}/3 attempts)'
        }
        
        return {
            'status': breach.scan_status,
            'message': status_messages.get(breach.scan_status, 'Unknown'),
            'attempts': breach.scan_attempts,
            'last_attempt': breach.last_scan_attempt,
            'error': breach.scan_error
        }
    
    @property
    def campaign_count(self):
        """Get the number of campaigns this contact is enrolled in"""
        # Use cached value if available (set by optimized queries)
        if hasattr(self, '_campaign_count'):
            return self._campaign_count

        # Fallback to database query if not cached
        from sqlalchemy import func
        # Use ContactCampaignStatus to count enrollments, not Email records
        # Access the class through db.Model's registry to avoid circular imports
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
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_contacted': self.last_contacted.isoformat() if self.last_contacted else None,
            'status': self.status,
            'risk_score': self.risk_score,
            'is_active': self.is_active,
            'unsubscribed': self.unsubscribed,
            'unsubscribed_at': self.unsubscribed_at.isoformat() if self.unsubscribed_at else None,
            'notes': self.notes,
            'priority': self.priority,
            'tags': self.tags.split(',') if self.tags else [],
            'next_action_date': self.next_action_date.isoformat() if self.next_action_date else None,
            # New breach status fields
            'is_breached': self.is_breached(),
            'breach_status': self.get_breach_status(),
            'breach_count': self.get_breach_count(),
            'campaign_count': self.campaign_count,
            'latest_breach_date': self.get_latest_breach_date().isoformat() if self.get_latest_breach_date() else None,
            # Email validation fields
            'email_validation_status': self.email_validation_status,
            'email_validation_score': self.email_validation_score,
            'email_validation_method': self.email_validation_method,
            'is_disposable': self.is_disposable,
            'is_role_based': self.is_role_based
        }
    
    def is_valid_email(self):
        """Validate email address format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, self.email or ''))
    
    def is_breached(self):
        """Check if contact's domain has any breaches"""
        if not self.domain:
            return False
        # Check if there are any breaches for this domain
        return db.session.query(Breach).filter_by(domain=self.domain).first() is not None
    
    def get_breach_status(self):
        """Get breach status as simple string"""
        return "BREACHED" if self.is_breached() else "NOT BREACHED"
    
    def get_breach_status_class(self):
        """Get CSS class for breach status"""
        return "text-danger" if self.is_breached() else "text-success"
    
    def get_breach_badge_class(self):
        """Get Bootstrap badge class for breach status"""
        return "badge bg-danger" if self.is_breached() else "badge bg-success"
    
    def get_breach_count(self):
        """Get number of breaches for this domain"""
        if not self.domain:
            return 0
        return db.session.query(Breach).filter_by(domain=self.domain).count()
    
    def get_latest_breach_date(self):
        """Get the most recent breach date for this domain"""
        if not self.domain:
            return None
        latest_breach = db.session.query(Breach).filter_by(domain=self.domain).order_by(Breach.breach_date.desc()).first()
        return latest_breach.breach_date if latest_breach else None

class Campaign(db.Model):
    """Campaign model for email campaign management"""
    __tablename__ = 'campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    template_type = db.Column(db.String(50))  # high_risk, medium_risk, low_risk
    status = db.Column(db.String(50), default='draft')  # draft, active, paused, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    scheduled_start = db.Column(db.DateTime)
    total_contacts = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    response_count = db.Column(db.Integer, default=0)
    bounce_count = db.Column(db.Integer, default=0)
    blocked_count = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    daily_limit = db.Column(db.Integer, default=50)
    description = db.Column(db.Text)
    sender_email = db.Column(db.String(255))
    sender_name = db.Column(db.String(255))
    template_id = db.Column(db.Integer, db.ForeignKey('email_templates.id'))
    target_risk_levels = db.Column(db.JSON)
    
    # Auto-enrollment settings
    auto_enroll = db.Column(db.Boolean, default=False)  # Enable automatic enrollment
    auto_enroll_breach_status = db.Column(db.String(50))  # breached, not_breached, unknown, all
    last_enrollment_check = db.Column(db.DateTime)  # Track when we last checked for new contacts
    
    # Email Sequence Configuration
    sequence_config_id = db.Column(db.Integer, db.ForeignKey('email_sequence_configs.id'))  # Which sequence timing to use

    # Email approval workflow fields
    requires_approval = db.Column(db.Boolean, default=False)  # True = emails need approval, False = automatic sending
    approval_mode = db.Column(db.String(20), default='automatic')  # 'automatic', 'manual_approval', 'batch_approval'
    
    # Relationships
    emails = db.relationship('Email', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    # Note: Campaign variants replaced with template-based variants system
    
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
            'template_type': self.template_type,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'scheduled_start': self.scheduled_start.isoformat() if self.scheduled_start else None,
            'total_contacts': self.total_contacts,
            'sent_count': self.sent_count,
            'response_count': self.response_count,
            'response_rate': self.response_rate,
            'active': self.active,
            'auto_enroll': self.auto_enroll,
            'auto_enroll_breach_status': self.auto_enroll_breach_status,
            'last_enrollment_check': self.last_enrollment_check.isoformat() if self.last_enrollment_check else None
        }

class TemplateVariant(db.Model):
    """Template Variant model for A/B testing different versions of email templates"""
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
    delivery_rate = db.Column(db.Float, default=0.0)
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

    def calculate_rates(self):
        """Calculate performance rates"""
        if self.emails_sent > 0:
            self.delivery_rate = round((self.emails_delivered / self.emails_sent) * 100, 2)
            if self.emails_delivered > 0:
                self.open_rate = round((self.emails_opened / self.emails_delivered) * 100, 2)
                self.click_rate = round((self.emails_clicked / self.emails_delivered) * 100, 2)
                self.response_rate = round((self.emails_replied / self.emails_delivered) * 100, 2)

    def to_dict(self):
        return {
            'id': self.id,
            'template_id': self.template_id,
            'variant_name': self.variant_name,
            'variant_label': self.variant_label,
            'subject_line': self.subject_line,
            'email_body': self.email_body,
            'email_body_html': self.email_body_html,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'weight': self.weight,
            'emails_sent': self.emails_sent,
            'emails_delivered': self.emails_delivered,
            'emails_opened': self.emails_opened,
            'emails_clicked': self.emails_clicked,
            'emails_replied': self.emails_replied,
            'delivery_rate': self.delivery_rate,
            'open_rate': self.open_rate,
            'click_rate': self.click_rate,
            'response_rate': self.response_rate,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Breach(db.Model):
    """Breach model for storing cybersecurity breach data"""
    __tablename__ = 'breaches'
    
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False, index=True)
    breach_name = db.Column(db.String(255))
    breach_year = db.Column(db.Integer)
    breach_date = db.Column(db.Date)
    records_affected = db.Column(db.Integer)
    data_types = db.Column(db.Text)  # JSON string of data types
    breach_data = db.Column(db.JSON)  # Full breach data from API
    risk_score = db.Column(db.Float)  # 0-10 scale
    severity = db.Column(db.String(50))  # low, medium, high
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Breach status derived from scanning results
    breach_status = db.Column(db.String(20), default='unassigned')  # unassigned, unknown, breached, not_breached

    # Domain-level scanning status and retry tracking
    scan_status = db.Column(db.String(20), default='not_scanned')  # not_scanned, scanning, completed, failed
    scan_attempts = db.Column(db.Integer, default=0)  # Number of scan attempts for this domain
    last_scan_attempt = db.Column(db.DateTime)  # When last scan was attempted for this domain
    scan_error = db.Column(db.Text)  # Last scan error message if any
    
    def __repr__(self):
        return f'<Breach {self.domain} - {self.breach_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'domain': self.domain,
            'breach_name': self.breach_name,
            'breach_year': self.breach_year,
            'breach_date': self.breach_date.isoformat() if self.breach_date else None,
            'records_affected': self.records_affected,
            'data_types': self.data_types,
            'risk_score': self.risk_score,
            'severity': self.severity,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }

class Email(db.Model):
    """Email model for tracking sent emails and responses"""
    __tablename__ = 'emails'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('email_templates.id'))
    variant_id = db.Column(db.Integer)  # Legacy field, no foreign key constraint
    email_type = db.Column(db.String(50), default='initial')  # initial, follow_up_1, follow_up_2, etc.
    subject = db.Column(db.String(500))
    body = db.Column(db.Text)
    content = db.Column(db.Text)  # Alias for body
    status = db.Column(db.String(50), default='pending')  # pending, sent, delivered, opened, clicked, replied, bounced, complained, awaiting_approval, approved, rejected
    sent_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    opened_at = db.Column(db.DateTime)
    clicked_at = db.Column(db.DateTime)
    replied_at = db.Column(db.DateTime)
    bounced_at = db.Column(db.DateTime)
    blocked_at = db.Column(db.DateTime)
    complained_at = db.Column(db.DateTime)
    brevo_message_id = db.Column(db.String(255))  # Brevo message ID for tracking webhooks
    thread_message_id = db.Column(db.String(255))  # Custom Message-ID for email threading

    # Additional tracking fields for webhooks
    open_count = db.Column(db.Integer, default=0)
    click_count = db.Column(db.Integer, default=0)
    bounce_type = db.Column(db.String(50))  # hard, soft
    block_reason = db.Column(db.String(255))
    clicked_links = db.Column(db.JSON)  # List of clicked URLs

    # Email approval tracking fields
    approval_status = db.Column(db.String(20), default='not_required')  # not_required, awaiting_approval, approved, rejected
    approved_by = db.Column(db.String(100))  # Username/email of approver
    approved_at = db.Column(db.DateTime)
    approval_notes = db.Column(db.Text)  # Optional notes from approver

    # Timestamp fields
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
            'bounced_at': self.bounced_at.isoformat() if self.bounced_at else None,
            'complained_at': self.complained_at.isoformat() if self.complained_at else None,
            'brevo_message_id': self.brevo_message_id,
            'thread_message_id': self.thread_message_id,
            'open_count': self.open_count,
            'click_count': self.click_count,
            'bounce_type': self.bounce_type,
            'clicked_links': self.clicked_links
        }

class Response(db.Model):
    """Response model for tracking email responses and lead scoring"""
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
    """Email template model for storing email templates and follow-up sequences"""
    __tablename__ = 'email_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    template_type = db.Column(db.String(50), nullable=False)  # initial, follow_up
    risk_level = db.Column(db.String(50), nullable=False)  # high, medium, low, generic
    sequence_order = db.Column(db.Integer, default=1)  # For follow-up sequences
    delay_days = db.Column(db.Integer, default=0)  # Days to wait before sending (deprecated)
    delay_amount = db.Column(db.Integer, default=0)  # Amount to delay (1, 5, 30, etc.)  
    delay_unit = db.Column(db.String(10), default='days')  # Unit: 'minutes', 'hours', 'days'
    
    # New sequence system columns
    sequence_step = db.Column(db.Integer, default=0)  # 0=initial, 1=follow1, 2=follow2, etc.
    breach_template_type = db.Column(db.String(20), default='proactive')  # 'breached' or 'proactive'
    available_variables = db.Column(db.JSON)  # ["{{company}}", "{{first_name}}", etc.]
    
    # Email content
    subject_line = db.Column(db.String(500), nullable=False)
    subject = db.Column(db.String(500))  # Alias for subject_line
    email_body = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text)  # Alias for email_body
    is_active = db.Column(db.Boolean, default=True)
    email_body_html = db.Column(db.Text)  # HTML version
    
    # Template settings
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))  # User who created the template
    
    # Performance tracking
    usage_count = db.Column(db.Integer, default=0)
    success_rate = db.Column(db.Float, default=0.0)  # Response rate for this template
    
    def __repr__(self):
        return f'<EmailTemplate {self.name} - {self.risk_level} - {self.template_type}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'template_type': self.template_type,
            'risk_level': self.risk_level,
            'sequence_order': self.sequence_order,
            'delay_days': self.delay_days,
            'delay_amount': self.delay_amount,
            'delay_unit': self.delay_unit,
            'subject_line': self.subject_line,
            'email_body': self.email_body,
            'email_body_html': self.email_body_html,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'usage_count': self.usage_count,
            'success_rate': self.success_rate
        }

class FollowUpSequence(db.Model):
    """Follow-up sequence model for managing automated email sequences"""
    __tablename__ = 'followup_sequences'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    template_type = db.Column(db.String(50))  # Alias for risk_level
    risk_level = db.Column(db.String(50), nullable=False)  # high, medium, low, generic
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    steps = db.Column(db.JSON)  # Array of follow-up steps
    
    # Sequence settings
    active = db.Column(db.Boolean, default=True)
    max_follow_ups = db.Column(db.Integer, default=5)
    stop_on_reply = db.Column(db.Boolean, default=True)
    stop_on_bounce = db.Column(db.Boolean, default=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))
    
    # Performance tracking
    usage_count = db.Column(db.Integer, default=0)
    completion_rate = db.Column(db.Float, default=0.0)  # How many complete the full sequence
    
    # Relationship to templates
    templates = db.relationship('EmailTemplate', 
                               primaryjoin="and_(EmailTemplate.risk_level==FollowUpSequence.risk_level, "
                                          "EmailTemplate.template_type=='follow_up')",
                               foreign_keys='EmailTemplate.risk_level',
                               viewonly=True)
    
    def __repr__(self):
        return f'<FollowUpSequence {self.name} - {self.risk_level}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'risk_level': self.risk_level,
            'description': self.description,
            'active': self.active,
            'max_follow_ups': self.max_follow_ups,
            'stop_on_reply': self.stop_on_reply,
            'stop_on_bounce': self.stop_on_bounce,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'usage_count': self.usage_count,
            'completion_rate': self.completion_rate
        }

class Settings(db.Model):
    """Settings model for storing configurable application settings"""
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
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
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

# Email Sequence Management Models

class EmailSequenceConfig(db.Model):
    """Configuration for email sequence timing and structure"""
    __tablename__ = 'email_sequence_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
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
            'steps': [step.to_dict() for step in self.steps.order_by(SequenceStep.step_number)],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class SequenceStep(db.Model):
    """Individual steps in an email sequence with configurable timing"""
    __tablename__ = 'sequence_steps'
    
    id = db.Column(db.Integer, primary_key=True)
    sequence_config_id = db.Column(db.Integer, db.ForeignKey('email_sequence_configs.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)  # 0, 1, 2, 3, 4...
    delay_days = db.Column(db.Integer, nullable=False)   # 0, 2, 5, 12, 26...
    step_name = db.Column(db.String(100))                # "Initial Email", "First Follow-up"
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
    """Tracks scheduled emails for each contact in a campaign"""
    __tablename__ = 'email_sequences'
    
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    sequence_step = db.Column(db.Integer, nullable=False)    # 0, 1, 2, 3, 4...
    template_type = db.Column(db.String(20), nullable=False) # 'breached' or 'proactive'
    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_datetime = db.Column(db.DateTime)              # Precise scheduling with time for flexible delays
    sent_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='scheduled')   # scheduled, sent, skipped_replied, failed
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'))  # Links to actual sent email
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    skip_reason = db.Column(db.String(100))  # Reason if skipped
    error_message = db.Column(db.Text)       # Error message if failed
    
    # UNIQUE CONSTRAINT: Prevent duplicate emails for same contact/campaign/step
    __table_args__ = (
        db.UniqueConstraint('campaign_id', 'contact_id', 'sequence_step', 
                          name='unique_campaign_contact_step'),
    )
    
    # Relationships with cascading deletion
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
            'template_type': self.template_type,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ContactCampaignStatus(db.Model):
    """Tracks individual contact progress through campaigns"""
    __tablename__ = 'contact_campaign_status'
    
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    breach_status = db.Column(db.String(20), nullable=False)    # 'breached', 'clean', 'unknown'
    current_sequence_step = db.Column(db.Integer, default=0)    # Current step in sequence
    replied_at = db.Column(db.DateTime)                         # Stops sequence when set
    sequence_completed_at = db.Column(db.DateTime)              # When sequence finished
    flawtrack_checked_at = db.Column(db.DateTime)               # When breach status was checked
    breach_data = db.Column(db.JSON)                            # Store FlawTrack response
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint - one record per contact per campaign
    __table_args__ = (db.UniqueConstraint('contact_id', 'campaign_id'),)
    
    # Relationships with cascading deletion
    contact = db.relationship('Contact', backref=db.backref('campaign_statuses', lazy='dynamic', cascade='all, delete-orphan'))
    campaign = db.relationship('Campaign', backref=db.backref('contact_statuses', lazy='dynamic', cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<ContactCampaignStatus C{self.contact_id} Camp{self.campaign_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'campaign_id': self.campaign_id,
            'breach_status': self.breach_status,
            'current_sequence_step': self.current_sequence_step,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None,
            'sequence_completed_at': self.sequence_completed_at.isoformat() if self.sequence_completed_at else None,
            'flawtrack_checked_at': self.flawtrack_checked_at.isoformat() if self.flawtrack_checked_at else None,
            'breach_data': self.breach_data,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class WebhookEvent(db.Model):
    """Stores all webhook events from email providers for analytics"""
    __tablename__ = 'webhook_events'
    
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    
    # Event details
    event_type = db.Column(db.String(50), nullable=False, index=True)  # delivered, opened, clicked, replied, bounced, etc.
    provider = db.Column(db.String(50), default='brevo')  # brevo, ses, mailgun, etc.
    provider_message_id = db.Column(db.String(255), index=True)  # External message ID
    
    # Event data
    event_data = db.Column(db.JSON)  # Full webhook payload
    ip_address = db.Column(db.String(45))  # IP address from event
    user_agent = db.Column(db.Text)  # User agent from event
    clicked_url = db.Column(db.Text)  # URL clicked (for click events)
    bounce_reason = db.Column(db.String(255))  # Bounce reason
    bounce_type = db.Column(db.String(50))  # hard, soft
    
    # Timestamps
    event_timestamp = db.Column(db.DateTime, nullable=False, index=True)  # When event occurred
    received_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)  # When we received it
    processed_at = db.Column(db.DateTime)  # When we processed it
    
    # Relationships
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
            'provider': self.provider,
            'provider_message_id': self.provider_message_id,
            'event_data': self.event_data,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'clicked_url': self.clicked_url,
            'bounce_reason': self.bounce_reason,
            'bounce_type': self.bounce_type,
            'event_timestamp': self.event_timestamp.isoformat() if self.event_timestamp else None,
            'received_at': self.received_at.isoformat() if self.received_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
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
        
        # This week's emails (last 7 days) - simplified for SQLite
        from datetime import timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        emails_this_week = Email.query.filter(Email.sent_at >= week_ago).count()
        
        # Response rate calculation
        responses_this_week = Email.query.filter(
            Email.sent_at >= week_ago,
            Email.replied_at.isnot(None)
        ).count()
        
        response_rate = round((responses_this_week / emails_this_week * 100), 2) if emails_this_week > 0 else 0
        
        # Hot leads (responses requiring action)
        hot_leads = db.session.query(Response).join(Email).filter(
            Response.action_required == True,
            Response.response_type == 'positive'
        ).count()
        
        # Email delivery metrics
        delivered_count = Email.query.filter(Email.status == 'delivered').count()
        opened_count = Email.query.filter(Email.opened_at.isnot(None)).count()
        bounced_count = Email.query.filter(Email.status == 'bounced').count()
        
        # Total sent emails for rate calculations
        total_sent = Email.query.filter(Email.sent_at.isnot(None)).count()
        
        # Calculate delivery rates
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
        # Return default stats if database error
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


# ===== A/B TESTING MODELS =====

class ABTest(db.Model):
    """A/B Test configuration and management"""
    __tablename__ = 'ab_tests'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    # Test configuration
    test_type = db.Column(db.String(50), nullable=False)  # 'subject', 'content', 'send_time', 'sender', 'cta'
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('email_templates.id'))

    # Test settings
    traffic_split = db.Column(db.Float, default=50.0)  # Percentage for variant A (B gets 100-A)
    sample_size = db.Column(db.Integer, default=100)   # Total contacts to include
    confidence_level = db.Column(db.Float, default=95.0)  # 95% confidence

    # Status and timing
    status = db.Column(db.String(20), default='draft')  # draft, running, completed, paused
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    winner_declared_at = db.Column(db.DateTime)
    winning_variant = db.Column(db.String(1))  # 'A' or 'B'

    # Results
    statistical_significance = db.Column(db.Float)
    primary_metric = db.Column(db.String(50), default='open_rate')  # open_rate, click_rate, response_rate

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    campaign = db.relationship('Campaign', backref='ab_tests')
    template = db.relationship('EmailTemplate', backref='ab_tests')
    variants = db.relationship('ABTestVariant', backref='ab_test', cascade='all, delete-orphan')
    assignments = db.relationship('ABTestAssignment', backref='ab_test', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'test_type': self.test_type,
            'status': self.status,
            'traffic_split': self.traffic_split,
            'sample_size': self.sample_size,
            'primary_metric': self.primary_metric,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'winning_variant': self.winning_variant,
            'statistical_significance': self.statistical_significance,
            'created_at': self.created_at.isoformat()
        }


class ABTestVariant(db.Model):
    """A/B Test variants (A and B versions)"""
    __tablename__ = 'ab_test_variants'

    id = db.Column(db.Integer, primary_key=True)
    ab_test_id = db.Column(db.Integer, db.ForeignKey('ab_tests.id'), nullable=False)
    variant_name = db.Column(db.String(1), nullable=False)  # 'A' or 'B'

    # Variant content (what's being tested)
    subject_line = db.Column(db.String(500))
    email_body_html = db.Column(db.Text)
    email_body_text = db.Column(db.Text)
    sender_name = db.Column(db.String(100))
    sender_email = db.Column(db.String(255))
    cta_text = db.Column(db.String(200))
    send_time_offset = db.Column(db.Integer, default=0)  # Hours offset from base send time

    # Performance metrics
    emails_sent = db.Column(db.Integer, default=0)
    emails_delivered = db.Column(db.Integer, default=0)
    emails_opened = db.Column(db.Integer, default=0)
    emails_clicked = db.Column(db.Integer, default=0)
    emails_replied = db.Column(db.Integer, default=0)
    emails_bounced = db.Column(db.Integer, default=0)
    emails_unsubscribed = db.Column(db.Integer, default=0)

    # Calculated rates (updated periodically)
    delivery_rate = db.Column(db.Float, default=0.0)
    open_rate = db.Column(db.Float, default=0.0)
    click_rate = db.Column(db.Float, default=0.0)
    response_rate = db.Column(db.Float, default=0.0)
    unsubscribe_rate = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def calculate_rates(self):
        """Calculate and update performance rates"""
        if self.emails_sent > 0:
            self.delivery_rate = round((self.emails_delivered / self.emails_sent) * 100, 2)
            self.unsubscribe_rate = round((self.emails_unsubscribed / self.emails_sent) * 100, 2)

        if self.emails_delivered > 0:
            self.open_rate = round((self.emails_opened / self.emails_delivered) * 100, 2)
            self.click_rate = round((self.emails_clicked / self.emails_delivered) * 100, 2)
            self.response_rate = round((self.emails_replied / self.emails_delivered) * 100, 2)

        self.updated_at = datetime.utcnow()

    def to_dict(self):
        return {
            'id': self.id,
            'variant_name': self.variant_name,
            'subject_line': self.subject_line,
            'sender_name': self.sender_name,
            'emails_sent': self.emails_sent,
            'emails_delivered': self.emails_delivered,
            'delivery_rate': self.delivery_rate,
            'open_rate': self.open_rate,
            'click_rate': self.click_rate,
            'response_rate': self.response_rate,
            'unsubscribe_rate': self.unsubscribe_rate
        }


class ABTestAssignment(db.Model):
    """Contact assignments to A/B test variants"""
    __tablename__ = 'ab_test_assignments'

    id = db.Column(db.Integer, primary_key=True)
    ab_test_id = db.Column(db.Integer, db.ForeignKey('ab_tests.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('ab_test_variants.id'), nullable=False)
    variant_name = db.Column(db.String(1), nullable=False)  # 'A' or 'B' for quick lookup

    # Assignment tracking
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    email_sent = db.Column(db.Boolean, default=False)
    email_sent_at = db.Column(db.DateTime)

    # Email performance for this contact
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'))  # Link to sent email
    delivered = db.Column(db.Boolean, default=False)
    opened = db.Column(db.Boolean, default=False)
    clicked = db.Column(db.Boolean, default=False)
    replied = db.Column(db.Boolean, default=False)
    bounced = db.Column(db.Boolean, default=False)
    unsubscribed = db.Column(db.Boolean, default=False)

    # Relationships
    contact = db.relationship('Contact', backref='ab_test_assignments')
    variant = db.relationship('ABTestVariant', backref='assignments')
    email = db.relationship('Email', backref='ab_test_assignment')

    def to_dict(self):
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'variant_name': self.variant_name,
            'email_sent': self.email_sent,
            'delivered': self.delivered,
            'opened': self.opened,
            'clicked': self.clicked,
            'replied': self.replied,
            'assigned_at': self.assigned_at.isoformat()
        }