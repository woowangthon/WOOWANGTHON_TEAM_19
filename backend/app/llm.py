"""LLM 어댑터 하나 (명세 4 원칙 ②). 서버 코드는 `reply()`만 부른다.

- scripted: 대본 YAML(부록 C)에서 (scenario, phase, hint_level, judge, step)로 찾는다.
  키가 없으면 (hint_level, judge) → (0, judge) → (hint_level, 없음) → (0, 없음) 순,
  같은 키 안에서는 마지막 step → 고정 문장. judge 열이 없는 줄은 「판정 없음」 줄이다.
- live: Anthropic(TK-47 1순위). build_adapter()가 FallbackAdapter로 감싸
  20초 초과·오류·빈 응답·거절이면 scripted로.
로그에는 단계·길이만 남기고 문장은 남기지 않는다.
reply()는 Reply(문장, source, 토큰 수)를 돌려준다. source로 그 답이 live였는지 밖에서 안다(B1).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml
from anthropic import AsyncAnthropic

from app import config

log = logging.getLogger(__name__)

SCRIPT_PATH = Path(__file__).resolve().parent / "scripts" / "day3.yaml"
FIXED_REPLY = "잠깐 생각이 막혔어. 한 번만 다시 말해 줄래?"
LIVE_TIMEOUT_S = 20.0
LIVE_MAX_TOKENS = 1024  # 생각(thinking) 토큰도 여기서 나간다. 답 길이는 프롬프트가 정한다
LIVE_EFFORT = "low"  # 짧은 대화·초안이라 낮게. thinking 끄기는 모델마다 400이라 effort로만
# 서버 쪽 역할 이름 → API 역할. 아이 쪽은 child/mentor, 초안은 user를 쓴다
ROLE_MAP = {"child": "user", "user": "user", "mentor": "assistant", "assistant": "assistant"}
EMPTY_TURN = "(이어서)"  # 첫·끝 메시지가 user가 아닐 때 채우는 자리표시(원문 아님)


@dataclass(frozen=True)
class ReplyRequest:
    scenario: str  # day3-{스타일 코드}
    phase: str  # study / chat / bridge
    hint_level: int
    step: int  # 이 단계에서 아이 메시지 순번(1부터)
    system: str  # 조립된 시스템 프롬프트(정답·별명 없음)
    turns: list[dict[str, str]] = field(default_factory=list)  # 치환본 최근 턴
    # 서버 판정(이번 답이 다루는 조각들의 요약). live는 system의 판정 문장, scripted는 대본 열로 쓴다
    judge: Literal["correct", "wrong"] | None = None


Source = Literal["live", "scripted", "fixed"]


@dataclass(frozen=True)
class Reply:
    """어댑터 응답. source: live=공급자, scripted=대본 줄, fixed=대본에 키가 없어 고정 문장."""

    text: str
    source: Source
    in_tokens: int | None = None  # live만(usage). 대본은 None
    out_tokens: int | None = None


class LLMAdapter(Protocol):
    async def reply(self, req: ReplyRequest) -> Reply: ...


class ScriptedAdapter:
    def __init__(self, lines: list[dict[str, Any]]):
        self._by_key: dict[tuple[str, str, int, str | None], dict[int, str]] = {}
        for ln in lines:
            key = (ln["scenario"], ln["phase"], int(ln["hint_level"]), ln.get("judge"))
            self._by_key.setdefault(key, {})[int(ln["step"])] = ln["reply"]

    @classmethod
    def from_file(cls, path: Path = SCRIPT_PATH) -> "ScriptedAdapter":
        return cls(yaml.safe_load(path.read_text(encoding="utf-8")) or [])

    async def reply(self, req: ReplyRequest) -> Reply:
        # 판정 줄이 먼저(정답에 「다시 해 볼래?」가 나가지 않게). 힌트를 쓴 뒤(예: chat,
        # hint_level 3)에도 대본이 있게 같은 단계 hint_level 0 줄로 한 번 더
        keys = [(req.hint_level, req.judge), (0, req.judge), (req.hint_level, None), (0, None)]
        steps = next(
            (s for h, j in keys if (s := self._by_key.get((req.scenario, req.phase, h, j)))), None
        )
        if not steps:
            return Reply(FIXED_REPLY, "fixed")
        return Reply(steps.get(req.step) or steps[max(steps)], "scripted")


class FallbackAdapter:
    """live가 느리거나 실패하면 scripted. 상태는 바꾸지 않는다(명세 4.6)."""

    def __init__(
        self, primary: LLMAdapter, fallback: LLMAdapter, timeout_s: float = LIVE_TIMEOUT_S
    ):
        self._primary = primary
        self._fallback = fallback
        self._timeout_s = timeout_s

    async def reply(self, req: ReplyRequest) -> Reply:
        # 실제로 답한 쪽의 Reply를 그대로 돌려준다(source가 폴백 여부를 알려 준다)
        try:
            return await asyncio.wait_for(self._primary.reply(req), self._timeout_s)
        except Exception as exc:  # 타임아웃 포함. 원문·응답은 로그에 남기지 않는다
            log.warning(
                "llm fallback phase=%s hint=%s judge=%s err=%s",
                req.phase,
                req.hint_level,
                req.judge,
                type(exc).__name__,
            )
            return await self._fallback.reply(req)


def to_messages(turns: list[dict[str, str]]) -> list[dict[str, str]]:
    """서버 턴 → Messages API 모양. 같은 역할 연속은 합치고, 첫·끝은 user로 맞춘다
    (assistant로 끝나면 프리필이 되어 400)."""
    out: list[dict[str, str]] = []
    for t in turns:
        role = ROLE_MAP.get(t.get("role", ""), "user")
        text = t.get("content") or t.get("text") or ""
        if not text:
            continue
        if out and out[-1]["role"] == role:
            out[-1] = {"role": role, "content": out[-1]["content"] + "\n" + text}
        else:
            out.append({"role": role, "content": text})
    if not out or out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": EMPTY_TURN})
    if out[-1]["role"] != "user":
        out.append({"role": "user", "content": EMPTY_TURN})
    return out


class AnthropicAdapter:
    """live. 비스트리밍 messages.create 1회. 클라이언트는 첫 호출 때 만든다."""

    def __init__(self, api_key: str, model: str = "claude-haiku-5-5", client: Any = None):
        self._api_key = api_key
        self.model = model
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            # 재시도는 FallbackAdapter의 20초 안에서 끝나야 의미가 있어 1회만
            self._client = AsyncAnthropic(
                api_key=self._api_key, timeout=LIVE_TIMEOUT_S, max_retries=1
            )
        return self._client

    async def reply(self, req: ReplyRequest) -> Reply:
        resp = await self._get_client().messages.create(
            model=self.model,
            max_tokens=LIVE_MAX_TOKENS,
            system=req.system,
            messages=to_messages(req.turns),
            output_config={"effort": LIVE_EFFORT},
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("llm refusal")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            raise ValueError("llm empty reply")
        usage = getattr(resp, "usage", None)
        in_tokens = getattr(usage, "input_tokens", None)
        out_tokens = getattr(usage, "output_tokens", None)
        log.info(
            "llm live phase=%s judge=%s len=%d in_tokens=%s out_tokens=%s",
            req.phase,
            req.judge,
            len(text),
            in_tokens,
            out_tokens,
        )
        return Reply(text, "live", in_tokens=in_tokens, out_tokens=out_tokens)


@lru_cache(maxsize=4)
def _live_adapter(api_key: str, model: str) -> AnthropicAdapter:
    # 요청마다 클라이언트를 새로 만들지 않게 키·모델별로 하나
    return AnthropicAdapter(api_key=api_key, model=model)


def build_adapter(scripted: LLMAdapter) -> LLMAdapter:
    """LLM_MODE=live이고 키가 있으면 live(실패 시 scripted), 아니면 scripted 그대로."""
    key = config.llm_api_key()
    if config.llm_effective_mode() != "live" or key is None:
        return scripted
    return FallbackAdapter(_live_adapter(key, config.llm_model()), scripted)
