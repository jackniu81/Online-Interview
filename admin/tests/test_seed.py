"""Seed questions data & idempotency tests (task 2.2)."""
from sqlalchemy import func, select

from app.models import Question
from app.seed import load_questions, seed_questions


def test_seed_data_valid():
    items = load_questions()  # asserts exactly 30
    for item in items:
        assert item["content"].strip(), "empty question content"
        assert item["reference_answer"].strip(), "empty reference answer"


async def test_seed_idempotent(db_session):
    total_before = await db_session.scalar(select(func.count()).select_from(Question))
    inserted, skipped = await seed_questions(db_session)
    assert inserted + skipped == 30

    # running again must insert nothing and leave the total unchanged
    inserted2, skipped2 = await seed_questions(db_session)
    assert inserted2 == 0
    assert skipped2 == 30

    total_after = await db_session.scalar(select(func.count()).select_from(Question))
    assert total_after == total_before + inserted
