from marshmallow import Schema, fields, ValidationError, validates, validates_schema
from utils.phone import normalize_to_e164

class ContactSchema(Schema):
    """Schema for validating contact data."""
    name = fields.Str(required=True, error_messages={
        'required': 'Contact name is required'
    })
    whatsapp_number = fields.Str(required=True, error_messages={
        'required': 'WhatsApp number is required'
    })
    group_id = fields.Int(required=False, allow_none=True)
    
    @validates('name')
    def validate_name(self, value):
        if not value or not value.strip():
            raise ValidationError('Name cannot be empty')
        if len(value) > 100:
            raise ValidationError('Name cannot exceed 100 characters')
    
    @validates('whatsapp_number')
    def validate_whatsapp_number(self, value):
        try:
            # Normalize the phone number
            normalized = normalize_to_e164(value)
            return normalized
        except ValueError as e:
            raise ValidationError(str(e))

class MessageSchema(Schema):
    """Schema for validating message data."""
    contact_id = fields.Int(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True)
    message = fields.Str(required=True, error_messages={
        'required': 'Message content is required'
    })
    
    @validates_schema
    def validate_recipient(self, data, **kwargs):
        if not data.get('contact_id') and not data.get('phone'):
            raise ValidationError(
                'Either contact_id or phone number must be provided'
            )
    
    @validates('phone')
    def validate_phone(self, value):
        if value:
            try:
                normalized = normalize_to_e164(value)
                return normalized
            except ValueError as e:
                raise ValidationError(str(e))
    
    @validates('message')
    def validate_message(self, value):
        if not value or not value.strip():
            raise ValidationError('Message cannot be empty')
        if len(value) > 4096:  # WhatsApp message limit
            raise ValidationError('Message cannot exceed 4096 characters')

class BulkMessageSchema(Schema):
    """Schema for validating bulk message data."""
    group_id = fields.Int(required=True, error_messages={
        'required': 'Group ID is required for bulk sending'
    })
    message = fields.Str(required=True, error_messages={
        'required': 'Message content is required'
    })
    
    @validates('message')
    def validate_message(self, value):
        if not value or not value.strip():
            raise ValidationError('Message cannot be empty')
        if len(value) > 4096:
            raise ValidationError('Message cannot exceed 4096 characters')

class ScheduleSchema(Schema):
    """Schema for validating schedule requests."""
    type = fields.Str(required=True)  # 'individual' or 'group'
    schedule_type = fields.Str(required=True)  # 'once' or 'cron'
    message = fields.Str(required=True)

    # Individual
    contact_id = fields.Int(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True)

    # Group
    group_id = fields.Int(required=False, allow_none=True)

    # Scheduling
    run_at = fields.Str(required=False, allow_none=True)  # ISO string from client
    cron = fields.Str(required=False, allow_none=True)

    @validates_schema
    def validate_schedule(self, data, **kwargs):
        t = (data.get('type') or '').lower()
        st = (data.get('schedule_type') or '').lower()

        if t not in ('individual', 'group'):
            raise ValidationError('type must be "individual" or "group"')
        if st not in ('once', 'cron'):
            raise ValidationError('schedule_type must be "once" or "cron"')

        if t == 'individual':
            if not data.get('contact_id') and not data.get('phone'):
                raise ValidationError('For individual type, provide contact_id or phone')
        elif t == 'group':
            if not data.get('group_id'):
                raise ValidationError('For group type, provide group_id')

        if st == 'once':
            if not data.get('run_at'):
                raise ValidationError('run_at is required for one-time schedules')
        elif st == 'cron':
            if not data.get('cron'):
                raise ValidationError('cron expression is required for cron schedules')
