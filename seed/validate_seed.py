#!/usr/bin/env python3
"""시드 문제 검증기 (표준 라이브러리만 사용).

실행:  python3 -I validate_seed.py seed_v0.1.json

검사 항목
  (a) 필수 필드·타입 / 태그·성취기준 코드 정합 / solution에 정답 표기 포함
  (b) id 유일, 태그당 5개, id가 태그로 시작
  (c) expr 평가값 == answer.value (Fraction 비교)
  (d) accepted[] 각 표기를 명세 3.2 허용 형식으로 파싱 → 전부 같은 값
  (e) text·hint1·hint2 에 정답의 어떤 표기도 없음 (자동 생성 표기로 검사)
  (f) forbidden 이 자동 생성 표기를 모두 포함
  (g) exact 문제는 accepted 가 1~2개
통과 시 요약 통계(태그별 수, 답>1, 자연수 답, 문장형 수) 출력.
"""
import ast
import json
import re
import sys
from collections import Counter
from fractions import Fraction

EXPECTED_TAGS = {
    "frac-div-nat": 5,
    "nat-div-nat": 5,
    "frac-div-frac-same": 5,
    "frac-div-frac-diff": 5,
}
TAG_TO_CODE = {
    "frac-div-nat": "[6수01-11]",
    "nat-div-nat": "[6수01-10]",
    "frac-div-frac-same": "[6수01-11]",
    "frac-div-frac-diff": "[6수01-11]",
}
REQUIRED = {
    "id": str, "tag": str, "standard": dict, "grade": int, "text": str,
    "expr": str, "answer": dict, "hint1": str, "hint2": str,
    "solution": str, "forbidden": list,
}
EXACT_ACCEPTED_RANGE = (1, 2)


# ---------- expr 평가 (Fraction, 안전한 AST만) ----------
def eval_expr(expr: str) -> Fraction:
    tree = ast.parse(expr.strip(), mode="eval")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int) and not isinstance(n.value, bool):
            return Fraction(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b
        raise ValueError(f"허용되지 않은 식 요소: {ast.dump(n)}")

    return ev(tree)


# ---------- 명세 3.2 허용 입력 형식 파서 ----------
_RE_FRAC = re.compile(r"^(\d+)\s*/\s*(\d+)$")
_RE_DEC = re.compile(r"^(\d+)(?:\.(\d+))?$")
_RE_KOR = re.compile(r"^(\d+)분의\s*(\d+)$")
_RE_MIXED = re.compile(r"^(\d+)\s+(\d+)\s*/\s*(\d+)$")
_RE_DIVSIGN = re.compile(r"^(\d+)\s*÷\s*(\d+)$")


def parse_input(s: str) -> Fraction:
    """3.2 표: a/b, 소수(유한), b분의 a, n a/b, a÷b. 그 외는 ValueError."""
    s = s.strip()
    if m := _RE_FRAC.match(s):
        return Fraction(int(m[1]), int(m[2]))
    if m := _RE_DEC.match(s):
        return Fraction(s)  # Fraction("0.375") 는 정확히 3/8
    if m := _RE_KOR.match(s):
        return Fraction(int(m[2]), int(m[1]))
    if m := _RE_MIXED.match(s):
        return Fraction(int(m[1])) + Fraction(int(m[2]), int(m[3]))
    if m := _RE_DIVSIGN.match(s):
        return Fraction(int(m[1]), int(m[2]))
    raise ValueError(f"허용 형식이 아님: {s!r}")


# ---------- 정답 표기 자동 생성 ----------
def finite_decimal(v: Fraction):
    """유한소수면 문자열, 아니면 None."""
    d = v.denominator
    k = 0
    while d % 2 == 0:
        d //= 2
        k += 1
    while d % 5 == 0:
        d //= 5
        k += 1
    if d != 1:
        return None
    scale = 10 ** k if k else 1
    # 10^k 로 늘렸을 때 분모가 2^a5^b 이면 정수가 됨 (k = max(a,b) 필요)
    while (v * scale).denominator != 1:
        scale *= 10
        k += 1
    n = (v * scale).numerator
    s = str(n).rjust(k + 1, "0")
    return s if k == 0 else f"{s[:-k]}.{s[-k:]}"


def answer_forms(v: Fraction) -> set:
    """기약분수·소수(유한)·한글 분수·대분수 표기. a÷b 형식은 문제 자체와 겹치므로 제외."""
    forms = set()
    a, b = v.numerator, v.denominator
    if b == 1:
        forms.add(str(a))
        return forms
    forms.add(f"{a}/{b}")
    forms.add(f"{b}분의 {a}")
    forms.add(f"{b}분의{a}")
    dec = finite_decimal(v)
    if dec is not None:
        forms.add(dec)
    if a > b:
        n, r = divmod(a, b)
        forms.add(f"{n} {r}/{b}")
        forms.add(f"{n}{_gwa_wa(n)} {b}분의 {r}")
    return forms


def _gwa_wa(n: int) -> str:
    """'n과/와' 조사: 끝 자리를 한국어로 읽었을 때 받침 유무로 결정.
    1(일)3(삼)6(육)7(칠)8(팔)·0(십/백/천) → 과, 2(이)4(사)5(오)9(구) → 와."""
    return "와" if n % 10 in (2, 4, 5, 9) else "과"


def contains_form(text: str, form: str) -> bool:
    """경계를 보는 부분 문자열 검사: 앞뒤가 숫자·'/'·'.' 이면 다른 수의 일부로 보고 제외.
    예) 답 '2' 는 '2/5' 의 2 와는 매치되지 않지만 '2명' 의 2 와는 매치됨(의도된 엄격함)."""
    pat = r"(?<![0-9./])" + re.escape(form) + r"(?![0-9./])"
    return re.search(pat, text) is not None


# ---------- 검사 ----------
class Report:
    def __init__(self):
        self.fails = []

    def fail(self, pid, check, msg):
        self.fails.append((pid, check, msg))


def check_problem(p: dict, rep: Report):
    pid = p.get("id", "<no id>")

    # (a) 필드·타입
    for k, t in REQUIRED.items():
        if k not in p:
            rep.fail(pid, "a", f"필수 필드 없음: {k}")
        elif not isinstance(p[k], t) or (t is int and isinstance(p[k], bool)):
            rep.fail(pid, "a", f"타입 오류: {k} 는 {t.__name__} 이어야 함")
    if any(f[0] == pid and f[1] == "a" for f in rep.fails):
        return None  # 구조가 깨졌으면 아래 검사는 의미 없음

    std = p["standard"]
    for k in ("code", "curriculum", "unit"):
        if not isinstance(std.get(k), str) or not std[k]:
            rep.fail(pid, "a", f"standard.{k} 누락/타입 오류")
    if std.get("curriculum") != "2022":
        rep.fail(pid, "a", f"standard.curriculum 은 '2022' 이어야 함: {std.get('curriculum')!r}")
    if std.get("unit") != "분수의 나눗셈":
        rep.fail(pid, "a", f"standard.unit 은 '분수의 나눗셈' 이어야 함: {std.get('unit')!r}")
    if p["grade"] != 6:
        rep.fail(pid, "a", f"grade 는 6 이어야 함: {p['grade']}")
    if p["tag"] not in EXPECTED_TAGS:
        rep.fail(pid, "a", f"알 수 없는 태그: {p['tag']}")
    elif std.get("code") != TAG_TO_CODE[p["tag"]]:
        rep.fail(pid, "a", f"태그 {p['tag']} 의 성취기준 코드는 {TAG_TO_CODE[p['tag']]} 이어야 함: {std.get('code')!r}")
    ans = p["answer"]
    if ans.get("kind") not in ("value", "exact"):
        rep.fail(pid, "a", f"answer.kind 는 value|exact: {ans.get('kind')!r}")
    if not isinstance(ans.get("value"), str) or not ans["value"]:
        rep.fail(pid, "a", "answer.value 는 비어 있지 않은 문자열")
    if not isinstance(ans.get("accepted"), list) or not ans["accepted"] or not all(isinstance(x, str) for x in ans["accepted"]):
        rep.fail(pid, "a", "answer.accepted 는 문자열 리스트(1개 이상)")
    if not all(isinstance(x, str) for x in p["forbidden"]):
        rep.fail(pid, "a", "forbidden 은 문자열 리스트")
    for k in ("text", "hint1", "hint2", "solution"):
        if not p[k].strip():
            rep.fail(pid, "a", f"{k} 가 비어 있음")
    if p["hint1"].strip() == p["hint2"].strip():
        rep.fail(pid, "a", "hint1 과 hint2 가 같음")
    if not p["id"].startswith(p["tag"] + "-"):
        rep.fail(pid, "b", f"id 는 '{p['tag']}-' 로 시작해야 함")

    # (c) expr == answer.value
    try:
        v_expr = eval_expr(p["expr"])
    except Exception as e:  # noqa: BLE001
        rep.fail(pid, "c", f"expr 평가 실패: {e}")
        return None
    try:
        v_ans = parse_input(ans["value"])
    except Exception as e:  # noqa: BLE001
        rep.fail(pid, "c", f"answer.value 파싱 실패: {e}")
        return None
    if v_expr != v_ans:
        rep.fail(pid, "c", f"expr={p['expr']!r} → {v_expr}, answer.value={ans['value']!r} → {v_ans} 불일치")
    if v_expr <= 0:
        rep.fail(pid, "c", f"정답이 양수가 아님: {v_expr}")
    # 기약분수 표기 강제 (value 는 항상 기약분수 또는 정수)
    canon = str(v_expr.numerator) if v_expr.denominator == 1 else f"{v_expr.numerator}/{v_expr.denominator}"
    if ans["value"] != canon:
        rep.fail(pid, "c", f"answer.value 는 기약분수/정수 표기여야 함: {ans['value']!r} (기대 {canon!r})")

    # (d) accepted 전부 파싱되고 같은 값
    for s in ans["accepted"]:
        try:
            v = parse_input(s)
        except Exception as e:  # noqa: BLE001
            rep.fail(pid, "d", f"accepted {s!r}: {e}")
            continue
        if v != v_expr:
            rep.fail(pid, "d", f"accepted {s!r} → {v} ≠ 정답 {v_expr}")
    if ans["value"] not in ans["accepted"]:
        rep.fail(pid, "d", f"accepted 에 answer.value {ans['value']!r} 가 없음")

    # (e) text·hint 에 정답 표기 없음
    forms = answer_forms(v_expr)
    for field in ("text", "hint1", "hint2"):
        for f in sorted(forms):
            if contains_form(p[field], f):
                rep.fail(pid, "e", f"{field} 에 정답 표기 {f!r} 포함: {p[field]!r}")

    # (f) forbidden ⊇ forms
    missing = sorted(forms - set(p["forbidden"]))
    if missing:
        rep.fail(pid, "f", f"forbidden 에 빠진 표기: {missing}")
    for s in p["forbidden"]:
        try:
            v = parse_input(s)
        except ValueError:
            # '1과 4분의 3' 같은 자유 표기는 파싱 대상 아님 → 값 검증 생략
            continue
        if v != v_expr:
            rep.fail(pid, "f", f"forbidden {s!r} → {v} 가 정답 {v_expr} 와 다름")

    # (g) exact 는 accepted 1~2개
    if ans.get("kind") == "exact":
        lo, hi = EXACT_ACCEPTED_RANGE
        if not (lo <= len(ans["accepted"]) <= hi):
            rep.fail(pid, "g", f"exact 문제의 accepted 는 {lo}~{hi}개여야 함: {len(ans['accepted'])}개")
        if "기약분수" not in p["text"]:
            rep.fail(pid, "g", "exact 문제의 text 에 표기 요구('기약분수')가 없음")

    # solution 에는 정답 표기가 있어야 함 (풀이 보기 화면용)
    if not any(contains_form(p["solution"], f) for f in forms):
        rep.fail(pid, "a", f"solution 에 정답 표기가 없음: {p['solution']!r}")

    return v_expr


def main(argv):
    if len(argv) != 2:
        print("사용법: python3 -I validate_seed.py seed_v0.1.json", file=sys.stderr)
        return 2
    path = argv[1]
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        print("FAIL: 최상위는 배열이어야 함")
        return 1

    rep = Report()
    values = {}
    for i, p in enumerate(data):
        if not isinstance(p, dict):
            rep.fail(f"#{i}", "a", "문제 항목이 객체가 아님")
            continue
        v = check_problem(p, rep)
        if v is not None:
            values[p["id"]] = (p, v)

    # (b) id 유일, 태그당 개수
    ids = [p.get("id") for p in data if isinstance(p, dict)]
    for pid, n in Counter(ids).items():
        if n > 1:
            rep.fail(pid, "b", f"id 중복 {n}회")
    tag_count = Counter(p.get("tag") for p in data if isinstance(p, dict))
    for tag, want in EXPECTED_TAGS.items():
        if tag_count.get(tag, 0) != want:
            rep.fail("<all>", "b", f"태그 {tag} 는 {want}개여야 함: {tag_count.get(tag, 0)}개")
    for tag in tag_count:
        if tag not in EXPECTED_TAGS:
            rep.fail("<all>", "b", f"정의되지 않은 태그: {tag}")
    if len(data) != sum(EXPECTED_TAGS.values()):
        rep.fail("<all>", "b", f"총 {sum(EXPECTED_TAGS.values())}문제여야 함: {len(data)}문제")

    if rep.fails:
        print(f"FAIL: {len(rep.fails)}건")
        for pid, check, msg in rep.fails:
            print(f"  [{check}] {pid}: {msg}")
        return 1

    # 통과 → 요약 통계
    n_gt1 = sum(1 for _, v in values.values() if v > 1)
    n_nat = sum(1 for _, v in values.values() if v.denominator == 1)
    n_word = sum(1 for p, _ in values.values() if "÷" not in p["text"])
    n_exact = sum(1 for p, _ in values.values() if p["answer"]["kind"] == "exact")
    n_accepted = sum(len(p["answer"]["accepted"]) for p, _ in values.values())
    print(f"PASS: {len(data)}문제, 검사 (a)~(g) 전부 통과  [{path}]")
    print("  태그별:", ", ".join(f"{t}={tag_count[t]}" for t in EXPECTED_TAGS))
    print(f"  성취기준:", ", ".join(f"{c}={n}" for c, n in sorted(Counter(p['standard']['code'] for p, _ in values.values()).items())))
    print(f"  답 > 1: {n_gt1}개 (요구 ≥2)")
    print(f"  자연수 답: {n_nat}개 (요구 ≥2)")
    print(f"  문장형(text 에 ÷ 없음): {n_word}개 (요구 ≥8)")
    print(f"  exact: {n_exact}개 (요구 2~3)")
    print(f"  accepted 총 {n_accepted}건 파싱·값 일치")
    ok = n_gt1 >= 2 and n_nat >= 2 and n_word >= 8 and 2 <= n_exact <= 3
    if not ok:
        print("WARN: 구성 요구(답>1 ≥2, 자연수 ≥2, 문장형 ≥8, exact 2~3)를 만족하지 않음")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
