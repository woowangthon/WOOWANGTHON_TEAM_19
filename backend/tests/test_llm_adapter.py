"""LLM 어댑터 (명세 4 원칙 ②, 4.6, 부록 C). 실제 공급자는 호출하지 않는다."""

import asyncio

import pytest

from app.llm import (
    FIXED_REPLY,
    AnthropicAdapter,
    FallbackAdapter,
    Reply,
    ReplyRequest,
    ScriptedAdapter,
    build_adapter,
    to_messages,
)

LINES = [
    {"scenario": "day3-EBSP", "phase": "study", "hint_level": 0, "step": 1, "reply": "s0-1"},
    {"scenario": "day3-EBSP", "phase": "study", "hint_level": 0, "step": 2, "reply": "s0-2"},
    {"scenario": "day3-EBSP", "phase": "chat", "hint_level": 0, "step": 1, "reply": "c-1"},
]


def _req(phase="study", hint_level=0, step=1, scenario="day3-EBSP") -> ReplyRequest:
    return ReplyRequest(
        scenario=scenario, phase=phase, hint_level=hint_level, step=step, system="", turns=[]
    )


async def test_scripted_returns_exact_key():
    assert await ScriptedAdapter(LINES).reply(_req(step=2)) == Reply("s0-2", "scripted")


async def test_scripted_falls_back_to_last_step_of_same_key():
    assert (await ScriptedAdapter(LINES).reply(_req(step=9))).text == "s0-2"


async def test_scripted_falls_back_to_fixed_reply_when_no_key():
    assert await ScriptedAdapter(LINES).reply(_req(phase="bridge")) == Reply(FIXED_REPLY, "fixed")


async def test_scripted_loads_default_yaml_file():
    adapter = ScriptedAdapter.from_file()
    assert (await adapter.reply(_req())).source == "scripted"


class _Boom:
    async def reply(self, req: ReplyRequest) -> Reply:
        raise RuntimeError("provider down")


class _Slow:
    async def reply(self, req: ReplyRequest) -> Reply:
        await asyncio.sleep(1)
        return Reply("late", "live")


class _Ok:
    async def reply(self, req: ReplyRequest) -> Reply:
        return Reply("live", "live")


async def test_fallback_uses_primary_when_ok():
    adapter = FallbackAdapter(_Ok(), ScriptedAdapter(LINES))
    assert await adapter.reply(_req()) == Reply("live", "live")


@pytest.mark.parametrize("primary", [_Boom(), _Slow()])
async def test_fallback_uses_scripted_on_error_or_timeout(primary):
    adapter = FallbackAdapter(primary, ScriptedAdapter(LINES), timeout_s=0.05)
    assert await adapter.reply(_req()) == Reply("s0-1", "scripted")


async def test_scripted_falls_back_to_hint_level_zero_of_same_phase():
    """힌트를 쓴 뒤 수다(chat, hint_level 3)도 대본 hint_level 0 줄로 답한다."""
    assert (await ScriptedAdapter(LINES).reply(_req(phase="chat", hint_level=3))).text == "c-1"


# ---------- live(Anthropic) 어댑터: 네트워크 없이 가짜 클라이언트로 ----------


class _Block:
    def __init__(self, type_: str, text: str = "") -> None:
        self.type = type_
        self.text = text


class _Resp:
    def __init__(
        self, blocks: list[_Block], stop_reason: str = "end_turn", usage: object = None
    ) -> None:
        self.content = blocks
        self.stop_reason = stop_reason
        self.usage = usage


class _FakeMessages:
    def __init__(self, resp: _Resp | Exception) -> None:
        self.resp = resp
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.resp, Exception):
            raise self.resp
        return self.resp


class _FakeClient:
    def __init__(self, resp: _Resp | Exception) -> None:
        self.messages = _FakeMessages(resp)


def _live(resp: _Resp | Exception) -> tuple[AnthropicAdapter, _FakeClient]:
    fake = _FakeClient(resp)
    return AnthropicAdapter(api_key="test-key", model="claude-haiku-5-5", client=fake), fake


async def test_live_sends_one_non_streaming_call_and_joins_text_blocks():
    adapter, fake = _live(_Resp([_Block("thinking"), _Block("text", "안녕"), _Block("text", "!")]))
    req = ReplyRequest(
        scenario="day3-EBSP",
        phase="study",
        hint_level=0,
        step=1,
        system="시스템",
        turns=[
            {"role": "child", "text": "a"},
            {"role": "mentor", "text": "b"},
            {"role": "child", "text": "c"},
        ],
    )
    out = await adapter.reply(req)
    assert out.text == "안녕!" and out.source == "live"
    assert len(fake.messages.calls) == 1
    call = fake.messages.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["system"] == "시스템"
    assert "stream" not in call
    assert call["messages"] == [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
    ]


def test_to_messages_handles_content_key_merges_and_ends_with_user():
    # 초안은 {"role": "user", "content": ...} 모양을 쓴다
    assert to_messages([{"role": "user", "content": "메모"}]) == [
        {"role": "user", "content": "메모"}
    ]
    # 연속 같은 역할은 합치고, 첫·끝은 user여야 한다(프리필 금지)
    msgs = to_messages(
        [
            {"role": "mentor", "text": "m"},
            {"role": "child", "text": "a"},
            {"role": "child", "text": "b"},
            {"role": "mentor", "text": "m2"},
        ]
    )
    assert msgs[0]["role"] == "user" and msgs[-1]["role"] == "user"
    assert {"role": "user", "content": "a\nb"} in msgs
    assert all(x["role"] != y["role"] for x, y in zip(msgs, msgs[1:], strict=False))
    assert to_messages([])[0]["role"] == "user"


@pytest.mark.parametrize(
    "resp",
    [
        RuntimeError("provider down"),
        _Resp([_Block("text", "")]),
        _Resp([_Block("text", "거절")], stop_reason="refusal"),
    ],
)
async def test_live_failure_or_empty_falls_back_to_scripted(resp):
    adapter, _ = _live(resp)
    assert await FallbackAdapter(adapter, ScriptedAdapter(LINES)).reply(_req()) == Reply(
        "s0-1", "scripted"
    )


async def test_live_timeout_falls_back_to_scripted():
    class _SlowMessages:
        async def create(self, **kwargs):
            await asyncio.sleep(1)

    class _SlowClient:
        messages = _SlowMessages()

    adapter = AnthropicAdapter(api_key="k", client=_SlowClient())
    fb = FallbackAdapter(adapter, ScriptedAdapter(LINES), timeout_s=0.05)
    assert await fb.reply(_req()) == Reply("s0-1", "scripted")


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


async def test_live_reply_carries_source_and_token_counts():
    adapter, _ = _live(_Resp([_Block("text", "합성 응답")], usage=_Usage(120, 30)))
    out = await FallbackAdapter(adapter, ScriptedAdapter(LINES)).reply(_req())
    assert out == Reply("합성 응답", "live", in_tokens=120, out_tokens=30)


async def test_live_reply_without_usage_has_no_token_counts():
    adapter, _ = _live(_Resp([_Block("text", "합성 응답")]))
    out = await adapter.reply(_req())
    assert out.source == "live" and out.in_tokens is None and out.out_tokens is None


async def test_fallback_to_fixed_when_script_has_no_key():
    adapter = FallbackAdapter(_Boom(), ScriptedAdapter(LINES))
    assert await adapter.reply(_req(phase="bridge")) == Reply(FIXED_REPLY, "fixed")


def test_live_client_is_created_lazily():
    # 클라이언트를 안 주면 생성자에서 만들지 않는다(첫 호출 때 만든다)
    assert AnthropicAdapter(api_key="k")._client is None


# ---------- 팩토리: LLM_MODE·키에 따라 ----------


@pytest.mark.parametrize(
    ("mode", "key"), [("scripted", None), ("scripted", "k"), ("live", None), ("live", "")]
)
def test_build_adapter_is_scripted_without_live_and_key(monkeypatch, mode, key):
    monkeypatch.setenv("LLM_MODE", mode)
    if key is None:
        monkeypatch.delenv("LLM_API_KEY", raising=False)
    else:
        monkeypatch.setenv("LLM_API_KEY", key)
    scripted = ScriptedAdapter(LINES)
    assert build_adapter(scripted) is scripted


@pytest.mark.parametrize(("env_model", "model"), [(None, "claude-haiku-5-5"), ("m-x", "m-x")])
def test_build_adapter_wraps_live_with_fallback(monkeypatch, env_model, model):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_API_KEY", "k")
    if env_model is None:
        monkeypatch.delenv("LLM_MODEL", raising=False)
    else:
        monkeypatch.setenv("LLM_MODEL", env_model)
    adapter = build_adapter(ScriptedAdapter(LINES))
    assert isinstance(adapter, FallbackAdapter)
    assert isinstance(adapter._primary, AnthropicAdapter)
    assert adapter._primary.model == model
