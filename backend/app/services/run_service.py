from __future__ import annotations

from uuid import uuid4
from fastapi import HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repositories import DatabaseRepository
from app.services.agent_runner import AgentRunner

settings = get_settings()

class RunService:
    @staticmethod
    def create_run(
        db: Session,
        project_id: str,
        task: str,
        user_id: str,
        background_tasks: BackgroundTasks
    ) -> dict[str, str]:
        # 1. Validate project existence and user ownership
        project = DatabaseRepository.get_project(db, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target project not found."
            )
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access permission for this project."
            )

        # 2. Setup identifiers
        run_id = str(uuid4())
        thread_id = f"thread_{run_id}"

        # 3. Persist thread and run state
        thread = DatabaseRepository.get_thread(db, thread_id)
        if not thread:
            DatabaseRepository.create_thread(db, thread_id, user_id, project_id)
            
        DatabaseRepository.create_run(db, run_id, thread_id, user_id, project_id, task)

        # 4. Route execution depending on environment
        if settings.environment == "test":
            # Testing mode: Use FastAPI in-process background tasks
            background_tasks.add_task(AgentRunner.run, run_id, thread_id, task)
        else:
            # Production: Offload to Celery tasks queue
            from app.core.celery_app import run_agent_task
            run_agent_task.delay(run_id, thread_id, task)

        return {
            "run_id": run_id,
            "thread_id": thread_id
        }

    @staticmethod
    def resume_run(
        db: Session,
        run_id: str,
        approved: bool,
        feedback: str | None,
        user_id: str,
        background_tasks: BackgroundTasks
    ) -> dict[str, str]:
        # 1. Validate run and ownership
        run = DatabaseRepository.get_run(db, run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target run execution not found."
            )
        if run.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access permission for this execution run."
            )

        if run.status != "interrupted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resume a run that is currently in '{run.status}' state."
            )

        # Update run status to resuming immediately in DB
        DatabaseRepository.update_run(db, run_id, status="resuming")

        # 2. Route resumption depending on environment
        if settings.environment == "test":
            # Testing mode: Use FastAPI in-process background tasks
            background_tasks.add_task(AgentRunner.resume, run_id, run.thread_id, approved, feedback)
        else:
            # Production: Offload to Celery tasks queue
            from app.core.celery_app import resume_agent_task
            resume_agent_task.delay(run_id, run.thread_id, approved, feedback)

        return {
            "status": "resuming"
        }
