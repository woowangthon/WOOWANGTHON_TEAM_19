"""명세 4.13 G6(11-14, bb 검토 반영): 과목 맞추기 + 정답 누설 검사 보강."""

import json
import re
from pathlib import Path

import pytest

from app.judge import contains_answer
from app.prompts import PromptInput, build_prompt, subject_name
from app.seed import BANK_DIR

BANK = [p for f in sorted(BANK_DIR.glob("*.json")) for p in json.loads(f.read_text("utf-8"))]
BY_ID = {p["id"]: p for p in BANK}


def _study(p: dict, hint_level: int = 0) -> str:
    return build_prompt(
        PromptInput(
            phase="study",
            grade_band="중1-3",
            honorific="friend",
            style="EBSP",
            polite=False,
            problem_text=p["text"],
            hint1=p["hint1"],
            hint2=p["hint2"],
            solution=p["solution"],
            hint_level=hint_level,
            judge=None,
            subject=subject_name(p["subject"]),
        )
    ).system


def test_subject_name():
    assert subject_name("math") == "수학"
    assert subject_name("korean") == "국어"
    assert subject_name("english") == "영어"
    assert subject_name(None) == "수학"


@pytest.mark.parametrize("pid", ["g8-kor-parts-of-speech-01", "g10-eng-relative-clauses-01"])
def test_role_line_follows_subject_not_math(pid):
    p = BY_ID[pid]
    s = _study(p)
    assert f"{subject_name(p['subject'])} 문제 하나를" in s
    assert "수학 문제 하나를" not in s and "분자·분모 값" not in s
    assert "말투만 참고" in s  # 분수 예시는 말투만


@pytest.mark.parametrize("p", BANK, ids=lambda p: p["id"])
def test_no_answer_in_prompt_before_solution(p):
    # 힌트 2단계까지 프롬프트에 정답이 없어야 한다. 한 자리 답(「6」)은 고정 예시(「6/11」「2~3문장」)와
    # 우연히 겹치므로 그 문제의 힌트 글에서만 본다
    s = _study(p, hint_level=2)
    if p["answer"]["kind"] == "choice":
        return  # 보기 번호·글은 문제 글에 늘 보인다

    def tok(a: str, t: str) -> bool:
        return re.search(rf"(?<![0-9A-Za-z가-힣]){re.escape(a)}(?![0-9A-Za-z가-힣])", t) is not None

    for a in {p["answer"]["value"], *p["answer"].get("accepted", []), *p.get("forbidden", [])}:
        # 고정 예시(「6/11」「2~3문장」)와 우연히 겹치는 값(1·11 등)이 있어, 문제마다 달라지는 부분(힌트 글)을 본다.
        # 정답이 프롬프트에 들어갈 길은 힌트뿐이다(문제 글은 아래에서 뺀다, 풀이는 힌트 3에서만)
        # 프롬프트에 문제마다 달라지는 칸(단원 이름·과목 줄 등)이 새로 생기면 그 칸도 where에 더할 것(bb 11-14)
        where = p["hint1"] + "\n" + p["hint2"]
        assert p["solution"] not in s
        assert not tok(a, where) or tok(a, p["text"]), (p["id"], a)


def test_leak_check_catches_forbidden_spellings():
    p = BY_ID["g4-math-large-numbers-01"]
    assert contains_answer("그건 7만이야", p["answer"], p["text"], p["forbidden"])
    assert contains_answer("70,000 맞지?", p["answer"], p["text"], p["forbidden"])
    assert not contains_answer("만의 자리부터 세어 봐", p["answer"], p["text"], p["forbidden"])


def test_leak_check_choice_text():
    p = BY_ID["g8-kor-parts-of-speech-01"]  # 정답 ② 관형사
    assert contains_answer("정답은 관형사야", p["answer"], p["text"], p["forbidden"])
    # 보기 글 둘 이상을 견주면 누설이 아니다
    assert not contains_answer(
        "관형사와 형용사가 어떻게 다른지 떠올려 봐", p["answer"], p["text"], p["forbidden"]
    )
    short = BY_ID["g8-kor-parts-of-speech-11"]  # 정답 보기 글 「세」(1글자) → 글 검사 안 함
    assert not contains_answer(
        "세 개를 세어 봐요", short["answer"], short["text"], short["forbidden"]
    )
    assert contains_answer("③이야", short["answer"], short["text"], short["forbidden"])


def test_scripts_have_no_math_words_in_study():
    text = (Path(__file__).resolve().parents[1] / "app" / "scripts" / "day3.yaml").read_text(
        "utf-8"
    )
    study = [ln for ln in text.splitlines() if "phase: study" in ln]
    for w in ("분자", "분모", "계산", "식을", "식이"):
        assert not any(w in ln for ln in study), w


def test_plain_unit_name_and_particle():
    from app.api import _obj_particle, plain_unit

    assert plain_unit("큰 수 (초4)") == "큰 수"
    assert plain_unit("분수 ÷ 자연수") == "분수 ÷ 자연수"
    n = plain_unit("관계사 (고1)")
    assert f"오늘 {n}{_obj_particle(n)} 다시 풀었어요." == "오늘 관계사를 다시 풀었어요."


def test_stuck_template_for_choice_and_text():
    from app.api import stuck_template

    assert stuck_template("품사", 2, True) == "품사 문제를 2번 고쳐 풀어 맞혔어요"
    assert stuck_template("품사", 3, False) == "품사 문제에서 3번 막혔어요"


async def test_text_problem_summary_does_not_call_llm():
    from types import SimpleNamespace

    from app.api import _stuck_phrase

    class Boom:
        async def reply(self, req):  # LLM을 부르면 실패
            raise AssertionError("LLM called")

    p = BY_ID["g10-eng-relative-clauses-01"]
    problem = SimpleNamespace(answer=p["answer"], text=p["text"], tag=p["tag"])
    row = SimpleNamespace(id="s", hint_level=1)
    student = SimpleNamespace(style="EBSP")
    out = await _stuck_phrase(Boom(), student, row, problem, ["③", "①"], solved=False)  # type: ignore[arg-type]
    assert out == "관계사 문제에서 2번 막혔어요"


def test_choice_hint_rule_in_study_prompt():
    s = _study(BY_ID["g10-eng-relative-clauses-16"])
    assert "보기 하나만 콕 집어 말하지 않는다" in s


def test_comparing_several_option_numbers_is_not_leak():
    # 명세 부록 D 「보기형 힌트」 보강 ②: 서로 다른 번호 2개 이상을 견주면 누설 아님
    p = BY_ID["g10-eng-relative-clauses-07"]
    a, t, f = p["answer"], p["text"], p["forbidden"]
    no = "①②③④".index(a["value"]) + 1
    others = [n for n in (1, 2, 3, 4) if n != no]
    assert not contains_answer(f"보기 {no}번이랑 {others[0]}번 중에 뭐가 맞을까?", a, t, f)
    assert not contains_answer(f"{a['value']}, {'①②③④'[others[1] - 1]} 둘을 견줘 봐", a, t, f)
    assert contains_answer(f"정답은 {no}번이야", a, t, f)  # 하나만 짚으면 그대로 누설


def test_choice_study_gets_turn_tail_no_numbers():
    # 명세 부록 D 「보기형 힌트」 보강 ①: 보기형 같이 풀기에만 대화 끝 지시
    def tail(pid: str, hint: int = 0) -> str | None:
        p = BY_ID[pid]
        return build_prompt(
            PromptInput(
                phase="study",
                grade_band="고1-3",
                honorific="friend",
                style="EBSP",
                polite=False,
                problem_text=p["text"],
                hint1=p["hint1"],
                hint2=p["hint2"],
                solution=p["solution"],
                hint_level=hint,
                judge=None,
                subject=subject_name(p["subject"]),
            )
        ).tail

    t = tail("g10-eng-relative-clauses-16") or ""
    assert "보기 번호" in t and "쓰지 않는다" in t
    assert tail("g4-math-large-numbers-01") is None  # 보기 없는 문제는 그대로
    assert (
        tail("g10-eng-relative-clauses-16", hint=3) is None
    )  # 풀이 보기 단계는 정답을 말해도 된다
