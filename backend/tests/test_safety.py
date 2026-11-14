"""🔴 키워드 1회 (명세 4.3, 부록 A). 평가 문장은 명세의 합성 문장이다.

「예상」 열을 그대로 고정한다 — 미탐(R9·R10)·오탐(G4·G10)도 예상대로 나와야 한다.
목록을 늘려 미탐이 줄면 이 표와 부록 A를 같이 고친다. R11~R23·G11~G17은 11-11 보강분.
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
    ("G5", "축구하다가 자살골 넣었어", None),  # 11-13 K05 「골」 제외
    ("G6", "동생이 내 과자 다 먹었어", None),
    ("G7", "게임 캐릭터가 또 죽었어", None),
    ("G8", "학원 끝나고 너무 피곤해", None),
    ("G9", "이 노래 진짜 죽인다", None),
    ("G10", "선생님이 오늘 숙제 다 끝내 버리래", "K16"),  # 오탐 예상
    # 11-11 보강(A2): 말끝 변화·맞춤법 틀림
    ("R11", "옥상에서 뛰어내릴까", "K09"),
    ("R12", "그냥 끝내버릴래", "K16"),
    ("R13", "죽어버릴까", "K31"),
    ("R14", "죽었으면 좋겠어", "K32"),
    ("R15", "나 죽을 거야", "K33"),
    ("R16", "죽고 시퍼", "K02"),
    ("R17", "죽구싶어", "K01"),
    ("R18", "살기시러", "K11"),
    # 11-11 공부 낱말 오탐 제외(A3) 뒤에도 원래 위험 문장은 잡힌다
    ("R19", "약을 한꺼번에", "K18"),
    ("R20", "목 매고", "K08"),
    ("R21", "그만 살래", "K13"),
    ("R22", "그만 살고 싶어", "K13"),
    ("R23", "내목매고싶어", "K08"),
    ("G11", "약분을 한꺼번에 하면 안 돼?", None),
    ("G12", "수학 과목 매일 하기 싫어", None),
    ("G13", "제목 매번", None),
    ("G14", "이제 그만 살살 해", None),
    ("G15", "배고파 죽을 거 같아", None),
    ("G16", "최대공약수를 한꺼번에", None),
    ("G17", "숙제 다 끝내버렸어", None),  # 11-11 F3: K16에서 과거형 「렸」 제외
]


def test_keyword_ids_are_sequential():
    # K01~K30 번호는 알림 행에 저장되므로 그대로, 새 패턴은 K31부터 덧붙인다
    assert [k for k, _ in KEYWORDS] == [f"K{n:02d}" for n in range(1, 34)]


@pytest.mark.parametrize(("sid", "sentence", "expected"), EVAL)
def test_eval_sentences_match_appendix_a(sid, sentence, expected):
    assert check(sentence) == expected, sid


def test_counts_match_appendix_a():
    red = [check(s) for sid, s, _ in EVAL if sid.startswith("R")]
    green = [check(s) for sid, s, _ in EVAL if sid.startswith("G")]
    assert sum(r is not None for r in red) == 21  # 23개 중 21개 탐지(R9·R10 미탐)
    assert sum(g is not None for g in green) == 2  # 17개 중 2개 오탐(G4·G10). G5는 11-13에 뺐다


def test_k16_still_catches_future_and_wish():
    # 과거형(끝내버렸어)만 뺐다. 앞으로 할 말·바람은 그대로 잡는다
    assert check("끝내버릴래") == "K16"
    assert check("끝내 버리고 싶어") == "K16"
    assert check("끝내버려야지") == "K16"
    assert check("끝내버렸어") is None


def test_spacing_does_not_matter():
    assert check("죽고싶어") == "K01"
    assert check("죽 고 싶") is None  # \s*는 정해진 자리에만


def test_fullwidth_is_normalized():
    assert check("자　해") is None
    assert check("ＳＯＳ 자해") == "K06"


@pytest.mark.parametrize(
    "sentence",
    ["오늘 축구에서 자살골 넣음ㅋㅋ", "자살골 넣었어", "피구는 아니고 축구 자살 골 말한 거야"],
)
def test_k05_own_goal_is_not_red(sentence):
    # 11-13: 「자살골」만 뺀다. 「자살 골」처럼 띄어 쓰면 그대로 잡는다(뜻이 갈리지 않게 좁게)
    expected = None if "자살골" in sentence else "K05"
    assert check(sentence) == expected


@pytest.mark.parametrize("sentence", ["자살골 넣었는데 진짜 자살하고 싶다", "자살하고 싶어"])
def test_k05_still_catches_real_mentions(sentence):
    assert check(sentence) is not None


@pytest.mark.parametrize(
    "sentence",
    ["죽​고 싶어", "자­살", "자‍살하고 싶어", "죽⁠고 싶어", "‮죽고 싶어"],
)
def test_invisible_format_chars_do_not_hide_red(sentence):
    # 11-14 이상 입력 점검: 보이지 않는 서식 문자(유니코드 Cf)를 끼우면 🔴을 피했다 → 검사 전에 지운다
    assert check(sentence) is not None


def test_spaced_letters_remain_a_known_limit():
    # 글자마다 띄운 「죽 고 싶 어」는 잡지 않는다 — 공백을 다 지우면 「자 살아 있네」가 「자살」로 붙어 오탐이 생긴다(부록 A)
    assert check("죽 고 싶 어") is None
    assert check("자 살아 있네") is None
