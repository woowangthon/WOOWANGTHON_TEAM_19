"""PII 입력 필터 (명세 4.2 ②). 아이 텍스트·강사 메모를 저장·프롬프트 전에 치환한다.

잡는 것: 전화·이메일 정규식, DB에 있는 별명·연락처, "~학원/~초등학교/~중학교" 단어.
잡지 않는 것: 임의 이름("우리 반 지민이"). 한계로 명세에 적혀 있다.
"""

import re
import unicodedata
from collections.abc import Iterable

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 국번(0으로 시작, 또는 +82 뒤 0 생략, 괄호 허용) + 3~4자리 + 4자리.
# 구분자는 - – — . 하나(앞뒤 공백 허용), 공백만, 또는 없음.
_SEP = r"\s*[-–—.]?\s*"
_PHONE = re.compile(
    rf"(?<!\d)(?:\+82[-. ]?\(?0?|\(?0)\d{{1,2}}\)?{_SEP}\d{{3,4}}{_SEP}\d{{4}}(?!\d)"
)
_SCHOOL = re.compile(r"[가-힣A-Za-z0-9]+(?:학원|초등학교|중학교)")
# 치환 표시 낱말. 별명이 이 낱말과 같으면 별명 치환을 건너뛴다(표시가 깨지지 않게)
_MARKER_WORDS = {"이름", "전화", "이메일", "학교"}
_NAME_MARK = "[이름]"
# 기본은 별명을 가린다(fail closed). 별명으로 시작하는 일상어만 예외로 둔다(11-11 A6).
# 「지우」가 데모 이름이라 지우개·지우기 같은 말이 깨졌다. 별명을 바꾸면 이 목록도 본다.
# 「지우는」「지우야」처럼 이름+조사로도 읽히는 말은 넣지 않는다(가리는 쪽).
_EVERYDAY_WORDS = ("지우개", "지우기", "지우고", "지우면", "지우다", "지우자", "지우세요")


def _name_pattern(name: str) -> str:
    """별명 + (그 별명으로 시작하는 일상어가 아닐 때만)."""
    tails = sorted(
        (w[len(name) :] for w in _EVERYDAY_WORDS if w.startswith(name) and len(w) > len(name)),
        key=len,
        reverse=True,
    )
    skip = f"(?!{'|'.join(map(re.escape, tails))})" if tails else ""
    return re.escape(name) + skip


def redact(text: str, names: Iterable[str] = ()) -> str:
    """치환본을 돌려준다. 원문은 이 함수 밖으로 저장하지 않는다."""
    out = unicodedata.normalize("NFKC", text)  # 전각 숫자·기호를 반각으로
    out = _EMAIL.sub("[이메일]", out)
    out = _PHONE.sub("[전화]", out)
    out = _SCHOOL.sub("[학교]", out)
    # 본문과 같은 정규화를 별명에도 적용해야 전각·호환 문자로 저장된 별명이 빠지지 않는다
    normalized = {unicodedata.normalize("NFKC", n).strip() for n in names} - _MARKER_WORDS
    for name in sorted(filter(None, normalized), key=len, reverse=True):
        out = re.sub(_name_pattern(name), _NAME_MARK, out, flags=re.IGNORECASE)
    return out


def unredact_name(text: str | None, nickname: str | None) -> str | None:
    """사람이 읽는 화면에 보여 주기 직전에만 「[이름]」을 별명으로 되돌린다.

    저장본·AI 프롬프트에는 쓰지 않는다. 별명이 비어 있으면 그대로 둔다.
    """
    if text is None or nickname is None or not nickname.strip():
        return text
    return text.replace(_NAME_MARK, nickname.strip())
