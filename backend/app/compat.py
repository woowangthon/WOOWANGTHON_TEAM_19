"""프론트 v0.5 호환 라우터 `/api/v1/compat` (11-15까지 임시).

프론트(src/api/http.ts)의 경로·JSON 모양(src/types.ts, camelCase) 그대로 응답한다.
- 판단은 새로 만들지 않는다. 전환·힌트·판정·마감은 기존 api.py 핸들러와 state_machine을 그대로 부른다.
- 신원은 기존과 같은 X-Demo-Role·X-Demo-Actor 헤더(current_child / current_guardian_child /
  current_instructor).
- 문제 화면에 정답·풀이를 싣지 않는다. 풀이는 hint_level 3(풀이 보기)에서만 준다.
- 오류는 기존 {code, message, request_id}에 프론트가 읽는 `detail`(= message)만 덧붙인다.
- 시드는 한 세션에 한 문제라 total은 1, 난이도는 시드에 없어 받기만 하고 버린다.
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    _lease_valid,
    _open_misconception,
    _owned_session,
    _quiz_options,
    _row_state,
    _today_session,
    _today_task,
    get_bridge,
    is_solved,
    post_end,
    post_message,
    post_phase,
    post_reply,
    put_mentor,
    start_session,
)
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
from app.state_machine import MAX_HINT, State, TransitionError, press_hint
from app.timeutil import SEOUL, as_utc, seoul_date


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

DIFFICULTY = "중급"  # 시드에 난이도가 없다. 프론트 타입을 채우는 표시용 고정값
STUDY_SEC = 20 * 60  # 명세 3.2 「같이 풀기 ~20분」. 서버 마감 아님(표시용)
TASK_MINUTES = 20
HINT_COUNT = MAX_HINT - 1  # 힌트 1·2. 3은 풀이 보기
WEEKDAY = "월화수목금토일"
ASSIGNED_BY = {"instructor": "선생님", "misconception": "친구1"}
STYLE_LABEL = {"EBSP": "같이 풀어주는", "EQLC": "들어주는", "DQSC": "짚어주는"}
TITLE_LABEL = {"hyung": "형", "unni": "언니", "friend": "친구"}
_OPERAND = r"\(?(\d+)(?:/(\d+))?\)?"
_EXPR = re.compile(rf"{_OPERAND} / {_OPERAND}")


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


def _seconds_left(until: datetime | None, now: datetime) -> int:
    return max(0, math.ceil((until - now).total_seconds())) if until is not None else 0


async def _problem(db: AsyncSession, row: Session) -> Problem | None:
    return await db.get(Problem, row.problem_id) if row.problem_id else None


async def _view(db: AsyncSession, row: Session, student: Student, now: datetime) -> dict[str, Any]:
    problem = await _problem(db, row)
    solved = await is_solved(db, row, problem)
    started = as_utc(row.phase_started_at)
    in_study = row.state == State.STUDY.value and started is not None
    # study 밖에서는 study를 떠날 때 저장한 초(11-11, 전에는 0이 됐다)
    study_sec = (now - started).total_seconds() if in_study and started else row.study_sec or 0
    return {
        "id": row.id,
        "phase": _phase(row, solved),
        "unit": _tag_name(problem),
        "difficulty": DIFFICULTY,
        "solved": 1 if solved or row.hint_level >= MAX_HINT else 0,
        "total": 1,
        "assisted": 1 if row.hint_level >= MAX_HINT and not solved else 0,
        "hintsUsed": min(row.hint_level, HINT_COUNT),
        "studyMin": math.ceil(study_sec / 60),
        "studyRemainingSec": max(0, STUDY_SEC - int(study_sec)) if in_study else 0,
        "chatRemainingSec": _seconds_left(as_utc(row.deadline_at), now),
        "timedOut": False,
        "streakDays": student.streak_days,
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


def _hint_state(hint_level: int) -> dict[str, Any]:
    return {
        "hintsLeft": max(0, HINT_COUNT - hint_level),
        "canShowSolution": HINT_COUNT <= hint_level < MAX_HINT,
    }


def _operands(expr: str) -> tuple[list[int] | None, list[int] | None]:
    """시드 expr "a/b / c" → 분수 칸. 괄호 안 덧셈 같은 모양은 None(프론트는 text로 보여야 한다)."""
    m = _EXPR.fullmatch(expr.strip())
    if m is None:
        return None, None
    return [int(m[1]), int(m[2] or 1)], [int(m[3]), int(m[4] or 1)]


# --- 학생: 준비 ----------------------------------------------------------------------


@router.get("/student/home")
async def student_home(db: Db, now: Now, student: Child) -> dict[str, Any]:
    session = await _today_session(db, student, now)
    task = None if session is not None else await _today_task(db, student)
    task_info = None
    if task is not None:
        problem = await db.get(Problem, task[0])
        task_info = {
            "unit": _tag_name(problem),
            "count": 1,
            "minutes": TASK_MINUTES,
            "assignedBy": ASSIGNED_BY[task[1]],
        }
    view = await _view(db, session, student, now) if session is not None else None
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
        "restricted": False,
        "inClass": True,
        "seeds": 0,
        "earnedToday": 0,
    }


@router.post("/student/promise", status_code=204)
async def accept_promise(db: Db, student: Child) -> None:
    """약속 화면 「약속할게」 = 동의 저장(AI 사용·🔴 보호자 알림 고지 1회)."""
    student.consent = True
    await db.commit()


@router.get("/student/mentor")
async def get_mentor(student: Child) -> dict[str, Any]:
    # 그림(띠)은 저장 칸이 없어 null — 스타일 코드와 분리(CLAUDE.md)
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
    problem = await _problem(db, row)
    solved = await is_solved(db, row, problem)
    await db.commit()
    if problem is None or _phase(row, solved) != "solve":
        return None  # 풀기 단계가 끝났다
    left, right = _operands(problem.expr)
    started = as_utc(row.phase_started_at)
    return {
        "id": problem.id,
        "index": 0,
        "total": 1,
        "text": problem.text,  # 나눗셈 문장제. 프론트 left/op/right 대신 보여야 한다
        "left": left,
        "right": right,
        "op": "÷",
        "hints": _hints(problem, row.hint_level),
        **_hint_state(row.hint_level),
        "remainingSec": max(0, STUDY_SEC - int((now - started).total_seconds())) if started else 0,
    }


class AnswerIn(BaseModel):
    problemId: str
    numerator: int
    denominator: int


@router.post("/sessions/{session_id}/answer")
async def submit_answer(
    session_id: str, body: AnswerIn, db: Db, now: Now, student: Child, llm: Llm
) -> dict[str, Any]:
    row = await _owned_session(db, session_id, student, now)
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
    text = f"{body.numerator}/{body.denominator}"
    out = await post_message(session_id, MessageIn(kind="text", text=text), db, now, student, llm)
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
    """풀이 보기 = hint_level 3. 힌트 1·2를 다 쓴 뒤에만(명세 3.2 「답을 먼저 주지 않는다」)."""
    row, problem = await _solving(db, session_id, student, now)
    if row.hint_level < HINT_COUNT:
        await db.commit()
        raise ApiError(409, "solution_unavailable", "힌트를 먼저 써 봐요.")
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
    session_id: str, body: AfterStudyIn, db: Db, now: Now, student: Child
) -> dict[str, Any]:
    to: Literal["chat", "bridge"] = "chat" if body.choice == "chat" else "bridge"
    await post_phase(session_id, PhaseIn(to=to), db, now, student)
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
        messages = [
            {"from": "me" if m.role == "child" else "mentor", "text": m.text_redacted}
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
    row = await _owned_session(db, session_id, student, now)
    # 끝난 세션(ended·crisis)·빈 말은 아래 post_message가 기본 경로와 같은 409·422로 거절한다
    if row.state != State.CHAT.value and row.state not in FINISHED:
        # 시간이 끝났거나 다른 단계 → 빈 답(프론트는 단계를 다시 맞춘다)
        view = await _view(db, row, student, now)
        await db.commit()
        return {
            "reply": "",
            "crisis": False,
            "queued": False,
            "pending": False,
            "source": None,
            "session": view,
        }
    try:
        msg = MessageIn(kind="text", text=body.text, texts=body.texts)
    except ValidationError:
        raise ApiError(422, "invalid_request", "요청 형식이 맞지 않아요.") from None
    out = await post_message(session_id, msg, db, now, student, llm)
    return await _chat_out(db, session_id, student, now, out)


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
    hardPoint: str | None = Field(default=None, max_length=30)  # 저장 칸이 없어 버린다
    quiz: str | None = None


@router.post("/sessions/{session_id}/wrap")
async def submit_wrap(
    session_id: str, body: WrapIn, db: Db, now: Now, student: Child, llm: Llm
) -> dict[str, Any]:
    quiz_id = None
    if body.quiz is not None:  # 프론트는 문장으로 고른다 → 같은 태그 퀴즈 후보에서 id로
        row = await _owned_session(db, session_id, student, now)
        options = await _quiz_options(db, await _problem(db, row))
        quiz_id = next((q["id"] for q in options if q["text"] == body.quiz), None)
        if quiz_id is None:
            await db.commit()
            raise ApiError(422, "invalid_request", "고를 수 있는 퀴즈가 아니에요.")
    await post_end(session_id, EndIn(quiz_problem_id=quiz_id), db, now, student, llm)
    return await _session_view(db, session_id, student, now)


# --- 보호자 ---------------------------------------------------------------------------


@router.get("/guardian/today")
async def get_guardian_today(db: Db, now: Now, student: GuardianChild) -> dict[str, Any]:
    card = await guardian_today(db, now, student)
    session = await db.scalar(
        select(Session).where(Session.student_id == student.id, Session.date == seoul_date(now))
    )
    problem = await _problem(db, session) if session is not None else None
    solved = await is_solved(db, session, problem) if session is not None else False
    hint_level = session.hint_level if session is not None else 0
    return {
        "childName": student.nickname,
        "dateLabel": _date_label(now),
        "done": session is not None and session.state == State.ENDED.value,
        "unit": _tag_name(problem) if problem else "-",
        "solved": 1 if solved or hint_level >= MAX_HINT else 0,
        "streak": student.streak_days,
        "hardPoint": None,
        "line": card["child_line"],
        "quiz": card["quiz"]["text"] if card["quiz"] else None,
        "teacherComment": card["instructor_comment"],
        "attendance": _attendance(student, now),
        "todayIndex": seoul_date(now).weekday(),
    }


@router.get("/guardian/alerts")
async def get_alerts(db: Db, student: GuardianChild) -> list[dict[str, Any]]:
    """🔴 알림 목록. 발췌는 현재 정책(±2턴·300자) 그대로 싣는다(11-10 회의 안건 2 확정 전)."""
    alerts = await db.scalars(
        select(Alert).where(Alert.student_id == student.id).order_by(Alert.created_at.desc())
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


async def _teacher_today(db: AsyncSession, now: datetime) -> dict[str, Any]:
    rows = []
    for student in await db.scalars(select(Student).order_by(Student.id)):
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
    await db.commit()
    return {
        "dateLabel": _date_label(now),
        "className": CLASS_NAME,
        "units": list(TAG_NAME.values()),
        "students": rows,
    }


async def _draft_out(
    db: AsyncSession, student: Student, note: InstructorNote, now: datetime
) -> dict[str, Any]:
    """사실 칸(scope·amount·mode)은 기록에서, comment는 초안(승인 뒤엔 승인본)."""
    session = await _today_row(db, student, now)
    if session is not None:
        problem = await _problem(db, session)
        solved = await is_solved(db, session, problem) or session.hint_level >= MAX_HINT
        amount, mode = f"{1 if solved else 0}/1문제", f"힌트 {session.hint_level}번"
    else:
        amount, mode = "미완료", "-"
    published = note.status == "published"
    return {
        "studentId": student.id,
        "studentName": student.nickname,
        "scope": await _unit_today(db, student, session, now) or note.covered,
        "amount": amount,
        "mode": mode,
        "comment": (note.final_body if published else note.draft_body) or "",
        "status": "승인됨" if published else "승인 대기",
    }


async def _note_or_409(db: AsyncSession, student: Student, now: datetime) -> InstructorNote:
    note = await _today_note(db, student.id, now)
    if note is None:
        raise ApiError(409, "no_note", "오늘 메모를 먼저 저장해 주세요.")
    return note


@router.get("/teacher/today")
async def teacher_today(db: Db, now: Now, _: Instructor) -> dict[str, Any]:
    return await _teacher_today(db, now)


class AssignIn(BaseModel):
    unit: str | None = None  # 단원 이름. null이면 지정 해제


@router.put("/teacher/students/{student_id}/task")
async def assign_task(
    student_id: str, body: AssignIn, db: Db, now: Now, actor: Instructor
) -> dict[str, Any]:
    student = await _student_or_404(db, student_id)
    if body.unit is None:
        # 해제. 이미 시작한 오늘 세션의 문제는 그대로다
        student.today_task_problem_id = None
        student.today_task_date = None
        await db.commit()
        return await _teacher_today(db, now)
    tag = UNIT_TAG.get(body.unit)
    problem_id = (
        await db.scalar(select(Problem.id).where(Problem.tag == tag).order_by(Problem.id).limit(1))
        if tag is not None
        else None
    )
    if problem_id is None:
        raise ApiError(422, "invalid_request", "고를 수 있는 단원이 아니에요.")
    await put_today_task(student.id, TodayTaskIn(problem_id=problem_id), db, now, actor)
    return await _teacher_today(db, now)


class TeacherMemoIn(BaseModel):
    covered: str = Field(default="", max_length=TEXT_MAX)
    stuck: str = Field(default="", max_length=TEXT_MAX)
    homework: str = Field(default="", max_length=TEXT_MAX)
    note: str = Field(default="", max_length=TEXT_MAX)


@router.get("/teacher/students/{student_id}/memo")
async def get_memo(student_id: str, db: Db, now: Now, _: Instructor) -> dict[str, Any]:
    student = await _student_or_404(db, student_id)
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
    note = NoteIn(
        student_id=student_id,
        covered=body.covered,
        stuck=body.stuck,
        homework=body.homework,
        memo=body.note,
    )
    await post_note(note, db, now, adapter, actor)


@router.post("/teacher/students/{student_id}/draft")
async def create_draft(student_id: str, db: Db, now: Now, _: Instructor) -> dict[str, Any]:
    """초안은 saveMemo 때 이미 만들어졌다. 여기서는 읽기만(재생성 없음)."""
    student = await _student_or_404(db, student_id)
    return await _draft_out(db, student, await _note_or_409(db, student, now), now)


class DraftEditIn(BaseModel):
    comment: str = Field(max_length=TEXT_MAX)


@router.put("/teacher/students/{student_id}/draft")
async def update_draft(
    student_id: str, body: DraftEditIn, db: Db, now: Now, _: Instructor
) -> dict[str, Any]:
    student = await _student_or_404(db, student_id)
    note = await _note_or_409(db, student, now)
    update_draft_body(note, student, body.comment)
    await db.commit()
    return await _draft_out(db, student, note, now)


@router.post("/teacher/students/{student_id}/draft/approve")
async def approve_draft(student_id: str, db: Db, now: Now, actor: Instructor) -> dict[str, Any]:
    """서버가 들고 있는 draft_body를 그대로 승인본으로(#9 publish)."""
    student = await _student_or_404(db, student_id)
    note = await _note_or_409(db, student, now)
    approve = ApproveIn(final_body=note.draft_body or "", action="publish")
    await approve_note(note.id, approve, db, actor)
    return await _draft_out(db, student, note, now)


@router.get("/teacher/alerts")
async def teacher_alerts(_: Instructor) -> list[dict[str, Any]]:
    return []  # 11-15는 강사 알림 없음(결정 11-09)
