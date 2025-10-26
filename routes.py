from flask import Blueprint, render_template, request, jsonify, current_app, url_for, abort
from datetime import datetime, timedelta
from marshmallow import ValidationError
from loguru import logger
from models import db, Contact, Group, Message, ScheduledMessage
from utils.validators import ContactSchema, MessageSchema, BulkMessageSchema, ScheduleSchema
from utils.phone import normalize_to_e164
from services.messaging import get_messaging_service
from services.ai import get_ai_service
from services.scheduler import schedule_message_once, schedule_message_cron, list_schedules, cancel_schedule, pause_schedule, resume_schedule, update_schedule
from services.settings_service import get_settings as get_app_settings, set_settings as save_app_settings, ZAPI_KEYS
from config import Config
from functools import wraps
from itsdangerous import URLSafeSerializer, BadSignature

main_bp = Blueprint('main', __name__)

# ----- Public contact form (invite link) helpers -----
def _invite_serializer():
    return URLSafeSerializer(Config.SECRET_KEY, salt='group-invite')

def generate_group_token(group_id: int) -> str:
    s = _invite_serializer()
    return s.dumps({'gid': int(group_id)})

def verify_group_token(token: str) -> int:
    try:
        s = _invite_serializer()
        data = s.loads(token)
        gid = int(data.get('gid'))
        return gid
    except (BadSignature, Exception):
        abort(404)


# Web Pages
@main_bp.route('/')
def dashboard():
    """Dashboard with metrics."""
    # Get metrics
    total_contacts = Contact.query.count()
    total_groups = Group.query.count()
    
    # Messages sent today
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    messages_today = Message.query.filter(Message.created_at >= today_start).count()
    
    # Recent messages
    recent_messages = Message.query.order_by(Message.created_at.desc()).limit(10).all()
    
    return render_template('dashboard.html',
                         total_contacts=total_contacts,
                         total_groups=total_groups,
                         messages_today=messages_today,
                         recent_messages=recent_messages)

@main_bp.route('/contacts')
def contacts_page():
    """Contacts management page."""
    return render_template('contacts.html')

@main_bp.route('/groups')
def groups_page():
    """Groups management page."""
    return render_template('groups.html')

@main_bp.route('/send')
def send_page():
    """Send messages page."""
    return render_template('send.html')

@main_bp.route('/history')
def history_page():
    """Message history page."""
    return render_template('history.html')

@main_bp.route('/cron')
def cron_page():
    """Cron schedules management page."""
    return render_template('cron.html')

@main_bp.route('/settings')
def settings_page():
    """Application settings page."""
    return render_template('settings.html')

# API Endpoints

# Contacts API
@main_bp.route('/api/contacts', methods=['GET'])
def get_contacts():
    """Get all contacts."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        
        query = Contact.query
        if search:
            query = query.filter(
                db.or_(
                    Contact.name.contains(search),
                    Contact.whatsapp_number.contains(search)
                )
            )
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'contacts': [c.to_dict() for c in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })
    except Exception as e:
        logger.exception("Error fetching contacts")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/contacts', methods=['POST'])
def create_contact():
    """Create a new contact."""
    try:
        schema = ContactSchema()
        data = schema.load(request.json)
        
        # Check if number already exists
        existing = Contact.query.filter_by(whatsapp_number=data['whatsapp_number']).first()
        if existing:
            return jsonify({'success': False, 'error': 'Contact with this number already exists'}), 400
        
        contact = Contact(
            name=data['name'],
            whatsapp_number=data['whatsapp_number'],
            group_id=data.get('group_id')
        )
        
        db.session.add(contact)
        db.session.commit()
        
        return jsonify({'success': True, 'contact': contact.to_dict()}), 201
        
    except ValidationError as e:
        return jsonify({'success': False, 'errors': e.messages}), 400
    except Exception as e:
        logger.exception("Error creating contact")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/contacts/<int:contact_id>', methods=['PUT', 'PATCH'])
def update_contact(contact_id):
    """Update a contact."""
    try:
        contact = Contact.query.get_or_404(contact_id)
        
        schema = ContactSchema(partial=True)
        data = schema.load(request.json)
        
        if 'name' in data:
            contact.name = data['name']
        if 'whatsapp_number' in data:
            # Check if new number already exists
            existing = Contact.query.filter(
                Contact.whatsapp_number == data['whatsapp_number'],
                Contact.id != contact_id
            ).first()
            if existing:
                return jsonify({'success': False, 'error': 'Another contact with this number already exists'}), 400
            contact.whatsapp_number = data['whatsapp_number']
        if 'group_id' in data:
            contact.group_id = data['group_id']
        
        db.session.commit()
        
        return jsonify({'success': True, 'contact': contact.to_dict()})
        
    except ValidationError as e:
        return jsonify({'success': False, 'errors': e.messages}), 400
    except Exception as e:
        logger.exception("Error updating contact")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    """Delete a contact."""
    try:
        contact = Contact.query.get_or_404(contact_id)
        db.session.delete(contact)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Contact deleted successfully'})
        
    except Exception as e:
        logger.exception("Error deleting contact")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Groups API
@main_bp.route('/api/groups', methods=['GET'])
def get_groups():
    """Get all groups."""
    try:
        groups = Group.query.all()
        return jsonify({
            'success': True,
            'groups': [g.to_dict() for g in groups]
        })
    except Exception as e:
        logger.exception("Error fetching groups")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/groups', methods=['POST'])
def create_group():
    """Create a new group."""
    try:
        data = request.json
        
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Group name is required'}), 400
        
        # Check if group name already exists
        existing = Group.query.filter_by(name=data['name']).first()
        if existing:
            return jsonify({'success': False, 'error': 'Group with this name already exists'}), 400
        
        group = Group(
            name=data['name'],
            description=data.get('description', '')
        )
        
        db.session.add(group)
        db.session.commit()
        
        return jsonify({'success': True, 'group': group.to_dict()}), 201
        
    except Exception as e:
        logger.exception("Error creating group")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/groups/<int:group_id>', methods=['DELETE'])
def delete_group(group_id):
    """Delete a group."""
    try:
        group = Group.query.get_or_404(group_id)
        db.session.delete(group)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Group deleted successfully'})
        
    except Exception as e:
        logger.exception("Error deleting group")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Messaging API
@main_bp.route('/api/send', methods=['POST'])
def send_message():
    """Send a single message."""
    try:
        schema = MessageSchema()
        data = schema.load(request.json)
        
        messaging = get_messaging_service()
        
        # Determine recipient
        if data.get('contact_id'):
            result = messaging.send_to_contact(data['contact_id'], data['message'])
        else:
            result = messaging.send_to_contact(data['phone'], data['message'])
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except ValidationError as e:
        return jsonify({'success': False, 'errors': e.messages}), 400
    except Exception as e:
        logger.exception("Error sending message")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/send-bulk', methods=['POST'])
def send_bulk_message():
    """Send messages to all contacts in a group."""
    try:
        schema = BulkMessageSchema()
        data = schema.load(request.json)
        
        messaging = get_messaging_service()
        
        # Start async bulk send
        job_id = messaging.send_bulk_async(
            data['group_id'],
            data['message'],
            sleep_between_secs=3.0  # Adjust based on your rate limits
        )
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Bulk send started'
        })
        
    except ValidationError as e:
        return jsonify({'success': False, 'errors': e.messages}), 400
    except Exception as e:
        logger.exception("Error starting bulk send")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/jobs/<job_id>/status', methods=['GET'])
def get_job_status(job_id):
    """Get the status of a bulk send job."""
    try:
        messaging = get_messaging_service()
        status = messaging.get_job_status(job_id)
        
        if status:
            return jsonify({'success': True, 'job': status})
        else:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
            
    except Exception as e:
        logger.exception("Error getting job status")
        return jsonify({'success': False, 'error': str(e)}), 500

# AI Compose API
@main_bp.route('/api/ai/compose', methods=['POST'])
def compose_with_ai():
    """Compose a message using AI."""
    try:
        data = request.json
        
        if not data.get('topic'):
            return jsonify({'success': False, 'error': 'Topic is required'}), 400
        
        ai_service = get_ai_service()
        
        result = ai_service.compose_message(
            topic=data['topic'],
            tone=data.get('tone', 'friendly'),
            placeholders=data.get('placeholders'),
            provider=data.get('provider', 'openrouter')
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.exception("Error composing message with AI")
        return jsonify({'success': False, 'error': str(e)}), 500

# Scheduling API
@main_bp.route('/api/schedule', methods=['POST'])
def schedule_message():
    """Schedule a message (individual or group) for later or recurring via cron."""
    try:
        schema = ScheduleSchema()
        data = schema.load(request.json)

        t = data['type']
        st = data['schedule_type']
        message = data['message']

        if st == 'once':
            # Expect run_at in 'YYYY-MM-DDTHH:MM' format (datetime-local)
            run_at_str = data['run_at']
            try:
                run_at = datetime.fromisoformat(run_at_str)
            except Exception:
                return jsonify({'success': False, 'error': 'Invalid run_at format. Use ISO datetime (YYYY-MM-DDTHH:MM)'}), 400

            if t == 'individual':
                result = schedule_message_once(
                    type='individual',
                    message=message,
                    run_at=run_at,
                    contact_id=data.get('contact_id'),
                    phone_number=data.get('phone')
                )
            else:
                result = schedule_message_once(
                    type='group',
                    message=message,
                    run_at=run_at,
                    group_id=data.get('group_id')
                )
        else:  # cron
            cron = data['cron']
            if t == 'individual':
                result = schedule_message_cron(
                    type='individual',
                    message=message,
                    cron_expression=cron,
                    contact_id=data.get('contact_id'),
                    phone_number=data.get('phone')
                )
            else:
                result = schedule_message_cron(
                    type='group',
                    message=message,
                    cron_expression=cron,
                    group_id=data.get('group_id')
                )

        return jsonify({'success': True, 'schedule': result}), 201

    except ValidationError as e:
        return jsonify({'success': False, 'errors': e.messages}), 400
    except Exception as e:
        logger.exception("Error scheduling message")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/schedules', methods=['GET'])
def get_schedules():
    """List all schedules with target details."""
    try:
        schedules = ScheduledMessage.query.order_by(ScheduledMessage.created_at.desc()).all()
        out = []
        for s in schedules:
            d = s.to_dict()
            # Enrich with target details
            if s.type == 'individual':
                if s.contact_id and s.contact:
                    d['target'] = {'type': 'contact', 'name': s.contact.name, 'number': s.contact.whatsapp_number}
                else:
                    d['target'] = {'type': 'phone', 'name': None, 'number': s.phone_number}
            elif s.type == 'group':
                if s.group_id and s.group:
                    d['target'] = {'type': 'group', 'name': s.group.name, 'number': None}
                else:
                    d['target'] = {'type': 'group', 'name': None, 'number': None}
            out.append(d)
        return jsonify({'success': True, 'schedules': out})
    except Exception as e:
        logger.exception("Error listing schedules")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Cancel a scheduled message."""
    try:
        ok = cancel_schedule(schedule_id)
        if ok:
            return jsonify({'success': True, 'message': 'Schedule canceled'})
        return jsonify({'success': False, 'error': 'Schedule not found'}), 404
    except Exception as e:
        logger.exception("Error canceling schedule")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/schedules/<int:schedule_id>/pause', methods=['POST'])
def pause_schedule_api(schedule_id):
    try:
        ok = pause_schedule(schedule_id)
        if ok:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Schedule not found or cannot pause'}), 400
    except Exception as e:
        logger.exception("Error pausing schedule")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/schedules/<int:schedule_id>/resume', methods=['POST'])
def resume_schedule_api(schedule_id):
    try:
        ok = resume_schedule(schedule_id)
        if ok:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Schedule not found or cannot resume'}), 400
    except Exception as e:
        logger.exception("Error resuming schedule")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/schedules/<int:schedule_id>', methods=['PUT', 'PATCH'])
def update_schedule_api(schedule_id):
    try:
        payload = request.json or {}
        st = payload.get('schedule_type')
        if st and st not in ('once', 'cron'):
            return jsonify({'success': False, 'error': 'schedule_type must be once or cron'}), 400
        result = update_schedule(
            schedule_id,
            message=payload.get('message'),
            schedule_type=st,
            run_at=payload.get('run_at'),
            cron_expression=payload.get('cron') or payload.get('cron_expression')
        )
        if result:
            return jsonify({'success': True, 'schedule': result})
        return jsonify({'success': False, 'error': 'Schedule not found or not updated'}), 400
    except Exception as e:
        logger.exception('Error updating schedule')
        return jsonify({'success': False, 'error': str(e)}), 500

# Invite link API
@main_bp.route('/api/groups/<int:group_id>/invite-link', methods=['GET'])
def get_group_invite_link(group_id):
    try:
        group = Group.query.get_or_404(group_id)
        token = generate_group_token(group.id)
        link = url_for('main.public_contact_form', token=token, _external=True)
        return jsonify({'success': True, 'link': link, 'group': group.to_dict()})
    except Exception as e:
        logger.exception('Error generating invite link')
        return jsonify({'success': False, 'error': str(e)}), 500


# Z-API Overview for dashboard
@main_bp.route('/api/zapi/overview', methods=['GET'])
def zapi_overview():
    try:
        from services.zapi_client import get_client
        client = get_client()
        data = client.get_overview()
        return jsonify({'success': True, 'overview': data})
    except Exception as e:
        logger.exception('Error fetching Z-API overview')
        return jsonify({'success': False, 'error': str(e)}), 500


# Settings API
@main_bp.route('/api/settings', methods=['GET'])
def get_settings_api():
    try:
        data = get_app_settings(ZAPI_KEYS)
        return jsonify({'success': True, 'settings': data})
    except Exception as e:
        logger.exception('Error fetching settings')
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/settings', methods=['POST'])
def save_settings_api():
    try:
        payload = request.json or {}
        # Only accept known keys
        to_save = {k: v for k, v in payload.items() if k in ZAPI_KEYS}
        if not to_save:
            return jsonify({'success': False, 'error': 'No valid settings provided'}), 400
        save_app_settings(to_save)
        return jsonify({'success': True})
    except Exception as e:
        logger.exception('Error saving settings')
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Message History API
@main_bp.route('/api/messages', methods=['GET'])
def get_messages():
    """Get message history."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        contact_id = request.args.get('contact_id', type=int)
        
        query = Message.query
        
        if status:
            query = query.filter_by(status=status)
        if contact_id:
            query = query.filter_by(contact_id=contact_id)
        
        query = query.order_by(Message.created_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'messages': [m.to_dict() for m in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })
        
    except Exception as e:
        logger.exception("Error fetching messages")
        return jsonify({'success': False, 'error': str(e)}), 500


# ----- Public contact form (invite link) -----
@main_bp.route('/form/<token>', methods=['GET'])
def public_contact_form(token):
    gid = verify_group_token(token)
    group = Group.query.get_or_404(gid)
    return render_template('public_contact_form.html', group=group, token=token)

@main_bp.route('/form/<token>', methods=['POST'])
def public_contact_submit(token):
    gid = verify_group_token(token)
    group = Group.query.get_or_404(gid)

    # Accept application/x-www-form-urlencoded or JSON
    name = (request.form.get('name') or (request.json or {}).get('name') or '').strip()
    phone = (request.form.get('whatsapp_number') or (request.json or {}).get('whatsapp_number') or '').strip()

    if not name or not phone:
        err = 'Nome e WhatsApp são obrigatórios.'
        if request.is_json:
            return jsonify({'success': False, 'error': err}), 400
        return render_template('public_contact_form.html', group=group, token=token, error=err, name=name, whatsapp_number=phone), 400

    try:
        normalized_phone = normalize_to_e164(phone)
    except ValueError as e:
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 400
        return render_template('public_contact_form.html', group=group, token=token, error=str(e), name=name, whatsapp_number=phone), 400

    try:
        # Upsert contact by phone
        existing = Contact.query.filter_by(whatsapp_number=normalized_phone).first()
        if existing:
            existing.name = name
            if existing.group_id is None:
                existing.group_id = group.id
            db.session.commit()
            contact = existing
        else:
            contact = Contact(name=name, whatsapp_number=normalized_phone, group_id=group.id)
            db.session.add(contact)
            db.session.commit()

        if request.is_json:
            return jsonify({'success': True, 'contact': contact.to_dict(), 'message': 'Cadastro recebido com sucesso!'}), 201
        return render_template('public_contact_form.html', group=group, token=token, success=True)

    except Exception as e:
        logger.exception('Error saving public contact')
        db.session.rollback()
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        return render_template('public_contact_form.html', group=group, token=token, error='Erro ao salvar. Tente novamente mais tarde.'), 500
