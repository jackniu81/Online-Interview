"""Encrypted exam-link tokens (design D4).

Token payload is JSON {exam_id, email} encrypted with Fernet; the URL never
contains the plaintext email.
"""
import json

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().link_encryption_key
    if not key:
        raise RuntimeError("LINK_ENCRYPTION_KEY is not configured (run admin/scripts/make_env.py)")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_exam_token(exam_id: int, email: str) -> str:
    payload = json.dumps({"exam_id": exam_id, "email": email}, separators=(",", ":"))
    return _fernet().encrypt(payload.encode("utf-8")).decode("utf-8")


def decrypt_exam_token(token: str) -> dict | None:
    """Return {'exam_id': int, 'email': str}; None when the token is invalid."""
    try:
        data = json.loads(_fernet().decrypt(token.encode("utf-8")))
        return {"exam_id": int(data["exam_id"]), "email": str(data["email"])}
    except (InvalidToken, ValueError, KeyError, TypeError):
        return None
