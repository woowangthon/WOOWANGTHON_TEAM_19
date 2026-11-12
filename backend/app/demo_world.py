"""체험 세트마다 체험 세상 하나(명세 4.12-4, 설계 §4·§10) — org.ts seed()와 같은 사람·학원·강의실·씨앗.

- lazy: `GET /demo/accounts`·`POST /demo/login`·`POST /auth/login`(X-Trial-Id) 처음에 만든다.
  `/trial`은 그대로(아이 행만). 세트 아이 `{t}-child`가 DB에 없으면 404 trial_not_found.
- id: s1 → `{t}-child`(기존 day3 행), g1 → `{t}-guardian`, t1 → `{t}-instructor`, 나머지 `{t}-{key}`.
  학원·강의실·신청·상품·주문도 `{t}-{key}`(a1, c1, app1, i1, o1).
- 아이디 = seed loginId + `_` + 세트별 8자(전역 유일, 추측 로그인 막기 11-12). 비밀번호 demo1234(해시 1번 계산 재사용).
  연결 코드·일련번호는 세트마다 무작위. 이메일은 해시만.
- 한 트랜잭션, add_all + flush 한 번(커밋은 부르는 쪽). 합성 데이터만.
"""

import re
import secrets
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import (
    DEFAULT_SETTINGS,
    demo_password_hash,
    email_hash,
    fail,
    rand_code,
    unique_serial,
)
from app.models import Student
from app.models_org import (
    Academy,
    AcademyApplication,
    Account,
    CosmeticOwned,
    Link,
    Notice,
    Order,
    Room,
    RoomPerson,
    SeedLedger,
    ShopItem,
)
from app.seeds import currency_of, once_key
from app.timeutil import SEOUL, seoul_date

_SUFFIX_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"

# (key, role, name, loginId, extra) — org.ts seed() users 순서 그대로
SEED_USERS: list[tuple[str, str, str, str, dict[str, Any]]] = [
    ("op", "operator", "우왕 운영팀", "operator", {"email": "ops@example.com"}),
    (
        "own1",
        "teacher",
        "박원장",
        "park_owner",
        {"academy": True, "status": "승인됨", "app": "app1", "email": "park@example.com"},
    ),
    ("own2", "teacher", "최원장", "choi_owner", {"app": "app2", "email": "choi@example.com"}),
    (
        "t1",
        "teacher",
        "김선생님",
        "kim_teacher",
        {"academy": True, "status": "승인됨", "email": "kim@example.com"},
    ),
    (
        "t2",
        "teacher",
        "이선생님",
        "lee_teacher",
        {"academy": True, "status": "승인 대기", "email": "lee@example.com"},
    ),
    ("t3", "teacher", "정선생님", "jung_teacher", {"email": "jung@example.com"}),
    ("s1", "student", "지우", "jiwoo", {"grade": 5, "link": True, "academy": True}),
    ("s2", "student", "이민준", "minjun", {"grade": 5, "link": True, "academy": True}),
    ("s3", "student", "박서연", "seoyeon", {"grade": 5, "link": True, "academy": True}),
    ("s4", "student", "최하린", "harin", {"grade": 5, "link": True, "academy": True}),
    (
        "g1",
        "guardian",
        "지우 보호자",
        "jiwoo_mom",
        {"link": True, "academy": True, "email": "mom@example.com"},
    ),
]
SEED_KEYS = {key for key, *_ in SEED_USERS}
SEED_LOGIN_IDS = [login for _, _, _, login, _ in SEED_USERS]
# 체험 아이디 형식(가입 불가): seed loginId + _ + 8자(예전 4자 세트도 막는다)
RESERVED_LOGIN = re.compile(
    r"^(" + "|".join(re.escape(x) for x in SEED_LOGIN_IDS) + r")_[a-z0-9]{4,8}$"
)
_KEY_ID = {"s1": "child", "g1": "guardian", "t1": "instructor"}
_ID_KEY = {v: k for k, v in _KEY_ID.items()}
_TRIAL_ACCOUNT = re.compile(r"^t-[a-z0-9]{16}-([a-z0-9]+)$")

# 체험 계정 시트(org.ts demoAccounts의 pick)
DEMO_PICK = [
    ("s1", ""),
    ("g1", ""),
    ("t1", ""),
    ("own1", "원장"),
    ("own2", "학원 심사 중"),
    ("t2", "소속 승인 대기"),
    ("t3", "소속 없음"),
    ("op", "학원 심사"),
]


def world_id(trial_id: str, key: str) -> str:
    """seed 키 → 체험 세상 id."""
    return f"{trial_id}-{_KEY_ID.get(key, key)}"


def seed_key_of(user_id: str) -> str | None:
    """`{아무 t}-child` 같은 전체 id든 seed 키(`s1`)든 seed 키로. 모르면 None."""
    if user_id in SEED_KEYS:
        return user_id
    m = _TRIAL_ACCOUNT.match(user_id)
    if m is None:
        return None
    key = _ID_KEY.get(m.group(1), m.group(1))
    return key if key in SEED_KEYS else None


async def world_exists(db: AsyncSession, trial_id: str) -> bool:
    """세상 유무는 학원 행으로 본다(지울 수 없는 행). 계정 행 기준이면 탈퇴 뒤 재생성 PK 충돌(11-12 A1)."""
    return await db.get(Academy, world_id(trial_id, "a1")) is not None


async def _suffix(db: AsyncSession) -> str:
    """세트별 8자(약 2.8조 가지 — 공통 비밀번호라 추측으로 남의 세트에 못 들어가게). 이 세트의 아이디 11개가 하나도 겹치지 않을 때까지 다시 뽑는다."""
    while True:
        suffix = "".join(secrets.choice(_SUFFIX_CHARS) for _ in range(8))
        ids = [f"{x}_{suffix}" for x in SEED_LOGIN_IDS]
        taken = await db.scalar(select(Account.id).where(Account.login_id.in_(ids)).limit(1))
        if taken is None:
            return suffix


async def _link_codes(db: AsyncSession, n: int) -> list[str]:
    while True:
        codes = {rand_code(6) for _ in range(n)}
        if len(codes) < n:
            continue
        taken = await db.scalar(select(Account.id).where(Account.link_code.in_(codes)).limit(1))
        if taken is None:
            return sorted(codes)


def _at(now: datetime, days_ago: int, hh: int | None = None, mm: int = 0) -> datetime:
    """서울 날짜 기준 n일 전. hh가 없으면 지금 시각에서 n일 전."""
    if hh is None:
        return now - timedelta(days=days_ago)
    day = seoul_date(now) - timedelta(days=days_ago)
    # UTC로 바꿔 저장한다(SQLite는 시간대를 버리고 as_utc가 UTC로 읽는다)
    return datetime.combine(day, time(hh, mm), tzinfo=SEOUL).astimezone(UTC)


async def ensure_world(db: AsyncSession, trial_id: str, now: datetime) -> bool:
    """세트 t의 체험 세상이 없으면 만든다. 만들었으면 True. 세트 아이가 없으면 404 trial_not_found."""
    if await world_exists(db, trial_id):
        return False
    # 동시 요청은 세트 아이 행을 잠가 줄 세운다(Postgres FOR UPDATE, SQLite는 무시). 잠근 뒤 다시 확인(A2)
    s1_id = world_id(trial_id, "s1")
    s1 = await db.get(Student, s1_id, with_for_update=True)
    if s1 is None:
        fail("체험이 끝났어요. 처음부터 다시 시작해 주세요.", 404, "trial_not_found")
    if await world_exists(db, trial_id):
        return False
    t = trial_id
    wid = lambda key: world_id(t, key)  # noqa: E731
    today = seoul_date(now)
    suffix = await _suffix(db)
    pw = demo_password_hash()
    serial = await unique_serial(db)
    linked_keys = [k for k, _, _, _, extra in SEED_USERS if extra.get("link")]
    codes = dict(zip(linked_keys, await _link_codes(db, len(linked_keys)), strict=True))
    rows: list[Any] = []
    stamp = {"trial_id": t, "created_at": now}

    for key, role, name, login, extra in SEED_USERS:
        rows.append(
            Account(
                id=wid(key),
                login_id=f"{login}_{suffix}",
                pw_hash=pw,
                role=role,
                name=name,
                grade=extra.get("grade"),
                email_hash=email_hash(extra["email"]) if "email" in extra else None,
                link_code=codes.get(key),
                academy_id=wid("a1") if extra.get("academy") else None,
                teacher_status=extra.get("status"),
                application_id=wid(extra["app"]) if "app" in extra else None,
                outfit=None,
                settings=dict(DEFAULT_SETTINGS),
                marketing=False,
                student_id=wid(key) if role == "student" else None,
                **stamp,
            )
        )
    # s2~s4 학생 행(강사 오늘·결과용): day3 아님, 연속 0, 세션 없음, 약속 동의 끝
    for key in ("s2", "s3", "s4"):
        name = next(n for k, _, n, _, _ in SEED_USERS if k == key)
        rows.append(
            Student(
                id=wid(key),
                nickname=name,
                grade_band="초5-6",
                streak_days=0,
                consent=True,
                fence_codes=[],
                created_at=now,
            )
        )
    rows.append(
        Link(
            student_account_id=wid("s1"),
            guardian_account_id=wid("g1"),
            status="연결됨",
            consent_at=today - timedelta(days=20),
            **stamp,
        )
    )
    rows += [
        AcademyApplication(
            id=wid("app1"),
            owner_id=wid("own1"),
            owner_name="박원장",
            org_type="학원",
            academy_name="우왕수학학원",
            biz_no="123-45-67890",
            ceo="박원장",
            phone="043-000-0000",
            address="충북 청주시 서원구",
            status="승인",
            applied_at=_at(now, 30),
            serial=serial,
            reject_reason=None,
            **stamp,
        ),
        AcademyApplication(
            id=wid("app2"),
            owner_id=wid("own2"),
            owner_name="최원장",
            org_type="학원",
            academy_name="새싹영어학원",
            biz_no="234-56-78901",
            ceo="최원장",
            phone="043-111-1111",
            address="충북 청주시 흥덕구",
            status="심사 중",
            applied_at=_at(now, 0, 9, 30),
            serial=None,
            reject_reason=None,
            **stamp,
        ),
        Academy(
            id=wid("a1"),
            name="우왕수학학원",
            org_type="학원",
            serial=serial,
            owner_id=wid("own1"),
            entry_code=None,
            entry_expires_at=None,
            **stamp,
        ),
        Room(
            id=wid("c1"),
            academy_id=wid("a1"),
            teacher_id=wid("t1"),
            name="5학년 A반",
            plan="분수의 나눗셈 (11월)",
            **stamp,
        ),
        Room(
            id=wid("c2"),
            academy_id=wid("a1"),
            teacher_id=wid("t1"),
            name="5학년 심화반",
            plan="분수 응용 문제",
            **stamp,
        ),
    ]
    for key in ("s1", "s2", "s3"):
        rows.append(
            RoomPerson(room_id=wid("c1"), student_account_id=wid(key), state="member", **stamp)
        )
    rows.append(
        RoomPerson(room_id=wid("c2"), student_account_id=wid("s4"), state="requested", **stamp)
    )
    # 재화 기록(org.ts L(): 학습 완료·칭찬 = 씨앗, 보호자 도장 = 도장 1개). created_at이 화면 시각(at)
    ledger = [
        ("s1", 3, 3, "학습 완료", "분수의 덧셈", "system", (18, 10)),
        ("s1", 3, 1, "보호자 도장", "오늘 이야기를 나눴어요", "g1", (18, 10)),
        ("s1", 2, 3, "학습 완료", "분수의 덧셈", "system", (18, 10)),
        ("s1", 2, 5, "학습지도자 칭찬", "단원평가 100점", "t1", (18, 10)),
        ("s1", 1, 3, "학습 완료", "분수의 덧셈", "system", (18, 10)),
        ("s1", 1, 1, "보호자 도장", "오늘 이야기를 나눴어요", "g1", (18, 10)),
        ("s2", 1, 24, "학습 완료", "지난 기록", "system", None),
        ("s2", 0, -20, "상점 구매", "칭찬 간식 쿠폰", "s2", None),
        ("s3", 1, 11, "학습 완료", "지난 기록", "system", None),
    ]
    for i, (key, days, amount, source, note, by, hm) in enumerate(ledger, start=1):
        at = _at(now, days, *hm) if hm else _at(now, days)
        rows.append(
            SeedLedger(
                id=wid(f"l{i}"),
                student_account_id=wid(key),
                date=today - timedelta(days=days),
                amount=amount,
                source=source,
                currency=currency_of(source),
                note=note,
                by=by if by == "system" else wid(by),
                once_key=once_key(wid(key), source, today - timedelta(days=days)),
                trial_id=t,
                created_at=at,
            )
        )
    items = [
        ("i1", "칭찬 간식 쿠폰", 20, 10, True, "수업 끝나고 과자 1개"),
        ("i2", "자리 고르기권", 15, None, True, "다음 수업 자리를 내가 골라요"),
        ("i3", "보드게임 10분", 25, 5, True, "금요일 수업 끝에"),
        ("i4", "겨울방학 특별 선물", 40, 3, False, "12월에 공개 예정"),
    ]
    for iid, name, price, stock, visible, note in items:
        rows.append(
            ShopItem(
                id=wid(iid),
                teacher_id=wid("t1"),
                name=name,
                price=price,
                stock=stock,
                visible=visible,
                note=note,
                **stamp,
            )
        )
    rows.append(
        Order(
            id=wid("o1"),
            student_account_id=wid("s2"),
            teacher_id=wid("t1"),
            item_name="칭찬 간식 쿠폰",
            price=20,
            status="교환 요청",
            trial_id=t,
            created_at=_at(now, 0, 16, 40),
        )
    )
    notices = [
        ("n1", "g1", (9, 0), "김선생님이 지우의 이번 주 범위를 정했어요: 분수의 덧셈·뺄셈", None),
        ("n2", "s1", (9, 0), "보호자가 어제 도장을 찍어 줬어! 씨앗 +2", "/student/shop"),
        ("n3", "own1", (10, 0), "이선생님이 소속을 신청했어요", "/owner"),
        ("n4", "t1", (16, 40), "이민준이 「칭찬 간식 쿠폰」 교환을 요청했어요", "/teacher/seeds"),
    ]
    for nid, key, (hh, mm), text, to in notices:
        rows.append(
            Notice(
                id=wid(nid),
                account_id=wid(key),
                text=text,
                to_path=to,
                read=False,
                trial_id=t,
                created_at=_at(now, 0, hh, mm),
            )
        )
    rows.append(CosmeticOwned(student_account_id=wid("s1"), cosmetic_id="glasses", **stamp))
    # savepoint 안에서 넣는다. 다른 요청이 먼저 만들었으면 이 몫만 버리고 False(같은 요청의 앞일은 남는다)
    try:
        async with db.begin_nested():
            db.add_all(rows)
    except IntegrityError:
        return False
    return True


async def demo_accounts(db: AsyncSession, trial_id: str) -> list[dict[str, Any]]:
    """체험 계정 시트(org.ts demoAccounts 모양)."""
    out = []
    for key, note in DEMO_PICK:
        acc = await db.get(Account, world_id(trial_id, key))
        if acc is not None:
            out.append(
                {
                    "id": acc.id,
                    "name": acc.name,
                    "role": acc.role,
                    "loginId": acc.login_id,
                    "note": note,
                }
            )
    return out
