"""Admin auth endpoints (capability: admin-auth)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.security import create_admin_token, require_admin, verify_admin_password

router = APIRouter(prefix="/api/admin", tags=["admin-auth"])


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginRequest) -> dict:
    if not verify_admin_password(body.password):
        # uniform message, never reveals password info
        raise HTTPException(status_code=401, detail="密码错误")
    return {"token": create_admin_token()}


@router.get("/me")
async def me(payload: dict = Depends(require_admin)) -> dict:
    return {"user": payload["sub"], "aud": payload["aud"]}
