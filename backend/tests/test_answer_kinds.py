"""숫자만 받던 답 칸을 넓힌다: 큰 정수(number) · 객관식(choice) · 낱말(text).

문제·보기는 전부 합성이다. 시드 20문제(분수)의 동작은 바뀌지 않아야 한다.
"""

import pytest

from app.judge import contains_answer, judge

CHOICE = {"kind": "choice", "value": "②", "accepted": ["②", "2", "2번", "관형사"]}
TEXT = {"kind": "text", "value": "who", "accepted": ["who", "that"]}
BIG = {"kind": "value", "value": "70000", "accepted": ["70000"]}


@pytest.mark.parametrize("text", ["②", "2", "2번", "2 번", "관형사", " ② ", "②번"])
def test_choice_correct_forms(text):
    assert judge(text, CHOICE) == "correct"


@pytest.mark.parametrize("text", ["①", "3", "4번", "④"])
def test_choice_other_option_is_wrong(text):
    assert judge(text, CHOICE) == "wrong"


@pytest.mark.parametrize("text", ["모르겠어", "5", "힌트 줘"])
def test_choice_unreadable_is_not_judged(text):
    """보기 번호가 아닌 말은 판정하지 않는다(서버 오류 500이던 자리)."""
    assert judge(text, CHOICE) is None


@pytest.mark.parametrize("text", ["who", "Who", "WHO.", " that ", "That!"])
def test_text_accepted_case_insensitive(text):
    assert judge(text, TEXT) == "correct"


@pytest.mark.parametrize("text", ["which", "whom"])
def test_text_single_word_wrong(text):
    assert judge(text, TEXT) == "wrong"


KTEXT = {"kind": "text", "value": "부사", "accepted": ["부사"]}


@pytest.mark.parametrize(
    "text", ["부사요", "부사예요", "부사이에요", "부사입니다", "부사야", "부사이야", "부사!"]
)
def test_korean_word_with_polite_ending(text):
    """아이가 말끝을 붙여도(「부사요」) 정답 낱말이면 정답."""
    assert judge(text, KTEXT) == "correct"


def test_korean_ending_does_not_rescue_wrong_word():
    assert judge("명사요", KTEXT) == "wrong"


def test_text_sentence_not_judged():
    assert judge("잘 모르겠는데 힌트 줄래", TEXT) is None


def test_big_integer_still_value():
    assert judge("70000", BIG) == "correct"
    assert judge("70", BIG) == "wrong"


def test_choice_leak_symbol_even_if_in_problem_text():
    problem = "품사는? ① 형용사 ② 관형사 ③ 부사 ④ 명사"
    assert contains_answer("정답은 ②야", CHOICE, problem)
    assert contains_answer("2번이 맞아", CHOICE, problem)
    assert not contains_answer("보기를 하나씩 문장에 넣어 봐", CHOICE, problem)


def test_text_leak_case_insensitive():
    assert contains_answer("Who를 넣으면 돼", TEXT, "The girl ___ is my cousin.")
    assert not contains_answer("사람을 꾸미는지 보자", TEXT, "The girl ___ is my cousin.")


# --- API: 문제 보기에 답 종류·보기를 싣고, 답을 글자로 받는다 ----------------------------

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.actors import DEMO_CHILD_ID  # noqa: E402
from app.api import get_llm  # noqa: E402
from app.db import get_db  # noqa: E402
from app.llm import ScriptedAdapter  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Problem  # noqa: E402
from app.seed import load_seed  # noqa: E402
from app.timeutil import get_now  # noqa: E402
from tests.test_compat import BASE, CHILD, SEOUL_TODAY, Clock  # noqa: E402

_STD = {"code": "[0합성-00]", "curriculum": "2022", "unit": "합성"}
SYNTH = {
    "t-big-01": dict(
        tag="t-big",
        grade=4,
        expr="7*10000",
        answer=BIG,
        text="58274163에서 숫자 7이 나타내는 값은? (쉼표 없이 숫자만 써 주세요)",
    ),
    "t-choice-01": dict(
        tag="t-choice",
        grade=8,
        expr="1",
        answer=CHOICE,
        text="'새'의 품사는 무엇일까요?\n① 형용사\n② 관형사\n③ 부사\n④ 명사\n(번호를 하나 골라 써 주세요)",
    ),
    "t-text-01": dict(
        tag="t-text",
        grade=10,
        expr="1",
        answer=TEXT,
        text="빈칸에 알맞은 관계사 한 단어를 쓰세요.\nThe girl ___ is my cousin.",
    ),
}


def _client_for(pid: str):
    @pytest_asyncio.fixture
    async def _fixture(db_session, make_student):
        await load_seed(db_session)
        for k, v in SYNTH.items():
            db_session.add(
                Problem(
                    id=k, standard=_STD, hint1="h1", hint2="h2", solution="s", forbidden=[], **v
                )
            )
        db_session.add(
            make_student(id=DEMO_CHILD_ID, today_task_problem_id=pid, today_task_date=SEOUL_TODAY)
        )
        await db_session.flush()
        app = create_app()
        clock = Clock()

        async def _db():
            yield db_session

        scripted = ScriptedAdapter.from_file()
        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_now] = lambda: clock.now
        app.dependency_overrides[get_llm] = lambda: scripted
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    return _fixture


big_client = _client_for("t-big-01")
choice_client = _client_for("t-choice-01")
text_client = _client_for("t-text-01")
seed_client = _client_for("frac-div-nat-01")


async def _start(c) -> tuple[str, dict]:
    sid = (await c.post(BASE + "/sessions", json={"difficulty": "중급"}, headers=CHILD)).json()[
        "id"
    ]
    p = (await c.get(BASE + f"/sessions/{sid}/problem", headers=CHILD)).json()
    return sid, p


async def _answer(c, sid, pid, **body):
    r = await c.post(
        BASE + f"/sessions/{sid}/answer", json={"problemId": pid, **body}, headers=CHILD
    )
    return r


async def test_seed_problem_stays_fraction(seed_client):
    _, p = await _start(seed_client)
    assert p["answerKind"] == "fraction" and p["choices"] is None and p["answerLang"] is None


async def test_big_number_problem(big_client):
    sid, p = await _start(big_client)
    assert p["answerKind"] == "number" and p["choices"] is None
    r = (await _answer(big_client, sid, p["id"], answer="70000")).json()
    assert r["correct"] is True


async def test_choice_problem_shows_buttons_and_judges(choice_client):
    sid, p = await _start(choice_client)
    assert p["answerKind"] == "choice"
    assert p["choices"] == ["형용사", "관형사", "부사", "명사"]
    assert "①" not in p["text"] and p["text"].startswith("'새'의 품사")
    assert "answer" not in p
    w = await _answer(choice_client, sid, p["id"], answer="①")
    assert w.status_code == 200 and w.json()["correct"] is False
    ok = (await _answer(choice_client, sid, p["id"], answer="②")).json()
    assert ok["correct"] is True


async def test_text_problem_accepts_word(text_client):
    sid, p = await _start(text_client)
    assert p["answerKind"] == "text" and p["choices"] is None
    assert p["answerLang"] == "en"  # 영어 낱말 답 → 화면이 「영어로 써 줘」
    ok = (await _answer(text_client, sid, p["id"], answer="Who")).json()
    assert ok["correct"] is True


async def test_answer_needs_fraction_or_text(seed_client):
    sid, p = await _start(seed_client)
    r = await _answer(seed_client, sid, p["id"])
    assert r.status_code == 422
