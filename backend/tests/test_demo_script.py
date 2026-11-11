"""시연 대본 5분 순서(명세 4.8-8)를 API만으로 끝까지 돌린다. 서버 파이프라인이 이어지는지의 기준.

세션 A(정상): 리셋 → 오늘 → 풀기(오답 → 힌트 → 정답) → 수다 1턴 → 다리 놓기 → 끝
             → 강사 메모 → 승인 → 보호자 카드
세션 B(🔴): 리셋 → 풀기 1턴 → 수다 중 R1 → 🔴 → 보호자 🔴 1줄
LLM은 scripted(기본 의존성). 문장은 명세에 있는 합성 문장만 쓴다.
"""

from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import config
from app.actors import DEMO_CHILD_ID, DEMO_GUARDIAN_ID, DEMO_INSTRUCTOR_ID
from app.db import get_db
from app.main import create_app
from app.timeutil import get_now

NOW = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)  # 서울 11-10 17:00
TOKEN = "synthetic-demo-token"
CHILD = {"X-Demo-Role": "child", "X-Demo-Actor": DEMO_CHILD_ID}
GUARDIAN = {"X-Demo-Role": "guardian", "X-Demo-Actor": DEMO_GUARDIAN_ID}
INSTRUCTOR = {"X-Demo-Role": "instructor", "X-Demo-Actor": DEMO_INSTRUCTOR_ID}


@pytest_asyncio.fixture
async def client(db_session, monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", TOKEN)
    monkeypatch.setattr(config, "_timer_scale_override", None)
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: NOW
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _reset(c, **opts):
    r = await c.post("/api/v1/demo/reset", headers={"X-Demo-Token": TOKEN}, json=opts)
    assert r.status_code == 200, r.text
    roles = {a["role"]: a["id"] for a in r.json()["actors"]}
    assert roles == {
        "child": DEMO_CHILD_ID,
        "guardian": DEMO_GUARDIAN_ID,
        "instructor": DEMO_INSTRUCTOR_ID,
    }


async def _say(c, sid, text):
    r = await c.post(
        f"/api/v1/sessions/{sid}/messages", headers=CHILD, json={"kind": "text", "text": text}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_session_a_normal_then_guardian_card(client):
    c = client
    await _reset(c, style="EBSP", honorific="hyung", polite=False, timer_scale=10)

    today = (await c.get("/api/v1/me/today", headers=CHILD)).json()
    assert today["streak_text"] == "3일째 같이 했어"
    assert today["today_task"]["source"] == "instructor"

    start = (await c.post("/api/v1/sessions", headers=CHILD)).json()
    sid = start["session_id"]

    assert (await _say(c, sid, "3/6"))["judge"] == "wrong"
    hint = await c.post(f"/api/v1/sessions/{sid}/messages", headers=CHILD, json={"kind": "hint"})
    assert hint.json()["hint_level"] == 1
    assert (await _say(c, sid, "3/8"))["judge"] == "correct"

    phase = (
        await c.post(f"/api/v1/sessions/{sid}/phase", headers=CHILD, json={"to": "chat"})
    ).json()
    assert phase["state"] == "chat"
    assert phase["streak_days"] == 4
    # 리셋의 timer_scale 10 → 수다 마감 1분 뒤
    deadline = datetime.fromisoformat(phase["deadline_at"])
    assert (deadline - NOW).total_seconds() == 60

    chat = await _say(c, sid, "오늘 체육 시간에 피구 했어")
    assert chat["state"] == "chat" and chat["crisis"] is None

    end_chat = await c.post(f"/api/v1/sessions/{sid}/phase", headers=CHILD, json={"to": "bridge"})
    assert end_chat.json()["state"] == "bridge"
    bridge = (await c.get(f"/api/v1/sessions/{sid}/bridge", headers=CHILD)).json()
    assert len(bridge["quiz_options"]) == 3 and len(bridge["summary"]) == 3
    quiz_id = bridge["quiz_options"][0]["id"]
    end = await c.post(
        f"/api/v1/sessions/{sid}/end", headers=CHILD, json={"quiz_problem_id": quiz_id}
    )
    assert end.json()["state"] == "ended"

    note = await c.post(
        "/api/v1/instructor/notes",
        headers=INSTRUCTOR,
        json={
            "student_id": DEMO_CHILD_ID,
            "covered": "분수 ÷ 자연수",
            "stuck": "곱셈으로 바꾸기",
            "homework": "교재 12쪽",
            "memo": "",
        },
    )
    assert note.status_code == 200
    note_id = note.json()["note_id"]

    card = (await c.get("/api/v1/guardian/today", headers=GUARDIAN)).json()
    assert card["instructor_comment"] is None  # 승인 전 — 프론트가 「선생님이 확인하면」 문구

    ok = await c.post(
        f"/api/v1/instructor/notes/{note_id}/approve",
        headers=INSTRUCTOR,
        json={"final_body": "오늘 분수 나눗셈을 잘 해냈습니다.", "action": "publish"},
    )
    assert ok.json()["status"] == "published"

    card = (await c.get("/api/v1/guardian/today", headers=GUARDIAN)).json()
    assert card["alert"] is None
    assert card["child_line"] == bridge["guardian_line"]
    assert card["quiz"]["text"] == bridge["quiz_options"][0]["text"]
    assert card["instructor_comment"] == "오늘 분수 나눗셈을 잘 해냈습니다."
    assert "피구" not in str(card)  # 수다 내용은 보호자에게 가지 않는다


async def test_reset_then_session_b_crisis(client):
    c = client
    await _reset(c)  # 세션 A의 흔적이 있어도 지운다
    await _reset(c, style="EQLC", honorific="unni", polite=True)

    sid = (await c.post("/api/v1/sessions", headers=CHILD)).json()["session_id"]
    assert (await _say(c, sid, "3/8"))["judge"] == "correct"
    await c.post(f"/api/v1/sessions/{sid}/phase", headers=CHILD, json={"to": "chat"})

    red = await _say(c, sid, "요즘 그냥 죽고 싶어")  # 부록 A R1, 시연 대본 문장
    assert red["state"] == "crisis"
    assert red["crisis"]["hotlines"] == ["109", "1388"]

    card = (await c.get("/api/v1/guardian/today", headers=GUARDIAN)).json()
    assert card["alert"] is not None
    assert card["alert"]["hotlines"] == ["109", "1388"]
    assert card["child_line"] is None  # 다리 놓기를 건너뛰었다

    today = (await c.get("/api/v1/me/today", headers=CHILD)).json()
    assert today["session"]["state"] == "crisis"
    assert today["streak_text"] == "4일째 같이 했어"  # 🔴여도 연속은 깎지 않는다
