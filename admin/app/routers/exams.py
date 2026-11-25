"""Exam management endpoints (capability: exam-management)."""
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crypto import encrypt_exam_token
from app.db import get_db
from app.models import Exam, ExamAnswer, ExamQuestion, GradingStatus, Question
from app.security import require_admin

router = APIRouter(prefix="/api/admin/exams", tags=["exam-management"])

ALLOWED_QUESTION_COUNTS = {5, 10, 15, 20}
ALLOWED_DURATIONS = {15, 20, 30, 40}
TERMINAL_GRADING = ("graded", "failed")


def display_status_expr():
    """SQL expression deriving 未完成/评分中/excellent/pass/fail (design D3)."""
    grading_exists = exists(
        select(ExamAnswer.id).where(
            ExamAnswer.exam_id == Exam.id,
            ExamAnswer.grading_status.not_in(TERMINAL_GRADING),
        )
    )
    return case(
        (Exam.completed_at.is_(None), "incomplete"),
        (grading_exists, "grading"),
        else_=Exam.result_status,
    )


@router.get("")
async def list_exams(
    status: str = Query("all"),
    days: int = Query(7, ge=1, le=365),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    status_expr = display_status_expr()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(Exam, status_expr.label("status")).where(Exam.created_at >= since)
    if status != "all":
        stmt = stmt.where(status_expr == status)
    total = await session.scalar(
        select(func.count()).select_from(stmt.subquery())
    )
    rows = (
        await session.execute(
            stmt.order_by(Exam.created_at.desc(), Exam.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        {
            "id": exam.id,
            "email": exam.email,
            "candidate_name": exam.candidate_name,
            "question_count": exam.question_count,
            "duration_minutes": exam.duration_minutes,
            "created_at": exam.created_at,
            "completed_at": exam.completed_at,
            "total_score": exam.total_score,
            "status": st,
        }
        for exam, st in rows
    ]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


@router.get("/{exam_id}")
async def get_exam_detail(
    exam_id: int,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Exam detail: candidate info, params, per-question answers/grading (task 5.3)."""
    row = await session.execute(
        select(Exam, display_status_expr().label("status")).where(Exam.id == exam_id)
    )
    found = row.one_or_none()
    if found is None:
        raise HTTPException(status_code=404, detail="考试不存在")
    exam, st = found

    questions = (await session.scalars(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id).order_by(ExamQuestion.sort_order)
    )).all()
    answers = (await session.scalars(
        select(ExamAnswer).where(ExamAnswer.exam_id == exam_id).order_by(ExamAnswer.sort_order)
    )).all()
    answers_by_order = {a.sort_order: a for a in answers}

    items = []
    for q in questions:
        a = answers_by_order.get(q.sort_order)
        items.append(
            {
                "sort_order": q.sort_order,
                "question_content": q.question_content,
                "answer_text": a.answer_text if a else None,
                "submitted_at": a.submitted_at if a else None,
                "score": a.score if a else None,
                "feedback": a.feedback if a else None,
                "grading_status": a.grading_status if a else GradingStatus.UNANSWERED.value,
            }
        )

    return {
        "id": exam.id,
        "email": exam.email,
        "candidate_name": exam.candidate_name,
        "candidate_phone": exam.candidate_phone,
        "question_count": exam.question_count,
        "duration_minutes": exam.duration_minutes,
        "created_at": exam.created_at,
        "started_at": exam.started_at,
        "completed_at": exam.completed_at,
        "total_score": exam.total_score,
        "status": st,
        "questions": items,
    }


class ExamCreateIn(BaseModel):
    email: EmailStr
    question_count: int = 5
    duration_minutes: int = 15

    @field_validator("question_count")
    @classmethod
    def count_whitelist(cls, v: int) -> int:
        if v not in ALLOWED_QUESTION_COUNTS:
            raise ValueError("题数必须为 5/10/15/20")
        return v

    @field_validator("duration_minutes")
    @classmethod
    def duration_whitelist(cls, v: int) -> int:
        if v not in ALLOWED_DURATIONS:
            raise ValueError("时长必须为 15/20/30/40 分钟")
        return v


async def create_exam(
    session: AsyncSession, email: str, question_count: int, duration_minutes: int
) -> Exam:
    """Sample questions, freeze snapshots, pre-create answer rows. Raises ValueError."""
    ids = (
        await session.scalars(select(Question.id).order_by(Question.id))
    ).all()
    if len(ids) < question_count:
        raise ValueError(f"题库题目不足：需要 {question_count} 题，当前共 {len(ids)} 题")

    sampled_ids = random.sample(list(ids), question_count)
    questions = (
        await session.scalars(select(Question).where(Question.id.in_(sampled_ids)))
    ).all()
    by_id = {q.id: q for q in questions}

    exam = Exam(
        email=email, question_count=question_count, duration_minutes=duration_minutes
    )
    session.add(exam)
    await session.flush()  # assign exam.id

    for order, qid in enumerate(sampled_ids):
        src = by_id[qid]
        session.add(
            ExamQuestion(
                exam_id=exam.id,
                sort_order=order,
                question_content=src.content,
                reference_answer=src.reference_answer,
            )
        )
        session.add(ExamAnswer(exam_id=exam.id, sort_order=order))
    await session.commit()
    await session.refresh(exam)
    return exam


@router.post("", status_code=201)
async def create_exam_endpoint(
    body: ExamCreateIn,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        exam = await create_exam(
            session, body.email, body.question_count, body.duration_minutes
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    token = encrypt_exam_token(exam.id, exam.email)
    link = f"{get_settings().frontend_url}/exam?t={token}"
    return {
        "id": exam.id,
        "email": exam.email,
        "question_count": exam.question_count,
        "duration_minutes": exam.duration_minutes,
        "created_at": exam.created_at,
        "link": link,
    }
