"""시간 도구. "하루"는 Asia/Seoul 날짜(서버가 UTC여도). 테스트는 get_now를 덮어쓴다."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def get_now() -> datetime:
    return datetime.now(UTC)


def seoul_date(now: datetime) -> date:
    return now.astimezone(SEOUL).date()


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite는 시간대를 버린다. 시간대 없는 값은 UTC로 본다."""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=UTC)


def school_year(now: datetime) -> int:
    """한국 학년도: 3월 1일 0시(KST)에 시작한다(명세 4.12-5 UG1)."""
    d = seoul_date(as_utc(now) or now)
    return d.year if d.month >= 3 else d.year - 1


def current_grade(grade: int | None, signup_at: datetime | None, now: datetime) -> int | None:
    """가입 학년 + 지난 학년도 수. 고3(12)에서 멈춘다(졸업 처리는 후속). 배치 없이 읽을 때 계산."""
    if grade is None or signup_at is None:
        return grade
    up = max(0, school_year(now) - school_year(signup_at))
    return min(12, grade + up)
