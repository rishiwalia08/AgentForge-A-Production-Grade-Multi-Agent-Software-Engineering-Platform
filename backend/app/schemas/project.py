from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the project")
    description: str | None = Field(default="", description="Optional project description")
    repo_path: str | None = Field(default=None, description="Optional path to the project codebase repository")

class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str
    repo_path: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
