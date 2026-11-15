"""띠(멘토 그림) 소유·지금 띠(명세 4.12-5, 11-14). 스타일 코드(EBSP 등)와 섞지 않는다.

가진 띠 = cosmetics_owned의 `animal-{띠}`(사기·장부·탈퇴 삭제를 옷과 같이 씀), 지금 띠 = student_mentor_current.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_org import CosmeticOwned, StudentMentorCurrent

ANIMALS = (
    "rat",
    "ox",
    "tiger",
    "rabbit",
    "dragon",
    "snake",
    "horse",
    "sheep",
    "monkey",
    "rooster",
    "dog",
    "pig",
)  # frontend/src/types.ts 와 같은 12개 키
DEFAULT_ANIMAL = "horse"
ANIMAL_PRICE = 5  # 칭찬 도장 개수(안 — 성호 확정 대기)
PREFIX = "animal-"


def cosmetic_id(animal: str) -> str:
    return PREFIX + animal


async def owned_animals(db: AsyncSession, student_id: str) -> list[str]:
    ids = await db.scalars(
        select(CosmeticOwned.cosmetic_id).where(
            CosmeticOwned.student_account_id == student_id,
            CosmeticOwned.cosmetic_id.startswith(PREFIX),
        )
    )
    have = {i[len(PREFIX) :] for i in ids}
    return [a for a in ANIMALS if a in have]


async def current_animal(db: AsyncSession, student_id: str) -> str | None:
    row = await db.get(StudentMentorCurrent, student_id)
    return row.animal if row is not None else None


async def give_animal(
    db: AsyncSession, student_id: str, animal: str, now: datetime, trial_id: str | None
) -> None:
    """소유 한 줄(이미 있으면 그대로). 커밋은 부르는 쪽."""
    if await db.get(CosmeticOwned, (student_id, cosmetic_id(animal))) is None:
        db.add(
            CosmeticOwned(
                student_account_id=student_id,
                cosmetic_id=cosmetic_id(animal),
                trial_id=trial_id,
                created_at=now,
            )
        )


async def set_current(
    db: AsyncSession, student_id: str, animal: str, now: datetime, trial_id: str | None
) -> None:
    row = await db.get(StudentMentorCurrent, student_id)
    if row is None:
        db.add(
            StudentMentorCurrent(
                student_id=student_id, animal=animal, trial_id=trial_id, created_at=now
            )
        )
    else:
        row.animal = animal
