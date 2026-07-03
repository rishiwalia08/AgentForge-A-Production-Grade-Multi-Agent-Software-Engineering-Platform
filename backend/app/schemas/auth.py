from __future__ import annotations

from pydantic import BaseModel, Field

class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., description="Google OAuth ID token")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
