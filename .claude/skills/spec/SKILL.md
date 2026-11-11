---
name: spec
description: 명세 v0.4(docs/spec_v0.4.md)에서 필요한 절만 찾아 읽게 하는 안내. "명세", "4.4", "API 계약", "상태기계", "테이블", "안전 규칙", "시드 스키마", "프롬프트", "범위에 있나" 같은 말이 나오거나 구현 전에 근거 절을 확인할 때 쓴다. FastAPI 테스트 픽스처 패턴도 들어 있다.
---

# 명세 v0.4 길잡이

정본은 `docs/spec_v0.4.md`(709줄, 약 9,000단어). **통째로 읽지 말고 아래 표에서 절을 골라 `Read`의 offset/limit으로 그 부분만 읽는다.** 줄 번호는 2026-11-09 복사본 기준이며, 파일을 고치면 어긋날 수 있으니 의심되면 `grep -n "^## "`로 다시 잡는다.

## 절 지도

| 찾는 것 | 절 | 시작 줄 |
|---|---|---|
| 11-05 전제, 멘토 성격 주석(스타일 3코드) | 0 | 21 |
| 한 장 요약, 듀오링고에서 가져오는 규칙 4개 | 1 | 37 |
| 참고 조사(따오는 것 / 안 따오는 것) | 2 | 43 |
| 처음 한 번(가입·동의·캐릭터 고르기·성격 검사) | 3.1 | 83 |
| 하루 세션 5단계, 힌트 버튼, 로딩, 수다 끝내기 | 3.2 | 99 |
| 보호자 화면 | 3.3 | 132 |
| 강사 화면(메모 → 초안 → 승인) | 3.4 | 140 |
| 기술 흐름 원칙 4개(서버가 판정, 어댑터 하나, 상태는 DB 행, 비스트리밍) | 4 | 152 |
| 공수표: 반드시 21.0 / 있으면 좋음 5.75 / 하지 않음 | 4.1 | 163 |
| **테이블 7개** 컬럼·제약·보존 | 4.2 | 195 |
| **안전 규칙**(🔴 키워드 1회, 사후 검사) | 4.3 | 214 |
| **API 13개 계약**(`/api/v1`, 오류 형식) | 4.4 | 230 |
| **상태기계** 5상태 + hint_level, 전이 7개 | 4.5 | 252 |
| 실패 모드와 복구 | 4.6 | 283 |
| 인계 계약(화면 ↔ 서버) | 4.7 | 296 |
| 시연 안정성(시드 day3, 리셋, 대본 5분) | 4.8 | 306 |
| 프라이버시 한 장(제출물) | 4.9 | 317 |
| 심사위원이 물을 것 | 4.10 | 330 |
| **11-15 범위표**(반드시/있으면 좋음/하지 않음/후속) | 5 | 343 |
| 화면 목록(UI·기능 매치) | 6 | 374 |
| 설문과 검증 | 7 | 401 |
| 디자인 방향 | 8 | 452 |
| 결정 목록(확정 / 확인 대기) | 9 | 496 |
| 8일 일정표(백 = 성호, 프 = 재하) | 10 | 525 |
| 🔴 키워드 30개 + 평가 문장 20개 | 부록 A | 550 |
| 시드 문제 JSON 스키마 | 부록 B | 587 |
| 대본 YAML(scripted 모드) | 부록 C | 609 |
| 프롬프트 3종 + 성격 코드 정의 | 부록 D | 621 |
| 초안 JSON · 요약 형식 · 역할 선택 · 🔴 화면 | 부록 E | 668 |

## 바로 쓰는 사실 (읽지 않아도 되게)

- 상태 5개: `study`(hint_level 0~3) → `chat` 또는 `bridge`(연속 +1) → `ended`. 어느 단계든 🔴면 `crisis`. 오답은 상태를 안 바꾼다.
- 수다 끝내기 버튼 = `POST /sessions/{id}/phase {to:"bridge"}`. 새 API 아님.
- 캐릭터 고르기 저장 = `PUT /me/mentor {style, honorific, polite}`. **style 값은 동물명이 아니라 스타일 코드로 바꾼다**(11-08 회의 결정, TK-50에서 스타일 코드로 반영).
- 세션 테이블은 `UNIQUE(학생, 날짜)` = 하루 1회. `deadline_at`은 chat 10분, 나머지 null. 서버는 매 요청마다 `now > deadline_at`이면 먼저 전이한다.
- 메시지는 치환본만, 만료 = 생성 + 72시간. 알림 행 만료 = 90일.
- 힌트는 버튼으로만. 숫자·분수 패턴이 없는 입력은 판정 없이 코칭.
- 배포본은 live + 타임아웃 시 scripted 폴백. 영상·현장은 로컬 scripted.

## 바뀐 것 (명세 본문보다 우선)

- 11-08 회의: 캐릭터는 그림체 먼저, 동물은 교체 가능. 명세의 수달·레서판다·펭귄은 예시로만 본다. 코드에는 스타일 코드.
- 11-08 회의: 역할은 재하 프론트 / 성호 백엔드, 배포·LLM 약관은 같이. 10절 일정표의 "프/백" 열은 그대로 유효.
- 11-09: 사후 검사(4.3)는 있으면 좋음 ④. 재하 흐름도에는 반드시로 그려져 있어 확인 필요.

## FastAPI 테스트 픽스처 패턴 (pytest)

출처: robhowley/py-pit-skills `pytest-service`(MIT)의 핵심만 옮김. 이 저장소 기준으로 바꾼 부분은 굵게.

- 엔드포인트 테스트는 `httpx.AsyncClient` + `ASGITransport`. 테스트 함수는 전부 `async def`, `pyproject`의 `asyncio_mode = "auto"`.
- DB는 **SQLite 인메모리 async 엔진을 session 범위**로 만들고, **function 범위 세션은 트랜잭션 안에서 열고 teardown에서 rollback**한다. 테스트끼리 데이터가 안 샌다. `expire_on_commit=False`.
- 외부 호출(LLM)은 **어댑터의 scripted 모드를 쓰거나 `app.dependency_overrides`로 가짜 어댑터를 주입**한다. 실제 공급자 호출 금지.
- 테스트 클래스 없이 최상위 `test_*` 함수만. 픽스처가 셋업을 전부 맡는다. 공유 픽스처는 `tests/conftest.py`.
- 시드 문제·학생 행은 팩토리 픽스처(`def _factory(**overrides)`)로 만든다. **아이 원문처럼 보이는 문장은 픽스처에 넣지 않는다.** 숫자·분수 입력과 짧은 합성 문장만.
- 상태기계는 HTTP 없이 순수 함수 단위로도 테스트한다(전이표 7개 × 입력 몇 개). HTTP 테스트는 한 바퀴(문제 → 오답 → 힌트 → 정답 → bridge → end) 1개와 🔴 1개면 11-15에 충분하다.

```python
# tests/conftest.py 뼈대
@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()

@pytest_asyncio.fixture
async def db_session(engine):
    async with engine.connect() as conn:
        async with conn.begin() as trans:
            session = async_sessionmaker(bind=conn, expire_on_commit=False)()
            yield session
            await session.close()
            await trans.rollback()
```

## 읽는 순서 (처음 들어온 사람)

0절 → 3.2 → 4(원칙) → 4.5 → 4.4 → 5절. 이 여섯 군데면 코드를 시작할 수 있다. 나머지는 해당 작업을 할 때.
