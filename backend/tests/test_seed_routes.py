"""명세 4.12 씨앗·상점·도장·꾸미기 + 남은 학습 함수(records·results·units), 설계 §10 P4·P5.

체험 세상(org.ts seed()와 같은 값)을 데모 로그인으로 쓴다. 이름·아이디는 모두 합성 값.
NOW = 서울 11-10(화) 06:00 → 이번 주 = 11-09(월)~. 지우(s1) 기록 합 18, 이번 주 +5.
"""

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from app import config, seed_routes
from app.api import get_llm
from app.db import get_db
from app.instructor import get_draft_adapter
from app.llm import ScriptedAdapter
from app.main import create_app
from app.models_org import Notice, Order, SeedLedger, ShopItem
from app.seed import load_seed
from app.seeds import STAMP, STUDY_DONE, add_seed, earn_study_seeds
from app.timeutil import get_now, seoul_date

NOW = datetime(2026, 11, 9, 21, 0, tzinfo=UTC)  # 서울 11-10 06:00
BASE = "/api/v1/compat"
PW = "abcd1234"


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def tick(self, seconds: int = 1) -> None:
        self.now += timedelta(seconds=seconds)


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


def _b(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _token_of(client, r) -> str:
    assert r.status_code == 200, r.text
    token = r.cookies.get("cm_session")
    assert token
    client.cookies.clear()
    return token


async def _trial(client) -> str:
    r = await client.post(f"{BASE}/trial")
    assert r.status_code == 200
    return r.json()["trialId"]


async def _login(client, trial_id: str, key: str) -> str:
    r = await client.post(
        f"{BASE}/demo/login", json={"userId": key}, headers={"X-Trial-Id": trial_id}
    )
    return await _token_of(client, r)


async def _signup(client, role: str, login: str) -> str:
    body = {
        "role": role,
        "loginId": login,
        "password": PW,
        "name": "새싹",
        "agreements": {"terms": True, "privacy": True, "marketing": False},
    }
    if role == "student":
        body["grade"] = 5
    else:
        body["email"] = f"{login}@example.com"
    return await _token_of(client, await client.post(f"{BASE}/auth/signup", json=body))


async def _give(db_session, student_id: str, amount: int) -> None:
    """테스트용 씨앗 더하기(잔액을 맞춘다)."""
    db_session.add(
        SeedLedger(
            student_account_id=student_id,
            date=seoul_date(NOW),
            amount=amount,
            source="학습 완료",
            note="테스트",
            by="system",
            created_at=NOW - timedelta(days=10),
        )
    )
    await db_session.flush()


async def _notices(db_session, account_id: str) -> list[str]:
    rows = await db_session.scalars(select(Notice.text).where(Notice.account_id == account_id))
    return list(rows)


# --- 학생: 지갑·상점 --------------------------------------------------------------------


async def test_wallet_balance_from_ledger(client):
    t = await _trial(client)
    kid = await _login(client, t, "s1")
    w = (await client.get(f"{BASE}/student/wallet", headers=_b(kid))).json()
    assert w["balance"] == 18
    assert len(w["history"]) == 6
    first = w["history"][0]
    assert set(first) == {"id", "at", "amount", "source", "note"}
    assert first["at"] == "11월 9일 · 18:10"  # 가장 최근이 먼저
    assert {h["source"] for h in w["history"]} == {"학습 완료", "보호자 도장", "학습지도자 칭찬"}


async def test_wallet_needs_student(client):
    t = await _trial(client)
    mom = await _login(client, t, "g1")
    r = await client.get(f"{BASE}/student/wallet", headers=_b(mom))
    assert r.status_code == 403
    r = await client.get(f"{BASE}/student/wallet")
    assert r.status_code == 401 and r.json()["code"] == "not_logged_in"


async def test_student_shop_shape(client):
    t = await _trial(client)
    kid = await _login(client, t, "s1")
    shop = (await client.get(f"{BASE}/student/shop", headers=_b(kid))).json()
    assert shop["balance"] == 18
    names = [i["name"] for i in shop["academyItems"]]
    assert names == ["칭찬 간식 쿠폰", "자리 고르기권", "보드게임 10분"]  # 숨긴 상품 제외
    assert set(shop["academyItems"][0]) == {"id", "name", "price", "stock", "visible", "note"}
    glasses = next(c for c in shop["cosmetics"] if c["id"] == "glasses")
    assert glasses == {
        "id": "glasses",
        "kind": "outfit",
        "name": "공부 안경",
        "price": 10,
        "owned": True,
        "equipped": False,
    }
    assert len(shop["cosmetics"]) == 8
    assert shop["orders"] == []


async def test_buy_item_stock_price_notice_order(client, db_session):
    t = await _trial(client)
    kid = await _login(client, t, "s1")
    # 18씨앗: 20짜리는 모자라다
    r = await client.post(f"{BASE}/student/shop/items/{t}-i1/buy", headers=_b(kid))
    assert r.status_code == 409 and r.json()["detail"] == "씨앗이 모자라요."
    # 숨긴 상품·없는 상품은 못 찾는다
    r = await client.post(f"{BASE}/student/shop/items/{t}-i4/buy", headers=_b(kid))
    assert r.status_code == 404 and r.json()["detail"] == "상품을 찾지 못했어요."
    # 수량 있는 상품을 사면 수량 -1, 씨앗 -가격, 교환 요청, 선생님 알림
    await _give(db_session, f"{t}-child", 30)
    shop = (await client.post(f"{BASE}/student/shop/items/{t}-i3/buy", headers=_b(kid))).json()
    assert shop["balance"] == 18 + 30 - 25
    item = next(i for i in shop["academyItems"] if i["id"] == f"{t}-i3")
    assert item["stock"] == 4
    assert shop["orders"][0]["itemName"] == "보드게임 10분"
    assert shop["orders"][0]["status"] == "교환 요청"
    assert shop["orders"][0]["studentName"] == "지우"
    assert shop["orders"][0]["price"] == 25
    assert "지우 학생이 「보드게임 10분」 교환을 요청했어요" in await _notices(
        db_session, f"{t}-instructor"
    )
    w = (await client.get(f"{BASE}/student/wallet", headers=_b(kid))).json()
    assert w["history"][0]["amount"] == -25 and w["history"][0]["source"] == "상점 구매"
    # 다 팔린 상품
    sold_out = await db_session.get(ShopItem, f"{t}-i2")
    sold_out.stock = 0
    await db_session.flush()
    r = await client.post(f"{BASE}/student/shop/items/{t}-i2/buy", headers=_b(kid))
    assert r.status_code == 409 and r.json()["detail"] == "다 팔렸어요."


async def test_student_outside_class_sees_no_items(client):
    await _trial(client)
    kid = await _signup(client, "student", "kid_new")
    shop = (await client.get(f"{BASE}/student/shop", headers=_b(kid))).json()
    assert shop["balance"] == 0 and shop["academyItems"] == []


async def test_cosmetic_buy_and_equip(client):
    t = await _trial(client)
    kid = await _login(client, t, "s1")
    r = await client.post(f"{BASE}/student/shop/cosmetics/glasses/buy", headers=_b(kid))
    assert r.status_code == 409 and r.json()["detail"] == "이미 가지고 있어요."
    r = await client.post(f"{BASE}/student/shop/cosmetics/nope/buy", headers=_b(kid))
    assert r.status_code == 404
    shop = (
        await client.post(f"{BASE}/student/shop/cosmetics/raincoat/buy", headers=_b(kid))
    ).json()
    assert shop["balance"] == 3
    rain = next(c for c in shop["cosmetics"] if c["id"] == "raincoat")
    assert rain["owned"] and rain["equipped"]  # 옷은 사면 바로 입는다
    me = (await client.get(f"{BASE}/me", headers=_b(kid))).json()
    assert me["outfit"] == "raincoat"
    r = await client.post(f"{BASE}/student/shop/cosmetics/cape/buy", headers=_b(kid))
    assert r.status_code == 409 and r.json()["detail"] == "씨앗이 모자라요."
    # 입기
    r = await client.put(f"{BASE}/student/outfit", json={"id": "cape"}, headers=_b(kid))
    assert r.status_code == 409 and r.json()["detail"] == "아직 없는 옷이에요."
    shop = (
        await client.put(f"{BASE}/student/outfit", json={"id": "glasses"}, headers=_b(kid))
    ).json()
    assert next(c for c in shop["cosmetics"] if c["id"] == "glasses")["equipped"] is True
    shop = (await client.put(f"{BASE}/student/outfit", json={"id": None}, headers=_b(kid))).json()
    assert not any(c["equipped"] for c in shop["cosmetics"])
    assert (await client.get(f"{BASE}/me", headers=_b(kid))).json()["outfit"] is None


async def test_emote_buy_does_not_change_outfit(client):
    t = await _trial(client)
    kid = await _login(client, t, "s1")
    shop = (await client.post(f"{BASE}/student/shop/cosmetics/thumbs/buy", headers=_b(kid))).json()
    assert shop["balance"] == 10
    assert (await client.get(f"{BASE}/me", headers=_b(kid))).json()["outfit"] is None


# --- 보호자 도장 -------------------------------------------------------------------------


async def test_stamp_once_a_day(client, db_session, clock):
    t = await _trial(client)
    mom = await _login(client, t, "g1")
    s = (await client.get(f"{BASE}/guardian/stamp", headers=_b(mom))).json()
    assert s == {"stampedToday": False, "balance": 18}
    s = (await client.post(f"{BASE}/guardian/stamp", headers=_b(mom))).json()
    assert s == {"stampedToday": True, "balance": 20}
    r = await client.post(f"{BASE}/guardian/stamp", headers=_b(mom))
    assert r.status_code == 409
    assert r.json()["detail"] == "오늘 도장은 이미 찍었어요. 내일 또 찍어 주세요."
    assert "보호자가 도장을 찍어 줬어! 씨앗 +2" in await _notices(db_session, f"{t}-child")
    # 다음 날(서울)은 다시 찍을 수 있다
    clock.now += timedelta(days=1)
    s = (await client.get(f"{BASE}/guardian/stamp", headers=_b(mom))).json()
    assert s["stampedToday"] is False


async def test_stamp_needs_linked_child(client):
    await _trial(client)
    mom = await _signup(client, "guardian", "mom_new")
    s = (await client.get(f"{BASE}/guardian/stamp", headers=_b(mom))).json()
    assert s == {"stampedToday": False, "balance": 0}
    r = await client.post(f"{BASE}/guardian/stamp", headers=_b(mom))
    assert r.status_code == 404 and r.json()["detail"] == "먼저 아이와 연결해 주세요."


# --- 학습지도자 --------------------------------------------------------------------------


async def test_seed_board_shape(client):
    t = await _trial(client)
    teacher = await _login(client, t, "t1")
    board = (await client.get(f"{BASE}/teacher/seeds", headers=_b(teacher))).json()
    rows = {s["name"]: s for s in board["students"]}
    assert set(rows) == {"지우", "이민준", "박서연"}  # 강의실 member만(최하린은 요청 중)
    assert rows["지우"] == {
        "id": f"{t}-child",
        "name": "지우",
        "balance": 18,
        "earnedWeek": 5,
        "grantedToday": 0,
    }
    assert rows["이민준"]["balance"] == 4 and rows["이민준"]["earnedWeek"] == 24
    assert [i["name"] for i in board["items"]][-1] == "겨울방학 특별 선물"  # 숨긴 것도 보인다
    assert board["orders"][0] == {
        "id": f"{t}-o1",
        "studentName": "이민준",
        "itemName": "칭찬 간식 쿠폰",
        "price": 20,
        "at": "11월 10일 · 16:40",
        "status": "교환 요청",
    }


async def test_grant_caps_and_room_rule(client, db_session):
    t = await _trial(client)
    teacher = await _login(client, t, "t1")
    url = f"{BASE}/teacher/seeds/{t}-s2"
    r = await client.post(url, json={"amount": 6, "note": "발표"}, headers=_b(teacher))
    assert r.status_code == 422 and r.json()["detail"] == "한 번에 1~5개까지 줄 수 있어요."
    r = await client.post(url, json={"amount": 0, "note": "발표"}, headers=_b(teacher))
    assert r.status_code == 422
    r = await client.post(url, json={"amount": 2.5, "note": "발표"}, headers=_b(teacher))
    assert r.status_code == 422
    r = await client.post(url, json={"amount": 3, "note": "  "}, headers=_b(teacher))
    assert r.status_code == 422 and r.json()["detail"] == "칭찬 이유를 골라 주세요."
    board = (await client.post(url, json={"amount": 5, "note": "발표"}, headers=_b(teacher))).json()
    row = next(s for s in board["students"] if s["id"] == f"{t}-s2")
    assert row["grantedToday"] == 5 and row["balance"] == 9
    await client.post(url, json={"amount": 5, "note": "숙제"}, headers=_b(teacher))
    r = await client.post(url, json={"amount": 1, "note": "숙제"}, headers=_b(teacher))
    assert r.status_code == 409 and r.json()["detail"] == "한 학생에게 하루 10개까지 줄 수 있어요."
    assert "김선생님이 칭찬 씨앗 5개를 줬어! (발표)" in await _notices(db_session, f"{t}-s2")
    # 요청만 한 학생(최하린)·다른 선생님 강의실이 없는 학생은 안 된다
    r = await client.post(
        f"{BASE}/teacher/seeds/{t}-s4", json={"amount": 1, "note": "x"}, headers=_b(teacher)
    )
    assert r.status_code == 403 and r.json()["detail"] == "내 강의실 학생에게만 줄 수 있어요."
    other = await _login(client, t, "t3")
    r = await client.post(
        f"{BASE}/teacher/seeds/{t}-child", json={"amount": 1, "note": "x"}, headers=_b(other)
    )
    assert r.status_code == 403


async def test_save_shop_item_new_and_edit(client):
    t = await _trial(client)
    teacher = await _login(client, t, "t1")
    new = {"name": "  연필  ", "price": 5, "stock": None, "visible": True, "note": "선물"}
    board = (await client.post(f"{BASE}/teacher/shop/items", json=new, headers=_b(teacher))).json()
    pencil = next(i for i in board["items"] if i["name"] == "연필")
    assert pencil["stock"] is None and pencil["price"] == 5
    edit = {**pencil, "price": 7, "stock": 2, "visible": False}
    board = (
        await client.put(
            f"{BASE}/teacher/shop/items/{pencil['id']}", json=edit, headers=_b(teacher)
        )
    ).json()
    got = next(i for i in board["items"] if i["id"] == pencil["id"])
    assert got["price"] == 7 and got["stock"] == 2 and got["visible"] is False
    for bad, msg in [
        ({**new, "name": " "}, "상품 이름을 적어 주세요."),
        ({**new, "price": 0}, "가격은 1~200 씨앗으로 정해 주세요."),
        ({**new, "price": 201}, "가격은 1~200 씨앗으로 정해 주세요."),
        ({**new, "stock": -1}, "수량은 0 이상으로 적어 주세요."),
        ({**new, "stock": 10000}, "수량은 9999개까지 적을 수 있어요."),  # A6: 1e30이면 500이었다
        ({**new, "stock": 1e30}, "수량은 9999개까지 적을 수 있어요."),
    ]:
        r = await client.post(f"{BASE}/teacher/shop/items", json=bad, headers=_b(teacher))
        assert r.status_code == 422 and r.json()["detail"] == msg
    # 남의 상품은 못 고친다
    other = await _login(client, t, "t3")
    r = await client.put(f"{BASE}/teacher/shop/items/{t}-i1", json=edit, headers=_b(other))
    assert r.status_code == 404 and r.json()["detail"] == "상품을 찾지 못했어요."


async def test_deliver_order(client, db_session):
    t = await _trial(client)
    teacher = await _login(client, t, "t1")
    board = (await client.post(f"{BASE}/teacher/orders/{t}-o1/deliver", headers=_b(teacher))).json()
    assert board["orders"][0]["status"] == "전달 완료"
    assert "「칭찬 간식 쿠폰」을 받았어!" in await _notices(db_session, f"{t}-s2")
    r = await client.post(f"{BASE}/teacher/orders/nope/deliver", headers=_b(teacher))
    assert r.status_code == 404 and r.json()["detail"] == "교환 요청을 찾지 못했어요."
    other = await _login(client, t, "t3")
    r = await client.post(f"{BASE}/teacher/orders/{t}-o1/deliver", headers=_b(other))
    assert r.status_code == 404


async def test_teacher_routes_need_teacher(client):
    t = await _trial(client)
    kid = await _login(client, t, "s1")
    assert (await client.get(f"{BASE}/teacher/seeds", headers=_b(kid))).status_code == 403


# --- 학습 완료 씨앗 ----------------------------------------------------------------------


async def _finish_study(client, clock, headers) -> str:
    """힌트 2번 + 풀이 보기 → 같이 풀기 끝 → 끝내기(skip)."""
    s = (await client.post(f"{BASE}/sessions", json={"difficulty": "중급"}, headers=headers)).json()
    sid = s["id"]
    p = (await client.get(f"{BASE}/sessions/{sid}/problem", headers=headers)).json()
    for _ in range(2):
        clock.tick()
        r = await client.post(
            f"{BASE}/sessions/{sid}/hint", json={"problemId": p["id"]}, headers=headers
        )
        assert r.status_code == 200, r.text
    clock.tick()
    r = await client.post(
        f"{BASE}/sessions/{sid}/solution", json={"problemId": p["id"]}, headers=headers
    )
    assert r.status_code == 200, r.text
    clock.tick()
    r = await client.post(
        f"{BASE}/sessions/{sid}/after-study", json={"choice": "skip"}, headers=headers
    )
    assert r.status_code == 200, r.text
    return sid


async def test_study_done_seed_trial_header_path(client, clock):
    t = await _trial(client)
    kid = {"X-Demo-Role": "child", "X-Demo-Actor": f"{t}-child"}
    await client.post(f"{BASE}/student/promise", headers=kid)
    home = (await client.get(f"{BASE}/student/home", headers=kid)).json()
    assert home["seeds"] == 0 and home["earnedToday"] == 0
    await _finish_study(client, clock, kid)
    home = (await client.get(f"{BASE}/student/home", headers=kid)).json()
    assert home["earnedToday"] == 3 and home["seeds"] == 3


async def test_study_done_seed_token_path(client, clock):
    t = await _trial(client)
    kid = _b(await _login(client, t, "s1"))
    await client.post(f"{BASE}/student/promise", headers=kid)
    await _finish_study(client, clock, kid)
    home = (await client.get(f"{BASE}/student/home", headers=kid)).json()
    assert home["earnedToday"] == 3 and home["seeds"] == 21
    w = (await client.get(f"{BASE}/student/wallet", headers=kid)).json()
    assert w["history"][0]["source"] == "학습 완료"
    assert w["history"][0]["note"] == "분수 ÷ 자연수"


async def test_study_done_seed_once_per_day(db_session):
    assert await earn_study_seeds(db_session, "t-aaaaaaaaaaaaaaaa-child", "단원", NOW) == 3
    assert await earn_study_seeds(db_session, "t-aaaaaaaaaaaaaaaa-child", "단원", NOW) == 0
    rows = list(await db_session.scalars(select(SeedLedger)))
    assert len(rows) == 1 and rows[0].trial_id == "t-aaaaaaaaaaaaaaaa"
    assert (
        await earn_study_seeds(
            db_session, "t-aaaaaaaaaaaaaaaa-child", "단원", NOW + timedelta(days=1)
        )
        == 3
    )


# --- 홈 칸 ------------------------------------------------------------------------------


async def test_home_fields_from_tables(client):
    t = await _trial(client)
    kid = await _login(client, t, "s1")
    home = (await client.get(f"{BASE}/student/home", headers=_b(kid))).json()
    assert home["seeds"] == 18 and home["earnedToday"] == 0 and home["inClass"] is True
    new = await _signup(client, "student", "kid_new")
    home = (await client.get(f"{BASE}/student/home", headers=_b(new))).json()
    assert home["seeds"] == 0 and home["inClass"] is False


async def test_home_header_path_keeps_in_class(client):
    t = await _trial(client)
    kid = {"X-Demo-Role": "child", "X-Demo-Actor": f"{t}-child"}
    home = (await client.get(f"{BASE}/student/home", headers=kid)).json()
    assert home["inClass"] is True  # 체험 헤더 경로는 전과 같게


# --- records·results·units --------------------------------------------------------------


async def test_records_shape(client, clock):
    t = await _trial(client)
    kid = _b(await _login(client, t, "s1"))
    assert (await client.get(f"{BASE}/student/records", headers=kid)).json() == []
    await client.post(f"{BASE}/student/promise", headers=kid)
    await _finish_study(client, clock, kid)
    recs = (await client.get(f"{BASE}/student/records", headers=kid)).json()
    assert recs == [
        {
            "date": "11월 10일 (화)",
            "unit": "분수 ÷ 자연수",
            "solved": 1,
            "total": 1,
            "difficulty": "중급",
            "hints": 2,
            "chatted": False,
        }
    ]


async def test_results_shape_and_scope(client, clock):
    t = await _trial(client)
    teacher = await _login(client, t, "t1")
    res = (await client.get(f"{BASE}/teacher/results", headers=_b(teacher))).json()
    assert {r["id"] for r in res} == {f"{t}-child", f"{t}-s2", f"{t}-s3"}
    jiwoo = next(r for r in res if r["id"] == f"{t}-child")
    assert set(jiwoo) == {
        "id",
        "name",
        "done",
        "unit",
        "solved",
        "total",
        "difficulty",
        "streak",
        "hints",
        "mistake",
        "hardPoint",
        "beginnerRepeat",
    }
    assert jiwoo["done"] is False and jiwoo["difficulty"] is None
    assert jiwoo["mistake"] is None and jiwoo["hardPoint"] is None
    # 지우가 끝내면 done
    kid = _b(await _login(client, t, "s1"))
    await client.post(f"{BASE}/student/promise", headers=kid)
    await _finish_study(client, clock, kid)
    res = (await client.get(f"{BASE}/teacher/results", headers=_b(teacher))).json()
    jiwoo = next(r for r in res if r["id"] == f"{t}-child")
    assert jiwoo["done"] is True and jiwoo["solved"] == 1 and jiwoo["unit"] == "분수 ÷ 자연수"
    assert jiwoo["hints"] == 2 and jiwoo["streak"] == 4
    # 강의실 없는 선생님은 빈 목록
    other = await _login(client, t, "t3")
    assert (await client.get(f"{BASE}/teacher/results", headers=_b(other))).json() == []


async def test_units_get_save(client):
    t = await _trial(client)
    teacher = await _login(client, t, "t1")
    units = (await client.get(f"{BASE}/teacher/units", headers=_b(teacher))).json()
    assert len(units) == 4
    assert units[0] == {
        "id": "frac-div-nat",
        "name": "분수 ÷ 자연수",
        "count": 5,
        "selected": True,
        "hasProblems": True,
    }
    saved = (
        await client.put(
            f"{BASE}/teacher/units", json={"selectedIds": ["nat-div-nat", "x"]}, headers=_b(teacher)
        )
    ).json()
    assert [u["id"] for u in saved if u["selected"]] == ["nat-div-nat"]
    again = (await client.get(f"{BASE}/teacher/units", headers=_b(teacher))).json()
    assert again == saved
    today = (await client.get(f"{BASE}/teacher/today", headers=_b(teacher))).json()
    assert today["units"] == ["자연수 ÷ 자연수"]
    # 알림 설정을 저장해도 단원 선택은 남고, Me.settings에 섞이지 않는다
    body = {"studyReminder": None, "learnDone": True, "activity": False, "marketing": False}
    me = (await client.put(f"{BASE}/me/settings", json=body, headers=_b(teacher))).json()
    assert "units" not in me["settings"]
    again = (await client.get(f"{BASE}/teacher/units", headers=_b(teacher))).json()
    assert again == saved
    # 다른 선생님은 자기 선택(기본 전체)
    other = await _login(client, t, "t3")
    units = (await client.get(f"{BASE}/teacher/units", headers=_b(other))).json()
    assert all(u["selected"] for u in units)


async def test_units_header_instructor_read_only(client):
    t = await _trial(client)
    h = {"X-Demo-Role": "instructor", "X-Demo-Actor": f"{t}-instructor"}
    units = (await client.get(f"{BASE}/teacher/units", headers=h)).json()
    assert all(u["selected"] for u in units)
    r = await client.put(f"{BASE}/teacher/units", json={"selectedIds": []}, headers=h)
    assert r.status_code == 403  # 저장할 계정이 없다


# --- 세상 사이 격리 ---------------------------------------------------------------------


async def test_cross_world_isolation(client, db_session):
    a = await _trial(client)
    b = await _trial(client)
    teacher_a = await _login(client, a, "t1")
    kid_a = await _login(client, a, "s1")
    await _login(client, b, "t1")  # 세상 b 만들기
    r = await client.post(
        f"{BASE}/teacher/seeds/{b}-s2", json={"amount": 1, "note": "x"}, headers=_b(teacher_a)
    )
    assert r.status_code == 403
    r = await client.post(f"{BASE}/teacher/orders/{b}-o1/deliver", headers=_b(teacher_a))
    assert r.status_code == 404
    await _give(db_session, f"{a}-child", 100)
    r = await client.post(f"{BASE}/student/shop/items/{b}-i2/buy", headers=_b(kid_a))
    assert r.status_code == 404
    board = (await client.get(f"{BASE}/teacher/seeds", headers=_b(teacher_a))).json()
    assert all(s["id"].startswith(a) for s in board["students"])
    assert all(i["id"].startswith(a) for i in board["items"])
    res = (await client.get(f"{BASE}/teacher/results", headers=_b(teacher_a))).json()
    assert all(r["id"].startswith(a) for r in res)
    order = await db_session.get(Order, f"{b}-o1")
    assert order.status == "교환 요청"


# --- 동시 요청 막기(보안 검토 11-12): 하루 1번 키·수량 원자 차감 ----------------------------


async def test_once_key_blocks_second_row_even_without_precheck(db_session):
    """사전 확인(earned_on)을 건너뛰고 도우미를 두 번 불러도 학습 완료·도장 행은 하루 1줄."""
    kid = "t-bbbbbbbbbbbbbbbb-child"
    assert await add_seed(db_session, kid, 3, STUDY_DONE, "단원", "system", NOW) is True
    # 같은 요청에서 먼저 한 일(알림)은 실패한 삽입 뒤에도 남아야 한다(savepoint)
    db_session.add(Notice(account_id="x", text="남아야 함", read=False, created_at=NOW))
    await db_session.flush()
    assert await add_seed(db_session, kid, 3, STUDY_DONE, "단원", "system", NOW) is False
    assert await add_seed(db_session, kid, 2, STAMP, "도장", "g", NOW) is True
    assert await add_seed(db_session, kid, 2, STAMP, "도장", "g", NOW) is False
    rows = list(await db_session.scalars(select(SeedLedger)))
    assert sorted(r.source for r in rows) == sorted([STUDY_DONE, STAMP])
    assert await _notices(db_session, "x") == ["남아야 함"]
    # 다음 날은 다시
    assert await add_seed(db_session, kid, 3, STUDY_DONE, "단원", "system", NOW + timedelta(days=1))


async def test_study_done_race_gives_zero(db_session, monkeypatch):
    async def _never(*_a, **_k) -> int:
        return 0

    monkeypatch.setattr("app.seeds.earned_on", _never)
    kid = "t-cccccccccccccccc-child"
    assert await earn_study_seeds(db_session, kid, "단원", NOW) == 3
    assert await earn_study_seeds(db_session, kid, "단원", NOW) == 0
    assert len(list(await db_session.scalars(select(SeedLedger)))) == 1


async def test_stamp_race_is_409(client, monkeypatch):
    t = await _trial(client)
    mom = await _login(client, t, "g1")
    assert (await client.post(f"{BASE}/guardian/stamp", headers=_b(mom))).status_code == 200

    async def _never(*_a, **_k) -> int:
        return 0

    monkeypatch.setattr(seed_routes, "earned_on", _never)  # 사전 확인을 지나쳤다고 친다
    r = await client.post(f"{BASE}/guardian/stamp", headers=_b(mom))
    assert r.status_code == 409 and r.json()["code"] == "already_stamped"
    monkeypatch.undo()
    s = (await client.get(f"{BASE}/guardian/stamp", headers=_b(mom))).json()
    assert s == {"stampedToday": True, "balance": 20}


async def test_stock_never_below_zero(client, db_session):
    t = await _trial(client)
    kid = await _login(client, t, "s1")
    await _give(db_session, f"{t}-child", 100)
    item = await db_session.get(ShopItem, f"{t}-i3")
    assert item is not None
    # 다른 요청이 마지막 1개를 먼저 가져갔다: DB는 0, 이 세션이 들고 있는 행은 아직 1
    item.stock = 1
    await db_session.flush()
    await db_session.execute(
        update(ShopItem)
        .where(ShopItem.id == f"{t}-i3")
        .values(stock=0)
        .execution_options(synchronize_session=False)
    )
    r = await client.post(f"{BASE}/student/shop/items/{t}-i3/buy", headers=_b(kid))
    assert r.status_code == 409 and r.json()["code"] == "sold_out"
    await db_session.refresh(item)
    assert item.stock == 0
    w = (await client.get(f"{BASE}/student/wallet", headers=_b(kid))).json()
    assert w["balance"] == 118  # 씨앗도 빠지지 않았다
    bought = await db_session.scalars(select(Order).where(Order.item_name == "보드게임 10분"))
    assert list(bought) == []
