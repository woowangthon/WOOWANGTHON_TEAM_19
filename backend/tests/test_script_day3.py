"""scripted 대본 day3.yaml 채움 검사 (명세 부록 C, 점검 문서 7-1 B2). 네트워크 없음."""

import json

import pytest
import yaml

from app.llm import FIXED_REPLY, SCRIPT_PATH, ReplyRequest, ScriptedAdapter
from app.seed import SEED_PATH

STYLES = ("EBSP", "EQLC", "DQSC")
JUDGES = ("correct", "wrong", None)
LINES = yaml.safe_load(SCRIPT_PATH.read_text(encoding="utf-8"))
SEED = json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _req(style, phase, hint_level=0, judge=None, step=1) -> ReplyRequest:
    return ReplyRequest(
        scenario=f"day3-{style}",
        phase=phase,
        hint_level=hint_level,
        step=step,
        system="",
        judge=judge,
    )


def _own(style, phase, hint_level, judge, step):
    """대체 경로 없이 그 키에 직접 쓴 줄."""
    return [
        ln
        for ln in LINES
        if ln["scenario"] == f"day3-{style}"
        and ln["phase"] == phase
        and ln["hint_level"] == hint_level
        and ln.get("judge") == judge
        and ln["step"] == step
    ]


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("hint_level", [0, 1, 2, 3])
@pytest.mark.parametrize("judge", JUDGES)
async def test_every_study_combo_has_own_line(style, hint_level, judge):
    assert len(_own(style, "study", hint_level, judge, 1)) == 1
    reply = (await ScriptedAdapter.from_file().reply(_req(style, "study", hint_level, judge))).text
    assert reply != FIXED_REPLY


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("hint_level", [0, 1, 2, 3])
async def test_wrong_step_one_and_two_differ(style, hint_level):
    adapter = ScriptedAdapter.from_file()
    one = (await adapter.reply(_req(style, "study", hint_level, "wrong", step=1))).text
    two = (await adapter.reply(_req(style, "study", hint_level, "wrong", step=2))).text
    assert one != two


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("hint_level", [0, 1, 2, 3])
async def test_correct_lines_do_not_ask_again(style, hint_level):
    """정답 뒤 화면의 다음 행동은 「계속」 버튼이라 되묻지 않는다."""
    reply = (
        await ScriptedAdapter.from_file().reply(_req(style, "study", hint_level, "correct"))
    ).text
    assert "?" not in reply and "다시" not in reply


@pytest.mark.parametrize("style", STYLES)
async def test_chat_steps_and_bridge(style):
    adapter = ScriptedAdapter.from_file()
    assert all(len(_own(style, "chat", 0, None, n)) == 1 for n in range(1, 5))
    chats = [(await adapter.reply(_req(style, "chat", step=n))).text for n in range(1, 5)]
    assert len(set(chats)) == 4  # step 1·2를 포함해 4줄 모두 다르다
    assert len(_own(style, "bridge", 0, None, 1)) == 1
    assert (await adapter.reply(_req(style, "bridge"))).text != FIXED_REPLY


def test_no_seed_answer_and_no_digits_in_replies():
    """시드 20문제 정답 문자열이 대본 답에 없다. 「3」「8」 같은 한 글자 정답도 있어
    답 문장에는 숫자 자체를 쓰지 않는다(키 열의 hint_level·step 숫자는 제외)."""
    answers: set[str] = set()
    for p in SEED:
        answers |= set(p["forbidden"]) | set(p["answer"]["accepted"]) | {p["answer"]["value"]}
    for ln in LINES:
        reply = ln["reply"]
        assert not any(ch.isdigit() for ch in reply), ln["scenario"]
        assert not any(a in reply for a in answers), ln["scenario"]


def test_no_secret_promise_or_name_question_in_replies():
    for ln in LINES:
        for bad in ("비밀 지켜", "이름이 뭐", "이름 알려", "나만 믿어"):
            assert bad not in ln["reply"], ln["scenario"]
