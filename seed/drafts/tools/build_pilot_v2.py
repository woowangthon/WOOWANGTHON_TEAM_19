"""시범 60문제를 검토 결과대로 고쳐 v2 스키마로 쓴다(bank/problems_v2/). 원본 bank/problems/는 건드리지 않는다.
사용: python3 -I tools/build_pilot_v2.py  (scratchpad에서)
"""

import json
import os
import re
from itertools import permutations

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(S, "bank", "problems")
OUT = os.path.join(S, "bank", "problems_v2")
GEN = "claude-opus-5-5"

ORDER = ["id", "unit_id", "tag", "subject", "grade", "standard", "difficulty", "problem_type",
         "targets_misconception", "text", "expr", "verify", "verify_note", "answer", "hint1", "hint2",
         "after_hint2", "solution", "forbidden", "source", "generator", "review", "review_note"]

CIRC = "①②③④"


def load(u):
    return {p["id"]: p for p in json.load(open(os.path.join(SRC, u + ".json")))}


def ordered(p):
    out = {k: p[k] for k in ORDER if k in p}
    for k in p:
        if k not in out:
            raise SystemExit(f"{p['id']}: 모르는 칸 {k}")
    return out


def choice_answer(text, sym):
    """보기 줄에서 정답 문구를 읽어 accepted를 만든다."""
    for line in text.split("\n"):
        if line.startswith(sym):
            opt = line[1:].strip()
            n = CIRC.index(sym) + 1
            return {"kind": "choice", "value": sym, "accepted": [sym, str(n), f"{n}번", opt]}, opt
    raise SystemExit(f"보기 {sym} 없음: {text[:40]}")


# ───────────────────────── 수학 ─────────────────────────
DIG = "영일이삼사오육칠팔구"


def _kor4(n):
    s = ""
    for val, name in ((1000, "천"), (100, "백"), (10, "십")):
        d = n // val % 10
        if d:
            s += ("" if d == 1 else DIG[d]) + name
    if n % 10:
        s += DIG[n % 10]
    return s


def kor_read(n):
    parts = []
    for i, unit in enumerate(["", "만", "억", "조"]):
        g = n // (10000 ** i) % 10000
        if g:
            w = _kor4(g)
            if unit == "만" and g == 1:
                w = ""
            parts.append(w + unit)
    return " ".join(reversed(parts))


def manok(n):
    parts = []
    for i, unit in enumerate(["", "만", "억", "조"]):
        g = n // (10000 ** i) % 10000
        if g:
            parts.append(f"{g}{unit}")
    return " ".join(reversed(parts))


def math_forbidden(v, text):
    forms = [str(v)]
    if v >= 1000:
        forms.append(f"{v:,}")
    if v >= 10000:
        forms += [manok(v), kor_read(v)]
    out = []
    for f in forms:
        # 문제 글에 '따로 선' 표기로 보이면 뺀다(다른 수의 일부인 숫자는 보이는 것으로 치지 않음)
        if re.search(r"(?<![0-9.,/])" + re.escape(f) + r"(?![0-9.,/])", text) or f in out:
            continue
        out.append(f)
    return out


def box_check(text_expr, op, other, want):
    """□ 유형 전수 대입: □에 0~9."""
    ok = []
    for d in range(10):
        s = text_expr.replace("□", str(d))
        a = int(s)
        if len(str(a)) != len(s):  # 맨 앞 0 → 자릿수가 줄어듦
            note_zero = True
        good = a < other if op == "<" else a > other
        if good and len(str(a)) == len(s):
            ok.append(d)
    lines = []
    for d in range(10):
        s = text_expr.replace("□", str(d))
        a = int(s)
        rel = "<" if a < other else ">"
        lines.append(f"{d}→{a}{rel}{other}")
    res = max(ok) if want == "max" else min(ok)
    return res, ok, lines


def card_all(cards):
    n = len(cards)
    nums = sorted({int("".join(map(str, p))) for p in permutations(cards) if p[0] != 0})
    return nums, n


MATH = {}

MATH["01"] = dict(
    text="58274163에서 숫자 7이 나타내는 값은 얼마인가요?\n(쉼표 없이 숫자만)",
    after_hint2="7이 오른쪽에서 몇 번째 자리인지 세어 자리 이름을 정하고, 그 자리 값만큼 0을 붙여 쓰기",
)
MATH["02"] = dict(
    text="어떤 책에 큰 수가 세 자리마다 쉼표를 찍어 2,948,503,617로 적혀 있어요. 이 수에서 숫자 9가 나타내는 값은 얼마인가요?\n(쉼표 없이 숫자만)",
    after_hint2="네 자리씩 끊은 뒤 9가 억 묶음의 어느 자리인지 정하고 그 값을 숫자로 쓰기",
)
MATH["03"] = dict(
    text="53조 6047억 2918만 3500에서 숫자 1이 나타내는 값은 얼마인가요?\n(쉼표 없이 숫자만)",
    hint2="1은 '2918만' 묶음 안에 있어요. 이 묶음의 네 숫자에 왼쪽부터 자리 이름을 차례로 붙여 보세요.",
    after_hint2="만 묶음 안에서 1의 자리 이름을 스스로 정하고 그 값을 숫자로 쓰기",
)
MATH["04"] = dict(
    difficulty="medium",
    problem_type="10배·100배 관계로 수 구하기(예: 1000만의 100배, 10배 하면 ○이 되는 수)",
    targets_misconception="'삼억 이천만'을 쓸 때 0의 개수를 빠뜨리거나 더 씀",
    text="3700만의 100배는 얼마인가요?\n(쉼표 없이 숫자만)",
    expr="3700*10000*100",
    answer_value="3700000000",
    hint1="어떤 수를 100배 하면 각 자리 숫자가 왼쪽으로 몇 자리씩 옮겨 가나요?",
    hint2="먼저 3700만을 쉼표 없이 숫자로만 써 보세요. 그다음 100배 하면 끝에 0이 몇 개 더 붙는지 따져 보세요.",
    after_hint2="3700만을 숫자로 바꾸고, 100배로 늘어나는 0의 개수를 정해 붙인 열 자리 수 쓰기",
    solution="3700만은 37000000이에요. 100배 하면 각 숫자가 두 자리씩 왼쪽으로 옮겨 가서 끝에 0이 두 개 더 붙어요. 그래서 3700000000(37억)이에요.",
)
MATH["05"] = dict(
    text="칠억 사천만 육백을 숫자로 써 보세요.\n(쉼표 없이 숫자만)",
    hint2="'사천만'은 만 묶음 네 자리 가운데 한 자리만 채워요. 나머지 세 자리에는 무엇을 써야 할까요? '육백'도 일 묶음 네 자리로 생각해 보세요.",
    after_hint2="만 묶음과 일 묶음의 빈자리에 0을 채워 네 자리씩 만든 뒤 억 묶음 뒤에 이어 쓰기",
)
MATH["06"] = dict(
    text="구천육십만 이천팔을 숫자로 써 보세요.\n(쉼표 없이 숫자만)",
    after_hint2="구천육십과 이천팔에서 비는 자리를 찾아 0을 넣어 각각 네 자리로 쓰고 이어 쓰기",
)
MATH["07"] = dict(
    text="이십삼억 오백만 칠십을 숫자로 써 보세요.\n(쉼표 없이 숫자만)",
    hint2="'오백만'은 만 묶음에서 백의 자리만 채워져요. 만 묶음과 일 묶음에서 비는 자리가 각각 몇 개인지 세어 보세요.",
    after_hint2="두 묶음의 빈자리 수만큼 0을 채워 네 자리씩 만들고 23 뒤에 이어 쓰기",
)
T2 = "○에서 시작해서 △씩 n번 뛰어 센 수 구하기(거꾸로 뛰어 세기 1문제 포함)"
MATH["08"] = dict(
    problem_type=T2,
    text="4500000에서 시작해서 100000씩 6번 뛰어 센 수는 얼마인가요?\n(쉼표 없이 숫자만)",
    hint1="100000은 어느 자리의 1인지 먼저 찾아보세요. 그 자리 숫자가 한 번에 얼마씩 커지나요?",
    after_hint2="십만의 자리 5에 6번 1씩 더하면서 받아올림이 생기는 때를 찾아 백만의 자리까지 고친 수 쓰기",
)
MATH["09"] = dict(
    problem_type=T2,
    text="8억 2000만에서 시작해서 1억씩 5번 뛰어 센 수는 얼마인가요?\n(쉼표 없이 숫자만)",
    after_hint2="억의 자리 8에 5를 더해 받아올림을 처리한 뒤 만 묶음을 붙여 숫자로만 쓰기",
)
MATH["10"] = dict(
    problem_type=T2,
    text="120300000에서 시작해서 10000000씩 거꾸로 4번 뛰어 센 수는 얼마인가요?\n(쉼표 없이 숫자만)",
    expr="120300000-4*10000000",
    answer_value="80300000",
    hint1="10000000은 천만이에요. 120300000에서 억의 자리와 천만의 자리 숫자가 각각 무엇인지 먼저 찾아보세요.",
    hint2="천만의 자리 숫자가 0에서 한 번 더 작아져야 할 때는 억의 자리에서 1을 받아내려요. 한 번 뛸 때마다 수를 차례로 적어 보세요.",
    after_hint2="천만씩 네 번 거꾸로 뛰면서 받아내림이 생기는 때를 찾아 마지막 수 쓰기",
    solution="120300000 → 110300000 → 100300000 → 90300000 → 80300000이에요. 세 번째로 뛸 때 천만의 자리가 0이라 억의 자리 1을 받아내렸고, 그래서 아홉 자리 수가 여덟 자리 수가 돼요.",
)
MATH["11"] = dict(
    difficulty="medium",
    problem_type="10배·100배 관계로 수 구하기(예: 1000만의 100배, 10배 하면 ○이 되는 수)",
    targets_misconception="'삼억 이천만'을 쓸 때 0의 개수를 빠뜨리거나 더 씀",
    standard_code="[4수01-01]",
    text="어떤 수를 10배 하면 2억 5060만이 돼요. 어떤 수는 얼마인가요?\n(쉼표 없이 숫자만)",
    expr="(2*100000000+5060*10000)/10",
    answer_value="25060000",
    hint1="어떤 수를 10배 하면 각 자리 숫자가 한 자리씩 왼쪽으로 옮겨 가요. 10배 하기 전의 수로 되돌리려면 숫자를 어느 쪽으로 옮겨야 할까요?",
    hint2="먼저 2억 5060만을 쉼표 없이 숫자로만 써 보세요. 그 수의 숫자를 모두 한 자리씩 옮기면 끝자리 0이 어떻게 되는지 보세요.",
    after_hint2="2억 5060만을 숫자로 바꾸고, 각 숫자를 한 자리씩 오른쪽으로 옮긴 수(끝의 0 하나가 없어진 수) 쓰기",
    solution="2억 5060만은 250600000이에요. 10배 하기 전의 수는 각 숫자가 한 자리씩 오른쪽으로 옮겨 간 수라서 끝의 0이 하나 줄어요. 그래서 25060000이에요.",
)
MATH["12"] = dict(
    problem_type=T2,
    text="어떤 규칙으로 뛰어 센 수가 52600000, 53100000, 53600000, …으로 이어져요. 같은 규칙으로 52600000에서 시작해서 8번 뛰어 센 수는 얼마인가요?\n(쉼표 없이 숫자만)",
    after_hint2="500000씩 8번이면 모두 얼마가 커지는지 계산해 52600000에 더하기",
)
SAME = "자릿수가 같은 두 수를 비교할 때 높은 자리가 같으면 아랫자리를 확인하지 않음"
DIFF = "자릿수가 다른 두 수를 맨 앞 숫자만 보고 비교함"
ZERO = "가장 작은 수를 만들 때 0을 맨 앞에 놓음"
MATH["13"] = dict(
    targets_misconception=SAME,
    text="73□4105 < 7352000일 때, □ 안에 들어갈 수 있는 숫자 중 가장 큰 숫자는 무엇인가요? □에는 숫자 하나가 들어가요.\n(쉼표 없이 숫자만)",
    box=("73□4105", "<", 7352000, "max"),
    after_hint2="만의 자리 숫자가 같아지는 경우에 아랫자리 4105와 2000을 견주어 되는지 판단하고, 들어갈 수 있는 가장 큰 숫자 정하기",
)
MATH["14"] = dict(
    targets_misconception=SAME,
    text="7□28193 > 7529000일 때, □ 안에 들어갈 수 있는 숫자 중 가장 작은 숫자는 무엇인가요? □에는 숫자 하나가 들어가요.\n(쉼표 없이 숫자만)",
    box=("7□28193", ">", 7529000, "min"),
    answer_value="6",
    hint2="□에 7529000의 십만의 자리 숫자와 같은 숫자를 넣어 보고, 그때 아랫자리끼리 견주어 조건이 맞는지 확인해요.",
    after_hint2="십만의 자리 숫자가 같을 때 아랫자리 28193과 29000을 견주어 조건이 맞는지 판단하고, 들어갈 수 있는 가장 작은 숫자 정하기",
    solution="□에 5를 넣으면 7528193 < 7529000이라 조건에 맞지 않아요. 6을 넣으면 7628193 > 7529000이 되므로 가장 작은 숫자는 6이에요. 높은 자리가 같다고 바로 끝내지 말고 아랫자리까지 견주어야 해요.",
)
MATH["15"] = dict(
    targets_misconception=DIFF,
    text="□3901256 > 9850000일 때, □ 안에 들어갈 수 있는 숫자 중 가장 작은 숫자는 무엇인가요? □에는 숫자 하나가 들어가요.\n(쉼표 없이 숫자만)",
    box=("□3901256", ">", 9850000, "min"),
    answer_value="1",
    hint1="맨 앞 숫자끼리 견주기 전에, 두 수가 각각 몇 자리 수인지부터 세어 보세요.",
    hint2="□가 있는 수는 여덟 자리이고 9850000은 일곱 자리예요. 자리 수가 다를 때 어느 쪽이 큰지 떠올린 다음, □에 어떤 숫자를 넣어도 되는지 따져 보세요.",
    after_hint2="자리 수가 많은 쪽이 크다는 것으로 □에 넣을 수 있는 숫자의 범위를 정하고, 맨 앞자리라는 점을 생각해 그중 가장 작은 숫자 고르기",
    solution="□가 있는 수는 여덟 자리, 9850000은 일곱 자리예요. 자리 수가 많은 수가 더 크므로 □에 1부터 9까지 어떤 숫자를 넣어도 조건이 맞아요. □는 맨 앞자리라 0을 넣으면 여덟 자리 수가 되지 않아요(3901256 < 9850000이라 조건에도 맞지 않아요). 그래서 가장 작은 숫자는 1이에요. 맨 앞 숫자만 보고 □가 9보다 커야 한다고 생각하면 틀려요.",
)
MATH["16"] = dict(
    targets_misconception=SAME,
    text="5□2700000 < 531000000일 때, □ 안에 들어갈 수 있는 숫자 중 가장 큰 숫자는 무엇인가요? □에는 숫자 하나가 들어가요.\n(쉼표 없이 숫자만)",
    box=("5□2700000", "<", 531000000, "max"),
    answer_value="2",
    hint2="□는 천만의 자리예요. 두 수의 천만의 자리 숫자가 같아지는 경우부터 따져 보고, 그때 아랫자리를 견주어 조건이 맞는지 판단해요.",
    after_hint2="천만의 자리가 같을 때 아랫자리 2700000과 1000000을 견주어 되는지 판단하고, 들어갈 수 있는 가장 큰 숫자 정하기",
    solution="□에 3을 넣으면 532700000 > 531000000이라 조건에 맞지 않아요. 2를 넣으면 522700000 < 531000000이므로 가장 큰 숫자는 2예요.",
)
MATH["17"] = dict(
    targets_misconception=ZERO,
    standard_code="[4수01-01]",
    text="숫자 카드 3, 0, 8, 5, 1, 6, 9, 4를 한 번씩 모두 써서 여덟 자리 수를 만들려고 해요. 십만의 자리 숫자가 9인 수 가운데 가장 작은 수는 얼마인가요?\n(쉼표 없이 숫자만)",
    cards=([3, 0, 8, 5, 1, 6, 9, 4], "min", 2, 9),  # 왼쪽에서 index 2 = 십만(8자리)
    answer_value="10934568",
    hint2="맨 앞자리와 십만의 자리를 먼저 정하고, 남은 카드를 어디부터 어떤 순서로 놓을지 생각해 보세요.",
    after_hint2="십만의 자리가 왼쪽에서 몇 번째인지 찾아 9를 놓고, 맨 앞에 0이 아닌 가장 작은 카드를 놓은 뒤 남은 카드를 작은 순서로 놓기",
    solution="여덟 자리 수에서 십만의 자리는 왼쪽에서 세 번째라 9를 놓아요. 맨 앞자리에는 0을 놓을 수 없으니 0이 아닌 가장 작은 1을 놓고, 둘째 자리에 0을 놓아요. 나머지 3, 4, 5, 6, 8을 작은 순서대로 놓으면 10934568이에요.",
)
MATH["18"] = dict(
    targets_misconception=SAME,
    text="숫자 카드 2, 7, 0, 5, 9, 4, 8을 한 번씩 모두 써서 일곱 자리 수를 만들려고 해요. 만들 수 있는 수 중 두 번째로 큰 수는 얼마인가요?\n(쉼표 없이 숫자만)",
    cards=([2, 7, 0, 5, 9, 4, 8], "max2", None, None),
    after_hint2="가장 큰 수를 직접 만든 뒤 십의 자리와 일의 자리를 바꾼 수가 그보다 작으면서 가장 가까운지 확인하고 쓰기",
)
MATH["19"] = dict(
    text="숫자 카드 1, 3, 5, 6, 7, 8, 0, 2, 4를 한 번씩 모두 써서 아홉 자리 수를 만들려고 해요. 만의 자리 숫자가 3인 수 중 가장 큰 수는 얼마인가요?\n(쉼표 없이 숫자만)",
    cards=([1, 3, 5, 6, 7, 8, 0, 2, 4], "max", 4, 3),  # 9자리에서 왼쪽 index 4 = 만
    after_hint2="만의 자리에 3을 놓고, 남은 여덟 장을 높은 자리부터 큰 순서로 놓기",
)
MATH["20"] = dict(
    targets_misconception=ZERO,
    text="숫자 카드 5, 0, 8, 2, 6, 1, 3을 한 번씩 모두 써서 일곱 자리 수를 만들려고 해요. 만들 수 있는 수 중 두 번째로 작은 수는 얼마인가요?\n(쉼표 없이 숫자만)",
    cards=([5, 0, 8, 2, 6, 1, 3], "min2", None, None),
    hint2="가장 작은 수를 만든 다음, 높은 자리는 그대로 두고 어느 자리 숫자끼리 바꾸어야 수가 가장 조금 커질지 생각해 보세요.",
    after_hint2="0을 맨 앞에 두지 않고 가장 작은 수를 만든 뒤, 바꿀 두 자리를 스스로 정해 바꾸기",
)


def build_math():
    src = load("g4-math-large-numbers")
    out = []
    for i in range(1, 21):
        n = f"{i:02d}"
        pid = f"g4-math-large-numbers-{n}"
        p = dict(src[pid])
        ch = dict(MATH.get(n, {}))
        box = ch.pop("box", None)
        cards = ch.pop("cards", None)
        av = ch.pop("answer_value", None)
        code = ch.pop("standard_code", None)
        if code:
            p["standard"] = dict(p["standard"], code=code)
        for k, v in ch.items():
            p[k] = v
        if p["problem_type"].startswith("10배") and not code:
            p["standard"] = dict(p["standard"], code="[4수01-01]")
        value = av or p["answer"]["value"]
        verify, note = "expr", None
        if box:
            expr_s, op, other, want = box
            res, ok, lines = box_check(expr_s, op, other, want)
            assert str(res) == value, (pid, res, value)
            verify = "manual"
            note = f"□에 0~9 전수 대입: {', '.join(lines)}. 조건을 만족하는 숫자 {ok} → {'가장 큰' if want == 'max' else '가장 작은'} 숫자 {res}."
            if expr_s.startswith("□"):
                note += " (□가 맨 앞자리라 0을 넣으면 자릿수가 줄어 제외)"
            p["expr"] = str(res)
        if cards:
            cs, want, pos, digit = cards
            nums, k = card_all(cs)
            if pos is not None:
                cand = [x for x in nums if str(x)[pos] == str(digit)]
                res = cand[0] if want == "min" else cand[-1]
                note = f"카드 {k}장 순열 전수(맨 앞 0 제외) {len(nums)}개 중 왼쪽에서 {pos + 1}번째 자리가 {digit}인 수 {len(cand)}개, {'가장 작은' if want == 'min' else '가장 큰'} 수 {res}."
            elif want == "max2":
                res = nums[-2]
                note = f"카드 {k}장 순열 전수(맨 앞 0 제외) {len(nums)}개: 가장 큰 수 {nums[-1]}, 두 번째 {nums[-2]}, 세 번째 {nums[-3]}."
            else:
                res = nums[1]
                note = f"카드 {k}장 순열 전수(맨 앞 0 제외) {len(nums)}개: 가장 작은 수 {nums[0]}, 두 번째 {nums[1]}, 세 번째 {nums[2]}."
            assert str(res) == value, (pid, res, value)
            verify = "manual"
            p["expr"] = str(res)
        p["verify"] = verify
        if note:
            p["verify_note"] = note
        v = int(value)
        p["answer"] = {"kind": "value", "value": value, "accepted": [value]}
        p["forbidden"] = math_forbidden(v, p["text"])
        p["generator"] = GEN
        p["review"] = "none"
        p.pop("review_note", None)
        assert p["text"].split("\n")[-1] == "(쉼표 없이 숫자만)", pid
        assert "after_hint2" in p, pid
        out.append(ordered(p))
    return out


# ───────────────────────── 국어 ─────────────────────────
K_T0 = "문장 속 작은따옴표 낱말의 품사 고르기"
K_T1 = "문장 속 낱말의 품사 이름 한 낱말로 쓰기"
K_T2 = "품사가 다른 하나 고르기(같은 문장 또는 낱말 묶음)"
K_T3 = "동사·형용사 구별 기준을 적용한 판단 고르기"
K_T4 = "같은 낱말이 문장에 따라 품사가 바뀌는 경우(관형사/수사, 부사/명사, 수사/명사) 판단"
K_T5 = "품사 분류 기준(형태·기능·의미)과 묶음이 바르게 짝지어진 것 고르기"
KM0 = "'새', '옛' 같은 관형사를 형용사로 고름"
KM1 = "수량을 나타내면 무조건 수사라고 봄(관형사 '세' 사람)"
KM2 = "형용사도 '-는다'가 붙는다고 생각함(예쁜다)"
KM3 = "'이다'를 동사·형용사로 고름(조사인 서술격 조사)"
KM4 = "같은 낱말은 문장이 달라도 늘 품사가 같다고 봄"
KM5 = "가리켜 부르는 말(대명사)과 이름(명사)을 구별하지 못함"
KM6 = "꾸미는 말이면 모두 같은 품사로 봄(관형사·부사 혼동)"
KM7 = "앞말에 붙어 뜻을 더하는 조사(만·도·까지)를 따로 쓰이는 부사로 고름"
CH = "\n(번호만 써 주세요)"
TX = "\n(한 낱말로 써 주세요)"

KOR = {}
KOR["01"] = dict(
    targets_misconception=KM0,
    text="「동생이 '새' 운동화를 신고 나갔다.」에서 '새'의 품사는 무엇일까요?\n① 형용사\n② 관형사\n③ 부사\n④ 명사" + CH,
    hint1="'새로운'은 '새롭고, 새로워서'처럼 모양이 바뀌어요. '새 운동화'의 '새'도 그렇게 바뀌는지 보세요.",
    hint2="'새'는 모양이 바뀌지 않아요. 이제 '새'가 꾸며 주는 낱말을 찾고, 그 낱말이 체언인지 용언인지 보세요.",
    after_hint2="'운동화'가 체언임을 판단하고, 모양이 바뀌지 않으면서 체언을 꾸미는 품사를 보기에서 고르기",
    solution="'새'는 '새고, 새니'처럼 활용하지 않으니 형용사(①)가 아니에요. 뒤에 오는 체언 '운동화'를 꾸며 주는 말이므로 관형사예요. 답은 ②예요. ③ 부사는 주로 용언을 꾸미고, ④ 명사는 조사가 붙어 문장의 주인 노릇을 하는데 '새'는 그렇지 않아요.",
)
KOR["02"] = dict(
    targets_misconception=KM1,
    text="「동생은 구슬을 '여섯'이나 모았다.」에서 '여섯'의 품사는 무엇일까요?\n① 수사\n② 관형사\n③ 대명사\n④ 부사" + CH,
    hint2="'여섯' 뒤에 조사 '이나'가 붙었어요. 조사가 붙는 낱말은 어떤 묶음일까요? '여섯 개'처럼 뒤의 말을 꾸밀 때와 견주어 보세요.",
    after_hint2="조사가 붙은 '여섯'을 체언으로 정하고, 체언 가운데 수량을 나타내는 품사를 고르기",
    solution="'여섯'에 조사 '이나'가 붙어 있으니 체언이에요. 수량을 나타내는 체언은 수사예요. 답은 ①이에요. ② 관형사는 '여섯 개'처럼 뒤의 체언을 꾸밀 때이고, ③ 대명사는 가리켜 부르는 말, ④ 부사는 조사가 붙지 않고 용언을 꾸미는 말이에요.",
)
KOR["03"] = dict(
    targets_misconception=KM2,
    text="「이번 숙제는 꽤 '어렵다'.」에서 '어렵다'의 품사는 무엇일까요?\n① 동사\n② 부사\n③ 형용사\n④ 관형사" + CH,
    after_hint2="'어렵는다'·'어려워라'·'어렵자'가 실제로 되는지 스스로 판단해 동사와 형용사 가운데 고르기",
    solution="'어렵다'는 숙제의 상태를 나타내고, '어렵는다'·'어려워라'·'어렵자'가 모두 안 되므로 형용사예요. 답은 ③이에요. ① 동사라면 '-는다'와 명령·청유가 자연스러워야 하고, ② 부사와 ④ 관형사는 모양이 바뀌지 않는데 '어렵다'는 '어렵고, 어려워서'로 바뀌어요.",
)
KOR["04"] = dict(
    targets_misconception=KM7,
    answer_sym="②",
    text="「동생'까지' 내 과자를 먹었다.」에서 '까지'의 품사는 무엇일까요?\n① 부사\n② 조사\n③ 형용사\n④ 명사" + CH,
    hint1="'까지'를 앞말 '동생'에서 떼어 내어 혼자 문장에 쓸 수 있는지 해 보세요.",
    hint2="'까지'는 '까지고, 까지니'처럼 모양이 바뀌지 않으니 보기 가운데 용언은 지울 수 있어요. 남은 보기에서는 '까지'가 다른 말을 꾸미는지, 앞말에 기대어 쓰이는지 보세요.",
    after_hint2="'까지'가 혼자 쓰이지 못하고 앞말에 붙어 뜻을 더한다는 것을 판단해 부사·명사·조사 가운데 고르기",
    solution="'까지'는 혼자 쓰이지 못하고 체언 '동생'에 붙어 '그것도 더하여'라는 뜻을 보태 주는 조사(보조사)예요. 답은 ②예요. ① 부사는 혼자 쓰이며 주로 용언을 꾸미는데 '까지'는 혼자 쓰이지 못해요. ③ 형용사는 모양이 바뀌는 용언인데 '까지'는 바뀌지 않아요. ④ 명사는 혼자 쓰이고 뒤에 조사가 붙는 말인데 '까지'는 그 자체가 앞말에 붙어요.",
)
KOR["05"] = dict(
    targets_misconception=KM3,
    text="「내 꿈은 과학자'이다'.」에서 '이다'의 품사는 무엇일까요?\n① 동사\n② 형용사\n③ 조사\n④ 부사" + CH,
    hint2="'이다'는 '이고, 이니'처럼 모양이 바뀌어요. 그런데 '과학자' 없이 혼자 쓸 수 있나요? 혼자 쓰지 못하고 체언 뒤에 붙는 말이 무엇이었는지 떠올려 보세요.",
    after_hint2="'이다'가 혼자 쓰일 수 없음을 판단하고, 모양은 바뀌어도 용언이 아닌 품사를 보기에서 고르기",
    solution="'이다'는 '이고, 이니'로 활용하지만 혼자 쓰이지 못하고 체언 '과학자' 뒤에 붙어 그 말이 서술어가 되게 해요. 그래서 서술격 조사예요. 답은 ③이에요. ①·② 동사·형용사는 혼자 서술어가 될 수 있는 용언이고, ④ 부사는 모양이 바뀌지 않아요.",
)
KOR["06"] = dict(
    text="「'아이고', 발목을 삐었네.」에서 '아이고'의 품사는 무엇일까요?\n① 감탄사\n② 부사\n③ 명사\n④ 조사" + CH,
    hint2="'아이고'를 빼도 문장이 그대로 성립해요. 다른 낱말을 꾸미지도, 조사가 붙지도 않고 혼자 쓰이는 말이에요.",
    after_hint2="다른 말과 관계없이 혼자 느낌을 드러내는 말이 보기 가운데 어느 품사인지 정하기",
    solution="'아이고'는 다른 말과 관계없이 혼자 느낌을 나타내는 감탄사예요. 답은 ①이에요. ② 부사는 다른 말을 꾸미고, ③ 명사는 조사가 붙어 문장 속 자리를 맡으며, ④ 조사는 혼자 쓰이지 못해요.",
)
KOR["07"] = dict(
    targets_misconception=KM6,
    text="「버스가 아주 '천천히' 지나갔다.」에서 '천천히'의 품사 이름을 쓰세요." + TX,
    hint2="'천천히'는 모양이 바뀌지 않고 '지나갔다'를 꾸며요. 꾸밈을 받는 말이 체언인지 용언인지에 따라 품사 이름이 달라져요.",
    after_hint2="'지나갔다'가 용언임을 판단하고, 용언을 꾸미는 품사 이름을 스스로 떠올려 쓰기",
    verify_note="'천천히': 활용하지 않음, 용언 '지나갔다'를 꾸밈 → 부사 하나. 통용 낱말 목록(규칙 8.1) 밖. 바른 표기는 '부사' 하나.",
)
KOR["08"] = dict(
    targets_misconception=KM5,
    text="「'저것'은 누가 두고 간 우산일까?」에서 '저것'의 품사 이름을 쓰세요." + TX,
    hint2="'저것'은 조사가 붙는 체언이에요. 우산이라는 이름을 직접 말했나요, 다른 방법으로 불렀나요?",
    after_hint2="'저것'이 이름이 아니라 가리켜 부르는 말임을 판단해 체언 가운데 품사 이름 쓰기",
    accepted=["대명사", "지시대명사", "지시 대명사"],
    verify_note="'저것': 조사 '은'이 붙는 체언, 사물 이름 대신 가리켜 부름 → 대명사(지시 대명사). 바른 표기 '대명사·지시대명사·지시 대명사'를 accepted에.",
)
KOR["09"] = dict(
    targets_misconception=KM0,
    text="「할머니는 '옛' 동네 이야기를 자주 들려주신다.」에서 '옛'의 품사 이름을 쓰세요." + TX,
    hint1="'옛'에 '-다'로 끝나는 기본형이 있는지, '옛고, 옛니'처럼 바뀌는지 보세요.",
    hint2="'옛'은 모양이 바뀌지 않으니 용언은 아니에요. '옛'이 꾸며 주는 '동네'가 체언인지 용언인지 따져 보세요.",
    after_hint2="'동네'가 체언임을 판단하고, 체언을 꾸미는 품사 이름을 스스로 떠올려 쓰기",
    solution="'옛'은 '-다'로 끝나는 기본형이 없고 '옛고, 옛니'처럼 활용하지도 않아요. 뒤의 체언 '동네'를 꾸미므로 관형사예요.",
    verify_note="'옛': 활용 없음, 기본형 없음, 체언 '동네'를 꾸밈 → 관형사. 통용 낱말 목록 밖. 바른 표기는 '관형사' 하나.",
    review="needs_review",
    review_note="[사전] '옛 동네'를 띄어 쓰는 두 낱말(관형사+명사)로 보았음. '옛동네'가 표준국어대사전에 합성어로 올라 있지 않은지 대조 필요(올라 있으면 '옛 사진' 등으로 바꿈).",
)
KOR["10"] = dict(
    difficulty="hard",
    problem_type=K_T4,
    targets_misconception=KM1,
    text="(가) 달걀 '일곱'을 삶았다.\n(나) '일곱' 사람이 버스에서 내렸다.\n(가)와 (나)에서 '일곱'은 각각 어떤 품사로 쓰였을까요?\n① (가) 관형사, (나) 수사\n② (가) 수사, (나) 수사\n③ (가) 관형사, (나) 관형사\n④ (가) 수사, (나) 관형사" + CH,
    answer_sym="④",
    hint1="두 문장에서 '일곱' 바로 뒤에 무엇이 오는지 각각 찾아보세요. 조사인가요, 다른 낱말인가요?",
    hint2="(가)의 '일곱' 뒤에는 조사 '을'이 붙어 있어요. 조사가 붙은 '일곱'이 어떤 품사인지 정하고, (나)의 '일곱'은 뒤의 어떤 말과 이어지는지 따져 보세요.",
    after_hint2="(가)를 조사가 붙은 체언(수사)으로 정하고, (나)의 '일곱'이 '사람'을 꾸미는지 판단해 짝 고르기",
    solution="(가)의 '일곱'은 조사 '을'이 붙은 체언이라 수사예요. (나)의 '일곱'은 뒤의 명사 '사람'을 꾸미므로 관형사예요. 답은 ④예요. ①은 두 문장을 거꾸로 짝지었고, ②는 (나)에서 꾸미는 '일곱'을, ③은 (가)에서 조사가 붙은 '일곱'을 잘못 보았어요.",
)
KOR["11"] = dict(
    targets_misconception=KM1,
    text="「귤 '하나'와 배 '둘'을 '세' 바구니에 나누어 담고 감 '넷'을 더 샀다.」에서 품사가 다른 하나는 무엇일까요?\n① 하나\n② 둘\n③ 세\n④ 넷" + CH,
    after_hint2="네 낱말 뒤에 조사가 붙는지 명사가 오는지 하나씩 보고 혼자만 다른 낱말 고르기",
    solution="'하나(와)', '둘(을)', '넷(을)'은 조사가 붙는 수사예요. '세'는 뒤의 '바구니'를 꾸미는 관형사예요. 답은 ③이에요.",
)
KOR["12"] = dict(
    targets_misconception=KM2,
    text="다음 낱말 가운데 품사가 다른 하나는 무엇일까요?\n① 자라다\n② 좁다\n③ 슬프다\n④ 고요하다" + CH,
    after_hint2="네 낱말에 '-는다/-ㄴ다'를 붙여 보고 자연스러운 하나를 스스로 찾기",
    solution="'자란다'는 되지만 '좁는다·슬픈다·고요한다'는 안 돼요. '자라다'만 동사이고 나머지는 형용사예요. 답은 ①이에요.",
)
KOR["13"] = dict(
    difficulty="hard",
    problem_type=K_T4,
    targets_misconception=KM4,
    text="(가) 이모네 '첫째'는 올해 중학생이 되었다.\n(나) 급식 줄에서 내가 '첫째'였다.\n'첫째'가 (가)와 (나)에서 쓰인 품사를 차례대로 바르게 고른 것은 무엇일까요?\n① (가) 명사, (나) 수사\n② (가) 수사, (나) 명사\n③ (가) 명사, (나) 명사\n④ (가) 수사, (나) 수사" + CH,
    answer_sym="①",
    hint1="두 문장의 '첫째'를 다른 말로 바꿔 보세요. '맏이'로 바꿀 수 있는 쪽과 '맨 앞 차례'로 바꿀 수 있는 쪽이 있는지 보세요.",
    hint2="(가)의 '첫째'는 '맏이'라는 사람을 가리키는 말이에요. (나)의 '첫째'는 사람을 가리키는지, 순서를 나타내는지 따져 보고 두 낱말의 품사를 각각 정해 보세요.",
    after_hint2="(가)가 사람을 가리키는 이름이라 명사임을 정하고, (나)가 차례를 나타내는지 판단해 수사·명사 가운데 정하기",
    solution="(가)의 '첫째'는 '맏이'를 뜻하는 이름이라 명사예요. (나)의 '첫째'는 줄에서의 순서를 나타내므로 수사예요. 답은 ①이에요. ②는 거꾸로 짝지었고, ③은 (나)의 순서를 나타내는 뜻을, ④는 (가)의 사람을 가리키는 뜻을 놓쳤어요.",
    review="needs_review",
    review_note="[사전] '첫째'의 명사(맏이)·수사(순서) 뜻풀이를 기억에 기대어 판정함. 표준국어대사전에서 (나) '급식 줄에서 내가 첫째였다'가 수사 뜻(순서가 가장 먼저인 차례)에 드는지, 명사 뜻(무엇보다 앞서는 것)과 겹치지 않는지 대조 필요.",
)
KOR["14"] = dict(
    targets_misconception=KM2,
    text="현재를 나타내는 '-는다/-ㄴ다'를 붙일 수 있는지로 동사와 형용사를 가를 때, 바르게 판단한 것은 무엇일까요?\n① '예쁘다'는 '예쁜다'가 되므로 동사이다.\n② '읽다'는 '읽는다'가 되므로 동사이다.\n③ '춥다'는 '춥는다'가 되므로 동사이다.\n④ '걷다'는 '걷는다'가 안 되므로 형용사이다." + CH,
    after_hint2="보기마다 '-는다' 꼴이 실제로 쓰이는지와 결론이 기준에 맞는지 둘 다 스스로 판단하기",
    sentence_forbidden=True,
)
KOR["15"] = dict(
    targets_misconception=KM2,
    text="'-어라'(명령)나 '-자'(청유)를 붙여 쓸 수 없어서 형용사로 보는 낱말은 무엇일까요?\n① 웃다\n② 씻다\n③ 가르치다\n④ 짧다" + CH,
    after_hint2="네 낱말에 '-어라', '-자'를 직접 붙여 보고 둘 다 안 되는 낱말 고르기",
)
KOR["16"] = dict(
    targets_misconception=KM2,
    text="낱말에 '-는다/-ㄴ다'와 명령의 '-어라/-아라'를 붙여 본 결과를 바르게 적은 것은 무엇일까요?\n① 높다: '높는다' 됨, '높아라' 됨\n② 놀다: '논다' 됨, '놀아라' 안 됨\n③ 닦다: '닦는다' 안 됨, '닦아라' 됨\n④ 둥글다: '둥근다' 안 됨, '둥글어라' 안 됨" + CH,
    answer_sym="④",
    hint1="보기마다 두 말을 '지금 ~', '얼른 ~' 같은 문장에 넣어 소리 내어 말해 보세요.",
    hint2="'높다'는 키나 산의 상태를 나타내서 '높는다'라고 말하지 않아요. 남은 세 보기도 두 말이 정말 되는지 하나씩 따져 보세요.",
    after_hint2="놀다·닦다·둥글다에 '-는다'와 명령 '-어라'를 붙여 보고 결과가 적힌 대로인지 각각 판단하기",
    solution="'둥근다'도 '둥글어라'도 쓰지 않으니 ④가 바르게 적었어요(그래서 '둥글다'는 형용사예요). ① '높는다'와 명령의 '높아라'는 쓰지 않아요. ② '놀아라'는 '밖에서 놀아라'처럼 자연스러워요. ③ '닦는다'는 '이를 닦는다'처럼 자연스러워요. 답은 ④예요.",
    sentence_forbidden=True,
)
KOR["17"] = dict(
    targets_misconception=KM1,
    text="(가) 시장에서 사과 '다섯' 개를 샀다.\n(나) '다섯'에 셋을 더하면 여덟이다.\n두 문장의 '다섯'의 품사를 바르게 짝지은 것은 무엇일까요?\n① (가) 수사, (나) 수사\n② (가) 관형사, (나) 수사\n③ (가) 수사, (나) 관형사\n④ (가) 관형사, (나) 관형사" + CH,
    after_hint2="(가)·(나) 각각 '다섯' 뒤를 보고 꾸미는 쪽과 조사가 붙은 쪽을 가려 짝 고르기",
)
KOR["18"] = dict(
    targets_misconception=KM4,
    text="(가) '오늘'은 내 생일이다.\n(나) 나는 '오늘' 일찍 잘 거야.\n'오늘'이 (가)와 (나)에서 각각 어떤 품사인지 바르게 짝지은 것은 무엇일까요?\n① (가) 명사, (나) 명사\n② (가) 부사, (나) 부사\n③ (가) 부사, (나) 명사\n④ (가) 명사, (나) 부사" + CH,
    hint2="조사가 붙는 '오늘'과 용언을 꾸미는 '오늘'은 품사가 달라요. 두 문장에서 '오늘'이 각각 어느 쪽인지 가려 보세요.",
    after_hint2="두 문장 가운데 조사가 붙은 쪽과 용언을 꾸미는 쪽을 가려 각각 품사를 정하기",
)
KOR["19"] = dict(
    difficulty="medium",
    targets_misconception=KM0,
    hint2="보기마다 묶음에 어울리지 않는 품사가 섞여 있는지 보세요. 먼저 관형사가 '-고, -니'로 모양이 바뀌는지부터 따져 보세요.",
    after_hint2="①을 지운 뒤 남은 세 보기의 묶음과 품사를 하나씩 따져 바르게 짝지어진 것 고르기",
    solution="용언은 동사·형용사, 수식언은 관형사·부사, 관계언은 조사, 독립언은 감탄사예요. 문장의 주체가 되는 체언에 명사·대명사·수사가 드는 짝만 맞아요. 답은 ③이에요. ① 관형사는 모양이 바뀌지 않아 용언이 아니고, ② 감탄사는 수식언이 아니라 독립언이며, ④ 부사는 관계언이 아니라 수식언이에요.",
)
KOR["20"] = dict(
    difficulty="medium",
    text="품사를 나누는 기준과 그 기준으로 나눈 결과가 바르게 짝지어진 것은 무엇일까요?\n① 형태 – 변하는 말, 변하지 않는 말\n② 기능 – 변하는 말, 변하지 않는 말\n③ 의미 – 체언, 용언, 수식언, 관계언, 독립언\n④ 형태 – 뜻에 따라 나눈 아홉 품사" + CH,
    answer_sym="①",
    hint2="'-언'으로 끝나는 묶음은 문장에서 하는 일로 나눈 거예요. 나머지 두 기준은 스스로 짝지어 보세요.",
    after_hint2="형태·의미 기준이 각각 어떤 결과와 짝인지 스스로 정해 남은 보기 가운데 고르기",
    solution="형태로 나누면 변하는 말과 변하지 않는 말, 기능으로 나누면 체언·용언·수식언·관계언·독립언, 의미로 나누면 아홉 품사가 돼요. 답은 ①이에요. ②는 형태로 나눈 결과를 기능에, ③은 기능으로 나눈 결과를 의미에, ④는 의미로 나눈 결과를 형태에 짝지었어요.",
)

K_TYPE = {"01": K_T0, "02": K_T0, "03": K_T0, "04": K_T0, "05": K_T0, "06": K_T0,
          "07": K_T1, "08": K_T1, "09": K_T1, "10": K_T4, "11": K_T2, "12": K_T2, "13": K_T4,
          "14": K_T3, "15": K_T3, "16": K_T3, "17": K_T4, "18": K_T4, "19": K_T5, "20": K_T5}


def fix_choice_lastline(text):
    lines = text.split("\n")
    if lines[-1].startswith("(번호"):
        lines[-1] = "(번호만 써 주세요)"
    return "\n".join(lines)


def build_kor():
    src = load("g8-kor-parts-of-speech")
    out = []
    for i in range(1, 21):
        n = f"{i:02d}"
        pid = f"g8-kor-parts-of-speech-{n}"
        p = dict(src[pid])
        ch = dict(KOR.get(n, {}))
        sym = ch.pop("answer_sym", None)
        acc = ch.pop("accepted", None)
        sent = ch.pop("sentence_forbidden", False)
        for k, v in ch.items():
            p[k] = v
        p["problem_type"] = K_TYPE[n]
        p["text"] = fix_choice_lastline(p["text"])
        kind = p["answer"]["kind"]
        if kind == "choice":
            sym = sym or p["answer"]["value"]
            ans, opt = choice_answer(p["text"], sym)
            p["answer"] = ans
            p["forbidden"] = [sym, opt] if sent else [sym]
            p["verify"] = "manual"
            assert p["text"].endswith(CH), pid
        else:
            val = p["answer"]["value"]
            p["answer"] = {"kind": "text", "value": val, "accepted": acc or [val]}
            p["forbidden"] = [val]
            p["verify"] = "manual"
            assert p["text"].endswith(TX), pid
        p["generator"] = GEN
        if "review" not in ch:
            p["review"] = "none"
            p.pop("review_note", None)
        assert "after_hint2" in p, pid
        out.append(ordered(p))
    return out


# ───────────────────────── 영어 ─────────────────────────
E_T0 = "빈칸에 알맞은 관계사 고르기"
E_T1 = "두 문장을 관계사로 바르게 합친 문장 고르기"
E_T2 = "빈칸에 관계사 한 단어 쓰기(정답이 하나뿐인 자리만: 소유격 whose, 선행사 없는 what, 관계부사 where/when/why, 쉼표 뒤 who/which)"
E_T3 = "what/that, 관계대명사/관계부사 어법 판단(틀린 것 고르기)"
EM0 = "사람/사물에 따라 who·which 바꿔 씀"
EM1 = "관계대명사 뒤 문장에 목적어를 또 씀(the book which I read it)"
EM2 = "what과 that 혼동(선행사 유무)"
EM3 = "관계부사 where 뒤에 불완전한 문장(목적어 빠진 절)을 씀"
EM4 = "소유격 자리에 who·which를 쓰거나 whose 뒤에 his·its를 또 씀"
EM5 = "관계부사를 선행사 종류(장소·때·이유)와 맞추지 못함"
EM6 = "쉼표 뒤 계속적 용법에 that을 씀"
EM7 = "접속사 that과 관계대명사 that을 구별하지 못함"
EM8 = "빠진 것 없는 문장 앞에 전치사 없이 which를 씀(the house which I live)"
ETX = "\n(영어 한 단어로 써 주세요)"

ENG = {}
ENG["01"] = dict(
    targets_misconception=EM0,
    hint1="빈칸 앞의 낱말이 사람인지 물건인지 먼저 보세요.",
    hint2="빈칸 바로 뒤에 is가 와요. is의 주어가 따로 있는지 보고 빈칸의 역할을 정한 다음, 앞 낱말의 종류와 맞춰 보세요.",
    after_hint2="is의 주어가 비었음을 판단해 빈칸 역할을 정하고, 사람인 The girl에 맞는 관계사 고르기",
    solution="선행사 The girl은 사람이고, 빈칸 뒤 is sitting의 주어가 비어 있어요. 그래서 사람을 받는 주격 관계대명사 who가 들어가요. 답은 ②예요. ① which는 사물에 쓰고, ③ whose는 뒤에 명사가 바로 와야 하며, ④ where는 장소 뒤에 빠진 것 없는 문장이 올 때 써요.",
)
ENG["02"] = dict(
    targets_misconception=EM0,
    hint1="빈칸 앞의 the umbrella는 사람인가요, 물건인가요?",
    hint2="gave me 뒤에 '무엇을'에 해당하는 말이 있는지 보세요. 빠진 자리가 빈칸의 역할이에요.",
    after_hint2="gave me 뒤 목적어가 빠졌음을 판단하고, 물건에 맞는 목적격 관계사 고르기",
    solution="선행사 the umbrella는 물건이고, my grandmother gave me 뒤에 '무엇을'이 빠져 있어요. 그래서 물건을 받는 목적격 관계대명사 which가 맞아요. 답은 ③이에요. ① who는 사람에 쓰고, ② whose는 뒤에 명사가 바로 와야 하며, ④ where는 뒤에 빠진 것 없는 문장이 와야 해요.",
)
ENG["03"] = dict(
    targets_misconception=EM4,
    hint1="빈칸 바로 뒤에 명사 eyes가 붙어 있다는 점을 보세요.",
    hint2="eyes는 누구의 눈인가요? 빈칸과 eyes가 한 덩어리가 되어 뒤 문장의 주어가 된다는 점을 보세요.",
    after_hint2="eyes가 a cat의 것임을 판단하고 '~의'를 나타낼 수 있는 관계사를 보기에서 고르기",
    solution="eyes는 a cat의 눈이에요. 빈칸과 eyes가 한 덩어리로 주어가 되니 소유격 관계대명사 whose가 들어가요. 답은 ①이에요. ② who와 ③ which는 뒤 문장에 주어나 목적어가 빠져 있어야 하는데 eyes are two different colors는 빠진 것이 없고, ④ what은 앞에 선행사가 없을 때 써요.",
)
ENG["04"] = dict(
    targets_misconception=EM8,
    text="빈칸에 알맞은 말을 고르세요.\nThis is the room ___ my sister practices the piano.\n① which\n② in what\n③ who\n④ in which\n(번호만 써 주세요)",
    hint1="빈칸 뒤 my sister practices the piano에 빠진 말(주어나 목적어)이 있는지 보세요.",
    hint2="my sister practices the piano는 주어와 목적어가 다 있는 문장이에요. 이렇게 빠진 것 없는 문장 앞에 관계대명사 한 낱말만 오는 보기는 지울 수 있어요.",
    after_hint2="남은 두 보기 가운데, 앞에 선행사 the room이 있다는 점에 맞는 것 고르기",
    solution="빈칸 뒤 my sister practices the piano는 빠진 것이 없는 문장이에요. 원래 문장은 my sister practices the piano in the room이라서 the room 앞의 in과 함께 in which를 써요(관계부사 where로 바꿔 쓸 수도 있어요). 답은 ④예요. ① which와 ③ who는 뒤 문장에 빠진 자리가 있어야 하고, ② in what은 앞에 선행사 the room이 있어서 쓸 수 없어요.",
)
ENG["05"] = dict(
    targets_misconception=EM5,
    hint1="빈칸 앞 낱말 the reason의 뜻을 떠올려 보세요.",
    hint2="the bus was late today는 빠진 것이 없는 문장이에요. 그러면 관계대명사 보기는 지울 수 있어요. 남은 보기 가운데 앞 낱말의 뜻과 어울리는 것을 보세요.",
    after_hint2="남은 두 관계부사 가운데 the reason(이유)의 뜻에 맞는 것 고르기",
    solution="the bus was late today는 빠진 것이 없는 문장이라 관계부사가 와야 해요. 선행사 the reason은 '이유'라서 why를 써요. 답은 ①이에요. ② which는 뒤 문장에 빠진 자리가 있어야 하고, ③ where는 장소 뒤에 쓰며, ④ what은 앞에 선행사가 있으면 쓸 수 없어요.",
)
ENG["06"] = dict(
    targets_misconception=EM4,
    hint1="둘째 문장의 His가 첫째 문장의 무엇을 가리키는지 보세요.",
    hint2="His를 관계대명사로 바꿨다면 원래 낱말이 문장에 남아 있으면 안 돼요. 겹쳐 쓴 보기를 먼저 지워 보세요.",
    after_hint2="his가 겹친 보기를 지운 뒤 남은 두 보기 가운데 소유를 나타낼 수 있는 관계사 고르기",
    solution="His는 a boy의 것이므로 소유격 관계대명사 whose로 바꾸고 his는 지워요: I met a boy whose father is a pilot. 답은 ③이에요. ①·④는 his가 겹치고, ② which는 소유를 나타내지 못해요.",
)
ENG["07"] = dict(
    targets_misconception=EM1,
    hint1="둘째 문장의 it이 첫째 문장의 무엇과 같은지 찾아보세요.",
    hint2="it 자리를 관계대명사가 대신하니 합친 문장에 it이 남으면 안 돼요. 남은 보기에서는 the bike에 어울리는 관계사인지 보세요.",
    after_hint2="it이 남은 보기를 지우고, 남은 두 보기 가운데 물건인 the bike에 맞는 관계사 고르기",
    solution="it = the bike(물건, 목적어)이므로 목적격 which로 바꾸고 it을 지워요: Here is the bike which I fixed yesterday. 답은 ②예요. ①은 it이 겹치고, ③ who는 사람에 쓰며, ④ where는 장소를 나타내는 부사를 대신하는데 여기서 바뀌는 it은 목적어라 맞지 않아요(it도 겹쳐요).",
)
ENG["08"] = dict(
    targets_misconception=EM8,
    hint1="둘째 문장의 there가 무엇을 가리키는지 보세요.",
    hint2="there는 '거기에서'라는 부사예요. 합친 문장에 there가 남아 있는 보기를 먼저 지우고, 남은 보기에서 grew up 뒤가 완전한지 보세요.",
    after_hint2="there가 남은 보기를 지운 뒤, grew up 뒤에 빠진 것이 없다는 점으로 남은 세 보기 가운데 고르기",
    solution="there = in the town이므로 관계부사 where로 바꾸고 there를 지워요: I visited the town where my mom grew up. 답은 ④예요. ①은 there가 겹치고, ②는 which 앞에 in이 없어서 틀리며(in which라면 맞아요), ③ what은 앞에 선행사가 있으면 쓸 수 없어요.",
)
ENG["09"] = dict(
    targets_misconception=EM6,
    hint1="네 보기 모두 쉼표(,) 뒤에 관계사가 와요. 쉼표 뒤에 쓸 수 있는 말과 없는 말을 떠올려 보세요.",
    hint2="He는 사람이고, 합친 문장에 he가 남으면 안 돼요. 그러고도 보기가 둘 남아요. 쉼표 뒤라는 점을 다시 보세요.",
    after_hint2="남은 두 보기 가운데 쉼표 뒤 계속적 용법에 쓸 수 있는 관계대명사 고르기",
    solution="He = an older brother(사람, 주어)예요. 계속적 용법(쉼표 뒤)에는 that을 쓰지 못하므로 , who를 써요: Jun has an older brother, who is a cook. 답은 ①이에요. ②는 쉼표 뒤에 that을 썼고, ③은 사람에 which를 썼으며, ④는 주어 he가 겹쳐요.",
)
ENG["10"] = dict(
    targets_misconception=EM2,
    hint1="the thing과 관계대명사를 한 낱말로 줄일 수 있는지 생각해 보세요.",
    hint2="'~하는 것'이라는 뜻으로 선행사를 품고 있는 관계대명사가 있어요. 그 낱말 앞에는 the thing을 또 쓰지 않아요.",
    after_hint2="남은 보기 가운데 that과 what의 차이, it이 겹치는지를 판단해 고르기",
    solution="the thing which를 한 낱말 what으로 줄여요: Tell me what you want for your birthday. 답은 ③이에요. ①의 that은 선행사가 없어서 틀리고, ②는 the thing과 what이 겹치며, ④는 it이 겹쳐요.",
)
ENG["11"] = dict(
    targets_misconception=EM4,
    text="빈칸에 들어갈 관계사를 쓰세요.\nI have a friend ___ dog can open the door by itself." + ETX,
    hint1="빈칸 바로 뒤에 dog라는 명사가 붙어 있어요. 누구의 개일까요?",
    hint2="dog 앞에 a나 the가 없어요. 빈칸과 dog가 한 덩어리로 뒤 문장의 주어가 돼요. 'his dog'의 his 자리라고 생각해 보세요.",
    after_hint2="his 자리, 곧 소유를 나타내는 자리에 들어가는 관계사를 스스로 떠올려 쓰기",
    solution="dog는 a friend의 개이므로 소유격 관계대명사 whose를 써요: I have a friend whose dog can open the door by itself.",
    verify_note="후보 10개 대입: whose만 됨. who·whom·which·that·what(뒤에 명사 dog가 바로 오고 dog can open…은 주어·목적어가 다 있어 빠진 자리가 없음), where·when·why·how(선행사 a friend는 장소·때·이유·방법이 아니고 dog 앞 소유 관계가 비어 있음).",
)
ENG["12"] = dict(
    targets_misconception=EM2,
    text="빈칸에 들어갈 관계사를 쓰세요.\nI couldn't hear ___ the teacher said this morning." + ETX,
    hint1="빈칸 앞에 꾸밈을 받는 명사(선행사)가 있는지 보세요.",
    hint2="빈칸 앞에 꾸밈을 받는 명사가 없고, said 뒤에 '무엇을'이 빠져 있어요. 이 두 가지가 함께일 때 쓰는 관계대명사를 떠올려 보세요.",
    after_hint2="선행사가 없고 목적어가 빠진 자리에 쓰는 관계대명사를 스스로 정해 쓰기",
    solution="hear 뒤에 선행사가 없고 said의 목적어가 비어 있으므로 '~하는 것'을 뜻하는 what을 써요: I couldn't hear what the teacher said this morning.",
    verify_note="후보 10개 대입: what만 됨. who·whom·which·whose(앞에 선행사가 없음), that(접속사 that이면 뒤 문장이 완전해야 하는데 said의 목적어가 빠져 있음), where·when·why·how(said는 목적어가 꼭 필요해 뒤 문장이 불완전하므로 관계부사·how 불가).",
)
ENG["13"] = dict(
    targets_misconception=EM8,
    text="빈칸에 들어갈 관계사를 쓰세요.\nThe library ___ we borrowed these books has closed." + ETX,
    hint1="The library는 사람·물건·장소 가운데 어떤 종류의 낱말인가요?",
    hint2="we borrowed these books는 빠진 것이 없는 문장이에요. 관계대명사와 관계부사 가운데 어느 쪽인지 정하고, 앞 낱말의 종류를 보세요.",
    after_hint2="관계부사를 써야 한다고 정하고, 장소에 맞는 관계부사를 스스로 떠올려 쓰기",
    solution="선행사 The library는 장소이고, 뒤 문장 we borrowed these books는 목적어까지 다 있는 완전한 문장이에요. 그래서 관계부사 where(= from which)를 써요: The library where we borrowed these books has closed.",
    verify_note="후보 10개 대입: where만 됨. which·that·who·whom·what(borrowed의 목적어 these books가 있어 빠진 자리가 없음), whose(뒤에 명사가 바로 오지 않음), when·why·how(선행사가 장소). 시범의 'we first studied together'는 study가 목적어를 가질 수 있어 which가 문법상 끼어들 여지가 있어 borrowed these books로 바꿈.",
)
ENG["14"] = dict(
    targets_misconception=EM6,
    text="빈칸에 들어갈 관계사를 쓰세요.\nMy aunt, ___ works as a nurse, visits us every Sunday." + ETX,
    hint1="빈칸 앞의 My aunt는 사람인가요, 물건인가요?",
    hint2="works의 주어가 보이지 않아요. 빈칸의 역할을 정하고 My aunt의 종류와 맞춰 보세요. 쉼표 뒤라는 점도 잊지 마세요.",
    after_hint2="주어 자리임을 판단하고, 사람·쉼표 뒤 두 조건에 맞는 관계대명사를 정해 쓰기",
    solution="선행사 My aunt는 사람이고, 빈칸은 works의 주어 자리예요. 앞에 쉼표가 있어 that은 쓸 수 없어요. 그래서 who를 써요: My aunt, who works as a nurse, visits us every Sunday.",
    verify_note="후보 10개 대입: who만 됨. that(쉼표 뒤 계속적 용법 불가), which(선행사가 사람), whom(주어 자리라 불가), whose(뒤에 명사가 바로 오지 않음), what(선행사 있음), where·when·why·how(works의 주어가 빠진 불완전한 문장).",
)
ENG["15"] = dict(
    targets_misconception=EM5,
    text="빈칸에 들어갈 관계사를 쓰세요.\nWe moved to this city in 2019, ___ I was ten years old." + ETX,
    hint1="빈칸 뒤 I was ten years old에 빠진 말이 있는지 먼저 보세요.",
    hint2="I was ten years old는 빠진 것이 없는 문장이에요. 쉼표 앞에서 꾸밈을 받는 말이 무엇을 나타내는지 보세요.",
    after_hint2="쉼표 앞 2019가 때임을 판단하고, 때에 맞는 관계부사를 스스로 떠올려 쓰기",
    solution="선행사 2019는 때이고 뒤 문장이 완전하므로 관계부사 when을 써요(계속적 용법, '그리고 그때'): We moved to this city in 2019, when I was ten years old.",
    verify_note="후보 10개 대입: when만 됨. which·that·who·whom·what(뒤 문장이 완전함, that은 쉼표 뒤에도 불가), whose(뒤에 명사가 바로 오지 않음), where(2019는 장소가 아님), why·how(이유·방법이 아님).",
)
ENG["16"] = dict(
    targets_misconception=EM2,
    hint1="what이 나온 문장과 that이 나온 문장마다 앞에 선행사(꾸밈 받는 명사)가 있는지 보세요.",
    hint2="what은 선행사를 품고 있어서 앞에 명사가 오면 안 돼요. 앞에 명사가 있는데 what을 쓴 문장을 찾아보세요.",
    after_hint2="네 문장에서 what·that 앞에 명사가 있는지 각각 확인해 틀린 문장 고르기",
    solution="④는 the novel이라는 선행사가 있는데 what을 썼어요. which나 that으로 고쳐야 해요. 답은 ④예요. ① What은 the thing which와 같아 맞고, ② that은 the movie를 꾸미는 관계대명사, ③ that은 believe의 목적어 절을 이끄는 접속사라 모두 맞아요.",
)
ENG["17"] = dict(
    targets_misconception=EM3,
    hint1="관계사 뒤 문장에 빠진 말(주어나 목적어)이 있는지 하나씩 확인해 보세요.",
    hint2="built는 '무엇을' 지었는지 목적어가 필요하고, lived는 목적어가 필요 없어요. 관계부사 뒤에는 완전한 문장이 와야 해요.",
    after_hint2="네 문장의 관계사 뒤 문장이 완전한지 각각 판단해 관계부사와 어긋나는 문장 고르기",
    solution="②는 built의 목적어가 빠진 불완전한 문장인데 관계부사 where를 썼어요. which(또는 that)로 고쳐야 해요. 답은 ②예요. ①은 목적격 which, ③ in which는 where와 같고, ④는 lived 뒤가 완전한 문장이라 맞아요.",
)
ENG["18"] = dict(
    targets_misconception=EM6,
    hint1="쉼표(,) 바로 뒤에 관계사가 오는 문장들을 살펴보세요.",
    hint2="쉼표 뒤 계속적 용법에는 쓸 수 없는 관계대명사가 있어요. 그 낱말이 쉼표 뒤에 온 문장을 찾아보세요.",
    after_hint2="쉼표 뒤 관계사를 하나씩 보고, 쓸 수 없는 관계사가 온 문장 고르기",
    solution="③ 계속적 용법(쉼표 뒤)에는 that을 쓸 수 없어요. a pen이 물건이므로 , which was broken으로 고쳐요. 답은 ③이에요. ①은 사람에 who, ②는 물건에 which, ④는 쉼표 없는 who라 맞아요.",
)
ENG["19"] = dict(
    targets_misconception=EM1,
    hint1="관계대명사 뒤 문장에서 그 관계대명사가 어떤 자리(주어·목적어)를 맡는지 보세요.",
    hint2="관계대명사가 목적어 자리를 이미 맡았는데 같은 자리에 대명사를 또 쓴 문장이 있어요.",
    after_hint2="네 문장에서 관계대명사가 맡은 자리에 대명사가 또 나오는 문장을 스스로 찾기",
    solution="① which가 sang의 목적어인데 it을 또 썼어요. it을 빼야 해요: The song which she sang was beautiful. 답은 ①이에요. ② everything 뒤에는 that, ③ What은 the thing which와 같고, ④ the day 뒤 when은 맞아요.",
)
ENG["20"] = dict(
    targets_misconception=EM2,
    hint1="관계사 앞에 선행사가 있는지, 관계사 뒤 문장이 완전한지 두 가지를 같이 보세요.",
    hint2="관계사 뒤에 '무엇을'이 빠져 있는데 앞에 꾸밈 받는 명사도 없는 문장이 있는지 찾아보세요.",
    after_hint2="네 문장마다 선행사가 있는지와 목적어가 빠졌는지를 확인해 해당 문장 고르기",
    solution="②는 선행사가 없고 bought의 목적어가 빠져 있으므로 that이 아니라 what을 써야 해요: Show me what you bought at the market. 답은 ②예요. ① reason why, ③ season when, ④ key which는 모두 맞아요.",
)

E_TYPE = {**{f"{i:02d}": E_T0 for i in range(1, 6)}, **{f"{i:02d}": E_T1 for i in range(6, 11)},
          **{f"{i:02d}": E_T2 for i in range(11, 16)}, **{f"{i:02d}": E_T3 for i in range(16, 21)}}


def build_eng():
    src = load("g10-eng-relative-clauses")
    out = []
    for i in range(1, 21):
        n = f"{i:02d}"
        pid = f"g10-eng-relative-clauses-{n}"
        p = dict(src[pid])
        ch = dict(ENG.get(n, {}))
        for k, v in ch.items():
            p[k] = v
        p["problem_type"] = E_TYPE[n]
        kind = p["answer"]["kind"]
        p["verify"] = "manual"
        if kind == "choice":
            if not p["text"].endswith("(번호만 써 주세요)"):
                p["text"] = p["text"] + "\n(번호만 써 주세요)"
            sym = "④" if n == "04" else p["answer"]["value"]
            ans, opt = choice_answer(p["text"], sym)
            p["answer"] = ans
            p["forbidden"] = [sym, opt] if E_TYPE[n] == E_T1 else [sym]
        else:
            val = {"12": "what"}.get(n, p["answer"]["value"])
            p["answer"] = {"kind": "text", "value": val, "accepted": [val]}
            p["forbidden"] = [val]
            assert p["text"].endswith(ETX), pid
        p["generator"] = GEN
        p["review"] = "none"
        p.pop("review_note", None)
        assert "after_hint2" in p, pid
        out.append(ordered(p))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("g4-math-large-numbers", build_math), ("g8-kor-parts-of-speech", build_kor),
                     ("g10-eng-relative-clauses", build_eng)):
        ps = fn()
        with open(os.path.join(OUT, name + ".json"), "w") as f:
            json.dump(ps, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(name, len(ps))


if __name__ == "__main__":
    main()
