"""Exam creation API tests (task 5.1)."""
import pytest
from sqlalchemy import delete, func, select

from app.crypto import decrypt_exam_token
from app.models import Exam, ExamAnswer, ExamQuestion, Question
from app.routers.exams import create_exam
from app.seed import seed_questions

TEST_EMAIL = "cand-a@test.example"


@pytest.fixture
async def cleanup_exams(db_session):
    yield
    exam_ids = (
        await db_session.scalars(select(Exam.id).where(Exam.email == TEST_EMAIL))
    ).all()
    if exam_ids:
        for model in (ExamQuestion, ExamAnswer):
            await db_session.execute(delete(model).where(model.exam_id.in_(exam_ids)))
        await db_session.execute(delete(Exam).where(Exam.id.in_(exam_ids)))
        await db_session.commit()


@pytest.fixture
async def empty_bank(db_session):
    """Temporarily empty the question bank; restore by re-seeding afterwards."""
    await db_session.execute(delete(Question))
    await db_session.commit()
    yield db_session
    await seed_questions(db_session)


async def test_create_default_params(client, auth_headers, cleanup_exams, db_session):
    resp = await client.post(
        "/api/admin/exams", json={"email": TEST_EMAIL}, headers=auth_headers
    )
    assert resp.status_code == 201
    body = resp.json()
    exam_id = body["id"]
    assert body["question_count"] == 5
    assert body["duration_minutes"] == 15
    assert body["link"].endswith("/exam?t=" + body["link"].split("?t=")[1])
    # link carries no plaintext email
    assert TEST_EMAIL not in body["link"]

    # token decrypts back to exam_id + email
    token = body["link"].split("?t=")[1]
    assert decrypt_exam_token(token) == {"exam_id": exam_id, "email": TEST_EMAIL}

    # snapshots + pre-created unanswered answer rows
    n_q = await db_session.scalar(
        select(func.count()).select_from(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    )
    n_a = await db_session.scalar(
        select(func.count()).select_from(ExamAnswer).where(ExamAnswer.exam_id == exam_id)
    )
    assert (n_q, n_a) == (5, 5)
    statuses = (
        await db_session.scalars(
            select(ExamAnswer.grading_status).where(ExamAnswer.exam_id == exam_id)
        )
    ).all()
    assert set(statuses) == {"unanswered"}


async def test_create_custom_params_unique_questions(client, auth_headers, cleanup_exams, db_session):
    resp = await client.post(
        "/api/admin/exams",
        json={"email": TEST_EMAIL, "question_count": 10, "duration_minutes": 30},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    exam_id = resp.json()["id"]
    contents = (
        await db_session.scalars(
            select(ExamQuestion.question_content).where(ExamQuestion.exam_id == exam_id)
        )
    ).all()
    assert len(contents) == 10
    assert len(set(contents)) == 10  # no duplicate sampling


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email"},
        {"email": TEST_EMAIL, "question_count": 7},
        {"email": TEST_EMAIL, "duration_minutes": 25},
    ],
)
async def test_invalid_params_rejected(client, auth_headers, payload):
    resp = await client.post("/api/admin/exams", json=payload, headers=auth_headers)
    assert resp.status_code == 422


async def test_insufficient_bank_errors(empty_bank):
    with pytest.raises(ValueError, match="题库题目不足"):
        await create_exam(empty_bank, TEST_EMAIL, 5, 15)


async def test_create_requires_auth(client):
    resp = await client.post("/api/admin/exams", json={"email": TEST_EMAIL})
    assert resp.status_code == 401
