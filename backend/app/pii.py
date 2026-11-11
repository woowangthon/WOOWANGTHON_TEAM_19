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


def redact(text: str, names: Iterable[str] = ()) -> str:
    """치환본을 돌려준다. 원문은 이 함수 밖으로 저장하지 않는다."""
    out = unicodedata.normalize("NFKC", text)  # 전각 숫자·기호를 반각으로
    out = _EMAIL.sub("[이메일]", out)
    out = _PHONE.sub("[전화]", out)
    out = _SCHOOL.sub("[학교]", out)
    # 본문과 같은 정규화를 별명에도 적용해야 전각·호환 문자로 저장된 별명이 빠지지 않는다
    normalized = {unicodedata.normalize("NFKC", n).strip() for n in names} - _MARKER_WORDS
    for name in sorted(filter(None, normalized), key=len, reverse=True):
        out = re.sub(re.escape(name), "[이름]", out, flags=re.IGNORECASE)
    return out
