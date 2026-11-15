"""문제 은행 초안 자동 검사(⑥). 사용: python3 -I check_bank.py <problems.json>... [--blueprint bp.json ...]

실패(FAIL)는 고쳐야 하고, 경고(WARN)는 사람이 판단한다.
- 수학: expr 재계산 == answer.value(>0), 현재 judge()로 value·accepted가 정답 판정되는지,
        실행 중 누설 검사(contains_answer)로 hint1·hint2가 정답을 흘리는지,
        시드 검증기 기준 표기(answer_forms)가 forbidden에 다 있는지, text·hint에 보이는지(WARN)
- choice: value가 ①~④, text에 ①~④ 보기 4개, hint에 정답 기호 없음, 단원별 정답 위치 쏠림(WARN)
- text: accepted 1개 이상, hint에 정답 낱말 없음(대소문자 무시, 낱말 경계)
- 공통: 필수 칸, id 유일, 문제 글 중복, 단원별 20문제·난이도 배분(설계도와 비교)
"""

import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from fractions import Fraction

from pathlib import Path

REPO = str(Path(__file__).resolve().parents[3])  # seed/drafts/tools → 저장소 루트
sys.path.insert(0, REPO + "/backend")
from app.judge import contains_answer, judge  # noqa: E402

_spec = importlib.util.spec_from_file_location("vs", REPO + "/seed/validate_seed.py")
vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vs)  # type: ignore[union-attr]

REQ = ["id", "unit_id", "subject", "grade", "difficulty", "text", "answer", "hint1", "hint2", "solution", "forbidden", "source"]
CIRCLED = ["①", "②", "③", "④"]


def _word_in(w, text):
    """낱말 경계 검사. 영어는 앞뒤 경계, 한글은 앞 경계만(뒤에 조사가 붙어도 잡는다)."""
    if re.fullmatch(r"[A-Za-z' -]+", w):
        return re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", text, re.I) is not None
    return re.search(r"(?<![가-힣A-Za-z])" + re.escape(w), text) is not None


def check(p, fails, warns):
    pid = p.get("id", "?")
    miss = [k for k in REQ if k not in p]
    if miss:
        fails.append((pid, f"필수 칸 없음 {miss}"))
        return
    a = p["answer"]
    kind = a.get("kind")
    hints = p["hint1"] + "\n" + p["hint2"]
    if p["subject"] == "math":
        try:
            v = vs.eval_expr(p["expr"])
        except Exception as e:  # noqa: BLE001
            fails.append((pid, f"expr 평가 실패 {p.get('expr')!r}: {e}"))
            return
        try:
            va = Fraction(a["value"])
        except Exception:  # noqa: BLE001
            fails.append((pid, f"answer.value가 수가 아님 {a['value']!r}"))
            return
        if v != va:
            fails.append((pid, f"expr={v} ≠ value={va}"))
        if v <= 0:
            fails.append((pid, f"정답이 양수가 아님 {v}"))
        if judge(a["value"], a) != "correct":
            fails.append((pid, f"judge가 value {a['value']!r}를 정답으로 못 읽음"))
        for s in a.get("accepted", []):
            if judge(s, a) != "correct":
                warns.append((pid, f"accepted {s!r}는 judge가 정답으로 못 읽음(죽은 표기)"))
        for h in ("hint1", "hint2"):
            if contains_answer(p[h], a, p["text"]):
                fails.append((pid, f"{h}가 실행 중 누설 검사에 걸림"))
        forms = vs.answer_forms(v) if v > 0 else set()
        lack = [f for f in forms if f not in p["forbidden"]]
        if lack:
            warns.append((pid, f"forbidden에 기본 표기 없음 {lack}"))
        for f in forms:
            for fld in ("text", "hint1", "hint2"):
                if vs.contains_form(p[fld], f):
                    warns.append((pid, f"{fld}에 정답 표기 {f!r}가 보임(시드 검증기 기준)"))
    elif kind == "choice":
        if a.get("value") not in CIRCLED:
            fails.append((pid, f"choice value가 ①~④가 아님 {a.get('value')!r}"))
        if not all(c in p["text"] for c in CIRCLED):
            fails.append((pid, "text에 보기 ①~④가 다 없음"))
        if a.get("value") in hints or re.search(r"정답[은는]?\s*[①-④1-4]", hints):
            fails.append((pid, "힌트에 정답 기호"))
        # 정답 보기 문구가 힌트에 그대로 나오면 경고(문제 글에도 있는 낱말이라 사람 판단)
        m = re.search(re.escape(a.get("value", "")) + r"\s*([^\n①②③④]+)", p["text"])
        if m:
            opt = m.group(1).strip().rstrip(".")
            if len(opt) >= 2 and _word_in(opt, hints):
                warns.append((pid, f"힌트에 정답 보기 문구 {opt!r}"))
    elif kind == "text":
        acc = a.get("accepted") or []
        if not acc:
            fails.append((pid, "text accepted 비어 있음"))
        for w in acc:
            if _word_in(w, hints):
                fails.append((pid, f"힌트에 정답 낱말 {w!r}"))
    else:
        fails.append((pid, f"알 수 없는 answer.kind {kind!r}"))


def main(argv):
    files = [x for x in argv if not x.startswith("--")]
    bps = []
    if "--blueprint" in argv:
        i = argv.index("--blueprint")
        bps = argv[i + 1 :]
        files = argv[:i]
    probs = []
    for f in files:
        probs += json.load(open(f))
    fails, warns = [], []
    ids = Counter(p.get("id") for p in probs)
    for k, n in ids.items():
        if n > 1:
            fails.append((k, f"id 중복 {n}회"))
    texts = Counter(re.sub(r"\s+", "", p.get("text", "")) for p in probs)
    for t, n in texts.items():
        if n > 1:
            fails.append((t[:30], f"문제 글 중복 {n}회"))
    for p in probs:
        check(p, fails, warns)
    by_unit = defaultdict(list)
    for p in probs:
        by_unit[p.get("unit_id")].append(p)
    bp = {}
    for f in bps:
        for u in json.load(open(f)):
            bp[u["unit_id"]] = u
    for u, ps in sorted(by_unit.items()):
        mix = Counter(p.get("difficulty") for p in ps)
        line = f"{u}: {len(ps)}문제 {dict(mix)}"
        if u in bp:
            want = bp[u].get("difficulty_mix", {})
            if dict(mix) != {k: v for k, v in want.items() if v}:
                warns.append((u, f"난이도 배분 {dict(mix)} ≠ 설계도 {want}"))
            if len(ps) != sum(want.values()):
                fails.append((u, f"문제 수 {len(ps)} ≠ 설계도 {sum(want.values())}"))
        pos = Counter(p["answer"].get("value") for p in ps if p["answer"].get("kind") == "choice")
        if pos:
            line += f" 정답위치 {dict(sorted(pos.items()))}"
            if max(pos.values()) > 0.4 * sum(pos.values()):
                warns.append((u, f"정답 위치 쏠림 {dict(pos)}"))
        print(line)
    print(f"\n총 {len(probs)}문제 · FAIL {len(fails)} · WARN {len(warns)}")
    for pid, m in fails:
        print("FAIL", pid, m)
    for pid, m in warns:
        print("WARN", pid, m)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
