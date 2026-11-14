"""연결·학원·소속·원장·운영자·강의실 API `/api/v1/compat`(명세 4.12, 설계 1112 §9·§10).

frontend/src/api/http.ts 경로·본문 그대로, 규칙·문구는 frontend/src/api/org.ts의 fail() 그대로,
응답 모양은 types.ts(Me·OwnerDashboard·AcademyApplication[]·TeacherClasses·StudentClasses).

- 코드·일련번호(연결 코드·학원 일련번호·입장 코드)로 찾을 때는 영역(realm = trial_id)이 같은 행만 찾는다
  (accounts.same_realm). 실제 가입(None)은 실제 행만, 체험 세상은 자기 세트 행만(보안 검토 11-12).
- id로 찾는 것은 반드시 「내 것」 조건과 함께 찾는다(내 강의실·내 학원·나와의 연결·운영자 범위).
  → 다른 체험 세상의 행에 id만으로 닿지 않는다.
- 운영자 심사 범위(설계 §9-1): 신청서 trial_id = 신청한 강사의 trial_id, 없으면 신청 요청의 X-Trial-Id.
  운영자는 자기 trial_id와 같은 신청서만 본다. 실제 강사(가입은 언제나 trial_id None)가 화면에서 신청하면
  그 화면의 세트로 묶여 그 세트 운영자가 심사한다 — 실제 운영자가 없으니 이 「스스로 심사」가 의도한
  시연 흐름이다. 승인으로 생기는 학원은 신청서가 아니라 원장 계정의 영역을 따른다(실제 강사 → 실제 학원).
- 로그에는 아이디·이름·코드를 남기지 않는다.
"""

import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import (
    CurrentAccount,
    Db,
    Now,
    application_view,
    connected_ids,
    fail,
    is_restricted,
    me_view,
    notify,
    require_account,
    same_realm,
    trial_id_from,
    unique_serial,
)
from app.compat import _CompatRoute
from app.models import Student
from app.models_org import Academy, AcademyApplication, Account, Link, Room, RoomPerson
from app.timeutil import as_utc, current_grade, get_now, seoul_date

router = APIRouter(prefix="/compat", route_class=_CompatRoute)

ENTRY_CODE_MIN = 10  # org.ts SEED_RULES.entryCodeMin(입장 코드 유효 시간, 분)


# --- 도우미 ----------------------------------------------------------------------------


def _norm(code: str) -> str:
    """org.ts norm: 공백·하이픈 빼고 대문자."""
    return "".join(ch for ch in code if not ch.isspace() and ch != "-").upper()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(8)}"


def grade_label(grade: int | None) -> str:
    """lib/grade.ts gradeLabel: 4 → 초4, 7 → 중1, 10 → 고1, 없으면 -."""
    if not grade:
        return "-"
    if grade <= 6:
        return f"초{grade}"
    if grade <= 9:
        return f"중{grade - 6}"
    return f"고{grade - 9}"


async def _name(db: AsyncSession, account_id: str) -> str:
    acc = await db.get(Account, account_id)
    return acc.name if acc is not None else "알 수 없음"


async def _row(db: AsyncSession, account_id: str, sub: str | None = None) -> dict[str, Any]:
    """types.ts PersonRow(sub는 있을 때만)."""
    out: dict[str, Any] = {"id": account_id, "name": await _name(db, account_id)}
    if sub is not None:
        out["sub"] = sub
    return out


async def kid_or_adult_text(db: AsyncSession, account_id: str, banmal: str, polite: str) -> str:
    """알림 말투(명세 4.12, 11-14 UT2): 학생이면 고른 반말/존댓말, 보호자·학습지도자는 존댓말."""
    acc = await db.get(Account, account_id)
    if acc is None or acc.role != "student":
        return polite
    student = await db.get(Student, acc.student_id or account_id)
    return polite if student is not None and student.polite else banmal


async def _notify_id(db: AsyncSession, account_id: str, text: str, to: str | None, now: datetime):
    """id로 알림. 계정이 없으면(탈퇴) 건너뛴다. 알림 trial_id는 받는 사람 것."""
    acc = await db.get(Account, account_id)
    if acc is not None:
        notify(db, acc, text, to, now=now)


async def _owned_academy(db: AsyncSession, u: Account) -> Academy | None:
    return await db.scalar(
        select(Academy).where(Academy.owner_id == u.id).order_by(Academy.created_at).limit(1)
    )


async def _must_owner(db: AsyncSession, account: Account | None) -> tuple[Account, Academy]:
    """원장 = 자기가 등록해 승인받은 학원·학교가 있는 학습지도자."""
    u = require_account(account, "teacher")
    ac = await _owned_academy(db, u)
    if ac is None:
        fail("학원·학교 관리자(원장)만 쓸 수 있어요.", 403, "forbidden")
    return u, ac


async def _rooms_of_teacher(db: AsyncSession, teacher_id: str) -> list[Room]:
    rows = await db.scalars(
        select(Room).where(Room.teacher_id == teacher_id).order_by(Room.created_at, Room.id)
    )
    return list(rows)


async def _room_ids_of_student(db: AsyncSession, student_id: str) -> list[str]:
    rows = await db.scalars(
        select(RoomPerson.room_id).where(
            RoomPerson.student_account_id == student_id, RoomPerson.state == "member"
        )
    )
    return list(rows)


async def _people(db: AsyncSession, room_id: str, state: str) -> list[str]:
    rows = await db.scalars(
        select(RoomPerson.student_account_id)
        .where(RoomPerson.room_id == room_id, RoomPerson.state == state)
        .order_by(RoomPerson.created_at, RoomPerson.student_account_id)
    )
    return list(rows)


async def _place(db: AsyncSession, room_id: str, student_id: str) -> RoomPerson | None:
    return await db.get(RoomPerson, (room_id, student_id))


async def _connected(db: AsyncSession, u: Account) -> list[Account]:
    out = []
    for pid in await connected_ids(db, u):
        acc = await db.get(Account, pid)
        if acc is not None:
            out.append(acc)
    return out


# --- 학원 자동 등록(org.ts enrollLinked·spreadFromStudent·spreadFromGuardian·syncLinkedPair) ---
# 연결된 한 쌍(학생 ↔ 보호자)까지만. 보호자를 거쳐 형제로 넘어가지 않는다.
# 보호자 → 아이는 연결된 아이가 딱 1명일 때만. 대상이 이미 다른 학원이면 덮어쓰지 않고 둘 다에게 알림.
# 한계(org.ts와 같음): Account.academy_id가 하나라 보호자는 학원 1곳에만 속한다.


async def _academy_name(db: AsyncSession, academy_id: str) -> str:
    ac = await db.get(Academy, academy_id)
    return ac.name if ac is not None else "다른 학원"


def _say(u: Account, kid: str, adult: str) -> str:
    """학생에겐 반말, 어른에겐 존댓말."""
    return kid if u.role == "student" else adult


async def _enroll_linked(
    db: AsyncSession, target: Account, academy_id: str, starter: Account, now: datetime
) -> None:
    if target.academy_id == academy_id:
        return
    if not target.academy_id:
        target.academy_id = academy_id
        return
    have, want = await _academy_name(db, target.academy_id), await _academy_name(db, academy_id)
    notify(
        db,
        target,
        _say(
            target,
            f"이미 「{have}」에 등록되어 있어서 「{want}」에 자동으로 옮기지 않았어.",
            f"이미 「{have}」에 등록되어 있어 「{want}」에 자동으로 옮기지 않았어요.",
        ),
        now=now,
    )
    who = f"아이 {target.name}은(는)" if target.role == "student" else f"보호자 {target.name}님은"
    notify(
        db,
        starter,
        _say(
            starter,
            f"{who} 이미 「{have}」에 등록되어 있어서 「{want}」에 자동으로 옮기지 않았어.",
            f"{who} 이미 「{have}」에 등록되어 있어 「{want}」에 자동으로 옮기지 않았어요.",
        ),
        now=now,
    )


async def _spread_from_student(
    db: AsyncSession, s: Account, academy_id: str, now: datetime
) -> None:
    for g in await _connected(db, s):
        if g.role == "guardian":
            await _enroll_linked(db, g, academy_id, s, now)


async def _spread_from_guardian(
    db: AsyncSession, g: Account, academy_id: str, now: datetime
) -> None:
    kids = [k for k in await _connected(db, g) if k.role == "student"]
    if len(kids) == 1:
        await _enroll_linked(db, kids[0], academy_id, g, now)
    elif any(k.academy_id != academy_id for k in kids):
        notify(
            db,
            g,
            "아이가 여러 명이라 아이들의 학원은 자동으로 등록하지 않았어요. "
            "아이마다 아이 계정에서 학원 코드를 넣어 주세요.",
            "/settings/family",
            now=now,
        )


async def _sync_linked_pair(db: AsyncSession, s: Account, g: Account, now: datetime) -> None:
    await db.flush()  # 방금 바꾼 연결이 connected_ids에 보이게
    if s.academy_id:
        await _enroll_linked(db, g, s.academy_id, s, now)
    elif g.academy_id:
        await _spread_from_guardian(db, g, g.academy_id, now)


# --- 학생 ⇄ 보호자 연결 ----------------------------------------------------------------


class LinkIn(BaseModel):
    code: str
    consent: bool = False


@router.post("/links")
async def link_with(body: LinkIn, db: Db, now: Now, account: CurrentAccount) -> dict[str, Any]:
    """상대 코드로 연결. 보호자가 하면 동의와 함께 바로 연결, 학생이 하면 보호자 동의 대기."""
    me = require_account(account, "student", "guardian")
    other = await db.scalar(
        select(Account).where(
            Account.link_code == _norm(body.code), same_realm(Account.trial_id, me.trial_id)
        )
    )
    if other is None:
        fail("코드를 찾지 못했어요. 6자리를 다시 확인해 주세요.", 404, "not_found")
    if other.id == me.id:
        fail("내 코드는 넣을 수 없어요.", 422)
    if other.role == me.role or other.role not in ("student", "guardian"):
        fail(
            "보호자의 코드를 넣어 주세요."
            if me.role == "student"
            else "아이의 코드를 넣어 주세요.",
            422,
        )
    student_id = me.id if me.role == "student" else other.id
    guardian_id = me.id if me.role == "guardian" else other.id
    ex = await db.get(Link, (student_id, guardian_id))
    if ex is not None and ex.status == "연결됨":
        fail("이미 연결되어 있어요.", 409, "already_linked")
    today = seoul_date(now)
    if me.role == "guardian":
        if not body.consent:
            fail(
                "만 14세 미만 아이는 보호자 동의가 있어야 연결할 수 있어요.",
                422,
                "consent_required",
            )
        if ex is not None:
            ex.status, ex.consent_at = "연결됨", today
        else:
            db.add(
                Link(
                    student_account_id=student_id,
                    guardian_account_id=guardian_id,
                    status="연결됨",
                    consent_at=today,
                    trial_id=me.trial_id,
                    created_at=now,
                )
            )
        await _sync_linked_pair(db, other, me, now)
        text = await kid_or_adult_text(
            db, other.id, f"{me.name}님과 연결됐어!", f"{me.name}님과 연결됐어요!"
        )
        notify(db, other, text, now=now)
    elif ex is None:
        db.add(
            Link(
                student_account_id=student_id,
                guardian_account_id=guardian_id,
                status="대기",
                consent_at=None,
                trial_id=me.trial_id,
                created_at=now,
            )
        )
        notify(
            db,
            other,
            f"{me.name} 학생이 연결을 요청했어요. 동의하면 연결돼요.",
            "/settings/family",
            now=now,
        )
    await db.commit()
    return await me_view(db, me)


class ConsentIn(BaseModel):
    consent: bool = False


@router.post("/links/{student_id}/confirm")
async def confirm_link(
    student_id: str, body: ConsentIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    """보호자: 학생이 보낸 연결 요청을 동의와 함께 수락. 나에게 온 대기 요청만 찾는다."""
    g = require_account(account, "guardian")
    if not body.consent:
        fail("보호자 동의에 체크해 주세요.", 422, "consent_required")
    link = await db.get(Link, (student_id, g.id))
    s = await db.get(Account, student_id)
    if link is None or link.status != "대기" or s is None:
        fail("연결 요청을 찾지 못했어요.", 404, "not_found")
    link.status, link.consent_at = "연결됨", seoul_date(now)
    text = await kid_or_adult_text(
        db,
        s.id,
        f"{g.name}님이 동의해서 연결됐어! 이제 학원에 들어갈 수 있어.",
        f"{g.name}님이 동의해서 연결됐어요! 이제 학원에 들어갈 수 있어요.",
    )
    notify(db, s, text, now=now)
    await _sync_linked_pair(db, s, g, now)
    await db.commit()
    return await me_view(db, g)


# --- 학원 입장(학생·보호자, 원장이 준 6자리) -------------------------------------------


class CodeIn(BaseModel):
    code: str


@router.post("/academy/join")
async def join_academy(
    body: CodeIn, request: Request, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    me = require_account(account, "student", "guardian")
    if me.role == "student" and await is_restricted(db, me.id):
        fail("보호자와 먼저 연결해야 학원에 들어갈 수 있어요.", 403, "restricted")
    if me.academy_id:
        fail("이미 학원에 등록되어 있어요.", 409)
    code = "".join(ch for ch in body.code if ch.isdigit())
    # 영역: 자기 영역 학원. 실제 가입 계정은 「이 브라우저의 체험 세트(X-Trial-Id)」 학원도 — 심사위원이
    # 새로 가입한 아이도 체험 학원 코드로 들어가 공부까지 가게(성호 11-12). 계정 영역은 그대로(None),
    # 연결 코드·일련번호는 여전히 같은 영역끼리만. 다른 세트·헤더 없음은 404.
    realm = same_realm(Academy.trial_id, me.trial_id)
    browser_trial = trial_id_from(request) if me.trial_id is None else None
    if browser_trial is not None:
        realm = or_(realm, Academy.trial_id == browser_trial)
    # 같은 숫자가 다른 학원의 지난 코드로 남아 있을 수 있어 가장 늦게 끝나는 것을 고른다
    ac = (
        await db.scalar(
            select(Academy)
            .where(Academy.entry_code == code, realm)
            .order_by(Academy.entry_expires_at.desc())
            .limit(1)
        )
        if code
        else None
    )
    if ac is None:
        fail("코드가 맞지 않아요. 학원에서 받은 6자리를 확인해 주세요.", 404, "not_found")
    expires = as_utc(ac.entry_expires_at)
    if expires is None or expires < now:
        fail("코드 시간이 지났어요. 학원에 새 코드를 요청해 주세요.", 410, "code_expired")
    me.academy_id = ac.id
    if me.role == "student":
        await _spread_from_student(db, me, ac.id, now)
    else:
        await _spread_from_guardian(db, me, ac.id, now)
    await db.commit()
    return await me_view(db, me)


# --- 학습지도자: 소속 -----------------------------------------------------------------


class SerialIn(BaseModel):
    serial: str


@router.post("/teacher/membership")
async def request_membership(
    body: SerialIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    """일련번호로 학원·학교 소속 신청 → 원장 승인 대기."""
    t = require_account(account, "teacher")
    if t.academy_id and t.teacher_status == "승인됨":
        fail("이미 소속이 있어요. 옮기려면 지금 소속을 먼저 나가 주세요.", 409)
    raw = _norm(body.serial)
    serial = f"{raw[:4]}-{raw[4:]}" if len(raw) == 8 else raw
    ac = await db.scalar(
        select(Academy).where(Academy.serial == serial, same_realm(Academy.trial_id, t.trial_id))
    )
    if ac is None:
        fail("일련번호를 찾지 못했어요. 원장님께 다시 확인해 주세요.", 404, "not_found")
    t.academy_id, t.teacher_status = ac.id, "승인 대기"
    await _notify_id(db, ac.owner_id, f"{t.name}님이 소속을 신청했어요", "/owner", now)
    await db.commit()
    return await me_view(db, t)


@router.delete("/teacher/membership")
async def leave_membership(db: Db, account: CurrentAccount) -> dict[str, Any]:
    t = require_account(account, "teacher")
    if await _owned_academy(db, t) is not None:
        fail("원장은 소속을 나갈 수 없어요(운영자 문의).", 409)
    if t.teacher_status == "승인됨" and await _rooms_of_teacher(db, t.id):
        fail("내 강의실이 남아 있어요. 강의실을 정리한 뒤 나갈 수 있어요.", 409)
    t.academy_id, t.teacher_status = None, None
    await db.commit()
    return await me_view(db, t)


class AcademyFormIn(BaseModel):
    orgType: Literal["학원", "학교"]
    academyName: str
    bizNo: str = ""
    ceo: str = ""
    phone: str = ""
    address: str = ""


_BIZ_NO = re.compile(r"^\d{3}-?\d{2}-?\d{5}$")


@router.post("/teacher/academy-applications")
async def apply_academy(
    body: AcademyFormIn, request: Request, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    """학원·학교 등록 신청 → 운영자 심사 → 승인되면 신청한 학습지도자가 원장."""
    t = require_account(account, "teacher")
    if t.academy_id and t.teacher_status == "승인됨":
        fail("이미 소속이 있어요. 새 학원을 등록하려면 지금 소속을 먼저 나가 주세요.", 409)
    prev = await db.get(AcademyApplication, t.application_id) if t.application_id else None
    if prev is not None and prev.status == "심사 중":
        # 가입 강사의 신청은 화면 세트 운영자가 심사한다. 세트가 바뀌면 새 세트로 옮겨
        # 영영 심사 중에 갇히지 않게 한다(11-12 A7). 체험 강사·같은 세트는 그대로 409.
        current = trial_id_from(request)
        if t.trial_id is None and current is not None and prev.trial_id != current:
            prev.trial_id = current
            await db.commit()
            return await me_view(db, t)
        fail("이미 심사 중인 신청이 있어요.", 409)
    if not body.academyName.strip():
        fail("이름을 적어 주세요.", 422)
    if body.orgType == "학원" and not _BIZ_NO.match(body.bizNo.strip()):
        fail("사업자등록번호는 숫자 10자리예요 (예: 123-45-67890).", 422)
    if not body.ceo.strip() or not body.phone.strip():
        fail("대표자와 연락처를 적어 주세요.", 422)
    app = AcademyApplication(
        id=_new_id("app"),
        owner_id=t.id,
        owner_name=t.name,
        org_type=body.orgType,
        academy_name=body.academyName.strip()[:60],
        biz_no=body.bizNo[:20],
        ceo=body.ceo[:40],
        phone=body.phone[:30],
        address=body.address[:120],
        status="심사 중",
        applied_at=now,
        serial=None,
        reject_reason=None,
        # 심사 범위: 강사의 세트, 없으면(실제 강사) 지금 화면의 세트(설계 §9-1). 실제 운영자가 없어
        # 실제 강사도 그 세트 운영자 계정으로 스스로 심사하는 것이 의도한 시연 흐름이다.
        trial_id=t.trial_id or trial_id_from(request),
        created_at=now,
    )
    db.add(app)
    t.application_id = app.id
    await db.commit()
    return await me_view(db, t)


# --- 원장(학원·학교 관리자) -----------------------------------------------------------


async def _owner_dash(db: AsyncSession, o: Account, ac: Academy, now: datetime) -> dict[str, Any]:
    in_ac = list(
        await db.scalars(
            select(Account)
            .where(Account.academy_id == ac.id)
            .order_by(Account.created_at, Account.id)
        )
    )
    expires = as_utc(ac.entry_expires_at)
    entry = (
        {"code": ac.entry_code, "expiresAt": int(expires.timestamp() * 1000)}
        if ac.entry_code and expires is not None and expires > now
        else None
    )
    teachers = []
    for u in in_ac:
        if u.role == "teacher" and u.teacher_status == "승인됨":
            n = len(await _rooms_of_teacher(db, u.id))
            teachers.append(
                await _row(db, u.id, f"{'원장 · ' if u.id == o.id else ''}강의실 {n}개")
            )
    rooms = list(
        await db.scalars(
            select(Room).where(Room.academy_id == ac.id).order_by(Room.created_at, Room.id)
        )
    )
    room_name = {r.id: r.name for r in rooms}
    classrooms = [
        {
            "id": r.id,
            "name": r.name,
            "teacherName": await _name(db, r.teacher_id),
            "teacherId": r.teacher_id,
            "count": len(await _people(db, r.id, "member")),
        }
        for r in rooms
    ]
    students = []
    for u in in_ac:
        if u.role == "student":
            names = []
            for rid in await _room_ids_of_student(db, u.id):
                if rid in room_name:
                    names.append(room_name[rid])
                else:
                    other = await db.get(Room, rid)
                    if other is not None:
                        names.append(other.name)
            sub = f"{grade_label(current_grade(u.grade, u.created_at, get_now()))} · {', '.join(names) or '강의실 없음'}"
            students.append(await _row(db, u.id, sub))
    return {
        "academy": {"id": ac.id, "name": ac.name, "serial": ac.serial, "orgType": ac.org_type},
        "entryCode": entry,
        "pendingTeachers": [
            await _row(db, u.id, "소속 신청")
            for u in in_ac
            if u.role == "teacher" and u.teacher_status == "승인 대기"
        ],
        "teachers": teachers,
        "classrooms": classrooms,
        "students": students,
    }


@router.get("/owner/dashboard")
async def get_owner_dashboard(db: Db, now: Now, account: CurrentAccount) -> dict[str, Any]:
    o, ac = await _must_owner(db, account)
    return await _owner_dash(db, o, ac, now)


class OwnerRoomIn(BaseModel):
    name: str
    plan: str = ""
    teacherId: str


class TeacherIdIn(BaseModel):
    teacherId: str


async def _academy_teacher(db: AsyncSession, ac: Academy, teacher_id: str) -> Account:
    t = await db.get(Account, teacher_id)
    if t is None or t.role != "teacher" or t.academy_id != ac.id or t.teacher_status != "승인됨":
        fail("우리 학원 학습지도자를 골라 주세요.", 422)
    return t


@router.post("/owner/classrooms")
async def owner_create_classroom(
    body: OwnerRoomIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    """원장이 강의실을 만들고 담당 학습지도자를 정한다(명세 4.12 5-4, org.ts ownerCreateClassroom)."""
    o, ac = await _must_owner(db, account)
    name = body.name.strip()
    if not name:
        fail("강의실 이름을 적어 주세요.", 422)
    t = await _academy_teacher(db, ac, body.teacherId)
    db.add(
        Room(
            id=_new_id("c"),
            academy_id=ac.id,
            teacher_id=t.id,
            name=name[:60],
            plan=body.plan.strip()[:120],
            trial_id=ac.trial_id,
            created_at=now,
        )
    )
    if t.id != o.id:
        notify(db, t, f"「{name[:60]}」 강의실을 맡게 됐어요", "/teacher/classes", now=now)
    await db.commit()
    return await _owner_dash(db, o, ac, now)


@router.put("/owner/classrooms/{class_id}/teacher")
async def owner_set_teacher(
    class_id: str, body: TeacherIdIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    o, ac = await _must_owner(db, account)
    room = await db.get(Room, class_id)
    if room is None or room.academy_id != ac.id:
        fail("강의실을 찾지 못했어요.", 404, "not_found")
    t = await _academy_teacher(db, ac, body.teacherId)
    if room.teacher_id != t.id:
        room.teacher_id = t.id
        if t.id != o.id:
            notify(db, t, f"「{room.name}」 강의실을 맡게 됐어요", "/teacher/classes", now=now)
    await db.commit()
    return await _owner_dash(db, o, ac, now)


@router.post("/owner/entry-code")
async def issue_entry_code(db: Db, now: Now, account: CurrentAccount) -> dict[str, Any]:
    """6자리 숫자, 10분. 입장 코드는 전역으로 찾으니 지금 살아 있는 다른 코드와 겹치지 않게 뽑는다."""
    o, ac = await _must_owner(db, account)
    while True:
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        clash = await db.scalar(
            select(Academy.id).where(
                Academy.entry_code == code, Academy.entry_expires_at > now, Academy.id != ac.id
            )
        )
        if clash is None:
            break
    ac.entry_code, ac.entry_expires_at = code, now + timedelta(minutes=ENTRY_CODE_MIN)
    await db.commit()
    return await _owner_dash(db, o, ac, now)


class IdsIn(BaseModel):
    ids: list[str]


@router.post("/owner/teachers/approve")
async def approve_teachers(
    body: IdsIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    """내 학원에 소속 신청한 학습지도자만 승인(다른 id는 조용히 건너뛴다, org.ts 그대로)."""
    o, ac = await _must_owner(db, account)
    for tid in body.ids[:100]:
        t = await db.get(Account, tid)
        if (
            t is not None
            and t.role == "teacher"
            and t.academy_id == ac.id
            and t.teacher_status == "승인 대기"
        ):
            t.teacher_status = "승인됨"
            notify(
                db,
                t,
                f"{ac.name} 소속이 승인됐어요. 이제 강의실을 열 수 있어요.",
                "/teacher/classes",
                now=now,
            )
    await db.commit()
    return await _owner_dash(db, o, ac, now)


# --- 운영자: 학원 등록 심사 ------------------------------------------------------------


def _in_scope(op: Account, app: AcademyApplication) -> bool:
    """운영자 범위 = 자기 세트 신청서(세트 계정 + 그 세트에서 가입·신청한 사람)."""
    return app.trial_id == op.trial_id


async def _applications(db: AsyncSession, op: Account) -> list[dict[str, Any]]:
    cond = same_realm(AcademyApplication.trial_id, op.trial_id)
    rows = list(
        await db.scalars(
            select(AcademyApplication)
            .where(cond)
            .order_by(AcademyApplication.created_at, AcademyApplication.id)
        )
    )
    rows.sort(key=lambda a: 0 if a.status == "심사 중" else 1)  # 심사 중 먼저(안정 정렬)
    return [application_view(a) for a in rows]


@router.get("/operator/applications")
async def get_applications(db: Db, account: CurrentAccount) -> list[dict[str, Any]]:
    op = require_account(account, "operator")
    return await _applications(db, op)


class ReviewIn(BaseModel):
    decision: Literal["승인", "반려"]
    reason: str = ""


@router.post("/operator/applications/{app_id}/review")
async def review_application(
    app_id: str, body: ReviewIn, db: Db, now: Now, account: CurrentAccount
) -> list[dict[str, Any]]:
    op = require_account(account, "operator")
    app = await db.get(AcademyApplication, app_id)
    if app is None or not _in_scope(op, app):
        fail("신청서를 찾지 못했어요.", 404, "not_found")
    if app.status != "심사 중":
        fail("이미 처리한 신청이에요.", 409)
    if body.decision == "반려":
        reason = (body.reason or "").strip()
        if not reason:
            fail("반려 사유를 적어 주세요.", 422)
        app.status, app.reject_reason = "반려", reason
        await _notify_id(
            db,
            app.owner_id,
            f"{app.academy_name} 등록이 반려됐어요: {reason}",
            "/settings/org",
            now,
        )
    else:
        app.status, app.serial = "승인", await unique_serial(db)
        owner = await db.get(Account, app.owner_id)
        academy = Academy(
            id=_new_id("ac"),
            name=app.academy_name,
            org_type=app.org_type,
            serial=app.serial,
            owner_id=app.owner_id,
            entry_code=None,
            entry_expires_at=None,
            # 학원 영역 = 원장 계정 영역(신청서 영역 아님): 실제 강사를 체험 세트 운영자가 승인해도
            # 학원은 실제 학원이라 실제 학생·강사만 코드로 닿는다
            trial_id=owner.trial_id if owner is not None else app.trial_id,
            created_at=now,
        )
        db.add(academy)
        if owner is not None:
            owner.academy_id, owner.teacher_status = academy.id, "승인됨"
        await _notify_id(
            db,
            app.owner_id,
            f"{app.academy_name} 등록이 승인됐어요. 일련번호 {app.serial}",
            "/owner",
            now,
        )
    await db.commit()
    return await _applications(db, op)


# --- 학습지도자: 강의실 ---------------------------------------------------------------


async def _classroom_view(db: AsyncSession, r: Room) -> dict[str, Any]:
    return {
        "id": r.id,
        "name": r.name,
        "plan": r.plan,
        "teacherName": await _name(db, r.teacher_id),
        "members": [await _row(db, i) for i in await _people(db, r.id, "member")],
        "invited": [await _row(db, i) for i in await _people(db, r.id, "invited")],
        "requests": [await _row(db, i) for i in await _people(db, r.id, "requested")],
    }


async def _teacher_classes(db: AsyncSession, t: Account) -> dict[str, Any]:
    rooms = await _rooms_of_teacher(db, t.id)
    in_any = {sid for r in rooms for sid in await _people(db, r.id, "member")}
    academy_students: list[dict[str, Any]] = []
    if t.teacher_status == "승인됨" and t.academy_id:
        studs = await db.scalars(
            select(Account)
            .where(Account.role == "student", Account.academy_id == t.academy_id)
            .order_by(Account.created_at, Account.id)
        )
        academy_students = [
            {
                "id": u.id,
                "name": u.name,
                "sub": "내 강의실"
                if u.id in in_any
                else grade_label(current_grade(u.grade, u.created_at, get_now())),
            }
            for u in studs
        ]
    return {
        "classrooms": [await _classroom_view(db, r) for r in rooms],
        "academyStudents": academy_students,
    }


async def _my_room(db: AsyncSession, t: Account, class_id: str) -> Room:
    room = await db.get(Room, class_id)
    if room is None or room.teacher_id != t.id:
        fail("강의실을 찾지 못했어요.", 404, "not_found")
    return room


@router.get("/teacher/classes")
async def get_teacher_classes(db: Db, account: CurrentAccount) -> dict[str, Any]:
    return await _teacher_classes(db, require_account(account, "teacher"))


class RoomIn(BaseModel):
    name: str
    plan: str = ""


@router.post("/teacher/classes")
async def create_classroom(
    body: RoomIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t = require_account(account, "teacher")
    if not t.academy_id or t.teacher_status != "승인됨":
        fail("소속 학원·학교의 승인을 받은 뒤에 강의실을 열 수 있어요.", 403, "forbidden")
    if not body.name.strip():
        fail("강의실 이름을 적어 주세요.", 422)
    db.add(
        Room(
            id=_new_id("c"),
            academy_id=t.academy_id,
            teacher_id=t.id,
            name=body.name.strip()[:60],
            plan=body.plan.strip()[:120],
            trial_id=t.trial_id,
            created_at=now,
        )
    )
    await db.commit()
    return await _teacher_classes(db, t)


class StudentIdIn(BaseModel):
    studentId: str


@router.post("/teacher/classes/{class_id}/invites")
async def invite_student(
    class_id: str, body: StudentIdIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t = require_account(account, "teacher")
    room = await _my_room(db, t, class_id)
    s = await db.get(Account, body.studentId)
    if s is None or s.role != "student" or not t.academy_id or s.academy_id != t.academy_id:
        fail("같은 학원 학생만 초대할 수 있어요.", 403, "forbidden")
    place = await _place(db, room.id, s.id)
    if place is not None and place.state == "member":
        fail("이미 들어와 있어요.", 409)
    if place is not None and place.state == "requested":
        place.state = "member"  # 요청이 있었으면 바로 입장
    elif place is None:
        db.add(
            RoomPerson(
                room_id=room.id,
                student_account_id=s.id,
                state="invited",
                trial_id=room.trial_id,
                created_at=now,
            )
        )
        notify(db, s, f"{t.name}이 「{room.name}」에 초대했어!", "/student/classes", now=now)
    await db.commit()
    return await _teacher_classes(db, t)


class AcceptIn(BaseModel):
    accept: bool


@router.post("/teacher/classes/{class_id}/requests/{student_id}")
async def answer_request(
    class_id: str, student_id: str, body: AcceptIn, db: Db, now: Now, account: CurrentAccount
) -> dict[str, Any]:
    t = require_account(account, "teacher")
    room = await _my_room(db, t, class_id)
    place = await _place(db, room.id, student_id)
    if place is None or place.state != "requested":
        fail("요청을 찾지 못했어요.", 404, "not_found")
    if body.accept:
        place.state = "member"
        text = await kid_or_adult_text(
            db, student_id, f"「{room.name}」에 들어왔어!", f"「{room.name}」에 들어왔어요!"
        )
        await _notify_id(db, student_id, text, "/student", now)
    else:
        await db.delete(place)
    await db.commit()
    return await _teacher_classes(db, t)


# --- 학생: 강의실 ----------------------------------------------------------------------


async def _student_classes(db: AsyncSession, s: Account) -> dict[str, Any]:
    if not s.academy_id:
        return {"joined": [], "invites": [], "available": []}
    rooms = list(
        await db.scalars(
            select(Room).where(Room.academy_id == s.academy_id).order_by(Room.created_at, Room.id)
        )
    )
    joined, invites, available = [], [], []
    for r in rooms:
        place = await _place(db, r.id, s.id)
        view = {"id": r.id, "name": r.name, "teacherName": await _name(db, r.teacher_id)}
        state = place.state if place is not None else None
        if state == "member":
            joined.append(view)
        elif state == "invited":
            invites.append(view)
        else:
            available.append({**view, "requested": state == "requested"})
    return {"joined": joined, "invites": invites, "available": available}


@router.get("/student/classes")
async def get_student_classes(db: Db, account: CurrentAccount) -> dict[str, Any]:
    return await _student_classes(db, require_account(account, "student"))


@router.post("/student/classes/{class_id}/request")
async def request_join(class_id: str, db: Db, now: Now, account: CurrentAccount) -> dict[str, Any]:
    s = require_account(account, "student")
    if await is_restricted(db, s.id):
        fail("보호자와 먼저 연결해 주세요.", 403, "restricted")
    room = await db.get(Room, class_id)
    if room is None or not s.academy_id or room.academy_id != s.academy_id:
        fail("강의실을 찾지 못했어요.", 404, "not_found")
    if await _place(db, room.id, s.id) is None:
        db.add(
            RoomPerson(
                room_id=room.id,
                student_account_id=s.id,
                state="requested",
                trial_id=room.trial_id,
                created_at=now,
            )
        )
        await _notify_id(
            db,
            room.teacher_id,
            f"{s.name} 학생이 「{room.name}」 참여를 요청했어요",
            "/teacher/classes",
            now,
        )
    await db.commit()
    return await _student_classes(db, s)


@router.post("/student/classes/{class_id}/invite")
async def accept_invite(
    class_id: str, body: AcceptIn, db: Db, account: CurrentAccount
) -> dict[str, Any]:
    s = require_account(account, "student")
    place = await _place(db, class_id, s.id)
    if place is None or place.state != "invited":
        fail("초대를 찾지 못했어요.", 404, "not_found")
    if body.accept:
        place.state = "member"
    else:
        await db.delete(place)
    await db.commit()
    return await _student_classes(db, s)


# --- 수업 타이머 알림 시점(학원 설정) — 결정 11-11 「강의실 수업 타이머」, 성호 11-12 -----------------
# 서버는 학원별 「n분 전」 목록만 저장한다. 타이머 실행·알림 표시는 프론트(서버 푸시·큐 없음).
# 읽기 = 학원 소속 학습지도자·원장, 쓰기 = 원장. 1~60 정수, 중복 없이, 최대 3개, 큰 것부터 저장.

TIMER_ALERTS_DEFAULT = [10, 5]
TIMER_ALERTS_MAX = 3


def _parse_alerts(raw: str | None) -> list[int]:
    nums = [int(x) for x in (raw or "").split(",") if x.strip().isdigit()]
    return nums or list(TIMER_ALERTS_DEFAULT)


class TimerAlertsIn(BaseModel):
    alertsMin: list[Any]


@router.get("/academy/timer-alerts")
async def get_timer_alerts(db: Db, account: CurrentAccount) -> dict[str, Any]:
    u = require_account(account, "teacher")
    ac = await _owned_academy(db, u)
    if ac is None and u.academy_id is not None:
        ac = await db.get(Academy, u.academy_id)
    return {"alertsMin": _parse_alerts(ac.timer_alerts if ac is not None else None)}


@router.put("/academy/timer-alerts")
async def save_timer_alerts(body: TimerAlertsIn, db: Db, account: CurrentAccount) -> dict[str, Any]:
    _, ac = await _must_owner(db, account)
    vals = body.alertsMin
    ok = all(type(v) is int and 1 <= v <= 60 for v in vals)  # bool·실수·문자 거부
    nums = sorted(set(vals), reverse=True) if ok else []
    if not nums or len(nums) > TIMER_ALERTS_MAX:
        fail(f"알림은 1~60분 사이로 {TIMER_ALERTS_MAX}개까지 정해 주세요.", 422, "invalid_alerts")
    ac.timer_alerts = ",".join(str(n) for n in nums)
    await db.commit()
    return {"alertsMin": nums}
