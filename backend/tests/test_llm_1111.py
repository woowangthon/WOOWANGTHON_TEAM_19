"""11-11 점검 보강 B1: live 답이 max_tokens로 끊기면 대본으로. 실제 공급자는 부르지 않는다."""

from app.llm import AnthropicAdapter, FallbackAdapter, Reply, ReplyRequest, ScriptedAdapter

LINES = [{"scenario": "day3-EBSP", "phase": "study", "hint_level": 0, "step": 1, "reply": "대본"}]


class _Block:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _Resp:
    def __init__(self, text: str, stop_reason: str) -> None:
        self.content = [_Block(text)]
        self.stop_reason = stop_reason
        self.usage = None


class _Client:
    def __init__(self, resp: _Resp) -> None:
        resp_ = resp

        class _Messages:
            async def create(self, **kwargs):
                return resp_

        self.messages = _Messages()


def _req() -> ReplyRequest:
    return ReplyRequest(
        scenario="day3-EBSP", phase="study", hint_level=0, step=1, system="", turns=[]
    )


async def test_truncated_live_reply_falls_back_to_script():
    live = AnthropicAdapter(api_key="k", client=_Client(_Resp("끊긴 답인데 여기서", "max_tokens")))
    out = await FallbackAdapter(live, ScriptedAdapter(LINES)).reply(_req())
    assert out == Reply("대본", "scripted")


async def test_complete_live_reply_is_kept():
    live = AnthropicAdapter(api_key="k", client=_Client(_Resp("다 쓴 답", "end_turn")))
    out = await FallbackAdapter(live, ScriptedAdapter(LINES)).reply(_req())
    assert out.text == "다 쓴 답" and out.source == "live"
