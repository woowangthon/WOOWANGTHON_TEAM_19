"""명세 4.12-5 「학년 자동 올림」(11-14 UG1): 학년도(3월 1일 KST 시작)가 지나면 학년을 계산으로 올린다."""

from datetime import UTC, datetime

from app.timeutil import current_grade, school_year


def test_school_year_starts_march_1_kst():
    assert school_year(datetime(2026, 2, 28, 14, 59, tzinfo=UTC)) == 2025  # KST 2/28 23:59
    assert school_year(datetime(2026, 2, 28, 15, 0, tzinfo=UTC)) == 2026  # KST 3/1 0:00
    assert school_year(datetime(2028, 2, 29, 12, tzinfo=UTC)) == 2027  # 윤년 2/29


def test_grade_goes_up_at_march_boundary():
    signup = datetime(2026, 11, 14, tzinfo=UTC)
    assert current_grade(5, signup, datetime(2027, 2, 28, 14, 59, tzinfo=UTC)) == 5
    assert current_grade(5, signup, datetime(2027, 2, 28, 15, 0, tzinfo=UTC)) == 6


def test_grade_6_becomes_middle_1():
    signup = datetime(2026, 11, 14, tzinfo=UTC)
    assert current_grade(6, signup, datetime(2027, 3, 2, tzinfo=UTC)) == 7  # 중1


def test_grade_stops_at_high_3():
    signup = datetime(2026, 11, 14, tzinfo=UTC)
    assert current_grade(11, signup, datetime(2030, 5, 1, tzinfo=UTC)) == 12
    assert current_grade(12, signup, datetime(2027, 5, 1, tzinfo=UTC)) == 12


def test_unknown_grade_or_naive_time():
    assert (
        current_grade(None, datetime(2026, 1, 1, tzinfo=UTC), datetime(2027, 5, 1, tzinfo=UTC))
        is None
    )
    # SQLite는 시간대를 버린다 → UTC로 본다
    assert current_grade(5, datetime(2026, 11, 14), datetime(2027, 3, 2, tzinfo=UTC)) == 6
