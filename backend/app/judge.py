"""정답 판정 (명세 3.2 허용 입력 형식, 부록 B answer.kind). 순수 함수.

- 입력 전체가 한 가지 형식일 때만 판정한다. 숫자·분수 패턴이 없으면 None(판정 안 함 → 코칭).
- kind="value": 분수 값이 같으면 정답. kind="exact": accepted[] 표기만 정답.
- kind="choice": 보기 번호(②·2·2번) 또는 accepted 보기 문구. 번호가 아닌 말은 None.
- kind="text": accepted 낱말(대소문자·끝 문장부호 무시). 띄어 쓴 문장은 None(대화로 본다).
- 정답 값은 서버 판정에만 쓴다. 이 모듈 밖으로 정답 문자열을 내보내지 않는다.
"""

import re
import unicodedata
from fractions import Fraction
from typing import Any, Literal

Judge = Literal["correct", "wrong"]

_INT = r"\d+"
_FRAC = re.compile(rf"({_INT})/({_INT})")
_DECIMAL = re.compile(rf"{_INT}(?:\.\d+)?")  # 유한소수·정수만(순환소수 표기는 없음)
_KOREAN = re.compile(rf"({_INT}) ?분의 ?({_INT})")  # b분의 a
_MIXED = re.compile(rf"({_INT}) ({_INT})/({_INT})")  # n a/b
_DIVIDE = re.compile(rf"({_INT})÷({_INT})")  # a÷b
_TRAILING = ".!?~ "


def _canonical(text: str) -> str:
    """비교용 표기: 전각→반각, 앞뒤 공백·끝 문장부호 제거, 기호 둘레 공백 정리."""
    out = unicodedata.normalize("NFKC", text).strip().rstrip(_TRAILING)
    out = re.sub(r"\s*([/÷])\s*", r"\1", out)
    out = re.sub(r"\s+", " ", out)
    return out


def _fraction(num: str, den: str) -> Fraction | None:
    return Fraction(int(num), int(den)) if int(den) != 0 else None


def parse_value(text: str) -> Fraction | None:
    """허용 형식이면 분수 값, 아니면 None."""
    s = _canonical(text)
    if m := _MIXED.fullmatch(s):
        part = _fraction(m[2], m[3])
        return None if part is None else int(m[1]) + part
    if m := _FRAC.fullmatch(s):
        return _fraction(m[1], m[2])
    if m := _DIVIDE.fullmatch(s):
        return _fraction(m[1], m[2])
    if m := _KOREAN.fullmatch(s):
        return _fraction(m[2], m[1])
    if _DECIMAL.fullmatch(s):
        return Fraction(s)
    return None


_CIRCLED = "①②③④"  # 보기는 ①~④(생성 규칙)
_CHOICE = re.compile(r"([1-4])(?: ?번)?")


def _choice_no(text: str) -> int | None:
    """「②」「2」「2번」「②번」 → 2. 보기 번호 꼴이 아니면 None."""
    s = _canonical(text).replace("번", " 번").strip()
    s = re.sub(r"\s+", " ", s)
    for i, c in enumerate(_CIRCLED, 1):
        s = s.replace(c, str(i))
    m = _CHOICE.fullmatch(s)
    return int(m[1]) if m else None


def _word(text: str) -> str:
    return _canonical(text).casefold()


def _judge_choice(text: str, answer: dict[str, Any]) -> Judge | None:
    want = _choice_no(str(answer.get("value", "")))
    got = _choice_no(text)
    if got is not None:
        return "correct" if got == want else "wrong"
    if _word(text) in {_word(a) for a in answer.get("accepted", [])}:
        return "correct"
    return None


# 아이가 낱말 뒤에 붙이는 말끝(「부사요」「대명사예요」). 떼고 나서 정답 낱말과 같을 때만 정답
_KO_ENDINGS = ("입니다", "이에요", "예요", "이요", "이야", "이다", "요", "야", "임")


def _judge_text(text: str, answer: dict[str, Any]) -> Judge | None:
    accepted = {_word(a) for a in [answer.get("value", ""), *answer.get("accepted", [])] if a}
    word = _word(text)
    if word in accepted:
        return "correct"
    for end in _KO_ENDINGS:
        if word.endswith(end) and word[: -len(end)] in accepted:
            return "correct"
    return "wrong" if word and " " not in word and len(word) <= 20 else None


def judge(text: str, answer: dict[str, Any]) -> Judge | None:
    """ "correct" / "wrong" / None(패턴 없음 → 판정 안 함)."""
    if answer.get("kind") == "choice":
        return _judge_choice(text, answer)
    if answer.get("kind") == "text":
        return _judge_text(text, answer)
    value = parse_value(text)
    if value is None:
        return None
    if answer.get("kind") == "exact":
        accepted = {_canonical(a) for a in answer.get("accepted", [])}
        return "correct" if _canonical(text) in accepted else "wrong"
    return "correct" if value == Fraction(answer["value"]) else "wrong"


def _loose(text: str) -> str:
    """답 문장 비교용: _canonical에 더해 「8 분의 3」 둘레 공백도 붙인다."""
    return re.sub(r"\s*분의\s*", "분의", _canonical(text))


def _has_token(text: str, token: str) -> bool:
    # 앞뒤가 숫자·분수 기호면 다른 수의 일부다(13/8 안의 3/8, 3/4 안의 3, 3.5 안의 3)
    pattern = rf"(?<![\d./÷]){re.escape(token)}(?![\d/÷]|\.\d)"
    return re.search(pattern, text) is not None


def contains_answer(text: str, answer: dict[str, Any], problem_text: str = "") -> bool:
    """멘토 답 문장에 정답 값·허용 표기가 들어 있나(A4 사후 검사). 문장은 돌려주지 않는다.
    문제 글에 이미 보이는 표기(1 ÷ 3 문제의 「1÷3」)는 새는 게 아니라 뺀다."""
    if answer.get("kind") == "choice":
        # 보기 번호는 문제 글에 늘 보이므로 빼지 않는다. 「정답은 ②」「2번이야」를 잡는다
        no = _choice_no(str(answer.get("value", "")))
        if no is None:
            return False
        body = text  # NFKC는 ②를 2로 바꾸므로 원문에서 찾는다
        pattern = rf"{_CIRCLED[no - 1]}|(?<!\d){no} ?번"
        return re.search(pattern, body) is not None
    if answer.get("kind") == "text":
        words = [a for a in [answer.get("value", ""), *answer.get("accepted", [])] if a]
        return any(
            re.search(rf"(?<![A-Za-z가-힣]){re.escape(w)}(?![A-Za-z])", text, re.I)
            and not re.search(rf"(?<![A-Za-z]){re.escape(w)}(?![A-Za-z])", problem_text, re.I)
            for w in words
        )
    body, shown = _loose(text), _loose(problem_text)
    tokens = {_loose(t) for t in [str(answer.get("value", "")), *answer.get("accepted", [])]}
    return any(t and _has_token(body, t) and not _has_token(shown, t) for t in tokens)
