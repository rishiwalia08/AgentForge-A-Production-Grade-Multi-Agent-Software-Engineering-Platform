from __future__ import annotations

import jwt
import requests
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db, DatabaseRepository

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google-login", auto_error=False)

# --- JWT Utilities ---

def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(seconds=settings.access_token_ttl_seconds)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def verify_token(token: str) -> dict[str, Any] | None:
    try:
        # Decodes token using standard PyJWT and settings parameters
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        # Explicit expired check
        return None
    except jwt.PyJWTError:
        return None

def refresh_token_ready(refresh_token: str) -> str | None:
    """Structure placeholder for checking refresh tokens and issuing new access tokens."""
    payload = verify_token(refresh_token)
    if payload:
        # Re-issue access token using sub claim
        return create_access_token({"sub": payload.get("sub")})
    return None

# --- Auth Providers ---

class AuthProvider:
    def verify_google_token(self, id_token: str) -> dict[str, Any] | None:
        raise NotImplementedError()

class MockAuth(AuthProvider):
    def verify_google_token(self, id_token: str) -> dict[str, Any] | None:
        if id_token.startswith("mock_token_"):
            name = id_token.replace("mock_token_", "").capitalize()
            email = f"{name.lower()}@example.com"
            return {
                "sub": f"mock-sub-{name.lower()}",
                "email": email,
                "name": name,
                "picture": f"https://example.com/{name.lower()}.jpg"
            }
        return None

class GoogleAuth(AuthProvider):
    def verify_google_token(self, id_token_str: str) -> dict[str, Any] | None:
        try:
            # Production: Verify ID token using Google Token Info endpoint
            url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token_str}"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                # Verify audience corresponds to our client ID if set
                if settings.google_client_id and data.get("aud") != settings.google_client_id:
                    return None
                return data
            return None
        except Exception:
            return None

def get_auth_provider() -> AuthProvider:
    if settings.environment in ("development", "test"):
        return MockAuth()
    return GoogleAuth()

# --- Security Dependency ---

def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing subject claim.",
        )
        
    user = DatabaseRepository.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user record not found.",
        )
        
    return {"id": user.id, "email": user.email, "name": user.name}
