"""계정 API `/api/v1/compat`(명세 4.12, 설계 §10) — frontend/src/api/http.ts 경로·본문 그대로.

getMe·login·checkLoginId·signup·logout·findLoginId·requestPasswordReset·demoAccounts·demoLogin·
updateProfile·changePassword·saveSettings·deleteAccount·resetChildPassword·getNotices·readNotices.
규칙·문구는 frontend/src/api/org.ts의 fail() 그대로. 응답 모양은 types.ts(camelCase).
로그에는 아이디·이름·이메일을 남기지 않는다.
"""

from typing import Any, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, or_, select, update

from app.accounts import (
    DEFAULT_SETTINGS,
    DEMO_PASSWORD,
    EMAIL_RULE,
    ID_RULE,
    PW_RULE,
    CurrentAccount,
    Db,
    Now,
    clear_session_cookie,
    connected_ids,
    email_hash,
    fail,
    hash_password,
    issue_session,
    me_view,
    new_account_id,
    notify,
    read_token,
    require_account,
    sha256,
    stamp_label,
    trial_id_from,
    unique_link_code,
    verify_password,
)
from app.compat import _CompatRoute
from app.demo import ResetBody, _write_day3_student
from app.demo_world import RESERVED_LOGIN, demo_accounts, ensure_world, seed_key_of, world_id
from app.models import Student
from app.models_org import Academy, Account, AuthToken, Link, Notice, RoomPerson
from app.seed import load_seed
from app.timeutil import seoul_date

router = APIRouter(prefix="/compat", route_class=_CompatRoute)

MSG_ID_RULE = "아이디는 영문 소문자로 시작하는 4~16자(소문자·숫자·_)예요."


def _norm_login(login_id: str) -> str:
    return login_id.strip().lower()


async def _login_taken(db: Db, login_id: str) -> bool:
    if RESERVED_LOGIN.match(login_id):  # 체험 아이디 형식은 가입 불가(설계 §10)
        return True
    return await db.scalar(select(Account.id).where(Account.login_id == login_id)) is not None


def _require_trial(request: Request) -> str:
    trial_id = trial_id_from(request)
    if trial_id is None:
        fail("체험 세트가 없어요. 처음부터 다시 시작해 주세요.", 400, "trial_required")
    return trial_id


# --- 로그인·가입·찾기 ------------------------------------------------------------------


@router.get("/me")
async def get_me(db: Db, account: CurrentAccount) -> dict[str, Any] | None:
    """로그인 전·만료면 200 null(org.ts getMe)."""
    return await me_view(db, account) if account is not None else None


class LoginIn(BaseModel):
    loginId: str
    password: str
    remember: bool = True


@router.post("/auth/login")
async def login(
    body: LoginIn, request: Request, response: Response, db: Db, now: Now
) -> dict[str, Any]:
    trial_id = trial_id_from(request)
    if trial_id is not None and await db.get(Student, f"{trial_id}-child") is not None:
        await ensure_world(db, trial_id, now)  # 체험 세상이 아직 없으면 처음 로그인 때 만든다
    acc = await db.scalar(select(Account).where(Account.login_id == _norm_login(body.loginId)))
    # 체험 계정은 비밀번호를 바꿔도 공개 비밀번호(시트 안내)로 늘 들어간다(A4)
    demo_pw = acc is not None and acc.trial_id is not None and body.password == DEMO_PASSWORD
    if acc is None or not (demo_pw or verify_password(body.password, acc.pw_hash)):
        await db.commit()  # 세상을 만들었으면 남긴다
        fail("아이디 또는 비밀번호가 맞지 않아요.", 401, "login_failed")
    await issue_session(db, request, response, acc, now, body.remember)
    await db.commit()
    return await me_view(db, acc)


@router.get("/auth/check-id")
async def check_login_id(loginId: str, db: Db) -> bool:
    """true = 쓸 수 있음."""
    login_id = _norm_login(loginId)
    if not ID_RULE.match(login_id):
        fail(MSG_ID_RULE, 422, "invalid_login_id")
    return not await _login_taken(db, login_id)


class Agreements(BaseModel):
    terms: bool = False
    privacy: bool = False
    marketing: bool = False


class SignupIn(BaseModel):
    role: Literal["student", "guardian", "teacher"]
    loginId: str
    password: str
    name: str
    grade: int | None = None
    email: str | None = None
    agreements: Agreements


@router.post("/auth/signup")
async def signup(
    body: SignupIn, request: Request, response: Response, db: Db, now: Now
) -> dict[str, Any]:
    name = body.name.strip()
    login_id = _norm_login(body.loginId)
    if not body.agreements.terms or not body.agreements.privacy:
        fail("필수 약관에 동의해 주세요.", 422)
    if not ID_RULE.match(login_id):
        fail(MSG_ID_RULE, 422, "invalid_login_id")
    if await _login_taken(db, login_id):
        fail("이미 쓰는 아이디예요.", 409, "login_id_taken")
    if not PW_RULE.match(body.password):
        fail("비밀번호는 영문과 숫자를 섞어 8~20자로 만들어 주세요.", 422)
    if not name:
        fail("이름을 적어 주세요.", 422)
    if len(name) > 12:
        fail("이름은 12자까지 쓸 수 있어요.", 422)
    if body.role == "student" and not (isinstance(body.grade, int) and 1 <= body.grade <= 12):
        fail("학년을 골라 주세요.", 422)
    if body.role != "student" and not EMAIL_RULE.match(body.email or ""):
        fail("이메일을 바르게 적어 주세요. 아이디·비밀번호를 찾을 때 써요.", 422)
    acc_id = new_account_id()
    while await db.get(Account, acc_id) is not None or await db.get(Student, acc_id) is not None:
        acc_id = new_account_id()
    today = seoul_date(now)
    acc = Account(
        id=acc_id,
        login_id=login_id,
        pw_hash=hash_password(body.password),
        role=body.role,
        name=name,
        grade=body.grade if body.role == "student" else None,
        email_hash=email_hash(body.email or "") if body.role != "student" else None,
        link_code=await unique_link_code(db) if body.role in ("student", "guardian") else None,
        settings={
            **DEFAULT_SETTINGS,
            "marketing": body.agreements.marketing,
            "studyReminder": "17:00" if body.role == "student" else None,
        },
        marketing=body.agreements.marketing,
        agreed_at=today,
        student_id=acc_id if body.role == "student" else None,
        # 가입은 언제나 실제 계정(영역 None). X-Trial-Id를 옮겨 적지 않는다 — 옮기면 체험 세상의
        # 연결 코드·학원에 닿는다(보안 검토 11-12). 심사 범위는 신청서가 따로 정한다(org_routes).
        trial_id=None,
        created_at=now,
    )
    db.add(acc)
    if body.role == "student":
        # day3와 같은 시작(오개념·오늘 과제)이되 연속 0, 약속 동의 전(명세 4.12-5)
        await load_seed(db)
        await _write_day3_student(
            db, ResetBody(), today, student_id=acc_id, consent=False, nickname=name
        )
        student = await db.get(Student, acc_id)
        assert student is not None
        student.streak_days = 0
        student.last_streak_date = None
        student.created_at = now
    await issue_session(db, request, response, acc, now, remember=True)
    await db.commit()
    return await me_view(db, acc)


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response, db: Db) -> None:
    """쿠키가 없거나 이미 만료여도 204(멱등). 토큰 행을 지우고 쿠키를 지운다."""
    token = read_token(request)
    if token is not None:
        await db.execute(delete(AuthToken).where(AuthToken.token_hash == sha256(token)))
        await db.commit()
    clear_session_cookie(response)


class FindIdIn(BaseModel):
    email: str


def _scope(request: Request) -> Any:
    """아이디·비밀번호 찾기 범위: 체험 세트 밖(일반 가입) + 지금 세트(설계 §9-13)."""
    trial_id = trial_id_from(request)
    if trial_id is None:
        return Account.trial_id.is_(None)
    return or_(Account.trial_id.is_(None), Account.trial_id == trial_id)


@router.post("/auth/find-id")
async def find_login_id(body: FindIdIn, request: Request, db: Db) -> list[str]:
    rows = list(
        await db.scalars(
            select(Account.login_id)
            .where(Account.email_hash == email_hash(body.email), _scope(request))
            .order_by(Account.created_at, Account.login_id)
        )
    )
    if not rows:
        fail("그 이메일로 가입한 계정이 없어요.", 404, "not_found")
    return [x[:3] + "*" * max(1, len(x) - 3) for x in rows]


class ResetPwIn(BaseModel):
    loginId: str
    email: str


@router.post("/auth/reset-password")
async def request_password_reset(body: ResetPwIn, request: Request, db: Db) -> str:
    """시연: 메일은 보내지 않고 'sent'만(명세 4.12-6). 학생은 'ask-guardian'."""
    acc = await db.scalar(
        select(Account).where(Account.login_id == _norm_login(body.loginId), _scope(request))
    )
    if acc is None:
        fail("아이디를 찾지 못했어요.", 404, "not_found")
    if acc.role == "student":
        return "ask-guardian"
    if acc.email_hash != email_hash(body.email):
        fail("아이디와 이메일이 맞지 않아요.", 400)
    return "sent"


# --- 체험 계정 -------------------------------------------------------------------------


@router.get("/demo/accounts")
async def get_demo_accounts(request: Request, db: Db, now: Now) -> list[dict[str, Any]]:
    trial_id = _require_trial(request)
    if await ensure_world(db, trial_id, now):
        await db.commit()
    return await demo_accounts(db, trial_id)


class DemoLoginIn(BaseModel):
    userId: str


@router.post("/demo/login")
async def demo_login(
    body: DemoLoginIn, request: Request, response: Response, db: Db, now: Now
) -> dict[str, Any]:
    """전체 id(`{다른 t}-child`)든 seed 키(`s1`)든 지금 X-Trial-Id 세상의 같은 키 계정으로."""
    trial_id = _require_trial(request)
    await ensure_world(db, trial_id, now)
    key = seed_key_of(body.userId)
    acc = await db.get(Account, world_id(trial_id, key)) if key is not None else None
    if acc is None:
        await db.commit()
        fail("계정을 찾지 못했어요.", 404, "not_found")
    await issue_session(db, request, response, acc, now, remember=True)
    await db.commit()
    return await me_view(db, acc)


# --- 설정 ------------------------------------------------------------------------------


class ProfileIn(BaseModel):
    name: str | None = None
    email: str | None = None


@router.put("/me")
async def update_profile(body: ProfileIn, db: Db, account: CurrentAccount) -> dict[str, Any]:
    u = require_account(account)
    if body.name is not None:
        n = body.name.strip()
        if not n or len(n) > 12:
            fail("이름은 1~12자로 적어 주세요.", 422)
        u.name = n
    if body.email is not None:
        if u.role == "student":
            fail("학생은 이메일을 받지 않아요.", 400)
        if not EMAIL_RULE.match(body.email):
            fail("이메일을 바르게 적어 주세요.", 422)
        u.email_hash = email_hash(body.email)
    await db.commit()
    return await me_view(db, u)


class PasswordIn(BaseModel):
    current: str
    next: str


@router.put("/me/password", status_code=204)
async def change_password(
    body: PasswordIn, request: Request, db: Db, account: CurrentAccount
) -> None:
    u = require_account(account)
    if not verify_password(body.current, u.pw_hash):
        fail("지금 비밀번호가 맞지 않아요.", 400, "wrong_password")
    if not PW_RULE.match(body.next):
        fail("새 비밀번호는 영문과 숫자를 섞어 8~20자로 만들어 주세요.", 422)
    if body.current == body.next:
        fail("지금과 다른 비밀번호로 바꿔 주세요.", 422)
    u.pw_hash = hash_password(body.next)
    # 다른 기기의 로그인은 끊고 지금 로그인만 남긴다(11-12 보안 점검)
    keep = read_token(request)
    stale = delete(AuthToken).where(AuthToken.account_id == u.id)
    if keep is not None:
        stale = stale.where(AuthToken.token_hash != sha256(keep))
    await db.execute(stale)
    await db.commit()


class SettingsIn(BaseModel):
    studyReminder: str | None
    learnDone: bool
    activity: bool
    marketing: bool


@router.put("/me/settings")
async def save_settings(body: SettingsIn, db: Db, account: CurrentAccount) -> dict[str, Any]:
    u = require_account(account)
    # 서버 전용 키(학습지도자 단원 선택 등, app/seeds.py)는 남긴다
    u.settings = {**(u.settings or {}), **body.model_dump()}
    u.marketing = body.marketing
    await db.commit()
    return await me_view(db, u)


class DeleteIn(BaseModel):
    password: str


@router.post("/me/delete", status_code=204)
async def delete_account(
    body: DeleteIn, response: Response, db: Db, account: CurrentAccount
) -> None:
    """비밀번호 확인 뒤 계정·연결·강의실 자리·토큰을 지운다. 학습 기록(students 행)은 남는다."""
    u = require_account(account)
    if u.trial_id is not None:  # 체험 세상은 여럿이 같이 쓴다 — 지우면 그 세트 로그인이 깨진다(A1)
        fail("체험 계정은 탈퇴할 수 없어요.", 409, "trial_account")
    if not verify_password(body.password, u.pw_hash):
        fail("비밀번호가 맞지 않아요.", 400, "wrong_password")
    if u.role == "teacher" and await db.scalar(
        select(Academy.id).where(Academy.owner_id == u.id).limit(1)
    ):
        fail("원장은 탈퇴 전에 학원 관리를 다른 학습지도자에게 넘겨야 해요(운영자 문의).", 409)
    await db.execute(
        delete(Link).where(or_(Link.student_account_id == u.id, Link.guardian_account_id == u.id))
    )
    await db.execute(delete(RoomPerson).where(RoomPerson.student_account_id == u.id))
    await db.execute(delete(AuthToken).where(AuthToken.account_id == u.id))
    await db.delete(u)
    await db.commit()
    clear_session_cookie(response)


class ChildPasswordIn(BaseModel):
    next: str


@router.put("/guardian/children/{child_id}/password", status_code=204)
async def reset_child_password(
    child_id: str, body: ChildPasswordIn, db: Db, now: Now, account: CurrentAccount
) -> None:
    g = require_account(account, "guardian")
    if child_id not in await connected_ids(db, g):
        fail("연결된 아이만 바꿀 수 있어요.", 403, "forbidden")
    if not PW_RULE.match(body.next):
        fail("비밀번호는 영문과 숫자를 섞어 8~20자로 만들어 주세요.", 422)
    child = await db.get(Account, child_id)
    if child is None:
        fail("연결된 아이만 바꿀 수 있어요.", 403, "forbidden")
    child.pw_hash = hash_password(body.next)
    await db.execute(
        delete(AuthToken).where(AuthToken.account_id == child.id)
    )  # 아이 기기 로그인 끊기
    notify(db, child, "보호자가 비밀번호를 새로 정해 줬어.", now=now)
    await db.commit()


# --- 알림함 ----------------------------------------------------------------------------


def _notice_view(n: Notice) -> dict[str, Any]:
    return {
        "id": n.id,
        "at": stamp_label(n.created_at),
        "text": n.text,
        "to": n.to_path,
        "read": n.read,
    }


@router.get("/notices")
async def get_notices(db: Db, account: CurrentAccount) -> list[dict[str, Any]]:
    u = require_account(account)
    rows = await db.scalars(
        select(Notice)
        .where(Notice.account_id == u.id)
        .order_by(Notice.created_at.desc(), Notice.id.desc())
    )
    return [_notice_view(n) for n in rows]


@router.post("/notices/read", status_code=204)
async def read_notices(db: Db, account: CurrentAccount) -> None:
    u = require_account(account)
    await db.execute(update(Notice).where(Notice.account_id == u.id).values(read=True))
    await db.commit()
