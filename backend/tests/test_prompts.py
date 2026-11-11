"""프롬프트 조립 단일 함수 (명세 4.2 ①, 부록 D). 정답·별명은 들어가지 않는다."""

import dataclasses
import json
import re

import pytest

from app.prompts import FEWSHOT, PROMPT_VERSION, STYLE_CARD, PromptInput, build_prompt
from app.seed import SEED_PATH

SEED = json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _input(p: dict, **kw) -> PromptInput:
    values: dict = {
        "phase": "study",
        "grade_band": "초5-6",
        "honorific": "hyung",
        "style": "EBSP",
        "polite": False,
        "problem_text": p["text"],
        "hint1": p["hint1"],
        "hint2": p["hint2"],
        "solution": p["solution"],
        "hint_level": 0,
        "judge": None,
        "turns": [{"role": "child", "text": "몰라"}],
    }
    values.update(kw)
    return PromptInput(**values)


def test_input_has_no_answer_or_nickname_field():
    names = {f.name for f in dataclasses.fields(PromptInput)}
    assert not names & {"answer", "forbidden", "nickname", "name"}


@pytest.mark.parametrize("level", [0, 1, 2])
@pytest.mark.parametrize("p", SEED, ids=[p["id"] for p in SEED])
def test_study_prompt_has_no_answer_before_solution(p, level):
    system = build_prompt(_input(p, hint_level=level)).system
    # 문제·힌트 본문에 원래 들어 있는 숫자(예: 답이 "3")는 제외하고 본다
    visible = p["text"] + p["hint1"] + p["hint2"]
    for s in set(p["forbidden"]) | set(p["answer"]["accepted"]) | {p["answer"]["value"]}:
        if s not in visible:
            assert s not in system, (p["id"], level, s)
    assert p["solution"] not in system


def test_hint_text_by_level():
    p = SEED[0]
    assert p["hint1"] not in build_prompt(_input(p, hint_level=0)).system
    assert p["hint1"] in build_prompt(_input(p, hint_level=1)).system
    two = build_prompt(_input(p, hint_level=2)).system
    assert p["hint2"] in two and p["hint1"] not in two
    three = build_prompt(_input(p, hint_level=3)).system
    assert p["solution"] in three and p["hint2"] not in three


@pytest.mark.parametrize(
    ("honorific", "word"), [("hyung", "형"), ("unni", "언니"), ("friend", "친구")]
)
def test_honorific(honorific, word):
    system = build_prompt(_input(SEED[0], honorific=honorific)).system
    assert f"{word}이다" in system or f"{word}다" in system


@pytest.mark.parametrize("style", ["EBSP", "EQLC", "DQSC"])
@pytest.mark.parametrize("phase", ["study", "chat", "bridge"])
def test_every_phase_and_style_builds(style, phase):
    prompt = build_prompt(_input(SEED[0], style=style, phase=phase))
    assert '"너"' in prompt.system
    assert "테스트학생" not in prompt.system
    for code in ("EBSP", "EQLC", "DQSC"):
        assert code not in prompt.system  # 코드가 아니라 말투 문장을 넣는다


def test_polite_line():
    assert "존댓말로 말한다" in build_prompt(_input(SEED[0], polite=True)).system
    assert "반말로 말한다" in build_prompt(_input(SEED[0], polite=False)).system
    # 예시는 반말로만 두므로 말투 규칙이 예시보다 우선이라고 적는다
    assert "말투 규칙이 예시보다 우선" in build_prompt(_input(SEED[0], polite=True)).system


def test_prompt_version_fits_session_column():
    assert PROMPT_VERSION and len(PROMPT_VERSION) <= 20  # models.Session.prompt_version


@pytest.mark.parametrize("style", ["EBSP", "EQLC", "DQSC"])
def test_style_card_is_short_and_in_every_phase(style):
    assert 5 <= len(STYLE_CARD[style]) <= 8
    for phase in ("study", "chat", "bridge"):
        system = build_prompt(_input(SEED[0], style=style, phase=phase)).system
        assert all(line in system for line in STYLE_CARD[style])
        # 다른 스타일 카드는 섞이지 않는다
        for other in {"EBSP", "EQLC", "DQSC"} - {style}:
            assert STYLE_CARD[other][0] not in system


@pytest.mark.parametrize("style", ["EBSP", "EQLC", "DQSC"])
@pytest.mark.parametrize("phase", ["study", "chat", "bridge"])
def test_fewshot_goes_into_system_not_turns(style, phase):
    pairs = FEWSHOT[style][phase]
    assert 2 <= len(pairs) <= 3
    turns = [{"role": "child", "text": "[이름] 합성 문장"}]
    prompt = build_prompt(_input(SEED[0], style=style, phase=phase, turns=turns))
    for child, mentor in pairs:
        assert child in prompt.system and mentor in prompt.system
    assert prompt.turns == turns  # 예시는 가짜 턴으로 넣지 않는다


def test_fewshot_numbers_do_not_overlap_seed():
    """예시 속 분수가 시드 문제·정답과 겹치지 않는다(정답 누출·문제 혼동 방지)."""
    seed_text = " ".join(p["text"] + p["hint1"] + p["hint2"] + p["solution"] for p in SEED)
    seed_fracs = set(re.findall(r"\d+/\d+", seed_text))
    for style in FEWSHOT.values():
        for pairs in style.values():
            for child, mentor in pairs:
                assert not set(re.findall(r"\d+/\d+", child + mentor)) & seed_fracs


@pytest.mark.parametrize("phase", ["study", "chat", "bridge"])
def test_fixed_part_comes_first(phase):
    """고정 부분(역할·호칭·카드·예시·규칙)이 앞, 문제·힌트·판정이 뒤. 문제가 달라도 앞부분은 같다."""
    a = build_prompt(_input(SEED[0], phase=phase, hint_level=0, judge=None)).system
    b = build_prompt(_input(SEED[5], phase=phase, hint_level=2, judge="wrong")).system
    if phase == "study":
        cut = a.index(SEED[0]["text"])
        assert a[:cut] == b[: b.index(SEED[5]["text"])]
        assert a.index(STYLE_CARD["EBSP"][0]) < cut
        assert a.index(FEWSHOT["EBSP"]["study"][0][1]) < cut
        assert a.index("판정 없음") > cut
    else:
        assert a == b


@pytest.mark.parametrize(
    ("judge", "word"), [("correct", "정답"), ("wrong", "오답"), (None, "판정 없음")]
)
def test_study_judge_line(judge, word):
    # 예시 대화에도 [정답]/[오답] 표시가 있어 판정 줄 자체를 본다
    assert f"서버 판정: {word}" in build_prompt(_input(SEED[0], judge=judge)).system


def test_chat_prompt_has_no_problem_or_hints():
    p = SEED[0]
    system = build_prompt(_input(p, phase="chat", hint_level=3)).system
    for s in (p["text"], p["hint1"], p["hint2"], p["solution"]):
        assert s not in system


def test_turns_are_passed_through():
    turns = [{"role": "child", "text": "[전화] 몰라"}]
    assert build_prompt(_input(SEED[0], turns=turns)).turns == turns
