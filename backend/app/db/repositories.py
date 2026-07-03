from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session
from app.db.models import User, Project, AgentThread, AgentRun, CheckpointRecord

class DatabaseRepository:
    # --- User Repository ---
    @staticmethod
    def get_user(db: Session, user_id: str) -> User | None:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User | None:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def create_user(
        db: Session,
        email: str,
        name: str,
        google_sub: str | None = None,
        picture_url: str = ""
    ) -> User:
        user = User(email=email, name=name, google_sub=google_sub, picture_url=picture_url)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    # --- Project Repository ---
    @staticmethod
    def get_project(db: Session, project_id: str) -> Project | None:
        return db.query(Project).filter(Project.id == project_id).first()

    @staticmethod
    def list_projects(db: Session, user_id: str) -> list[Project]:
        return db.query(Project).filter(Project.user_id == user_id).all()

    @staticmethod
    def create_project(
        db: Session,
        user_id: str,
        name: str,
        description: str = "",
        repo_path: str | None = None
    ) -> Project:
        project = Project(user_id=user_id, name=name, description=description, repo_path=repo_path)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def delete_project(db: Session, project_id: str) -> bool:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            db.delete(project)
            db.commit()
            return True
        return False

    # --- AgentThread Repository ---
    @staticmethod
    def get_thread(db: Session, thread_id: str) -> AgentThread | None:
        return db.query(AgentThread).filter(AgentThread.thread_id == thread_id).first()

    @staticmethod
    def create_thread(
        db: Session,
        thread_id: str,
        user_id: str,
        project_id: str
    ) -> AgentThread:
        thread = AgentThread(thread_id=thread_id, user_id=user_id, project_id=project_id, status="running")
        db.add(thread)
        db.commit()
        db.refresh(thread)
        return thread

    @staticmethod
    def update_thread(
        db: Session,
        thread_id: str,
        status: str | None = None,
        current_node: str | None = None,
        last_error: str | None = None
    ) -> AgentThread | None:
        thread = db.query(AgentThread).filter(AgentThread.thread_id == thread_id).first()
        if thread:
            if status:
                thread.status = status
            if current_node:
                thread.current_node = current_node
            if last_error:
                thread.last_error = last_error
            db.commit()
            db.refresh(thread)
        return thread

    # --- AgentRun Repository ---
    @staticmethod
    def get_run(db: Session, run_id: str) -> AgentRun | None:
        return db.query(AgentRun).filter(AgentRun.id == run_id).first()

    @staticmethod
    def create_run(
        db: Session,
        run_id: str,
        thread_id: str,
        user_id: str,
        project_id: str,
        input_message: str,
        status: str = "running"
    ) -> AgentRun:
        run = AgentRun(
            id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            project_id=project_id,
            input_message=input_message,
            status=status
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def update_run(
        db: Session,
        run_id: str,
        status: str | None = None,
        supervisor_decision: dict[str, Any] | None = None,
        final_state: dict[str, Any] | None = None,
        error: str | None = None
    ) -> AgentRun | None:
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if run:
            if status:
                run.status = status
            if supervisor_decision:
                run.supervisor_decision = supervisor_decision
            if final_state:
                run.final_state = final_state
            if error:
                run.error = error
            db.commit()
            db.refresh(run)
        return run
