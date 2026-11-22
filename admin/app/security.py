"""JWT creation/validation and auth dependencies (design D4/D6)."""
import hmac
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

ADMIN_AUD = "admin"
EXAM_AUD = "exam"

_admin_bearer = HTTPBearer(auto_error=False)
_exam_bearer = HTTPBearer(auto_error=False)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_admin_token() -> str:
    payload = {
        "sub": "admin",
        "aud": ADMIN_AUD,
        "exp": _now() + timedelta(hours=12),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def create_exam_token(exam_id: int) -> str:
    # valid for exam duration + 10 min buffer (server clocks are authoritative anyway)
    payload = {
        "sub": str(exam_id),
        "aud": EXAM_AUD,
        "exp": _now() + timedelta(minutes=24 * 60),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def _decode(token: str, aud: str) -> dict:
    return jwt.decode(
        token, get_settings().jwt_secret, algorithms=["HS256"], audience=aud
    )


async def require_admin(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_admin_bearer)],
) -> dict:
    """Dependency guarding /api/admin/* management endpoints."""
    if creds is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    try:
        return _decode(creds.credentials, ADMIN_AUD)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="unauthorized")


async def require_exam_session(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_exam_bearer)],
) -> int:
    """Dependency guarding candidate exam endpoints; returns exam_id."""
    if creds is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    try:
        payload = _decode(creds.credentials, EXAM_AUD)
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="unauthorized")


def verify_admin_password(password: str) -> bool:
    return hmac.compare_digest(
        password.encode("utf-8"), get_settings().admin_password.encode("utf-8")
    )
