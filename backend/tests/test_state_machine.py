"""명세 4.5 상태기계 전이표 7개를 HTTP 없이 순수 함수로 검사한다."""

from datetime import UTC, datetime, timedelta

import pytest

from app.state_machine import (
    SessionState,
    State,
    TransitionError,
    end,
    enter_phase,
    expire_if_due,
    press_hint,
    start,
    to_crisis,
)

NOW = datetime(2026, 11, 10, 6, 0, tzinfo=UTC)


def _study(hint_level: int = 0, streak_applied: bool = False) -> SessionState:
    return SessionState(state=State.STUDY, hint_level=hint_level, streak_applied=streak_applied)


# 1. 시작 전 → study, hint 0
def test_start_enters_study_at_hint_zero():
    s = start(NOW)
    assert s.state is State.STUDY
    assert s.hint_level == 0
    assert s.deadline_at is None
    assert s.phase_started_at == NOW


# 2. study 힌트 버튼 → hint +1, 3이면 오개념 open
@pytest.mark.parametrize("before", [0, 1])
def test_hint_button_raises_level_without_opening_misconception(before):
    s, opened = press_hint(_study(before))
    assert s.hint_level == before + 1
    assert opened is False


def test_hint_button_to_three_opens_misconception():
    s, opened = press_hint(_study(2))
    assert s.hint_level == 3
    assert opened is True


def test_hint_button_at_three_is_rejected():
    with pytest.raises(TransitionError):
        press_hint(_study(3))


def test_hint_button_outside_study_is_rejected():
    with pytest.raises(TransitionError):
        press_hint(SessionState(state=State.CHAT))


# 3·4. study → chat / bridge, 연속 +1 한 번
def test_solved_study_to_chat_sets_deadline_and_streak():
    s, streak_inc = enter_phase(_study(1), "chat", NOW, solved=True)
    assert s.state is State.CHAT
    assert s.deadline_at == NOW + timedelta(minutes=10)
    assert s.phase_started_at == NOW
    assert s.streak_applied is True
    assert streak_inc is True


def test_solution_viewed_study_to_bridge_counts_streak():
    s, streak_inc = enter_phase(_study(3), "bridge", NOW, solved=False)
    assert s.state is State.BRIDGE
    assert s.deadline_at is None
    assert streak_inc is True


def test_unsolved_study_cannot_leave():
    with pytest.raises(TransitionError):
        enter_phase(_study(2), "chat", NOW, solved=False)


def test_timer_scale_shortens_chat_deadline():
    s, _ = enter_phase(_study(), "chat", NOW, solved=True, timer_scale=10)
    assert s.deadline_at == NOW + timedelta(minutes=1)


# 5. chat → bridge (버튼 또는 마감), 연속은 다시 더하지 않는다
def test_chat_to_bridge_by_button_does_not_repeat_streak():
    chat, _ = enter_phase(_study(), "chat", NOW, solved=True)
    s, streak_inc = enter_phase(chat, "bridge", NOW + timedelta(minutes=3))
    assert s.state is State.BRIDGE
    assert s.deadline_at is None
    assert streak_inc is False


def test_chat_expires_to_bridge_after_deadline():
    chat, _ = enter_phase(_study(), "chat", NOW, solved=True)
    s = expire_if_due(chat, NOW + timedelta(minutes=10, seconds=1))
    assert s.state is State.BRIDGE


def test_chat_stays_before_deadline():
    chat, _ = enter_phase(_study(), "chat", NOW, solved=True)
    s = expire_if_due(chat, NOW + timedelta(minutes=9))
    assert s.state is State.CHAT


def test_chat_cannot_go_back_to_study_or_chat():
    chat, _ = enter_phase(_study(), "chat", NOW, solved=True)
    with pytest.raises(TransitionError):
        enter_phase(chat, "chat", NOW)


# 6. bridge → ended
def test_bridge_ends():
    bridge, _ = enter_phase(_study(3), "bridge", NOW)
    assert end(bridge).state is State.ENDED


def test_end_from_study_is_rejected():
    with pytest.raises(TransitionError):
        end(_study())


# 7. study / chat / bridge → crisis
@pytest.mark.parametrize("state", [State.STUDY, State.CHAT, State.BRIDGE])
def test_red_keyword_goes_to_crisis_from_any_active_state(state):
    s = to_crisis(SessionState(state=state, deadline_at=NOW))
    assert s.state is State.CRISIS
    assert s.deadline_at is None


@pytest.mark.parametrize("state", [State.ENDED, State.CRISIS])
def test_crisis_from_closed_state_is_rejected(state):
    with pytest.raises(TransitionError):
        to_crisis(SessionState(state=state))


def test_crisis_keeps_applied_streak():
    chat, _ = enter_phase(_study(), "chat", NOW, solved=True)
    assert to_crisis(chat).streak_applied is True
