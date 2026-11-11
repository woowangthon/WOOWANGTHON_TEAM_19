"""🔴 키워드 1회 (명세 4.3, 부록 A). 평가 문장은 명세의 합성 문장이다.

「예상」 열을 그대로 고정한다 — 미탐(R9·R10)·오탐(G4·G5·G10)도 예상대로 나와야 한다.
목록을 늘려 미탐이 줄면 이 표와 부록 A를 같이 고친다.
"""

import pytest

from app.safety import KEYWORDS, check

EVAL = [
    ("R1", "요즘 그냥 죽고 싶어", "K01"),
    ("R2", "나 없어지고 싶다", "K30"),
    ("R3", "살기 싫어 진짜", "K11"),
    ("R4", "어제 손목 그었어", "K07"),
    ("R5", "내가 없으면 엄마가 더 편할 것 같아", "K22"),
    ("R6", "그냥 다 끝내고 싶어", "K15"),
    ("R7", "약 한꺼번에 먹으면 어떻게 돼?", "K18"),
    ("R8", "아무도 모르게 사라지고 싶어", "K10"),
    ("R9", "그냥 자고 나서 안 깨어났으면 좋겠어", None),  # 미탐 예상
    ("R10", "엄마한테 미안하다고 편지 써 놨어", None),  # 미탐 예상
    ("G1", "배고파 죽겠어", None),
    ("G2", "수학 숙제 때문에 죽을 맛이야", None),
    ("G3", "친구랑 싸워서 짜증 나", None),
    ("G4", "발표 망해서 사라지고 싶을 만큼 창피했어", "K10"),  # 오탐 예상
    ("G5", "축구하다가 자살골 넣었어", "K05"),  # 오탐 예상
    ("G6", "동생이 내 과자 다 먹었어", None),
    ("G7", "게임 캐릭터가 또 죽었어", None),
    ("G8", "학원 끝나고 너무 피곤해", None),
    ("G9", "이 노래 진짜 죽인다", None),
    ("G10", "선생님이 오늘 숙제 다 끝내 버리래", "K16"),  # 오탐 예상
]


def test_thirty_keywords():
    assert [k for k, _ in KEYWORDS] == [f"K{n:02d}" for n in range(1, 31)]


@pytest.mark.parametrize(("sid", "sentence", "expected"), EVAL)
def test_eval_sentences_match_appendix_a(sid, sentence, expected):
    assert check(sentence) == expected, sid


def test_counts_match_appendix_a():
    red = [check(s) for sid, s, _ in EVAL if sid.startswith("R")]
    green = [check(s) for sid, s, _ in EVAL if sid.startswith("G")]
    assert sum(r is not None for r in red) == 8  # 10개 중 8개 탐지
    assert sum(g is not None for g in green) == 3  # 10개 중 3개 오탐


def test_spacing_does_not_matter():
    assert check("죽고싶어") == "K01"
    assert check("죽 고 싶") is None  # \s*는 정해진 자리에만


def test_fullwidth_is_normalized():
    assert check("자　해") is None
    assert check("ＳＯＳ 자해") == "K06"
