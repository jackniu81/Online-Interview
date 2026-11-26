"""Candidate exam endpoints (capability: exam-taking, design D4/D5)."""
import math
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, func, select

from app.crypto import decrypt_exam_token
from app.db import get_db
from app.models import Exam, ExamAnswer, ExamQuestion, GradingStatus
from app.security import create_exam_token, require_exam_session
from app.services import autosubmit

router = APIRouter(prefix="/api/exams", tags=["exam-taking"])

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
INVALID_LINK = HTTPException(status_code=404, detail="链接无效")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _resolve_exam(session, token: str) -> Exam:
    """Decrypt token -> exam, or the unified invalid-link error (no info leak)."""
    data = decrypt_exam_token(token)
    if data is None:
        raise INVALID_LINK
    exam = await session.get(Exam, data["exam_id"])
    if exam is None or exam.email != data["email"]:
        raise INVALID_LINK
    return exam


def _remaining_seconds(exam: Exam) -> int:
    """Ceiling of seconds left (full duration right after start, never <0).

    ``started_at`` is re-read from the DB, whose value is second-precision after
    Postgres truncates microseconds, so a fresh start yields exactly the full
    duration instead of one second less.
    """
    if exam.started_at is None:
        return exam.duration_minutes * 60
    deadline = exam.started_at + timedelta(minutes=exam.duration_minutes)
    return max(0, math.ceil((deadline - _now()).total_seconds()))


@router.get("/info")
async def exam_info(
    t: str = Query(...),
    session=Depends(get_db),
) -> dict:
    exam = await _resolve_exam(session, t)
    started = exam.started_at is not None
    await autosubmit.ensure_not_timed_out(exam)
    if started:
        # lazy check commits in another session; re-read the authoritative row
        await session.refresh(exam)
    if exam.completed_at is not None:
        return {"completed": True}
    return {
        "completed": False,
        "started": exam.started_at is not None,
        "question_count": exam.question_count,
        "duration_minutes": exam.duration_minutes,
        "remaining_seconds": _remaining_seconds(exam),
    }


class BeginIn(BaseModel):
    token: str
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def name_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("姓名不能为空")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str) -> str:
        if not PHONE_RE.match(v):
            raise ValueError("手机号格式不正确")
        return v


@router.post("/begin")
async def exam_begin(
    body: BeginIn,
    session=Depends(get_db),
) -> dict:
    """Register candidate info, start (or resume) the exam, issue exam-scoped JWT."""
    exam = await _resolve_exam(session, body.token)
    if exam.completed_at is not None:
        raise HTTPException(status_code=409, detail="考试已完成")
    if await autosubmit.ensure_not_timed_out(exam):
        await session.refresh(exam)
    if exam.completed_at is not None:
        raise HTTPException(status_code=409, detail="考试已完成")

    first_start = exam.started_at is None
    if first_start:
        exam.started_at = _now()
    exam.candidate_name = body.name
    exam.candidate_phone = body.phone
    await session.commit()

    if not first_start:
        # resume: keep the original deadline, re-arm timer if its handle is gone
        deadline = exam.started_at + timedelta(minutes=exam.duration_minutes)
        if exam.id not in autosubmit._timers and _now() < deadline:
            autosubmit.schedule_auto_submit(exam.id, deadline)

    return {
        "exam_id": exam.id,
        "session_token": create_exam_token(exam.id, exam.duration_minutes),
        "started_at": exam.started_at,
        "remaining_seconds": _remaining_seconds(exam),
        "question_count": exam.question_count,
    }


@router.get("/current-question")
async def current_question(
    exam_id: int = Depends(require_exam_session),
    session=Depends(get_db),
) -> dict:
    """Serve only the smallest not-yet-submitted question (design D8, no going back)."""
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="链接无效")
    if await autosubmit.ensure_not_timed_out(exam):
        await session.refresh(exam)
    if exam.started_at is None:
        raise HTTPException(status_code=409, detail="考试尚未开始")
    if exam.completed_at is not None:
        raise HTTPException(status_code=409, detail="考试已完成")
    row = (await session.execute(
        select(ExamQuestion)
        .join(ExamAnswer, and_(ExamAnswer.exam_id == ExamQuestion.exam_id,
                               ExamAnswer.sort_order == ExamQuestion.sort_order))
        .where(ExamQuestion.exam_id == exam_id, ExamAnswer.submitted_at.is_(None))
        .order_by(ExamQuestion.sort_order)
        .limit(1)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=409, detail="所有题目已提交")
    return {
        "sort_order": row.sort_order,
        "question_content": row.question_content,
        "question_number": row.sort_order + 1,
        "question_count": exam.question_count,
        "remaining_seconds": _remaining_seconds(exam),
    }


class AnswerIn(BaseModel):
    sort_order: int
    answer_text: str = ""

    @field_validator("sort_order")
    @classmethod
    def order_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("sort_order 不能为负")
        return v


@router.post("/submit-answer")
async def submit_answer(
    body: AnswerIn,
    exam_id: int = Depends(require_exam_session),
    session=Depends(get_db),
) -> dict:
    """Accept exactly the current question; mark pending for async grading (design D2/D5)."""
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="链接无效")
    # lazy timeout check first: timed out -> auto-submit, then reject this request
    if await autosubmit.ensure_not_timed_out(exam):
        await session.refresh(exam)  # the hand-in committed in another session
    if exam.started_at is None:
        raise HTTPException(status_code=409, detail="考试尚未开始")
    if exam.completed_at is not None:
        raise HTTPException(status_code=409, detail="考试超时，已自动交卷")
    current = await session.scalar(
        select(func.min(ExamAnswer.sort_order)).where(
            ExamAnswer.exam_id == exam_id, ExamAnswer.submitted_at.is_(None)
        )
    )
    if current is None:
        raise HTTPException(status_code=409, detail="所有题目已提交")
    if body.sort_order != current:
        raise HTTPException(status_code=409, detail="只能提交当前题目（禁止重复或越序提交）")
    answer = await session.scalar(
        select(ExamAnswer).where(
            ExamAnswer.exam_id == exam_id, ExamAnswer.sort_order == body.sort_order
        )
    )
    answer.answer_text = body.answer_text
    answer.submitted_at = _now()
    answer.grading_status = GradingStatus.PENDING.value
    is_last = body.sort_order == exam.question_count - 1
    if is_last:
        # last question submitted -> hand in (conditional update keeps it idempotent)
        await autosubmit.finish_exam(session, exam_id)
        autosubmit.cancel_timer(exam_id)
    await session.commit()
    return {
        "ok": True,
        "sort_order": body.sort_order,
        "is_last": is_last,
        "next_order": None if is_last else body.sort_order + 1,
        "remaining_seconds": _remaining_seconds(exam),
    }


@router.post("/finish")
async def finish_early(
    exam_id: int = Depends(require_exam_session),
    session=Depends(get_db),
) -> dict:
    """Hand in now (countdown hit zero client-side, etc); unanswered stay empty."""
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="链接无效")
    if exam.started_at is None:
        raise HTTPException(status_code=409, detail="考试尚未开始")
    finished = await autosubmit.finish_exam(session, exam_id)
    autosubmit.cancel_timer(exam_id)
    await session.commit()
    return {"ok": True, "just_finished": finished}
