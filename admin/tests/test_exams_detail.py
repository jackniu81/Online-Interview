"""Exam detail API tests (task 5.3)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.models import Exam, ExamAnswer, ExamQuestion
from app.routers.exams import create_exam

DETAIL_EMAIL = "detail-test@example.com"


@pytest.fixture
async def cleanup_detail(db_session):
    yield
    ids = (await db_session.scalars(select(Exam.id).where(Exam.email == DETAIL_EMAIL))).all()
    if ids:
        for model in (ExamQuestion, ExamAnswer):
            await db_session.execute(delete(model).where(model.exam_id.in_(ids)))
        await db_session.execute(delete(Exam).where(Exam.id.in_(ids)))
        await db_session.commit()


async def _finish_exam(session, exam, statuses, *, name="张三", phone="13800000000"):
    """Mark exam started/completed and set per-question answer rows."""
    now = datetime.now(timezone.utc)
    exam.started_at = now - timedelta(minutes=20)
    exam.completed_at = now
    exam.candidate_name = name
    exam.candidate_phone = phone
    if all(st in ("graded", "failed") for st in statuses):
        scores = [30 if st == "failed" else 90 for st in statuses]
        exam.total_score = sum(scores) // len(scores)
        exam.result_status = "excellent" if exam.total_score >= 85 else "pass" if exam.total_score >= 60 else "fail"
    answers = (
        await session.scalars(
            select(ExamAnswer).where(ExamAnswer.exam_id == exam.id).order_by(ExamAnswer.sort_order)
        )
    ).all()
    for a, st in zip(answers, statuses):
        a.grading_status = st
        a.answer_text = f"answer {a.sort_order}"
        a.submitted_at = now
        if st == "graded":
            a.score = 90
            a.feedback = "很好"
        elif st == "failed":
            a.score = None
            a.feedback = None
    await session.commit()


async def test_detail_incomplete(client, auth_headers, db_session, cleanup_detail):
    exam = await create_exam(db_session, DETAIL_EMAIL, 5, 15)
    resp = await client.get(f"/api/admin/exams/{exam.id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "incomplete"
    assert body["completed_at"] is None
    assert body["question_count"] == 5
    assert len(body["questions"]) == 5
    q0 = body["questions"][0]
    assert q0["grading_status"] == "unanswered"
    assert q0["answer_text"] is None and q0["score"] is None
    assert q0["question_content"]


async def test_detail_grading(client, auth_headers, db_session, cleanup_detail):
    exam = await create_exam(db_session, DETAIL_EMAIL, 5, 15)
    await _finish_exam(db_session, exam, ("graded", "graded", "pending", "grading", "graded"))
    resp = await client.get(f"/api/admin/exams/{exam.id}", headers=auth_headers)
    body = resp.json()
    assert body["status"] == "grading"
    by_order = {q["sort_order"]: q for q in body["questions"]}
    assert by_order[0]["grading_status"] == "graded" and by_order[0]["score"] == 90
    assert by_order[0]["feedback"] == "很好"
    assert by_order[2]["grading_status"] == "pending" and by_order[2]["score"] is None


async def test_detail_completed(client, auth_headers, db_session, cleanup_detail):
    exam = await create_exam(db_session, DETAIL_EMAIL, 5, 15)
    await _finish_exam(db_session, exam, ("graded",) * 5)
    resp = await client.get(f"/api/admin/exams/{exam.id}", headers=auth_headers)
    body = resp.json()
    assert body["status"] == "excellent"
    assert body["total_score"] == 90
    assert body["candidate_name"] == "张三"
    assert body["candidate_phone"] == "13800000000"
    assert body["completed_at"] is not None
    assert all(q["grading_status"] == "graded" for q in body["questions"])


async def test_detail_failed_grading_marks_fail(client, auth_headers, db_session, cleanup_detail):
    exam = await create_exam(db_session, DETAIL_EMAIL, 5, 15)
    await _finish_exam(db_session, exam, ("failed", "graded", "failed", "failed", "failed"))
    resp = await client.get(f"/api/admin/exams/{exam.id}", headers=auth_headers)
    body = resp.json()
    assert body["status"] == "fail"
    by_order = {q["sort_order"]: q for q in body["questions"]}
    assert by_order[0]["grading_status"] == "failed" and by_order[0]["score"] is None


async def test_detail_404_and_auth(client, auth_headers):
    resp = await client.get("/api/admin/exams/99999999", headers=auth_headers)
    assert resp.status_code == 404
    resp = await client.get("/api/admin/exams/1")
    assert resp.status_code == 401
