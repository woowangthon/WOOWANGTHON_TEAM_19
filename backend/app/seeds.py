"""씨앗(재화) 규칙과 단원 선택 — 라우터 없는 도우미(명세 4.12, 설계 §10 P4·P5).

- 규칙 숫자·꾸미기 목록은 frontend/src/api/org.ts SEED_RULES·COSMETICS 그대로.
- 씨앗 기록(seed_ledger)의 학생 키 = students.id(설계 §9-8). 잔액 = 기록 합.
- 학습 완료 씨앗은 학생·서울 날짜당 한 번(earn_study_seeds). compat의 after-study가 부른다.
- 하루 1번 출처(학습 완료·보호자 도장)는 seed_ledger.once_key 유일 제약으로 동시 요청도 막는다.
  씨앗이 빠지는 일(구매)·상한 있는 일(칭찬)은 lock_student로 학생 계정 행을 잠근 뒤 잔액·상한을 읽는다.
- 학습지도자 단원 선택은 accounts.settings의 `units` 키(태그 목록)에 둔다(새 열을 만들지 않는다).
  me_view·saveSettings는 이 키를 건드리지 않는다.
compat.py와 seed_routes.py가 둘 다 쓰므로 순환 import를 피해 여기 따로 둔다.
"""

import re
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.actors import Actor
from app.api import TAG_NAME
from app.models_org import Account, Room, RoomPerson, SeedLedger
from app.timeutil import seoul_date

SEED_RULES = {
    "studyDone": 3,  # 하루 학습 완료 (하루 1번)
    "guardianStamp": 2,  # 보호자 도장 (하루 1번, 아이 1명당)
    "teacherMax": 5,  # 학습지도자 칭찬 1번에 최대
    "teacherDailyCap": 10,  # 학습지도자 칭찬 학생 1명 하루 최대
}
STUDY_DONE = "학습 완료"
STAMP = "보호자 도장"
PRAISE = "학습지도자 칭찬"
PURCHASE = "상점 구매"

# (id, kind, name, price) — org.ts COSMETICS 순서 그대로
COSMETICS: list[tuple[str, str, str, int]] = [
    ("glasses", "outfit", "공부 안경", 10),
    ("raincoat", "outfit", "노란 우비", 15),
    ("scarf", "outfit", "겨울 목도리", 20),
    ("cape", "outfit", "별 망토", 25),
    ("thumbs", "emote", "엄지 척", 8),
    ("thanks", "emote", "고마워", 8),
    ("sleepy", "emote", "졸려", 8),
    ("best", "emote", "최고야", 12),
]
ONCE_A_DAY = (STUDY_DONE, STAMP)  # once_key를 붙이는 출처
UNITS_KEY = "units"  # accounts.settings 안 학습지도자 단원 선택(태그 목록)
_TRIAL_OF = re.compile(r"^(t-[a-z0-9]{16})-")


# --- 씨앗 기록 ---------------------------------------------------------------------------


async def balance_of(db: AsyncSession, student_id: str) -> int:
    total = await db.scalar(
        select(func.coalesce(func.sum(SeedLedger.amount), 0)).where(
            SeedLedger.student_account_id == student_id
        )
    )
    return int(total or 0)


async def earned_on(db: AsyncSession, student_id: str, source: str, day: date) -> int:
    """그날 그 출처로 받은 씨앗 합(org.ts earnedOn)."""
    total = await db.scalar(
        select(func.coalesce(func.sum(SeedLedger.amount), 0)).where(
            SeedLedger.student_account_id == student_id,
            SeedLedger.source == source,
            SeedLedger.date == day,
        )
    )
    return int(total or 0)


async def _trial_of(db: AsyncSession, student_id: str) -> str | None:
    """기록의 trial_id: 계정이 있으면 그 계정의 세트, 없으면 체험 아이 id 접미사에서."""
    acc = await db.get(Account, student_id)
    if acc is not None:
        return acc.trial_id
    m = _TRIAL_OF.match(student_id)
    return m.group(1) if m else None


def once_key(student_id: str, source: str, day: date) -> str | None:
    """하루 1번 출처면 유일 키, 아니면 None."""
    return f"{student_id}:{source}:{day.isoformat()}" if source in ONCE_A_DAY else None


async def lock_student(db: AsyncSession, student_id: str) -> None:
    """학생 계정 행을 잠근다(Postgres FOR UPDATE, SQLite는 아무 일 없음).

    같은 학생의 구매·칭찬 요청을 줄 세워, 잔액·상한을 읽고 쓰는 사이에 다른 요청이 끼지 못하게 한다.
    트랜잭션이 끝날 때(커밋·롤백) 풀린다.
    """
    await db.execute(select(Account.id).where(Account.id == student_id).with_for_update())


async def add_seed(
    db: AsyncSession,
    student_id: str,
    amount: int,
    source: str,
    note: str,
    by: str,
    now: datetime,
) -> bool:
    """기록 한 줄(org.ts addSeed). 커밋은 부르는 쪽이 한다.

    하루 1번 출처는 once_key가 이미 있으면 넣지 않고 False. savepoint 안에서 넣어서
    실패해도 같은 요청에서 먼저 한 일은 롤백되지 않는다.
    """
    day = seoul_date(now)
    row = SeedLedger(
        student_account_id=student_id,
        date=day,
        amount=amount,
        source=source,
        note=note[:60],
        by=by,
        trial_id=await _trial_of(db, student_id),
        once_key=once_key(student_id, source, day),
        created_at=now,
    )
    if row.once_key is None:
        db.add(row)
        await db.flush()
        return True
    try:
        async with db.begin_nested():
            db.add(row)
    except IntegrityError:
        return False  # 같은 날 같은 출처가 이미 있다(동시 요청)
    return True


async def earn_study_seeds(db: AsyncSession, student_id: str, unit: str, now: datetime) -> int:
    """하루 학습 완료 → 씨앗(학생·서울 날짜당 한 번). 받은 양을 돌려준다(org.ts earnStudySeeds)."""
    if await earned_on(db, student_id, STUDY_DONE, seoul_date(now)) > 0:
        return 0
    amount = SEED_RULES["studyDone"]
    if not await add_seed(db, student_id, amount, STUDY_DONE, unit, "system", now):
        return 0  # 동시 요청이 먼저 받았다
    return amount


async def in_class(db: AsyncSession, student_id: str) -> bool:
    """강의실 member인지(org.ts roomsOfStudent(id).length > 0)."""
    found = await db.scalar(
        select(RoomPerson.room_id)
        .where(RoomPerson.student_account_id == student_id, RoomPerson.state == "member")
        .limit(1)
    )
    return found is not None


async def teachers_of_student(db: AsyncSession, student_id: str) -> set[str]:
    rows = await db.scalars(
        select(Room.teacher_id)
        .join(RoomPerson, RoomPerson.room_id == Room.id)
        .where(RoomPerson.student_account_id == student_id, RoomPerson.state == "member")
    )
    return set(rows)


def week_days(now: datetime) -> list[date]:
    """이번 주 월~일(서울, org.ts weekKeys)."""
    today = seoul_date(now)
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


# --- 단원 선택(학습지도자) -----------------------------------------------------------------


def selected_tags(account: Account | None) -> list[str]:
    """저장한 선택이 없으면(체험 헤더 강사 포함) 전체 단원이 선택된 것으로 본다."""
    saved = (account.settings or {}).get(UNITS_KEY) if account is not None else None
    if not isinstance(saved, list):
        return list(TAG_NAME)
    return [t for t in TAG_NAME if t in saved]


async def selected_unit_names(db: AsyncSession, actor: Actor) -> list[str]:
    """학습지도자 오늘 화면의 단원 목록(선택한 것만). 계정이 아니면 전체."""
    account = await db.get(Account, actor.id) if actor.allowed is not None else None
    return [TAG_NAME[t] for t in selected_tags(account)]


def save_selected_tags(account: Account, tags: list[str]) -> None:
    """JSON 열은 새 dict를 넣어야 바뀐 것으로 잡힌다."""
    account.settings = {**(account.settings or {}), UNITS_KEY: [t for t in TAG_NAME if t in tags]}
