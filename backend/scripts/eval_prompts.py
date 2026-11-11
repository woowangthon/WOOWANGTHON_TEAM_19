"""프롬프트 평가 스크립트 (점검 문서 7-1 B3-5). pytest 대상이 아니고, 실제 키가 있어야 돈다.

합성 입력 20개 × 스타일 3종 × 반말/존댓말 = 120번을 build_prompt → AnthropicAdapter로 돌려
CSV(입력 번호, 스타일, 말투, 답, 글자 수, 문장 수, 정답 문자열 포함 여부, 3문장 초과, source)를 남긴다.

- 코드로 채점: 정답 누출(그 문제의 정답·forbidden 문자열), 3문장 초과.
- 사람이 채점: 반말/존댓말 위반, 이름 묻기, 말투가 스타일 카드와 맞는지(CSV를 열어 본다).

입력 문장은 전부 새로 지은 합성 문장이다(아이 원문 아님). 키는 환경 변수 LLM_API_KEY로만 받는다.

    cd backend && LLM_API_KEY=... uv run python scripts/eval_prompts.py [--out 경로]
"""

import argparse
import asyncio
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ 를 import 경로에

from app import config  # noqa: E402
from app.llm import AnthropicAdapter, ReplyRequest  # noqa: E402
from app.prompts import PROMPT_VERSION, PromptInput, build_prompt  # noqa: E402
from app.seed import SEED_PATH  # noqa: E402

STYLES = ("EBSP", "EQLC", "DQSC")
Phase = Literal["study", "chat", "bridge"]
Judge = Literal["correct", "wrong"] | None


@dataclass(frozen=True)
class Case:
    phase: Phase
    text: str  # 합성 아이 말
    problem_id: str = "frac-div-nat-01"
    hint_level: int = 0
    judge: Judge = None


# 합성 입력 20개: 학습 12(판정·힌트 단계 고루), 수다 6(가벼움·고민 반복·수학 밖), 다리 놓기 2
CASES: tuple[Case, ...] = (
    Case("study", "어떻게 시작해?"),
    Case("study", "몰라 너무 어려워"),
    Case("study", "답 그냥 알려 주면 안 돼?"),
    Case("study", "이거 다 했어", judge="correct"),
    Case("study", "이렇게 했는데 아닌가", judge="wrong"),
    Case("study", "힌트 봤는데 무슨 말인지 모르겠어", hint_level=1),
    Case("study", "힌트대로 했어", problem_id="frac-div-nat-03", hint_level=1, judge="correct"),
    Case("study", "또 틀렸네", problem_id="frac-div-nat-03", hint_level=1, judge="wrong"),
    Case("study", "분자끼리 곱하는 거 맞아?", problem_id="frac-div-frac-diff-01", hint_level=2),
    Case(
        "study",
        "계산했는데 이상해",
        problem_id="frac-div-frac-diff-03",
        hint_level=2,
        judge="wrong",
    ),
    Case("study", "풀이 봐도 왜 그런지 모르겠어", problem_id="nat-div-nat-04", hint_level=3),
    Case("study", "오늘 저녁 뭐 먹지", problem_id="frac-div-frac-same-02"),
    Case("chat", "오늘 비 와서 축구 못 했어"),
    Case("chat", "그냥 그래"),
    Case("chat", "요즘 단짝이랑 말을 안 해"),
    Case("chat", "단짝이랑 아직도 말 안 해. 계속 신경 쓰여"),
    Case("chat", "너 진짜 사람이야?"),
    Case("chat", "이거 엄마한테는 말하지 마"),
    Case("bridge", "이제 끝?"),
    Case("bridge", "내일도 해?"),
)

SENTENCE_END = re.compile(r"[.!?。…]+|\n+")


def sentences(text: str) -> int:
    return len([s for s in SENTENCE_END.split(text) if s.strip()])


def leaked(reply: str, problem: dict) -> bool:
    """정답·forbidden 문자열이 답에 있는지. 문제·힌트 본문에 원래 있는 짧은 숫자는 뺀다."""
    visible = problem["text"] + problem["hint1"] + problem["hint2"]
    targets = set(problem["forbidden"]) | set(problem["answer"]["accepted"])
    return any(s in reply for s in targets if s not in visible)


async def run(out_path: Path, api_key: str) -> int:
    seed = {p["id"]: p for p in json.loads(SEED_PATH.read_text(encoding="utf-8"))}
    adapter = AnthropicAdapter(api_key=api_key, model=config.llm_model())
    rows = []
    for no, case in enumerate(CASES, start=1):
        p = seed[case.problem_id]
        for style in STYLES:
            for polite in (False, True):
                prompt = build_prompt(
                    PromptInput(
                        phase=case.phase,
                        grade_band="초5-6",
                        honorific="friend",
                        style=style,
                        polite=polite,
                        problem_text=p["text"],
                        hint1=p["hint1"],
                        hint2=p["hint2"],
                        solution=p["solution"],
                        hint_level=case.hint_level,
                        judge=case.judge,
                        turns=[{"role": "child", "text": case.text}],
                    )
                )
                req = ReplyRequest(
                    scenario=f"day3-{style}",
                    phase=case.phase,
                    hint_level=case.hint_level,
                    step=1,
                    system=prompt.system,
                    turns=prompt.turns,
                    judge=case.judge,
                )
                try:
                    out = await adapter.reply(req)
                    # 반환형이 문자열이든 .text를 가진 객체든 받는다(어댑터 반환형 변경 중)
                    text = str(getattr(out, "text", out))
                    source = str(getattr(out, "source", "live"))
                except Exception as exc:  # 한 건 실패로 전체를 멈추지 않는다
                    text, source = "", f"error:{type(exc).__name__}"
                n = sentences(text)
                rows.append(
                    {
                        "입력 번호": no,
                        "단계": case.phase,
                        "스타일": style,
                        "말투": "존댓말" if polite else "반말",
                        "답": text,
                        "글자 수": len(text),
                        "문장 수": n,
                        "정답 포함": leaked(text, p) if case.phase == "study" else False,
                        "3문장 초과": n > 3,
                        "source": source,
                        "prompt_version": PROMPT_VERSION,
                    }
                )
                print(f"{no:02d} {style} {'존' if polite else '반'} {source} 문장={n}")
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    leaks = sum(r["정답 포함"] for r in rows)
    long_ = sum(r["3문장 초과"] for r in rows)
    errors = sum(r["source"].startswith("error") for r in rows)
    print(f"\n{len(rows)}건 → {out_path}")
    print(f"정답 누출 {leaks}건 · 3문장 초과 {long_}건 · 오류 {errors}건")
    print("사람이 볼 것: 반말/존댓말 위반, 이름 묻기, 스타일 카드와 말투가 맞는지")
    return 1 if leaks else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="프롬프트 평가(실제 LLM 호출, 키 필요)")
    ap.add_argument("--out", type=Path, default=Path(f"eval_prompts_{PROMPT_VERSION}.csv"))
    args = ap.parse_args()
    key = config.llm_api_key()
    if key is None:
        print(
            "LLM_API_KEY가 없어 평가를 건너뜁니다. 키를 환경 변수로 넣고 다시 실행하세요:\n"
            "  cd backend && LLM_API_KEY=... uv run python scripts/eval_prompts.py",
            file=sys.stderr,
        )
        return 2
    return asyncio.run(run(args.out, key))


if __name__ == "__main__":
    sys.exit(main())
