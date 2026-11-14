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
import json
import logging
import re
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
# 짧은 대화·초안이라 낮게. Haiku 5.5는 thinking을 생략하면 adaptive로 켜지고(effort 기본 medium),
# {"type": "disabled"}는 effort low~high에서만 받고 xhigh·max에서는 400이다(claude-api 스킬
# 「Migrating to Claude Haiku 5.5」, 2026-11 기준). 공식 권장이 effort로 줄이기라 thinking은 보내지 않는다
LIVE_EFFORT = "low"
# 서버 쪽 역할 이름 → API 역할. 아이 쪽은 child/mentor, 초안은 user를 쓴다
ROLE_MAP = {"child": "user", "user": "user", "mentor": "assistant", "assistant": "assistant"}
EMPTY_TURN = "(이어서)"  # 첫·끝 메시지가 user가 아닐 때 채우는 자리표시(원문 아님)
# 아이 화면으로 가는 단계. 이 단계 답만 속생각 걸러내기를 한다(강사 초안은 손대지 않는다)
CHILD_PHASES = frozenset({"study", "chat", "bridge"})
# 실제 모델 시험(11-13): 과부하(503)가 약 14%. SDK가 간격을 두고 다시 보낸다(전체는 FallbackAdapter 20초 안)
LIVE_MAX_RETRIES = 3
# 「너:」「멘토:」 같은 말한이 머리말(줄 맨 앞)
_LABEL = re.compile(r"^\s*\**\s*(?:너|멘토|나|답안|대답|답)\s*\**\s*[:：]\s*\**\s*", re.MULTILINE)
# 아이를 3인칭으로 가리키며 시작하는 답. 계획(「…한다.」)이면 버리고, 아이에게 하는 말이면 2인칭으로 고친다
_PLAN_START = re.compile(r"^\s*아이(?:가|는|에게|한테|의|를| 말| 답)")
# 11-13 시험: 오답에 「아이가 1/99라고 답했구나」가 18번 중 4~6번. 프롬프트로 다 안 막혀 앞머리만 고친다
_THIRD_TO_SECOND = (
    (re.compile(r"^아이가 낸 답"), "네가 낸 답"),
    (re.compile(r"^아이 답"), "네 답"),
    (re.compile(r"^아이의 답"), "네 답"),
    (re.compile(r"^아이가 "), "네가 "),
    (re.compile(r"^아이는 "), "너는 "),
)
# 서버 내부 말(「서버 판정은 오답이야」)은 아이에게 보내지 않는다
# 개인정보 가림 표시([이름] 등)를 따라 쓴 답도 아이에게 보내지 않는다(11-13 「[이름]이라고 부를게」)
_INTERNAL = re.compile(r"서버|판정|이번 답은|질문 없이 (말|끝)|\[(이름|전화|학교|이메일)\]")
# 11-13: 정규식으로 하나씩 막는 대신 응답 형식을 강제한다(구조화 출력). 아이에게 보낼 문장은 reply 칸에만.
# 생각·계획은 모델 내부 thinking으로 가고, 형식 밖 글은 나올 수 없다. clean_reply는 2차 안전망으로 남긴다
REPLY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}


def _reply_field(text: str) -> str:
    """구조화 출력의 reply 칸. JSON이 아니면(가짜 클라이언트·형식 미지원) 받은 글 그대로."""
    try:
        data = json.loads(text)
    except ValueError:
        return text
    return data.get("reply", "") if isinstance(data, dict) else text


# 멘토가 반·학교·집·가족이 있는 척(11-13 「그때 우리 반에선」). 멘토가 쓸 일이 없는 말이라 다시 받는다
_FAKE_LIFE = re.compile(
    r"우리\s*(반|학교|집|엄마|아빠|가족|동네)"
    # 「~더라」는 직접 겪은 일을 떠올리는 말끝(11-14 「신기하더라요」「어깨 펴지더라」)
    r"|더라(?:고|요)?(?=[\s.!?~ㅋㅎ,]|$)"
    # 11-14 held-out: 「물 한 잔 마시는 편」「멍하니 있었을 듯」「나도 구경하고 싶다」
    r"|(?:마시|먹)는 편|멍하니 있었을|구경하고 싶"
)
_QUOTES = ('""', "“”", "「」", "''")


def _is_plan(sentence: str) -> bool:
    """「…했다.」「…한다.」처럼 평서 「다」로 끝나거나, 「…라고 물었으니/했으니」처럼 아이 말을 근거로
    할 일을 정하는 문장이면 아이에게 하는 말이 아니라 계획이다."""
    s = sentence.strip()
    return (
        re.search(r"다[.!]?\s*$", s) is not None or re.search(r"(물었|했|말했)으니", s) is not None
    )


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]


def clean_reply(text: str) -> str | None:
    """아이에게 보낼 답만 남긴다. 「너:」 머리말이 있으면 마지막 머리말 뒤만 쓴다.
    계획 문단은 버리고, 3인칭 앞머리는 2인칭으로 고친다. 답이 없거나 서버 말이 섞이면 None
    (다시 받거나 대본으로)."""
    labels = list(_LABEL.finditer(text))
    if labels:
        text = text[labels[-1].end() :]
    text = text.strip()
    if len(text) >= 2 and any(text[0] == a and text[-1] == b for a, b in _QUOTES):
        text = text[1:-1].strip()
    # 계획 문단 뒤 빈 줄 다음에 답이 오는 모양이면 계획 문단만 버린다
    while _PLAN_START.match(text) and "\n\n" in text and _is_plan(text.split("\n\n", 1)[0]):
        text = text.split("\n\n", 1)[1].strip()
    if _FAKE_LIFE.search(text):
        # 반·학교·집이 있는 척·해 본 척 문장만 뺀다(답 전체를 버리면 대본으로 넘어간다)
        kept = [x for x in re.split(r"(?<=[.!?~ㅋㅎ])\s+", text) if x and not _FAKE_LIFE.search(x)]
        text = " ".join(kept).strip()
    if not text or _INTERNAL.search(text):
        return None
    if _PLAN_START.match(text):
        if _is_plan(_first_sentence(text)):
            return None
        for pat, repl in _THIRD_TO_SECOND:
            text = pat.sub(repl, text, count=1)
        if _PLAN_START.match(text):
            return None
    return text


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
    # 아이가 고른 말투. False면 대본의 존댓말을 반말로 바꿔 낸다(None = 모름, 그대로)
    polite: bool | None = None
    # 로그에만 쓴다(폴백 이유를 세션과 잇기, 수정 명세 B31). LLM에는 보내지 않는다
    session_id: str | None = None
    # 마지막 아이 말 바로 뒤에 붙이는 시스템 메시지(명세 부록 D 「수다 끝 무렵」). live만 쓴다
    tail_system: str | None = None


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


_BANMAL = (
    (re.compile(r"거예요"), "거야"),
    (re.compile(r"이에요"), "이야"),
    (re.compile(r"예요"), "야"),
    (re.compile(r"^네,\s*"), "응, "),
    (re.compile(r"(?<=[가-힣])요(?=[.!?~,]|\s|$)"), ""),
)


_POLITE_ENDINGS = (
    # 명세 부록 D 「이번 답 지시」(11-14): 「~군요」는 거리감 → 「~네요」(「쓰이는구나」→「쓰이네요」)
    (re.compile(r"(?:는)?구나요"), "네요"),
    (re.compile(r"겠다요"), "겠어요"),  # 11-14 held-out 「식은땀 나겠다요」
    (re.compile(r"(?<=[가-힣])지(?=[.!?~]|\s*$)"), "죠"),  # 수정 명세 T1 「기운 빠지지」
    (re.compile(r"겠다(?=[.!?~ㅋㅎ]|\s*$)"), "겠어요"),
    # 11-14 24조합: 존댓말에 감탄을 허용하자 「진짜 멋있다!」가 섞였다
    (re.compile(r"(?<=[있밌없])다(?=[.!?~ㅋㅎ]|\s*$)"), "어요"),
    (re.compile(r"(?:는)?구나(?=[.!?~]|\s*$)"), "네요"),
)


def fix_polite_endings(text: str) -> str:
    """존댓말 설정인데 섞여 나온 반말 말끝 두 가지만 고친다(11-13 시험에서 섞인 말끝이 이 둘)."""
    for pat, repl in _POLITE_ENDINGS:
        text = pat.sub(repl, text)
    return text


def to_banmal(text: str) -> str:
    """대본 존댓말 → 반말(11-13: 들어주는 스타일 대본은 전부 존댓말이라 반말 아이에게 어색했다).
    대본 63줄의 말끝만 다룬다(「~요」「~예요」「네,」)."""
    for pat, repl in _BANMAL:
        text = pat.sub(repl, text)
    return text


class ScriptedAdapter:
    def __init__(self, lines: list[dict[str, Any]]):
        self._by_key: dict[tuple[str, str, int, str | None], dict[int, str]] = {}
        # 존댓말 짝(명세 부록 C 「대본 말투」, 11-14 UT3). 사람이 고친 문장, 없으면 reply 그대로
        self._polite: dict[tuple[str, str, int, str | None, int], str] = {}
        for ln in lines:
            key = (ln["scenario"], ln["phase"], int(ln["hint_level"]), ln.get("judge"))
            self._by_key.setdefault(key, {})[int(ln["step"])] = ln["reply"]
            if ln.get("reply_polite"):
                self._polite[(*key, int(ln["step"]))] = ln["reply_polite"]

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
        step = req.step if req.step in steps else max(steps)
        text = steps[step]
        if req.polite:
            key = next(
                (req.scenario, req.phase, h, j)
                for h, j in keys
                if self._by_key.get((req.scenario, req.phase, h, j)) is steps
            )
            return Reply(self._polite.get((*key, step), text), "scripted")
        return Reply(to_banmal(text) if req.polite is False else text, "scripted")


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
                "llm fallback session=%s phase=%s hint=%s judge=%s reason=%s",
                req.session_id,
                req.phase,
                req.hint_level,
                req.judge,
                "timeout" if isinstance(exc, TimeoutError) else type(exc).__name__,
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
                api_key=self._api_key, timeout=LIVE_TIMEOUT_S, max_retries=LIVE_MAX_RETRIES
            )
        return self._client

    async def reply(self, req: ReplyRequest) -> Reply:
        # 아이 화면 단계에서 계획만 온 답은 한 번 더 받는다. 또 그러면 폴백(대본)으로
        for _ in range(2):
            out = await self._once(req)
            if req.phase not in CHILD_PHASES:
                return out
            text = clean_reply(out.text)
            if text is not None and req.polite:
                text = fix_polite_endings(text)
            if text is not None:
                return Reply(text, "live", in_tokens=out.in_tokens, out_tokens=out.out_tokens)
            log.warning("llm meta reply phase=%s len=%d", req.phase, len(out.text))
        raise ValueError("llm meta reply")

    async def _once(self, req: ReplyRequest) -> Reply:
        resp = await self._get_client().messages.create(
            model=self.model,
            max_tokens=LIVE_MAX_TOKENS,
            system=req.system,
            messages=to_messages(req.turns)
            + ([{"role": "system", "content": req.tail_system}] if req.tail_system else []),
            output_config=(
                {"effort": LIVE_EFFORT, "format": {"type": "json_schema", "schema": REPLY_SCHEMA}}
                if req.phase in CHILD_PHASES
                else {"effort": LIVE_EFFORT}
            ),
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("llm refusal")
        if resp.stop_reason == "max_tokens":  # 끊긴 답은 아이에게 보내지 않는다 → 폴백이 대본으로
            raise RuntimeError("llm truncated")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if req.phase in CHILD_PHASES:
            text = _reply_field(text).strip()
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
