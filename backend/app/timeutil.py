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
