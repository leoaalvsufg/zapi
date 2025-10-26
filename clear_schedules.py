#!/usr/bin/env python
"""Script para limpar todos os agendamentos e parar envios de mensagens."""

from app import create_app, db
from models import ScheduledMessage
from services.scheduler import scheduler
from loguru import logger

def clear_all_schedules():
    """Remove todos os agendamentos do banco e do scheduler."""
    app = create_app()
    
    with app.app_context():
        try:
            # Remover todos os jobs do scheduler
            if scheduler:
                try:
                    # Remover todos os jobs
                    jobs = scheduler.get_jobs()
                    for job in jobs:
                        logger.info(f"Removendo job: {job.id}")
                        scheduler.remove_job(job.id)
                    logger.info(f"Total de {len(jobs)} jobs removidos do scheduler")
                except Exception as e:
                    logger.error(f"Erro ao remover jobs do scheduler: {e}")
                
                try:
                    # Parar o scheduler
                    scheduler.shutdown(wait=False)
                    logger.info("Scheduler parado com sucesso")
                except Exception as e:
                    logger.error(f"Erro ao parar scheduler: {e}")
            
            # Limpar todos os agendamentos do banco
            schedules = ScheduledMessage.query.all()
            count = len(schedules)
            
            for schedule in schedules:
                logger.info(f"Removendo agendamento ID: {schedule.id}, Job ID: {schedule.job_id}")
                db.session.delete(schedule)
            
            db.session.commit()
            logger.info(f"Total de {count} agendamentos removidos do banco de dados")
            
            # Verificar se ainda há algum agendamento
            remaining = ScheduledMessage.query.count()
            if remaining == 0:
                logger.info("✓ Todos os agendamentos foram removidos com sucesso!")
            else:
                logger.warning(f"⚠ Ainda existem {remaining} agendamentos no banco")
                
        except Exception as e:
            logger.error(f"Erro ao limpar agendamentos: {e}")
            db.session.rollback()

if __name__ == "__main__":
    clear_all_schedules()