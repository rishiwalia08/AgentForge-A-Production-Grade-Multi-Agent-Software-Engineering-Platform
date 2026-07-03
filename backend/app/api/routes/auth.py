from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db, DatabaseRepository
from app.core.auth import get_auth_provider, create_access_token
from app.schemas.auth import GoogleLoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/google-login", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    provider = get_auth_provider()
    user_info = provider.verify_google_token(payload.id_token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID token validation failed."
        )

    email = user_info.get("email")
    name = user_info.get("name") or email.split("@")[0].capitalize()
    google_sub = user_info.get("sub")
    picture = user_info.get("picture") or ""

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address not provided in Google credentials."
        )

    # Fetch user or create if new
    user = DatabaseRepository.get_user_by_email(db, email)
    if not user:
        user = DatabaseRepository.create_user(db, email, name, google_sub, picture)

    # Issue JWT token
    access_token = create_access_token({"sub": user.id, "email": user.email, "name": user.name})

    return TokenResponse(access_token=access_token)
