"""Question bank CRUD API tests (task 4.1)."""
import pytest
from sqlalchemy import delete

from app.models import Question

MARK = "【qtest】"


@pytest.fixture
async def cleanup(db_session):
    yield
    await db_session.execute(delete(Question).where(Question.content.startswith(MARK)))
    await db_session.commit()


async def _create(client, auth_headers, content, ref="参考答案"):
    return await client.post(
        "/api/admin/questions",
        json={"content": content, "reference_answer": ref},
        headers=auth_headers,
    )


async def test_create_and_fetch(client, auth_headers, cleanup):
    resp = await _create(client, auth_headers, f"{MARK}第一题：请说明 X")
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] > 0
    assert data["reference_answer"] == "参考答案"


async def test_blank_fields_rejected(client, auth_headers):
    resp = await _create(client, auth_headers, "   ", ref="ref")
    assert resp.status_code == 422
    resp = await _create(client, auth_headers, f"{MARK}ok", ref="  ")
    assert resp.status_code == 422


async def test_list_requires_auth(client):
    resp = await client.get("/api/admin/questions")
    assert resp.status_code == 401


async def test_update_and_delete(client, auth_headers, cleanup):
    qid = (await _create(client, auth_headers, f"{MARK}将被修改")).json()["id"]

    resp = await client.put(
        f"/api/admin/questions/{qid}",
        json={"content": f"{MARK}修改后", "reference_answer": "新参考答案"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == f"{MARK}修改后"

    resp = await client.delete(f"/api/admin/questions/{qid}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.put(
        f"/api/admin/questions/{qid}",
        json={"content": f"{MARK}x", "reference_answer": "y"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


async def test_pagination_order_and_search(client, auth_headers, cleanup):
    ids = []
    for i in range(3):
        r = await _create(client, auth_headers, f"{MARK}分页题目{i}")
        ids.append(r.json()["id"])
    await _create(client, auth_headers, f"{MARK}无关题目内容", ref=f"含关键字{MARK}在答案里")

    resp = await client.get(
        "/api/admin/questions", params={"page": 1, "page_size": 2}, headers=auth_headers
    )
    body = resp.json()
    assert body["total"] >= 4
    assert len(body["items"]) == 2
    # newest first: id desc breaks created_at ties
    assert body["items"][0]["id"] >= body["items"][1]["id"]

    resp = await client.get(
        "/api/admin/questions", params={"q": "分页题目"}, headers=auth_headers
    )
    found = resp.json()
    assert found["total"] == 3

    # search matches reference_answer too
    resp = await client.get(
        "/api/admin/questions", params={"q": MARK}, headers=auth_headers
    )
    assert resp.json()["total"] == 4
