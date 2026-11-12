"""강사 API 8·9·10번. 명세 4.4·3.4·4.6.

- 강사 신원은 데모 헤더 X-Demo-Role: instructor / X-Demo-Actor. 강사 테이블은 없어서
  11-15는 역할만 확인하고 actor는 비어 있지 않은지만 본다. 체험 학습지도자(`t-…-instructor`)는
  같은 세트 아이만 보고, 다른 학생 id는 404 student_not_found(명세 4.11-2).
- 강사 메모(3칸 + 자유 메모)와 승인본은 pii.redact 치환본만 저장한다.
- 초안은 메모 저장 순간 한 번(재생성 없음). 어댑터 실패·빈 응답·JSON 아님이면 템플릿.
- 로그에는 note id·길이만 남기고 문장은 남기지 않는다.
"""

import asyncio
import json
import logging
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import CurrentAccount, token_sent
from app.actors import Actor, actor_from_request, instructor_allows
from app.db import get_db
from app.errors import ApiError
from app.llm import LIVE_TIMEOUT_S, LLMAdapter, ReplyRequest, ScriptedAdapter, build_adapter
from app.models import InstructorNote, Problem, Session, Student
from app.pii import redact
from app.timeutil import get_now, seoul_date

log = logging.getLogger(__name__)

router = APIRouter(prefix="/instructor")

Db = Annotated[AsyncSession, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]

DRAFT_PROMPT_VERSION = "draft-v0.1"
# 부록 D 초안 프롬프트. 숙제·점수는 넣지 않는다(서버가 사실 칸에 붙인다).
DRAFT_SYSTEM = (
    "너는 학원 강사의 메모를 학부모용 코멘트 초안으로 바꾼다.\n"
    "입력: 오늘 다룬 것, 막힌 것, 자유 메모, (있으면) 아이 학습 요약 3줄.\n"
    '출력은 JSON {"body": "..."} 하나. 3~4문장, 존댓말. 입력에 없는 사실을 지어내지 않는다.\n'
    "숙제·점수는 쓰지 않는다(서버가 사실 칸에 따로 붙인다).\n"
    "학습 요약이 없으면 메모만으로 쓴다."
)
TEXT_MAX = 2000


async def current_instructor(
    request: Request,
    db: Db,
    account: CurrentAccount,
    x_demo_role: Annotated[str | None, Header()] = None,
    x_demo_actor: Annotated[str | None, Header()] = None,
) -> Actor:
    """학습지도자 신원. 계정이면 allowed(내 강의실 member), 체험 헤더면 scope 규칙 그대로."""
    return await actor_from_request(
        db, "instructor", x_demo_role, x_demo_actor, account=account, token_sent=token_sent(request)
    )


Instructor = Annotated[Actor, Depends(current_instructor)]


@lru_cache(maxsize=1)
def _scripted() -> ScriptedAdapter:
    return ScriptedAdapter.from_file()


def get_draft_adapter() -> LLMAdapter:
    """초안용 어댑터. live면 live(실패 시 scripted), scripted는 초안 대본이 없어 → 템플릿."""
    return build_adapter(_scripted())


DraftAdapter = Annotated[LLMAdapter, Depends(get_draft_adapter)]


async def _student_or_404(db: AsyncSession, student_id: str, actor: Actor | None = None) -> Student:
    """학습지도자 범위 밖 학생도 404(있는지 알리지 않는다). 범위는 instructor_allows 한 곳."""
    ok = actor is None or instructor_allows(actor, student_id)
    student = await db.get(Student, student_id) if ok else None
    if student is None:
        raise ApiError(404, "student_not_found", "학생을 찾을 수 없어요.")
    return student


# ---------- #10 오늘 할 것 지정 ----------


class TodayTaskIn(BaseModel):
    problem_id: str = Field(min_length=1, max_length=40)


@router.put("/students/{sid}/today-task")
async def put_today_task(
    sid: str, body: TodayTaskIn, db: Db, now: Now, actor: Instructor
) -> dict[str, Any]:
    student = await _student_or_404(db, sid, actor)
    if await db.get(Problem, body.problem_id) is None:
        raise ApiError(404, "problem_not_found", "문제를 찾을 수 없어요.")
    # 다시 지정하면 덮어쓴다(명세 4.2 today_task)
    assigned = seoul_date(now)
    student.today_task_problem_id = body.problem_id
    student.today_task_date = assigned
    await db.commit()
    return {"problem_id": body.problem_id, "assigned_date": assigned.isoformat()}


# ---------- #8 메모 → 초안 ----------


class NoteIn(BaseModel):
    student_id: str = Field(min_length=1, max_length=36)
    covered: str = Field(default="", max_length=TEXT_MAX)
    stuck: str = Field(default="", max_length=TEXT_MAX)
    homework: str = Field(default="", max_length=TEXT_MAX)
    memo: str = Field(default="", max_length=TEXT_MAX)


def _template_body(covered: str, stuck: str, memo: str) -> str:
    """메모 3칸을 문장으로(명세 4.6). 숙제는 사실 칸에 따로 간다."""
    lines = []
    if covered.strip():
        lines.append(f"오늘 수업에서는 「{covered.strip()}」 내용을 다뤘습니다.")
    if stuck.strip():
        lines.append(f"「{stuck.strip()}」 부분에서 조금 어려워했습니다.")
    if memo.strip():
        note = memo.strip()
        # 끝맺음이 없으면 마침표를 붙여 다음 문장과 이어 붙지 않게 한다
        if not note.endswith((".", "?", "!", "。", "？", "！")):
            note += "."
        lines.append(f"선생님 메모: {note}")
    if not lines:
        lines.append("오늘 수업을 마쳤습니다.")
    lines.append("다음 시간에 한 번 더 확인하겠습니다.")
    return " ".join(lines)


def _parse_draft(raw: str) -> str | None:
    """구조화 출력 {"body": "..."}에서 본문만. 모양이 다르면 None(→ 템플릿).

    모델이 코드 펜스(```json … ```)로 감싸거나 앞뒤에 설명을 붙여도 첫 { ~ 마지막 }만 읽는다.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        # 첫 줄(```json)과 마지막 펜스를 떼어 낸다
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rstrip().removesuffix("```")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    body = data.get("body")
    if not isinstance(body, str) or not body.strip():
        return None
    return body.strip()


async def _draft_body(
    adapter: LLMAdapter, student: Student, covered: str, stuck: str, memo: str, summary: list[str]
) -> str:
    parts = [f"오늘 다룬 것: {covered}", f"막힌 것: {stuck}", f"자유 메모: {memo}"]
    if summary:
        parts.append("아이 학습 요약:\n" + "\n".join(summary))
    req = ReplyRequest(
        scenario=f"day3-{student.style}",
        phase="draft",
        hint_level=0,
        step=1,
        system=DRAFT_SYSTEM,
        turns=[{"role": "user", "content": "\n".join(parts)}],
    )
    try:
        raw = (await asyncio.wait_for(adapter.reply(req), LIVE_TIMEOUT_S)).text
    except Exception as exc:  # 타임아웃 포함. 문장은 로그에 남기지 않는다
        log.warning("draft fallback err=%s", type(exc).__name__)
        raw = ""
    body = _parse_draft(raw)
    if body is None:
        log.info("draft template len_in=%d", len(covered) + len(stuck) + len(memo))
        return _template_body(covered, stuck, memo)
    return body


def _note_out(note: InstructorNote) -> dict[str, Any]:
    return {
        "note_id": note.id,
        "draft": {"body": note.draft_body, "facts": note.facts},
        "status": note.status,
    }


async def _today_note(db: AsyncSession, student_id: str, now: datetime) -> InstructorNote | None:
    return await db.scalar(
        select(InstructorNote)
        .where(InstructorNote.student_id == student_id, InstructorNote.date == seoul_date(now))
        .limit(1)
    )


@router.post("/notes")
async def post_note(
    body: NoteIn, db: Db, now: Now, adapter: DraftAdapter, actor: Instructor
) -> dict[str, Any]:
    student = await _student_or_404(db, body.student_id, actor)
    existing = await _today_note(db, student.id, now)
    if existing is not None:
        # 초안은 메모 저장 순간 한 번, 재생성 없음(명세 3.4). 두 번 눌러도 같은 노트
        return _note_out(existing)
    names = [student.nickname]
    covered = redact(body.covered, names)
    stuck = redact(body.stuck, names)
    homework = redact(body.homework, names)
    memo = redact(body.memo, names)
    session = await db.scalar(
        select(Session).where(Session.student_id == student.id, Session.date == seoul_date(now))
    )
    summary = list(session.study_summary or []) if session is not None else []
    note = InstructorNote(
        student_id=student.id,
        date=seoul_date(now),
        covered=covered,
        stuck=stuck,
        homework=homework,
        memo_redacted=memo,
        draft_body=await _draft_body(adapter, student, covered, stuck, memo, summary),
        facts={"homework": homework, "score": None},
        status="draft",
        prompt_version=DRAFT_PROMPT_VERSION,
    )
    db.add(note)
    await db.commit()
    log.info("note created id=%s body_len=%d", note.id, len(note.draft_body or ""))
    return _note_out(note)


@router.get("/notes")
async def get_note(student_id: str, db: Db, now: Now, actor: Instructor) -> dict[str, Any] | None:
    student = await _student_or_404(db, student_id, actor)
    note = await _today_note(db, student.id, now)
    return _note_out(note) if note is not None else None


def update_draft_body(note: InstructorNote, student: Student | None, body: str) -> None:
    """승인 전 초안 문장을 사람이 고쳐 저장한다(재생성 아님, 명세 3.4·4.4 #9, 11-11).

    draft 상태에서만. 치환본만 저장하고 커밋은 부르는 쪽이 한다. 문장은 로그에 남기지 않는다.
    """
    if note.status != "draft":
        raise ApiError(409, "note_closed", "이미 처리한 코멘트예요.")
    if not body.strip():
        raise ApiError(422, "invalid_request", "보낼 문장이 비어 있어요.")
    names = [student.nickname] if student is not None else []
    edited = redact(body.strip(), names)
    note.draft_body = edited
    log.info("draft edited id=%s body_len=%d", note.id, len(edited))


# ---------- #9 승인 ----------


class ApproveIn(BaseModel):
    final_body: str = Field(default="", max_length=TEXT_MAX)
    action: Literal["publish", "skip"]


@router.post("/notes/{note_id}/approve")
async def approve_note(note_id: str, body: ApproveIn, db: Db, actor: Instructor) -> dict[str, str]:
    note = await db.get(InstructorNote, note_id)
    if note is None or not instructor_allows(actor, note.student_id):
        raise ApiError(404, "note_not_found", "코멘트를 찾을 수 없어요.")
    if note.status != "draft":
        raise ApiError(409, "note_closed", "이미 처리한 코멘트예요.")
    if body.action == "publish":
        if not body.final_body.strip():
            raise ApiError(422, "invalid_request", "보낼 문장이 비어 있어요.")
        student = await db.get(Student, note.student_id)
        names = [student.nickname] if student is not None else []
        note.final_body = redact(body.final_body.strip(), names)
        note.status = "published"
    else:
        note.status = "skipped"
    await db.commit()
    log.info("note %s id=%s", note.status, note.id)
    return {"status": note.status}
