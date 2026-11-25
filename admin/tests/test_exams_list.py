"""Exam list API tests (task 5.2)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.models import Exam, ExamAnswer

LIST_EMAIL = "list-test@example.com"


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
async def clean_list_exams(db_session):
    yield
    ids = (await db_session.scalars(select(Exam.id).where(Exam.email == LIST_EMAIL))).all()
    if ids:
        await db_session.execute(delete(ExamAnswer).where(ExamAnswer.exam_id.in_(ids)))
        await db_session.execute(delete(Exam).where(Exam.id.in_(ids)))
        await db_session.commit()


async def _mk_exam(
    session,
    *,
    completed: bool = False,
    answer_statuses: tuple[str, ...] = ("unanswered",),
    result: str | None = None,
    total_score: int | None = None,
    created_at: datetime | None = None,
) -> Exam:
    exam = Exam(
        email=LIST_EMAIL,
        question_count=len(answer_statuses),
        duration_minutes=15,
        completed_at=_now() if completed else None,
        result_status=result,
        total_score=total_score,
    )
    if created_at is not None:
        exam.created_at = created_at
    session.add(exam)
    await session.flush()
    for order, st in enumerate(answer_statuses):
        session.add(
            ExamAnswer(
                exam_id=exam.id,
                sort_order=order,
                grading_status=st,
                submitted_at=_now() if st != "unanswered" else None,
                score=90 if st == "graded" else None,
            )
        )
    await session.commit()
    return exam


async def test_status_derivation_and_filters(client, auth_headers, db_session, clean_list_exams):
    e_inc = await _mk_exam(db_session)
    e_grading = await _mk_exam(db_session, completed=True, answer_statuses=("graded", "pending"))
    e_exc = await _mk_exam(
        db_session, completed=True, answer_statuses=("graded",), result="excellent", total_score=90
    )
    e_fail = await _mk_exam(
        db_session, completed=True, answer_statuses=("failed",), result="fail", total_score=30
    )

    resp = await client.get("/api/admin/exams", headers=auth_headers)
    assert resp.status_code == 200
    by_id = {i["id"]: i["status"] for i in resp.json()["items"]}
    assert by_id[e_inc.id] == "incomplete"
    assert by_id[e_grading.id] == "grading"
    assert by_id[e_exc.id] == "excellent"
    assert by_id[e_fail.id] == "fail"

    # status filter
    resp = await client.get(
        "/api/admin/exams", params={"status": "excellent"}, headers=auth_headers
    )
    items = resp.json()["items"]
    assert {i["id"] for i in items} == {e_exc.id}
    # 未完成的考试完成时间与分数为空
    resp = await client.get(
        "/api/admin/exams", params={"status": "incomplete"}, headers=auth_headers
    )
    inc = next(i for i in resp.json()["items"] if i["id"] == e_inc.id)
    assert inc["completed_at"] is None and inc["total_score"] is None


async def test_time_range_filter(client, auth_headers, db_session, clean_list_exams):
    old = await _mk_exam(db_session, created_at=_now() - timedelta(days=10))
    recent = await _mk_exam(db_session)

    resp = await client.get("/api/admin/exams", headers=auth_headers)  # 默认近 1 周
    ids = {i["id"] for i in resp.json()["items"]}
    assert recent.id in ids and old.id not in ids

    resp = await client.get("/api/admin/exams", params={"days": 30}, headers=auth_headers)
    ids = {i["id"] for i in resp.json()["items"]}
    assert old.id in ids

    # 组合过滤：状态 + 时间
    await db_session.execute(
        delete(Exam).where(Exam.id == old.id)
    )
    await db_session.commit()
    resp = await client.get(
        "/api/admin/exams", params={"days": 30, "status": "incomplete"}, headers=auth_headers
    )
    assert all(i["status"] == "incomplete" for i in resp.json()["items"])
