from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class RunCreate(BaseModel):
    project_id: str = Field(..., description="ID of the project to run the agent on")
    task: str = Field(..., description="Task description / prompt for execution")

class RunResponse(BaseModel):
    id: str
    thread_id: str
    project_id: str
    user_id: str
    input_message: str
    status: str
    supervisor_decision: dict[str, Any] | None = None
    final_state: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RunResume(BaseModel):
    approved: bool = Field(..., description="Set true to approve, false to reject the pending action")
    feedback: str | None = Field(default=None, description="Optional text feedback from the human")
