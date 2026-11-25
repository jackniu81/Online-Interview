"""Candidate exam endpoints (capability: exam-taking, design D4/D5)."""
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator

from app.crypto import decrypt_exam_token
from app.db import get_db
from app.models import Exam
from app.security import create_exam_token
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
    if exam.started_at is None:
        return exam.duration_minutes * 60
    left = int(exam.duration_minutes * 60 - (_now() - exam.started_at).total_seconds())
    return max(left, 0)


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
    await autosubmit.ensure_not_timed_out(exam)
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
