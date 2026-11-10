"""FastAPI dependencies: who is calling, and what role do they have.

The role in the database is the source of truth (the role inside the token is for the
frontend to display). A `pro` role with a past `pro_expires_at` counts as `public`."""
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import User, utcnow
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)

_SESSION_ERROR = "Your session is invalid or has expired. Please log in again."


def effective_role(user: Optional[User]) -> str:
    if user is None:
        return "public"
    if user.role == "pro" and user.pro_expires_at is not None and user.pro_expires_at < utcnow():
        return "public"
    return user.role


def is_pro(user: Optional[User]) -> bool:
    return effective_role(user) in ("pro", "admin")


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """None when no token is sent (public visitor). 401 when a token is sent but bad."""
    if creds is None:
        return None
    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail=_SESSION_ERROR)
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail=_SESSION_ERROR)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail=_SESSION_ERROR)
    return user


def get_current_user(user: Optional[User] = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in to use this feature.")
    return user


def require_role(*allowed: str):
    """Use as Depends(require_role("pro")). Admins can use every Pro endpoint."""

    def checker(user: User = Depends(get_current_user)) -> User:
        role = effective_role(user)
        if role == "admin" or role in allowed:
            return user
        if "pro" in allowed:
            raise HTTPException(
                status_code=403, detail="This feature needs a Professional subscription."
            )
        raise HTTPException(status_code=403, detail="This feature is for administrators only.")

    return checker
