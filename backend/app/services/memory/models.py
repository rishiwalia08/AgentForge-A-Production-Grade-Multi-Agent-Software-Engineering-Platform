from __future__ import annotations

import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class UserMemory(Base):
    __tablename__ = "user_memories"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    memory_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ProjectMemory(Base):
    __tablename__ = "project_memories"
    id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False)
    memory_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ErrorMemory(Base):
    __tablename__ = "error_memories"
    id = Column(String, primary_key=True)
    error = Column(Text, nullable=False)
    cause = Column(Text, nullable=False)
    solution = Column(Text, nullable=False)
    file_changed = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class VectorMemory(Base):
    __tablename__ = "vector_memories"
    id = Column(String, primary_key=True)
    text = Column(Text, nullable=False)
    embedding_json = Column(JSON, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
