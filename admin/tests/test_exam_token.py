"""Candidate link/info/begin tests (task 6.1)."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import delete, select

from app.config import get_settings
from app.crypto import encrypt_exam_token
from app.models import Exam, ExamAnswer, ExamQuestion
from app.routers.exams import create_exam
from app.security import EXAM_AUD

TK_EMAIL = "token-test@example.com"


@pytest.fixture
async def cleanup_tk(db_session):
    yield
    ids = (await db_session.scalars(select(Exam.id).where(Exam.email == TK_EMAIL))).all()
    if ids:
        for model in (ExamQuestion, ExamAnswer):
            await db_session.execute(delete(model).where(model.exam_id.in_(ids)))
        await db_session.execute(delete(Exam).where(Exam.id.in_(ids)))
        await db_session.commit()


def _token_for(exam_id: int, email: str = TK_EMAIL) -> str:
    return encrypt_exam_token(exam_id, email)


async def test_info_valid_token(client, db_session, cleanup_tk):
    exam = await create_exam(db_session, TK_EMAIL, 5, 15)
    resp = await client.get("/api/exams/info", params={"t": _token_for(exam.id)})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "completed": False,
        "started": False,
        "question_count": 5,
        "duration_minutes": 15,
        "remaining_seconds": 15 * 60,
    }


async def test_info_invalid_or_tampered(client, db_session, cleanup_tk):
    exam = await create_exam(db_session, TK_EMAIL, 5, 15)
    resp = await client.get("/api/exams/info", params={"t": "garbage"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "链接无效"
    # tampered payload (valid fernet style but wrong email) rejected
    resp = await client.get("/api/exams/info", params={"t": _token_for(exam.id, "attacker@x.com")})
    assert resp.status_code == 404
    resp = await client.get("/api/exams/info", params={"t": _token_for(99999999)})
    assert resp.status_code == 404
    resp = await client.get("/api/exams/info")  # missing param
    assert resp.status_code == 422


async def test_info_completed_exam(client, db_session, cleanup_tk):
    exam = await create_exam(db_session, TK_EMAIL, 5, 15)
    exam.completed_at = datetime.now(timezone.utc)
    await db_session.commit()
    resp = await client.get("/api/exams/info", params={"t": _token_for(exam.id)})
    assert resp.status_code == 200
    assert resp.json() == {"completed": True}


async def test_begin_success_and_jwt(client, db_session, cleanup_tk):
    exam = await create_exam(db_session, TK_EMAIL, 5, 15)
    resp = await client.post(
        "/api/exams/begin",
        json={"token": _token_for(exam.id), "name": " 李四 ", "phone": "13912345678"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["exam_id"] == exam.id
    assert body["remaining_seconds"] == 15 * 60

    payload = jwt.decode(
        body["session_token"], get_settings().jwt_secret, algorithms=["HS256"], audience=EXAM_AUD
    )
    assert payload["sub"] == str(exam.id)

    db_exam = await db_session.get(Exam, exam.id)
    await db_session.refresh(db_exam)
    assert db_exam.started_at is not None
    assert db_exam.candidate_name == "李四"
    assert db_exam.candidate_phone == "13912345678"


async def test_begin_invalid_inputs(client, db_session, cleanup_tk):
    exam = await create_exam(db_session, TK_EMAIL, 5, 15)
    base = {"token": _token_for(exam.id), "name": "李四", "phone": "13912345678"}
    for patch in (
        {"name": ""},
        {"name": "   "},
        {"phone": "12345678901"},
        {"phone": "1381234567"},
        {"token": "garbage"},
    ):
        body = {**base, **patch}
        resp = await client.post("/api/exams/begin", json=body)
        assert resp.status_code == (404 if "token" in patch else 422), (patch, resp.text)


async def test_begin_repeat_is_idempotent_timer(client, db_session, cleanup_tk):
    exam = await create_exam(db_session, TK_EMAIL, 5, 15)
    resp = await client.post(
        "/api/exams/begin", json={"token": _token_for(exam.id), "name": "李四", "phone": "13912345678"}
    )
    first_started = datetime.fromisoformat(resp.json()["started_at"])
    # simulate an earlier start; re-begin must NOT reset the deadline
    db_exam = await db_session.get(Exam, exam.id)
    past = datetime.now(timezone.utc) - timedelta(minutes=3)
    db_exam.started_at = past
    await db_session.commit()

    resp2 = await client.post(
        "/api/exams/begin", json={"token": _token_for(exam.id), "name": "李四改", "phone": "13912345678"}
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert datetime.fromisoformat(body2["started_at"]) == past
    assert 15 * 60 - 4 * 60 <= body2["remaining_seconds"] <= 15 * 60 - 3 * 60
    db_exam = await db_session.get(Exam, exam.id)
    await db_session.refresh(db_exam)
    assert db_exam.started_at == past  # unchanged
    assert db_exam.candidate_name == "李四改"


async def test_begin_completed_rejected(client, db_session, cleanup_tk):
    exam = await create_exam(db_session, TK_EMAIL, 5, 15)
    exam.completed_at = datetime.now(timezone.utc)
    await db_session.commit()
    resp = await client.post(
        "/api/exams/begin", json={"token": _token_for(exam.id), "name": "李四", "phone": "13912345678"}
    )
    assert resp.status_code == 409
