from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class TraceResponse(BaseModel):
    id: str
    run_id: str
    thread_id: str
    parent_trace_id: str | None = None
    agent: str
    input_data: str | None = None
    reasoning_summary: str | None = None
    tool_called: str | None = None
    tool_arguments: str | None = None
    tool_result: str | None = None
    latency: float | None = None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    status: str
    error_message: str | None = None
    timestamp: datetime

    class Config:
        from_attributes = True

class TimelineStep(BaseModel):
    step: int
    agent: str
    tool: str | None = None
    decision: str | None = None
    reason: str | None = None

class PerformanceMetrics(BaseModel):
    total_steps: int
    agents_called: list[str]
    tools_used: list[str]
    duration: float
    success_rate: float
    errors: list[str]
