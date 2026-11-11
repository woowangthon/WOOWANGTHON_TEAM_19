"""계정 신원의 바탕(명세 4.12, 설계 1112 §10): 비밀번호 해시·로그인 토큰·쿠키·현재 계정·Me 모양.

다른 모듈이 쓰는 이름(바꾸지 말 것):
- `CurrentAccount` / `current_account` — 유효한 쿠키 `cm_session` 또는 `Authorization: Bearer`의 계정,
  없거나 만료면 None. `token_sent(request)` — 토큰이 오긴 했는지(만료 구분용).
- `require_account(account, *roles)` — 없으면 401 not_logged_in, 역할이 다르면 403 forbidden.
- `fail(message, status=400, code=...)` — org.ts fail() 문구 그대로 오류를 낸다.
- `me_view(db, account)` — types.ts Me 모양. `is_restricted(db, student_account_id)`.
- `notify(db, account_id, text, to)`, `stamp_label(dt)`, `trial_id_from(request)`.
- `same_realm(column, trial_id)` — 코드로 찾을 때 쓰는 영역 조건(실제 가입 ⇄ 체험 세상 격리).

비밀번호는 scrypt(표준 라이브러리), 토큰·이메일은 sha256만 저장한다. 로그에 원문을 남기지 않는다.
"""

import hashlib
import hmac
import re
import secrets
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Annotated, Any, NoReturn

from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import ApiError
from app.models_org import (
    Academy,
    AcademyApplication,
    Account,
    AuthToken,
    Link,
    Notice,
)
from app.timeutil import SEOUL, as_utc, get_now

COOKIE = "cm_session"
REMEMBER_TTL = timedelta(days=30)
SESSION_TTL = timedelta(days=1)  # remember=false: 세션 쿠키 + DB 만료 1일

ID_RULE = re.compile(r"^[a-z][a-z0-9_]{3,15}$")  # org.ts ID_RULE
PW_RULE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,20}$")  # org.ts PW_RULE
EMAIL_RULE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEMO_PASSWORD = "demo1234"
DEFAULT_SETTINGS: dict[str, Any] = {
    "studyReminder": "17:00",
    "learnDone": True,
    "activity": True,
    "marketing": False,
}
CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 헷갈리는 0·O·1·I 제외(org.ts)
_ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
_TRIAL_RE = re.compile(r"^t-[a-z0-9]{16}$")
ROLE_LABEL = {
    "student": "학생",
    "guardian": "보호자",
    "teacher": "학습지도자",
    "operator": "운영자",
}

Db = Annotated[AsyncSession, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]


# --- 오류 ------------------------------------------------------------------------------


def fail(message: str, status: int = 400, code: str = "bad_request") -> NoReturn:
    """org.ts fail(msg)과 같은 문구로 오류. compat 라우터가 detail(=message)을 붙인다."""
    raise ApiError(status, code, message)


# --- 해시 ------------------------------------------------------------------------------

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        got = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), digest)


@lru_cache(maxsize=1)
def demo_password_hash() -> str:
    """체험 세상 계정 공통 비밀번호 해시. 프로세스마다 한 번만 계산(설계 §9-10)."""
    return hash_password(DEMO_PASSWORD)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def email_hash(email: str) -> str:
    """이메일은 정규화(앞뒤 공백 제거·소문자) 뒤 sha256만 저장한다."""
    return sha256(email.strip().lower())


def new_account_id() -> str:
    return "a-" + "".join(secrets.choice(_ID_CHARS) for _ in range(16))


def rand_code(n: int, chars: str = CODE_CHARS) -> str:
    return "".join(secrets.choice(chars) for _ in range(n))


async def unique_link_code(db: AsyncSession) -> str:
    while True:
        code = rand_code(6)
        if await db.scalar(select(Account.id).where(Account.link_code == code)) is None:
            return code


async def unique_serial(db: AsyncSession) -> str:
    while True:
        serial = f"{rand_code(4)}-{rand_code(4)}"
        if await db.scalar(select(Academy.id).where(Academy.serial == serial)) is None:
            return serial


# --- 시각 ------------------------------------------------------------------------------


def stamp_label(when: datetime) -> str:
    """org.ts stampLabel과 같은 「11월 12일 · 09:05」(서울 시간)."""
    d = (as_utc(when) or when).astimezone(SEOUL)
    return f"{d.month}월 {d.day}일 · {d.hour:02d}:{d.minute:02d}"


def ymd(d: date) -> str:
    return d.isoformat()


# --- 토큰·쿠키 -------------------------------------------------------------------------


def read_token(request: Request) -> str | None:
    """Bearer가 먼저(테스트·도구), 없으면 쿠키 cm_session."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    return request.cookies.get(COOKIE) or None


def token_sent(request: Request) -> bool:
    return read_token(request) is not None


def trial_id_from(request: Request) -> str | None:
    """X-Trial-Id가 체험 세트 형식(`t-<16>`)이면 그 값, 아니면 None."""
    raw = (request.headers.get("x-trial-id") or "").strip()
    return raw if _TRIAL_RE.match(raw) else None


def same_realm(column: Any, trial_id: str | None) -> Any:
    """영역(realm) 조건. 영역 = trial_id 값.

    실제 가입 계정(None)은 실제 행만, 체험 세상은 자기 세트 행만 찾는다. 연결 코드·입장 코드·
    일련번호처럼 「코드로 찾는」 곳은 반드시 이 조건을 함께 건다(보안 검토 11-12).
    """
    return column.is_(None) if trial_id is None else column == trial_id


def _secure(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"


async def issue_session(
    db: AsyncSession,
    request: Request,
    response: Response,
    account: Account,
    now: datetime,
    remember: bool,
) -> str:
    """토큰을 새로 만들어 sha256만 저장하고 쿠키로 준다. 커밋은 부르는 쪽이 한다."""
    token = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            token_hash=sha256(token),
            account_id=account.id,
            expires_at=now + (REMEMBER_TTL if remember else SESSION_TTL),
            trial_id=account.trial_id,
            created_at=now,
        )
    )
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(REMEMBER_TTL.total_seconds()) if remember else None,
        httponly=True,
        samesite="lax",
        secure=_secure(request),
        path="/",
    )
    return token


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


async def account_for_token(db: AsyncSession, token: str, now: datetime) -> Account | None:
    row = await db.get(AuthToken, sha256(token))
    if row is None:
        return None
    expires = as_utc(row.expires_at)
    if expires is None or expires <= now:
        return None
    return await db.get(Account, row.account_id)


async def current_account(request: Request, db: Db, now: Now) -> Account | None:
    """유효한 토큰의 계정. 토큰이 없거나 만료·로그아웃이면 None(요청마다 한 번, FastAPI가 캐시)."""
    token = read_token(request)
    if token is None:
        return None
    return await account_for_token(db, token, now)


CurrentAccount = Annotated[Account | None, Depends(current_account)]


def require_account(account: Account | None, *roles: str) -> Account:
    if account is None:
        fail("로그인이 필요해요.", 401, "not_logged_in")
    if roles and account.role not in roles:
        names = "·".join(ROLE_LABEL[r] for r in roles)
        fail(f"이 기능은 {names} 화면에서만 쓸 수 있어요.", 403, "forbidden")
    return account


# --- 연결·알림 -------------------------------------------------------------------------


async def connected_ids(db: AsyncSession, account: Account) -> list[str]:
    """연결됨 상대 계정 id(학생이면 보호자들, 보호자면 아이들). 동의 순·id 순."""
    if account.role == "student":
        col, other = Link.student_account_id, Link.guardian_account_id
    else:
        col, other = Link.guardian_account_id, Link.student_account_id
    rows = await db.scalars(
        select(other)
        .where(col == account.id, Link.status == "연결됨")
        .order_by(Link.consent_at, other)
    )
    return list(rows)


async def first_child_id(db: AsyncSession, guardian_id: str) -> str | None:
    """보호자가 보는 아이: 연결된 첫 아이(consent_at, 학생 id 순, 설계 §9-13)."""
    return await db.scalar(
        select(Link.student_account_id)
        .where(Link.guardian_account_id == guardian_id, Link.status == "연결됨")
        .order_by(Link.consent_at, Link.student_account_id)
        .limit(1)
    )


async def is_restricted(db: AsyncSession, student_account_id: str) -> bool:
    """학생: 연결됨 보호자가 없으면 제한 모드(수다·학원 막음, org.ts isRestricted)."""
    found = await db.scalar(
        select(Link.guardian_account_id)
        .where(Link.student_account_id == student_account_id, Link.status == "연결됨")
        .limit(1)
    )
    return found is None


def notify(
    db: AsyncSession,
    account: Account | str,
    text: str,
    to: str | None = None,
    now: datetime | None = None,
    trial_id: str | None = None,
) -> None:
    """알림함에 한 줄(org.ts notify). 커밋은 부르는 쪽이 한다."""
    account_id = account if isinstance(account, str) else account.id
    if trial_id is None and not isinstance(account, str):
        trial_id = account.trial_id
    row = Notice(account_id=account_id, text=text, to_path=to, read=False, trial_id=trial_id)
    if now is not None:
        row.created_at = now
    db.add(row)


# --- Me 모양 ---------------------------------------------------------------------------


def application_view(app: AcademyApplication) -> dict[str, Any]:
    """types.ts AcademyApplication(ownerId 없이)."""
    return {
        "id": app.id,
        "orgType": app.org_type,
        "academyName": app.academy_name,
        "bizNo": app.biz_no,
        "ceo": app.ceo,
        "phone": app.phone,
        "address": app.address,
        "status": app.status,
        "appliedAt": stamp_label(app.applied_at),
        "serial": app.serial,
        "rejectReason": app.reject_reason,
        "ownerName": app.owner_name,
    }


async def _people(db: AsyncSession, ids: list[str]) -> list[dict[str, Any]]:
    out = []
    for pid in ids:
        acc = await db.get(Account, pid)
        if acc is not None:
            out.append({"id": acc.id, "name": acc.name, "role": acc.role})
    return out


async def me_view(db: AsyncSession, u: Account) -> dict[str, Any]:
    """org.ts meView 그대로. email은 해시만 있어 항상 null(원문 미저장)."""
    academy = await db.get(Academy, u.academy_id) if u.academy_id else None
    if u.role == "student":
        pend_col, pend_other = Link.student_account_id, Link.guardian_account_id
    else:
        pend_col, pend_other = Link.guardian_account_id, Link.student_account_id
    pending = list(
        await db.scalars(
            select(pend_other)
            .where(pend_col == u.id, Link.status == "대기")
            .order_by(Link.created_at, pend_other)
        )
    )
    app = await db.get(AcademyApplication, u.application_id) if u.application_id else None
    show_academy = academy is not None and (u.role != "teacher" or u.teacher_status == "승인됨")
    membership = None
    if u.role == "teacher" and academy is not None:
        membership = {
            "academyId": academy.id,
            "name": academy.name,
            "orgType": academy.org_type,
            "status": u.teacher_status or "승인 대기",
            "isOwner": academy.owner_id == u.id,
        }
    return {
        "id": u.id,
        "role": u.role,
        "name": u.name,
        "loginId": u.login_id,
        "email": None,
        "grade": u.grade,
        "linkCode": u.link_code,
        "linked": await _people(db, await connected_ids(db, u)),
        "pendingLinks": await _people(db, pending),
        "academy": {"id": academy.id, "name": academy.name}
        if show_academy and academy is not None
        else None,
        "membership": membership,
        "application": application_view(app) if app is not None else None,
        "restricted": u.role == "student" and await is_restricted(db, u.id),
        "outfit": u.outfit if u.role == "student" else None,
        # 알림 설정 칸만 내보낸다(단원 선택 같은 서버 전용 키는 빼고)
        "settings": {
            **DEFAULT_SETTINGS,
            **{k: v for k, v in (u.settings or {}).items() if k in DEFAULT_SETTINGS},
        },
    }
