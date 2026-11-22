"""Question seed data loader (idempotent, design D10)."""
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Question

_DATA_FILE = Path(__file__).resolve().parent / "questions.json"


def load_questions() -> list[dict[str, Any]]:
    data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    assert len(data) == 30, f"expected 30 seed questions, got {len(data)}"
    return data


def content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


async def seed_questions(session: AsyncSession) -> tuple[int, int]:
    """Insert missing seed questions; returns (inserted, skipped)."""
    existing = {
        content_hash(c) for (c,) in await session.execute(select(Question.content))
    }
    inserted = skipped = 0
    for item in load_questions():
        if content_hash(item["content"]) in existing:
            skipped += 1
            continue
        session.add(
            Question(content=item["content"], reference_answer=item["reference_answer"])
        )
        existing.add(content_hash(item["content"]))
        inserted += 1
    await session.commit()
    return inserted, skipped
