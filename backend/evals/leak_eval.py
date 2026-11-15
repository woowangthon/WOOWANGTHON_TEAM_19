"""학년별 시범 문제 정답 누설 실제 모델 시험(명세 4.13 G6, 11-14).

단원마다 6문제 × 힌트 0~2 대화를 실제 모델로 돌리고, 서버와 같은 검사(contains_answer + forbidden)로
누설을 센다. 정답·답 문장은 화면에 내지 않고 셈만 낸다(답 문장은 --out 파일에만).
  cd backend && uv run python -m evals.leak_eval --out /tmp/leak.json
"""

import argparse
import asyncio
import json
import re
from collections import Counter
from pathlib import Path

from app import config
from app.judge import contains_answer
from app.llm import AnthropicAdapter, FallbackAdapter, ReplyRequest, ScriptedAdapter
from app.prompts import PromptInput, build_prompt, subject_name
from app.seed import BANK_DIR

PICK = ("01", "04", "07", "10", "13", "16")
# 명세 부록 D 「보기형 힌트」: 「틀린/다른 것 고르기」형을 더한다(11-14 bb 판단)
ODD_ONE_OUT = {f"g10-eng-relative-clauses-{n}" for n in (16, 17, 18, 19, 20)} | {
    "g8-kor-parts-of-speech-11",
    "g8-kor-parts-of-speech-12",
}
STYLES = ("EBSP", "EQLC", "DQSC")
FRACTION_WORDS = re.compile(r"분수|분자|분모")


def _wrong(p: dict) -> str:
    kind = p["answer"]["kind"]
    if kind == "choice":
        right = p["answer"]["value"]
        return next(c for c in "①②③④" if c != right)
    if kind == "text":
        return "that" if p["subject"] == "english" else "명사"
    return "1"


def _reason(text: str, p: dict) -> str | None:
    if not contains_answer(text, p["answer"], p["text"], p.get("forbidden")):
        return None
    if p["answer"]["kind"] == "choice":
        num_only = contains_answer(text, {**p["answer"], "accepted": []}, p["text"])
        return "choice" if num_only else "choice_text"
    return p["answer"]["kind"]


async def run(out: Path) -> None:
    key = config.llm_api_key()
    assert key, "LLM_API_KEY 없음"
    adapter = FallbackAdapter(
        AnthropicAdapter(api_key=key, model=config.llm_model()), ScriptedAdapter.from_file()
    )
    bank = [q for f in sorted(BANK_DIR.glob("*.json")) for q in json.loads(f.read_text("utf-8"))]
    probs = [q for q in bank if q["id"].rsplit("-", 1)[1] in PICK or q["id"] in ODD_ONE_OUT]
    rows = []
    for i, p in enumerate(probs):
        style = STYLES[i % 3]
        polite = i % 2 == 1
        band = {4: "초3-4", 8: "중1-3", 10: "고1-3"}.get(p["grade"], "초5-6")
        steps = [
            ("몰라 어떻게 해", 0, None),
            (_wrong(p), 1, "wrong"),
            ("힌트 하나만 더 줘", 2, None),
        ]
        turns: list[dict[str, str]] = []
        for child, hint, judge in steps:
            turns.append({"role": "child", "text": child})
            pr = build_prompt(
                PromptInput(
                    phase="study",
                    grade_band=band,
                    honorific="friend",
                    style=style,
                    polite=polite,
                    problem_text=p["text"],
                    hint1=p["hint1"],
                    hint2=p["hint2"],
                    solution=p["solution"],
                    hint_level=hint,
                    judge=judge,
                    turns=turns[-20:],
                    subject=subject_name(p["subject"]),
                )
            )
            r = await adapter.reply(
                ReplyRequest(
                    scenario=f"day3-{style}",
                    phase="study",
                    hint_level=hint,
                    step=1,
                    system=pr.system,
                    turns=pr.turns,
                    judge=judge,
                    polite=polite,
                    tail_system=pr.tail,
                )
            )
            turns.append({"role": "mentor", "text": r.text})
            rows.append(
                {
                    "id": p["id"],
                    "subject": p["subject"],
                    "hint": hint,
                    "source": r.source,
                    "leak": _reason(r.text, p) if r.source == "live" else None,
                    "fraction_word": bool(FRACTION_WORDS.search(r.text)) and p["subject"] != "math",
                    "reply": r.text,
                }
            )
    live = [x for x in rows if x["source"] == "live"]
    summary = {
        "답": len(rows),
        "대본으로 넘어감": len(rows) - len(live),
        "누설(live 답 기준)": sum(1 for x in live if x["leak"]),
        "누설 이유": dict(Counter(x["leak"] for x in live if x["leak"])),
        "과목별 누설": dict(Counter(x["subject"] for x in live if x["leak"])),
        "국어·영어 답에 분수 낱말": sum(1 for x in live if x["fraction_word"]),
    }
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    asyncio.run(run(ap.parse_args().out))


if __name__ == "__main__":
    main()
