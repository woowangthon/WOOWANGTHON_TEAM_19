"""세션 상태기계 (명세 4.5). DB·HTTP 없이 값만 받아 새 값을 돌려주는 순수 함수.

전환·힌트·시간 마감은 여기서만 정한다. LLM은 이 결과를 바꾸지 않는다.
"""

import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

CHAT_MINUTES = 10
STUDY_MINUTES = 20  # 같이 풀기 ~20분. 강제 종료가 아니라 선택지가 열리는 시각(명세 4.11-4)
MAX_HINT = 3  # 3 = 풀이 보기


class State(StrEnum):
    STUDY = "study"
    CHAT = "chat"
    BRIDGE = "bridge"
    ENDED = "ended"
    CRISIS = "crisis"


ACTIVE = frozenset({State.STUDY, State.CHAT, State.BRIDGE})


class TransitionError(Exception):
    """허용되지 않은 전이. API에서는 409로 바꾼다."""


@dataclass(frozen=True)
class SessionState:
    state: State
    hint_level: int = 0
    streak_applied: bool = False
    phase_started_at: datetime | None = None
    deadline_at: datetime | None = None


def study_remaining_sec(started: datetime | None, now: datetime, timer_scale: float = 1) -> int:
    """같이 풀기 20분까지 남은 초(올림). 0이면 study_time_over와 같다."""
    if started is None:
        return 0
    limit = timedelta(minutes=STUDY_MINUTES) / timer_scale
    return max(0, math.ceil((started + limit - now).total_seconds()))


def study_time_over(started: datetime | None, now: datetime, timer_scale: float = 1) -> bool:
    """phase_started_at + 20분(÷ timer_scale) ≤ now(서버 시각). 시작 시각이 없으면 False.

    지나면 힌트 수와 무관하게 「풀이 보기」·「수다로 넘어가기」를 허용한다(명세 4.11-4).
    """
    return started is not None and study_remaining_sec(started, now, timer_scale) == 0


def start(now: datetime) -> SessionState:
    """전이 1: 시작 전 → study, hint 0."""
    return SessionState(state=State.STUDY, phase_started_at=now)


def press_hint(s: SessionState) -> tuple[SessionState, bool]:
    """전이 2: 힌트 버튼. (새 상태, 오개념 open 여부)."""
    if s.state is not State.STUDY or s.hint_level >= MAX_HINT:
        raise TransitionError(f"hint not allowed: {s.state} level {s.hint_level}")
    level = s.hint_level + 1
    return replace(s, hint_level=level), level == MAX_HINT


def enter_phase(
    s: SessionState,
    to: Literal["chat", "bridge"],
    now: datetime,
    *,
    solved: bool = False,
    timer_scale: float = 1,
) -> tuple[SessionState, bool]:
    """전이 3·4·5. (새 상태, 이번에 연속 +1 했는지).

    study에서 나가려면 정답(solved)이거나 풀이 보기(hint 3)이거나 20분이 지나야 한다.
    연속 +1은 study를 떠날 때 한 번만(streak_applied로 중복 방지).
    """
    target = State(to)
    if s.state is State.STUDY and target in (State.CHAT, State.BRIDGE):
        over = study_time_over(s.phase_started_at, now, timer_scale)
        if not (solved or s.hint_level >= MAX_HINT or over):
            raise TransitionError("study not finished")
    elif not (s.state is State.CHAT and target is State.BRIDGE):
        raise TransitionError(f"{s.state} -> {target} not allowed")

    deadline = now + timedelta(minutes=CHAT_MINUTES) / timer_scale if target is State.CHAT else None
    streak_inc = not s.streak_applied
    new = replace(
        s,
        state=target,
        phase_started_at=now,
        deadline_at=deadline,
        streak_applied=True,
    )
    return new, streak_inc


def expire_if_due(s: SessionState, now: datetime) -> SessionState:
    """매 요청 맨 앞에서 부른다. chat 마감이 지났으면 bridge로(전이 5)."""
    if s.state is State.CHAT and s.deadline_at is not None and now > s.deadline_at:
        return replace(s, state=State.BRIDGE, phase_started_at=now, deadline_at=None)
    return s


def end(s: SessionState) -> SessionState:
    """전이 6: bridge → ended."""
    if s.state is not State.BRIDGE:
        raise TransitionError(f"end not allowed from {s.state}")
    return replace(s, state=State.ENDED, deadline_at=None)


def to_crisis(s: SessionState) -> SessionState:
    """전이 7: 🔴 키워드. 연속은 깎지 않는다(streak_applied 유지)."""
    if s.state not in ACTIVE:
        raise TransitionError(f"crisis not allowed from {s.state}")
    return replace(s, state=State.CRISIS, deadline_at=None)
