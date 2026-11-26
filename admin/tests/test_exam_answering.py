"""Sequential answering, submit guards, hand-in & auto-submit (tasks 6.2/6.3)."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.crypto import encrypt_exam_token
from app.models import Exam, ExamAnswer, ExamQuestion, GradingStatus
from app.routers.exams import create_exam
from app.services import autosubmit

AK_EMAIL = "answer-test@example.com"


@pytest.fixture
async def cleanup_ak(db_session):
    yield
    ids = (await db_session.scalars(select(Exam.id).where(Exam.email == AK_EMAIL))).all()
    if ids:
        for model in (ExamQuestion, ExamAnswer):
            await db_session.execute(delete(model).where(model.exam_id.in_(ids)))
        await db_session.execute(delete(Exam).where(Exam.id.in_(ids)))
        await db_session.commit()


async def _begin(client, db_session, exam) -> dict:
    resp = await client.post(
        "/api/exams/begin",
        json={
            "token": encrypt_exam_token(exam.id, AK_EMAIL),
            "name": "张三",
            "phone": "13812345678",
        },
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['session_token']}"}


async def _set_started_at(db_session, exam_id: int, value: datetime):
    exam = await db_session.get(Exam, exam_id)
    exam.started_at = value
    await db_session.commit()


async def test_sequential_questions_and_submits(client, db_session, cleanup_ak):
    exam = await create_exam(db_session, AK_EMAIL, 5, 15)
    headers = await _begin(client, db_session, exam)

    for order in range(5):
        resp = await client.get("/api/exams/current-question", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["sort_order"] == order
        assert body["question_number"] == order + 1
        assert body["question_count"] == 5
        assert "question_content" in body and "reference_answer" not in body

        resp = await client.post(
            "/api/exams/submit-answer",
            json={"sort_order": order, "answer_text": f"答案{order}"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        sub = resp.json()
        assert sub["is_last"] == (order == 4)
        assert sub["next_order"] == (None if order == 4 else order + 1)

        ans = await db_session.scalar(
            select(ExamAnswer).where(
                ExamAnswer.exam_id == exam.id, ExamAnswer.sort_order == order
            )
        )
        await db_session.refresh(ans)
        assert ans.grading_status == GradingStatus.PENDING.value
        assert ans.submitted_at is not None

    # exam handed in on the last submit; nothing left to serve
    db_exam = await db_session.get(Exam, exam.id)
    await db_session.refresh(db_exam)
    assert db_exam.completed_at is not None
    resp = await client.get("/api/exams/current-question", headers=headers)
    assert resp.status_code == 409


async def test_submit_out_of_order_rejected(client, db_session, cleanup_ak):
    exam = await create_exam(db_session, AK_EMAIL, 5, 15)
    headers = await _begin(client, db_session, exam)
    # skipping ahead
    resp = await client.post(
        "/api/exams/submit-answer", json={"sort_order": 2, "answer_text": "x"}, headers=headers
    )
    assert resp.status_code == 409
    # submit current, then try to resubmit (going back)
    resp = await client.post(
        "/api/exams/submit-answer", json={"sort_order": 0, "answer_text": "a0"}, headers=headers
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/exams/submit-answer", json={"sort_order": 0, "answer_text": "changed"}, headers=headers
    )
    assert resp.status_code == 409
    ans = await db_session.scalar(
        select(ExamAnswer).where(
            ExamAnswer.exam_id == exam.id, ExamAnswer.sort_order == 0
        )
    )
    await db_session.refresh(ans)
    assert ans.answer_text == "a0"  # the rejected resubmit did not overwrite


async def test_no_auth_and_negative_order_rejected(client, db_session, cleanup_ak):
    exam = await create_exam(db_session, AK_EMAIL, 5, 15)
    resp = await client.get("/api/exams/current-question")
    assert resp.status_code == 401
    resp = await client.post("/api/exams/submit-answer", json={"sort_order": 0})
    assert resp.status_code == 401

    headers = await _begin(client, db_session, exam)
    resp = await client.post(
        "/api/exams/submit-answer", json={"sort_order": -1}, headers=headers
    )
    assert resp.status_code == 422


async def test_remaining_seconds_decay_server_side(client, db_session, cleanup_ak):
    exam = await create_exam(db_session, AK_EMAIL, 5, 15)
    headers = await _begin(client, db_session, exam)
    # rewind the start by 3 minutes -> remaining reflects server time, not the client
    await _set_started_at(db_session, exam.id, datetime.now(timezone.utc) - timedelta(minutes=3))
    resp = await client.get("/api/exams/current-question", headers=headers)
    assert 12 * 60 - 5 <= resp.json()["remaining_seconds"] <= 12 * 60
    # refresh (info endpoint) must not reset the countdown
    resp = await client.get(
        "/api/exams/info", params={"t": encrypt_exam_token(exam.id, AK_EMAIL)}
    )
    assert 12 * 60 - 5 <= resp.json()["remaining_seconds"] <= 12 * 60


async def test_submit_after_timeout_rejected(client, db_session, cleanup_ak):
    exam = await create_exam(db_session, AK_EMAIL, 5, 15)
    headers = await _begin(client, db_session, exam)
    # started 16 min ago (duration 15) -> lazy check hands in, then rejects
    await _set_started_at(db_session, exam.id, datetime.now(timezone.utc) - timedelta(minutes=16))
    resp = await client.post(
        "/api/exams/submit-answer", json={"sort_order": 0, "answer_text": "late"}, headers=headers
    )
    assert resp.status_code == 409
    db_exam = await db_session.get(Exam, exam.id)
    await db_session.refresh(db_exam)
    assert db_exam.completed_at is not None
    # untouched answers were swept to pending (empty -> 0 by grading queue)
    statuses = (await db_session.scalars(
        select(ExamAnswer.grading_status).where(ExamAnswer.exam_id == exam.id)
    )).all()
    assert set(statuses) == {GradingStatus.PENDING.value}


async def test_auto_submit_concurrent_only_one_wins(client, db_session, cleanup_ak):
    exam = await create_exam(db_session, AK_EMAIL, 5, 15)
    results = await asyncio.gather(*(autosubmit.auto_submit(exam.id) for _ in range(3)))
    assert sum(1 for r in results if r) == 1
    # a later hand-in attempt (e.g. candidate submit racing the timer) loses
    assert await autosubmit.auto_submit(exam.id) is False


async def test_manual_finish_is_idempotent_with_timer(client, db_session, cleanup_ak):
    exam = await create_exam(db_session, AK_EMAIL, 5, 15)
    headers = await _begin(client, db_session, exam)
    resp = await client.post("/api/exams/finish", headers=headers)
    assert resp.status_code == 200 and resp.json()["just_finished"] is True
    # the losing side of the race reports just_finished=False (one winner only)
    resp2 = await client.post("/api/exams/finish", headers=headers)
    assert resp2.status_code == 200 and resp2.json()["just_finished"] is False
    assert await autosubmit.auto_submit(exam.id) is False
    db_exam = await db_session.get(Exam, exam.id)
    await db_session.refresh(db_exam)
    assert db_exam.completed_at is not None
    # unanswered swept to pending -> list derives 评分中
    statuses = (await db_session.scalars(
        select(ExamAnswer.grading_status).where(ExamAnswer.exam_id == exam.id)
    )).all()
    assert set(statuses) == {GradingStatus.PENDING.value}


async def test_restore_timers_completes_overdue_exams(client, db_session, cleanup_ak):
    exam = await create_exam(db_session, AK_EMAIL, 5, 15)
    headers = await _begin(client, db_session, exam)
    await _set_started_at(db_session, exam.id, datetime.now(timezone.utc) - timedelta(minutes=20))
    autosubmit.cancel_timer(exam.id)  # simulate a process restart (no in-memory timer)

    count = await autosubmit.restore_timers()
    assert count >= 1
    db_exam = await db_session.get(Exam, exam.id)
    await db_session.refresh(db_exam)
    assert db_exam.completed_at is not None
