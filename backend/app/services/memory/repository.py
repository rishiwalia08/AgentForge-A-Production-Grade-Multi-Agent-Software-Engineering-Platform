from __future__ import annotations

import datetime
from sqlalchemy.orm import Session
from app.services.memory.models import UserMemory, ProjectMemory, ErrorMemory, VectorMemory

class MemoryRepository:
    @staticmethod
    def store_user_memory(session: Session, memory_id: str, user_id: str, memory_type: str, content: str, metadata: dict | None) -> None:
        db_mem = UserMemory(
            id=memory_id,
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            metadata_json=metadata
        )
        session.add(db_mem)

    @staticmethod
    def store_project_memory(session: Session, memory_id: str, project_id: str, memory_type: str, content: str, metadata: dict | None) -> None:
        db_mem = ProjectMemory(
            id=memory_id,
            project_id=project_id,
            memory_type=memory_type,
            content=content,
            metadata_json=metadata
        )
        session.add(db_mem)

    @staticmethod
    def store_error_memory(session: Session, memory_id: str, error: str, cause: str, solution: str, file_changed: str | None) -> None:
        db_mem = ErrorMemory(
            id=memory_id,
            error=error,
            cause=cause,
            solution=solution,
            file_changed=file_changed
        )
        session.add(db_mem)

    @staticmethod
    def store_vector_memory(session: Session, memory_id: str, text: str, embedding: list[float], metadata: dict | None) -> None:
        db_mem = VectorMemory(
            id=memory_id,
            text=text,
            embedding_json=embedding,
            metadata_json=metadata
        )
        session.add(db_mem)

    @staticmethod
    def retrieve_user_memories(session: Session, user_id: str, memory_type: str | None = None) -> list[UserMemory]:
        query = session.query(UserMemory).filter(UserMemory.user_id == user_id)
        if memory_type:
            query = query.filter(UserMemory.memory_type == memory_type)
        return query.all()

    @staticmethod
    def retrieve_project_memories(session: Session, project_id: str, memory_type: str | None = None) -> list[ProjectMemory]:
        query = session.query(ProjectMemory).filter(ProjectMemory.project_id == project_id)
        if memory_type:
            query = query.filter(ProjectMemory.memory_type == memory_type)
        return query.all()

    @staticmethod
    def retrieve_error_memories(session: Session, query_str: str | None = None) -> list[ErrorMemory]:
        if query_str:
            return session.query(ErrorMemory).filter(
                (ErrorMemory.error.like(f"%{query_str}%")) | (ErrorMemory.cause.like(f"%{query_str}%"))
            ).all()
        return session.query(ErrorMemory).all()

    @staticmethod
    def retrieve_vector_memories(session: Session) -> list[VectorMemory]:
        return session.query(VectorMemory).all()

    @staticmethod
    def update_user_memory(session: Session, memory_id: str, content: str | None = None, metadata: dict | None = None) -> bool:
        mem = session.query(UserMemory).filter(UserMemory.id == memory_id).first()
        if mem:
            if content:
                mem.content = content
            if metadata:
                mem.metadata_json = metadata
            return True
        return False

    @staticmethod
    def update_project_memory(session: Session, memory_id: str, content: str | None = None, metadata: dict | None = None) -> bool:
        mem = session.query(ProjectMemory).filter(ProjectMemory.id == memory_id).first()
        if mem:
            if content:
                mem.content = content
            if metadata:
                mem.metadata_json = metadata
            return True
        return False
