# 친구1 전체 점검과 개발 계획 v0.1 (2026-11-11)

이 문서는 2026-11-11 하루 동안 한 점검·실측·조사를 한곳에 모은 것이다. 읽는 쪽은 이 문서만 들고 개발을 이어 갈 사람(또는 Claude 세션)이다. 앞 대화를 보지 못했다고 가정하고 썼다.

- 대상 브랜치: `TK-56-deploy` (main에서 갈라짐, 커밋 10개, **아직 push하지 않음**)
- 검증 상태: `cd backend && uv run pytest` 480 passed · ruff 0 · pyright 0 (11-11 확인)
- 일정: 11-12 22:00 코드 프리즈 · 11-13 리허설·영상 · 11-15 15:00 제출
- 함께 볼 파일: `docs/review_1111/`(조사 문서 2개, 프론트 연결 패치 2개), `docs/api_contract_v0.1.md`, `docs/deploy_render_v0.1.md`, `docs/spec_v0.4.md`(절 번호로만 읽는다)

---

## 0. 한 장 요약

**백엔드는 실제로 돈다.** 실측에서 아이 하루(같이 풀기 → 수다 → 다리 놓기 → 끝), 🔴 경로, 강사 메모 → 초안 → 승인 → 보호자 카드, 리셋, 재시작이 모두 끝까지 갔고 500은 0건, 정답 누출도 0건이었다.

**MVP가 아직 안 된 이유는 네 가지다.**

1. **배포가 없다.** push도 Render 연결도 하지 않았다. 진짜 LLM(live)은 키가 없어 한 번도 불러 보지 못했다.
2. **프론트가 서버에 붙어 있지 않다.** 저장소 `frontend/`는 비어 있다. 재하의 v0.5는 압축본으로만 있고, 가짜 서버(mock)로 돈다. 테스트용 패치를 넣으면 아이 흐름과 보호자 카드는 붙지만, 풀기 화면이 나눗셈을 「−」로 그리고 일부 문제에서 흰 화면이 된다.
3. **강사 화면과 리셋이 서버에 안 붙는다.** 호환 라우터에 강사 경로가 없고, 프론트의 리셋 버튼은 mock만 지운다. 시연 대본(세션 A → 리셋 → 세션 B → 보호자 → 강사)을 화면으로 완주할 수 없다.
4. **팀 결정이 문서와 어긋나 있다.** 로그인, 🔴 발췌, 시크릿 모드, DB 종류, 끊어 보내기가 명세·결정 DB·프론트 문서에서 서로 다르다.

**권하는 순서**: ① 배포해서 live를 실제로 확인 → ② 프론트를 저장소에 넣고 치명 결함 2개 수정 → ③ 강사·리셋 연결 → ④ live 여부 표시와 대본 채우기 → ⑤ 결정 반영. 상세는 6절.

---

## 1. 지금 있는 것 (실측으로 확인한 것만)

| 영역 | 상태 | 근거 |
|---|---|---|
| 아이 API (오늘·세션·메시지·전환·다리 놓기·끝·멘토 설정) | 동작 | `backend/app/api.py`, 실측 2회 |
| 판정 | 서버 코드가 판정하고 조각마다 저장한다(`messages.judge`). 「풀었나」는 저장값을 읽는다 | `judge.py`, `models.py`, `tests/test_turns.py` |
| 끊어 보내기 | 조각 최대 5개를 한 턴으로 받는다. 답 생성 중 온 조각은 저장·🔴 검사·판정만 하고(`queued`), 끝나면 `/reply`로 이어 답한다. LLM은 DB 잠금 밖에서 부른다 | `api.py` `_accept`·`_reply`, 명세 3.2·4.4 #4·#4a |
| 🔴 | 조각마다 즉시, 끊어 보낸 문장도 이어 붙여 검사. LLM 없이 고정 문장·109·1388·종료·알림 1건 | `safety.py`, `api.py` `_crisis` |
| LLM 어댑터 | live(Anthropic Haiku 5.5, 비스트리밍, 20초) → 실패 시 대본 → 고정 문장. **live는 가짜 클라이언트 테스트만 통과, 실제 호출 0회** | `llm.py` |
| 강사·보호자 | 메모 → 초안(템플릿 폴백) → 승인 → 보호자 카드 | `instructor.py`, `guardian.py` |
| 시연 장치 | `/demo/reset`(토큰), 타이머 배율, 기동 시 데모 배우 자동 생성 | `demo.py`, `main.py` |
| 호환 라우터 | 재하 v0.5 모양 그대로 `/api/v1/compat`: 아이 흐름 + 보호자 카드·알림 | `compat.py`, 계약 메모 compat 절 |
| 배포 준비 | `render.yaml`(워커 1개, 휘발성 SQLite), CORS(localhost + `CORS_ORIGINS`) | `render.yaml`, `main.py` |

지연(로컬): 일반 요청 4~25ms. LLM 인증 실패는 0.3초 만에 대본으로, 무응답은 20초 뒤 대본으로 넘어간다.

---

## 2. 지켜야 할 원칙 (바꾸려면 성호에게 먼저 묻는다)

루트 `CLAUDE.md`가 정본이다. 개발 중 특히 걸리는 것만 적는다.

- **판정·전환·힌트·시간은 서버 코드가 한다.** LLM은 문장만 만든다. 대본도 같은 판정 값을 받는다(대본에만 따로 규칙을 넣지 않는다 — 성호 11-11).
- **정답 문자열은 프롬프트와 응답에 넣지 않는다.** 풀이는 힌트 단계 3에서만.
- **아이 원문을 저장·로그·테스트에 남기지 않는다.** 치환본만 저장, 72시간 만료. 테스트 문장은 합성.
- 스트리밍, 백그라운드 큐, 외부 발송(메일·푸시)은 없다.
- 범위는 명세 5절 표. 표에 없는 기능은 만들지 않고 질문 DB에 적는다.
- 프론트 디자인(색·글꼴·배치·그림)은 재하 영역이다. 기능 결함만 고치고, 고친 곳은 재하에게 알린다.
- 테스트 먼저. 커밋 제목 `TK-<n>: 내용`. 명세를 바꿀 일이면 명세와 결정 DB를 코드보다 먼저 고친다.
- 노션에 쓰기 전에는 바꿀 목록을 보여 주고 승인받는다.
- **push 규칙**: 원격은 공개 저장소 `woowangthon/WOOWANGTHON_TEAM_19`. `NOTE.md`와 `CLAUDE.md`를 빼고, 원격 main 위에 커밋 1개로 올린 브랜치 + PR. 로컬 기록을 그대로 올리면 과거 커밋의 NOTE.md가 공개된다. 시점은 성호가 정한다.

---

## 3. 문제 목록

심각도: **상** = 시연이 깨지거나 거짓이 됨, **중** = 시연 품질·안전에 영향, **하** = 다듬기.

### 3.1 배포 (D)

| # | 문제 | 심각도 | 고치는 방법 | 끝났다는 기준 |
|---|---|---|---|---|
| D1 | 배포본이 없다. Render CLI가 없어 대시보드 작업은 성호가 직접 해야 한다 | 상 | 2절 push 규칙대로 올림 → `docs/deploy_render_v0.1.md` 순서로 Blueprint 연결 → 환경 변수(`LLM_API_KEY`, `DEMO_TOKEN`, `CORS_ORIGINS`) 입력 | 배포 URL `/healthz`가 `db ok`, `llm_mode live`, `llm_key true` |
| D2 | live를 실제로 불러 본 적이 없다. 키·모델 ID가 틀려도 화면에는 대본 답이 나와 티가 안 난다 | 상 | 배포 후 대본에 없는 말을 한 번 보내 답을 확인하고, 서버 로그에 `llm fallback` 경고가 없는지 본다. B1(source 표시)이 있으면 응답으로 바로 확인된다 | 대본에 없는 입력에 문맥이 맞는 답, 로그에 폴백 경고 없음 |
| D3 | `render.yaml`의 `PYTHON_VERSION: 3.12.16`을 Render가 지원하는지 확인 못 했다 | 중 | 빌드가 실패하면 Render가 가진 3.12.x로 바꾼다 | 빌드 성공 |
| D4 | 무료 플랜은 15분 쉬면 꺼지고 DB가 빈다(재기동 약 1분). 그날 대화·알림·승인이 사라진다 | 중 | 시연 직전 한 번 깨우고 리셋을 부르는 절차를 대본에 넣는다. 사라지면 안 되면 유료 디스크나 Postgres(결정 필요) | 리허설에서 슬립 복귀 시간을 재고 대본에 적음 |
| D5 | 로그 레벨을 DEBUG로 두면 aiosqlite가 치환본을 찍는다. 접근 로그에 세션 id가 남는다 | 하 | 운영은 INFO 고정(안내 문서에 있음) | — |

### 3.2 백엔드 (B)

| # | 문제 | 심각도 | 고치는 방법 | 끝났다는 기준 |
|---|---|---|---|---|
| B1 | **그 답이 live였는지 밖에서 알 수 없다.** `/healthz`는 키가 "있는지"만 본다. 대본으로 답해도 live처럼 보인다 — 「짜고 친다」 의심의 실제 빈틈 | 상 | 어댑터가 `(문장, source)`를 돌려주게 하고 `/messages`·`/reply`·compat 응답에 `source: live / scripted / fixed`를 넣는다. 로그에 source·지연·토큰 수(`usage`)를 남긴다(원문 제외). 화면 배지는 재하와 합의 | 폴백 테스트에서 `source == "scripted"`, live 가짜 클라이언트에서 `"live"`. 계약 메모 갱신 |
| B2 | 대본이 얇다(`day3.yaml` 17줄). 수다 두 번째 답이 첫 답과 같고, 정답 대본이 「한 줄로 말해 줄래?」라고 묻는데 화면에는 「계속」 버튼뿐이다. 오프라인 리허설과 live 장애 때 이 문장이 나간다 | 중 | 스타일 3종 × (study 판정 3종 × 힌트 단계, chat 3~4 step, bridge)로 채운다. 화면 흐름과 맞지 않는 질문형 문장은 뺀다. 문장은 성호 검토 | scripted 모드로 대본 완주 시 같은 문장 반복 없음 |
| B3 | 말투·성격 세팅이 한 줄짜리다(`prompts.py` `STYLE_LINE`). 같이 풀기·수다 프롬프트에 버전 기록이 없다 | 중 | 스타일 카드(5~8줄) + 스타일별 예시 대화 2~3쌍(시드와 다른 숫자) + `prompt_version` 기록 + 평가 문장 20개 채점(TK-37). 파인튜닝·Ollama는 하지 않는다(`docs/review_1111/research_llm.md`) | 평가표에서 정답 누출 0, 3문장 초과 0, 반말/존댓말 위반 0 |
| B4 | live 설정 미확정: 지금 `max_tokens 1024`, effort low, thinking 파라미터 없음. Haiku 5.5에서 thinking을 끌 수 있다는 조사 결과와 어댑터 주석이 다르다 | 중 | 키가 생기면 thinking on/off로 지연·토큰을 재고 정한다. `claude-api` 스킬로 사실 확인 | 측정값을 계약 메모에 기록 |
| B5 | 강사 초안: 모델이 JSON을 코드 블록으로 감싸면 파싱 실패 → 템플릿. 템플릿 문장이 마침표 없이 이어 붙는다 | 중 | `_parse_draft` 앞에서 코드 블록 벗기기, 템플릿 문장 이음 수정 | 펜스 감싼 입력 테스트 통과 |
| B6 | 신원 헤더를 확인하는 코드가 역할별 의존성 3개에 복제돼 있다(`api.py` `current_child`, `guardian.py` `current_guardian_child`, `instructor.py` `current_instructor`). 헤더를 그대로 믿으므로 공개 URL에서는 누구나 데모 배우 행세를 할 수 있다 | 중 | 공통 함수 하나로 모으고 세 의존성은 껍데기로(동작 불변). 로그인은 6절 P3 — 결정 뒤 | 기존 테스트 그대로 통과 |
| B7 | compat `submitAnswer`가 답 생성 중 `queued`로 오면 `message`가 빈 문자열이 된다(화면이 잘못 넘어갈 위험, 미재현) | 중 | queued일 때 프론트가 알 수 있게 `queued` 칸을 싣고 계약에 적는다 | 테스트 1건 |
| B8 | 🔴 발췌(±2턴)가 수다에서 같이 풀기 턴까지 넘어가 아이가 쓴 답이 실린다 | 중(정책) | 4절 결정 2에 따른다. 발췌 유지면 같은 단계 안에서만 자른다 | 결정 후 |
| B9 | 같이 풀기 20분은 서버 마감이 없다(수다 10분만 있다). 프론트 카운트다운이 0이 되면 화면이 그대로 멈춘다 | 중 | 명세 4.5에 풀기 마감이 없으므로 서버는 그대로 두고, 프론트가 0에서 「수다로 갈까?」를 보여 주게 요청(F7). 서버 마감을 넣으려면 명세 먼저 | 결정 후 |
| B10 | 23:58에 시작한 세션은 자정이 지나면 버려지고 새 세션이 생긴다 | 하 | 시연에 영향 없음. README 한 줄 | — |
| B11 | 데모 배우 하나를 심사위원 여럿이 같이 쓴다. 한 사람의 리셋이 다른 사람 진행을 지운다(명세 4.6 「미정」) | 중 | 최소안: 체험 계정을 3~5쌍으로 늘리고 리셋이 요청한 배우만 지우게. 로그인 결정과 같이 본다 | 결정 후 |
| B12 | 답 생성 표시는 25초 뒤 풀린다. 요청이 죽으면 그동안 힌트가 409 | 하 | 그대로 둔다(문서화됨) | — |
| B13 | 멘토 답을 사이에 둔 🔴 끊김("죽고" → 답 → "싶어")은 못 잡는다 | 하(알려진 한계) | 키워드 방식의 한계로 명세 4.3에 1줄 추가 | 명세 반영 |
| B14 | 묵은 함정: `errors.py:28`이 HTTPException의 headers를 버린다(405에 Allow 없음). `pii.py:13` 전화 정규식이 `010 - 1234 - 5678`·en-dash를 못 잡는다. `pii.py:25` 별명이 "이름"·"전화"면 치환 표시가 깨진다 | 하 | 각각 테스트 1건씩 넣고 수정 | 테스트 통과 |
| B15 | 스키마는 `create_all`뿐이다. 예전 `dev.db`를 그대로 쓰면 새 칸이 없어 오류 | 하 | 로컬 `backend/dev.db` 삭제 후 재기동. README에 1줄 | — |
| B16 | `docs/llm_alternatives_v0.1.md`의 「Haiku 5.5 최소 캐시 286토큰」은 오독이다(공식 512). Anthropic 보관 기간 표현(30일 vs 기본 비보관)도 대조 필요 | 하 | 문서 정정 | — |
| B17 | compat 힌트는 시드의 힌트 문장을 그대로 보낸다(명세는 「힌트 문장은 LLM」) | 하(결정) | 정답 은닉에는 안전. 4절 결정 6 | 결정 후 |

### 3.3 프론트 (F) — 재하 영역, v0.5 기준

근거 패치: `docs/review_1111/frontend_patch_v1.diff`(헤더·mock/http 섞기), `frontend_patch_v2.diff`(끊어 보내기). 줄 번호는 재하 압축본 기준이다(원본: `~/Downloads/성호전달-AI멘토-v0.5.zip`).

| # | 문제 | 심각도 | 고치는 방법 |
|---|---|---|---|
| F1 | 나눗셈이 「3/4 − 2/1」로 보인다. 문제 문장이 안 나온다 | 상 | `Solve.tsx:149`: `op`가 `÷`면 ÷, 문장(`text`)을 식 위에 표시 |
| F2 | `left`·`right`가 null인 문제(예 `(1 + 3/4) ÷ 2/3`)에서 화면 전체가 하얗게 된다 | 상 | null이면 식 없이 문장만. `Fraction.tsx:6` 방어 + 오류 경계 1개 |
| F3 | 서버에 붙지 않는다: 헤더 없음(401), `/me` 없음(로그인 화면에서 멈춤), 오류는 `detail`만 읽음 | 상 | 패치 v1: `X-Demo-Role`·`X-Demo-Actor` 헤더, `j.message ?? j.detail`, `api/index.ts`에서 아이 흐름·보호자 함수만 http·나머지는 mock |
| F4 | 끊어 보내기 미반영(전송 중 입력 비활성화) | 중 | 패치 v2 `Chat.tsx`: 1.5초 묶어 `texts`, 입력 계속 켬, `queued`면 「생각 중」 유지, `pending`이면 `/reply`, 답 기다리는 동안 힌트 버튼 끔 |
| F5 | **강사 화면이 서버에 안 붙는다.** compat에 강사 경로가 없고, 메모·초안·지정의 모양이 서버와 다르다(메모만 저장 없음, 초안 고치기 없음, 단원으로 지정) | 상 | compat에 강사 경로 추가 + 프론트 한 줄. 상세는 7-1 「F5」 |
| F6 | 리셋·빠른 모드 버튼이 mock만 건드린다 | 상 | 시연자용으로 `/api/v1/demo/reset`(X-Demo-Token)을 부르는 작은 패널, 또는 대본에 curl 1줄. 토큰을 빌드에 넣지 않는다 |
| F7 | 풀기 카운트다운 0에서 화면이 멈춘다(B9) | 중 | 0이 되면 수다로 넘어가는 선택을 보여 줌 |
| F8 | 위기·약속 화면이 「대화 내용은 보내지 않았어」라고 하는데 서버는 발췌를 보낸다 | 상(정책) | 4절 결정 2 뒤에 문구와 데이터를 맞춘다 |
| F9 | 결정과 다른 화면: 보호자 「괜찮아요」 활성(결정은 회색 「후속」), 🔴이 강사에게도 보임(결정은 보호자만) | 중 | 버튼 회색 처리, 강사 알림 탭 숨김 |
| F10 | 다리 놓기 제목 「선생님께 보낼 한 줄」(실제는 보호자). 「어려웠던 점」 칩이 비면 제목만 남음. 퀴즈 칩 긴 문장이 화면 밖으로 잘림 | 중 | 제목 수정, 빈 섹션 숨김, `.chip`에 `max-width:100%; white-space:normal` |
| F11 | 문구 어긋남: 홈 「오늘도 해냈어!」와 「오늘 할 것이 아직 없어요」 동시 표시, 🔴 뒤 보호자 홈 「아직 공부 전」, 홈 이름이 mock(지우)과 서버(민수)로 다름 | 중 | `done`·`solved` 기준으로 정리. 체험 계정 이름을 서버 데모 배우와 맞춤 |
| F12 | 힌트 점 3개(서버는 힌트 2 + 풀이), 자연수 답을 「3 위 1 아래」로 넣어야 함, 세션이 사라진 뒤 돌아갈 버튼 없음 | 중 | 점 2개, 자연수 입력 안내, 404면 「처음으로」 |
| F13 | 터치 영역 44px 미만(칩 40, 분자·분모 42, 화살표 36), 강사 메모 입력칸 라벨 없음, 힌트 조사 오류("분모 11는"), favicon 404, dev 서버 `host: true`(LAN 노출) | 하 | 각각 수정 |

정상으로 확인된 것: 가로 스크롤 없음, 전송 중 버튼 비활성(답 확인·시작·보내고 끝내기), 새로고침 이어짐, 서버 꺼짐 시 오류·「다시 시도」, 이미지 alt.

### 3.4 명세·결정·문서 불일치 (S)

| # | 어긋난 곳 | 고치는 방법 |
|---|---|---|
| S1 | DB: 명세 4.8-5·10절은 Postgres, 배포는 휘발성 SQLite(11-11 성호) | 명세 수정 + 결정 DB 1건 |
| S2 | 끊어 보내기: 명세는 고쳤고 결정 DB 「등록 대기」. 루트 `CLAUDE.md`에는 아직 「전송 중 버튼 비활성화」 | 결정 DB 1건 + `CLAUDE.md` 「이미 정한 것」 수정 |
| S3 | 로그인: 명세 5절은 「로그인 대신 역할 선택」, 재하 문서는 「아이디·비밀번호 확정」. 결정 DB에서 못 찾음 | 4절 결정 1 |
| S4 | 🔴 보호자 알림: 코드·명세는 발췌 ±2턴, 재하 문서·화면은 원문 없음 | 4절 결정 2 |
| S5 | 시크릿 모드: `CLAUDE.md`는 미결정, 재하 문서는 폐기 | 결정 DB 확인 후 `CLAUDE.md` 수정 |
| S6 | 계약이 두 벌(기본 `/api/v1`, 임시 `/api/v1/compat`) | 결정 DB에 「compat는 11-15까지 임시」 1건 |
| S7 | `NOTE.md` 맨 위 항목이 11-10 기준이다 | 세션 끝에 `handoff-note`로 갱신 |

---

## 4. 먼저 정해야 하는 것 (정해지기 전에는 코드를 쓰지 않는다)

| # | 정할 것 | 추천 | 근거 |
|---|---|---|---|
| 1 | 11-15 신원 방식 | **체험 계정 고정 + Bearer 서명 토큰**, 가입·소셜 로그인은 이후. `AUTH_MODE=demo/login` 스위치로 기존 테스트 유지 | 다른 주소 쿠키는 아이폰 Safari가 막는다. DB가 휘발성이라 DB 저장 토큰·가입 계정은 15분 뒤 사라진다. 카카오·구글은 만 14세 미만에 맞지 않아 어른 계정용으로만 권장. 상세 `docs/review_1111/research_auth.md` |
| 2 | 🔴 보호자 알림에 발췌를 넣을지 | **원문 없이 분류·긴급도·행동 안내**로 통일(재하 화면과 같음) | 화면이 아이에게 「안 보냈어」라고 말하고 있어 지금은 거짓이 된다. 발췌 유지 시 B8·F8을 반대로 맞춘다 |
| 3 | live 표시 | 응답 `source` + 화면 작은 배지 | B1 |
| 4 | 프론트 코드를 저장소에 어떻게 넣나 | 재하가 `frontend/`에 직접 올리고, 연결 패치는 PR로 | 지금 `frontend/`가 비어 있고 공개 저장소에 그림 파일이 올라간다(재하 확인 필요) |
| 5 | 프론트 배포 위치 | 정적 호스팅(예: Vercel) + `CORS_ORIGINS`에 주소 등록 | 토큰 방식이면 쿠키 문제가 없다 |
| 6 | compat 힌트 문장 | 시드 문장 그대로(지금) | 정답이 새지 않고 빠르다. 명세 3.2에 1줄 |
| 7 | 장기 기억(세션 요약 보관) | 11-15는 값만(스타일·오개념·힌트 사용). 요약 보관은 보관 기간·보호자 동의를 정한 뒤 | 원문 미저장·72시간 규칙과 충돌 |
| 8 | 심사위원 동시 접속 | 체험 계정 여러 쌍 + 배우별 리셋 | B11 |

---

## 5. MVP 기준(명세 5절 「반드시」)에서 빠진 것

| 5절 항목 | 서버 | 화면 연결 | 남은 일 |
|---|---|---|---|
| 역할 선택(테스트 계정) | 헤더 방식 있음 | 프론트는 mock 로그인 | 결정 1, F3 |
| 아이 오늘 → 같이 풀기 → 수다 → 다리 놓기 → 끝 | 있음 | 패치 넣으면 연결됨 | F1·F2·F4·F10·F12 |
| 약속 화면 | `Student.consent` 칸은 있으나 바꾸는 API가 없다(늘 통과) | 정적 화면 있음, mock에만 저장 | 문구(F8), 7-1 「약속 화면 동의 저장」 |
| 캐릭터 고르기 | `PUT /me/mentor`(스타일·호칭·말투). 그림 저장 칸 없음 | compat 연결됨 | 그림은 프론트에만 저장(지금 그대로 둠) |
| 🔴 감지 → 종료 → 보호자 알림 | 있음 | 연결됨 | 결정 2 |
| 강사 메모 → 초안 → 승인 → 보호자 카드 | 있음 | **미연결** | F5, B5 |
| 보호자 오늘 | 있음 | 연결됨 | F11 |
| 뼈대(어댑터·상태기계·시드·프롬프트·PII) | 있음 | — | B2·B3 |
| 시드 day3 + 리셋 + 타이머 단축 | 있음 | **미연결** | F6 |
| 배포 | 설정만 있음 | — | D1~D4 |
| 시연 대본 완주(세션 A → 리셋 → 세션 B) | API로는 완주 | **화면으로 미완주** | P1 전체 |
| 제출물(README·영상·PDF) | — | — | 11-13~14, README에 「영상은 대본 모드, 배포 URL은 live」 1줄 |

---

## 6. 작업 순서

각 작업은 테스트 먼저, 끝나면 `uv run pytest`·ruff·pyright 통과를 확인한다. 한 작업 = 한 커밋 묶음.

### P0 — 배포해서 live 확인 (오늘)
1. **push** (성호가 시점 승인): 원격 main을 받아 그 위에 `NOTE.md`·`CLAUDE.md`를 뺀 현재 트리를 커밋 1개로 올린 `TK-56-deploy` 브랜치 → PR. 올리기 전에 `git ls-files`로 두 파일이 빠졌는지 확인.
2. Render 연결과 환경 변수 입력은 성호가 한다(`docs/deploy_render_v0.1.md`).
3. 배포 확인: `/healthz` → 아이 헤더로 세션 시작 → 대본에 없는 말 1턴 → 로그의 폴백 경고 확인(D2). B4 측정도 여기서.
4. B1(`source`)을 먼저 넣으면 3번이 응답만으로 확인된다. 작은 변경이니 P0에 포함한다.

### P1 — 화면으로 대본 완주 (11-11~12)
1. 결정 4에 따라 프론트를 `frontend/`에 넣는다(재하).
2. F1·F2·F3 (치명): 풀기 화면, 흰 화면, 서버 연결.
3. F4: 끊어 보내기 화면.
4. F5: compat에 강사 경로 추가(7-1 「F5」의 표와 방식 그대로). 초안 고치기 저장은 명세 3.4·4.4 #9에 한 줄 먼저. 계약 메모에 표 추가.
5. F6: 리셋 연결.
6. B7, B5.
7. 화면 실측을 다시 돌린다(7절).

### P2 — 시연 품질 (11-12 프리즈 전)
1. B2 대본 채우기 → scripted 모드로 대본 완주(오프라인 리허설 조건).
2. B3 스타일 카드·예시 대화·평가 문장 채점(TK-37, `prompt-engineer` 에이전트).
3. F7~F13 중 중 이상.
4. B6 헤더 의존성 합치기, B14 묵은 함정.
5. S1~S7 문서·결정 DB 정리(노션은 승인 뒤).

### P3 — 결정이 난 것만
1. 결정 1(로그인 최소안): `accounts`·`guardian_links` 테이블, `/auth/login`·`/me`·`/demo/accounts`, 기동 시 체험 계정 생성(`DEMO_PASSWORD` 환경 변수), argon2, `AUTH_MODE` 스위치, 프론트 토큰 저장. 설계표는 `research_auth.md` ⑤.
2. 결정 2(발췌 정책): `guardian.py`의 발췌 함수 하나, 명세 3.2·4.2·4.3·4.4 #4·#11·부록 E, `Alert.excerpt`, compat `getAlerts`, 프론트 문구.
3. 결정 8(체험 계정 여러 쌍).

### 하지 않는 것 (발표 「다음 단계」로)
소셜 로그인, 파인튜닝·로컬 모델, 장기 대화 기억·임베딩 검색, 영구 DB·백업, 프롬프트 캐싱, 안전 LLM 분류.

---

## 7. 검증 방법

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format . && uv run pyright

# 배포와 같은 방식으로 로컬 기동(빈 DB)
cd backend && DATABASE_URL=sqlite+aiosqlite:////tmp/chingu1_local.db LLM_MODE=scripted DEMO_TOKEN=<임의값> \
  uv run --frozen --no-dev uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
curl -s localhost:8000/healthz
curl -s -H 'X-Demo-Role: child' -H 'X-Demo-Actor: demo-child-minsu' localhost:8000/api/v1/me/today
```

화면 실측은 `webapp-testing` 스킬(Playwright)로 360×640에서 아래를 끝까지 누른다. 느린 답은 네트워크 지연이 아니라 **서버 쪽 LLM을 느리게** 해야 재현된다(`LLM_MODE=live` + 가짜 키 + `ANTHROPIC_BASE_URL`을 4초 늦게 답하는 가짜 서버로).

1. 빈 DB 기동 → 홈
2. 오답 → 힌트 1·2 → 정답 (DB `messages.judge` 확인, 화면 문구가 판정과 맞는지)
3. 수다 3조각 연달아 → 멘토 답 1개. 답 생성 중 조각 → 기다림 표시 → 이어 답
4. 답 생성 중 🔴 → 즉시 위기 화면, 알림 1건
5. 리셋 → 세션 B → 다리 놓기 → 끝 → 보호자 카드
6. 강사 메모 → 초안 → 승인 → 보호자 카드에 반영
7. 서버 재시작(같은 DB / DB 삭제) 뒤 화면
8. 전 과정에서 500 0건, 응답에 정답 문자열 0건(풀이 보기 제외), 콘솔 오류, 가로 스크롤

「됐다」는 이 8개를 배포 URL에서 한 번, scripted 로컬에서 한 번 통과했을 때만 말한다.

---

## 7-1. 기술 스택과 구현 방법

### 스택 (지금 쓰는 것 — 새 라이브러리는 아래 「추가」에 적힌 것만)

| 층 | 기술 | 비고 |
|---|---|---|
| 백엔드 | Python 3.12, FastAPI, Pydantic v2, uvicorn(워커 1개) | 패키지 관리는 `uv`(`backend/pyproject.toml`, `uv.lock`) |
| DB | SQLAlchemy 2 async + aiosqlite(SQLite 파일) | 마이그레이션 도구 없음. 기동 때 `create_all`. 칸을 바꾸면 로컬 DB 파일을 지운다 |
| LLM | `anthropic` SDK, 모델 `claude-haiku-5-5`, 비스트리밍 `messages.create` | 키 `LLM_API_KEY`, 모델 `LLM_MODEL`, 모드 `LLM_MODE=live/scripted`. SDK 사실 확인은 `claude-api` 스킬 |
| 대본 | YAML(`backend/app/scripts/day3.yaml`), PyYAML | 조회 키: scenario(`day3-{스타일}`), phase, hint_level, judge, step |
| 테스트 | pytest + pytest-asyncio, httpx `ASGITransport`, ruff, pyright | DB는 인메모리 SQLite, 테스트마다 rollback. 동시성 테스트만 파일 SQLite |
| 프론트(재하 v0.5) | React 19, TypeScript 5.8, Vite 6, react-router 7, vitest | 화면은 `src/api/client.ts` 함수만 부른다. 실제 호출은 `src/api/http.ts`, 가짜 서버는 `mock.ts` |
| 배포 | Render 웹 서비스(무료, `render.yaml`), 프론트는 정적 호스팅(미정) | `VITE_API_MODE=http`, `VITE_API_BASE=<백엔드>/api/v1/compat` |
| 화면 실측 | Playwright(`.claude/skills/webapp-testing`) | 360×640 |

추가가 필요한 것: 로그인을 하면 `argon2-cffi`(비밀번호 해시)와 `pyjwt`(서명 토큰). 그 밖에는 없다.

### 항목별 구현 방법

아래는 11-11에 코드(`backend/app/*.py`)와 재하 v0.5의 `types.ts`·`client.ts`·`mock.ts`를 줄 단위로 대조해 쓴 것이다. 설계안이며 아직 코드로 돌려 보지는 않았다. 「주의」는 대조하다가 찾은, 그냥 짜면 틀리는 지점이다.

#### B1 `source` 표시 (그 답이 live였는지)

지금: `LLMAdapter.reply(req) -> str`(`llm.py`). 폴백은 `FallbackAdapter` 안에서 일어나 밖에서 모른다.

1. `llm.py`에 `@dataclass(frozen=True) class Reply: text: str; source: Literal["live","scripted","fixed"]; in_tokens: int | None = None; out_tokens: int | None = None`을 두고 `reply()`가 이것을 돌려주게 한다.
   - `AnthropicAdapter`: `source="live"`, 토큰은 `resp.usage.input_tokens`·`output_tokens`.
   - `ScriptedAdapter`: 대본 줄을 찾으면 `"scripted"`, `FIXED_REPLY`로 떨어지면 `"fixed"`.
   - `FallbackAdapter`: 실제로 답한 쪽의 `Reply`를 그대로 돌려준다.
2. 호출하는 곳은 **세 곳**이다. 전부 `.text`로 바꾼다: `api.py` `_reply`(약 579줄), `api.py` 다리 놓기 요약(약 832줄), `instructor.py` `_draft_body`(약 161줄).
3. `api.py` `_out()`에 `source` 인자를 더한다. `_save_reply`가 넘긴다. 🔴 고정 문장과 `queued` 응답은 각각 `"fixed"`, `None`.
4. 로그는 `_save_reply`의 기존 `message session=…` 줄에 `source`, 토큰 수, 걸린 시간(ms)을 붙인다. 문장은 넣지 않는다. DB 칸은 만들지 않는다.
5. `compat.py`: `sendChat`·`submitAnswer`·`reply` 응답에 `source`를 그대로 싣는다. 프론트 `types.ts`의 `ChatReply`·`AnswerResult`에 `source?: 'live' | 'scripted' | 'fixed'`.
6. (선택) `/healthz?probe=1`: 그때만 `max_tokens`를 작게 해서 실제 호출 1회, `{"llm_probe": "ok" | 예외 타입, "ms": …}`. 기본 호출은 지금처럼 설정만 본다.

주의: 테스트용 가짜 어댑터가 6개 파일에 11개 있다(`tests/test_turns.py` 4, `test_llm_adapter.py` 3, `test_deploy.py`·`test_child_flow.py`·`test_instructor.py`·`test_messages.py` 각 1). 반환형을 바꾸면 전부 고쳐야 한다.
테스트: 가짜 클라이언트 live → `"live"`와 토큰 수, 예외 → `"scripted"`, 대본 키 없음 → `"fixed"`, `/messages` 응답에 `source` 칸.

#### B2 대본 채우기

지금: 한 줄 = `{scenario, phase, hint_level, judge, step, reply}`. 찾는 순서는 (hint, judge) → (0, judge) → (hint, 없음) → (0, 없음), step이 없으면 그 키의 가장 큰 step(`ScriptedAdapter.reply`). 코드는 고치지 않고 `backend/app/scripts/day3.yaml`만 채운다.

- 분량: 스타일 3종 × [study: judge 3종(correct/wrong/없음) × hint 0·1·2·3] + [chat: step 1~4] + [bridge: step 1]. 한 스타일에 약 17줄, 합쳐 50줄 안팎.
- study에서 `step`은 「이 단계에서 아이가 말한 순번」이라 오답을 반복하면 올라간다. wrong 줄은 step 1·2를 다르게 써서 같은 말이 반복되지 않게 한다.
- 정답 줄은 화면의 다음 행동(「계속」 버튼)과 맞게, 되묻지 않는 문장으로 쓴다.
- 대본에는 정답 숫자를 쓰지 않는다(문제마다 다르고, 정답 누출 검사에 걸린다).
- 다리 놓기 요약 호출은 phase가 `summary`라 대본에 없고 템플릿으로 간다. 그대로 둔다.

테스트: 모든 (스타일, phase, judge, hint) 조합이 `FIXED_REPLY`가 아님, chat step 1·2가 다른 문장, YAML 전체에 시드 20문제의 정답 문자열이 없음.

#### B3 말투·성격 (프롬프트)

지금: `prompts.py`의 `STYLE_LINE[code]` 한 줄 + 반말/존댓말 한 줄. system의 줄 순서는 [역할·말투, 호칭 규칙, 문제·힌트, 판정, 규칙].

1. `STYLE_CARD[code]`(5~8줄: 이렇게 말한다 / 이렇게는 말하지 않는다 / 칭찬하는 법 / 막혔을 때)와 `FEWSHOT[code][phase]`(아이 말 → 멘토 답 2~3쌍)를 상수로 둔다. 예시 속 숫자는 시드 20문제와 겹치지 않게 한다. 반말·존댓말 예시를 둘 다 두거나, 예시는 반말로만 두고 「말투 규칙이 예시보다 우선」이라고 한 줄 적는다.
2. `build_prompt`의 줄 순서를 **고정 부분 → 변하는 부분**으로 바꾼다: [역할·호칭·스타일 카드·예시·규칙] 다음에 [문제·힌트 단계·써도 되는 힌트·판정]. 내용은 같고 순서만 바뀐다. 나중에 프롬프트 캐싱을 켤 수 있는 모양이다(고정 부분이 512토큰을 넘어야 적용).
3. 예시는 system 안에 글로 넣는다. `messages`에 가짜 턴으로 넣지 않는다(최근 6턴 창과 섞이고 치환본 기록처럼 보인다).
4. 버전: `prompts.py`에 `PROMPT_VERSION = "study-chat-v2"`. `Session.prompt_version` 칸은 **이미 있다**(`models.py:94`, 지금은 아무도 쓰지 않음). `start_session`에서 새 세션을 만들 때 적는다. 새 칸은 필요 없다.
5. 평가 스크립트 `backend/scripts/eval_prompts.py`(새 파일, 키 필요, pytest에는 넣지 않음): 고정 입력 20개 × 스타일 3종 × 반말/존댓말을 `build_prompt` → `AnthropicAdapter`로 돌려 CSV(입력 번호, 스타일, 답, 글자 수, 문장 수, 정답 문자열 포함 여부, source)를 남긴다. 입력은 합성 문장만. 코드로 채점: 정답 누출, 3문장 초과. 사람이 채점: 반말/존댓말 위반, 이름 묻기, 말투가 스타일 카드와 맞는지.

주의: `tests/test_prompts.py`가 system 문자열 일부를 검사한다. 순서를 바꾸면 그 기대값을 같이 고친다. 정답·forbidden·별명이 프롬프트에 없다는 기존 테스트는 그대로 통과해야 한다.

#### B4 live 설정 확정

지금: `LIVE_MAX_TOKENS = 1024`, `output_config={"effort": "low"}`, thinking 파라미터는 보내지 않는다. 코드 주석은 「thinking 끄기는 모델마다 400」이라 하고, 11-11 조사는 「Haiku 5.5는 끌 수 있다」고 한다. 둘 다 실측한 것이 아니다.

- 키가 생기면 같은 입력 10개로 (가) 지금 설정 (나) thinking 끔을 각각 돌려 지연 p50·최대, 출력 토큰, 400 여부를 잰다. 파라미터 이름과 허용 값은 `claude-api` 스킬로 먼저 확인한다.
- 400이 나면 `FallbackAdapter`가 조용히 대본으로 넘기므로, 측정할 때는 `AnthropicAdapter`를 직접 부른다.
- 결과와 고른 값을 계약 메모에 적고, 코드 주석을 사실에 맞게 고친다.

#### B5 강사 초안 파싱

`instructor.py` `_parse_draft(raw)` 맨 앞에서: 앞뒤 공백 제거 → ```` ``` ````로 시작하면 첫 줄과 마지막 펜스를 떼어 냄 → 첫 `{`부터 마지막 `}`까지만 잘라 `json.loads`. 실패하면 지금처럼 `None`(템플릿). 템플릿(`_template_body`)은 메모 끝에 마침표·물음표·느낌표가 없으면 마침표를 붙이고 다음 문장을 잇는다.
테스트: ```` ```json\n{"body":"…"}\n``` ````, 앞뒤에 설명 글이 붙은 경우, 마침표 없는 메모.

#### B6 신원 확인 코드 모으기

지금: 역할별 의존성이 세 개다 — `api.py` `current_child` → `Student`, `guardian.py` `current_guardian_child` → `Student`, `instructor.py` `current_instructor` → `str`. 헤더 유무·역할 확인이 세 번 복제돼 있고, 신원 해석은 모두 `actors.py` `resolve_actor`를 거친다.

- `actors.py`에 `async def actor_from_request(db, want_role, x_demo_role, x_demo_actor, authorization=None) -> Actor`를 만들어 「헤더 없음 401 → 역할 다름 403 → `resolve_actor`」를 한곳에 둔다. 세 의존성은 이 함수를 부르는 2~3줄짜리 껍데기로 남긴다(반환형이 달라 하나로 합칠 수는 없다).
- 로그인을 넣을 때는 이 함수 안에서 `config.auth_mode()`를 보고 갈린다. 지금은 demo 한 갈래만 둔다.
- 오류 코드·문구는 바꾸지 않는다(테스트가 `no_actor`·`forbidden`을 본다).

#### B7 compat 답 제출이 `queued`일 때

`compat.py` `submitAnswer`는 `post_message` 결과의 `reply`를 `message`로 쓴다. 답 생성 중이면 `reply`가 `None`이다. 응답에 `queued: true`를 싣고 `message`는 빈 문자열, `correct`는 저장된 판정대로 준다. 프론트는 `queued`면 화면을 넘기지 않고 `pending`을 기다린다. 계약 메모에 한 줄.

#### B14 묵은 함정

- `errors.py`: `StarletteHTTPException` 처리기가 `JSONResponse`를 만들 때 `headers=exc.headers`를 넘긴다(405의 `Allow`).
- `pii.py:13`: 전화 정규식의 구분자를 `\s*[-–—.]?\s*`로 넓힌다. 테스트 `010 - 1234 - 5678`, `010–1234–5678`.
- `pii.py:25`: 별명이 치환 표시 낱말(「이름」·「전화」 등)과 같으면 별명 치환을 건너뛴다.

#### F5 강사 화면 연결 — 모양이 달라서 그대로는 안 붙는다

프론트가 부르는 것(`client.ts`)과 서버(`instructor.py`)의 차이:

| 프론트 함수 | 프론트가 기대하는 것 | 서버에 있는 것 | 차이 |
|---|---|---|---|
| `getTeacherToday()` | `TeacherToday {dateLabel, className, units[], students[{id, name, task, status, draftStatus}]}` | 학생 목록을 주는 API가 **없다** | compat에서 새로 조립해야 한다 |
| `assignTask(studentId, unit \| null)` | **단원 이름**으로 지정, `null`이면 해제. `TeacherToday` 반환 | `PUT /instructor/students/{sid}/today-task {problem_id}` — **문제 id**로 지정, 해제 없음 | 단원 → 문제 고르기, 해제 처리 필요 |
| `getMemo(studentId)` | `{memo: TeacherMemo, draft: Draft \| null}` | `GET /instructor/notes?student_id=` → `{note_id, draft{body, facts}, status}` 또는 null | 모양 변환 |
| `saveMemo(studentId, memo)` | 메모만 저장(초안 없이), 여러 번 가능 | 메모만 저장하는 API **없음**. `POST /instructor/notes`가 메모 저장과 초안 생성을 한 번에 하고, 같은 날 다시 부르면 **기존 노트를 그대로** 돌려준다(명세 3.4 「초안은 한 번, 재생성 없음」) | 아래 방식 |
| `createDraft(studentId)` | 저장된 메모로 초안 생성 | 위와 같음 | 아래 방식 |
| `updateDraft(studentId, comment)` | 고친 코멘트를 서버에 저장(승인 뒤에도 고치면 「승인 대기」로 돌아감) | **없음**. 서버는 승인할 때 `final_body`를 한 번 받는다 | 아래 방식 |
| `approveDraft(studentId)` | **본문 없이** 승인 | `POST /instructor/notes/{note_id}/approve {final_body, action}` | 서버가 고친 문장을 들고 있어야 함 |
| `getTeacherAlerts()` | 긴급 알림 목록 | 11-15는 강사 알림 없음(결정) | 빈 배열 |
| `getUnits`·`saveUnits`·`getResults` | 범위·결과 화면 | 없음 | mock 유지 |

붙이는 방식(권장: compat에 추가, 서버 규칙은 그대로):

- **`GET /compat/teacher/today`**: `Student` 전체를 읽는다(데모는 1명). `units`는 `api.py`의 `TAG_NAME` 값 4개. `task`는 `today_task_date`가 오늘이면 그 문제의 태그 이름, 아니면 null. `status`: 오늘 세션 없음 + 지정 없음 → `지정 전`, 지정만 → `지정됨`, 세션이 study·chat·bridge → `진행 중`, ended·crisis → `완료`. `draftStatus`: 오늘 노트가 없으면 null, `draft` → `승인 대기`, `published` → `승인됨`. `className`은 고정 문자열.
- **`PUT /compat/teacher/students/{id}/task {unit}`**: 단원 이름 → 태그(`TAG_NAME` 역방향) → 그 태그의 문제 하나(id 순서로 첫 문제)를 골라 `put_today_task`와 같은 대입을 한다. `unit: null`이면 `today_task_problem_id`·`today_task_date`를 비운다. 주의: 아이가 오늘 세션을 이미 시작했으면 그 세션의 문제는 바뀌지 않는다(지금 서버 동작).
- **메모·초안**: 서버에 「초안 없는 메모」 상태가 없다. 다행히 화면은 두 함수를 **연달아** 부른다(`screens/teacher/Today.tsx:76-77`: `saveMemo` 다음 줄이 `createDraft`). 그래서 프론트를 고치지 않고 이렇게 맞춘다.
  - `PUT …/memo`: `post_note`를 부른다(메모 저장 + 초안 생성이 한 번에 일어난다. LLM을 부르므로 최대 20초). 오늘 노트가 이미 있으면 서버 규칙대로 기존 노트를 그대로 둔다 — 같은 날 메모를 다시 고쳐도 반영되지 않는다(명세 3.4). 응답은 204.
  - `POST …/draft`: 오늘 노트를 읽어 `Draft` 모양으로 돌려준다. 노트가 없으면 409.
  - 한계: 화면이 나중에 「메모만 저장」 버튼을 따로 두면 이 방식이 깨진다. 그때는 `InstructorNote.status`에 `"memo"`(초안 전) 상태를 추가해야 하고, 명세 4.2를 먼저 고친다.
  - `GET …/memo`: 오늘 노트가 있으면 `{memo: {covered, stuck, homework, note: memo_redacted}, draft}`, 없으면 빈 메모와 `draft: null`.
  - `PUT …/draft {comment}`: 노트가 `draft` 상태일 때만 `draft_body`를 PII 치환해 덮어쓴다(`instructor.py`에 작은 함수 `update_draft_body` 추가). `published`면 409 `note_closed`. 초안 「재생성」이 아니라 사람이 고친 문장을 저장하는 것이지만, 명세 3.4·4.4 #9에 한 줄 적고 시작한다.
  - `POST …/draft/approve`: 오늘 노트의 `draft_body`를 `final_body`로 넣어 `approve_note(action="publish")`.
- **`Draft` 모양 채우기**: `scope` = 오늘 지정된 단원 이름(없으면 `covered`), `amount` = 오늘 세션이 있으면 `{푼 수}/1문제`·없으면 `미완료`, `mode` = `힌트 {hint_level}번`(세션 없으면 `-`), `comment` = `draft_body`(승인 뒤에는 `final_body`), `status` = 위 `draftStatus`.
- **헤더**: 강사 요청에는 `X-Demo-Role: instructor`, `X-Demo-Actor: demo-instructor`. 테스트 패치 v1은 주소(`#/guardian`)로 역할을 정했다. 실제로는 로그인한 계정의 역할(`useAuth().me.role`)로 정한다: student → child, guardian → guardian, teacher → instructor.
- `api/index.ts`의 연결 목록에 `getTeacherToday`, `assignTask`, `getMemo`, `saveMemo`, `createDraft`, `updateDraft`, `approveDraft`, `getTeacherAlerts`를 더한다.

테스트(`tests/test_compat.py`): 메모 → 초안 → 고치기 → 승인 → 보호자 카드에 고친 문장, 승인 뒤 고치기 409, 단원 지정 → 아이 `student/home`에 반영, 아이 헤더로 강사 경로 403.

#### F1~F4 프론트 연결 (패치 2개가 출발점)

- `src/api/http.ts` `call()`: 역할 헤더 2개(위), 오류는 `j.message ?? j.detail`.
- `src/api/index.ts`: `const mixed = { ...mockApi }` 뒤 연결할 함수 이름 목록만 `httpApi` 것으로 덮는다(패치 v1 그대로). 지금 목록 17개 + 강사 8개 + `reply`.
- `src/screens/student/Solve.tsx`: `p.text`가 있으면 식 위에 문장. `p.left && p.right`일 때만 식을 그리고 기호는 `p.op` 그대로(`+`·`−`·`÷`). `types.ts`의 `ProblemView.op`에 `'÷'`, `text?: string`, `left`·`right`를 nullable로.
- `src/components/Fraction.tsx`: 값이 없으면 아무것도 그리지 않는다. `App.tsx`에 오류 경계 하나(깨지면 「다시 시도」).
- `src/screens/student/Chat.tsx`(패치 v2): 조각을 배열에 모으고 마지막 입력 뒤 1.5초에 `texts`로 한 번 전송(5개가 차면 즉시). `queued`면 기다림 표시만 유지, `pending`이면 `POST …/reply`를 `pending`이 false가 될 때까지(최대 3회). 답을 기다리는 동안 힌트 버튼은 끈다. 입력창은 끄지 않는다.
- 체험 계정과 서버 배우 맞추기: mock의 `jiwoo`·`jiwoo_mom`·`kim_teacher`를 서버의 `demo-child-minsu`·`demo-guardian-minsu`·`demo-instructor`에 짝짓는다. 화면 이름이 서버 이름(민수)으로 나오므로 체험 계정 표시 이름도 맞춘다.

#### F6 리셋·빠른 모드

서버: `POST /api/v1/demo/reset`, 헤더 `X-Demo-Token`, 본문(전부 선택) `{style, honorific, polite, timer_scale}`. `timer_scale`을 생략하면 환경 변수 `TIMER_SCALE`로 돌아간다. compat 밖의 기본 경로다.

- 프론트 `resetDemo()`: `VITE_API_BASE`에서 `/compat`을 뗀 주소로 위 경로를 부른다. 빠른 모드가 켜져 있으면 `timer_scale: 20`(프론트 주석의 「20배」와 같게)을 싣는다.
- 토큰은 빌드에 넣지 않는다. 체험 시트에 토큰 입력칸을 두고 `sessionStorage`에만 둔다. 급하면 대본에 curl 한 줄(`docs/deploy_render_v0.1.md`에 예시).
- 리셋 뒤에는 프론트의 mock 저장소(localStorage)도 같이 지워야 화면이 어긋나지 않는다(mock의 `resetDemo`를 이어서 부른다).
- `setDemo({fast})`만 따로 누르는 경우는 서버에 대응이 없다. 리셋할 때만 적용된다고 화면에 적거나 버튼을 리셋과 합친다.

#### 약속 화면 동의 저장 (작은 빈틈)

`Student.consent` 칸은 **있다**(`models.py:54`, 데모 아이는 true). 다만 이 값을 바꾸는 API가 없고 compat `getStudentHome`은 `needsOnboarding`을 늘 false로 준다. 최소안: `POST /compat/student/promise` → `consent = True`, `needsOnboarding = not student.consent`. 약속 화면을 시연에서 보여 주려면 리셋 본문에 `consent: false` 선택 칸을 더한다(기본 true).

#### 로그인 최소안 (결정 1이 난 뒤)

- 테이블(`models.py`): `Account(id, role[child/guardian/instructor], login_id UNIQUE, password_hash, nickname, student_id NULL)`, `GuardianLink(guardian_account_id, student_id, consent_at)`, `AuthIdentity(provider, subject, account_id, UNIQUE(provider, subject))`(빈 테이블, 소셜 로그인 자리). 아이 계정의 `student_id`는 기존 `Student.id`.
- 토큰: `pyjwt` HS256, `{sub: account_id, role, exp: now + 7일}`, 비밀키 `AUTH_SECRET`. DB에 저장하지 않으므로 Render가 재시작해도 유효하다(체험 계정 id를 고정 문자열로 만들기 때문). 강제 로그아웃은 못 한다(이후 과제).
- 경로(`backend/app/auth.py` 새 파일): `POST /api/v1/auth/login {loginId, password}` → `{token, me}`, `GET /api/v1/me`, `POST /api/v1/auth/logout`(200만), `GET /api/v1/demo/accounts`(아이디·역할·표시 이름). 프론트 경로 이름과 같게 compat에도 건다.
- 체험 계정: `demo.py` `ensure_demo_actors`와 리셋에서 함께 만든다. 비밀번호는 환경 변수 `DEMO_PASSWORD`를 `argon2-cffi` `PasswordHasher`(기본값이 argon2id)로 해시. 환경 변수가 없으면 로그인 모드에서 기동 실패로 둔다(빈 비밀번호 방지).
- 신원: B6의 `actor_from_request`에서 `AUTH_MODE=login`이면 `Authorization: Bearer`를 검증해 계정 → 역할·id → `resolve_actor`. 보호자는 `GuardianLink`로 아이를 찾는다(`GUARDIAN_TO_CHILD` 상수 대체). `demo`면 지금 헤더. pytest 기본은 demo라 기존 테스트는 그대로.
- 실패 제한: 아이디 기준 5회 실패 → 15분 잠금, 프로세스 메모리 dict. 오류 문구는 「아이디 또는 비밀번호가 달라요」 하나로. (5회·15분·7일은 설계 판단값이다.)
- 프론트: 로그인 응답의 토큰을 `lib/storage.ts`로 저장, `call()`에 `Authorization` 헤더, 401이면 토큰을 지우고 로그인 화면. 가입·아이디 찾기·재설정은 mock 그대로.
- CORS는 지금 설정(`allow_headers=["*"]`, 쿠키 없음)으로 된다.
- 테스트: 로그인 성공·실패·잠금, 토큰 없음·만료·위조 401, 보호자 토큰으로 아이 경로 403, `AUTH_MODE=login`에서 데모 헤더 거부.

#### 발췌 정책 (결정 2가 난 뒤, 「원문 없음」으로 갈 때)

발췌가 나가는 곳은 **세 군데**다.

1. `api.py` `_crisis`: `build_excerpt(...)`로 만들어 `Alert.excerpt`에 저장하고, `/messages` 응답 `crisis.excerpt`로 아이 화면에도 준다.
2. `guardian.py` `_guardian_excerpt` → `GET /guardian/today`의 `alert.excerpt`.
3. `compat.py` `getAlerts`·`sendChat`의 crisis.

바꾸는 순서: 명세 3.2·4.2·4.3·4.4 #4·#11·부록 E와 결정 DB → `_crisis`가 발췌를 만들지도 저장하지도 않게(`Alert.excerpt`는 NULL 허용으로 남김) → 응답은 `{level: "긴급", category: "안전", action: 고정 안내문, hotlines}` → compat `getAlerts`에서 `excerpt` 제거 → 테스트의 발췌 기대값 수정. 발췌를 유지하기로 하면 반대로 프론트 문구(F8)를 고치고, `build_excerpt`가 같은 단계(`phase_started_at` 이후) 턴만 쓰게 한다(B8).

#### 체험 계정 여러 쌍 (결정 8이 난 뒤)

`demo.py`는 `DEMO_CHILD_ID` 하나에 묶여 있다(`_wipe_demo_child`, `_write_day3_student`, `ensure_demo_actors`, `ACTORS`). `actors.py`에 `DEMO_PAIRS = [(child_id, guardian_id, 표시 이름), …]`를 두고 위 함수들이 `child_id`를 인자로 받게 한다. `GUARDIAN_TO_CHILD`는 이 목록에서 만든다. 리셋 본문에 `actor`(선택)를 받아 그 아이만 지우고, 없으면 전체. 강사는 한 명을 같이 쓴다.

## 8. 아직 확인하지 못한 것

- 진짜 LLM 답의 품질·지연·거절률, live 답에 정답이 새는지(키 없음)
- Render 실제 환경: 콜드 스타트, 슬립 복귀, 빌드
- 수다 10분 마감 자동 전환과 타이머 배율의 화면 동작
- 자연수 답(`3/1`) 판정의 화면 경로(데모 아이에게 3/8 문제만 배정됨)
- 실기기 터치, 키보드가 올라올 때 가림
- 카카오 PKCE 지원·테스트 앱 검수 여부, AWS Bedrock의 Claude 파인튜닝 현황(조사 문서의 「확인 필요」)

## 9. 이 문서의 근거

11-11에 돌린 점검 9건: 파이프라인 실앱 호출, 프론트↔백 구조 대조, 성호 구상 비판 검토, 로그인 조사, LLM 조사, 백엔드 로컬 실측(요청 52건), UI 실측 2회(스크린샷 133장), 자동 보안 검토 1건. 스크린샷과 실측 스크립트는 세션 임시 폴더에 있어 지워질 수 있다. 다시 필요하면 7절 방법으로 재현한다.
