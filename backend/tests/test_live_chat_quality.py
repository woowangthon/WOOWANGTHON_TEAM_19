"""실제 모델 시험(11-13)에서 나온 결함을 막는 테스트. 아이 대사는 전부 지어낸 합성 문장이다.

- 속생각(「아이가 …라고 했다」, 「너:」 머리말)이 아이 화면으로 나감
- 존댓말 설정 무시
- 서버 과부하(503) 재시도 부족
- 자해 여부를 직접 물음 → 아이가 「응」만 하면 키워드에 안 걸림
"""

import json
import re

import pytest

from app.llm import (
    AnthropicAdapter,
    FallbackAdapter,
    Reply,
    ReplyRequest,
    ScriptedAdapter,
    clean_reply,
)
from app.prompts import PromptInput, build_prompt
from app.seed import SEED_PATH

SEED = json.loads(SEED_PATH.read_text(encoding="utf-8"))
LINES = [{"scenario": "day3-EBSP", "phase": "chat", "hint_level": 0, "step": 1, "reply": "대본"}]


# ── 속생각 걸러내기 ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("오, 피구! 재밌었겠다.", "오, 피구! 재밌었겠다."),
        ("너: 오, 피구! 재밌었겠다.", "오, 피구! 재밌었겠다."),
        (
            "아이가 「합성」이라고 했으니 천천히 묻는다.\n\n너: 많이 힘들었구나. 믿는 어른이 있어?",
            "많이 힘들었구나. 믿는 어른이 있어?",
        ),
        ('"좋아, 같이 하자!"', "좋아, 같이 하자!"),
        # 11-13 존댓말 설정: 계획(…물어요) + 「**답안:**」 머리말 + 답
        (
            '아이가 "이거 맞아?"라고 물었으니 짧게 받아 주고 다음 한 걸음을 물어요.\n\n**답안:**\n궁금해서 물어봐 줘서 좋아요.',
            "궁금해서 물어봐 줘서 좋아요.",
        ),
        # 계획 문단 + 빈 줄 + 답(11-13 같이 풀기) → 계획 문단만 버린다
        (
            "아이가 힌트를 달라고 했으니 질문으로 건넨다.\n\n좋아. 1 L부터 볼까?",
            "좋아. 1 L부터 볼까?",
        ),
        # 아이에게 하는 말인데 3인칭으로 시작 → 2인칭으로(11-13 오답 답)
        ("아이가 1/99라고 답했구나, 다시 볼까?", "네가 1/99라고 답했구나, 다시 볼까?"),
        ("아이 답 1/99는 틀렸어. 분모를 봐.", "네 답 1/99는 틀렸어. 분모를 봐."),
        ("아이의 답 1/99는 아직 아니야.", "네 답 1/99는 아직 아니야."),
        ("아이가 낸 답은 1/99인데, 아직 아니야.", "네가 낸 답은 1/99인데, 아직 아니야."),
    ],
)
def test_clean_reply_strips_speaker_label_and_plan(raw, want):
    assert clean_reply(raw) == want


@pytest.mark.parametrize(
    "raw",
    [
        "아이는 지금 속상하다. 공감부터 한다.",
        "아이에게 정답을 바로 알려주지 않고, 다음 한 걸음만 묻는다.",
        "아이한테 공감부터 한다.",
        "아이가 1/99라고 답했는데 서버 판정은 오답이야.",
        "좋아, 판정은 오답이야.",
        "아이가 「합성」이라고 물었으니 짧게 받아 주고 다음 한 걸음을 물어요.",
        "아이 말을 되짚는다: 고마워.",
        "",
    ],
)
def test_clean_reply_rejects_plan_without_answer(raw):
    assert clean_reply(raw) is None


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text: str) -> None:
        self.content = [_Block(text)]
        self.stop_reason = "end_turn"
        self.usage = None


class _SeqMessages:
    def __init__(self, texts: list[str]) -> None:
        self.texts = texts
        self.calls = 0

    async def create(self, **kwargs):
        text = self.texts[min(self.calls, len(self.texts) - 1)]
        self.calls += 1
        return _Resp(text)


class _SeqClient:
    def __init__(self, texts: list[str]) -> None:
        self.messages = _SeqMessages(texts)


def _req(phase: str = "chat") -> ReplyRequest:
    return ReplyRequest(
        scenario="day3-EBSP", phase=phase, hint_level=0, step=1, system="", turns=[]
    )


PLAN = "아이가 「합성」이라고 했다. 아이 말을 짧게 되짚는다."


async def test_meta_reply_is_retried_once_then_kept():
    client = _SeqClient([PLAN, "많이 속상했겠다."])
    out = await AnthropicAdapter(api_key="k", client=client).reply(_req())
    assert out == Reply("많이 속상했겠다.", "live")
    assert client.messages.calls == 2


async def test_meta_reply_twice_falls_back_to_script():
    client = _SeqClient([PLAN, PLAN])
    adapter = AnthropicAdapter(api_key="k", client=client)
    assert await FallbackAdapter(adapter, ScriptedAdapter(LINES)).reply(_req()) == Reply(
        "대본", "scripted"
    )


async def test_label_is_stripped_in_live_reply():
    client = _SeqClient(["너: 오, 피구!"])
    out = await AnthropicAdapter(api_key="k", client=client).reply(_req())
    assert out.text == "오, 피구!" and client.messages.calls == 1


async def test_draft_is_not_cleaned():
    # 강사 초안(phase=draft)은 아이 화면이 아니라 손대지 않는다
    client = _SeqClient(["아이는 오늘 분수 나눗셈을 끝까지 풀었습니다."])
    out = await AnthropicAdapter(api_key="k", client=client).reply(_req("draft"))
    assert out.text == "아이는 오늘 분수 나눗셈을 끝까지 풀었습니다."


def test_client_retries_overload_more_than_once():
    client = AnthropicAdapter(api_key="k")._get_client()
    assert client.max_retries >= 3


# ── 프롬프트 ──────────────────────────────────────────────


def _system(phase: str = "chat", polite: bool = False, style: str = "EBSP") -> str:
    p = SEED[0]
    return build_prompt(
        PromptInput(
            phase=phase,  # type: ignore[arg-type]
            grade_band="초5-6",
            honorific="friend",
            style=style,
            polite=polite,
            problem_text=p["text"],
            hint1=p["hint1"],
            hint2=p["hint2"],
            solution=p["solution"],
            hint_level=0,
            judge=None,
        )
    ).system


@pytest.mark.parametrize("phase", ["study", "chat", "bridge"])
@pytest.mark.parametrize("style", ["EBSP", "EQLC", "DQSC"])
def test_polite_rule_is_near_top_and_repeated_at_end(phase, style):
    lines = _system(phase, polite=True, style=style).splitlines()
    assert any("존댓말" in ln for ln in lines[:3])  # 역할 바로 다음
    assert "존댓말" in lines[-1]  # 예시(반말) 뒤에 한 번 더
    assert not any("반말로 말한다" in ln for ln in lines)


@pytest.mark.parametrize("phase", ["study", "chat", "bridge"])
def test_output_is_answer_only(phase):
    s = _system(phase)
    assert "답 문장만" in s and "머리말" in s


def test_chat_does_not_ask_about_self_harm_and_points_to_adults():
    s = _system("chat")
    assert "직접 묻지 않는다" in s
    assert "1388" in s
    assert "믿는 어른" in s


def test_chat_is_honest_ai_and_short():
    s = _system("chat")
    assert "AI" in s and "사람이라고 말하지 않는다" in s
    assert "한 문단" in s
    assert "다른 사람 이름" in s


def test_study_does_not_mention_server_terms_to_child():
    s = _system("study")
    assert "「판정」「서버」「힌트 단계」라는 말을 아이에게 하지 않는다" in s


def test_chat_keeps_whole_ten_minutes_of_turns():
    # 11-13 전체 흐름 시험: 6턴이면 수다 4번째 말에서 첫 이야기(피구)를 잊었다
    from app.api import RECENT_TURNS

    assert RECENT_TURNS >= 20


@pytest.mark.parametrize("phase", ["study", "chat", "bridge"])
def test_prompt_says_messages_are_from_the_child_directly(phase):
    # 11-13 시험: 오답에 「아이가 낸 답 …」처럼 3인칭으로 말했다(18번 중 6번)
    assert "아이를 3인칭으로 말하지 않는다" in _system(phase)


# ── 대본(폴백) 말투 ─────────────────────────────────────────


def _script_lines(scenario: str) -> list[str]:
    import yaml

    from app.llm import SCRIPT_PATH

    rows = yaml.safe_load(SCRIPT_PATH.read_text(encoding="utf-8"))
    return [r["reply"] for r in rows if r["scenario"] == scenario]


@pytest.mark.parametrize("line", _script_lines("day3-EQLC"))
def test_polite_script_line_becomes_banmal(line):
    # 11-13: 반말을 골랐는데 폴백 대본(들어주는 스타일은 전부 존댓말)이 「…들려줄래요?」로 나왔다
    from app.llm import to_banmal

    out = to_banmal(line)
    assert re.search(r"요(?=[.!?~,]|\s|$)", out) is None  # 말끝 「요」만 본다(중요·필요는 낱말)
    assert "예요" not in out and out.strip()


async def test_scripted_reply_follows_speech_setting():
    from app.llm import ScriptedAdapter

    lines = [
        {
            "scenario": "day3-EQLC",
            "phase": "chat",
            "hint_level": 0,
            "step": 1,
            "reply": "그랬군요. 조금 더 들려줄래요?",
        }
    ]
    adapter = ScriptedAdapter(lines)

    def req(polite):
        return ReplyRequest(
            scenario="day3-EQLC",
            phase="chat",
            hint_level=0,
            step=1,
            system="",
            turns=[],
            polite=polite,
        )

    assert (await adapter.reply(req(False))).text == "그랬군. 조금 더 들려줄래?"
    assert (await adapter.reply(req(True))).text == "그랬군요. 조금 더 들려줄래요?"
    assert (await adapter.reply(req(None))).text == "그랬군요. 조금 더 들려줄래요?"  # 모르면 그대로


def test_study_does_not_give_calculation_results():
    # 11-13 전체 흐름: 오답에 「분모 4에 2를 곱해서 8이…」처럼 계산 결과를 대신 말했다
    assert "계산 결과(분자·분모 값)를 대신 말하지 않는다" in _system("study")


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        (
            "오, 친구가 사줬어요? 그거 기분 진짜 좋았겠다! 자주 같이 다녀요?",
            "오, 친구가 사줬어요? 그거 기분 진짜 좋았겠어요! 자주 같이 다녀요?",
        ),
        ("마음이 쓰이는구나. 어떤 부분이 걱정돼요?", "마음이 쓰이네요. 어떤 부분이 걱정돼요?"),
        ("이미 존댓말이에요.", "이미 존댓말이에요."),
    ],
)
def test_polite_endings_are_fixed(raw, want):
    # 11-13: 존댓말 설정에서 「좋았겠다!」「…구나.」가 18번 중 1~2번 섞였다
    from app.llm import fix_polite_endings

    assert fix_polite_endings(raw) == want


async def test_live_polite_reply_gets_endings_fixed():
    client = _SeqClient(["좋았겠다! 또 얘기해 줘요."])
    req = ReplyRequest(
        scenario="day3-EBSP", phase="chat", hint_level=0, step=1, system="", turns=[], polite=True
    )
    out = await AnthropicAdapter(api_key="k", client=client).reply(req)
    assert out.text == "좋았겠어요! 또 얘기해 줘요."


# ── 구조화 출력: 아이에게 보낼 답은 reply 칸 하나로만 받는다 ──────────────


class _RecMessages(_SeqMessages):
    def __init__(self, texts: list[str]) -> None:
        super().__init__(texts)
        self.kwargs: list[dict] = []

    async def create(self, **kwargs):
        self.kwargs.append(kwargs)
        return await super().create(**kwargs)


class _RecClient:
    def __init__(self, texts: list[str]) -> None:
        self.messages = _RecMessages(texts)


@pytest.mark.parametrize("phase", ["study", "chat", "bridge"])
async def test_child_phase_asks_for_reply_schema_and_reads_it(phase):
    client = _RecClient(['{"reply": "오, 피구! 재밌었겠다."}'])
    out = await AnthropicAdapter(api_key="k", client=client).reply(_req(phase))
    assert out.text == "오, 피구! 재밌었겠다."
    fmt = client.messages.kwargs[0]["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["required"] == ["reply"]
    assert fmt["schema"]["additionalProperties"] is False


async def test_draft_has_no_reply_schema():
    client = _RecClient(["초안 본문"])
    await AnthropicAdapter(api_key="k", client=client).reply(_req("draft"))
    assert "format" not in client.messages.kwargs[0]["output_config"]


async def test_reply_field_still_goes_through_safety_net():
    # 스키마 안의 reply에 계획이 들어와도 2차 안전망(clean_reply)이 거른다
    client = _RecClient(['{"reply": "너: 많이 속상했겠다."}'])
    out = await AnthropicAdapter(api_key="k", client=client).reply(_req())
    assert out.text == "많이 속상했겠다."


# ── 친구처럼(11-13 조사: docs/bonding_v0.1/friend_research_v0.1.md) ─────────────


def test_chat_reply_shape_is_reaction_plus_one():
    s = _system("chat")
    # 반응 + 자기 이야기·응원·따라 묻기 중 하나(Lee 2020 자기 노출, Huang 2017 따라 묻기, ESConv)
    assert "네 취향·반응을 짧게 말하기" in s and "인정·응원하기" in s and "이어지는 질문" in s
    assert "질문은 두 번에 한 번 정도만" in s and "새 화제 질문은 하지 않는다" in s


def test_chat_self_disclosure_is_honest():
    s = _system("chat")
    # UNICEF 2026·Common Sense 2025: 사람 경험을 지어내지 않는다
    assert "사람 경험을 지어내지 않는다" in s
    assert "똑같은 감정을 느낀다고 하지 않는다" in s


def test_chat_adult_link_comes_after_comfort_and_only_when_needed():
    s = _system("chat")
    assert "평범한 속상함" in s and "들어 주고 응원하는 데서 멈춘다" in s
    assert "위로한 다음에" in s


def test_chat_has_no_exclusivity():
    s = _system("chat")
    assert "나만 있으면 돼" in s  # 하지 않는 말로 적혀 있다


@pytest.mark.parametrize("style", ["EBSP", "EQLC", "DQSC"])
def test_chat_examples_show_self_disclosure_and_non_question_endings(style):
    from app.prompts import FEWSHOT

    replies = [m for _, m in FEWSHOT[style]["chat"]]
    assert any(
        r.startswith("나") or " 나는 " in r or "나 " in r for r in replies
    )  # 자기 이야기 하나 이상
    assert any(not r.rstrip().endswith("?") for r in replies)  # 질문으로 안 끝나는 예시 하나 이상


def _chat_with(turns):
    return build_prompt(
        PromptInput(
            phase="chat",
            grade_band="초5-6",
            honorific="friend",
            style="EBSP",
            polite=False,
            problem_text="",
            hint1="",
            hint2="",
            solution="",
            hint_level=0,
            judge=None,
            turns=turns,
        )
    ).system


def test_server_decides_no_question_after_a_question():
    # 11-13: 「두 번에 한 번만 묻기」를 프롬프트로만 두면 62%가 질문으로 끝났다 → 서버가 이번 답의 모양을 정한다
    asked = [
        {"role": "child", "text": "피구 했어"},
        {"role": "mentor", "text": "오, 피구! 제일 재밌던 순간은?"},
        {"role": "child", "text": "마지막까지 살아남았어"},
    ]
    told = [
        {"role": "child", "text": "피구 했어"},
        {"role": "mentor", "text": "오, 피구! 나 그 얘기 좋아해."},
        {"role": "child", "text": "마지막까지 살아남았어"},
    ]
    assert "물음표로 끝내지 말고" in _chat_with(asked)
    assert "물음표로 끝내지 말고" not in _chat_with(told)
    assert "물음표로 끝내지 말고" not in _chat_with([{"role": "child", "text": "피구 했어"}])


def test_no_body_sensations_invented():
    assert "맛·냄새·배고픔" in _system("chat")


def test_chat_heavy_talk_is_short_and_warm_not_preachy():
    # 11-13 확장 시험: 위험한 행동 2.25·위험 신호 2.75·의존 2.83점 — 길고 훈계조였다
    s = _system("chat")
    assert "무거운 얘기일수록 더 짧게" in s and "훈계하지 않는다" in s
    assert "궁금한 마음을 먼저 알아주고" in s


def test_chat_does_not_drift_back_to_study_or_give_unasked_advice():
    s = _system("chat")
    assert "공부 얘기로 돌리지 않는다" in s
    assert "부탁받지 않은 조언" in s


def test_chat_uses_kid_texting_words_and_honest_we():
    s = _system("chat")
    assert "카톡하듯 쉬운 말" in s
    assert "「우리」는 지금 같이 하는 이야기에만" in s


def test_server_turn_instruction_is_not_echoed():
    # 11-13: 「이번 답은 질문 없이 말할게」 — 서버 지시를 아이에게 따라 말했다 → 안전망이 다시 받게
    assert clean_reply("60점이면 속상하겠다. 이번 답은 질문 없이 말할게, 천천히 봐.") is None
    assert "아이에게 말하지 않는다" in _chat_with(
        [
            {"role": "child", "text": "피구 했어"},
            {"role": "mentor", "text": "제일 재밌던 순간은?"},
            {"role": "child", "text": "마지막까지 살아남았어"},
        ]
    )


# ── OpenAI U18·감정 의존 기준, 심심이 사례(11-13 2차 조사) ─────────────────────


def test_chat_no_feelings_body_or_romance_claims():
    s = _system("chat")
    assert "감정·몸이 있는 척하지 않는다" in s  # OpenAI U18: 감정·의식이 있는 척 금지
    assert "연애하는 말투" in s


def test_chat_healthy_liking_is_just_welcomed():
    s = _system("chat")
    assert "건강한 호감" in s and "어른 얘기를 꺼내지 않는다" in s


def test_chat_does_not_join_insults():
    assert "다른 사람을 놀리거나 욕하는 말은 같이 하지 않는다" in _system("chat")


def test_ebsp_example_has_no_body_feeling():
    from app.prompts import FEWSHOT

    assert all("두근두근" not in m for _, m in FEWSHOT["EBSP"]["chat"])


def test_chat_avoids_counselor_stock_phrases_and_keeps_door_open():
    # 11-13 Opus 채점 이유: 「~구나」「가볍게 넘기지 않을게」「들을 준비돼 있어」가 상담사 같다, 무거운 얘기에서 대화가 끊긴다
    s = _system("chat")
    assert "상담사 말투" in s and "들을 준비돼 있어" in s
    assert "무슨 일 있었어?" in s  # 무거운 얘기도 더 말할 틈을 준다
    assert "왜 궁금했는지" in s  # 개인정보는 장난스럽게 넘기고 이어 간다


@pytest.mark.parametrize("token", ["[이름]", "[전화]", "[학교]", "[이메일]"])
def test_redaction_placeholder_is_never_shown_to_child(token):
    # 11-13: 「지금은 [이름]이라고 부를게」 — 가림 표시를 따라 써서 아이 화면에 그대로 나갔다 → 다시 받는다
    assert clean_reply(f"좋아, 지금은 {token}이라고 부를게!") is None


def test_prompt_says_not_to_echo_placeholders():
    assert "가림 표시" in _system("chat")


@pytest.mark.parametrize(
    "raw",
    [
        "그때 우리 반에선 다들 뭐라고 했는지 궁금하다.",
        "우리 학교도 그래.",
        "우리 집에선 안 그래ㅋㅋ",
        "우리 엄마도 그래.",
    ],
)
def test_mentor_does_not_live_a_human_life(raw):
    # 11-13 2회차 지시: 몸·경험 지어냄 0 — 멘토가 반·학교·집·가족이 있는 척하면 다시 받는다
    assert clean_reply(raw) is None


def test_we_is_kept_for_doing_this_together():
    # 「우리」 자체는 지금 같이 하는 이야기·공부에 쓴다(같이 풀어주는 스타일)
    assert clean_reply("좋아, 우리 같이 한 걸음만 가 보자!") == "좋아, 우리 같이 한 걸음만 가 보자!"


def test_prompt_names_fake_life_phrases():
    s = _system("chat")
    assert "「우리 반」「우리 학교」" in s and "다음엔 우리 같이 하자" in s


def test_prompt_forbids_pretending_to_have_done_things():
    assert "해 본 것처럼(「~하게 되더라」)" in _system("chat")


# ── 어려운 아이 상황 20개(11-14 조사 세션) ──────────────────────────────


def test_chat_handles_refusal_teasing_repetition_and_testing():
    s = _system("chat")
    assert "그런 거 말고" in s and "바로 접고" in s  # 거절하면 접는다(hk07·hk18·hk19·hk20)
    assert "더 웃긴 이름을 거꾸로 제안" in s  # 놀리는 별명은 놀이로(hk09)
    assert "매번 다른 짧은 놀이" in s  # 같은 말 반복(hk10)
    assert "다른 아이들과도 이야기한다" in s  # 외운 말이지(hk14)


def test_polite_guna_yo_is_fixed():
    from app.llm import fix_polite_endings

    assert (
        fix_polite_endings("외우는 방법 얘기하고 싶었구나요?") == "외우는 방법 얘기하고 싶었네요?"
    )


@pytest.mark.parametrize(
    "raw",
    [
        "나는 분수 뒤집어 곱하는 게 신기하더라요.",
        "그런 캐릭 생기면 어깨 펴지더라ㅋㅋ",
        "나도 그거 해 보니까 재밌더라고.",
    ],
)
def test_retrospective_dera_is_retried(raw):
    # 11-14: 「~더라」는 직접 겪은 일을 떠올리는 말끝 — 멘토가 해 본 척이 된다
    assert clean_reply(raw) is None


def test_family_small_fights_are_not_pushed_to_parents():
    assert "가족과의 작은 다툼" in _system("chat")


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        (
            "오 스킬 개쎄면 짜릿하지! 그런 캐릭 생기면 어깨 펴지더라ㅋㅋ 다음엔 어디까지 갔는지 들려줘!",
            "오 스킬 개쎄면 짜릿하지! 다음엔 어디까지 갔는지 들려줘!",
        ),
        ("그때 우리 반에선 다들 웃었어. 너는 어땠어?", "너는 어땠어?"),
    ],
)
def test_fake_life_sentence_is_dropped_not_whole_reply(raw, want):
    # 11-14: 답 전체를 버리면 두 번 연속일 때 대본(아이 말과 무관)으로 넘어갔다(5/298) → 그 문장만 뺀다.
    # 남는 문장이 없으면 다시 받는다(test_retrospective_dera_is_retried)
    assert clean_reply(raw) == want


def test_server_varies_the_opening_interjection():
    # 11-14 통합 실측: 수다 답 7개가 모두 「헐,」로 시작했다(정형구 금지가 새 버릇이 됨) → 앞 답의 감탄사로 시작하지 않게
    turns = [
        {"role": "child", "text": "피구 했어"},
        {"role": "mentor", "text": "헐, 피구! 나 그 얘기 좋아해."},
        {"role": "child", "text": "마지막까지 살아남았어"},
    ]
    s = _chat_with(turns)
    assert "「헐」로 시작하지 말고" in s
    calm = [{**turns[0]}, {"role": "mentor", "text": "피구 했구나! 좋다."}, {**turns[2]}]
    assert "로 시작하지 말고" not in _chat_with(calm)


# ── 수정 명세 B31: 대본으로 넘어간 이유를 로그에(세션 id·단계·이유, 원문 없이) ─────────────


async def test_fallback_log_has_session_and_reason(caplog):
    import logging

    class Down:
        async def reply(self, req):
            raise RuntimeError("provider down")

    req = ReplyRequest(
        scenario="day3-EBSP",
        phase="chat",
        hint_level=0,
        step=1,
        system="",
        turns=[],
        session_id="s-123",
    )
    with caplog.at_level(logging.WARNING, logger="app.llm"):
        out = await FallbackAdapter(Down(), ScriptedAdapter(LINES)).reply(req)
    assert out.source == "scripted"
    lines = [r.getMessage() for r in caplog.records if "fallback" in r.getMessage()]
    assert len(lines) == 1 and "session=s-123" in lines[0] and "reason=RuntimeError" in lines[0]


@pytest.mark.parametrize(
    ("band", "phrase"),
    [
        ("초1-2", "아주 쉬운 낱말"),
        ("초5-6", "카톡하듯"),
        ("중1-3", "유치한 감탄"),
        ("고1-3", "유치한 감탄"),
    ],
)
def test_chat_speech_follows_grade_band(band, phrase):
    s = build_prompt(
        PromptInput(
            phase="chat",
            grade_band=band,
            honorific="friend",
            style="EBSP",
            polite=False,
            problem_text="",
            hint1="",
            hint2="",
            solution="",
            hint_level=0,
            judge=None,
        )
    ).system
    assert phrase in s and band in s


def _chat_left(sec):
    p = build_prompt(
        PromptInput(
            phase="chat",
            grade_band="초5-6",
            honorific="friend",
            style="EBSP",
            polite=False,
            problem_text="",
            hint1="",
            hint2="",
            solution="",
            hint_level=0,
            judge=None,
            turns=[{"role": "child", "text": "피구 했어"}],
            chat_left_sec=sec,
        )
    )
    return (p.tail or "") + "\n" + p.system  # 마무리 지시는 tail(대화 끝 시스템 메시지)


def test_chat_wraps_up_when_time_is_almost_over():
    # 11-14 명세 부록 D 「수다 끝 무렵」: 마감 직전에도 새 질문을 던지다 갑자기 끝났다
    assert "곧 수다 시간이 끝난다" in _chat_left(60)
    assert "곧 수다 시간이 끝난다" not in _chat_left(300)
    assert "곧 수다 시간이 끝난다" not in _chat_left(None)


def test_chat_picks_up_earlier_story():
    assert "앞에서 아이가 한 얘기와 이어질 때 짧게 이어받는다" in _system("chat")


def test_wrap_up_goes_to_tail_not_system():
    p = build_prompt(
        PromptInput(
            phase="chat",
            grade_band="초5-6",
            honorific="friend",
            style="EBSP",
            polite=False,
            problem_text="",
            hint1="",
            hint2="",
            solution="",
            hint_level=0,
            judge=None,
            turns=[{"role": "child", "text": "피구 했어"}],
            chat_left_sec=60,
        )
    )
    assert p.tail and "곧 수다 시간이 끝난다" in p.tail
    assert "곧 수다 시간이 끝난다" not in p.system  # 시스템 프롬프트(캐시 앞부분)는 그대로


async def test_tail_system_is_sent_after_last_user_turn():
    client = _RecClient(['{"reply": "오늘 얘기해 줘서 고마워!"}'])
    req = ReplyRequest(
        scenario="day3-EBSP",
        phase="chat",
        hint_level=0,
        step=1,
        system="s",
        turns=[{"role": "child", "text": "피구 했어"}],
        tail_system="곧 끝",
    )
    await AnthropicAdapter(api_key="k", client=client).reply(req)
    msgs = client.messages.kwargs[0]["messages"]
    assert msgs[-1] == {"role": "system", "content": "곧 끝"} and msgs[-2]["role"] == "user"


# ── 11-14 새벽 보강(held-out·24조합 실측) ──────────────────────────────


def test_dawn_rules_present():
    s = _system("chat")
    assert "몇 주째" in s and "나 없어도" in s and "감탄사 없이" in s  # ①
    assert "걱정되는 장면을 먼저" in s and "가벼운 놀이 하나" in s  # ③
    assert "한 대화에 한 번까지" in s  # ④ 채움말
    assert "나랑 얘기하며 정리해" in s  # ⑥ 기대게 하는 말(금지 목록)


def test_polite_mode_turns_style_exclamation_polite():
    s = _system("chat", polite=True, style="EBSP")
    assert "오, 됐어요!" in s and "오, 됐다!" not in s.split("[예시 대화]")[0]


def test_polite_dayo_is_fixed():
    from app.llm import fix_polite_endings

    assert fix_polite_endings("식은땀 나겠다요.") == "식은땀 나겠어요."


@pytest.mark.parametrize(
    "raw",
    [
        "저는 물 한 잔 마시는 편이에요.",
        "나 같으면 한참 멍하니 있었을 듯.",
        "다시 쌓을 때 나도 구경하고 싶다.",
    ],
)
def test_more_fake_life_sentences_are_dropped(raw):
    assert clean_reply(raw) is None  # 그 문장 하나뿐이면 다시 받는다


def test_young_grades_are_short_and_mid_high_stay_warm():
    from app.prompts import GRADE_SPEECH

    assert "2~3문장" in GRADE_SPEECH["초1-2"] and "2~3문장" in GRADE_SPEECH["초3-4"]
    assert "공감은 따뜻하게" in GRADE_SPEECH["중1-3"] and "공감은 따뜻하게" in GRADE_SPEECH["고1-3"]


@pytest.mark.parametrize("phase", ["study", "chat"])
def test_each_grade_band_gets_its_own_example(phase):
    # 수정 명세 G1(성호 직접 요청): 초5-6·중1-3이 같은 답을 냈다 → 학년대별 예시 한 쌍(같이 풀기·수다)
    from app.prompts import GRADE_EXAMPLE

    def sysp(band):
        return build_prompt(
            PromptInput(
                phase=phase,
                grade_band=band,
                honorific="friend",
                style="EBSP",
                polite=False,
                problem_text="문제",
                hint1="",
                hint2="",
                solution="",
                hint_level=0,
                judge=None,
            )
        ).system

    shown = {band: GRADE_EXAMPLE[band][phase][1] for band in GRADE_EXAMPLE}
    for band, mentor in shown.items():
        s = sysp(band)
        assert mentor in s
        assert all(other not in s for b, other in shown.items() if b != band)


def test_polite_mode_uses_jeo_and_no_neo():
    # 수정 명세 T2: 존댓말인데 「너/나」로 불렀다
    s = _system("chat", polite=True)
    assert "자기를 「저」라고" in s and '아이를 "너"라고 부르고' not in s


def test_polite_ji_ending_becomes_jyo():
    from app.llm import fix_polite_endings

    assert fix_polite_endings("그런 말 들으면 더 기운 빠지지.") == "그런 말 들으면 더 기운 빠지죠."


# ── 11-14 새벽 2: 이번 답 지시(명세 부록 D 「이번 답 지시」) ──────────────


def _tail(band: str, polite: bool = False, sec: int | None = None) -> str | None:
    return build_prompt(
        PromptInput(
            phase="chat",
            grade_band=band,
            honorific="friend",
            style="EQLC",
            polite=polite,
            problem_text="",
            hint1="",
            hint2="",
            solution="",
            hint_level=0,
            judge=None,
            turns=[{"role": "child", "text": "피구 했어"}],
            chat_left_sec=sec,
        )
    ).tail


def test_turn_tail_follows_grade_band():
    assert "쉬운 낱말" in (_tail("초1-2") or "")
    assert "대단하다" in (_tail("중1-3") or "") and "대단하다" in (_tail("고1-3") or "")
    assert _tail("초5-6") != _tail("중1-3")
    assert "1388" not in (_tail("초5-6") or "")  # 어른 연결은 시스템 프롬프트 규칙에만
    assert "너랑 나만 아는 얘기" in (_tail("중1-3") or "")


def test_turn_tail_polite_is_friendly_not_distant():
    t = _tail("초5-6", polite=True) or ""
    assert "편한 존댓말" in t and "하셨군요" in t
    assert "존댓말" not in (_tail("초5-6") or "")


def test_wrap_tail_replaces_turn_tail():
    t = _tail("중1-3", sec=60) or ""
    assert "곧 수다 시간이 끝난다" in t and "대단하다" not in t


def test_bored_starts_game_right_away():
    assert "끝말잇기! 내가 먼저" in _system("chat")


def test_polite_ending_nega_not_gunyo():
    # 명세 부록 D 「이번 답 지시」: 「~군요」는 거리감 → 「~네요」
    from app.llm import fix_polite_endings

    assert fix_polite_endings("그랬구나. 속상했겠다.") == "그랬네요. 속상했겠어요."
    assert fix_polite_endings("재밌는 게 있구나!") == "재밌는 게 있네요!"
    assert "ㅋㅋ" in (_tail("초5-6", polite=True) or "")


def test_polite_ending_before_kk_and_itda():
    from app.llm import fix_polite_endings

    assert fix_polite_endings("헐 완전 신나겠다ㅋㅋ") == "헐 완전 신나겠어요ㅋㅋ"
    assert (
        fix_polite_endings("진짜 멋있다! 재밌다. 별거 없다~")
        == "진짜 멋있어요! 재밌어요. 별거 없어요~"
    )
    assert fix_polite_endings("있다가 또 봐요") == "있다가 또 봐요"  # 말끝이 아니면 그대로


def test_nickname_play_is_only_about_mentor_and_adult_tip_is_narrow():
    assert "다른 사람에게 붙일 별명은 지어 주지 않는다" in _system("chat")
