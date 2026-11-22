"""Question bank CRUD endpoints (capability: question-bank)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Question
from app.security import require_admin

router = APIRouter(prefix="/api/admin/questions", tags=["question-bank"])

SUMMARY_LEN = 80


class QuestionIn(BaseModel):
    content: str
    reference_answer: str

    @field_validator("content", "reference_answer")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空")
        return v


class QuestionOut(BaseModel):
    id: int
    content: str
    reference_answer: str
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionListItem(QuestionOut):
    summary: str


@router.get("")
async def list_questions(
    page: int = 1,
    page_size: int = 20,
    q: str = "",
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    stmt = select(Question)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Question.content.ilike(like), Question.reference_answer.ilike(like)))
    total = await session.scalar(
        select(func.count()).select_from(stmt.subquery())
    )
    rows = (
        await session.scalars(
            stmt.order_by(Question.created_at.desc(), Question.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = []
    for row in rows:
        data = QuestionOut.model_validate(row).model_dump()
        data["summary"] = row.content[:SUMMARY_LEN]
        items.append(data)
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


@router.post("", status_code=201)
async def create_question(
    body: QuestionIn,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> QuestionOut:
    question = Question(content=body.content, reference_answer=body.reference_answer)
    session.add(question)
    await session.commit()
    await session.refresh(question)
    return QuestionOut.model_validate(question)


async def _get_or_404(session: AsyncSession, question_id: int) -> Question:
    question = await session.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return question


@router.put("/{question_id}")
async def update_question(
    question_id: int,
    body: QuestionIn,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> QuestionOut:
    question = await _get_or_404(session, question_id)
    question.content = body.content
    question.reference_answer = body.reference_answer
    await session.commit()
    await session.refresh(question)
    return QuestionOut.model_validate(question)


@router.delete("/{question_id}", status_code=204)
async def delete_question(
    question_id: int,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    question = await _get_or_404(session, question_id)
    # hard delete: exams keep their own snapshots, unaffected (spec question-bank)
    await session.delete(question)
    await session.commit()
