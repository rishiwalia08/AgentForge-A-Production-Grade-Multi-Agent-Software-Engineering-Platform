from __future__ import annotations

import datetime
from sqlalchemy import Column, String, Text, DateTime, Float, Integer
from app.services.memory_manager import Base

class TraceRecord(Base):
    __tablename__ = "trace_records"

    id = Column(String(36), primary_key=True)
    run_id = Column(String(128), nullable=False, index=True)
    thread_id = Column(String(128), nullable=False, index=True)
    parent_trace_id = Column(String(36), nullable=True, index=True)
    agent = Column(String(128), nullable=False, index=True)
    
    input_data = Column(Text, nullable=True)
    reasoning_summary = Column(Text, nullable=True)
    
    tool_called = Column(String(255), nullable=True)
    tool_arguments = Column(Text, nullable=True)
    tool_result = Column(Text, nullable=True)
    
    latency = Column(Float, nullable=True)
    
    # Token and Cost tracking
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    
    # Error tracking
    status = Column(String(32), default="SUCCESS")  # SUCCESS, FAILED, INTERRUPTED
    error_message = Column(Text, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
