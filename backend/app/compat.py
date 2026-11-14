"""프론트 v0.5 호환 라우터 `/api/v1/compat` (11-15까지 임시).

프론트(src/api/http.ts)의 경로·JSON 모양(src/types.ts, camelCase) 그대로 응답한다.
- 판단은 새로 만들지 않는다. 전환·힌트·판정·마감은 기존 api.py 핸들러와 state_machine을 그대로 부른다.
- 신원은 기존과 같은 X-Demo-Role·X-Demo-Actor 헤더(current_child / current_guardian_child /
  current_instructor).
- 문제 화면에 정답·풀이를 싣지 않는다. 풀이는 hint_level 3(풀이 보기)에서만 준다.
- 오류는 기존 {code, message, request_id}에 프론트가 읽는 `detail`(= message)만 덧붙인다.
- 한 세션 문제 수는 SESSION_PROBLEMS(기본 1 → total 1). 난이도는 시드에 없어 받기만 하고 버린다.
"""

import math
import re
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.accounts import CurrentAccount, connected_ids, is_restricted
from app.actors import Actor
from app.api import (
    FINISHED,
    HOTLINES,
    TAG_NAME,
    Child,
    Db,
    EndIn,
    Llm,
    MentorIn,
    MessageIn,
    Now,
    PhaseIn,
    _accept,
    _Claimed,
    _lease_valid,
    _open_misconception,
    _owned_session,
    _plan_ids,
    _quiz_base,
    _quiz_options,
    _release_lease,
    _row_state,
    _today_session,
    _today_task,
    _with_seq_retry,
    get_bridge,
    is_solved,
    next_streak,
    plan_position,
    post_end,
    post_message,
    post_phase,
    post_reply,
    progress,
    put_mentor,
    start_session,
    sync_progress,
)
from app.demo import ResetBody, _write_day3_student
from app.errors import ApiError, _body
from app.guardian import GuardianChild, guardian_today
from app.instructor import (
    TEXT_MAX,
    ApproveIn,
    DraftAdapter,
    Instructor,
    NoteIn,
    TodayTaskIn,
    _student_or_404,
    _today_note,
    approve_note,
    post_note,
    put_today_task,
    update_draft_body,
)
from app.models import MESSAGE_TTL, Alert, InstructorNote, Message, Problem, Session, Student
from app.models_org import Account, Room
from app.pii import unredact_name
from app.safety import check as red_keyword
from app.seed import load_seed
from app.seeds import (
    STUDY_DONE,
    balance_of,
    earn_study_seeds,
    earned_on,
    in_class,
    selected_unit_names,
    stamps_of,
)
from app.state_machine import (
    MAX_HINT,
    State,
    TransitionError,
    press_hint,
    study_remaining_sec,
    study_time_over,
)
from app.timeutil import SEOUL, as_utc, seoul_date
from app.trial import ACCOUNT_PREFIX, TRIAL_HOURLY_MAX, TRIAL_PREFIX, new_trial_id


class _CompatRoute(APIRoute):
    """이 라우터의 오류 응답에만 `detail`을 함께 싣는다(프론트 http.ts가 detail을 읽는다)."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        inner = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await inner(request)
            except ApiError as exc:
                body = _body(exc.code, exc.message)
                return JSONResponse({**body, "detail": exc.message}, status_code=exc.status)
            except RequestValidationError:
                # 입력값(아이 원문일 수 있음)은 싣지 않는다
                msg = "요청 형식이 맞지 않아요."
                return JSONResponse({**_body("invalid_request", msg), "detail": msg}, 422)

        return handler


router = APIRouter(prefix="/compat", route_class=_CompatRoute)

# 아이가 🔴으로 끝난 날 보호자 첫 화면 안내. 문구는 여기 한곳만 바꾸면 된다(11-11, 성호 결정 대기)
GUARDIAN_ALERT_NOTICE = "오늘 확인이 필요한 알림이 있어요"
DIFFICULTY = "중급"  # 시드에 난이도가 없다. 프론트 타입을 채우는 표시용 고정값
STUDY_SEC = 20 * 60  # 명세 3.2 「같이 풀기 ~20분」. 남은 초는 state_machine.study_remaining_sec
TASK_MINUTES = 20
HINT_COUNT = MAX_HINT - 1  # 힌트 1·2. 3은 풀이 보기
WEEKDAY = "월화수목금토일"
ASSIGNED_BY = {"instructor": "선생님", "misconception": "친구1"}
STYLE_LABEL = {"EBSP": "같이 풀어주는", "EQLC": "들어주는", "DQSC": "짚어주는"}
TITLE_LABEL = {"hyung": "형", "unni": "언니", "friend": "친구"}
_OPERAND = r"\(?(\d+)(?:/(\d+))?\)?"
_EXPR = re.compile(rf"{_OPERAND} / {_OPERAND}")


_CHOICE_LINE = re.compile(r"^\s*([①②③④])\s*(.+?)\s*$")


def _answer_view(problem: Problem) -> tuple[str, str, list[str] | None]:
    """(answerKind, 화면에 보일 문제 글, 보기). 정답은 싣지 않는다.

    - fraction: 시드처럼 분수 칸(기존 그대로). value 답이 분수이거나 식을 두 분수로 나눌 수 있을 때
    - number: value 답이 자연수이고 분수 식이 아닐 때(큰 수 등) → 숫자 한 칸
    - choice: 문제 글의 ①~④ 줄을 보기 버튼으로 떼어 낸다
    - text: 낱말 한 개를 쓴다
    """
    kind = (problem.answer or {}).get("kind")
    if kind == "choice":
        stem, choices = [], []
        for line in problem.text.split("\n"):
            m = _CHOICE_LINE.match(line)
            if m:
                choices.append(m[2])
            elif not line.strip().startswith(
                "(번호"
            ):  # 「(번호를 … 써 주세요)」 안내는 버튼이 대신한다
                stem.append(line)
        if len(choices) >= 2:
            return "choice", "\n".join(stem).strip(), choices
        return "choice", problem.text, None
    if kind == "text":
        return "text", problem.text, None
    value = str((problem.answer or {}).get("value", ""))
    if value.isdigit() and _operands(problem.expr) == (None, None):
        return "number", problem.text, None
    return "fraction", problem.text, None


def _answer_lang(problem: Problem) -> str | None:
    """낱말 답의 글자(en = 영어 낱말, ko = 한글 낱말). 화면이 「영어로 써 줘」를 고르게만 쓴다(답 자체는 안 실음)."""
    words = [str(problem.answer.get("value", "")), *problem.answer.get("accepted", [])]
    words = [w for w in words if w]
    if words and all(re.fullmatch(r"[A-Za-z' -]+", w) for w in words):
        return "en"
    if words and all(re.search(r"[가-힣]", w) for w in words):
        return "ko"
    return None


def _tag_name(problem: Problem | None) -> str:
    return TAG_NAME.get(problem.tag, problem.tag) if problem else "오늘 문제"


def _date_label(now: datetime) -> str:
    d = seoul_date(now)
    return f"{d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일"


def _attendance(student: Student, now: datetime) -> list[bool]:
    """이번 주 월~일. 연속 칸(마지막 날·일수)으로 거꾸로 센다(따로 저장한 출석표는 없다)."""
    today = seoul_date(now)
    monday = today - timedelta(days=today.weekday())
    last = student.last_streak_date
    days = (
        {last - timedelta(days=i) for i in range(student.streak_days)}
        if last is not None
        else set()
    )
    return [monday + timedelta(days=i) in days for i in range(7)]


def _phase(row: Session, solved: bool) -> str:
    """내부 상태 → 프론트 Phase. study에서 정답이거나 풀이 보기(hint 3)면 transition."""
    if row.state == State.STUDY.value:
        return "transition" if solved or row.hint_level >= MAX_HINT else "solve"
    return {"chat": "chat", "bridge": "wrap", "ended": "done", "crisis": "crisis"}[row.state]


def _shown_streak(row: Session, student: Student, phase: str, now: datetime) -> int:
    """완료 화면(transition)은 다음 전환에서 셀 연속 일수를 미리 보여 준다(3 → 4 어긋남, 11-11).

    실제 +1은 그대로 전환 진입 때 한 번(streak_applied). 화면 숫자만 맞춘다.
    """
    if phase == "transition" and not row.streak_applied:
        return next_streak(student.streak_days, student.last_streak_date, seoul_date(now))
    return student.streak_days


def _seconds_left(until: datetime | None, now: datetime) -> int:
    return max(0, math.ceil((until - now).total_seconds())) if until is not None else 0


async def _problem(db: AsyncSession, row: Session) -> Problem | None:
    return await db.get(Problem, row.problem_id) if row.problem_id else None


async def _view(db: AsyncSession, row: Session, student: Student, now: datetime) -> dict[str, Any]:
    # 여러 문제 세션: 지금 문제를 끝냈으면 먼저 다음 문제로(기본 1문제면 아무것도 안 한다)
    await sync_progress(db, row, now)
    problem = await _problem(db, row)
    solved = await is_solved(db, row, problem)
    prog = await progress(db, row)
    started = as_utc(row.phase_started_at)
    in_study = row.state == State.STUDY.value and started is not None
    # study 밖에서는 study를 떠날 때 저장한 초(11-11, 전에는 0이 됐다)
    study_sec = (now - started).total_seconds() if in_study and started else row.study_sec or 0
    phase = _phase(row, solved)
    return {
        "id": row.id,
        "phase": phase,
        "unit": _tag_name(problem),
        "difficulty": DIFFICULTY,
        "solved": prog.solved,
        "total": prog.total,
        "assisted": prog.assisted,
        "hintsUsed": prog.hints,
        "studyMin": math.ceil(study_sec / 60),
        # 0이면 서버가 풀이 보기·수다로 넘어가기를 연다(같은 함수, 명세 4.11-4)
        "studyRemainingSec": study_remaining_sec(started, now, config.timer_scale())
        if in_study
        else 0,
        "chatRemainingSec": _seconds_left(as_utc(row.deadline_at), now),
        "timedOut": in_study and study_time_over(started, now, config.timer_scale()),
        "streakDays": _shown_streak(row, student, phase, now),
    }


async def _session_view(
    db: AsyncSession, session_id: str, student: Student, now: datetime
) -> dict[str, Any]:
    row = await _owned_session(db, session_id, student, now)
    view = await _view(db, row, student, now)
    await db.commit()
    return view


def _hints(problem: Problem, hint_level: int) -> list[str]:
    return [problem.hint1, problem.hint2][: min(hint_level, HINT_COUNT)]


def _hint_state(hint_level: int, timed_out: bool = False) -> dict[str, Any]:
    """timed_out(같이 풀기 20분 지남)이면 힌트 수와 무관하게 풀이 보기를 연다."""
    return {
        "hintsLeft": max(0, HINT_COUNT - hint_level),
        "canShowSolution": (timed_out or HINT_COUNT <= hint_level) and hint_level < MAX_HINT,
    }


def _operands(expr: str) -> tuple[list[int] | None, list[int] | None]:
    """시드 expr "a/b / c" → 분수 칸. 괄호 안 덧셈 같은 모양은 None(프론트는 text로 보여야 한다)."""
    m = _EXPR.fullmatch(expr.strip())
    if m is None:
        return None, None
    return [int(m[1]), int(m[2] or 1)], [int(m[3]), int(m[4] or 1)]


# --- 학생: 준비 ----------------------------------------------------------------------


@router.get("/student/home")
async def student_home(db: Db, now: Now, student: Child, account: CurrentAccount) -> dict[str, Any]:
    session = await _today_session(db, student, now)
    task = None if session is not None else await _today_task(db, student)
    task_info = None
    if task is not None:
        problem = await db.get(Problem, task[0])
        task_info = {
            "unit": _tag_name(problem),
            "count": len(await _plan_ids(db, task[0])),  # 기본 1(SESSION_PROBLEMS)
            "minutes": TASK_MINUTES,
            "assignedBy": ASSIGNED_BY[task[1]],
        }
    view = await _view(db, session, student, now) if session is not None else None
    # 계정 학생이면 보호자 연결 전 = 제한 모드(명세 4.12-5). 체험 헤더 경로는 전과 같이 False
    restricted = account is not None and await is_restricted(db, account.id)
    # 씨앗·강의실은 새 테이블에서(명세 4.12). 체험 헤더 경로의 inClass는 전과 같이 True
    seeds = await balance_of(db, student.id)
    stamps = await stamps_of(db, student.id)
    earned = await earned_on(db, student.id, STUDY_DONE, seoul_date(now))
    joined = await in_class(db, student.id) if account is not None else True
    await db.commit()
    return {
        "name": student.nickname,
        "dateLabel": _date_label(now),
        "streakDays": student.streak_days,
        "attendance": _attendance(student, now),
        "todayIndex": seoul_date(now).weekday(),
        "task": task_info,
        "needsOnboarding": not student.consent,  # 약속 화면 동의 전이면 true
        "session": view,
        "doneToday": session is not None and session.state in FINISHED,
        # 오늘 세션이 🔴로 끝났으면 true(계약 #2, 11-11). 홈에서 다시 시작하지 않게 한다
        "endedInCrisis": session is not None and session.state == State.CRISIS.value,
        "restricted": restricted,
        "inClass": joined,
        "seeds": seeds,
        "stamps": stamps,
        "earnedToday": earned,
    }


@router.post("/student/promise", status_code=204)
async def accept_promise(db: Db, student: Child) -> None:
    """약속 화면 「약속할게」 = 동의 저장(AI 사용·🔴 보호자 알림 고지 1회)."""
    student.consent = True
    await db.commit()


@router.get("/student/mentor")
async def get_mentor(student: Child) -> dict[str, Any]:
    # 그림(띠)은 저장 칸이 없어 null — 스타일 코드와 분리(팀 결정 11-09)
    return {
        "style": STYLE_LABEL[student.style],
        "title": TITLE_LABEL[student.honorific],
        "speech": "존댓말" if student.polite else "반말",
        "animal": None,
    }


class MentorSettingIn(BaseModel):
    style: Literal["같이 풀어주는", "들어주는", "짚어주는"]
    title: Literal["형", "언니", "친구"]
    speech: Literal["반말", "존댓말"]
    animal: str | None = None  # 받기만 하고 저장하지 않는다


@router.put("/student/mentor")
async def save_mentor(body: MentorSettingIn, db: Db, now: Now, student: Child) -> dict[str, Any]:
    style = {v: k for k, v in STYLE_LABEL.items()}[body.style]
    honorific = {v: k for k, v in TITLE_LABEL.items()}[body.title]
    mentor = MentorIn.model_validate(
        {"style": style, "honorific": honorific, "polite": body.speech == "존댓말"}
    )
    await put_mentor(mentor, db, now, student)
    return await get_mentor(student)


# --- 학생: 하루 세션 -------------------------------------------------------------------


@router.get("/sessions/active")
async def active_session(db: Db, now: Now, student: Child) -> dict[str, Any] | None:
    session = await _today_session(db, student, now)
    view = await _view(db, session, student, now) if session is not None else None
    await db.commit()
    return view


class StartIn(BaseModel):
    difficulty: str | None = None  # 시드에 난이도가 없어 쓰지 않는다


@router.post("/sessions")
async def start(db: Db, now: Now, student: Child, _: StartIn | None = None) -> dict[str, Any]:
    started = await start_session(db, now, student)
    return await _session_view(db, started["session_id"], student, now)


@router.get("/sessions/{session_id}/problem")
async def get_problem(session_id: str, db: Db, now: Now, student: Child) -> dict[str, Any] | None:
    row = await _owned_session(db, session_id, student, now)
    await sync_progress(db, row, now)
    problem = await _problem(db, row)
    solved = await is_solved(db, row, problem)
    index, total = await plan_position(db, row)
    await db.commit()
    if problem is None or _phase(row, solved) != "solve":
        return None  # 풀기 단계가 끝났다
    left, right = _operands(problem.expr)
    answer_kind, text, choices = _answer_view(problem)
    if answer_kind != "fraction":
        left = right = None  # 분수 식 그림은 분수 문제에만
    started = as_utc(row.phase_started_at)
    scale = config.timer_scale()
    return {
        "id": problem.id,
        "index": index,
        "total": total,
        "text": text,  # 나눗셈 문장제. 프론트 left/op/right 대신 보여야 한다. choice면 보기 줄은 뺀다
        "answerKind": answer_kind,  # fraction / number / choice / text — 화면이 입력 칸을 고른다
        "choices": choices,  # choice일 때 보기 문구(①부터 순서대로), 아니면 None
        "answerLang": _answer_lang(problem) if answer_kind == "text" else None,  # en / ko
        "left": left,
        "right": right,
        "op": "÷",
        "hints": _hints(problem, row.hint_level),
        **_hint_state(row.hint_level, study_time_over(started, now, scale)),
        "remainingSec": study_remaining_sec(started, now, scale),
    }


class AnswerIn(BaseModel):
    problemId: str
    numerator: int | None = None  # 분수 칸(시드)
    denominator: int | None = None
    answer: str | None = Field(default=None, max_length=40)  # 숫자 한 칸·보기 기호·낱말

    def as_text(self) -> str | None:
        if self.answer is not None and self.answer.strip():
            return self.answer.strip()
        if self.numerator is not None and self.denominator is not None:
            return f"{self.numerator}/{self.denominator}"
        return None


@router.post("/sessions/{session_id}/answer")
async def submit_answer(
    session_id: str, body: AnswerIn, db: Db, now: Now, student: Child, llm: Llm
) -> dict[str, Any]:
    row = await _owned_session(db, session_id, student, now)
    await sync_progress(db, row, now)
    problem = await _problem(db, row)
    solved = await is_solved(db, row, problem)
    if problem is None or body.problemId != problem.id or _phase(row, solved) != "solve":
        # 이미 지난 문제 → 빈 message(프론트는 세션을 다시 읽는다)
        view = await _view(db, row, student, now)
        await db.commit()
        return {
            "correct": False,
            "numeratorOk": False,
            "denominatorOk": False,
            "message": "",
            "autoHint": None,
            **_hint_state(row.hint_level),
            "queued": False,
            "pending": False,
            "source": None,
            "session": view,
        }
    text = body.as_text()
    if text is None:
        raise ApiError(422, "invalid_request", "답을 넣어 주세요.")
    try:
        msg = MessageIn(kind="text", text=text)
    except ValidationError:  # 터무니없이 큰 수(11-12 점검: 500이던 것)
        raise ApiError(422, "invalid_request", "요청 형식이 맞지 않아요.") from None
    out = await post_message(session_id, msg, db, now, student, llm)
    correct = out["judge"] == "correct"  # 저장된 판정(흡수돼도 판정은 즉시)
    return {
        "correct": correct,
        "numeratorOk": correct,  # 부분 판정은 없다
        "denominatorOk": correct,
        "message": out["reply"] or "",  # queued면 앞 답을 기다리는 중이라 빈 문장
        "autoHint": None,  # 힌트는 버튼으로만(명세 3.2)
        **_hint_state(out["hint_level"]),
        "queued": out["queued"],  # true면 화면을 넘기지 말고 pending을 기다린다(B7)
        "pending": out["pending"],
        "source": out["source"],  # live / scripted / fixed, queued면 None(B1)
        "session": await _session_view(db, session_id, student, now),
    }


class ProblemRef(BaseModel):
    problemId: str | None = None


async def _press(
    db: AsyncSession, row: Session, student: Student, problem: Problem, now: datetime
) -> None:
    """힌트 버튼 = 전이 2. hint 3 도달이면 오개념 open(api.py와 같은 함수)."""
    try:
        new, open_mc = press_hint(_row_state(row))
    except TransitionError:
        await db.commit()
        raise ApiError(409, "hint_unavailable", "지금은 힌트를 쓸 수 없어요.") from None
    row.hint_level = new.hint_level
    if open_mc:
        await _open_misconception(db, student, problem.tag, now)


async def _solving(
    db: AsyncSession, session_id: str, student: Student, now: datetime
) -> tuple[Session, Problem]:
    row = await _owned_session(db, session_id, student, now)
    if _lease_valid(row, now):  # 답 생성 중: 기본 경로 kind:hint와 같이 409(계약 프론트 할 일 9)
        await db.commit()
        raise ApiError(409, "busy", "앞의 말에 답하고 있어요. 답을 본 뒤 다시 눌러 줘.")
    await sync_progress(db, row, now)
    problem = await _problem(db, row)
    if problem is None or _phase(row, await is_solved(db, row, problem)) != "solve":
        await db.commit()
        raise ApiError(409, "hint_unavailable", "지금은 힌트를 쓸 수 없어요.")
    return row, problem


@router.post("/sessions/{session_id}/hint")
async def request_hint(
    session_id: str, db: Db, now: Now, student: Child, _: ProblemRef | None = None
) -> dict[str, Any]:
    row, problem = await _solving(db, session_id, student, now)
    if row.hint_level >= HINT_COUNT:  # 힌트 2개를 다 썼다 → 「풀이 같이 보기」로
        await db.commit()
        raise ApiError(409, "hint_unavailable", "힌트를 다 썼어요. 풀이를 같이 봐요.")
    await _press(db, row, student, problem, now)
    await db.commit()
    return {
        "hints": _hints(problem, row.hint_level),
        "hintsLeft": max(0, HINT_COUNT - row.hint_level),
    }


@router.post("/sessions/{session_id}/solution")
async def show_solution(
    session_id: str, db: Db, now: Now, student: Child, _: ProblemRef | None = None
) -> dict[str, Any]:
    """풀이 보기 = hint_level 3. 힌트 1·2를 다 쓴 뒤에만(명세 3.2 「답을 먼저 주지 않는다」).

    같이 풀기 20분이 지났으면 힌트 수와 무관하게 연다(명세 4.11-4, 막다른 화면 금지).
    """
    row, problem = await _solving(db, session_id, student, now)
    over = study_time_over(as_utc(row.phase_started_at), now, config.timer_scale())
    if row.hint_level < HINT_COUNT:
        if not over:
            await db.commit()
            raise ApiError(409, "solution_unavailable", "힌트를 먼저 써 봐요.")
        row.hint_level = HINT_COUNT  # 남은 힌트를 건너뛴다. 아래 _press가 3으로 올리고 오개념 open
    await _press(db, row, student, problem, now)
    await db.commit()
    return {
        "steps": [problem.solution],
        "session": await _session_view(db, session_id, student, now),
    }


class AfterStudyIn(BaseModel):
    choice: Literal["chat", "skip"]


@router.post("/sessions/{session_id}/after-study")
async def after_study(
    session_id: str, body: AfterStudyIn, db: Db, now: Now, student: Child, account: CurrentAccount
) -> dict[str, Any]:
    # 계정 학생만: 보호자와 연결 전이면 수다를 막는다(설계 §9-8). 체험 헤더 경로는 그대로
    if (
        body.choice == "chat"
        and account is not None
        and account.role == "student"
        and await is_restricted(db, account.id)
    ):
        raise ApiError(409, "restricted", "보호자와 연결한 뒤에 수다를 할 수 있어요.")
    to: Literal["chat", "bridge"] = "chat" if body.choice == "chat" else "bridge"
    await post_phase(session_id, PhaseIn(to=to), db, now, student)
    # 학습 완료 씨앗(하루 1번, org.ts earnStudySeeds): 같이 풀기를 끝냈을 때(정답 또는 풀이 보기)만
    row = await _owned_session(db, session_id, student, now)
    if row.state != State.STUDY.value:
        problem = await _problem(db, row)
        # 여러 문제면 한 문제라도 끝냈을 때(한 문제면 예전과 같은 조건)
        if (await progress(db, row)).solved > 0:
            await earn_study_seeds(db, student.id, _tag_name(problem), now)
    return await _session_view(db, session_id, student, now)


@router.get("/sessions/{session_id}/chat")
async def get_chat(session_id: str, db: Db, now: Now, student: Child) -> dict[str, Any]:
    """수다 단계(phase_started_at 이후) 메시지만. 풀이 단계의 답은 싣지 않는다."""
    row = await _owned_session(db, session_id, student, now)
    started = as_utc(row.phase_started_at)
    messages: list[dict[str, str]] = []
    if row.state == State.CHAT.value and started is not None:
        rows = await db.scalars(
            select(Message).where(Message.session_id == row.id).order_by(Message.seq)
        )
        # 아이 말은 화면에 보이기 직전에만 자기 별명으로 되돌린다(TK-106). 저장본·프롬프트는 치환본
        messages = [
            {"from": "me", "text": unredact_name(m.text_redacted, student.nickname) or ""}
            if m.role == "child"
            else {"from": "mentor", "text": m.text_redacted}
            for m in rows
            if (created := as_utc(m.expires_at)) is not None and created - MESSAGE_TTL >= started
        ]
    remaining = _seconds_left(as_utc(row.deadline_at), now)
    await db.commit()
    return {"messages": messages, "remainingSec": remaining}


class ChatIn(BaseModel):
    text: str | None = Field(default=None, max_length=1000)
    texts: list[str] | None = None  # 1.5초 묶음(11-11). 길이·개수 검사는 MessageIn이 한다


@router.post("/sessions/{session_id}/chat")
async def send_chat(
    session_id: str, body: ChatIn, db: Db, now: Now, student: Child, llm: Llm
) -> dict[str, Any]:
    row = await _owned_session(db, session_id, student, now)  # 수다 마감이 지났으면 bridge로
    # 끝난 세션(ended·crisis)·빈 말은 아래 post_message가 기본 경로와 같은 409·422로 거절한다
    if row.state == State.STUDY.value:
        # 아직 수다 전 단계 → 빈 답(프론트는 단계를 다시 맞춘다). 다만 🔴 문장은 그냥 버리지 않고
        # 기본 경로(_accept)로 보내 위기 처리를 거친다(단계가 어긋난 화면, 11-12 점검). 원문은 메모리에서만
        pieces = [t for t in (body.texts or [body.text or ""]) if t and t.strip()]
        if any(red_keyword(t) for t in pieces) or (
            len(pieces) > 1 and (red_keyword("\n".join(pieces)) or red_keyword("".join(pieces)))
        ):
            try:
                msg = MessageIn(kind="text", texts=pieces)
            except ValidationError:
                raise ApiError(422, "invalid_request", "요청 형식이 맞지 않아요.") from None
            return await _bridge_chat(db, session_id, msg, student, now)
        view = await _view(db, row, student, now)
        await db.commit()
        return _empty_chat(view)
    try:
        msg = MessageIn(kind="text", text=body.text, texts=body.texts)
    except ValidationError:
        raise ApiError(422, "invalid_request", "요청 형식이 맞지 않아요.") from None
    if row.state == State.BRIDGE.value:
        return await _bridge_chat(db, session_id, msg, student, now)
    out = await post_message(session_id, msg, db, now, student, llm)
    return await _chat_out(db, session_id, student, now, out)


def _empty_chat(view: dict[str, Any]) -> dict[str, Any]:
    return {
        "reply": "",
        "crisis": False,
        "hotlines": [],
        "queued": False,
        "pending": False,
        "source": None,
        "session": view,
    }


async def _bridge_chat(
    db: AsyncSession, session_id: str, msg: MessageIn, student: Student, now: datetime
) -> dict[str, Any]:
    """A1(11-11): 수다 마감 뒤(다리 놓기)에 온 말. 기본 경로 트랜잭션 1(_accept: 치환본 저장·
    🔴 키워드·crisis 처리)을 그대로 거치고, LLM은 부르지 않는다(마감 뒤 AI가 또 말하지 않게)."""
    out = await _with_seq_retry(
        db, student, session_id, lambda: _accept(session_id, msg, db, now, student)
    )
    if isinstance(out, _Claimed):  # 답 생성 표시를 세웠지만 답하지 않는다 → 바로 푼다
        await _release_lease(db, out.session_id, out.lease)
        await db.commit()
    elif out["crisis"] is not None:
        return await _chat_out(db, session_id, student, now, out)
    return _empty_chat(await _session_view(db, session_id, student, now))


async def _chat_out(
    db: AsyncSession, session_id: str, student: Student, now: datetime, out: dict[str, Any]
) -> dict[str, Any]:
    crisis = out["crisis"] is not None
    return {
        "reply": out["reply"] or "",  # queued·버려진 답이면 빈 문장
        "crisis": crisis,
        "hotlines": list(HOTLINES) if crisis else [],
        "queued": out["queued"],
        "pending": out["pending"],
        "source": out["source"],  # live / scripted / fixed, queued·버려진 답이면 None
        "session": await _session_view(db, session_id, student, now),
    }


@router.post("/sessions/{session_id}/reply")
async def reply_more(session_id: str, db: Db, now: Now, student: Child, llm: Llm) -> dict[str, Any]:
    """pending이면 프론트가 부른다: 흡수된 조각에 답 하나 더(#4a)."""
    out = await post_reply(session_id, db, now, student, llm)
    return await _chat_out(db, session_id, student, now, out)


@router.post("/sessions/{session_id}/chat/end")
async def end_chat(session_id: str, db: Db, now: Now, student: Child) -> dict[str, Any]:
    await post_phase(session_id, PhaseIn(to="bridge"), db, now, student)
    return await _session_view(db, session_id, student, now)


@router.get("/sessions/{session_id}/wrap")
async def get_wrap(session_id: str, db: Db, now: Now, student: Child, llm: Llm) -> dict[str, Any]:
    bridge = await get_bridge(session_id, db, now, student, llm)
    view = await _session_view(db, session_id, student, now)
    return {
        "unit": view["unit"],
        "solved": view["solved"],
        "total": view["total"],
        "difficulty": DIFFICULTY,
        "studyMin": view["studyMin"],
        "chatMin": 0,  # 수다 시간은 따로 저장하지 않는다
        "streakDays": student.streak_days,
        "aiLine": bridge["guardian_line"],
        "hardChips": [],  # 「어려웠던 점」은 명세·DB에 칸이 없다
        "quizOptions": [q["text"] for q in bridge["quiz_options"]],
    }


class WrapIn(BaseModel):
    hardPoint: str | None = Field(default=None, max_length=30)  # 저장 칸이 없어 버린다(🔴 검사 뒤)
    quiz: str | None = None


@router.post("/sessions/{session_id}/wrap")
async def submit_wrap(
    session_id: str, body: WrapIn, db: Db, now: Now, student: Child, llm: Llm
) -> dict[str, Any]:
    # 11-14 점검 B4: 아이가 직접 쓴 「어려웠던 점」도 입력이다 → 키워드 1회. 걸리면 수다와 같은 위기 경로
    # (치환본 저장·세션 crisis·보호자 알림). 안 걸리면 지금처럼 버린다. 원문은 메모리에서만
    if body.hardPoint and body.hardPoint.strip() and red_keyword(body.hardPoint):
        await _bridge_chat(
            db, session_id, MessageIn(kind="text", text=body.hardPoint), student, now
        )
        return await _session_view(db, session_id, student, now)
    quiz_id = None
    if body.quiz is not None:  # 프론트는 문장으로 고른다 → 같은 태그 퀴즈 후보에서 id로
        row = await _owned_session(db, session_id, student, now)
        options = await _quiz_options(db, await _quiz_base(db, row))
        quiz_id = next((q["id"] for q in options if q["text"] == body.quiz), None)
        if quiz_id is None:
            await db.commit()
            raise ApiError(422, "invalid_request", "고를 수 있는 퀴즈가 아니에요.")
    await post_end(session_id, EndIn(quiz_problem_id=quiz_id), db, now, student, llm)
    return await _session_view(db, session_id, student, now)


# --- 보호자 ---------------------------------------------------------------------------


@router.get("/guardian/today")
async def get_guardian_today(
    db: Db, now: Now, student: GuardianChild, account: CurrentAccount
) -> dict[str, Any]:
    card = await guardian_today(db, now, student)
    # 첫 화면 🔴 안내는 연결된 아이 누구든 오늘 🔴이면(11-14 점검 B5). 카드 내용은 첫 아이 그대로
    kids = await _guardian_children(db, student, account)
    red_today = await db.scalar(
        select(Session.id)
        .where(
            Session.student_id.in_(kids),
            Session.date == seoul_date(now),
            Session.state == State.CRISIS.value,
        )
        .limit(1)
    )
    session = await db.scalar(
        select(Session).where(Session.student_id == student.id, Session.date == seoul_date(now))
    )
    problem = await _problem(db, session) if session is not None else None
    solved = (await progress(db, session)).solved if session is not None else 0
    return {
        "childName": student.nickname,
        "dateLabel": _date_label(now),
        "done": session is not None and session.state == State.ENDED.value,
        "unit": _tag_name(problem) if problem else "-",
        "solved": solved,  # 끝낸 문제 수(한 문제 세션이면 0/1 그대로)
        "streak": student.streak_days,
        "hardPoint": None,
        "line": card["child_line"],
        "quiz": card["quiz"]["text"] if card["quiz"] else None,
        "teacherComment": card["instructor_comment"],
        "homework": card["homework"],  # 승인된 강사 노트의 사실 칸(명세 부록 D)
        "attendance": _attendance(student, now),
        "todayIndex": seoul_date(now).weekday(),
        # 오늘 🔴로 끝났으면 첫 화면에 「공부 전」 대신 이 안내(알림 탭으로)
        "alertNotice": GUARDIAN_ALERT_NOTICE if red_today is not None else None,
    }


async def _guardian_children(
    db: AsyncSession, student: Student, account: Account | None
) -> dict[str, str]:
    """🔴 알림을 볼 아이들 {학생 id: 별명}. 카드는 「연결된 첫 아이」(설계 §9-13)지만 알림은 연결된 모든 아이 —
    11-14 점검 B5: 둘째 아이 🔴이 보호자에게 안 보였다. 학생 계정 id = students.id(models_org)."""
    kids = {student.id: student.nickname}
    if account is not None and account.role == "guardian":
        for sid in await connected_ids(db, account):
            row = await db.get(Student, sid)
            if row is not None:
                kids.setdefault(row.id, row.nickname)
    return kids


@router.get("/guardian/alerts")
async def get_alerts(
    db: Db, student: GuardianChild, account: CurrentAccount
) -> list[dict[str, Any]]:
    """🔴 알림 목록. 발췌 ±2턴·300자를 싣는다(결정 11-10·11-11, 🔴일 때만). 연결된 모든 아이 것."""
    kids = await _guardian_children(db, student, account)
    alerts = await db.scalars(
        select(Alert).where(Alert.student_id.in_(kids)).order_by(Alert.created_at.desc())
    )
    out = []
    for a in alerts:
        created = as_utc(a.created_at)
        assert created is not None
        at = created.astimezone(SEOUL)
        out.append(
            {
                "id": a.id,
                "at": f"{at.month}월 {at.day}일 · {at:%H:%M}",
                "level": "긴급",  # 🔴(자해·자살)만 있다
                "category": "안전",
                "action": "지금 아이와 직접 이야기해 주세요. 도움: " + "·".join(HOTLINES),
                "status": "확인함" if a.guardian_seen else "미확인",
                "excerpt": a.excerpt,
                "hotlines": list(HOTLINES),
                "childName": kids.get(a.student_id),  # 아이가 둘 이상이면 누구 알림인지
            }
        )
    return out


# --- 강사 (F5, 11-11) -----------------------------------------------------------------
# 서버 규칙은 #8·#9·#10 그대로: 초안은 메모 저장 순간 한 번(재생성 없음), 승인 전에만 사람이 고친다.

CLASS_NAME = "데모 반"  # 반 테이블이 없다. 표시용 고정값
DRAFT_STATUS = {"draft": "승인 대기", "published": "승인됨"}
UNIT_TAG = {v: k for k, v in TAG_NAME.items()}


async def _assigned_unit(db: AsyncSession, student: Student, now: datetime) -> str | None:
    """오늘 강사가 지정한 문제의 단원 이름. 지정이 없거나 오늘 것이 아니면 None."""
    if student.today_task_problem_id is None or student.today_task_date != seoul_date(now):
        return None
    return _tag_name(await db.get(Problem, student.today_task_problem_id))


async def _unit_today(
    db: AsyncSession, student: Student, session: Session | None, now: datetime
) -> str | None:
    """오늘 단원. 아이가 시작했으면 그 세션의 문제(지정은 세션으로 옮겨져 비워진다 —
    명세 4.2), 아니면 강사가 지정한 것."""
    if session is not None and session.problem_id:
        return _tag_name(await db.get(Problem, session.problem_id))
    return await _assigned_unit(db, student, now)


async def _today_row(db: AsyncSession, student: Student, now: datetime) -> Session | None:
    return await db.scalar(
        select(Session).where(Session.student_id == student.id, Session.date == seoul_date(now))
    )


async def _teacher_today(db: AsyncSession, now: datetime, actor: Actor) -> dict[str, Any]:
    """계정 학습지도자는 내 강의실 member, 체험 학습지도자는 같은 세트 아이만,
    그 밖의 강사는 전체(명세 4.11-2·4.12)."""
    query = select(Student).order_by(Student.id)
    if actor.allowed is not None:
        query = query.where(Student.id.in_(actor.allowed))
    elif actor.scope is not None:
        query = query.where(Student.id == actor.scope)
    else:  # 체험이 아닌 헤더 강사는 체험 아이·가입 학생을 못 본다(헤더를 꾸며도, 11-11·A3)
        query = query.where(
            ~Student.id.startswith(TRIAL_PREFIX), ~Student.id.startswith(ACCOUNT_PREFIX)
        )
    rows = []
    for student in await db.scalars(query):
        session = await _today_session(db, student, now)  # 수다 마감이 지났으면 먼저 전이
        task = await _unit_today(db, student, session, now)
        if session is None:
            status = "지정됨" if task else "지정 전"
        else:
            status = "완료" if session.state in FINISHED else "진행 중"
        note = await _today_note(db, student.id, now)
        rows.append(
            {
                "id": student.id,
                "name": student.nickname,
                "task": task,
                "status": status,
                "draftStatus": DRAFT_STATUS.get(note.status) if note is not None else None,
            }
        )
    class_name = CLASS_NAME
    if actor.allowed is not None:  # 계정 학습지도자: 첫 강의실 이름(없으면 「내 강의실」)
        first_room = await db.scalar(
            select(Room.name)
            .where(Room.teacher_id == actor.id)
            .order_by(Room.created_at, Room.id)
            .limit(1)
        )
        class_name = first_room or "내 강의실"
    await db.commit()
    return {
        "dateLabel": _date_label(now),
        "className": class_name,
        "units": await selected_unit_names(db, actor),  # 학습지도자가 고른 단원(기본 전체)
        "students": rows,
    }


async def _draft_out(
    db: AsyncSession, student: Student, note: InstructorNote, now: datetime
) -> dict[str, Any]:
    """사실 칸(scope·amount·mode)은 기록에서, comment는 초안(승인 뒤엔 승인본)."""
    session = await _today_row(db, student, now)
    if session is not None:
        prog = await progress(db, session)  # 한 문제면 예전 그대로(0·1/1문제, 힌트 hint_level번)
        amount, mode = f"{prog.solved}/{prog.total}문제", f"힌트 {prog.hint_presses}번"
    else:
        amount, mode = "미완료", "-"
    published = note.status == "published"
    return {
        "studentId": student.id,
        "studentName": student.nickname,
        "scope": await _unit_today(db, student, session, now) or note.covered,
        "amount": amount,
        "mode": mode,
        # 저장본은 치환본. 학습지도자 화면에는 「[이름]」만 아이 이름으로 되돌려 보인다(11-11 성호)
        "comment": unredact_name(
            note.final_body if published else note.draft_body, student.nickname
        )
        or "",
        "status": "승인됨" if published else "승인 대기",
        # 초안 출처(수정 명세 B33): live = AI 초안, template = 기본 문장. 예전 노트는 알 수 없어 None
        "source": (note.facts or {}).get("draft_source"),
    }


async def _note_or_409(db: AsyncSession, student: Student, now: datetime) -> InstructorNote:
    note = await _today_note(db, student.id, now)
    if note is None:
        raise ApiError(409, "no_note", "오늘 메모를 먼저 저장해 주세요.")
    return note


@router.get("/teacher/today")
async def teacher_today(db: Db, now: Now, actor: Instructor) -> dict[str, Any]:
    return await _teacher_today(db, now, actor)


class AssignIn(BaseModel):
    unit: str | None = None  # 단원 이름. null이면 지정 해제


@router.put("/teacher/students/{student_id}/task")
async def assign_task(
    student_id: str, body: AssignIn, db: Db, now: Now, actor: Instructor
) -> dict[str, Any]:
    student = await _student_or_404(db, student_id, actor)
    if body.unit is None:
        # 해제. 이미 시작한 오늘 세션의 문제는 그대로다
        student.today_task_problem_id = None
        student.today_task_date = None
        await db.commit()
        return await _teacher_today(db, now, actor)
    tag = UNIT_TAG.get(body.unit)
    problem_id = (
        await db.scalar(select(Problem.id).where(Problem.tag == tag).order_by(Problem.id).limit(1))
        if tag is not None
        else None
    )
    if problem_id is None:
        raise ApiError(422, "invalid_request", "고를 수 있는 단원이 아니에요.")
    await put_today_task(student.id, TodayTaskIn(problem_id=problem_id), db, now, actor)
    return await _teacher_today(db, now, actor)


class TeacherMemoIn(BaseModel):
    covered: str = Field(default="", max_length=TEXT_MAX)
    stuck: str = Field(default="", max_length=TEXT_MAX)
    homework: str = Field(default="", max_length=TEXT_MAX)
    note: str = Field(default="", max_length=TEXT_MAX)


@router.get("/teacher/students/{student_id}/memo")
async def get_memo(student_id: str, db: Db, now: Now, actor: Instructor) -> dict[str, Any]:
    student = await _student_or_404(db, student_id, actor)
    note = await _today_note(db, student.id, now)
    if note is None:
        return {"memo": {"covered": "", "stuck": "", "homework": "", "note": ""}, "draft": None}
    memo = {
        "covered": note.covered,
        "stuck": note.stuck,
        "homework": note.homework,
        "note": note.memo_redacted,
    }
    return {"memo": memo, "draft": await _draft_out(db, student, note, now)}


@router.put("/teacher/students/{student_id}/memo", status_code=204)
async def save_memo(
    student_id: str, body: TeacherMemoIn, db: Db, now: Now, adapter: DraftAdapter, actor: Instructor
) -> None:
    """#8 post_note: 메모 저장 + 초안 생성 한 번. 오늘 노트가 있으면 그대로 둔다(명세 3.4)."""
    await _student_or_404(db, student_id, actor)  # 없는 학생(긴 id 포함)은 404가 먼저(11-12 점검)
    note = NoteIn(
        student_id=student_id,
        covered=body.covered,
        stuck=body.stuck,
        homework=body.homework,
        memo=body.note,
    )
    await post_note(note, db, now, adapter, actor)


@router.post("/teacher/students/{student_id}/draft")
async def create_draft(student_id: str, db: Db, now: Now, actor: Instructor) -> dict[str, Any]:
    """초안은 saveMemo 때 이미 만들어졌다. 여기서는 읽기만(재생성 없음)."""
    student = await _student_or_404(db, student_id, actor)
    return await _draft_out(db, student, await _note_or_409(db, student, now), now)


class DraftEditIn(BaseModel):
    comment: str = Field(max_length=TEXT_MAX)


@router.put("/teacher/students/{student_id}/draft")
async def update_draft(
    student_id: str, body: DraftEditIn, db: Db, now: Now, actor: Instructor
) -> dict[str, Any]:
    student = await _student_or_404(db, student_id, actor)
    note = await _note_or_409(db, student, now)
    update_draft_body(note, student, body.comment)
    await db.commit()
    return await _draft_out(db, student, note, now)


@router.post("/teacher/students/{student_id}/draft/approve")
async def approve_draft(student_id: str, db: Db, now: Now, actor: Instructor) -> dict[str, Any]:
    """서버가 들고 있는 draft_body를 그대로 승인본으로(#9 publish)."""
    student = await _student_or_404(db, student_id, actor)
    note = await _note_or_409(db, student, now)
    # 서버가 들고 있는 초안이라 길이 검사를 다시 하지 않는다(템플릿·이름 치환으로 2000자를 넘을 수 있음)
    approve = ApproveIn.model_construct(final_body=note.draft_body or "", action="publish")
    await approve_note(note.id, approve, db, actor)
    return await _draft_out(db, student, note, now)


@router.get("/teacher/alerts")
async def teacher_alerts(_: Instructor) -> list[dict[str, Any]]:
    return []  # 11-15는 강사 알림 없음(결정 11-09)


@router.post("/trial")
async def create_trial(db: Db, now: Now) -> dict[str, Any]:
    """방문자 한 명의 세트(아이 + 보호자 + 학습지도자). 본문·토큰·역할 헤더 없음.

    아이 행만 만든다(보호자·학습지도자는 id 접미사로 짝을 찾는다). 아이는 day3 상태지만
    약속 동의 전이라 약속·캐릭터 고르기부터 시작한다. 이전 세트는 건드리지 않는다.
    발급 수는 서버 메모리가 아니라 DB에서 센다(함수 인스턴스가 바뀐다).
    """
    recent = await db.scalar(
        select(func.count())
        .select_from(Student)
        .where(
            # 세트 아이(`-child`)만 센다. 체험 세상의 s2~s4 학생 행은 세지 않는다(설계 §9-6)
            Student.id.startswith(TRIAL_PREFIX),
            Student.id.endswith("-child"),
            Student.created_at >= now - timedelta(hours=1),
        )
    )
    if (recent or 0) >= TRIAL_HOURLY_MAX:
        raise ApiError(429, "trial_limit", "잠시 뒤 다시 시도해 주세요.")
    today = seoul_date(now)
    trial_id = new_trial_id()
    child_id = f"{trial_id}-child"
    await load_seed(db)
    await _write_day3_student(
        db, ResetBody(), today, student_id=child_id, consent=False, past_days=True
    )
    child = await db.get(Student, child_id)
    assert child is not None
    child.created_at = now
    await db.commit()
    return {
        "trialId": trial_id,
        "actors": {
            "child": child_id,
            "guardian": f"{trial_id}-guardian",
            "instructor": f"{trial_id}-instructor",
        },
        "date": today.isoformat(),
    }
