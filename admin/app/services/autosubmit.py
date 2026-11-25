"""Server-authoritative auto-submit (design D5): delayed task + lazy check.

Both paths converge on ``auto_submit``, whose ``completed_at IS NULL`` conditional
update guarantees that only one of (candidate final submit / timer / lazy check)
takes effect.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Exam

TIMER_BUFFER_SECONDS = 5

# exam_id -> asyncio.TimerHandle, kept so a lifespan shutdown can cancel them
_timers: dict[int, asyncio.TimerHandle] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def deadline_of(exam: Exam) -> datetime | None:
    if exam.started_at is None or exam.completed_at is not None:
        return None
    return exam.started_at + timedelta(minutes=exam.duration_minutes)


async def auto_submit(exam_id: int) -> bool:
    """Finish the exam unconditionally; empty answers stay as-is. True if this call finished it."""
    assert SessionLocal is not None
    async with SessionLocal() as session:
        result = await session.execute(
            update(Exam)
            .where(Exam.id == exam_id, Exam.completed_at.is_(None))
            .values(completed_at=_now())
        )
        await session.commit()
        return result.rowcount == 1


async def _run_auto_submit(exam_id: int) -> None:
    _timers.pop(exam_id, None)
    try:
        await auto_submit(exam_id)
    except Exception:  # pragma: no cover - keep the timer loop alive
        import logging

        logging.getLogger("app.autosubmit").exception("auto_submit failed for exam %s", exam_id)


def schedule_auto_submit(exam_id: int, deadline: datetime) -> None:
    """Register an in-process timer; idempotent per exam."""
    if exam_id in _timers:
        return
    delay = max((deadline - _now()).total_seconds(), 0) + TIMER_BUFFER_SECONDS
    loop = asyncio.get_running_loop()
    _timers[exam_id] = loop.call_later(delay, lambda: asyncio.ensure_future(_run_auto_submit(exam_id)))


def cancel_timer(exam_id: int) -> None:
    handle = _timers.pop(exam_id, None)
    if handle:
        handle.cancel()


def cancel_all() -> None:
    """Cancel every pending timer (lifespan shutdown)."""
    for handle in _timers.values():
        handle.cancel()
    _timers.clear()


async def ensure_not_timed_out(exam: Exam) -> bool:
    """Lazy timeout check (task 6.3). Returns True if the exam just got finished here."""
    deadline = deadline_of(exam)
    if deadline is None or _now() < deadline:
        return False
    finished = await auto_submit(exam.id)
    cancel_timer(exam.id)
    return finished


async def restore_timers() -> int:
    """On startup, re-schedule (or immediately run) timers for started, unfinished exams."""
    assert SessionLocal is not None
    count = 0
    async with SessionLocal() as session:
        exams = (
            await session.scalars(
                select(Exam).where(Exam.started_at.is_not(None), Exam.completed_at.is_(None))
            )
        ).all()
        for exam in exams:
            deadline = exam.started_at + timedelta(minutes=exam.duration_minutes)
            if _now() >= deadline:
                await auto_submit(exam.id)
            else:
                schedule_auto_submit(exam.id, deadline)
            count += 1
    return count
