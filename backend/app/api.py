"""아이 쪽 API 2·3·4번과 healthz(12번). 명세 4.4.

- 아이 신원은 데모 헤더 X-Demo-Role / X-Demo-Actor로 받는다.
- 전환·시간 마감은 state_machine 순수 함수가 정하고, 여기서는 DB 행에 옮겨 적기만 한다.
- 응답에 정답·힌트·풀이를 넣지 않는다(problem은 id·text만).
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field, StrictBool
from sqlalchemy import CursorResult, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.accounts import CurrentAccount, token_sent
from app.actors import actor_from_request
from app.db import get_db
from app.errors import ApiError
from app.judge import contains_answer, judge, parse_value
from app.llm import FIXED_REPLY, LLMAdapter, Reply, ReplyRequest, ScriptedAdapter, build_adapter
from app.models import (
    EXCERPT_MAX,
    MESSAGE_TTL,
    Alert,
    Message,
    Misconception,
    Problem,
    Session,
    Student,
)
from app.models_org import SessionProblem
from app.pii import redact
from app.prompts import PROMPT_VERSION, PromptInput, build_prompt
from app.safety import check as red_keyword
from app.state_machine import (
    ACTIVE,
    MAX_HINT,
    SessionState,
    State,
    TransitionError,
    end,
    enter_phase,
    expire_if_due,
    press_hint,
    start,
    study_time_over,
    to_crisis,
)
from app.timeutil import as_utc, get_now, seoul_date
from app.trial import AI_DAILY_MAX, AI_HOURLY_MAX

log = logging.getLogger(__name__)

health_router = APIRouter()
router = APIRouter()

Db = Annotated[AsyncSession, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]

FINISHED = (State.ENDED.value, State.CRISIS.value)


@health_router.get("/healthz")
async def healthz(db: Db) -> dict[str, Any]:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # 상태 확인용. 원인은 응답에 싣지 않는다
        db_status = "error"
    return {
        "db": db_status,
        "llm_key": config.llm_key_present(),
        "llm_mode": config.llm_effective_mode(),
        "tz": "Asia/Seoul",
    }


async def current_child(
    request: Request,
    db: Db,
    account: CurrentAccount,
    x_demo_role: Annotated[str | None, Header()] = None,
    x_demo_actor: Annotated[str | None, Header()] = None,
) -> Student:
    # 로그인 계정이 먼저, 없으면 데모 헤더(명세 4.12)
    actor = await actor_from_request(
        db, "child", x_demo_role, x_demo_actor, account=account, token_sent=token_sent(request)
    )
    student = actor.student
    assert student is not None  # child 역할은 학생이 없으면 resolve_actor가 404
    return student


Child = Annotated[Student, Depends(current_child)]


async def _today_session(db: AsyncSession, student: Student, now: datetime) -> Session | None:
    """오늘(서울 날짜) 세션을 읽고, 마감이 지났으면 먼저 전이해 행에 반영한다."""
    row = await db.scalar(
        select(Session).where(Session.student_id == student.id, Session.date == seoul_date(now))
    )
    if row is None:
        return None
    await _expire_row(db, row, now)
    return row


def _row_state(row: Session) -> SessionState:
    return SessionState(
        state=State(row.state),
        hint_level=row.hint_level,
        streak_applied=row.streak_applied,
        phase_started_at=as_utc(row.phase_started_at),
        deadline_at=as_utc(row.deadline_at),
    )


async def _expire_row(db: AsyncSession, row: Session, now: datetime) -> None:
    """마감이 지났으면 먼저 전이해 행에 반영한다(명세 4.2 시간 칸). 오늘 세션이 아니어도 쓴다."""
    before = _row_state(row)
    after = expire_if_due(before, now)
    if after != before:
        row.state = after.state.value
        row.phase_started_at = after.phase_started_at
        row.deadline_at = after.deadline_at
        await db.flush()


async def _today_task(db: AsyncSession, student: Student) -> tuple[str, str] | None:
    """(problem_id, source). 강사 지정이 먼저, 없으면 미해결 오개념 태그의 첫 문제."""
    if student.today_task_problem_id:
        return student.today_task_problem_id, "instructor"
    tags = (
        await db.scalars(
            select(Misconception.tag)
            .where(Misconception.student_id == student.id, Misconception.status == "open")
            .order_by(Misconception.first_wrong_date, Misconception.tag)
        )
    ).all()
    for tag in tags:
        pid = await db.scalar(
            select(Problem.id).where(Problem.tag == tag).order_by(Problem.id).limit(1)
        )
        if pid is not None:
            return pid, "misconception"
    return None


# --- 한 세션 여러 문제(SESSION_PROBLEMS > 1, 11-12) ------------------------------------
# 기본 1이면 session_problems 표를 아예 읽지 않는다(그 표가 없는 DB에서도 예전 그대로).
# 지금 문제·힌트는 sessions.problem_id·hint_level 그대로 쓰고, 다음 문제로 갈 때 바꿔 적는다.


async def _plan_ids(db: AsyncSession, first_id: str) -> list[str]:
    """첫 문제 + 같은 태그 시드를 id 순으로(첫 문제 뒤부터 돌아서). 최대 SESSION_PROBLEMS개."""
    n = config.session_problems()
    if n <= 1:
        return [first_id]
    first = await db.get(Problem, first_id)
    if first is None:
        return [first_id]
    ids = list(
        (
            await db.scalars(
                select(Problem.id).where(Problem.tag == first.tag).order_by(Problem.id)
            )
        ).all()
    )
    i = ids.index(first_id)
    return (ids[i:] + ids[:i])[:n]


async def _create_plan(db: AsyncSession, session: Session, now: datetime) -> None:
    """세션을 새로 만들 때 한 번. 문제가 1개뿐이면 행을 만들지 않는다(= 한 문제 세션)."""
    if config.session_problems() <= 1 or session.problem_id is None:
        return
    ids = await _plan_ids(db, session.problem_id)
    if len(ids) <= 1:
        return
    from app.seeds import _trial_of  # seeds가 api를 import한다(순환 방지)

    trial = await _trial_of(db, session.student_id)
    for i, pid in enumerate(ids):
        db.add(
            SessionProblem(
                session_id=session.id, idx=i, problem_id=pid, trial_id=trial, created_at=now
            )
        )
    await db.flush()


async def _plan(db: AsyncSession, row: Session) -> list[SessionProblem]:
    if config.session_problems() <= 1:
        return []
    return list(
        (
            await db.scalars(
                select(SessionProblem)
                .where(SessionProblem.session_id == row.id)
                .order_by(SessionProblem.idx)
            )
        ).all()
    )


def _current(plan: Sequence[SessionProblem]) -> SessionProblem | None:
    """끝나지 않은 첫 문제. 다 끝났으면(마지막은 끝 표시를 하지 않는다) 마지막."""
    return next((p for p in plan if not p.finished), plan[-1] if plan else None)


async def plan_position(db: AsyncSession, row: Session) -> tuple[int, int]:
    """(지금 문제 순번 0부터, 전체 문제 수). 한 문제 세션은 (0, 1)."""
    plan = await _plan(db, row)
    cur = _current(plan)
    return (cur.idx, len(plan)) if cur is not None else (0, 1)


async def sync_progress(db: AsyncSession, row: Session, now: datetime) -> None:
    """지금 문제를 끝냈으면(정답 또는 풀이 보기) 다음 문제로: problem_id 교체, hint_level 0.

    마지막 문제이거나 20분이 지났으면 넘기지 않는다 → 지금처럼 transition(수다·다리 놓기).
    """
    if row.state != State.STUDY.value:
        return
    plan = await _plan(db, row)
    cur = _current(plan)
    if cur is None or cur.finished or cur.idx >= len(plan) - 1:
        return
    solved = await is_solved(db, row, await db.get(Problem, row.problem_id))
    if not (solved or row.hint_level >= MAX_HINT):
        return
    if study_time_over(as_utc(row.phase_started_at), now, config.timer_scale()):
        return
    cur.finished = True
    cur.hint_level = row.hint_level
    cur.assisted = not solved
    nxt = plan[cur.idx + 1]
    last_seq = await db.scalar(select(func.max(Message.seq)).where(Message.session_id == row.id))
    nxt.start_seq = last_seq or 0
    row.problem_id = nxt.problem_id
    row.hint_level = 0
    await db.flush()
    log.info("next problem session=%s idx=%d", row.id, nxt.idx)


@dataclass(frozen=True)
class Progress:
    """세션 전체 결과. 한 문제 세션은 예전 계산(solved 0/1, total 1)과 같다."""

    solved: int  # 끝낸 문제(정답 + 풀이 보기)
    total: int
    assisted: int  # 그중 풀이 보기로 끝낸 문제
    hints: int  # 쓴 힌트 수(문제마다 최대 2, 풀이 보기는 세지 않는다)
    hint_presses: int  # 힌트 단계 합(풀이 보기 3 포함). 한 문제면 hint_level 그대로


async def progress(db: AsyncSession, row: Session) -> Progress:
    problem = await db.get(Problem, row.problem_id) if row.problem_id else None
    solved = await is_solved(db, row, problem)
    done = solved or row.hint_level >= MAX_HINT
    assisted = row.hint_level >= MAX_HINT and not solved
    plan = await _plan(db, row)
    finished = [p for p in plan if p.finished]
    return Progress(
        solved=len(finished) + int(done),
        total=len(plan) or 1,
        assisted=sum(p.assisted for p in finished) + int(assisted),
        hints=sum(min(p.hint_level, MAX_HINT - 1) for p in finished)
        + min(row.hint_level, MAX_HINT - 1),
        hint_presses=sum(p.hint_level for p in finished) + row.hint_level,
    )


async def _quiz_base(db: AsyncSession, row: Session) -> Problem | None:
    """다리 놓기 퀴즈의 기준 문제 = 세션의 첫 문제(여러 문제면 problem_id가 바뀌므로)."""
    plan = await _plan(db, row)
    pid = plan[0].problem_id if plan else row.problem_id
    return await db.get(Problem, pid) if pid else None


def _streak_text(student: Student) -> str:
    if student.streak_days <= 0:
        return "오늘부터 같이 해 보자"
    return f"{student.streak_days}일째 같이 했어"


def _greeting(session: Session | None) -> str:
    if session is not None and session.state in FINISHED:
        return "오늘도 고마워. 내일 봐!"
    if session is not None:
        return "하던 거 이어서 해 볼까?"
    return "안녕! 오늘도 같이 해 볼까?"


@router.get("/me/today")
async def me_today(db: Db, now: Now, student: Child) -> dict[str, Any]:
    session = await _today_session(db, student, now)
    task = None if session is not None else await _today_task(db, student)
    await db.commit()
    return {
        "greeting": _greeting(session),
        "streak_text": _streak_text(student),
        "today_task": {"problem_id": task[0], "source": task[1]} if task else None,
        "session": (
            {"id": session.id, "state": session.state, "hint_level": session.hint_level}
            if session is not None
            else None
        ),
    }


@router.post("/sessions")
async def start_session(db: Db, now: Now, student: Child) -> dict[str, Any]:
    session = await _today_session(db, student, now)
    if session is not None and session.state in FINISHED:
        await db.commit()
        raise ApiError(409, "session_finished", "오늘은 이미 끝났어요. 내일 봐요.")
    if session is None:
        task = await _today_task(db, student)
        if task is None:
            raise ApiError(409, "no_task", "오늘 할 문제가 없어요.")
        s = start(now)
        session = Session(
            student_id=student.id,
            date=seoul_date(now),
            state=s.state.value,
            hint_level=s.hint_level,
            problem_id=task[0],
            phase_started_at=s.phase_started_at,
            prompt_version=PROMPT_VERSION,
        )
        try:
            async with db.begin_nested():
                db.add(session)
                # 강사 지정은 세션으로 옮기고 비운다(명세 4.2 today_task)
                student.today_task_problem_id = None
                student.today_task_date = None
        except IntegrityError:
            # 동시 요청이 먼저 오늘 세션을 만들었다 → 그 세션을 이어서(명세 4.6)
            # 세이브포인트 rollback이 만료시킨 속성을 비동기로 다시 읽는다
            await db.refresh(student)
            session = await _today_session(db, student, now)
            assert session is not None
        else:
            await _create_plan(db, session, now)  # 여러 문제 모드일 때만 행이 생긴다
    problem = await db.get(Problem, session.problem_id) if session.problem_id else None
    await db.commit()
    return {
        "session_id": session.id,
        "state": session.state,
        "hint_level": session.hint_level,
        "problem": {"id": problem.id, "text": problem.text} if problem else None,
    }


# --- 4. POST /sessions/{id}/messages -------------------------------------------------

CRISIS_REPLY = "지금 한 말이 걱정돼서, 어른에게 알릴게"  # 부록 E. LLM 없이 고정
HOTLINES = ["109", "1388"]  # 자살예방상담 · 청소년상담
EXCERPT_TURNS = 3  # 🔴 문장 + 앞 2턴(뒤 턴은 아직 없다)
RECENT_TURNS = 6  # 프롬프트에 넘기는 최근 턴 수
ROLE_LABEL = {"child": "아이", "mentor": "친구1"}


@lru_cache
def _scripted() -> ScriptedAdapter:
    return ScriptedAdapter.from_file()


def get_llm() -> LLMAdapter:
    """어댑터 하나(명세 4 원칙 ②). LLM_MODE=live + 키면 live(실패 시 scripted), 아니면 scripted."""
    return build_adapter(_scripted())


Llm = Annotated[LLMAdapter, Depends(get_llm)]


MAX_PIECES = 5  # 한 턴에 묶어 보내는 조각 수 상한
REPLY_LEASE = timedelta(seconds=25)  # 답 생성 중 표시 유효 시간(LLM 20초 + 여유)
SEQ_RETRIES = 5  # 순번(seq) 충돌 시 다시 시도하는 횟수


class MessageIn(BaseModel):
    kind: Literal["text", "hint"]
    text: str | None = Field(default=None, max_length=1000)
    # 끊어 보내기: 프론트가 1.5초 안 조각을 묶어 보낸다(11-11). 오면 text 대신 쓴다
    texts: list[Annotated[str, Field(max_length=1000)]] | None = Field(
        default=None, max_length=MAX_PIECES
    )

    def pieces(self) -> list[str]:
        raw = self.texts if self.texts is not None else [self.text or ""]
        return [t for t in raw if t.strip()]


def build_excerpt(turns: Sequence[tuple[str, str]]) -> str:
    """🔴 발췌: 최근 ±2턴(치환본)을 이어붙여 300자. 넘치면 앞을 자른다(🔴 문장이 끝에 있다).

    팀 결정 ③(보호자 카드에서 발췌를 뺄지)이 나면 이 함수만 바꾼다.
    """
    joined = " / ".join(f"{ROLE_LABEL.get(r, r)}: {t}" for r, t in turns[-EXCERPT_TURNS:])
    if len(joined) <= EXCERPT_MAX:
        return joined
    return "…" + joined[-(EXCERPT_MAX - 1) :]


def _step(
    messages: Sequence[Message], covered: Sequence[Message], phase_started_at: datetime | None
) -> int:
    """이 단계(phase_started_at 이후)의 아이 턴 수. 이번 답이 다루는 조각들은 한 턴.
    생성 시각 = 만료 − 72시간. turn_id가 없는 옛 행은 행마다 한 턴."""
    started = as_utc(phase_started_at)
    covered_ids = {m.id for m in covered}
    turns: set[str] = set()
    for m in messages:
        created = as_utc(m.expires_at)
        if m.role != "child" or created is None or m.id in covered_ids:
            continue
        if started is None or created - MESSAGE_TTL >= started:
            turns.add(m.turn_id or m.id)
    return max(len(turns) + (1 if covered else 0), 1)


def turn_judge(judges: Sequence[str | None]) -> Literal["correct", "wrong"] | None:
    """조각 판정 요약: correct가 하나라도 있으면 correct, 아니면 wrong이 있으면 wrong."""
    if "correct" in judges:
        return "correct"
    if "wrong" in judges:
        return "wrong"
    return None


def _lease_valid(row: Session, now: datetime) -> bool:
    until = as_utc(row.replying_until)
    return until is not None and until > now


async def _claim_lease(db: AsyncSession, row: Session, now: datetime) -> datetime | None:
    """답 생성 표시를 세운다. 조건부 UPDATE라 동시 요청 중 하나만 이긴다. 진 쪽은 None."""
    lease = now + REPLY_LEASE
    res = await db.execute(
        update(Session)
        .where(
            Session.id == row.id,
            or_(Session.replying_until.is_(None), Session.replying_until <= now),
        )
        .values(replying_until=lease)
        .execution_options(synchronize_session=False)
    )
    return lease if cast(CursorResult[Any], res).rowcount == 1 else None


async def _release_lease(db: AsyncSession, session_id: str, lease: datetime) -> None:
    """내가 세운 표시일 때만 푼다(만료 뒤 다른 요청이 이어받았으면 그대로 둔다)."""
    await db.execute(
        update(Session)
        .where(Session.id == session_id, Session.replying_until == lease)
        .values(replying_until=None)
        .execution_options(synchronize_session=False)
    )


async def _open_misconception(db: AsyncSession, student: Student, tag: str, now: datetime) -> None:
    """hint 3 도달 → 오개념 open. UNIQUE(학생, tag)라 이미 있으면(resolved 포함) 그대로 둔다."""
    exists = await db.scalar(
        select(Misconception.id).where(
            Misconception.student_id == student.id, Misconception.tag == tag
        )
    )
    if exists is not None:
        return
    try:
        async with db.begin_nested():
            db.add(Misconception(student_id=student.id, tag=tag, first_wrong_date=seoul_date(now)))
    except IntegrityError:
        pass  # 동시 요청이 먼저 만들었다


def _out(
    row: Session,
    reply: str | None,
    verdict: str | None,
    *,
    queued: bool = False,
    pending: bool = False,
    crisis: dict[str, Any] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    return {
        "reply": reply,
        "source": source,  # live / scripted / fixed. 답이 없으면(queued·버려짐) None
        "judge": verdict,
        "hint_level": row.hint_level,
        "state": row.state,
        "crisis": crisis,
        "queued": queued,
        "pending": pending,
    }


async def _session_messages(db: AsyncSession, session_id: str) -> list[Message]:
    return list(
        (
            await db.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.seq)
                .execution_options(populate_existing=True)
            )
        ).all()
    )


def _unanswered(messages: Sequence[Message]) -> list[Message]:
    """멘토 행과 turn_id를 공유하지 않는 아이 조각 = 아직 답 안 된 조각."""
    answered = {m.turn_id for m in messages if m.role == "mentor" and m.turn_id}
    return [m for m in messages if m.role == "child" and m.turn_id and m.turn_id not in answered]


async def _with_seq_retry[T](
    db: AsyncSession, student: Student, session_id: str, fn: Callable[[], Awaitable[T]]
) -> T:
    """같은 세션에 동시 요청이 오면 seq(UNIQUE)가 겹친다. 진 쪽은 통째로 rollback(반쯤 바뀐
    상태는 커밋되지 않는다)하고 다시 한다. LLM 호출은 이 안에 없어 다시 해도 싸다."""
    for _ in range(SEQ_RETRIES):
        try:
            return await fn()
        except IntegrityError:
            await db.rollback()
            await db.refresh(student)  # rollback이 만료시킨 속성을 비동기로 다시 읽는다
    log.info("message busy session=%s", session_id)
    raise ApiError(409, "busy", "앞의 말을 아직 처리하고 있어요. 잠깐 뒤에 다시 보내 줘.")


async def _active_row(
    db: AsyncSession, session_id: str, student: Student, now: datetime
) -> Session:
    row = await db.get(Session, session_id, populate_existing=True)
    if row is None or row.student_id != student.id:
        raise ApiError(404, "session_not_found", "세션을 찾을 수 없어요.")
    await _expire_row(db, row, now)
    if row.state in FINISHED:
        await db.commit()
        raise ApiError(409, "session_finished", "오늘은 이미 끝났어요. 내일 봐요.")
    return row


@dataclass(frozen=True)
class _Claimed:
    """트랜잭션 1에서 답 생성 표시를 세운 요청. 이 요청이 LLM을 부른다."""

    session_id: str
    lease: datetime
    turn_id: str
    verdict: str | None  # 응답의 judge: 이 요청 조각들의 판정 요약
    reply_only: bool = False  # /reply: 응답 judge도 다룬 조각들의 요약으로


@router.post("/sessions/{session_id}/messages")
async def post_message(
    session_id: str, body: MessageIn, db: Db, now: Now, student: Child, llm: Llm
) -> dict[str, Any]:
    """트랜잭션 1(저장·🔴·판정·답 생성 표시) → 트랜잭션 밖 LLM → 트랜잭션 2(답 저장).
    답 생성 중에 온 text 조각은 흡수(queued, LLM 없음), hint는 409 busy(11-11)."""
    first = await _with_seq_retry(
        db, student, session_id, lambda: _accept(session_id, body, db, now, student)
    )
    if not isinstance(first, _Claimed):
        return first
    return await _reply(db, now, student, llm, first)


@router.post("/sessions/{session_id}/reply")
async def post_reply(session_id: str, db: Db, now: Now, student: Child, llm: Llm) -> dict[str, Any]:
    """답 안 된 조각에 멘토 답 1개(4a, 11-11). 생성 중이면 queued, 조각이 없으면 409."""
    row = await _active_row(db, session_id, student, now)
    if row.state == State.BRIDGE.value:
        # A1: 수다 마감 뒤(다리 놓기)에는 AI가 또 말하지 않는다. 받은 말은 이미 저장·🔴 검사됨(11-12 점검)
        await db.commit()
        return _out(row, None, None)
    if _lease_valid(row, now):
        await db.commit()
        return _out(row, None, None, queued=True)
    if not _unanswered(await _session_messages(db, row.id)):
        await db.commit()
        raise ApiError(409, "nothing_to_reply", "답할 말이 없어요.")
    lease = await _claim_lease(db, row, now)
    await db.commit()
    if lease is None:
        return _out(row, None, None, queued=True)
    # 표시를 잡는 사이에 다른 요청이 이미 답했으면(동시 /reply) 표시를 풀고 답하지 않는다(11-12 점검)
    if not _unanswered(await _session_messages(db, row.id)):
        await _release_lease(db, row.id, lease)
        await db.commit()
        return _out(row, None, None)
    return await _reply(
        db, now, student, llm, _Claimed(row.id, lease, str(uuid.uuid4()), None, reply_only=True)
    )


async def _accept(
    session_id: str, body: MessageIn, db: AsyncSession, now: datetime, student: Student
) -> dict[str, Any] | _Claimed:
    """트랜잭션 1. 짧게: 조각 저장·🔴·판정, 답 생성 표시. LLM은 부르지 않는다."""
    row = await _active_row(db, session_id, student, now)
    pieces = body.pieces() if body.kind == "text" else []
    if body.kind == "text" and not pieces:
        raise ApiError(422, "invalid_request", "보낼 말이 비어 있어요.")

    problem = await db.get(Problem, row.problem_id) if row.problem_id else None
    messages = await _session_messages(db, row.id)
    seq = messages[-1].seq + 1 if messages else 1
    turn_id = str(uuid.uuid4())

    def add_message(role: str, text_redacted: str, verdict: str | None = None) -> None:
        nonlocal seq
        msg = Message.new(
            session_id=row.id,
            seq=seq,
            role=role,
            text_redacted=text_redacted,
            now=now,
            turn_id=turn_id,
            judge=verdict,
        )
        db.add(msg)
        messages.append(msg)
        seq += 1

    if body.kind == "hint":
        # 표시를 먼저 세운다. 진 UPDATE는 아무것도 바꾸지 않아 rollback 없이 거절할 수 있다
        lease = await _claim_lease(db, row, now)
        if lease is None:  # 답을 만드는 중에는 힌트를 기다리게 하지 않고 거절한다
            await db.commit()
            raise ApiError(409, "busy", "앞의 말에 답하고 있어요. 답을 본 뒤 다시 눌러 줘.")
        try:
            new, open_mc = press_hint(_row_state(row))
        except TransitionError:
            await _release_lease(db, row.id, lease)
            await db.commit()
            raise ApiError(409, "hint_unavailable", "지금은 힌트를 쓸 수 없어요.") from None
        row.hint_level = new.hint_level
        if open_mc and problem is not None:
            await _open_misconception(db, student, problem.tag, now)
        await db.commit()
        return _Claimed(row.id, lease, turn_id, None)

    verdicts: list[str | None] = []
    for raw in pieces:
        # 순서(명세 4): 조각마다 키워드 1회(원문은 메모리에서만) → PII 치환 → 치환본만 저장
        trigger = red_keyword(raw)
        redacted = redact(raw, names=[student.nickname])
        verdict = None
        if trigger is None and row.state == State.STUDY.value and problem is not None:
            verdict = judge(redacted, problem.answer)
        add_message("child", redacted, verdict)
        if trigger is not None:  # 답 생성 중이어도 즉시(늦게 온 답은 트랜잭션 2가 버린다)
            return await _crisis(db, row, student, messages, add_message, trigger, now)
        verdicts.append(verdict)

    # 끊어 보낸 🔴 문장("죽고" / "싶어")은 조각 하나씩으로는 안 걸린다. LLM에는 답 안 된
    # 조각이 합쳐져 가므로, 같은 묶음(치환본)을 이어 붙여 한 번 더 본다. 줄바꿈·붙여 쓰기 둘 다.
    open_texts = [m.text_redacted for m in _unanswered(messages)]
    if len(open_texts) > 1:
        trigger = red_keyword("\n".join(open_texts)) or red_keyword("".join(open_texts))
        if trigger is not None:
            return await _crisis(db, row, student, messages, add_message, trigger, now)

    summary = turn_judge(verdicts)
    lease = await _claim_lease(db, row, now)
    await db.commit()
    if lease is None:
        log.info("message queued session=%s pieces=%d", row.id, len(pieces))
        return _out(row, None, summary, queued=True)
    return _Claimed(row.id, lease, turn_id, summary)


async def _mentor_last_hour(db: AsyncSession, now: datetime) -> int:
    """서버 전체 최근 1시간 멘토 답 수. 만료 시각 = 만든 시각 + 72시간이라 그걸로 센다(칸 추가 없음)."""
    since = now - timedelta(hours=1) + MESSAGE_TTL
    count = await db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.role == "mentor", Message.expires_at >= since)
    )
    return count or 0


async def _reply(
    db: AsyncSession, now: datetime, student: Student, llm: LLMAdapter, claim: _Claimed
) -> dict[str, Any]:
    """답 안 된 조각 전부를 한 user 턴으로 LLM에 한 번. 호출은 트랜잭션 밖(쓰기 잠금 없이)."""
    row = await db.get(Session, claim.session_id, populate_existing=True)
    assert row is not None
    problem = await db.get(Problem, row.problem_id) if row.problem_id else None
    messages = await _session_messages(db, row.id)
    covered = _unanswered(messages)
    covered_ids = [m.id for m in covered]
    verdict = turn_judge([m.judge for m in covered])
    if claim.reply_only:
        claim = replace(claim, verdict=verdict)
    history = [
        {"role": m.role, "text": m.text_redacted} for m in messages if m.id not in covered_ids
    ][-RECENT_TURNS:]
    if covered:
        history.append({"role": "child", "text": "\n".join(m.text_redacted for m in covered)})
    phase = cast(Literal["study", "chat", "bridge"], row.state)  # 끝난 상태는 앞에서 걸렀다
    prompt = build_prompt(
        PromptInput(
            phase=phase,
            grade_band=student.grade_band,
            honorific=student.honorific,
            style=student.style,
            polite=student.polite,
            problem_text=problem.text if problem else "",
            hint1=problem.hint1 if problem else "",
            hint2=problem.hint2 if problem else "",
            solution=problem.solution if problem else "",
            hint_level=row.hint_level,
            judge=verdict,
            turns=history,
        )
    )
    req = ReplyRequest(
        scenario=f"day3-{student.style}",
        phase=phase,
        hint_level=row.hint_level,
        step=_step(messages, covered, row.phase_started_at),
        system=prompt.system,
        turns=prompt.turns,
        judge=verdict,
    )
    # 남용 상한(명세 4.11-5): 오늘 세션 또는 서버 전체 최근 1시간 멘토 답이 상한이면 그 턴은 대본.
    # DB에서 센다. LLM 호출 전 트랜잭션 안에서 세어 두고 커밋한다(호출 중 연결을 쥐지 않게)
    over_cap = sum(m.role == "mentor" for m in messages) >= AI_DAILY_MAX or (
        await _mentor_last_hour(db, now) >= AI_HOURLY_MAX
    )
    await db.commit()  # 읽기만 했다. LLM을 기다리는 동안 연결·잠금을 쥐지 않는다
    started = time.monotonic()
    try:
        reply = await (_scripted() if over_cap else llm).reply(req)
        # A4 사후 검사: 풀이 보기(힌트 3) 전·못 맞힌 study에서 정답이 새면 대본으로(폴백과 같은 대본)
        if (
            phase == State.STUDY.value
            and row.hint_level < 3
            and problem is not None
            and contains_answer(reply.text, problem.answer, problem.text)
            and not await is_solved(db, row, problem)
        ):
            log.warning("answer_leak 대체 session=%s source=%s", row.id, reply.source)
            reply = await _scripted().reply(req)
            await db.commit()  # is_solved 읽기 트랜잭션을 닫는다
    except Exception:
        await _release_lease(db, row.id, claim.lease)
        await db.commit()
        raise
    return await _with_seq_retry(
        db,
        student,
        row.id,
        lambda: _save_reply(
            db, student, claim, covered_ids, reply, now, int((time.monotonic() - started) * 1000)
        ),
    )


async def _save_reply(
    db: AsyncSession,
    student: Student,
    claim: _Claimed,
    covered_ids: Sequence[str],
    reply: Reply,
    now: datetime,
    llm_ms: int,
) -> dict[str, Any]:
    """트랜잭션 2. 그사이 🔴·끝이면 답을 버린다. 아니면 답 저장 + 다룬 조각을 같은 턴으로."""
    row = await db.get(Session, claim.session_id, populate_existing=True)
    assert row is not None
    messages = await _session_messages(db, row.id)
    await _release_lease(db, row.id, claim.lease)
    if row.state in FINISHED:
        crisis = None
        if row.state == State.CRISIS.value:
            excerpt = await db.scalar(
                select(Alert.excerpt)
                .where(Alert.session_id == row.id)
                .order_by(Alert.created_at.desc())
                .limit(1)
            )
            crisis = {"excerpt": excerpt, "hotlines": list(HOTLINES)}
        await db.commit()
        log.info("reply dropped session=%s state=%s", row.id, row.state)
        return _out(row, None, claim.verdict, crisis=crisis)
    still_open = {m.id for m in _unanswered(messages)}
    if any(i not in still_open for i in covered_ids):
        # 표시가 만료돼 다른 요청이 이 조각들에 먼저 답했다 → 두 번 답하지 않는다
        await db.commit()
        return _out(row, None, claim.verdict, queued=True)
    for m in messages:
        if m.id in covered_ids:
            m.turn_id = claim.turn_id
    seq = messages[-1].seq + 1 if messages else 1
    db.add(
        Message.new(
            session_id=row.id,
            seq=seq,
            role="mentor",
            text_redacted=reply.text,
            now=now,
            turn_id=claim.turn_id,
        )
    )
    pending = len(still_open) > len(covered_ids)
    await db.commit()
    log.info(
        "message session=%s phase=%s pieces=%d len=%d pending=%s source=%s "
        "in_tokens=%s out_tokens=%s ms=%d",
        row.id,
        row.state,
        len(covered_ids),
        len(reply.text),
        pending,
        reply.source,
        reply.in_tokens,
        reply.out_tokens,
        llm_ms,
    )
    return _out(row, reply.text, claim.verdict, pending=pending, source=reply.source)


async def _crisis(
    db: AsyncSession,
    row: Session,
    student: Student,
    messages: Sequence[Message],
    add_message: Callable[[str, str], None],
    trigger: str,
    now: datetime,
) -> dict[str, Any]:
    """🔴 전이 7. LLM 없이 flag·알림 행·발췌를 같은 트랜잭션에 쓴다(명세 4.2·4.3)."""
    phase = row.state
    new = to_crisis(_row_state(row))
    excerpt = build_excerpt([(m.role, m.text_redacted) for m in messages])
    row.state = new.state.value
    row.deadline_at = new.deadline_at
    row.flag = "red"
    row.end_reason = "crisis"
    row.ended_at = now
    row.replying_until = None  # 생성 중이던 답은 트랜잭션 2에서 버려진다
    db.add(
        Alert.new(
            session_id=row.id, student_id=student.id, trigger=trigger, excerpt=excerpt, now=now
        )
    )
    add_message("mentor", CRISIS_REPLY)
    await db.commit()
    log.warning("crisis session=%s phase=%s len=%d", row.id, phase, len(excerpt))
    return _out(
        row,
        CRISIS_REPLY,
        None,
        crisis={"excerpt": excerpt, "hotlines": list(HOTLINES)},
        source="fixed",
    )


# --- 5·6·7. 전환 · 다리 놓기 · 끝 (명세 4.4·4.5·부록 E) ------------------------------

# 태그 → 보호자·강사가 읽는 한글 이름. 시드 태그 4개(9절). 없는 태그는 코드 그대로.
TAG_NAME = {
    "frac-div-nat": "분수 ÷ 자연수",
    "nat-div-nat": "자연수 ÷ 자연수",
    "frac-div-frac-same": "분모가 같은 분수의 나눗셈",
    "frac-div-frac-diff": "분모가 다른 분수의 나눗셈",
}
QUIZ_COUNT = 3
STUCK_FALLBACK = "막힌 곳 기록 없음"  # 부록 E 요약 ② 실패 시
STUCK_NO_WRONG = "틀린 답 없음"  # 요약 ② 오답 0건(풀이 보기로 넘어간 경우도 맞는 말)
SUMMARY_PHASE = "summary"  # 대본에 없는 단계 → scripted는 FIXED_REPLY → 템플릿


class PhaseIn(BaseModel):
    to: Literal["chat", "bridge"]


class EndIn(BaseModel):
    quiz_problem_id: str | None = None


def next_streak(days: int, last: date | None, today: date) -> int:
    """연속 규칙(명세 3.2). 어제 했으면 +1, 오늘 이미 셌으면 그대로, 그 밖은 1. 프리즈는 규칙만."""
    if last == today:
        return max(days, 1)
    if last is not None and (today - last).days == 1:
        return days + 1
    return 1


def _tag_name(tag: str | None) -> str:
    return TAG_NAME.get(tag or "", tag or "오늘 문제")


def _obj_particle(word: str) -> str:
    """목적격 조사 을/를. 마지막 글자가 한글이고 받침이 있으면 「을」."""
    last = word[-1] if word else ""
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28:
        return "을"
    return "를"


async def _owned_session(
    db: AsyncSession, session_id: str, student: Student, now: datetime
) -> Session:
    """세션 소유 확인 + 마감 전이 먼저(명세 4.2). 없거나 남의 세션이면 404."""
    row = await db.get(Session, session_id)
    if row is None or row.student_id != student.id:
        raise ApiError(404, "session_not_found", "세션을 찾을 수 없어요.")
    await _expire_row(db, row, now)
    return row


async def _judged_texts(
    db: AsyncSession, row: Session, verdict: str, since_seq: int = 0
) -> list[str]:
    """저장된 판정(messages.judge)이 verdict인 아이 조각 치환본. 다시 판정하지 않는다.

    since_seq > 0이면 그 순번 뒤 조각만(여러 문제 세션의 지금 문제)."""
    query = select(Message.text_redacted).where(
        Message.session_id == row.id,
        Message.role == "child",
        Message.judge == verdict,
    )
    if since_seq > 0:
        query = query.where(Message.seq > since_seq)
    return list((await db.scalars(query.order_by(Message.seq))).all())


async def is_solved(db: AsyncSession, row: Session, problem: Problem | None) -> bool:
    """저장된 판정 중 정답이 하나라도 있으면 solved(11-11: 재판정 제거).

    여러 문제 세션이면 지금 문제를 시작한 뒤의 판정만 본다."""
    if problem is None:
        return False
    cur = _current(await _plan(db, row))
    since = cur.start_seq if cur is not None else 0
    return bool(await _judged_texts(db, row, "correct", since))


@router.post("/sessions/{session_id}/phase")
async def post_phase(
    session_id: str, body: PhaseIn, db: Db, now: Now, student: Child
) -> dict[str, Any]:
    row = await _owned_session(db, session_id, student, now)
    if row.state in FINISHED:
        await db.commit()
        raise ApiError(409, "session_finished", "오늘은 이미 끝났어요. 내일 봐요.")
    if row.state != body.to:  # 같은 단계 재요청(수다 마감 직후 끝내기 등)은 그대로 돌려준다
        problem = await db.get(Problem, row.problem_id) if row.problem_id else None
        solved = row.state == State.STUDY.value and await is_solved(db, row, problem)
        try:
            new, streak_inc = enter_phase(
                _row_state(row), body.to, now, solved=solved, timer_scale=config.timer_scale()
            )
        except TransitionError:
            await db.commit()
            raise ApiError(409, "phase_not_allowed", "지금은 그 단계로 갈 수 없어요.") from None
        started = as_utc(row.phase_started_at)
        if row.state == State.STUDY.value and started is not None:  # 같이 풀기를 떠난다
            row.study_sec = int((now - started).total_seconds())
        row.state = new.state.value
        row.phase_started_at = new.phase_started_at
        row.deadline_at = new.deadline_at
        row.streak_applied = new.streak_applied
        if streak_inc:  # 연속 +1은 전환 진입 때 한 번(streak_applied로 중복 방지)
            today = seoul_date(now)
            student.streak_days = next_streak(student.streak_days, student.last_streak_date, today)
            student.last_streak_date = today
    await db.commit()
    deadline = as_utc(row.deadline_at)
    log.info("phase session=%s to=%s", row.id, row.state)
    return {
        "state": row.state,
        "deadline_at": deadline.isoformat() if deadline else None,
        "streak_days": student.streak_days,
        "streak_text": _streak_text(student),
    }


async def _quiz_options(db: AsyncSession, problem: Problem | None) -> list[dict[str, str]]:
    """같은 태그 시드 중 오늘 문제를 뺀 id 순 앞 3개. 칸이 없어 매번 같은 규칙으로 계산한다."""
    if problem is None:
        return []
    rows = (
        await db.scalars(
            select(Problem)
            .where(Problem.tag == problem.tag, Problem.id != problem.id)
            .order_by(Problem.id)
            .limit(QUIZ_COUNT)
        )
    ).all()
    return [{"id": p.id, "text": p.text} for p in rows]  # 정답·힌트는 싣지 않는다


SUMMARY_SYSTEM = (
    "너는 아이의 오늘 수학 풀이 기록을 보고, 어디서 막혔는지 보호자와 선생님이 읽을 "
    "한 구절(20자 안팎)을 쓴다. 정답이나 숫자 답을 쓰지 않는다. 이름을 쓰지 않는다. "
    "아이가 낸 틀린 답만 주어진다."
)


async def _stuck_phrase(
    llm: LLMAdapter, student: Student, row: Session, problem: Problem | None, texts: list[str]
) -> str:
    """요약 ② 막힌 곳. 입력은 저장 판정이 wrong인 study 조각만(수다·정답 제외), 실패하면 템플릿."""
    if problem is None:
        return STUCK_FALLBACK
    answer = problem.answer
    answer_value = parse_value(str(answer.get("value", "")))
    # texts = 저장 판정 "wrong"(숫자·분수 형식의 study 답). 수다는 판정을 저장하지 않는다.
    # exact 문제에서 값만 같은 표기(6/16 등)도 정답 값이라 뺀다.
    attempts = [t for t in texts if parse_value(t) != answer_value]
    if not attempts:  # A8: 틀린 답이 없으면 요약할 막힌 곳이 없다 → LLM 없이 고정 문장
        return STUCK_NO_WRONG
    try:
        out = await llm.reply(
            ReplyRequest(
                scenario=f"day3-{student.style}",
                phase=SUMMARY_PHASE,
                hint_level=row.hint_level,
                step=1,
                system=f"{SUMMARY_SYSTEM}\n문제: {problem.text} / 쓴 힌트 단계: {row.hint_level}",
                turns=[{"role": "child", "text": t} for t in attempts],
            )
        )
    except Exception as exc:  # 원문·응답은 로그에 남기지 않는다
        log.warning("summary fallback session=%s err=%s", row.id, type(exc).__name__)
        return STUCK_FALLBACK
    lines = out.text.strip().splitlines()
    phrase = lines[0].strip() if lines else ""
    leaks = [str(answer.get("value", "")), *answer.get("accepted", [])]
    if not phrase or phrase == FIXED_REPLY or any(s and s in phrase for s in leaks):
        return STUCK_FALLBACK
    return phrase


async def _ensure_bridge(
    db: AsyncSession, llm: LLMAdapter, student: Student, row: Session, problem: Problem | None
) -> None:
    """첫 호출 때 요약 3줄·보호자 한 줄을 만들어 세션 행에 저장한다. 이후엔 저장본."""
    if row.study_summary is not None and row.guardian_line is not None:
        return
    name = _tag_name(problem.tag if problem else None)
    solved = await is_solved(db, row, problem)
    open_tags = (
        await db.scalars(
            select(Misconception.tag)
            .where(Misconception.student_id == student.id, Misconception.status == "open")
            .order_by(Misconception.first_wrong_date, Misconception.tag)
        )
    ).all()
    line3 = "미해결: " + ", ".join(_tag_name(t) for t in open_tags) if open_tags else "미해결 없음"
    prog = await progress(db, row)
    if prog.total > 1:  # 여러 문제 세션(SESSION_PROBLEMS)
        line1 = (
            f"{name} 문제 {prog.total}개 중 {prog.solved}개, "
            f"힌트 {prog.hints}번(풀이 보기 {prog.assisted}개)"
        )
    else:
        line1 = (
            f"{name} 문제 1개, 힌트 {row.hint_level}단계에서 {'정답' if solved else '풀이 보기'}"
        )
    row.study_summary = [
        line1,
        await _stuck_phrase(llm, student, row, problem, await _judged_texts(db, row, "wrong")),
        line3,
    ]
    row.guardian_line = f"오늘 {name}{_obj_particle(name)} 다시 풀었어요."
    await db.flush()


@router.get("/sessions/{session_id}/bridge")
async def get_bridge(session_id: str, db: Db, now: Now, student: Child, llm: Llm) -> dict[str, Any]:
    row = await _owned_session(db, session_id, student, now)
    if row.state not in (State.BRIDGE.value, State.ENDED.value):
        await db.commit()
        raise ApiError(409, "phase_not_allowed", "아직 다리 놓기 단계가 아니에요.")
    problem = await db.get(Problem, row.problem_id) if row.problem_id else None
    await _ensure_bridge(db, llm, student, row, problem)
    quiz = await _quiz_options(db, await _quiz_base(db, row))
    await db.commit()
    log.info("bridge session=%s state=%s", row.id, row.state)
    return {
        "quiz_options": quiz,
        "guardian_line": row.guardian_line,
        "summary": list(row.study_summary or []),
    }


@router.post("/sessions/{session_id}/end")
async def post_end(
    session_id: str, body: EndIn, db: Db, now: Now, student: Child, llm: Llm
) -> dict[str, Any]:
    row = await _owned_session(db, session_id, student, now)
    if row.state in FINISHED:
        await db.commit()
        raise ApiError(409, "session_finished", "오늘은 이미 끝났어요. 내일 봐요.")
    try:
        new = end(_row_state(row))
    except TransitionError:
        await db.commit()
        raise ApiError(409, "phase_not_allowed", "다리 놓기에서만 끝낼 수 있어요.") from None
    problem = await db.get(Problem, row.problem_id) if row.problem_id else None
    if body.quiz_problem_id is not None:
        allowed = {q["id"] for q in await _quiz_options(db, await _quiz_base(db, row))}
        if body.quiz_problem_id not in allowed:
            await db.commit()
            raise ApiError(422, "invalid_request", "고를 수 있는 퀴즈가 아니에요.")
    await _ensure_bridge(db, llm, student, row, problem)  # 카드 저장(아직 안 만들었으면 여기서)
    row.quiz_problem_id = body.quiz_problem_id
    row.state = new.state.value
    row.deadline_at = new.deadline_at
    row.ended_at = now
    row.end_reason = "normal"
    await db.commit()
    log.info("end session=%s quiz=%s", row.id, body.quiz_problem_id is not None)
    return {"state": row.state, "streak_text": _streak_text(student)}


# --- 13. PUT /me/mentor ---------------------------------------------------------------


class MentorIn(BaseModel):
    style: Literal["EBSP", "EQLC", "DQSC"]
    honorific: Literal["hyung", "unni", "friend"]
    polite: StrictBool


@router.put("/me/mentor")
async def put_mentor(body: MentorIn, db: Db, now: Now, student: Child) -> dict[str, Any]:
    """캐릭터 고르기 「시작하기」. 대화 중에는 바꾸지 않는다(새 세션에서만)."""
    session = await _today_session(db, student, now)
    if session is not None and State(session.state) in ACTIVE:
        await db.commit()
        raise ApiError(409, "session_in_progress", "오늘 대화가 끝난 뒤에 바꿀 수 있어요.")
    student.style = body.style
    student.honorific = body.honorific
    student.polite = body.polite
    await db.commit()
    return body.model_dump()
