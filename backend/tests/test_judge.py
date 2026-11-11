"""정답 판정 (명세 3.2 허용 입력 형식 표, 부록 B kind)."""

import json
from fractions import Fraction

import pytest

from app.judge import judge, parse_value
from app.seed import SEED_PATH

SEED = json.loads(SEED_PATH.read_text(encoding="utf-8"))
ACCEPTED = [(p["id"], p["answer"], a) for p in SEED for a in p["answer"]["accepted"]]


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("3/8", Fraction(3, 8)),
        ("0.375", Fraction(3, 8)),
        ("8분의 3", Fraction(3, 8)),
        ("8 분의 3", Fraction(3, 8)),
        ("1 1/2", Fraction(3, 2)),
        ("3÷8", Fraction(3, 8)),
        ("3 ÷ 8", Fraction(3, 8)),
        ("7", Fraction(7)),
        (" 3 / 8 ", Fraction(3, 8)),
        ("3/8.", Fraction(3, 8)),
        ("３/８", Fraction(3, 8)),  # 전각 숫자
    ],
)
def test_parse_value_formats(text, value):
    assert parse_value(text) == value


@pytest.mark.parametrize("text", ["이거 어떻게 해?", "", "몰라", "3/0", "1÷0", "3/8 아니면 3/4"])
def test_parse_value_no_pattern(text):
    assert parse_value(text) is None


@pytest.mark.parametrize(("pid", "answer", "text"), ACCEPTED)
def test_every_accepted_form_is_correct(pid, answer, text):
    assert judge(text, answer) == "correct", pid


def test_seed_has_at_least_60_accepted_forms():
    assert len(ACCEPTED) >= 60  # 명세 3.2: 20문제 × 3표기


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3/4", "wrong"),
        ("0.38", "wrong"),  # 근사는 오답
        ("3÷4", "wrong"),
        ("6/16", "correct"),  # value: 값이 같으면 정답
        ("이거 어떻게 해?", None),
        ("모르겠어", None),
    ],
)
def test_value_kind(text, expected):
    answer = {"kind": "value", "value": "3/8", "accepted": ["3/8"]}
    assert judge(text, answer) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1/6", "correct"),
        ("6분의 1", "correct"),
        ("2/12", "wrong"),  # exact: 값은 같아도 기약분수가 아니면 오답
        ("0.1666", "wrong"),
        ("힌트 줘", None),
    ],
)
def test_exact_kind(text, expected):
    answer = {"kind": "exact", "value": "1/6", "accepted": ["1/6", "6분의 1"]}
    assert judge(text, answer) == expected


def test_one_third_repeating_decimal_is_wrong():
    answer = {"kind": "value", "value": "1/3", "accepted": ["1/3"]}
    assert judge("0.333", answer) == "wrong"
