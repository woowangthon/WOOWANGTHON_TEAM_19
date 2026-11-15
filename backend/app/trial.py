"""공개 체험 세트의 id 규칙과 남용 상한 상수(명세 4.11 2·5번). 상수는 여기 한곳에.

세트 id `t-<16자 소문자·숫자>`, 배우 id는 `<세트 id>-child|guardian|instructor`.
테이블은 따로 두지 않고 접미사로 짝을 찾는다.
"""

import re
import secrets
import string

TRIAL_HOURLY_MAX = 300  # 서버 전체, 최근 1시간 세트 발급 상한(넘으면 429 trial_limit)
AI_DAILY_MAX = 150  # 한 아이 하루 멘토 답(LLM) 상한. 넘으면 그 턴은 대본
# 서버 전체 최근 1시간 멘토 답 상한. 세트를 새로 받아 아이당 상한을 피해도 여기서 막힌다(11-11)
AI_HOURLY_MAX = 1500

TRIAL_PREFIX = "t-"
# 실제 가입 계정 id 접두(accounts.new_account_id). 데모 헤더로는 이 학생에 닿지 못한다(11-12 A3)
ACCOUNT_PREFIX = "a-"
_ALPHABET = string.ascii_lowercase + string.digits
_ACTOR_RE = re.compile(r"^(t-[a-z0-9]{16})-(child|guardian|instructor)$")


def new_trial_id() -> str:
    return TRIAL_PREFIX + "".join(secrets.choice(_ALPHABET) for _ in range(16))


def trial_child_of(actor_id: str, role: str) -> str | None:
    """체험 세트의 보호자·학습지도자 id면 같은 세트 아이 id, 아니면 None."""
    m = _ACTOR_RE.match(actor_id)
    if m is None or m.group(2) != role:
        return None
    return f"{m.group(1)}-child"


def is_trial_actor(actor_id: str, role: str) -> bool:
    """체험 세트의 그 역할 id인지(`t-<16>-child|guardian|instructor`)."""
    m = _ACTOR_RE.match(actor_id)
    return m is not None and m.group(2) == role


def instructor_can_see(instructor_id: str, student_id: str) -> bool:
    """체험 학습지도자는 같은 세트 아이만, 그 밖의 강사는 체험 아이·가입 학생이 아닌 학생만(11-11·A3)."""
    scope = trial_child_of(instructor_id, "instructor")
    if scope is not None:
        return student_id == scope
    return not student_id.startswith((TRIAL_PREFIX, ACCOUNT_PREFIX))
