from __future__ import annotations

import logging
import os
from celery import Celery
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.repositories import DatabaseRepository
from app.services.agent_runner import AgentRunner

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize Celery bound to Redis
celery_app = Celery(
    "agent_platform",
    broker=settings.redis_url,
    backend=settings.redis_url
)

# Route tasks to specific queues
celery_app.conf.task_routes = {
    "app.core.celery_app.run_agent_task": {"queue": "agent_execution"},
    "app.core.celery_app.resume_agent_task": {"queue": "agent_execution"},
    "app.core.celery_app.indexing_task": {"queue": "indexing_tasks"},
    "app.core.celery_app.memory_task": {"queue": "memory_tasks"},
}

# General configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Task 1: Background Agent execution
@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3
)
def run_agent_task(self, run_id: str, thread_id: str, task: str) -> None:
    logger.info(f"Starting Celery task run_agent_task for run {run_id}", extra={"run_id": run_id, "event": "worker_task_start"})
    try:
        AgentRunner.run(run_id, thread_id, task)
        logger.info(f"Celery task run_agent_task completed successfully for run {run_id}", extra={"run_id": run_id, "event": "worker_task_success"})
    except Exception as exc:
        logger.error(f"Task run_agent_task failed: {exc}", exc_info=True, extra={"run_id": run_id, "event": "worker_task_failed"})
        
        # If we have exhausted all retries, flag the run status in database as failed
        if self.request.retries >= self.max_retries:
            db = SessionLocal()
            try:
                DatabaseRepository.update_run(db, run_id, status="failed", error=str(exc))
                logger.info(f"Marked run {run_id} as failed in database", extra={"run_id": run_id})
            finally:
                db.close()
                
        raise exc

# Task 2: Background Agent resumption
@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3
)
def resume_agent_task(self, run_id: str, thread_id: str, approved: bool, feedback: str | None) -> None:
    logger.info(f"Starting Celery task resume_agent_task for run {run_id}", extra={"run_id": run_id, "event": "worker_task_resume"})
    try:
        AgentRunner.resume(run_id, thread_id, approved, feedback)
        logger.info(f"Celery task resume_agent_task completed successfully for run {run_id}", extra={"run_id": run_id, "event": "worker_task_resume_success"})
    except Exception as exc:
        logger.error(f"Task resume_agent_task failed: {exc}", exc_info=True, extra={"run_id": run_id, "event": "worker_task_resume_failed"})
        
        if self.request.retries >= self.max_retries:
            db = SessionLocal()
            try:
                DatabaseRepository.update_run(db, run_id, status="failed", error=str(exc))
                logger.info(f"Marked run {run_id} as failed in database upon resumption retry failure", extra={"run_id": run_id})
            finally:
                db.close()
                
        raise exc

# Stub task placeholders for other separate queues (to show queue routing setup)
@celery_app.task
def indexing_task(file_path: str) -> str:
    logger.info(f"Indexing repository file: {file_path}")
    return f"Indexed {file_path}"

@celery_app.task
def memory_task(content: str) -> str:
    logger.info("Consolidating system background experience memory")
    return "Memory item consolidated"
