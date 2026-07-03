from __future__ import annotations

import datetime
import os
from typing import Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.memory.models import Base
from app.services.memory.embeddings.base import BaseEmbeddingProvider
from app.services.memory.embeddings.ollama import OllamaEmbeddingProvider
from app.services.memory.vector.base import BaseVectorStore
from app.services.memory.vector.faiss_store import FAISSVectorStore
from app.services.memory.evaluator import LLMMemoryEvaluator
from app.services.memory.repository import MemoryRepository

class MemoryManager:
    def __init__(
        self, 
        db_url: str | None = None, 
        embedding_provider: BaseEmbeddingProvider | None = None, 
        evaluator: Any = None,
        vector_store: BaseVectorStore | None = None
    ):
        if db_url is None:
            db_url = "sqlite:///./data/agent_memory.db"
            
        if db_url.startswith("postgresql"):
            try:
                import psycopg2
            except ImportError:
                print("Warning: psycopg2 not installed. Falling back to local SQLite database.")
                db_url = "sqlite:///./data/agent_memory.db"
            
        if db_url.startswith("sqlite:///"):
            file_path = db_url.replace("sqlite:///", "")
            if file_path and not file_path.startswith(":memory:"):
                os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
                
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
        self.embedding_provider = embedding_provider
        self.evaluator = evaluator
        self.vector_store = vector_store or FAISSVectorStore()
        
        self._load_vector_memories()

    def _load_vector_memories(self) -> None:
        session = self.Session()
        try:
            memories = MemoryRepository.retrieve_vector_memories(session)
            for mem in memories:
                self.vector_store.add(mem.embedding_json, mem.text, mem.metadata_json)
        finally:
            session.close()

    def store_memory(self, category: str, content: str, metadata: dict | None = None, **kwargs) -> dict:
        metadata = metadata or {}
        
        importance = "save"
        if self.evaluator:
            importance = self.evaluator.evaluate(content, category)
            
        if importance == "ignore":
            return {"status": "ignored", "reason": "unimportant"}
        elif importance == "evaluation_pending":
            return {"status": "pending", "reason": "LLM offline"}

        session = self.Session()
        try:
            memory_id = str(datetime.datetime.utcnow().timestamp()) + "-" + category
            if category == "user":
                user_id = kwargs.get("user_id") or metadata.get("user_id") or "default_user"
                mem_type = kwargs.get("memory_type") or metadata.get("memory_type") or "preference"
                MemoryRepository.store_user_memory(session, memory_id, user_id, mem_type, content, metadata)
            elif category == "project":
                project_id = kwargs.get("project_id") or metadata.get("project_id") or "default_project"
                mem_type = kwargs.get("memory_type") or metadata.get("memory_type") or "context"
                MemoryRepository.store_project_memory(session, memory_id, project_id, mem_type, content, metadata)
            elif category == "error":
                cause = kwargs.get("cause") or metadata.get("cause") or ""
                solution = kwargs.get("solution") or metadata.get("solution") or ""
                file_changed = kwargs.get("file_changed") or metadata.get("file_changed")
                MemoryRepository.store_error_memory(session, memory_id, content, cause, solution, file_changed)
            elif category == "semantic":
                # Fallback to default mock embedding if provider not configured to prevent crashes
                if self.embedding_provider:
                    embedding = self.embedding_provider.get_embedding(content)
                else:
                    # Let's import mock provider inline from test utils if available, or generate a simple float list
                    embedding = [0.1] * 128
                
                MemoryRepository.store_vector_memory(session, memory_id, content, embedding, metadata)
                self.vector_store.add(embedding, content, metadata)
                
            session.commit()
            return {"status": "saved", "id": memory_id}
        except Exception as exc:
            session.rollback()
            raise exc
        finally:
            session.close()

    def retrieve_memory(self, category: str, query: str | None = None, **kwargs) -> list[dict]:
        session = self.Session()
        try:
            if category == "user":
                user_id = kwargs.get("user_id") or "Rishi"
                mem_type = kwargs.get("memory_type")
                results = MemoryRepository.retrieve_user_memories(session, user_id, mem_type)
                return [
                    {
                        "id": r.id,
                        "user_id": r.user_id,
                        "memory_type": r.memory_type,
                        "content": r.content,
                        "metadata": r.metadata_json,
                        "created_at": r.created_at.isoformat()
                    } for r in results
                ]
            elif category == "project":
                project_id = kwargs.get("project_id") or "default_project"
                mem_type = kwargs.get("memory_type")
                results = MemoryRepository.retrieve_project_memories(session, project_id, mem_type)
                return [
                    {
                        "id": r.id,
                        "project_id": r.project_id,
                        "memory_type": r.memory_type,
                        "content": r.content,
                        "metadata": r.metadata_json,
                        "created_at": r.created_at.isoformat()
                    } for r in results
                ]
            elif category == "error":
                results = MemoryRepository.retrieve_error_memories(session, query)
                return [
                    {
                        "id": r.id,
                        "error": r.error,
                        "cause": r.cause,
                        "solution": r.solution,
                        "file_changed": r.file_changed,
                        "timestamp": r.timestamp.isoformat()
                    } for r in results
                ]
            return []
        finally:
            session.close()

    def search_memory(self, query: str, limit: int = 5) -> list[dict]:
        if self.embedding_provider:
            embedding = self.embedding_provider.get_embedding(query)
            return self.vector_store.search(embedding, k=limit)
        return []

    def update_memory(self, category: str, memory_id: str, content: str | None = None, metadata: dict | None = None, **kwargs) -> bool:
        session = self.Session()
        try:
            updated = False
            if category == "user":
                updated = MemoryRepository.update_user_memory(session, memory_id, content, metadata)
            elif category == "project":
                updated = MemoryRepository.update_project_memory(session, memory_id, content, metadata)
            if updated:
                session.commit()
            return updated
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()
