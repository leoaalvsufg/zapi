import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from flask import current_app, Flask

from models import db, ScheduledMessage
from services.messaging import get_messaging_service

# Global scheduler instance
scheduler: Optional[BackgroundScheduler] = None
# Keep a reference to the Flask app to create app contexts in background threads
_flask_app: Optional[Flask] = None


def init_scheduler(app) -> None:
    """Initialize and start the APScheduler, restore pending jobs from DB."""
    global scheduler, _flask_app
    if scheduler is None:
        scheduler = BackgroundScheduler()
        scheduler.start()
        logger.info("APScheduler started")

    # Keep app reference for background jobs
    _flask_app = app

    # Attach to app for reference
    app.extensions = getattr(app, 'extensions', {})
    app.extensions['scheduler'] = scheduler

    with app.app_context():
        restore_pending_jobs()


def restore_pending_jobs() -> None:
    """Restore pending scheduled jobs from the database into the scheduler."""
    pending: List[ScheduledMessage] = (
        ScheduledMessage.query.filter(ScheduledMessage.status == 'scheduled').all()
    )
    restored = 0
    for sched in pending:
        try:
            if sched.schedule_type == 'once' and sched.run_at:
                # Skip past-due one-time schedules, mark failed
                if sched.run_at <= datetime.utcnow():
                    sched.status = 'failed'
                    continue
                _add_date_job(sched)
                restored += 1
            elif sched.schedule_type == 'cron' and sched.cron_expression:
                _add_cron_job(sched)
                restored += 1
        except Exception:
            logger.exception(f"Failed to restore schedule {sched.id}")
            sched.status = 'failed'
    db.session.commit()
    logger.info(f"Restored {restored} scheduled jobs")


def _add_date_job(sched: ScheduledMessage) -> None:
    assert scheduler is not None
    scheduler.add_job(
        func=run_send_job,
        trigger=DateTrigger(run_date=sched.run_at),
        id=sched.job_id,
        kwargs={'scheduled_id': sched.id},
        replace_existing=True,
        misfire_grace_time=60,
        coalesce=True,
        max_instances=1,
    )


def _parse_cron_expression(expr: str) -> CronTrigger:
    parts = [p.strip() for p in expr.split()]  # standard 5-field cron
    if len(parts) != 5:
        raise ValueError("Cron expression must have 5 fields: minute hour day month day_of_week")
    minute, hour, day, month, day_of_week = parts
    return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)


def _add_cron_job(sched: ScheduledMessage) -> None:
    assert scheduler is not None
    trigger = _parse_cron_expression(sched.cron_expression)
    scheduler.add_job(
        func=run_send_job,
        trigger=trigger,
        id=sched.job_id,
        kwargs={'scheduled_id': sched.id},
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


def run_send_job(scheduled_id: int) -> None:
    """Job function that performs the actual send using MessagingService."""
    # Ensure we have a Flask app context even when running in APScheduler threads
    app_obj: Optional[Flask] = _flask_app
    if app_obj is None:
        # Fallback: try current_app if available
        try:
            app_obj = current_app  # type: ignore[assignment]
        except Exception:
            app_obj = None
    if app_obj is None:
        logger.error("No Flask app context available for scheduler job; aborting run_send_job")
        return
    with app_obj.app_context():
        sched: Optional[ScheduledMessage] = ScheduledMessage.query.get(scheduled_id)
        if not sched:
            logger.error(f"ScheduledMessage {scheduled_id} not found")
            return

        messaging = get_messaging_service()
        try:
            # Update status for one-time jobs
            if sched.schedule_type == 'once':
                sched.status = 'running'
                db.session.commit()

            if sched.type == 'individual':
                if sched.contact_id:
                    result = messaging.send_to_contact(sched.contact_id, sched.message)
                    success = result.get('success', False)
                else:
                    result = messaging.send_to_contact(sched.phone_number, sched.message)
                    success = result.get('success', False)
            elif sched.type == 'group':
                results = messaging.send_bulk_by_group(sched.group_id, sched.message, sleep_between_secs=3.0)
                success = all(r.get('success') for r in results if isinstance(r, dict) and 'success' in r)
            else:
                success = False

            sched.last_run_at = datetime.utcnow()
            if sched.schedule_type == 'once':
                sched.status = 'completed' if success else 'failed'
                # Remove job after completion
                try:
                    if scheduler:
                        scheduler.remove_job(sched.job_id)
                except Exception:
                    logger.warning(f"Could not remove job {sched.job_id} after completion")
            # For cron jobs, keep as scheduled
            db.session.commit()
        except Exception:
            logger.exception(f"Error executing scheduled job {sched.id}")
            sched.last_run_at = datetime.utcnow()
            if sched.schedule_type == 'once':
                sched.status = 'failed'
            db.session.commit()


def schedule_message_once(
    *,
    type: str,
    message: str,
    run_at: datetime,
    contact_id: Optional[int] = None,
    phone_number: Optional[str] = None,
    group_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Schedule a one-time message."""
    job_id = uuid.uuid4().hex

    sched = ScheduledMessage(
        job_id=job_id,
        type=type,
        schedule_type='once',
        contact_id=contact_id,
        phone_number=phone_number,
        group_id=group_id,
        message=message,
        run_at=run_at,
        status='scheduled',
    )
    db.session.add(sched)
    db.session.commit()

    _add_date_job(sched)

    return sched.to_dict()


def schedule_message_cron(
    *,
    type: str,
    message: str,
    cron_expression: str,
    contact_id: Optional[int] = None,
    phone_number: Optional[str] = None,
    group_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Schedule a recurring message using cron expression."""
    # Validate cron expression
    _ = _parse_cron_expression(cron_expression)

    job_id = uuid.uuid4().hex

    sched = ScheduledMessage(
        job_id=job_id,
        type=type,
        schedule_type='cron',
        contact_id=contact_id,
        phone_number=phone_number,
        group_id=group_id,
        message=message,
        cron_expression=cron_expression,
        status='scheduled',
    )
    db.session.add(sched)
    db.session.commit()

    _add_cron_job(sched)

    return sched.to_dict()


def list_schedules() -> List[Dict[str, Any]]:
    items = ScheduledMessage.query.order_by(ScheduledMessage.created_at.desc()).all()
    return [i.to_dict() for i in items]


def update_schedule(
    schedule_id: int,
    *,
    message: Optional[str] = None,
    schedule_type: Optional[str] = None,
    run_at: Optional[datetime] = None,
    cron_expression: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update an existing schedule and refresh the APScheduler job."""
    sched: Optional[ScheduledMessage] = ScheduledMessage.query.get(schedule_id)
    if not sched:
        return None

    # Convert run_at from string if necessary
    if isinstance(run_at, str) and run_at:
        try:
            run_at = datetime.fromisoformat(run_at)
        except Exception:
            raise ValueError('Invalid run_at format. Use ISO datetime (YYYY-MM-DDTHH:MM)')

    # Apply updates
    if message is not None:
        sched.message = message

    if schedule_type is not None and schedule_type in ('once', 'cron'):
        sched.schedule_type = schedule_type
        # Clear fields not relevant
        if schedule_type == 'once':
            sched.cron_expression = None
        else:
            sched.run_at = None

    if sched.schedule_type == 'once':
        if run_at is not None:
            sched.run_at = run_at
        if not sched.run_at or sched.run_at <= datetime.utcnow():
            raise ValueError('run_at must be a future datetime for one-time schedules')
    else:
        if cron_expression is not None:
            # Validate cron expression
            _ = _parse_cron_expression(cron_expression)
            sched.cron_expression = cron_expression
        if not sched.cron_expression:
            raise ValueError('cron_expression is required for cron schedules')

    db.session.commit()

    # Refresh scheduler job
    try:
        if scheduler and sched.job_id:
            try:
                scheduler.remove_job(sched.job_id)
            except Exception:
                pass
        if sched.status == 'scheduled':
            if sched.schedule_type == 'once':
                _add_date_job(sched)
            else:
                _add_cron_job(sched)
        elif sched.status == 'paused':
            # Keep it out of active scheduler
            pass
    except Exception:
        logger.exception(f"Error refreshing scheduler job for schedule {schedule_id}")

    return sched.to_dict()


def cancel_schedule(schedule_id: int) -> bool:
    sched: Optional[ScheduledMessage] = ScheduledMessage.query.get(schedule_id)
    if not sched:
        return False
    # Try to remove from scheduler
    try:
        if scheduler and sched.job_id:
            scheduler.remove_job(sched.job_id)
    except Exception:
        logger.warning(f"Could not remove job {sched.job_id} from scheduler during cancel")
    # Mark as canceled
    sched.status = 'canceled'
    db.session.commit()
    return True


def pause_schedule(schedule_id: int) -> bool:
    """Pause a scheduled job without deleting it (primarily for cron jobs)."""
    sched: Optional[ScheduledMessage] = ScheduledMessage.query.get(schedule_id)
    if not sched:
        return False
    try:
        if scheduler and sched.job_id:
            try:
                scheduler.pause_job(sched.job_id)
            except Exception:
                # If job not found, we'll just mark as paused in DB
                pass
        sched.status = 'paused'
        db.session.commit()
        return True
    except Exception:
        logger.exception(f"Error pausing schedule {schedule_id}")
        db.session.rollback()
        return False


essential_cron_statuses = {'scheduled', 'paused'}

def resume_schedule(schedule_id: int) -> bool:
    """Resume a paused scheduled job. Re-add it to scheduler if missing."""
    sched: Optional[ScheduledMessage] = ScheduledMessage.query.get(schedule_id)
    if not sched:
        return False
    try:
        if scheduler and sched.job_id:
            try:
                # Try resume if it exists
                scheduler.resume_job(sched.job_id)
            except Exception:
                # If not present, re-add depending on type
                if sched.schedule_type == 'cron' and sched.cron_expression:
                    _add_cron_job(sched)
                elif sched.schedule_type == 'once' and sched.run_at and sched.run_at > datetime.utcnow():
                    _add_date_job(sched)
                else:
                    # Cannot resume an expired one-time schedule
                    logger.warning(f"Cannot resume schedule {schedule_id}: invalid timing or missing trigger")
                    return False
        else:
            # No scheduler or job id; try to re-add
            if sched.schedule_type == 'cron' and sched.cron_expression:
                _add_cron_job(sched)
            elif sched.schedule_type == 'once' and sched.run_at and sched.run_at > datetime.utcnow():
                _add_date_job(sched)
            else:
                logger.warning(f"Cannot resume schedule {schedule_id}: invalid timing or missing trigger")
                return False
        sched.status = 'scheduled'
        db.session.commit()
        return True
    except Exception:
        logger.exception(f"Error resuming schedule {schedule_id}")
        db.session.rollback()
        return False
