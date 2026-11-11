"""PII 입력 필터 (명세 4.2). 문장은 전부 합성 값."""

import pytest

from app.pii import redact


@pytest.mark.parametrize(
    "raw",
    ["010-1234-5678", "01012345678", "010 1234 5678", "02-123-4567", "010.1234.5678"],
)
def test_phone_numbers_are_replaced(raw):
    assert redact(f"번호는 {raw} 이야") == "번호는 [전화] 이야"


def test_email_is_replaced():
    assert redact("메일 test.user+a@example.co.kr 로") == "메일 [이메일] 로"


@pytest.mark.parametrize("word", ["가나학원", "다라초등학교", "마바중학교"])
def test_school_and_academy_words_are_replaced(word):
    assert redact(f"나 {word}에 다녀") == "나 [학교]에 다녀"


def test_known_names_are_replaced():
    assert redact("테스트학생이 그랬어", names=["테스트학생"]) == "[이름]이 그랬어"


def test_blank_known_names_are_ignored():
    assert redact("3/8", names=["", "  "]) == "3/8"


@pytest.mark.parametrize("answer", ["3/8", "0.375", "8분의 3", "1 1/2", "3÷8", "12/35", "2.25"])
def test_math_answers_are_untouched(answer):
    assert redact(answer) == answer


def test_arbitrary_names_are_not_caught():
    # 명세 4.2: 임의 이름은 잡지 않는다(한계). 바뀌면 이 테스트를 고친다.
    assert redact("짝꿍 가나다랑 놀았어") == "짝꿍 가나다랑 놀았어"


@pytest.mark.parametrize(
    "raw",
    ["+82 10-1234-5678", "+82-10-1234-5678", "+821012345678", "(02) 123-4567", "(010)1234-5678"],
)
def test_phone_variants_are_replaced(raw):
    assert redact(f"번호는 {raw} 이야") == "번호는 [전화] 이야"


def test_fullwidth_digits_are_normalized_before_matching():
    assert redact("번호는 ０１０-１２３４-５６７８ 이야") == "번호는 [전화] 이야"


def test_known_names_match_case_insensitively():
    assert redact("TESTKID said hi", names=["testkid"]) == "[이름] said hi"


def test_fullwidth_known_name_matches_normalized_text():
    # 별명이 전각으로 저장돼 있어도 정규화된 본문에서 잡혀야 한다
    assert redact("Kid 왔어", names=["Ｋｉｄ"]) == "[이름] 왔어"


@pytest.mark.parametrize("raw", ["010 - 1234 - 5678", "010–1234–5678", "010—1234—5678"])
def test_phone_with_spaced_or_dash_variants(raw):
    # B14: 공백 낀 하이픈·en dash·em dash도 잡는다(합성 번호)
    assert redact(f"번호는 {raw} 이야") == "번호는 [전화] 이야"


@pytest.mark.parametrize("name", ["이름", "전화", "이메일", "학교"])
def test_nickname_equal_to_marker_word_does_not_break_markers(name):
    # B14: 별명이 치환 표시 낱말과 같으면 별명 치환을 건너뛴다
    out = redact("번호 010-1234-5678 메일 a@example.com 가나학원", names=[name])
    assert out == "번호 [전화] 메일 [이메일] [학교]"
