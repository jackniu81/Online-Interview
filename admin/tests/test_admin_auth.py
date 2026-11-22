"""Admin login & endpoint auth tests (task 3.1)."""
import jwt
import pytest

from app.config import get_settings
from app.security import ADMIN_AUD, create_admin_token


async def test_login_success(client):
    resp = await client.post(
        "/api/admin/login", json={"password": get_settings().admin_password}
    )
    assert resp.status_code == 200
    token = resp.json()["token"]
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"], audience=ADMIN_AUD)
    assert payload["sub"] == "admin"

    me = await client.get(
        "/api/admin/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200


async def test_login_wrong_password(client):
    resp = await client.post("/api/admin/login", json={"password": "definitely-wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "密码错误"


async def test_protected_without_token(client):
    resp = await client.get("/api/admin/me")
    assert resp.status_code == 401


async def test_protected_expired_token(client):
    expired = jwt.encode(
        {"sub": "admin", "aud": ADMIN_AUD, "exp": 0},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    resp = await client.get(
        "/api/admin/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert resp.status_code == 401


async def test_admin_token_rejected_on_exam_audience(client):
    # audience isolation: an admin token must not validate as an exam session token
    token = create_admin_token()
    with pytest.raises(jwt.InvalidAudienceError):
        jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"], audience="exam")
