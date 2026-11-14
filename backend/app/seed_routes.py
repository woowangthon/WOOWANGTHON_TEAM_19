"""씨앗·상점·도장·꾸미기 API와 남은 학습 함수 `/api/v1/compat`(명세 4.12, 설계 §10 P4·P5).

frontend/src/api/http.ts 경로·본문 그대로, 응답은 types.ts 모양(camelCase).
- 학생: getWallet·getStudentShop·buyAcademyItem·buyCosmetic·equipOutfit
- 보호자: getStampState·stamp (아이 = 연결된 첫 아이)
- 학습지도자: getSeedBoard·grantSeeds·saveShopItem·deliverOrder
- 학습: getRecords(`/student/records`)·getResults(`/teacher/results`)·getUnits·saveUnits(`/teacher/units`)
규칙·문구는 frontend/src/api/org.ts fail() 그대로. 씨앗·상점은 로그인 계정만(require_account),
records·results·units는 기존 학습 신원(Child·Instructor: 계정 또는 체험 헤더)을 쓴다.
DB가 모르는 값(실수 유형·어려운 점·연속 초급 등)은 지어내지 않고 null/0. 아이 원문은 싣지 않는다.
"""

import secrets
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import (
    CurrentAccount,
    Db,
    Now,
    fail,
    first_child_id,
    notify,
    require_account,
    stamp_label,
)
from app.actors import Actor
from app.api import TAG_NAME, Child, _today_session, progress
from app.compat import DIFFICULTY, _CompatRoute, _problem, _unit_today
from app.instructor import Instructor
from app.models import Message, Problem, Session, Student
from app.models_org import Account, CosmeticOwned, Order, Room, RoomPerson, SeedLedger, ShopItem
from app.seeds import (
    COSMETIC_BUY,
    COSMETICS,
    PRAISE,
    PURCHASE,
    SEED,
    SEED_RULES,
    STAMP,
    add_seed,
    balance_of,
    earned_on,
    lock_student,
    save_selected_tags,
    selected_tags,
    stamps_of,
    teachers_of_student,
    week_days,
)
from app.state_machine import State
from app.timeutil import seoul_date
from app.trial import ACCOUNT_PREFIX, TRIAL_PREFIX

router = APIRouter(prefix="/compat", route_class=_CompatRoute)

_ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
_WEEKDAY_SUN0 = "일월화수목금토"  # lib/date shortLabel
_COSMETIC = {c[0]: c for c in COSMETICS}


def _new_id(prefix: str) -> str:
    return f"{prefix}-" + "".join(secrets.choice(_ID_CHARS) for _ in range(16))


async def _name_of(db: AsyncSession, account_id: str) -> str:
    """org.ts nameOf: 계정 이름, 없으면 학생 별명, 그것도 없으면 「알 수 없음」."""
    acc = await db.get(Account, account_id)
    if acc is not None:
        return acc.name
    student = await db.get(Student, account_id)
    return student.nickname if student is not None else "알 수 없음"


async def _order_view(db: AsyncSession, o: Order) -> dict[str, Any]:
    return {
        "id": o.id,
        "studentName": await _name_of(db, o.student_account_id),
        "itemName": o.item_name,
        "price": o.price,
        "at": stamp_label(o.created_at),
        "status": o.status,
    }


def _item_view(i: ShopItem) -> dict[str, Any]:
    return {
        "id": i.id,
        "name": i.name,
        "price": i.price,
        "stock": i.stock,
        "visible": i.visible,
        "note": i.note,
    }


# --- 학생: 지갑·상점 --------------------------------------------------------------------


@router.get("/student/wallet")
async def get_wallet(db: Db, account: CurrentAccount) -> dict[str, Any]:
    s = require_account(account, "student")
    rows = await db.scalars(
        select(SeedLedger)
        .where(SeedLedger.student_account_id == s.id)
        .order_by(SeedLedger.created_at.desc(), SeedLedger.id.desc())
    )
    history = [
        {
            "id": r.id,
            "at": stamp_label(r.created_at),
            "amount": r.amount,
            "source": r.source,
            "currency": r.currency,
            "note": r.note,
        }
        for r in rows
    ]
    return {
        "balance": await balance_of(db, s.id),
        "stamps": await stamps_of(db, s.id),
        "history": history,
    }


async def _student_shop(db: AsyncSession, s: Account) -> dict[str, Any]:
    teachers = await teachers_of_student(db, s.id)
    items = (
        await db.scalars(
            select(ShopItem)
            .where(ShopItem.teacher_id.in_(teachers), ShopItem.visible.is_(True))
            .order_by(ShopItem.created_at, ShopItem.id)
        )
        if teachers
        else []
    )
    owned = set(
        await db.scalars(
            select(CosmeticOwned.cosmetic_id).where(CosmeticOwned.student_account_id == s.id)
        )
    )
    orders = await db.scalars(
        select(Order)
        .where(Order.student_account_id == s.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    return {
        "balance": await balance_of(db, s.id),  # 씨앗(학원 상점)
        "stamps": await stamps_of(db, s.id),  # 칭찬 도장(꾸미기, cosmetics.price 단위)
        "academyItems": [_item_view(i) for i in items],
        "cosmetics": [
            {
                "id": cid,
                "kind": kind,
                "name": name,
                "price": price,
                "owned": cid in owned,
                "equipped": s.outfit == cid,
            }
            for cid, kind, name, price in COSMETICS
        ],
        "orders": [await _order_view(db, o) for o in orders],
    }


@router.get("/student/shop")
async def get_student_shop(db: Db, account: CurrentAccount) -> dict[str, Any]:
    return await _student_shop(db, require_account(account, "student"))


@router.post("/student/shop/items/{item_id}/buy")
async def buy_academy_item(
    item_id: str, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    s = require_account(account, "student")
    item = await db.get(ShopItem, item_id)
    if (
        item is None
        or not item.visible
        or item.teacher_id not in await teachers_of_student(db, s.id)
    ):
        fail("상품을 찾지 못했어요.", 404, "item_not_found")
    if item.stock is not None and item.stock <= 0:
        fail("다 팔렸어요.", 409, "sold_out")
    await lock_student(db, s.id)  # 같은 학생의 동시 구매를 줄 세운 뒤 잔액을 읽는다
    if await balance_of(db, s.id) < item.price:
        fail("씨앗이 모자라요.", 409, "not_enough_seeds")
    if item.stock is not None:
        # 수량은 DB에서 한 번에 깎는다(0 밑으로 안 감). 0줄이면 다른 요청이 마지막을 가져갔다
        res = await db.execute(
            update(ShopItem)
            .where(ShopItem.id == item.id, ShopItem.stock > 0)
            .values(stock=ShopItem.stock - 1)
            .execution_options(synchronize_session=False)
        )
        if getattr(res, "rowcount", 0) != 1:
            fail("다 팔렸어요.", 409, "sold_out")
        await db.refresh(item, ["stock"])
    await add_seed(db, s.id, -item.price, PURCHASE, item.name, s.id, now)
    db.add(
        Order(
            id=_new_id("o"),
            student_account_id=s.id,
            teacher_id=item.teacher_id,
            item_name=item.name,
            price=item.price,
            status="교환 요청",
            trial_id=s.trial_id,
            created_at=now,
        )
    )
    notify(
        db,
        item.teacher_id,
        f"{s.name} 학생이 「{item.name}」 교환을 요청했어요",
        "/teacher/seeds",
        now,
        s.trial_id,
    )
    await db.commit()
    return await _student_shop(db, s)


@router.post("/student/shop/cosmetics/{cosmetic_id}/buy")
async def buy_cosmetic(
    cosmetic_id: str, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    s = require_account(account, "student")
    c = _COSMETIC.get(cosmetic_id)
    if c is None:
        fail("상품을 찾지 못했어요.", 404, "item_not_found")
    _, kind, name, price = c
    await lock_student(db, s.id)  # 같은 학생의 동시 구매를 줄 세운 뒤 보유·잔액을 읽는다
    if await db.get(CosmeticOwned, (s.id, cosmetic_id)) is not None:
        fail("이미 가지고 있어요.", 409, "already_owned")
    short = price - await stamps_of(db, s.id)
    if short > 0:
        fail(f"도장이 {short}개 더 필요해요.", 409, "not_enough_stamps")
    await add_seed(db, s.id, -price, COSMETIC_BUY, name, s.id, now)
    db.add(
        CosmeticOwned(
            student_account_id=s.id, cosmetic_id=cosmetic_id, trial_id=s.trial_id, created_at=now
        )
    )
    if kind == "outfit":
        s.outfit = cosmetic_id  # 사면 바로 입어 본다
    await db.commit()
    return await _student_shop(db, s)


class OutfitIn(BaseModel):
    id: str | None = None


@router.put("/student/outfit")
async def equip_outfit(body: OutfitIn, db: Db, account: CurrentAccount) -> dict[str, Any]:
    s = require_account(account, "student")
    if body.id is not None and await db.get(CosmeticOwned, (s.id, body.id)) is None:
        fail("아직 없는 옷이에요.", 409, "not_owned")
    s.outfit = body.id
    await db.commit()
    return await _student_shop(db, s)


# --- 보호자 도장 -------------------------------------------------------------------------


async def _stamp_state(db: AsyncSession, child: str | None, now: datetime) -> dict[str, Any]:
    if child is None:
        return {"stampedToday": False, "balance": 0, "stamps": 0}
    return {
        "stampedToday": await earned_on(db, child, STAMP, seoul_date(now)) > 0,
        "balance": await balance_of(db, child),  # 씨앗(그대로)
        "stamps": await stamps_of(db, child),
    }


@router.get("/guardian/stamp")
async def get_stamp_state(db: Db, now: Now, account: CurrentAccount) -> dict[str, Any]:
    g = require_account(account, "guardian")
    return await _stamp_state(db, await first_child_id(db, g.id), now)


@router.post("/guardian/stamp")
async def stamp(db: Db, now: Now, account: CurrentAccount) -> dict[str, Any]:
    g = require_account(account, "guardian")
    child = await first_child_id(db, g.id)
    if child is None:
        fail("먼저 아이와 연결해 주세요.", 404, "not_linked")
    if await earned_on(db, child, STAMP, seoul_date(now)) > 0:
        fail("오늘 도장은 이미 찍었어요. 내일 또 찍어 주세요.", 409, "already_stamped")
    amount = SEED_RULES["guardianStamp"]
    if not await add_seed(db, child, amount, STAMP, "오늘 이야기를 나눴어요", g.id, now):
        # 동시 요청이 먼저 찍었다(once_key 유일 제약)
        fail("오늘 도장은 이미 찍었어요. 내일 또 찍어 주세요.", 409, "already_stamped")
    notify(
        db, child, f"보호자가 도장을 찍어 줬어! 도장 +{amount}", "/student/shop", now, g.trial_id
    )
    await db.commit()
    return await _stamp_state(db, child, now)


# --- 학습지도자: 씨앗 판 ----------------------------------------------------------------


async def _my_students(db: AsyncSession, teacher_id: str) -> list[str]:
    """내 강의실 member(강의실 순, 들어온 순, 중복 없이 — org.ts seedBoard ids)."""
    rows = await db.execute(
        select(RoomPerson.student_account_id)
        .join(Room, Room.id == RoomPerson.room_id)
        .where(Room.teacher_id == teacher_id, RoomPerson.state == "member")
        .order_by(Room.created_at, Room.id, RoomPerson.created_at, RoomPerson.student_account_id)
    )
    return list(dict.fromkeys(r[0] for r in rows))


async def _seed_board(db: AsyncSession, t: Account, now: datetime) -> dict[str, Any]:
    today = seoul_date(now)
    week = week_days(now)
    students = []
    for sid in await _my_students(db, t.id):
        earned_week = await db.scalar(
            select(func.coalesce(func.sum(SeedLedger.amount), 0)).where(
                SeedLedger.student_account_id == sid,
                SeedLedger.currency == SEED,
                SeedLedger.amount > 0,
                SeedLedger.date >= week[0],
                SeedLedger.date <= week[-1],
            )
        )
        students.append(
            {
                "id": sid,
                "name": await _name_of(db, sid),
                "balance": await balance_of(db, sid),
                "stamps": await stamps_of(db, sid),
                "earnedWeek": int(earned_week or 0),
                "grantedToday": await earned_on(db, sid, PRAISE, today),
            }
        )
    orders = list(
        await db.scalars(
            select(Order)
            .where(Order.teacher_id == t.id)
            .order_by(Order.created_at.desc(), Order.id.desc())
        )
    )
    orders.sort(key=lambda o: o.status != "교환 요청")  # 교환 요청 먼저(안정 정렬)
    items = await db.scalars(
        select(ShopItem)
        .where(ShopItem.teacher_id == t.id)
        .order_by(ShopItem.created_at, ShopItem.id)
    )
    return {
        "students": students,
        "orders": [await _order_view(db, o) for o in orders],
        "items": [_item_view(i) for i in items],
    }


@router.get("/teacher/seeds")
async def get_seed_board(db: Db, now: Now, account: CurrentAccount) -> dict[str, Any]:
    return await _seed_board(db, require_account(account, "teacher"), now)


class GrantIn(BaseModel):
    amount: float  # 정수 여부는 아래에서 org.ts 문구로 검사한다
    note: str = ""


@router.post("/teacher/seeds/{student_id}")
async def grant_seeds(
    student_id: str, body: GrantIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t = require_account(account, "teacher")
    if student_id not in await _my_students(db, t.id):
        fail("내 강의실 학생에게만 줄 수 있어요.", 403, "forbidden")
    cap, max_one = SEED_RULES["teacherDailyCap"], SEED_RULES["teacherMax"]
    if not body.amount.is_integer() or not 1 <= body.amount <= max_one:
        fail(f"한 번에 1~{max_one}개까지 줄 수 있어요.", 422, "invalid_amount")
    amount = int(body.amount)
    note = body.note.strip()[:30]
    if not note:
        fail("칭찬 이유를 골라 주세요.", 422, "invalid_note")
    await lock_student(db, student_id)  # 같은 학생 칭찬을 줄 세운 뒤 오늘 합을 읽는다
    if await earned_on(db, student_id, PRAISE, seoul_date(now)) + amount > cap:
        fail(f"한 학생에게 하루 {cap}개까지 줄 수 있어요.", 409, "daily_cap")
    await add_seed(db, student_id, amount, PRAISE, note, t.id, now)
    notify(
        db,
        student_id,
        f"{t.name}이 칭찬 씨앗 {amount}개를 줬어! ({note})",
        "/student/shop",
        now,
        t.trial_id,
    )
    await db.commit()
    return await _seed_board(db, t, now)


class ShopItemIn(BaseModel):
    id: str | None = None
    name: str = ""
    price: float = 0
    stock: float | None = None
    visible: bool = True
    note: str = ""


def _check_item(body: ShopItemIn) -> tuple[str, int, int | None]:
    name = body.name.strip()
    if not name:
        fail("상품 이름을 적어 주세요.", 422, "invalid_item")
    if not body.price.is_integer() or not 1 <= body.price <= 200:
        fail("가격은 1~200 씨앗으로 정해 주세요.", 422, "invalid_item")
    if body.stock is not None and (not body.stock.is_integer() or body.stock < 0):
        fail("수량은 0 이상으로 적어 주세요.", 422, "invalid_item")
    if body.stock is not None and body.stock > 9999:  # 큰 수는 DB 정수 넘침 500(A6)
        fail("수량은 9999개까지 적을 수 있어요.", 422, "invalid_item")
    return name[:60], int(body.price), None if body.stock is None else int(body.stock)


@router.post("/teacher/shop/items")
async def create_shop_item(
    body: ShopItemIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t = require_account(account, "teacher")
    name, price, stock = _check_item(body)
    db.add(
        ShopItem(
            id=_new_id("i"),
            teacher_id=t.id,
            name=name,
            price=price,
            stock=stock,
            visible=body.visible,
            note=body.note[:120],
            trial_id=t.trial_id,
            created_at=now,
        )
    )
    await db.commit()
    return await _seed_board(db, t, now)


@router.put("/teacher/shop/items/{item_id}")
async def update_shop_item(
    item_id: str, body: ShopItemIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t = require_account(account, "teacher")
    name, price, stock = _check_item(body)
    item = await db.get(ShopItem, item_id)
    if item is None or item.teacher_id != t.id:
        fail("상품을 찾지 못했어요.", 404, "item_not_found")
    item.name, item.price, item.stock = name, price, stock
    item.visible, item.note = body.visible, body.note[:120]
    await db.commit()
    return await _seed_board(db, t, now)


@router.post("/teacher/orders/{order_id}/deliver")
async def deliver_order(order_id: str, db: Db, now: Now, account: CurrentAccount) -> dict[str, Any]:
    t = require_account(account, "teacher")
    order = await db.get(Order, order_id)
    if order is None or order.teacher_id != t.id:
        fail("교환 요청을 찾지 못했어요.", 404, "order_not_found")
    order.status = "전달 완료"
    notify(
        db,
        order.student_account_id,
        f"「{order.item_name}」을 받았어!",
        "/student/shop",
        now,
        t.trial_id,
    )
    await db.commit()
    return await _seed_board(db, t, now)


# --- 학습: 학생 기록 -------------------------------------------------------------------


def _short_label(d: date) -> str:
    """lib/date shortLabel: 「11월 12일 (목)」."""
    return f"{d.month}월 {d.day}일 ({_WEEKDAY_SUN0[(d.weekday() + 1) % 7]})"


@router.get("/student/records")
async def get_records(db: Db, student: Child) -> list[dict[str, Any]]:
    """같이 풀기를 끝낸 날(세션이 study를 떠남)마다 한 줄. 메타데이터만(대화 원문 없음).

    chatted = 판정 없는 아이 말(수다 쪽)이 남아 있는지. 메시지는 72시간 뒤 만료라 그 뒤엔 false.
    """
    sessions = await db.scalars(
        select(Session)
        .where(Session.student_id == student.id, Session.state != State.STUDY.value)
        .order_by(Session.date.desc())
    )
    out = []
    for row in sessions:
        chatted = await db.scalar(
            select(Message.id)
            .where(Message.session_id == row.id, Message.role == "child", Message.judge.is_(None))
            .limit(1)
        )
        problem = await _problem(db, row)
        prog = await progress(db, row)  # 한 문제 세션이면 예전 값(0·1 / 1, 힌트 최대 2)
        out.append(
            {
                "date": _short_label(row.date),
                "unit": TAG_NAME.get(problem.tag, problem.tag) if problem else "오늘 문제",
                "solved": prog.solved,
                "total": prog.total,
                "difficulty": DIFFICULTY,
                "hints": prog.hints,
                "chatted": chatted is not None,
            }
        )
    return out


# --- 학습: 학습지도자 결과·단원 ----------------------------------------------------------


@router.get("/teacher/results")
async def get_results(db: Db, now: Now, actor: Instructor) -> list[dict[str, Any]]:
    """오늘 결과(compat /teacher/today와 같은 범위). 실수 유형·어려운 점은 칸이 없어 null."""
    query = select(Student).order_by(Student.id)
    if actor.allowed is not None:
        query = query.where(Student.id.in_(actor.allowed))
    elif actor.scope is not None:
        query = query.where(Student.id == actor.scope)
    else:  # 헤더 강사는 체험 아이·가입 학생을 못 본다(A3)
        query = query.where(
            ~Student.id.startswith(TRIAL_PREFIX), ~Student.id.startswith(ACCOUNT_PREFIX)
        )
    out = []
    for student in await db.scalars(query):
        session = await _today_session(db, student, now)
        done = session is not None and session.state != State.STUDY.value
        prog = await progress(db, session) if session is not None else None
        out.append(
            {
                "id": student.id,
                "name": student.nickname,
                "done": done,
                "unit": await _unit_today(db, student, session, now) or "-",
                "solved": prog.solved if prog is not None and done else 0,
                "total": prog.total if prog is not None else 1,
                "difficulty": DIFFICULTY if done else None,
                "streak": student.streak_days,
                "hints": prog.hints if prog is not None else 0,
                "mistake": None,
                "hardPoint": None,
                "beginnerRepeat": 0,  # 난이도를 저장하지 않는다
            }
        )
    await db.commit()
    return out


async def _units(db: AsyncSession, account: Account | None) -> list[dict[str, Any]]:
    rows = await db.execute(select(Problem.tag, func.count()).group_by(Problem.tag))
    counts: dict[str, int] = {tag: n for tag, n in rows.all()}
    chosen = set(selected_tags(account))
    return [
        {
            "id": tag,
            "name": name,
            "count": counts.get(tag, 0),
            "selected": tag in chosen,
            "hasProblems": counts.get(tag, 0) > 0,
        }
        for tag, name in TAG_NAME.items()
    ]


async def _teacher_account(db: AsyncSession, actor: Actor) -> Account | None:
    return await db.get(Account, actor.id) if actor.allowed is not None else None


@router.get("/teacher/units")
async def get_units(db: Db, actor: Instructor) -> list[dict[str, Any]]:
    """시드 태그 = 단원. 선택은 계정 학습지도자별(accounts.settings), 체험 헤더는 전체 선택."""
    return await _units(db, await _teacher_account(db, actor))


class UnitsIn(BaseModel):
    selectedIds: list[str]


@router.put("/teacher/units")
async def save_units(body: UnitsIn, db: Db, actor: Instructor) -> list[dict[str, Any]]:
    account = await _teacher_account(db, actor)
    if account is None:
        fail("로그인한 학습지도자만 단원을 저장할 수 있어요.", 403, "forbidden")
    save_selected_tags(account, body.selectedIds)
    await db.commit()
    return await _units(db, account)
