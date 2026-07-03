from __future__ import annotations

import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON
from app.services.memory_manager import Base

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id = Column(String, primary_key=True)
    file_path = Column(String, nullable=False)
    chunk_type = Column(String, nullable=False)  # "code_ast", "text", "code_chunk"
    content = Column(Text, nullable=False)
    embedding_json = Column(JSON, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
