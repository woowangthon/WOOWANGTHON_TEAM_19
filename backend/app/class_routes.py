"""강의실 수업 진행·공지/숙제 `/api/v1/compat/class-live…`·원장 강의실(명세 4.12 5-4, 재하 시나리오 11-13).

frontend/src/lib/classSession.ts·classBoard.ts가 브라우저에만 두던 것을 서버로 옮긴다.
응답 모양은 그 파일의 ClassSession·ClassDefaults·ClassPost 그대로, 쓰기마다 전체(GET과 같은 모양)를 돌려준다.

- 범위: 원장 = 자기 학원의 강의실 전부, 학습지도자 = 자기가 맡은 강의실, 학생 = 내가 들어간 강의실, 보호자 = 연결된 아이의 강의실.
  학생·보호자 응답의 학생 목록(members·joined·removed·done)은 본인·자기 아이만 남긴다(다른 집 아이 이름 안 보임).
- 쓰기: 강의실 담당 학습지도자 또는 그 학원 원장 / 기본값·장소는 원장 / 수업 참여·숙제 다 했어는 그 강의실 학생.
- 시각은 서버 now(epoch 밀리초). 알림은 프론트가 다시 읽어 띄운다(서버 푸시·외부 발송 없음).
- 로그에는 이름·글 내용을 남기지 않는다.
"""

import datetime as dt
import re
import secrets
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import CurrentAccount, Db, Now, connected_ids, fail, require_account
from app.compat import _CompatRoute
from app.models_org import (
    Academy,
    Account,
    ClassLive,
    ClassLiveSetting,
    ClassPost,
    Room,
    RoomPerson,
)

router = APIRouter(prefix="/compat", route_class=_CompatRoute)

MIN = 60_000
DEFAULTS: dict[str, Any] = {
    "classMin": 50,
    "breakMin": 10,
    "games": True,
    "notifyGuardian": True,
    "showPlace": False,
}
CLASS_LENGTHS = (40, 50, 60)
BREAK_LENGTHS = (5, 10, 15)
TITLE_MAX, BODY_MAX, PLACE_MAX = 40, 300, 20
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _ms(now: datetime) -> int:
    return int(now.timestamp() * 1000)


# --- 범위 ------------------------------------------------------------------------------


class _Scope:
    def __init__(self, academy_id: str | None, rooms: list[Room], visible: set[str] | None):
        self.academy_id = academy_id
        self.rooms = rooms
        self.visible = visible  # None = 모두 보임(학습지도자)


async def _owned_academy(db: AsyncSession, u: Account) -> Academy | None:
    return await db.scalar(
        select(Academy).where(Academy.owner_id == u.id).order_by(Academy.created_at).limit(1)
    )


async def _member_rooms(db: AsyncSession, student_ids: list[str]) -> list[Room]:
    if not student_ids:
        return []
    rows = await db.scalars(
        select(Room)
        .join(RoomPerson, RoomPerson.room_id == Room.id)
        .where(RoomPerson.student_account_id.in_(student_ids), RoomPerson.state == "member")
        .order_by(Room.created_at, Room.id)
    )
    return list(dict.fromkeys(rows))


async def _scope(db: AsyncSession, u: Account) -> _Scope:
    if u.role == "teacher":
        ac = await _owned_academy(db, u)
        academy_id = ac.id if ac else (u.academy_id if u.teacher_status == "승인됨" else None)
        if academy_id is None:
            return _Scope(None, [], None)
        # 원장 = 학원 강의실 전부, 그 밖의 학습지도자 = 자기가 맡은 강의실만(명세 4.12 2 「내 강의실 학생」)
        cond = Room.academy_id == academy_id
        if ac is None:
            cond = cond & (Room.teacher_id == u.id)
        rooms = await db.scalars(select(Room).where(cond).order_by(Room.created_at, Room.id))
        return _Scope(academy_id, list(rooms), None)
    if u.role == "student":
        rooms = await _member_rooms(db, [u.id])
        return _Scope(u.academy_id or (rooms[0].academy_id if rooms else None), rooms, {u.id})
    if u.role == "guardian":
        kids = await connected_ids(db, u)
        rooms = await _member_rooms(db, kids)
        return _Scope(u.academy_id or (rooms[0].academy_id if rooms else None), rooms, set(kids))
    return _Scope(None, [], set())


async def _members(db: AsyncSession, room_id: str) -> list[dict[str, str]]:
    rows = await db.execute(
        select(Account.id, Account.name)
        .join(RoomPerson, RoomPerson.student_account_id == Account.id)
        .where(RoomPerson.room_id == room_id, RoomPerson.state == "member")
        .order_by(RoomPerson.created_at, Account.id)
    )
    return [{"id": i, "name": n} for i, n in rows.all()]


async def _settings(db: AsyncSession, academy_id: str | None) -> ClassLiveSetting | None:
    return await db.get(ClassLiveSetting, academy_id) if academy_id else None


async def _payload(db: AsyncSession, u: Account) -> dict[str, Any]:
    sc = await _scope(db, u)
    see = (
        (lambda ids: ids)
        if sc.visible is None
        else (lambda ids: [i for i in ids if i in sc.visible])
    )  # noqa: E731
    keep = (
        (lambda rows: rows)
        if sc.visible is None
        else (lambda rows: [r for r in rows if r["id"] in sc.visible])
    )  # noqa: E731
    names = {}
    sessions: dict[str, Any] = {}
    posts: list[dict[str, Any]] = []
    room_ids = [r.id for r in sc.rooms]
    for r in sc.rooms:
        members = await _members(db, r.id)
        teacher = await db.get(Account, r.teacher_id)
        names[r.id] = (members, teacher.name if teacher else "알 수 없음")
    lives = (
        await db.scalars(select(ClassLive).where(ClassLive.class_id.in_(room_ids)))
        if room_ids
        else []
    )
    by_name = {}
    for r in sc.rooms:
        by_name.update({m["id"]: m["name"] for m in names[r.id][0]})
    room_name = {r.id: r.name for r in sc.rooms}
    for lv in lives:
        members, teacher_name = names[lv.class_id]
        sessions[lv.class_id] = {
            "classId": lv.class_id,
            "className": room_name[lv.class_id],
            "teacherName": teacher_name,
            "phase": lv.phase,
            "startAt": lv.start_at,
            "endAt": lv.end_at,
            "members": keep(members),
            "joined": keep(
                [
                    {"id": j["id"], "name": by_name.get(j["id"], "학생"), "at": j["at"]}
                    for j in lv.joined or []
                    if j["id"] in by_name
                ]
            ),
            "removed": see(list(lv.removed or [])),
            "closedAt": lv.closed_at,
        }
    rows = (
        await db.scalars(
            select(ClassPost).where(ClassPost.class_id.in_(room_ids)).order_by(ClassPost.at.desc())
        )
        if room_ids
        else []
    )
    for p in rows:
        members, teacher_name = names[p.class_id]
        posts.append(
            {
                "id": p.id,
                "classId": p.class_id,
                "className": room_name[p.class_id],
                "teacherName": teacher_name,
                "kind": p.kind,
                "title": p.title,
                "body": p.body,
                "due": p.due,
                "at": p.at,
                "members": keep(members),
                "done": see(list(p.done or [])),
            }
        )
    st = await _settings(db, sc.academy_id)
    ac = await db.get(Academy, sc.academy_id) if sc.academy_id else None
    # 수업 끝나기 알림 시점 = 학원 설정 timer-alerts(5-3, 기본 10·5분 전) — 성호 11-13
    alerts = [
        int(x)
        for x in ((ac.timer_alerts if ac else None) or "10,5").split(",")
        if x.strip().isdigit()
    ]
    places = {k: v for k, v in ((st.places if st else None) or {}).items() if k in room_name}
    return {
        "sessions": sessions,
        "defaults": {
            **DEFAULTS,
            **((st.defaults if st else None) or {}),
            "alertsMin": alerts or [10, 5],
        },
        "places": places,
        "posts": posts,
    }


@router.get("/class-live")
async def get_class_live(db: Db, account: CurrentAccount) -> dict[str, Any]:
    return await _payload(db, require_account(account))


# --- 학습지도자: 수업 진행 -----------------------------------------------------------------


async def _teach_room(
    db: AsyncSession, account: Account | None, class_id: str
) -> tuple[Account, Room]:
    """그 강의실 담당 학습지도자 또는 그 학원 원장."""
    t = require_account(account, "teacher")
    room = await db.get(Room, class_id)
    if room is not None and room.teacher_id != t.id:
        ac = await _owned_academy(db, t)
        if ac is None or ac.id != room.academy_id:
            room = None
    if room is None:
        fail("강의실을 찾지 못했어요.", 404, "not_found")
    return t, room


async def _live(db: AsyncSession, class_id: str) -> ClassLive:
    lv = await db.get(ClassLive, class_id)
    if lv is None:
        fail("지금 진행 중인 수업이 없어요.", 409, "no_class")
    return lv


def _real_date(s: str) -> bool:
    """「2026-13-45」처럼 모양만 맞는 날짜를 거른다."""
    try:
        dt.date.fromisoformat(s)
    except ValueError:
        return False
    return True


def _minutes(v: int, allowed: tuple[int, ...] | None = None) -> int:
    if type(v) is not int or not 1 <= v <= 180 or (allowed and v not in allowed):
        fail("시간을 다시 골라 주세요.", 422, "invalid_minutes")
    return v


# StrictInt: true가 1로 바뀌어 1분 수업이 되던 것(11-14 이상 입력 점검)
class MinutesIn(BaseModel):
    minutes: StrictInt


class DeltaIn(BaseModel):
    deltaMin: StrictInt


class StudentIdIn(BaseModel):
    studentId: str = Field(min_length=1, max_length=40)


@router.post("/class-live/{class_id}/start")
async def start_class(
    class_id: str, body: MinutesIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t, room = await _teach_room(db, account, class_id)
    n, m = _ms(now), _minutes(body.minutes)
    lv = await db.get(ClassLive, class_id)
    if lv is None:
        lv = ClassLive(
            class_id=class_id, academy_id=room.academy_id, trial_id=room.trial_id, created_at=now
        )
        db.add(lv)
    lv.phase, lv.start_at, lv.end_at, lv.closed_at = "class", n, n + m * MIN, None
    lv.joined, lv.removed = [], []
    await db.commit()
    return await _payload(db, t)


@router.post("/class-live/{class_id}/adjust")
async def adjust_time(
    class_id: str, body: DeltaIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t, _ = await _teach_room(db, account, class_id)
    if type(body.deltaMin) is not int or not -60 <= body.deltaMin <= 60:
        fail("시간을 다시 골라 주세요.", 422, "invalid_minutes")
    lv = await _live(db, class_id)
    lv.end_at = max(_ms(now) + MIN, lv.end_at + body.deltaMin * MIN)  # 줄여도 1분은 남긴다
    await db.commit()
    return await _payload(db, t)


@router.post("/class-live/{class_id}/break")
async def give_break(
    class_id: str, body: MinutesIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t, _ = await _teach_room(db, account, class_id)
    lv, n = await _live(db, class_id), _ms(now)
    lv.phase, lv.start_at, lv.end_at = "break", n, n + _minutes(body.minutes) * MIN
    await db.commit()
    return await _payload(db, t)


@router.post("/class-live/{class_id}/resume")
async def resume_class(
    class_id: str, body: MinutesIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t, _ = await _teach_room(db, account, class_id)
    lv, n = await _live(db, class_id), _ms(now)
    lv.phase, lv.start_at, lv.end_at = "class", n, n + _minutes(body.minutes) * MIN
    await db.commit()
    return await _payload(db, t)


@router.post("/class-live/{class_id}/end")
async def end_class(class_id: str, db: Db, now: Now, account: CurrentAccount) -> dict[str, Any]:
    t, _ = await _teach_room(db, account, class_id)
    lv, n = await _live(db, class_id), _ms(now)
    lv.end_at, lv.closed_at = min(lv.end_at, n), n
    await db.commit()
    return await _payload(db, t)


@router.post("/class-live/{class_id}/remove")
async def remove_joined(
    class_id: str, body: StudentIdIn, db: Db, account: CurrentAccount
) -> dict[str, Any]:
    t, _ = await _teach_room(db, account, class_id)
    lv = await _live(db, class_id)
    # 이 강의실 학생(또는 참여 중인 아이)만 뺄 수 있다 — 아무 문자열이 removed에 쌓이던 것
    known = {m["id"] for m in await _members(db, class_id)} | {j["id"] for j in lv.joined or []}
    if body.studentId not in known:
        fail("이 강의실 학생이 아니에요.", 404, "student_not_found")
    lv.joined = [j for j in lv.joined or [] if j["id"] != body.studentId]
    lv.removed = list(dict.fromkeys([*(lv.removed or []), body.studentId]))
    await db.commit()
    return await _payload(db, t)


# --- 학생: 수업 참여 -----------------------------------------------------------------------


async def _my_class(db: AsyncSession, account: Account | None, class_id: str) -> Account:
    s = require_account(account, "student")
    rp = await db.get(RoomPerson, (class_id, s.id))
    if rp is None or rp.state != "member":
        fail("강의실을 찾지 못했어요.", 404, "not_found")
    return s


@router.post("/class-live/{class_id}/join")
async def join_class(class_id: str, db: Db, now: Now, account: CurrentAccount) -> dict[str, Any]:
    s = await _my_class(db, account, class_id)
    lv = await _live(db, class_id)
    if lv.closed_at is not None:
        fail("수업이 이미 끝났어.", 409, "class_closed")
    if not any(j["id"] == s.id for j in lv.joined or []):
        lv.joined = [*(lv.joined or []), {"id": s.id, "at": _ms(now)}]
        lv.removed = [x for x in lv.removed or [] if x != s.id]
        await db.commit()
    return await _payload(db, s)


# --- 원장: 기본값·장소 ---------------------------------------------------------------------


async def _must_owner(db: AsyncSession, account: Account | None) -> tuple[Account, Academy]:
    u = require_account(account, "teacher")
    ac = await _owned_academy(db, u)
    if ac is None:
        fail("학원·학교 관리자(원장)만 쓸 수 있어요.", 403, "forbidden")
    return u, ac


async def _setting_row(db: AsyncSession, ac: Academy, now: datetime) -> ClassLiveSetting:
    st = await db.get(ClassLiveSetting, ac.id)
    if st is None:
        st = ClassLiveSetting(
            academy_id=ac.id, defaults={}, places={}, trial_id=ac.trial_id, created_at=now
        )
        db.add(st)
    return st


class DefaultsIn(BaseModel):
    classMin: int
    breakMin: int
    games: bool
    notifyGuardian: bool
    showPlace: bool


@router.put("/class-live/defaults")
async def save_defaults(
    body: DefaultsIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    o, ac = await _must_owner(db, account)
    _minutes(body.classMin, CLASS_LENGTHS)
    _minutes(body.breakMin, BREAK_LENGTHS)
    st = await _setting_row(db, ac, now)
    st.defaults = body.model_dump()
    await db.commit()
    return await _payload(db, o)


class PlaceIn(BaseModel):
    place: str


@router.put("/class-live/{class_id}/place")
async def save_place(
    class_id: str, body: PlaceIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    o, ac = await _must_owner(db, account)
    room = await db.get(Room, class_id)
    if room is None or room.academy_id != ac.id:
        fail("강의실을 찾지 못했어요.", 404, "not_found")
    st = await _setting_row(db, ac, now)
    places = dict(st.places or {})
    v = body.place.strip()[:PLACE_MAX]
    if v:
        places[class_id] = v
    else:
        places.pop(class_id, None)
    st.places = places
    await db.commit()
    return await _payload(db, o)


# --- 공지·숙제 -----------------------------------------------------------------------------


class PostIn(BaseModel):
    kind: Literal["notice", "homework"]
    title: str
    body: str = ""
    due: str | None = None


@router.post("/class-live/{class_id}/posts")
async def add_post(
    class_id: str, body: PostIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t, room = await _teach_room(db, account, class_id)
    title = body.title.strip()[:TITLE_MAX]
    if not title:
        fail("제목을 적어 주세요.", 422)
    if body.kind == "homework" and not (
        body.due and _DATE.match(body.due) and _real_date(body.due)
    ):
        fail("숙제 마감일을 골라 주세요.", 422)
    db.add(
        ClassPost(
            id=f"p-{secrets.token_hex(8)}",
            class_id=class_id,
            academy_id=room.academy_id,
            kind=body.kind,
            title=title,
            body=body.body.strip()[:BODY_MAX],
            due=body.due if body.kind == "homework" else None,
            at=_ms(now),
            done=[],
            trial_id=room.trial_id,
            created_at=now,
        )
    )
    await db.commit()
    return await _payload(db, t)


@router.delete("/class-live/posts/{post_id}")
async def remove_post(post_id: str, db: Db, account: CurrentAccount) -> dict[str, Any]:
    p = await db.get(ClassPost, post_id)
    if p is None:
        fail("글을 찾지 못했어요.", 404, "not_found")
    t, _ = await _teach_room(db, account, p.class_id)
    await db.delete(p)
    await db.commit()
    return await _payload(db, t)


@router.post("/class-live/posts/{post_id}/done")
async def toggle_done(post_id: str, db: Db, account: CurrentAccount) -> dict[str, Any]:
    p = await db.get(ClassPost, post_id)
    if p is None:
        require_account(account, "student")
        fail("글을 찾지 못했어요.", 404, "not_found")
    s = await _my_class(db, account, p.class_id)
    done = list(p.done or [])
    p.done = [x for x in done if x != s.id] if s.id in done else [*done, s.id]
    await db.commit()
    return await _payload(db, s)


# --- 탈퇴(TK-107) -------------------------------------------------------------------------


async def scrub_student(db: AsyncSession, student_id: str) -> None:
    """탈퇴한 학생을 수업 참여·뺀 목록·숙제 다 했어에서 뺀다(그 학생이 남지 않게)."""
    for lv in await db.scalars(select(ClassLive)):
        if any(j["id"] == student_id for j in lv.joined or []) or student_id in (lv.removed or []):
            lv.joined = [j for j in lv.joined or [] if j["id"] != student_id]
            lv.removed = [x for x in lv.removed or [] if x != student_id]
    for p in await db.scalars(select(ClassPost)):
        if student_id in (p.done or []):
            p.done = [x for x in p.done if x != student_id]
