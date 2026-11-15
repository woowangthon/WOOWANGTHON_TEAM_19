"""pilot_blueprint_fixes.md + 11-13 두 번째 검토를 시범 3단원 설계도에 반영한다(여러 번 돌려도 같은 결과).
사용: python3 -I tools/patch_pilot_blueprints.py  (scratchpad에서)
"""

import json
import os

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(S, "bank")


def edit(fname, unit_id, fn, indent):
    path = os.path.join(B, fname)
    raw = open(path).read()
    data = json.loads(raw)
    for u in data:
        if u["unit_id"] == unit_id:
            fn(u)
    out = json.dumps(data, ensure_ascii=False, indent=indent)
    if raw.endswith("\n"):
        out += "\n"
    open(path, "w").write(out)


def math(u):
    u["misconceptions"] = [
        "'삼억 이천만'을 쓸 때 0의 개수를 빠뜨리거나 더 씀",
        "자릿수가 다른 두 수를 맨 앞 숫자만 보고 비교함",
        "세 자리 쉼표와 만 단위 네 자리 끊기를 섞어 자리 이름을 틀림",
        "뛰어 세기에서 받아올림이 생기는 자리를 놓침",
        "자릿수가 같은 두 수를 비교할 때 높은 자리가 같으면 아랫자리를 확인하지 않음",
        "가장 작은 수를 만들 때 0을 맨 앞에 놓음",
    ]
    u["problem_types"] = [
        {
            "type": "수에서 특정 숫자가 나타내는 값 구하기(예: 어느 자리 숫자 7이 나타내는 값)",
            "count": 3,
            "difficulty": "easy",
            "answer_form": "자연수",
            "covers": ["[4수01-01]"],
        },
        {
            "type": "한글로 쓴 큰 수를 숫자로 쓰기(예: 이억 오천만 삼백)",
            "count": 3,
            "difficulty": "easy",
            "answer_form": "자연수",
            "covers": ["[4수01-01]"],
        },
        {
            "type": "10배·100배 관계로 수 구하기(예: 1000만의 100배, 10배 하면 ○이 되는 수)",
            "count": 2,
            "difficulty": "medium",
            "answer_form": "자연수",
            "covers": ["[4수01-01]"],
            "conditions": "한 문제는 「○의 10배·100배」(만·억 표기 → 숫자), 한 문제는 거꾸로 「10배(100배) 하면 ○이 되는 수」. 정답은 10자리 이하.",
        },
        {
            "type": "○에서 시작해서 △씩 n번 뛰어 센 수 구하기(거꾸로 뛰어 세기 1문제 포함)",
            "count": 4,
            "difficulty": "medium",
            "answer_form": "자연수",
            "covers": ["[4수01-02]"],
            "conditions": "4문제 가운데 3문제 이상은 받아올림·받아내림이 있게. 거꾸로 뛰어 세기 1문제 포함. 「n번째 수」라고 쓰지 않음.",
        },
        {
            "type": "□ 안에 들어갈 수 있는 숫자 중 가장 큰(작은) 것 구하기로 크기 비교",
            "count": 4,
            "difficulty": "medium",
            "answer_form": "자연수(한 자리)",
            "covers": ["[4수01-02]"],
            "verify": "manual",
            "conditions": "정답은 1~9, 문제 속 상대 수의 같은 자리 숫자와 달라야 함(경계보다 하나 크거나 작게, 둘을 섞음). 정답 숫자가 문제 글에 따로 선 숫자로 보이지 않게. 4문제 중 1문제는 두 수의 자릿수가 다르게.",
        },
        {
            "type": "숫자 카드를 한 번씩 써서 조건에 맞는 가장 큰(작은) 수 또는 두 번째로 큰 수 만들기",
            "count": 4,
            "difficulty": "hard",
            "answer_form": "자연수",
            "covers": ["[4수01-01]", "[4수01-02]"],
            "verify": "manual",
            "conditions": "자리 조건이 하나 붙은 가장 큰(작은) 수 2문제 + 두 번째로 큰 수 1문제 + 두 번째로 작은 수 1문제. 조건 없는 「가장 작은 수」는 hard가 아님.",
        },
    ]
    u["difficulty_mix"] = {"easy": 6, "medium": 10, "hard": 4}
    u["answer_rules"] = [
        "문제 글 마지막 줄은 고정 문구 「(쉼표 없이 숫자만)」(규칙 v2 3.1, thousands_comma 단원).",
        "정답은 1 이상의 자연수 하나. 음수·천 단위 쉼표(1,234)·단위·글자·식·좌표·구간이 답이 되는 문제는 만들지 않는다.",
        "답은 쉼표 없이 숫자만(「250000300」). 만·억 글자를 섞어 쓰지 않는다.",
        "문제 글의 수는 숫자만 또는 만·억 섞기 가운데 한 가지(문제 안에서 섞지 않음, 단원 전체로는 둘 다 씀). 세 자리 쉼표는 쉼표 오개념 문항 1~2개의 문제 글에만.",
        "폰 입력 실수를 줄이려고 정답은 10자리 이하(억 단위까지)로 한다. 조 단위 수는 「어느 자리 숫자가 나타내는 값」처럼 답이 짧은 유형에서만, 단원당 2문제 이하.",
    ]
    u["notes"] = (
        "채점기는 천 단위 쉼표(1,234)를 읽지 못한다(needs_judge: thousands_comma). 채점기 확장 전까지 모든 문항에 쉼표 없이 숫자만 쓰게 안내한다. "
        "조 단위: 4-1 「큰 수」 단원이 조까지 다루므로 범위 안으로 본다(검토 의견). 다만 교과서 1차 확인 전에는 조 단위 문항을 단원당 2개 이하, 「숫자가 나타내는 값」 유형에만. "
        "학년 배치는 2022 검정 교과서 4-1(비상) 목차 [확인]과 4-2 관례 [추측]에 기댐. 성취기준은 3~4학년군 공통이라 3학년 내용과 섞이지 않게 범위를 적어 둠. "
        "core_concepts 「10배·100배 관계」는 시범 1판에 문항이 없어 「10배·100배 관계로 수 구하기」 유형(2문제)을 새로 두고, 「숫자가 나타내는 값」 4→3, 뛰어 세기 5→4로 줄였다(난이도 배분 easy 7·medium 9 → easy 6·medium 10)."
    )


def korean(u):
    u["misconceptions"] = [
        "'새', '옛' 같은 관형사를 형용사로 고름",
        "수량을 나타내면 무조건 수사라고 봄(관형사 '세' 사람)",
        "형용사도 '-는다'가 붙는다고 생각함(예쁜다)",
        "'이다'를 동사·형용사로 고름(조사인 서술격 조사)",
        "같은 낱말은 문장이 달라도 늘 품사가 같다고 봄",
        "가리켜 부르는 말(대명사)과 이름(명사)을 구별하지 못함",
        "꾸미는 말이면 모두 같은 품사로 봄(관형사·부사 혼동)",
        "앞말에 붙어 뜻을 더하는 조사(만·도·까지)를 따로 쓰이는 부사로 고름",
    ]
    pt = u["problem_types"]
    pt[0]["conditions"] = "조사 문항은 '이다'(서술격)만 내지 말고 격조사·보조사도 1문제 이상."
    pt[1]["conditions"] = "대상 낱말에 작은따옴표. accepted: 대명사는 「대명사·지시대명사·지시 대명사·인칭대명사·인칭 대명사」 가운데 맞는 것 모두."
    pt[2]["count"] = 2
    pt[3]["conditions"] = "'-는다/-ㄴ다', 명령('-어라')·청유('-자') 기준을 낱말에 직접 적용하는 판단만. '이다'의 품사 까닭은 이 유형에서 묻지 않음(첫 유형과 겹침)."
    pt[4]["type"] = "같은 낱말이 문장에 따라 품사가 바뀌는 경우(관형사/수사, 부사/명사, 수사/명사) 판단"
    pt[4]["count"] = 4
    pt[4]["conditions"] = "관형사/수사 2 · 부사/명사 1 · 명사/대명사 또는 수사/명사 1. (가)(나) 두 문장."
    pt[5]["difficulty"] = "medium"
    pt[5]["conditions"] = "외우면 풀리는 유형이라 medium."
    u["difficulty_mix"] = {"easy": 6, "medium": 10, "hard": 4}
    base = u["notes"].split(" 성취기준 코드 번호는 1차 확인 대기")[0]
    u["notes"] = base + (
        " 성취기준 코드 번호는 1차 확인 대기(NCIC 통합검색으로 확인 중) — 확인되면 단원에서 한 번 고치고 문항마다 review_note로 되풀이하지 않는다."
        " 통용 낱말 금지 목록(규칙 v2 8.1): 밝다·크다·붉다·늙다·굳다·길다·늦다·있다·감사하다·헌·다른·첫째·오늘·내일·어제·지금·여기·모두·다·정말·진짜·참·만세는 「같은 낱말의 품사가 바뀌는 경우」 유형에서만 쓴다."
        " '헌'은 동사 '헐다'(낡아지다)의 활용형과 뜻이 겹치고 「헌책」 같은 합성어도 있어 대상 낱말로 쓰지 않는다."
        " 힌트에 「관계언」「독립언」을 쓰지 않는다(묶음에 품사가 하나뿐이라 답이 됨). 「이다」 문항의 오답 보기에 「'-는다'를 붙일 수 없다」처럼 사실인 문장을 쓰지 않는다."
        " 입력 안내: 객관식 「(번호만 써 주세요)」, 단답 「(한 낱말로 써 주세요)」. forbidden: 객관식은 정답 기호만(보기가 문장이면 정답 문장도), 단답은 정답 낱말 단독."
        " 문장 속 낱말 표시는 작은따옴표로 하고 ①~④는 보기 줄에만 쓴다."
    )


def english(u):
    u["misconceptions"] = [
        "사람/사물에 따라 who·which 바꿔 씀",
        "관계대명사 뒤 문장에 목적어를 또 씀(the book which I read it)",
        "what과 that 혼동(선행사 유무)",
        "관계부사 where 뒤에 불완전한 문장(목적어 빠진 절)을 씀",
        "소유격 자리에 who·which를 쓰거나 whose 뒤에 his·its를 또 씀",
        "관계부사를 선행사 종류(장소·때·이유)와 맞추지 못함",
        "쉼표 뒤 계속적 용법에 that을 씀",
        "접속사 that과 관계대명사 that을 구별하지 못함",
        "빠진 것 없는 문장 앞에 전치사 없이 which를 씀(the house which I live)",
    ]
    pt = u["problem_types"]
    pt[0]["conditions"] = "전치사+관계대명사(in which 등)를 정답으로 묻는 문항 1문제 이상(이 유형이나 합치기 유형에서)."
    pt[2]["type"] = "빈칸에 관계사 한 단어 쓰기(정답이 하나뿐인 자리만: 소유격 whose, 선행사 없는 what, 관계부사 where/when/why, 쉼표 뒤 who/which)"
    pt[2]["conditions"] = (
        "that도 맞는 자리는 내지 않음. 5문제의 정답이 서로 다르게. 빈칸 뒤 동사는 목적어가 꼭 필요한 것(how·why가 못 들어가게), "
        "관계부사 자리는 목적어까지 다 있는 완전한 문장으로. 후보 10개(who·whom·which·that·whose·what·where·when·why·how) 대입 결과를 verify_note에."
    )
    pt[3]["conditions"] = "맞는 문장 셋은 서로 다른 문법 포인트. 접속사 that 문장은 단원당 1문제까지."
    u["out_of_scope"] = [
        "복합관계사(whoever, whatever)",
        "유사관계대명사 as/than/but",
        "관계사 생략(생략 여부 묻기, 관계사가 생략된 문장을 문제·보기에 쓰기), 주격 관계대명사 + be 생략",
        "도치·강조 구문",
        "whom, 전치사 + whom",
        "관계부사 how / the way",
    ]
    u["notes"] = (
        "관계대명사 who/which/that/whose는 [별표 4]에서 '중'이라 고1에선 복습+관계부사·what·계속적 용법이 핵심. "
        "forbidden: 객관식은 정답 기호만(두 문장 합치기처럼 보기가 문장이면 정답 문장도), 단답은 정답 낱말 단독(규칙 v2 7절). "
        "입력 안내: 객관식 「(번호만 써 주세요)」, 단답 「(영어 한 단어로 써 주세요)」. 문제 지시문·힌트·풀이는 해요체. 영어 문장에 é 같은 ASCII 밖 글자를 쓰지 않는다. "
        "학교별 진도 다름: 같은 언어 형식을 중3~고1에 걸쳐 다룬다 [추측]."
    )


edit("v2_blueprint_math.json", "g4-math-large-numbers", math, 1)
edit("v2_blueprint_korean.json", "g8-kor-parts-of-speech", korean, 1)
edit("v2_blueprint_english.json", "g10-eng-relative-clauses", english, 2)
print("ok")
