from typing import Optional, Dict, Any, List
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from models import db, Setting
from config import Config

ZAPI_KEYS = [
    'ZAPI_INSTANCE_ID',
    'ZAPI_INSTANCE_TOKEN',
    'ZAPI_SEND_TEXT_URL',
    'ZAPI_CLIENT_TOKEN',
]

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    s = Setting.query.filter_by(key=key).first()
    return s.value if s else default


def set_settings(data: Dict[str, Any]) -> None:
    for k, v in data.items():
        s = Setting.query.filter_by(key=k).first()
        if s:
            s.value = v
        else:
            db.session.add(Setting(key=k, value=v))
    db.session.commit()


def get_settings(keys: Optional[List[str]] = None) -> Dict[str, Optional[str]]:
    q = Setting.query
    if keys:
        q = q.filter(Setting.key.in_(keys))
    rows = q.all()
    out = {r.key: r.value for r in rows}
    if keys:
        for k in keys:
            out.setdefault(k, None)
    return out


def get_effective_zapi_config() -> Dict[str, Optional[str]]:
    """Get runtime Z-API config preferring DB settings, fallback to env Config."""
    db_vals = get_settings(ZAPI_KEYS)
    instance_id = db_vals.get('ZAPI_INSTANCE_ID') or Config.ZAPI_INSTANCE_ID
    instance_token = db_vals.get('ZAPI_INSTANCE_TOKEN') or Config.ZAPI_INSTANCE_TOKEN
    send_text_url = db_vals.get('ZAPI_SEND_TEXT_URL') or Config.ZAPI_SEND_TEXT_URL

    if not send_text_url and instance_id and instance_token:
        send_text_url = (
            f"https://api.z-api.io/instances/{instance_id}/token/{instance_token}/send-text"
        )

    client_token = db_vals.get('ZAPI_CLIENT_TOKEN') or getattr(Config, 'ZAPI_CLIENT_TOKEN', None)

    return {
        'instance_id': instance_id,
        'instance_token': instance_token,
        'send_text_url': send_text_url,
        'client_token': client_token,
    }
