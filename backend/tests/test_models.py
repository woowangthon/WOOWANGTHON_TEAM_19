"""명세 4.2 테이블 7개와 핵심 제약."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.models import Alert, Message, Misconception, Problem, Session, Student
from app.seed import load_seed
from tests.conftest import TODAY

EXPECTED_TABLES = {
    "students",
    "problems",
    "sessions",
    "messages",
    "misconceptions",
    "instructor_notes",
    "alerts",
}


# 계정·학원·씨앗 테이블 12개(명세 4.12, 11-12) — 학습 테이블 7개는 그대로
ORG_TABLES = {
    "accounts",
    "auth_tokens",
    "links",
    "academies",
    "academy_applications",
    "rooms",
    "room_people",
    "seed_ledger",
    "shop_items",
    "orders",
    "cosmetics_owned",
    "notices",
}


async def test_seven_tables_are_created(engine):
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    # session_problems: 한 세션 여러 문제(SESSION_PROBLEMS, 11-12). 기본 1이면 비어 있다
    # class_live·class_live_settings·class_posts: 강의실 수업 진행·공지/숙제(명세 4.12 5-4, 11-13)
    assert names == EXPECTED_TABLES | ORG_TABLES | {
        "session_problems",
        "class_live",
        "class_live_settings",
        "class_posts",
    }


async def test_student_has_no_real_name_column(engine):
    async with engine.connect() as conn:
        cols = await conn.run_sync(
            lambda c: {x["name"] for x in inspect(c).get_columns("students")}
        )
    assert not {"name", "real_name", "full_name"} & cols


async def test_one_session_per_student_per_day(db_session, make_student):
    student = make_student()
    db_session.add(student)
    await db_session.flush()
    db_session.add(Session(student_id=student.id, date=TODAY))
    await db_session.flush()
    db_session.add(Session(student_id=student.id, date=TODAY))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_one_misconception_per_student_per_tag(db_session, make_student):
    student = make_student()
    db_session.add(student)
    await db_session.flush()
    db_session.add(Misconception(student_id=student.id, tag="frac-div-nat", first_wrong_date=TODAY))
    await db_session.flush()
    db_session.add(Misconception(student_id=student.id, tag="frac-div-nat", first_wrong_date=TODAY))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_new_session_defaults_to_study_hint_zero(db_session, make_student):
    student = make_student()
    db_session.add(student)
    await db_session.flush()
    s = Session(student_id=student.id, date=TODAY)
    db_session.add(s)
    await db_session.flush()
    assert (s.state, s.hint_level, s.streak_applied, s.end_reason) == ("study", 0, False, None)


async def test_message_expires_72h_after_creation(db_session, make_student):
    student = make_student()
    db_session.add(student)
    await db_session.flush()
    s = Session(student_id=student.id, date=TODAY)
    db_session.add(s)
    await db_session.flush()
    now = datetime(2026, 11, 10, 6, 0, tzinfo=UTC)
    m = Message.new(session_id=s.id, seq=1, role="child", text_redacted="3/8", now=now)
    assert m.expires_at == now + timedelta(hours=72)


async def test_alert_expires_90d_after_creation():
    now = datetime(2026, 11, 10, 6, 0, tzinfo=UTC)
    a = Alert.new(session_id="s", student_id="st", trigger="R1", excerpt="x" * 400, now=now)
    assert a.expires_at == now + timedelta(days=90)
    assert len(a.excerpt) == 300


async def test_seed_loads_twenty_problems_once(db_session):
    assert await load_seed(db_session) == 20
    assert await load_seed(db_session) == 0  # 두 번 불러도 중복 없음
    rows = (await db_session.scalars(select(Problem))).all()
    assert len(rows) == 20
    p = next(r for r in rows if r.id == "frac-div-nat-01")
    assert p.answer["value"] == "3/8"
    assert p.hint1 and p.hint2 and p.solution


async def test_student_style_is_style_code_not_animal(db_session, make_student):
    student = make_student()
    db_session.add(student)
    await db_session.flush()
    got = await db_session.get(Student, student.id)
    assert got is not None and got.style in {"EBSP", "EQLC", "DQSC"}
