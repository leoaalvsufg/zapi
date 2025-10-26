from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Group(db.Model):
    """Model for contact groups."""
    __tablename__ = 'groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    contacts = db.relationship('Contact', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Group {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'contact_count': self.contacts.count()
        }

class Contact(db.Model):
    """Model for contacts."""
    __tablename__ = 'contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    whatsapp_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    messages = db.relationship('Message', backref='contact', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Contact {self.name} ({self.whatsapp_number})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'whatsapp_number': self.whatsapp_number,
            'group_id': self.group_id,
            'group_name': self.group.name if self.group else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Message(db.Model):
    """Model for sent messages."""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)
    phone_number = db.Column(db.String(20))  # For messages sent to non-contacts
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # success, failed, queued, pending
    provider = db.Column(db.String(50), default='z-api')
    provider_message_id = db.Column(db.String(100))
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        contact_info = f"Contact {self.contact_id}" if self.contact_id else self.phone_number
        return f'<Message to {contact_info} - {self.status}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'contact_name': self.contact.name if self.contact else None,
            'phone_number': self.phone_number or (self.contact.whatsapp_number if self.contact else None),
            'content': self.content,
            'status': self.status,
            'provider': self.provider,
            'provider_message_id': self.provider_message_id,
            'error': self.error,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ScheduledMessage(db.Model):
    """Model for scheduled messages (one-time or cron)."""
    __tablename__ = 'scheduled_messages'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(64), unique=True, index=True)
    type = db.Column(db.String(20), nullable=False)  # individual or group
    schedule_type = db.Column(db.String(20), nullable=False)  # once or cron

    # Targets
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)
    
    # Relationships
    contact = db.relationship('Contact', backref='scheduled_messages')
    group = db.relationship('Group', backref='scheduled_messages')

    # Content
    message = db.Column(db.Text, nullable=False)

    # Scheduling
    run_at = db.Column(db.DateTime, nullable=True, index=True)  # for one-time
    cron_expression = db.Column(db.String(100), nullable=True)  # for cron

    # Status
    status = db.Column(db.String(20), default='scheduled', index=True)  # scheduled, running, completed, canceled, failed
    last_run_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ScheduledMessage {self.id} {self.schedule_type} {self.status}>'

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'type': self.type,
            'schedule_type': self.schedule_type,
            'contact_id': self.contact_id,
            'phone_number': self.phone_number,
            'group_id': self.group_id,
            'message': self.message,
            'run_at': self.run_at.isoformat() if self.run_at else None,
            'cron_expression': self.cron_expression,
            'status': self.status,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Setting(db.Model):
    """Simple key-value settings storage."""
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Setting {self.key}>'

    def to_dict(self):
        return {'key': self.key, 'value': self.value}
