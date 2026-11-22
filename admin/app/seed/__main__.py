"""CLI: python -m app.seed — idempotently load the 30 seed questions."""
import asyncio

from app.db import dispose_db, init_db
from app.seed import seed_questions


async def main() -> None:
    init_db()
    from app import db

    assert db.SessionLocal is not None
    async with db.SessionLocal() as session:
        inserted, skipped = await seed_questions(session)
    await dispose_db()
    print(f"seed done: {inserted} inserted, {skipped} already existed")


if __name__ == "__main__":
    asyncio.run(main())
