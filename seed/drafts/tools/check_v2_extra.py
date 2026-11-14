"""v2 칸·규칙 추가 검사(pilot_review의 검사기 제안 일부). 사용: python3 -I tools/check_v2_extra.py bank/problems_v2/*.json --blueprint bank/v2_blueprint_*.json"""
import json, re, sys
from collections import Counter, defaultdict
argv = sys.argv[1:]
i = argv.index("--blueprint"); files, bps = argv[:i], argv[i+1:]
bp = {u["unit_id"]: u for f in bps for u in json.load(open(f))}
LAST = {("math","value"):"(쉼표 없이 숫자만)", ("korean","choice"):"(번호만 써 주세요)", ("english","choice"):"(번호만 써 주세요)",
        ("korean","text"):"(한 낱말로 써 주세요)", ("english","text"):"(영어 한 단어로 써 주세요)"}
bad = []
for f in files:
    ps = json.load(open(f)); u = bp[ps[0]["unit_id"]]
    types = {t["type"]: t for t in u["problem_types"]}
    cnt = Counter(p["problem_type"] for p in ps)
    for t in u["problem_types"]:
        if cnt[t["type"]] != t["count"]: bad.append((u["unit_id"], f"유형 개수 {t['type'][:20]} {cnt[t['type']]}≠{t['count']}"))
    hint_sents = Counter()
    for p in ps:
        pid = p["id"][-2:]; a = p["answer"]
        t = types.get(p["problem_type"])
        if not t: bad.append((p["id"], "problem_type 설계도에 없음")); continue
        if t["difficulty"] != p["difficulty"]: bad.append((p["id"], "난이도≠유형"))
        if p["targets_misconception"] and p["targets_misconception"] not in u["misconceptions"]: bad.append((p["id"], "오개념 문장 설계도에 없음"))
        if p["subject"] == "math" and p["standard"]["code"] not in t["covers"]: bad.append((p["id"], "code∉covers"))
        if p["text"].split("\n")[-1] != LAST[(p["subject"], a["kind"])]: bad.append((p["id"], "마지막 줄 고정 문구 아님"))
        if not p.get("after_hint2") or p["after_hint2"] in ("없음", "답 쓰기"): bad.append((p["id"], "after_hint2"))
        if p.get("verify") not in ("expr", "manual"): bad.append((p["id"], "verify"))
        if p["verify"] == "manual" and p["subject"] == "math" and not p.get("verify_note"): bad.append((p["id"], "verify_note 없음"))
        if a["kind"] == "text" and not p.get("verify_note"): bad.append((p["id"], "단답 verify_note 없음"))
        if p["review"] not in ("none", "needs_review") or (p["review"] == "needs_review" and not re.match(r"\[(사전|유일성|범위|코드|난이도|오개념)\]", p.get("review_note", ""))): bad.append((p["id"], "review"))
        if a["kind"] == "choice" and a["value"] not in p["forbidden"]: bad.append((p["id"], "forbidden에 정답 기호 없음"))
        if a["kind"] == "text" and a["value"] not in p["forbidden"]: bad.append((p["id"], "forbidden에 정답 낱말 없음"))
        lines = p["text"].split("\n")
        first_opt = next((k for k, l in enumerate(lines) if l[:1] in "①②③④"), len(lines))
        if any(c in "\n".join(lines[:first_opt]) for c in "①②③④"): bad.append((p["id"], "보기 목록 밖 ①~④"))
        if len(lines) > 8: bad.append((p["id"], f"text {len(lines)}줄"))
        for l in lines[first_opt:]:
            if l[:1] in "①②③④" and len(l) > (60 if p["subject"] == "english" and re.search("[A-Za-z]{3}", l) else 30): bad.append((p["id"], f"보기 줄 김 {len(l)}"))
        if p["subject"] == "english" and re.search(r"[^\x00-\x7f]", "\n".join(re.findall(r"[A-Za-z][A-Za-z ,.'?!0-9]+[A-Za-z.?!]", p["text"]))): bad.append((p["id"], "영문 ASCII 밖"))
        for fld in ("hint1", "hint2", "solution"):
            for s in re.split(r"(?<=[.?!])\s+", p[fld]):
                if re.search(r"(봐|보자|해|야|어|지)\.$|[^요]다\.$", s.strip()) and not re.search(r"[A-Za-z]\.$", s.strip()): bad.append((p["id"], f"{fld} 문체? {s.strip()[-15:]}"))
        for s in re.split(r"(?<=[.?!])\s+", p["hint1"] + " " + p["hint2"]):
            hint_sents[s.strip()] += 1
        if re.search(r"(이)?라면|안 되면|그보다 하나", p["hint1"] + p["hint2"]): bad.append((p["id"], "가정형 표현"))
    for s, n in hint_sents.items():
        if n > 1 and len(s) > 10: bad.append((u["unit_id"], f"힌트 문장 되풀이 {s[:30]}"))
for x in bad: print("X", *x)
print("extra issues:", len(bad))
