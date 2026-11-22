"""Shared pytest fixtures."""
import httpx
import pytest

from app.db import init_db
from app.main import app


@pytest.fixture
async def client():
    init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def db_session():
    """Real PostgreSQL session (dev db from .env)."""
    init_db()
    from app import db

    assert db.SessionLocal is not None
    async with db.SessionLocal() as session:
        yield session


@pytest.fixture
async def auth_headers(client):
    """Admin bearer headers for protected-endpoint tests."""
    from app.config import get_settings

    resp = await client.post(
        "/api/admin/login", json={"password": get_settings().admin_password}
    )
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}
