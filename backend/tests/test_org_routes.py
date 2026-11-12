"""명세 4.12 연결·학원·소속·원장·운영자·강의실(설계 1112 §9·§10, org_routes.py).

규칙·문구는 frontend/src/api/org.ts 그대로. 이름·아이디·이메일·사업자번호는 모두 합성 값.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import config
from app.api import get_llm
from app.db import get_db
from app.instructor import get_draft_adapter
from app.llm import ScriptedAdapter
from app.main import create_app
from app.seed import load_seed
from app.timeutil import get_now

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10 06:00
BASE = "/api/v1/compat"
PW = "abcd1234"
FORM = {
    "orgType": "학원",
    "academyName": "  별빛수학  ",
    "bizNo": "111-22-33333",
    "ceo": "가대표",
    "phone": "000-0000-0000",
    "address": "예시시 예시구",
}


class Clock:
    def __init__(self) -> None:
        self.now = NOW


@pytest_asyncio.fixture
async def clock() -> Clock:
    return Clock()


@pytest_asyncio.fixture
async def client(db_session, clock, monkeypatch):
    monkeypatch.setattr(config, "_timer_scale_override", None)
    await load_seed(db_session)
    await db_session.flush()
    app = create_app()

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: clock.now
    app.dependency_overrides[get_llm] = ScriptedAdapter.from_file
    app.dependency_overrides[get_draft_adapter] = ScriptedAdapter.from_file
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class Who:
    """로그인한 한 사람: Bearer 토큰으로 부른다(쿠키 저장소는 비운다)."""

    def __init__(self, client: AsyncClient, token: str, me: dict, trial: str | None) -> None:
        self.client, self.token, self.me, self.trial = client, token, me, trial

    @property
    def id(self) -> str:
        return self.me["id"]

    def headers(self) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self.token}"}
        if self.trial:
            h["X-Trial-Id"] = self.trial
        return h

    async def call(self, method: str, path: str, **kw):
        return await self.client.request(method, f"{BASE}{path}", headers=self.headers(), **kw)

    async def ok(self, method: str, path: str, **kw) -> Any:
        r = await self.call(method, path, **kw)
        assert r.status_code in (200, 204), r.text
        return r.json() if r.status_code == 200 else None

    async def refresh(self) -> dict:
        self.me = await self.ok("GET", "/me")
        return self.me

    async def notices(self) -> list[str]:
        return [n["text"] for n in await self.ok("GET", "/notices")]


def _take(client: AsyncClient, r) -> str:
    assert r.status_code == 200, r.text
    token = r.cookies.get("cm_session")
    assert token
    client.cookies.clear()
    return token


async def _signup(client, role: str, login: str, trial: str | None = None, **extra) -> Who:
    body = {
        "role": role,
        "loginId": login,
        "password": PW,
        "name": extra.pop("name", login[:10]),
        "agreements": {"terms": True, "privacy": True, "marketing": False},
        **extra,
    }
    if role == "student":
        body.setdefault("grade", 5)
    else:
        body.setdefault("email", f"{login}@example.com")
    headers = {"X-Trial-Id": trial} if trial else {}
    r = await client.post(f"{BASE}/auth/signup", json=body, headers=headers)
    return Who(client, _take(client, r), r.json(), trial)


async def _trial(client) -> str:
    r = await client.post(f"{BASE}/trial")
    assert r.status_code == 200
    return r.json()["trialId"]


async def _demo(client, trial: str, key: str) -> Who:
    r = await client.post(f"{BASE}/demo/login", json={"userId": key}, headers={"X-Trial-Id": trial})
    return Who(client, _take(client, r), r.json(), trial)


async def _linked_pair(client, kid: str, mom: str, trial: str | None = None) -> tuple[Who, Who]:
    """학생 가입 → 보호자 가입 → 보호자가 아이 코드 + 동의로 바로 연결."""
    s = await _signup(client, "student", kid, trial)
    g = await _signup(client, "guardian", mom, trial)
    await g.ok("POST", "/links", json={"code": s.me["linkCode"], "consent": True})
    await s.refresh()
    await g.refresh()
    return s, g


# --- 연결 --------------------------------------------------------------------------------


async def test_student_requests_link_guardian_confirms(client):
    s = await _signup(client, "student", "kid_one", name="새싹")
    g = await _signup(client, "guardian", "mom_one", name="새싹엄마")
    # 잘못된 코드들
    r = await s.call("POST", "/links", json={"code": "ZZZZZZ"})
    assert (
        r.status_code == 404
        and r.json()["detail"] == "코드를 찾지 못했어요. 6자리를 다시 확인해 주세요."
    )
    r = await s.call("POST", "/links", json={"code": s.me["linkCode"]})
    assert r.json()["detail"] == "내 코드는 넣을 수 없어요."
    other_kid = await _signup(client, "student", "kid_two")
    r = await s.call("POST", "/links", json={"code": other_kid.me["linkCode"]})
    assert r.json()["detail"] == "보호자의 코드를 넣어 주세요."
    # 학생이 보호자 코드(소문자·하이픈 섞여도) → 대기
    code = g.me["linkCode"].lower()
    me = await s.ok("POST", "/links", json={"code": f"{code[:3]}-{code[3:]}"})
    assert me["pendingLinks"] == [{"id": g.id, "name": "새싹엄마", "role": "guardian"}]
    assert me["linked"] == [] and me["restricted"] is True
    assert "새싹 학생이 연결을 요청했어요. 동의하면 연결돼요." in await g.notices()
    g_me = await g.refresh()
    assert [p["id"] for p in g_me["pendingLinks"]] == [s.id]
    # 동의 없이 → 거절, 동의 → 연결
    r = await g.call("POST", f"/links/{s.id}/confirm", json={"consent": False})
    assert r.status_code == 422 and r.json()["detail"] == "보호자 동의에 체크해 주세요."
    g_me = await g.ok("POST", f"/links/{s.id}/confirm", json={"consent": True})
    assert [p["id"] for p in g_me["linked"]] == [s.id] and g_me["pendingLinks"] == []
    s_me = await s.refresh()
    assert s_me["restricted"] is False and [p["id"] for p in s_me["linked"]] == [g.id]
    assert "새싹엄마님이 동의해서 연결됐어! 이제 학원에 들어갈 수 있어." in await s.notices()
    # 다시 확인 → 요청 없음, 다시 연결 → 이미
    r = await g.call("POST", f"/links/{s.id}/confirm", json={"consent": True})
    assert r.status_code == 404 and r.json()["detail"] == "연결 요청을 찾지 못했어요."
    r = await s.call("POST", "/links", json={"code": g.me["linkCode"]})
    assert r.status_code == 409 and r.json()["detail"] == "이미 연결되어 있어요."
    # 학습지도자는 못 쓴다
    teacher = await _signup(client, "teacher", "teach_one")
    assert (await teacher.call("POST", "/links", json={"code": "ABCDEF"})).status_code == 403


async def test_guardian_links_directly_with_consent(client):
    s = await _signup(client, "student", "kid_one", name="새싹")
    g = await _signup(client, "guardian", "mom_one", name="새싹엄마")
    r = await g.call("POST", "/links", json={"code": s.me["linkCode"], "consent": False})
    assert r.status_code == 422
    assert r.json()["detail"] == "만 14세 미만 아이는 보호자 동의가 있어야 연결할 수 있어요."
    r = await g.call("POST", "/links", json={"code": g.me["linkCode"], "consent": True})
    assert r.json()["detail"] == "내 코드는 넣을 수 없어요."
    me = await g.ok("POST", "/links", json={"code": s.me["linkCode"], "consent": True})
    assert [p["id"] for p in me["linked"]] == [s.id]
    assert "새싹엄마님과 연결됐어!" in await s.notices()
    assert (await s.refresh())["restricted"] is False
    # 학생이 먼저 요청해 둔 대기도 보호자 직접 연결로 바뀐다
    s2 = await _signup(client, "student", "kid_two")
    await s2.ok("POST", "/links", json={"code": g.me["linkCode"]})
    me = await g.ok("POST", "/links", json={"code": s2.me["linkCode"], "consent": True})
    assert {p["id"] for p in me["linked"]} == {s.id, s2.id} and me["pendingLinks"] == []


# --- 학원 자동 등록 ----------------------------------------------------------------------


async def _entry_code(owner: Who) -> str:
    dash = await owner.ok("POST", "/owner/entry-code")
    return dash["entryCode"]["code"]


async def _real_owner(client, trial: str, login: str, academy: str) -> Who:
    """실제 강사 가입 → 신청 → 그 화면 세트 운영자 승인 = 실제 학원 원장(영역 격리 뒤 실제 학생용)."""
    boss = await _signup(client, "teacher", login, trial)
    me = await boss.ok(
        "POST", "/teacher/academy-applications", json={**FORM, "academyName": academy}
    )
    op = await _demo(client, trial, "op")
    path = f"/operator/applications/{me['application']['id']}/review"
    await op.ok("POST", path, json={"decision": "승인"})
    return boss


async def test_auto_enroll_pairs_siblings_and_conflict(client, clock):
    t = await _trial(client)
    # 실제 가입 학생·보호자는 실제 학원에만 닿는다(영역 격리) → 실제 학원을 세운다
    own1 = await _real_owner(client, t, "boss_one", "우왕수학학원")
    # 제한 모드 학생은 입장 불가
    lone = await _signup(client, "student", "kid_lone", t)
    code = await _entry_code(own1)
    r = await lone.call("POST", "/academy/join", json={"code": code})
    assert r.status_code == 403
    assert r.json()["detail"] == "보호자와 먼저 연결해야 학원에 들어갈 수 있어요."
    # 학생이 들어가면 연결된 보호자도 같이
    s, g = await _linked_pair(client, "kid_one", "mom_one", t)
    r = await s.call("POST", "/academy/join", json={"code": "000000" if code != "000000" else "1"})
    assert r.status_code == 404
    assert r.json()["detail"] == "코드가 맞지 않아요. 학원에서 받은 6자리를 확인해 주세요."
    me = await s.ok("POST", "/academy/join", json={"code": f"{code[:3]} {code[3:]}"})
    assert me["academy"]["name"] == "우왕수학학원"
    assert (await g.refresh())["academy"]["name"] == "우왕수학학원"
    r = await s.call("POST", "/academy/join", json={"code": code})
    assert r.status_code == 409 and r.json()["detail"] == "이미 학원에 등록되어 있어요."
    # 보호자 → 아이: 아이가 2명이면 자동 등록 안 하고 안내
    mom2 = await _signup(client, "guardian", "mom_two", t)
    k2 = await _signup(client, "student", "kid_two", t)
    k3 = await _signup(client, "student", "kid_three", t)
    for k in (k2, k3):
        await mom2.ok("POST", "/links", json={"code": k.me["linkCode"], "consent": True})
    me = await mom2.ok("POST", "/academy/join", json={"code": code})
    assert me["academy"] is not None
    assert (await k2.refresh())["academy"] is None and (await k3.refresh())["academy"] is None
    assert any(x.startswith("아이가 여러 명이라") for x in await mom2.notices())
    # 보호자 → 아이 1명: 같이. 학원 있는 보호자와 새로 연결되면 아이도(syncLinkedPair)
    k4 = await _signup(client, "student", "kid_four", t)
    await k4.ok("POST", "/links", json={"code": g.me["linkCode"]})
    await g.ok("POST", f"/links/{k4.id}/confirm", json={"consent": True})
    # g는 이제 아이 둘(s, k4) → 형제 규칙: k4에게 자동 등록 안 함 + 안내
    assert (await k4.refresh())["academy"] is None
    assert any(x.startswith("아이가 여러 명이라") for x in await g.notices())
    # 보호자 한 명 + 아이 한 명: 아이가 학원 없고 보호자가 학원 있으면 아이도 등록
    k5 = await _signup(client, "student", "kid_five", t)
    mom5 = await _signup(client, "guardian", "mom_five", t)
    k6 = await _signup(client, "student", "kid_six", t)
    await mom5.ok("POST", "/links", json={"code": k6.me["linkCode"], "consent": True})
    await k6.ok("POST", "/academy/join", json={"code": code})
    assert (await mom5.refresh())["academy"] is not None  # 학생 → 보호자
    del k5
    # 충돌: 다른 학원에 있는 보호자에게 새 학원 학생이 들어가면 덮어쓰지 않고 둘 다 안내
    own2 = await _real_owner(client, t, "boss_two", "새싹영어학원")
    code2 = await _entry_code(own2)
    k7 = await _signup(client, "student", "kid_seven", t, name="일곱")
    await mom5.ok("POST", "/links", json={"code": k7.me["linkCode"], "consent": True})
    await k7.ok("POST", "/academy/join", json={"code": code2})
    assert (await mom5.refresh())["academy"]["name"] == "우왕수학학원"
    want = "이미 「우왕수학학원」에 등록되어 있어 「새싹영어학원」에 자동으로 옮기지 않았어요."
    assert want in await mom5.notices()
    assert any(
        x.startswith("보호자 mom_five님은 이미 「우왕수학학원」") for x in await k7.notices()
    )
    # 코드 만료
    clock.now += timedelta(minutes=11)
    k8, _ = await _linked_pair(client, "kid_eight", "mom_eight", t)
    r = await k8.call("POST", "/academy/join", json={"code": code2})
    assert r.status_code == 410
    assert r.json()["detail"] == "코드 시간이 지났어요. 학원에 새 코드를 요청해 주세요."


# --- 학원 신청 → 심사 → 원장 → 소속 → 강의실 → 오늘 수업 -------------------------------


async def test_full_academy_flow(client, clock):
    t = await _trial(client)
    # 체험 헤더 없이 가입한 강사도 화면(X-Trial-Id)에서 신청하면 그 세트 운영자가 심사한다
    boss = await _signup(client, "teacher", "boss_one", name="가원장")
    boss.trial = t
    r = await boss.call("POST", "/teacher/academy-applications", json={**FORM, "bizNo": "12"})
    assert r.status_code == 422 and r.json()["detail"].startswith("사업자등록번호는")
    r = await boss.call("POST", "/teacher/academy-applications", json={**FORM, "ceo": " "})
    assert r.json()["detail"] == "대표자와 연락처를 적어 주세요."
    me = await boss.ok("POST", "/teacher/academy-applications", json=FORM)
    assert me["application"]["status"] == "심사 중"
    assert me["application"]["academyName"] == "별빛수학"
    assert me["application"]["ownerName"] == "가원장"
    r = await boss.call("POST", "/teacher/academy-applications", json=FORM)
    assert r.status_code == 409 and r.json()["detail"] == "이미 심사 중인 신청이 있어요."
    assert (await boss.call("GET", "/owner/dashboard")).status_code == 403
    # 운영자: 심사 중 먼저, 반려는 사유 필요
    op = await _demo(client, t, "op")
    apps = await op.ok("GET", "/operator/applications")
    assert [a["status"] for a in apps] == ["심사 중", "심사 중", "승인"]
    mine = next(a for a in apps if a["academyName"] == "별빛수학")
    path = f"/operator/applications/{mine['id']}/review"
    r = await op.call("POST", path, json={"decision": "반려", "reason": " "})
    assert r.status_code == 422 and r.json()["detail"] == "반려 사유를 적어 주세요."
    apps = await op.ok("POST", path, json={"decision": "승인"})
    mine = next(a for a in apps if a["academyName"] == "별빛수학")
    assert mine["status"] == "승인" and mine["serial"]
    r = await op.call("POST", path, json={"decision": "승인"})
    assert r.status_code == 409 and r.json()["detail"] == "이미 처리한 신청이에요."
    assert any(x.startswith("별빛수학 등록이 승인됐어요. 일련번호") for x in await boss.notices())
    me = await boss.refresh()
    assert me["membership"]["isOwner"] is True and me["membership"]["status"] == "승인됨"
    assert me["academy"]["name"] == "별빛수학"
    r = await boss.call("DELETE", "/teacher/membership")
    assert (
        r.status_code == 409 and r.json()["detail"] == "원장은 소속을 나갈 수 없어요(운영자 문의)."
    )
    # 원장 대시보드 + 입장 코드
    dash = await boss.ok("GET", "/owner/dashboard")
    assert dash["academy"]["serial"] == mine["serial"] and dash["entryCode"] is None
    assert dash["teachers"] == [{"id": boss.id, "name": "가원장", "sub": "원장 · 강의실 0개"}]
    dash = await boss.ok("POST", "/owner/entry-code")
    code = dash["entryCode"]["code"]
    assert len(code) == 6 and code.isdigit()
    expires = datetime.fromtimestamp(dash["entryCode"]["expiresAt"] / 1000, UTC)
    assert expires == clock.now + timedelta(minutes=10)
    # 학생·보호자 입장
    s, g = await _linked_pair(client, "kid_one", "mom_one", t)
    await s.ok("POST", "/academy/join", json={"code": code})
    # 강사 소속 신청(일련번호는 소문자·하이픈 없이도) → 원장 승인
    tea = await _signup(client, "teacher", "teach_one", t, name="나선생")
    r = await tea.call("POST", "/teacher/membership", json={"serial": "ZZZZ-ZZZZ"})
    assert r.status_code == 404
    assert r.json()["detail"] == "일련번호를 찾지 못했어요. 원장님께 다시 확인해 주세요."
    r = await tea.call("POST", "/teacher/classes", json={"name": "반"})
    assert r.status_code == 403
    me = await tea.ok(
        "POST", "/teacher/membership", json={"serial": mine["serial"].replace("-", "").lower()}
    )
    assert me["membership"]["status"] == "승인 대기" and me["academy"] is None
    assert "나선생님이 소속을 신청했어요" in await boss.notices()
    dash = await boss.ok("GET", "/owner/dashboard")
    assert dash["pendingTeachers"] == [{"id": tea.id, "name": "나선생", "sub": "소속 신청"}]
    assert dash["students"] == [{"id": s.id, "name": "kid_one", "sub": "초5 · 강의실 없음"}]
    dash = await boss.ok("POST", "/owner/teachers/approve", json={"ids": [tea.id, "nobody"]})
    assert dash["pendingTeachers"] == [] and len(dash["teachers"]) == 2
    assert "별빛수학 소속이 승인됐어요. 이제 강의실을 열 수 있어요." in await tea.notices()
    # 강의실 → 초대 → 수락
    r = await tea.call("POST", "/teacher/classes", json={"name": " ", "plan": ""})
    assert r.json()["detail"] == "강의실 이름을 적어 주세요."
    cls = await tea.ok(
        "POST", "/teacher/classes", json={"name": "5학년 별반", "plan": "분수 나눗셈"}
    )
    room = cls["classrooms"][0]
    assert room["name"] == "5학년 별반" and room["teacherName"] == "나선생"
    assert cls["academyStudents"] == [{"id": s.id, "name": "kid_one", "sub": "초5"}]
    # 오늘 화면 이름은 첫 강의실(아직 member 없음)
    today = await tea.ok("GET", "/teacher/today")
    assert today["className"] == "5학년 별반" and today["students"] == []
    cls = await tea.ok("POST", f"/teacher/classes/{room['id']}/invites", json={"studentId": s.id})
    assert [p["id"] for p in cls["classrooms"][0]["invited"]] == [s.id]
    assert "나선생이 「5학년 별반」에 초대했어!" in await s.notices()
    mine_cls = await s.ok("GET", "/student/classes")
    assert [c["id"] for c in mine_cls["invites"]] == [room["id"]]
    mine_cls = await s.ok("POST", f"/student/classes/{room['id']}/invite", json={"accept": True})
    assert [c["id"] for c in mine_cls["joined"]] == [room["id"]] and mine_cls["invites"] == []
    r = await s.call("POST", f"/student/classes/{room['id']}/invite", json={"accept": True})
    assert r.status_code == 404 and r.json()["detail"] == "초대를 찾지 못했어요."
    r = await tea.call("POST", f"/teacher/classes/{room['id']}/invites", json={"studentId": s.id})
    assert r.status_code == 409 and r.json()["detail"] == "이미 들어와 있어요."
    # 요청 → 수락(두 번째 강의실). 만든 순서가 분명하게 시계를 1초 넘긴다
    clock.now += timedelta(seconds=1)
    cls = await tea.ok("POST", "/teacher/classes", json={"name": "5학년 달반"})
    room2 = next(c for c in cls["classrooms"] if c["name"] == "5학년 달반")
    mine_cls = await s.ok("POST", f"/student/classes/{room2['id']}/request")
    assert mine_cls["available"] == [
        {"id": room2["id"], "name": "5학년 달반", "teacherName": "나선생", "requested": True}
    ]
    assert "kid_one 학생이 「5학년 달반」 참여를 요청했어요" in await tea.notices()
    path = f"/teacher/classes/{room2['id']}/requests/{s.id}"
    cls = await tea.ok("POST", path, json={"accept": True})
    room2 = next(c for c in cls["classrooms"] if c["name"] == "5학년 달반")
    assert [p["id"] for p in room2["members"]] == [s.id] and room2["requests"] == []
    r = await tea.call("POST", path, json={"accept": True})
    assert r.status_code == 404 and r.json()["detail"] == "요청을 찾지 못했어요."
    # 소속을 나가려면 강의실을 먼저 정리
    r = await tea.call("DELETE", "/teacher/membership")
    assert r.json()["detail"] == "내 강의실이 남아 있어요. 강의실을 정리한 뒤 나갈 수 있어요."
    # 원장 대시보드: 강의실·학생
    dash = await boss.ok("GET", "/owner/dashboard")
    assert {c["name"]: c["count"] for c in dash["classrooms"]} == {"5학년 별반": 1, "5학년 달반": 1}
    assert dash["students"][0]["sub"] == "초5 · 5학년 별반, 5학년 달반"
    # 오늘 수업: 쿠키 신원으로 학생이 보이고 메모 → 초안 → 승인 → 보호자 카드
    cookie = {"Cookie": f"cm_session={tea.token}"}
    today = (await client.get(f"{BASE}/teacher/today", headers=cookie)).json()
    assert today["className"] == "5학년 별반"
    assert [x["id"] for x in today["students"]] == [s.id]
    memo = {"covered": "분수 나눗셈", "stuck": "역수", "homework": "2쪽", "note": "잘했어요"}
    r = await client.put(f"{BASE}/teacher/students/{s.id}/memo", json=memo, headers=cookie)
    assert r.status_code == 204, r.text
    d = (await client.post(f"{BASE}/teacher/students/{s.id}/draft", headers=cookie)).json()
    assert d["status"] == "승인 대기" and d["comment"]
    r = await client.post(f"{BASE}/teacher/students/{s.id}/draft/approve", headers=cookie)
    assert r.status_code == 200 and r.json()["status"] == "승인됨"
    gt = await g.ok("GET", "/guardian/today")
    assert gt is not None
    # 다른 강사(강의실 없음)는 이 학생을 못 본다
    t3 = await _demo(client, t, "t3")
    today = await t3.ok("GET", "/teacher/today")
    assert today["className"] == "내 강의실" and today["students"] == []
    r = await t3.call("GET", f"/teacher/students/{s.id}/memo")
    assert r.status_code == 404


async def test_leave_and_reject(client):
    t = await _trial(client)
    t2 = await _demo(client, t, "t2")  # 소속 승인 대기
    me = await t2.ok("DELETE", "/teacher/membership")
    assert me["membership"] is None
    op = await _demo(client, t, "op")
    apps = await op.ok("GET", "/operator/applications")
    app2 = next(a for a in apps if a["status"] == "심사 중")
    apps = await op.ok(
        "POST",
        f"/operator/applications/{app2['id']}/review",
        json={"decision": "반려", "reason": " 서류 부족 "},
    )
    assert next(a for a in apps if a["id"] == app2["id"])["rejectReason"] == "서류 부족"
    own2 = await _demo(client, t, "own2")
    assert "새싹영어학원 등록이 반려됐어요: 서류 부족" in await own2.notices()
    # 반려 뒤에는 다시 신청할 수 있다
    me = await own2.ok("POST", "/teacher/academy-applications", json=FORM)
    assert me["application"]["status"] == "심사 중"


# --- 학습 규칙(토큰 경로) -----------------------------------------------------------------


async def test_restricted_student_cannot_chat(client):
    s = await _signup(client, "student", "kid_one")
    await s.ok("POST", "/student/promise")
    sid = (await s.ok("POST", "/sessions", json={"difficulty": "중급"}))["id"]
    r = await s.call("POST", f"/sessions/{sid}/after-study", json={"choice": "chat"})
    assert r.status_code == 409 and r.json()["code"] == "restricted"
    assert r.json()["detail"] == "보호자와 연결한 뒤에 수다를 할 수 있어요."
    # 학원 강의실 요청도 막힘
    r = await s.call("POST", "/student/classes/whatever/request")
    assert r.status_code == 403 and r.json()["detail"] == "보호자와 먼저 연결해 주세요."
    # 연결 뒤에는 막지 않는다(학습 상태 규칙은 기존대로)
    g = await _signup(client, "guardian", "mom_one")
    await g.ok("POST", "/links", json={"code": s.me["linkCode"], "consent": True})
    r = await s.call("POST", f"/sessions/{sid}/after-study", json={"choice": "chat"})
    assert r.json().get("code") != "restricted"


async def test_trial_header_chat_unchanged(client):
    """체험 헤더 경로(계정 없음)는 restricted 검사를 하지 않는다."""
    t = await _trial(client)
    h = {"X-Demo-Role": "child", "X-Demo-Actor": f"{t}-child"}
    await client.post(f"{BASE}/student/promise", headers=h)
    sid = (await client.post(f"{BASE}/sessions", json={"difficulty": "중급"}, headers=h)).json()[
        "id"
    ]
    r = await client.post(f"{BASE}/sessions/{sid}/after-study", json={"choice": "chat"}, headers=h)
    assert r.json().get("code") != "restricted"


async def test_demo_teacher_today_class_name(client):
    t = await _trial(client)
    t1 = await _demo(client, t, "t1")
    assert (await t1.ok("GET", "/teacher/today"))["className"] == "5학년 A반"
    # 체험 헤더 학습지도자는 예전 고정 이름 그대로
    h = {"X-Demo-Role": "instructor", "X-Demo-Actor": f"{t}-instructor"}
    r = await client.get(f"{BASE}/teacher/today", headers=h)
    assert r.json()["className"] == "데모 반"


async def test_demo_world_classes_shapes(client):
    t = await _trial(client)
    t1 = await _demo(client, t, "t1")
    cls = await t1.ok("GET", "/teacher/classes")
    assert [c["name"] for c in cls["classrooms"]] == ["5학년 A반", "5학년 심화반"]
    assert [p["id"] for p in cls["classrooms"][1]["requests"]] == [f"{t}-s4"]
    subs = {p["id"]: p["sub"] for p in cls["academyStudents"]}
    assert subs[f"{t}-child"] == "내 강의실" and subs[f"{t}-s4"] == "초5"
    s1 = await _demo(client, t, "s1")
    mine = await s1.ok("GET", "/student/classes")
    assert [c["name"] for c in mine["joined"]] == ["5학년 A반"]
    assert mine["available"][0]["name"] == "5학년 심화반"
    own1 = await _demo(client, t, "own1")
    dash = await own1.ok("GET", "/owner/dashboard")
    assert [p["name"] for p in dash["pendingTeachers"]] == ["이선생님"]
    # 원장 아닌 강사·학생은 대시보드 못 봄
    r = await t1.call("GET", "/owner/dashboard")
    assert r.status_code == 403 and r.json()["detail"] == "학원·학교 관리자(원장)만 쓸 수 있어요."
    assert (await s1.call("GET", "/owner/dashboard")).status_code == 403
    assert (await s1.call("GET", "/operator/applications")).status_code == 403


# --- 체험 세상 격리 ----------------------------------------------------------------------


async def test_cross_world_isolation(client):
    a, b = await _trial(client), await _trial(client)
    a_t1, b_t1 = await _demo(client, a, "t1"), await _demo(client, b, "t1")
    a_g1, b_s1 = await _demo(client, a, "g1"), await _demo(client, b, "s1")
    a_op, b_op = await _demo(client, a, "op"), await _demo(client, b, "op")
    a_own1 = await _demo(client, a, "own1")
    # 강의실: 다른 세상 학생 초대 403, 다른 세상 강의실 요청 처리 404
    r = await a_t1.call("POST", f"/teacher/classes/{a}-c1/invites", json={"studentId": f"{b}-s4"})
    assert r.status_code == 403
    r = await a_t1.call("POST", f"/teacher/classes/{b}-c2/requests/{b}-s4", json={"accept": True})
    assert r.status_code == 404
    r = await a_t1.call("POST", f"/teacher/classes/{b}-c1/invites", json={"studentId": f"{b}-s4"})
    assert r.status_code == 404
    # 학생: 다른 세상 강의실 요청·초대 수락 404
    assert (await b_s1.call("POST", f"/student/classes/{a}-c2/request")).status_code == 404
    r = await b_s1.call("POST", f"/student/classes/{a}-c1/invite", json={"accept": True})
    assert r.status_code == 404
    # 보호자: 다른 세상 학생 id로 확인 404
    r = await a_g1.call("POST", f"/links/{b}-child/confirm", json={"consent": True})
    assert r.status_code == 404
    # 운영자: 자기 세상 신청서만 보고 다른 세상 것은 심사 못 함
    a_apps = await a_op.ok("GET", "/operator/applications")
    assert {x["id"] for x in a_apps} == {f"{a}-app1", f"{a}-app2"}
    r = await a_op.call(
        "POST", f"/operator/applications/{b}-app2/review", json={"decision": "승인"}
    )
    assert r.status_code == 404 and r.json()["detail"] == "신청서를 찾지 못했어요."
    assert all(
        x["status"] == "심사 중"
        for x in await b_op.ok("GET", "/operator/applications")
        if x["id"] == f"{b}-app2"
    )
    # 원장: 다른 세상 강사 승인은 조용히 건너뜀
    await a_own1.ok("POST", "/owner/teachers/approve", json={"ids": [f"{b}-t2"]})
    b_t2 = await _demo(client, b, "t2")
    assert (await b_t2.refresh())["membership"]["status"] == "승인 대기"
    # 학습: 다른 세상 학생 메모 404
    r = await a_t1.call("GET", f"/teacher/students/{b}-s2/memo")
    assert r.status_code == 404
    del b_t1


# --- 영역(realm) 격리: 실제 가입 ⇄ 체험 세상(보안 검토 11-12) -------------------------------


async def test_realm_isolation_codes(client, db_session):
    from app.models_org import Account

    t = await _trial(client)
    own1, g1, s1 = (
        await _demo(client, t, "own1"),
        await _demo(client, t, "g1"),
        await _demo(client, t, "s1"),
    )
    t3 = await _demo(client, t, "t3")
    # 브라우저가 체험 세트(X-Trial-Id)를 들고 있어도 가입은 실제 계정(trial_id 없음)
    kid, mom = await _linked_pair(client, "kid_real", "mom_real", t)
    teach = await _signup(client, "teacher", "teach_real", t)
    for who in (kid, mom, teach):
        acc = await db_session.get(Account, who.id)
        assert acc is not None and acc.trial_id is None
    solo = await _signup(client, "student", "kid_solo", t)
    # 연결 코드: 실제 → 체험 404, 체험 → 실제 404
    r = await solo.call("POST", "/links", json={"code": g1.me["linkCode"]})
    assert r.status_code == 404
    r = await g1.call("POST", "/links", json={"code": solo.me["linkCode"], "consent": True})
    assert r.status_code == 404
    # 학원 입장 코드: 실제 학생 → 체험 학원은 「그 브라우저의 체험 세트(X-Trial-Id)」가 아니면 404
    # (같은 세트면 들어간다 — test_real_account_joins_own_trial_academy, 성호 11-12)
    demo_code = await _entry_code(own1)
    kid.trial = None
    r = await kid.call("POST", "/academy/join", json={"code": demo_code})
    assert r.status_code == 404
    other = await _trial(client)
    mom.trial = other
    r = await mom.call("POST", "/academy/join", json={"code": demo_code})
    assert r.status_code == 404
    kid.trial = mom.trial = t
    # 일련번호: 실제 강사 → 체험 학원 404
    demo_serial = (await own1.ok("GET", "/owner/dashboard"))["academy"]["serial"]
    r = await teach.call("POST", "/teacher/membership", json={"serial": demo_serial})
    assert r.status_code == 404
    # 실제 학원을 하나 세운다(신청 → 그 화면 세트 운영자 승인)
    await teach.ok("POST", "/teacher/academy-applications", json=FORM)
    op = await _demo(client, t, "op")
    apps = await op.ok("GET", "/operator/applications")
    mine = next(a for a in apps if a["academyName"] == "별빛수학")
    await op.ok("POST", f"/operator/applications/{mine['id']}/review", json={"decision": "승인"})
    real_serial = (await teach.ok("GET", "/owner/dashboard"))["academy"]["serial"]
    real_code = await _entry_code(teach)
    # 체험 계정 → 실제 학원 코드·일련번호 404
    s1_acc = await db_session.get(Account, s1.id)
    assert s1_acc is not None
    s1_acc.academy_id = None
    await db_session.flush()
    r = await s1.call("POST", "/academy/join", json={"code": real_code})
    assert r.status_code == 404
    r = await t3.call("POST", "/teacher/membership", json={"serial": real_serial})
    assert r.status_code == 404
    # 같은 영역끼리는 된다
    await kid.ok("POST", "/academy/join", json={"code": real_code})
    await t3.ok("POST", "/teacher/membership", json={"serial": demo_serial})


async def test_real_account_joins_own_trial_academy(client, db_session):
    """성호 11-12: 심사위원이 새로 가입한 아이도 그 브라우저 체험 학원 코드로 들어가 공부까지 간다.
    계정은 실제 영역(trial_id None) 그대로, 학원만 체험 학원. 체험 강사가 강의실에 받으면 「할 일」에 보인다."""
    from app.models_org import Account

    t = await _trial(client)
    own1 = await _demo(client, t, "own1")
    kid, mom = await _linked_pair(client, "kid_trialjoin", "mom_trialjoin", t)
    code = await _entry_code(own1)
    me = await kid.ok("POST", "/academy/join", json={"code": code})
    assert me["academy"] is not None
    acc = await db_session.get(Account, kid.id)
    assert acc is not None and acc.trial_id is None  # 계정 영역은 바뀌지 않는다
    assert (await mom.refresh())["academy"] == me["academy"]  # 연결된 보호자도 같이(기존 규칙)
    # 체험 강사 강의실에 참여 요청 → 강사 수락 → 강사 「할 일」에 보인다
    t1 = await _demo(client, t, "t1")
    rooms = await kid.ok("GET", "/student/classes")
    room_id = next(r for r in rooms["available"] if r["teacherName"] == t1.me["name"])["id"]
    await kid.ok("POST", f"/student/classes/{room_id}/request")
    await t1.ok("POST", f"/teacher/classes/{room_id}/requests/{kid.id}", json={"accept": True})
    today = await t1.ok("GET", "/teacher/today")
    assert kid.id in [s["id"] for s in today["students"]]


async def test_real_teacher_reviewed_in_demo_world_gets_real_academy(client, db_session):
    from app.models_org import Academy, AcademyApplication, Account

    t = await _trial(client)
    boss = await _signup(client, "teacher", "boss_real", t, name="가원장")
    me = await boss.ok("POST", "/teacher/academy-applications", json=FORM)
    app_row = await db_session.get(AcademyApplication, me["application"]["id"])
    assert app_row is not None and app_row.trial_id == t  # 심사는 이 화면 세트 운영자가
    op = await _demo(client, t, "op")
    await op.ok("POST", f"/operator/applications/{app_row.id}/review", json={"decision": "승인"})
    me = await boss.refresh()
    ac = await db_session.get(Academy, me["academy"]["id"])
    assert ac is not None and ac.trial_id is None  # 학원은 원장 계정 영역(실제)
    owner = await db_session.get(Account, boss.id)
    assert owner is not None and owner.trial_id is None
    code = await _entry_code(boss)
    kid, _ = await _linked_pair(client, "kid_join", "mom_join", t)
    me = await kid.ok("POST", "/academy/join", json={"code": code})
    assert me["academy"]["name"] == "별빛수학"


async def test_real_teacher_application_follows_new_trial(client, db_session):
    """A7: 가입 강사의 심사 중 신청은 세트가 바뀌면 새 세트로 옮긴다(영영 심사 중이 되지 않게)."""
    from app.models_org import AcademyApplication

    t_old, t_new = await _trial(client), await _trial(client)
    boss = await _signup(client, "teacher", "boss_move", t_old, name="나원장")
    me = await boss.ok("POST", "/teacher/academy-applications", json=FORM)
    app_id = me["application"]["id"]
    # 같은 세트에서 다시 내면 그대로 409
    r = await boss.call("POST", "/teacher/academy-applications", json=FORM)
    assert r.status_code == 409
    boss.trial = t_new
    me = await boss.ok("POST", "/teacher/academy-applications", json=FORM)
    assert me["application"]["id"] == app_id and me["application"]["status"] == "심사 중"
    row = await db_session.get(AcademyApplication, app_id)
    assert row is not None and row.trial_id == t_new
    # 새 세트 운영자가 심사할 수 있다
    op = await _demo(client, t_new, "op")
    await op.ok("POST", f"/operator/applications/{app_id}/review", json={"decision": "승인"})
    me = await boss.refresh()
    assert me["academy"]["name"] == "별빛수학"
