"""🔴 키워드 검사 1회 (명세 4.3, 부록 A K01–K30). LLM 호출 전, 입력마다.

- 정규식은 부록 A 그대로. 바꾸면 부록 A와 tests/test_safety.py의 평가 표를 같이 고친다.
- 원문은 이 함수 안에서만 본다. 돌려주는 것은 키워드 id뿐이다.
- 덜 잡는 쪽이다(목록 밖 표현은 놓친다). 한계는 명세 4.3에 적혀 있다.
"""

import re
import unicodedata

_PATTERNS = [
    r"죽고\s*싶",
    r"죽고\s*십",
    r"죽어\s*버리고\s*싶",
    r"죽을\s*래",
    r"자살",
    r"자해",
    r"손목.{0,3}(긋|그[어었])",
    r"목\s*매",
    r"뛰어\s*내리",
    r"사라지고\s*싶",
    r"살기\s*싫",
    r"살고\s*싶지\s*않",
    r"그만\s*살",
    r"태어나지\s*말",
    r"다\s*끝내고\s*싶",
    r"끝내\s*버리",
    r"칼로.{0,5}(손목|팔|나를)",
    r"약.{0,4}(한꺼번에|왕창)",
    r"수면제",
    r"유서",
    r"나\s*같은\s*(건|애는?)\s*없어도",
    r"내가\s*없으면.{0,10}(나을|좋을|편할)",
    r"죽는\s*게\s*(낫|나아)",
    r"죽는\s*방법",
    r"나를?\s*(때리고|다치게\s*하고)\s*싶",
    r"몸에\s*상처",
    r"높은\s*(데|곳)에?서.{0,5}(떨어|뛰)",
    r"영원히\s*잠들",
    r"하늘나라\s*(가고|갈래)",
    r"없어지고\s*싶",
]

KEYWORDS: list[tuple[str, re.Pattern[str]]] = [
    (f"K{i:02d}", re.compile(p)) for i, p in enumerate(_PATTERNS, start=1)
]


def check(text: str) -> str | None:
    """첫 매치의 키워드 id(K01 식), 없으면 None."""
    normalized = unicodedata.normalize("NFKC", text)  # 전각 문자를 반각으로(pii와 같은 정규화)
    for kid, pattern in KEYWORDS:
        if pattern.search(normalized):
            return kid
    return None
