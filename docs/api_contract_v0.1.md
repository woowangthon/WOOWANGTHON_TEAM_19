# API 계약 메모 v0.1 (프론트용, 2026-11-09)

정본은 `docs/spec_v0.4.md` 4.4. 이 메모는 API 13개를 모두 적는다.
스키마 원본은 서버의 FastAPI 자동 문서 `GET /openapi.json`(사람용 `/docs`)이다.

## 공통

- 기본 경로 `/api/v1`, JSON. 필드 이름은 snake_case.
- 아이 API(2·3·4·5·6·7·13번) 요청 헤더: `X-Demo-Role: child`, `X-Demo-Actor: <학생 id>`(시드 배우 고정 ID).
- 보호자 API(11번) 요청 헤더: `X-Demo-Role: guardian`, `X-Demo-Actor: <보호자 id>`. 서버가 대응표로 학생을 찾는다.
- 신원은 서버의 `resolve_actor` 하나가 푼다(MVP는 아래 데모 배우 대응표). 실서비스에서 계정·연결 테이블로 바뀌어도 헤더·응답 모양은 그대로다.

데모 배우 고정 ID(`POST /demo/reset`이 만든다, 합성 데이터). 서버가 켜질 때 데모 아이 행이 없으면 리셋 기본값(day3·EBSP·형·반말)으로 만들어 두므로, 배포 DB가 비어도 리셋 전에 바로 쓸 수 있다:

| 역할 | `X-Demo-Role` | `X-Demo-Actor` | 라벨 | 비고 |
| --- | --- | --- | --- | --- |
| 아이 | `child` | `demo-child-minsu` | 민수 | 학생 행 id. 아이 역할은 다른 학생 행 id도 받는다 |
| 보호자 | `guardian` | `demo-guardian-minsu` | 민수 보호자 | → 학생 `demo-child-minsu`. 대응표에 없는 id는 404 `guardian_not_found` |
| 강사 | `instructor` | `demo-instructor` | 강사 | 11-15는 비어 있지 않은 값이면 받는다 |
- 오류는 **모든 경로**에서 같은 모양이다. 분기는 `code`로 하고 `message`는 화면에 보여 줘도 되는 문장이다.

```json
{ "code": "session_finished", "message": "오늘은 이미 끝났어요. 내일 봐요.", "request_id": "3f2a…" }
```

| HTTP | code | 언제 |
| --- | --- | --- |
| 401 | `no_actor` | `X-Demo-Role`·`X-Demo-Actor` 중 하나라도 없음 |
| 403 | `forbidden` | 역할이 그 API의 역할(`child`·`guardian`·`instructor`)이 아님. 1번은 `X-Demo-Token` 없음·틀림 |
| 404 | `student_not_found` | `X-Demo-Actor`의 학생이 없음(보호자는 리셋 전이라 연결된 학생 행이 없을 때) |
| 404 | `guardian_not_found` | GET /guardian/today — `X-Demo-Actor`가 보호자 대응표에 없음 |
| 409 | `session_finished` | POST /sessions — 오늘 세션이 `ended` 또는 `crisis` |
| 409 | `no_task` | POST /sessions — 진행 중 세션도, 오늘 할 문제도 없음 |
| 404 | `session_not_found` | POST /sessions/{id}/messages — 세션이 없거나 다른 학생의 세션 |
| 409 | `session_finished` | POST /sessions/{id}/messages — 세션이 `ended` 또는 `crisis` |
| 409 | `hint_unavailable` | POST /sessions/{id}/messages — `study`가 아니거나 이미 `hint_level` 3 |
| 409 | `busy` | POST /sessions/{id}/messages — `kind: "hint"`인데 멘토 답을 만드는 중(11-11). 아무것도 저장되지 않는다. 답을 받은 뒤 다시 누르면 된다. `text`는 409가 아니라 흡수(`queued: true`)된다. 순번 충돌을 몇 번 다시 시도해도 실패하면 드물게 `text`에도 온다 |
| 409 | `nothing_to_reply` | POST /sessions/{id}/reply — 답 안 된 아이 조각이 없음 |
| 404 | `session_not_found` | 5·6·7번 — 세션이 없거나 다른 학생의 세션 |
| 409 | `session_finished` | 5·7번 — 세션이 `ended` 또는 `crisis` |
| 409 | `phase_not_allowed` | 5번 허용되지 않은 전이(정답 전·풀이 보기 전 등), 6번 `bridge`·`ended`가 아님, 7번 `bridge`가 아님 |
| 409 | `session_in_progress` | PUT /me/mentor — 오늘 세션이 `study`·`chat`·`bridge` |
| 404·405 등 | `http_error` | 없는 경로·메서드 |
| 422 | `invalid_request` | 요청 형식 오류(4번: `kind`가 틀림, `text`·조각 1000자 초과, 조각 6개 이상, `kind: "text"`인데 `text`·`texts`가 비어 있음 / 5번: `to`가 틀림 / 7번: 고를 수 없는 퀴즈 / 13번: 값이 틀림) |
| 500 | `internal_error` | 서버 오류. 내용은 싣지 않음 |

## 1. POST /api/v1/demo/reset

시연자 패널 전용. 헤더 `X-Demo-Token: <비밀>`(서버 환경변수 `DEMO_TOKEN`과 같아야 함). 역할 헤더는 필요 없다.

```json
{ "scenario": "day3", "style": "EQLC", "honorific": "unni", "polite": true, "timer_scale": 1 }
```

모든 칸 생략 가능(본문 자체도 생략 가능). 기본값은 `scenario: "day3"`, `style: "EBSP"`, `honorific: "hyung"`, `polite: false`(반말). `timer_scale`은 생략하면 서버 환경변수 `TIMER_SCALE`(없으면 1)을 따른다.

응답 200:

```json
{
  "ok": true,
  "actors": [
    { "role": "child", "id": "demo-child-minsu", "label": "민수" },
    { "role": "guardian", "id": "demo-guardian-minsu", "label": "민수 보호자" },
    { "role": "instructor", "id": "demo-instructor", "label": "강사" }
  ],
  "date": "2026-11-10"
}
```

- 리셋 뒤 상태(day3, 명세 4.8-3): 연속 3일(`/me/today`의 `streak_text`가 "3일째 같이 했어"), 오늘 할 것 `frac-div-nat-01`(3/4 ÷ 2, `source: "instructor"`), 미해결 오개념 2개(`frac-div-nat`·`frac-div-frac-diff`) + 해소 1개(`nat-div-nat`), 오늘 세션·강사 메모·알림 없음.
- 데모 아이의 세션·메시지·알림·오개념·강사 노트를 지우고 다시 만든다. 데모 배우가 아닌 학생은 건드리지 않는다. 두 번 불러도 같은 상태.
- `timer_scale`은 서버 프로세스 메모리에 둔다(수다 10분 ÷ 배율). 본문에 `timer_scale`이 없으면 앞 리셋이 정한 배율을 지우고 환경변수 `TIMER_SCALE`(없으면 1)로 돌아간다. 서버를 다시 켜도 환경변수로 돌아간다.
- 오류: 토큰 없음·틀림·서버에 `DEMO_TOKEN` 없음 403 `forbidden`(본문 검사보다 먼저). `scenario`가 `day3`가 아님, `style`·`honorific`이 목록 밖, `timer_scale` ≤ 0·숫자 아님 422 `invalid_request`.

## 12. GET /healthz (= GET /api/v1/healthz)

헤더 없음.

```json
{ "db": "ok", "llm_key": false, "llm_mode": "scripted", "tz": "Asia/Seoul" }
```

`db`는 `"ok"` \| `"error"`, `llm_key`는 키가 있는지만(bool), `llm_mode`는 `"live"` \| `"scripted"`.

## 2. GET /api/v1/me/today

빈 값도 같은 모양으로 온다(명세 4.8 4번). 키는 항상 4개.

시작 전:

```json
{
  "greeting": "안녕! 오늘도 같이 해 볼까?",
  "streak_text": "3일째 같이 했어",
  "today_task": { "problem_id": "frac-div-nat-01", "source": "instructor" },
  "session": null
}
```

진행 중(새로고침하면 이어서):

```json
{
  "greeting": "하던 거 이어서 해 볼까?",
  "streak_text": "3일째 같이 했어",
  "today_task": null,
  "session": { "id": "…", "state": "study", "hint_level": 1 }
}
```

- `today_task.source`: `"instructor"`(강사 지정) \| `"misconception"`(미해결 오개념 태그의 시드 문제).
- `today_task`는 **세션이 있으면 null**, 할 문제가 없어도 null.
- `session.state`: `"study"` \| `"chat"` \| `"bridge"` \| `"ended"` \| `"crisis"`. `hint_level` 0~3.
- 수다 마감(`deadline_at`)이 지났으면 서버가 먼저 `bridge`로 바꾼 뒤 돌려준다.
- `ended`·`crisis`면 `greeting`이 "…내일 봐!" 문장이다.

## 3. POST /api/v1/sessions

본문 없음. 응답 200(새로 만들 때와 진행 중 세션을 돌려줄 때 같음).

```json
{
  "session_id": "…",
  "state": "study",
  "hint_level": 0,
  "problem": { "id": "frac-div-nat-01", "text": "3/4 ÷ 2 를 계산해 보세요." }
}
```

- 진행 중이면 **그 세션**을 그대로 돌려준다(두 번 눌러도 안전).
- 끝났으면 409 `session_finished`, 할 문제가 없으면 409 `no_task`.
- `problem`에는 `id`·`text`만 온다. 정답·힌트·풀이는 오지 않는다.
- 주의: `/me/today`는 `session.id`, 여기는 `session_id`(명세 표 그대로).

## 4. POST /api/v1/sessions/{id}/messages

`{id}`는 POST /sessions의 `session_id`. 아이 헤더 필요. **비스트리밍** — 답은 한 번에 온다. 기다리는 동안 「생각 중…」. **입력은 열어 둔다**(1.5초 묶기 + 서버 흡수, 11-11 성호 결정, 결정 DB 등록 대기 — 아래 「끊어 보내기」).

요청:

```json
{ "kind": "text", "text": "8분의 3" }
```
```json
{ "kind": "hint" }
```

```json
{ "kind": "text", "texts": ["음", "3/8", "맞아?"] }
```

- `kind`: `"text"`(아이가 쓴 말) \| `"hint"`(힌트 버튼, `text` 없음).
- `text`(한 조각) 또는 `texts`(1~5조각, 각 1000자 이하). 둘 다 오면 `texts`만 쓴다. 빈 조각은 버리고, 남는 게 없으면 422.

응답 200(키는 항상 8개):

```json
{ "reply": "…", "source": "live", "judge": "wrong", "hint_level": 1, "state": "study", "crisis": null, "queued": false, "pending": false }
```

- `reply`: 멘토 답. `queued: true`이면 `null`.
- `source`(11-11, B1): 그 답을 누가 만들었나. `"live"` = LLM 공급자, `"scripted"` = 대본 줄(LLM 모드가 scripted이거나 live가 실패·20초 초과해 폴백), `"fixed"` = 대본에도 없어 고정 문장이거나 🔴 고정 문장. `reply`가 `null`이면(queued·버려진 답) `null`. 화면 배지는 재하와 합의.
- `queued`: `true`면 앞의 답을 만드는 중이라 이 조각은 **저장·🔴 검사·판정만** 하고 답은 아직 없다. 「생각 중…」을 그대로 둔다.
- `pending`: `true`면 이 답을 만드는 사이 새 조각이 흡수됐다 → 바로 `POST /sessions/{id}/reply`를 부른다.

- `judge`: `"correct"` \| `"wrong"` \| `null`. **`study`의 `text`만 조각마다 판정**한다(조각 전체가 답 형식일 때만. "3/8 맞아?"는 판정 안 함). 응답의 `judge`는 이 요청 조각들의 요약: correct가 하나라도 있으면 correct, 아니면 wrong이 있으면 wrong, 아니면 null. 숫자·분수 형식(3/8, 0.375, 8분의 3, 1 1/2, 3÷8, 정수)이 아니면 `null`(판정 없이 코칭). `hint`·`chat`·`bridge`는 항상 `null`.
- 정답이어도 `state`는 `study` 그대로다. 「수다할래?」 화면을 띄우고 고른 결과로 5번 API(`/phase`)를 부른다. 풀이 보기(`hint_level` 3) 뒤에도 같다.
- `hint_level`: `kind: "hint"`마다 +1(0→1 힌트1, 2 힌트2, 3 풀이 보기). 3에서 또 누르면 409 `hint_unavailable` — 3이면 힌트 버튼을 숨긴다.
- `state`: 수다 마감이 지났으면 서버가 먼저 `bridge`로 바꾼 뒤 처리한다. 응답의 `state`를 보고 화면을 바꾼다.
- 아이가 쓴 말은 화면이 그대로 들고 있다. 서버에는 전화·이메일·별명·학교 이름을 바꾼 치환본만 남는다.

🔴(자해·자살 키워드)일 때 — LLM을 부르지 않는다:

```json
{
  "reply": "지금 한 말이 걱정돼서, 어른에게 알릴게",
  "judge": null,
  "hint_level": 0,
  "state": "crisis",
  "source": "fixed",
  "crisis": { "excerpt": "아이: 몰라 / 친구1: … / 아이: …", "hotlines": ["109", "1388"] }
}
```

- `crisis`가 `null`이 아니면 🔴 화면(부록 E)으로 간다: 고정 문장, `excerpt` 그대로, 109·1388 전화 버튼, 「오늘은 여기까지 하자」. 다리 놓기 없음.
- `excerpt`는 🔴 문장과 그 앞 2턴의 치환본, 300자 이하(넘치면 앞이 `…`로 잘림). 보호자 카드에도 싣는다(결정 11-10·11-11).
- 이 세션의 이후 요청은 409 `session_finished`.
- 🔴은 조각마다 즉시 본다. 앞 답을 만드는 중이어도 이 조각의 응답이 바로 위 모양이고, 늦게 끝난 앞 요청의 답은 버려진다(그 응답은 `reply: null`, `state: "crisis"`, `crisis`가 채워짐).

### 끊어 보내기 (11-11 성호 결정, 결정 DB 등록 대기)

1. 아이가 보낸 말은 화면에 바로 띄우고, **약 1.5초** 안에 이어 보낸 조각을 모아 `texts`로 한 번에 보낸다(최대 5개, 넘치면 다음 묶음).
2. 응답이 `queued: true`면 답을 기다리는 중이다. 「생각 중…」을 유지하고 아무것도 다시 보내지 않는다(앞 요청의 응답이 답을 가져온다).
3. 응답이 `pending: true`면 `POST /sessions/{id}/reply`(본문 없음)를 부른다. 그 응답도 `pending: true`면 한 번 더.
4. 힌트 버튼은 답을 기다리는 동안 누르면 409 `busy` → 답이 온 뒤 다시.

## 4a. POST /api/v1/sessions/{id}/reply

본문 없음. 답 안 된 아이 조각 전부에 멘토 답 1개. 응답은 4번과 같은 8개 키(`judge`는 다룬 조각들의 요약, `source`도 같은 뜻).
- 다른 요청이 답을 만드는 중이면 `queued: true`(LLM 안 부름).
- 답할 조각이 없으면 409 `nothing_to_reply`. 끝난 세션이면 409 `session_finished`.

## 5. POST /api/v1/sessions/{id}/phase

아이 헤더 필요. 「수다할래?」 예 → `chat`, 끝낼래 → `bridge`. 수다 끝내기 버튼도 이것(`to: "bridge"`).

```json
{ "to": "chat" }
```

응답 200:

```json
{ "state": "chat", "deadline_at": "2026-11-09T21:10:00+00:00", "streak_days": 3, "streak_text": "3일째 같이 했어" }
```

- 허용 전이: `study` → `chat`·`bridge`(정답을 한 번이라도 맞혔거나 `hint_level` 3일 때만), `chat` → `bridge`. 그 밖은 409 `phase_not_allowed`.
- `deadline_at`: `chat`이면 수다 마감(ISO 8601, UTC), 그 밖은 `null`. 화면 타이머는 표시용이고 마감은 서버가 판정한다.
- **연속 +1은 `study`를 떠날 때 한 번만.** `chat` → `bridge`에서는 늘지 않는다. 어제 했으면 +1, 오늘 이미 셌으면 그대로, 끊겼으면 1.
- 지금 상태와 같은 `to`(예: 수다 마감 직후 「끝내기」 — 서버가 이미 `bridge`로 바꿈)는 바꾸지 않고 200으로 지금 값을 돌려준다.
- `ended`·`crisis`면 409 `session_finished`, 없거나 남의 세션이면 404 `session_not_found`.

## 6. GET /api/v1/sessions/{id}/bridge

아이 헤더 필요. 「다리 놓기」 화면에서 부른다. `bridge`(또는 끝난 뒤 `ended`)에서만, 그 밖은 409 `phase_not_allowed`.

```json
{
  "quiz_options": [
    { "id": "frac-div-nat-02", "text": "6/7 ÷ 3 을 계산해 보세요." },
    { "id": "frac-div-nat-03", "text": "…" },
    { "id": "frac-div-nat-04", "text": "…" }
  ],
  "guardian_line": "오늘 분수 ÷ 자연수를 다시 풀었어요.",
  "summary": ["분수 ÷ 자연수 문제 1개, 힌트 1단계에서 정답", "막힌 곳 기록 없음", "미해결 없음"]
}
```

- `quiz_options`: 오늘 문제와 같은 태그의 시드 문제 3개(오늘 문제 제외, id 순). `id`·`text`만 — 정답·힌트 없음. 아이가 그중 하나를 보호자께 낸다.
- `guardian_line`: 어른에게 가는 한 줄 미리보기.
- `summary` 3줄: ① 푼 것(`정답` 또는 `풀이 보기`) ② 막힌 곳 한 구절(만들지 못하면 `"막힌 곳 기록 없음"`) ③ `"미해결: …"` 또는 `"미해결 없음"`. 수다 내용은 들어가지 않는다.
- 첫 호출 때 만들어 저장하고, 다시 부르면 같은 값이 온다.

## 7. POST /api/v1/sessions/{id}/end

아이 헤더 필요. 「다리 놓기」에서 확인을 누를 때. 퀴즈를 안 골라도 끝낼 수 있다.

```json
{ "quiz_problem_id": "frac-div-nat-03" }
```

응답 200:

```json
{ "state": "ended", "streak_text": "3일째 같이 했어" }
```

- `quiz_problem_id`: `null`(또는 생략) 또는 6번 `quiz_options`의 `id` 중 하나. 그 밖은 422 `invalid_request`.
- 6번을 부르지 않았어도 여기서 카드(요약·한 줄)를 만들어 저장한다. 연속은 바뀌지 않는다.
- `bridge`가 아니면 409 `phase_not_allowed`, 이미 끝났으면 409 `session_finished`.
- 끝난 뒤 `/me/today`는 `session.state: "ended"`와 「내일 봐」 인사를 돌려준다.

## 13. PUT /api/v1/me/mentor

아이 헤더 필요. 캐릭터 고르기 1장의 「시작하기」.

```json
{ "style": "EBSP", "honorific": "hyung", "polite": false }
```

- 응답 200은 요청과 같은 모양 그대로.
- `style`: `"EBSP"` \| `"EQLC"` \| `"DQSC"`, `honorific`: `"hyung"` \| `"unni"` \| `"friend"`, `polite`: `true`(존댓말) \| `false`(반말, JSON bool만). 틀리거나 빠지면 422 `invalid_request`.
- 오늘 세션이 `study`·`chat`·`bridge`이면 409 `session_in_progress`(대화 중에는 캐릭터를 바꾸지 않는다). 세션이 없거나 끝났으면 바꿀 수 있고 다음 세션부터 쓴다.

## 8. 강사 API 공통 (#8·#9·#10)

- 요청 헤더: `X-Demo-Role: instructor`, `X-Demo-Actor: <강사 id>`. 강사 테이블이 없어 11-15는 **역할만 확인**하고 actor는 비어 있지 않은지만 본다.
- 오류: 헤더 없음·빈 값 401 `no_actor`, 역할이 `instructor`가 아님 403 `forbidden`. 나머지는 위 「공통」 표와 같은 모양.
- 메모 칸·승인본은 서버가 PII 치환(`[전화]` `[이메일]` `[이름]` `[학교]`)한 뒤 저장한다. 응답에 오는 문장도 치환본이다.
- 날짜는 서울 날짜(`YYYY-MM-DD`). "오늘 노트"는 학생·서울 날짜로 찾는다.

## 8-1. POST /api/v1/instructor/notes

```json
{ "student_id": "…", "covered": "분수 ÷ 자연수", "stuck": "나눗셈을 곱셈으로 바꾸는 단계", "homework": "익힘책 24쪽", "memo": "힌트 한 번 뒤에 스스로 풀었음" }
```

응답 200(동기 생성):

```json
{
  "note_id": "…",
  "draft": {
    "body": "오늘 수업에서는 「분수 ÷ 자연수」 내용을 다뤘습니다. 「나눗셈을 곱셈으로 바꾸는 단계」 부분에서 조금 어려워했습니다. 선생님 메모: 힌트 한 번 뒤에 스스로 풀었음 다음 시간에 한 번 더 확인하겠습니다.",
    "facts": { "homework": "익힘책 24쪽", "score": null }
  },
  "status": "draft"
}
```

- 4칸 모두 문자열(각 2000자 이하), 빈 문자열 허용. `student_id`가 없으면 404 `student_not_found`.
- `draft.body`: 어댑터 초안(JSON `{"body"}`), 실패·빈 응답이면 **템플릿(메모 3칸을 문장으로)**. 지금은 live가 없어 템플릿이 기본이다. 숙제는 본문에 넣지 않고 `facts.homework`로 간다. `score`는 항상 `null`.
- **같은 학생·같은 날 두 번째 POST는 새로 만들지 않고 기존 노트를 그대로 돌려준다**(재생성 없음, 명세 3.4). 새로 보낸 칸은 반영되지 않는다.

## 8-2. GET /api/v1/instructor/notes?student_id=…

오늘 노트가 있으면 8-1과 같은 모양(`status`는 `draft` \| `published` \| `skipped`), 없으면 `null`. 학생이 없으면 404 `student_not_found`.

## 9. POST /api/v1/instructor/notes/{note_id}/approve

```json
{ "final_body": "고친 문장", "action": "publish" }
```

응답 200 `{ "status": "published" }` 또는 `{ "status": "skipped" }`.

- `action`: `"publish"`(고쳐서 승인 → 보호자 카드로) \| `"skip"`(보내지 않음). 그 밖의 값은 422 `invalid_request`.
- `publish`는 `final_body`가 공백뿐이면 422 `invalid_request`. `skip`이면 `final_body`는 무시한다(생략 가능).
- 노트가 없으면 404 `note_not_found`, 이미 `published`·`skipped`면 409 `note_closed`.

## 10. PUT /api/v1/instructor/students/{sid}/today-task

```json
{ "problem_id": "frac-div-nat-01" }
```

응답 200 `{ "problem_id": "frac-div-nat-01", "assigned_date": "2026-11-10" }`.

- 다시 지정하면 덮어쓴다. 다음 `POST /sessions`가 세션으로 옮기고 비운다.
- 학생이 없으면 404 `student_not_found`, 문제가 없으면 404 `problem_not_found`.

## 11. GET /api/v1/guardian/today

헤더 `X-Demo-Role: guardian`, `X-Demo-Actor: demo-guardian-minsu`. 키는 **항상 4개**, 없으면 `null`(명세 4.8-4).

빈 카드:

```json
{ "alert": null, "child_line": null, "quiz": null, "instructor_comment": null, "homework": null }
```

다 찬 카드:

```json
{
  "alert": { "created_at": "2026-11-09T21:00:00+00:00", "excerpt": "(±2턴 치환본, 300자 이하)", "hotlines": ["109", "1388"] },
  "child_line": "오늘 분수 ÷ 자연수를 다시 풀었어요.",
  "quiz": { "text": "3/4 ÷ 2 를 계산해 보세요." },
  "instructor_comment": "(강사가 승인한 문장)",
  "homework": "(숙제 칸 그대로, 치환본에서 이름만 되돌림)"
}
```

- 「오늘」은 서울 날짜. `created_at`은 UTC ISO 8601(화면에서 서울 시각으로 바꿔 "오늘 {시각} 위험 신호가 있었어요").
- `alert`: 그 학생의 오늘 🔴 알림 중 가장 최근 1건. 있으면 카드 맨 위 빨간 줄. 발췌(`excerpt`)를 싣는다(결정 11-10·11-11).
- `child_line`: 오늘 세션이 `ended`(정상 종료)일 때만 보호자 한 줄. 진행 중·`crisis`면 `null`.
- `quiz`: 아이가 고른 퀴즈 문제의 `text`. 정답은 오지 않는다.
- `homework`(11-13): 오늘 강사 노트가 `published`일 때 사실 칸의 숙제(부록 D). 승인 전·빈 칸은 `null`.
- `instructor_comment`: 오늘 강사 노트가 `published`일 때 승인본. 초안·건너뜀·노트 없음은 `null` → 프론트가 **"선생님이 확인하면 여기에 와요"**를 보여 준다.
- 대화 내용은 어떤 경우에도 오지 않는다(명세 3.3).
- 오류: 헤더 없음 401 `no_actor`, 역할이 `guardian`이 아님 403 `forbidden`, 대응표에 없는 보호자 404 `guardian_not_found`, 리셋 전이라 학생 행이 없음 404 `student_not_found`.

## compat (11-15까지 임시)

프론트 v0.5(`src/api/http.ts`·`src/types.ts`)를 경로 수정 없이 붙이는 호환 라우터. 코드 `backend/app/compat.py`, 테스트 `backend/tests/test_compat.py`.
프론트는 `VITE_API_BASE=<서버>/api/v1/compat`. 판단(판정·힌트·전환·마감·🔴)은 새로 만들지 않고 위 #2~#7·#11·#13 핸들러와 `state_machine`을 그대로 부른다. 응답은 camelCase(프론트 타입 그대로).

| 프론트 함수 | 경로 (`/api/v1/compat` 아래) | 내부 |
| --- | --- | --- |
| getStudentHome | GET /student/home | `_today_session`·`_today_task`(#2와 같은 규칙). 출석표는 `streak_days`·`last_streak_date`로 거꾸로 셈 |
| getMentor / saveMentor | GET·PUT /student/mentor | #13 `put_mentor`. 같이 풀어주는↔EBSP, 들어주는↔EQLC, 짚어주는↔DQSC · 형/언니/친구↔hyung/unni/friend · 존댓말↔polite. `animal`은 저장 칸이 없어 받기만 하고 GET은 `null` |
| getActiveSession | GET /sessions/active | 오늘 세션(마감 전이 먼저) 또는 `null` |
| startSession | POST /sessions `{difficulty}` | #3 `start_session`. 난이도는 시드에 없어 버림 |
| getProblem | GET /sessions/{id}/problem | 풀기 단계면 문제, 아니면 `null`. 정답·풀이 없음 |
| submitAnswer | POST /sessions/{id}/answer `{problemId, numerator, denominator}` | `"{n}/{d}"`로 #4 `post_message(kind=text)` → 저장된 `judge`. 앞 답을 만드는 중이면 판정만 하고 `message: ""`·`queued: true`(`correct`는 저장된 판정대로) — **`queued`면 화면을 넘기지 말고 「생각 중…」을 유지**, 앞 요청의 답이 오고 `pending: true`면 `/reply`(B7). 응답에 `source`(#4와 같은 뜻, `queued`면 `null`) |
| requestHint | POST /sessions/{id}/hint | `press_hint`(전이 2). 힌트 1·2만. 시드 `hint1`·`hint2` 문장 |
| showSolution | POST /sessions/{id}/solution | 힌트 2개를 쓴 뒤에만 `press_hint` → hint_level 3(오개념 open). 시드 `solution` |
| afterStudy | POST /sessions/{id}/after-study `{choice}` | #5 `post_phase` (chat→chat, skip→bridge). 연속 +1은 여기서 한 번 |
| getChat | GET /sessions/{id}/chat | 수다 단계(phase_started_at 이후) 치환본만. 풀이 단계 메시지는 싣지 않음 |
| sendChat | POST /sessions/{id}/chat `{text}` 또는 `{texts}` | #4 `post_message`. 🔴이면 `crisis: true` + `hotlines`. 응답에 `queued`·`pending`·`source`(#4와 같은 뜻, `queued`면 `reply: ""`·`source: null`). 빈 말은 422, 끝난 세션(`ended`·`crisis`)은 409 `session_finished`(11-11). 수다가 아닌 진행 중 단계면 전처럼 빈 답 |
| (답 더 받기) | POST /sessions/{id}/reply | #4a. 응답은 sendChat과 같은 모양 |
| endChat | POST /sessions/{id}/chat/end | #5 `post_phase(to=bridge)` |
| getWrap | GET /sessions/{id}/wrap | #6 `get_bridge`. `aiLine`=보호자 한 줄, `quizOptions`=같은 태그 시드 3개의 문장 |
| submitWrap | POST /sessions/{id}/wrap `{hardPoint, quiz}` | 퀴즈 문장→id로 바꿔 #7 `post_end`. `hardPoint`는 칸이 없어 버림 |
| getGuardianToday | GET /guardian/today | #11 `guardian_today` + 세션 숫자 |
| getAlerts | GET /guardian/alerts | Alert 행 목록. **발췌 ±2턴·300자 그대로** `excerpt`로 실음 |
| acceptPromise | POST /student/promise | `Student.consent = true`, 204. `getStudentHome.needsOnboarding = not consent`(11-11). 데모 리셋은 consent true라 리셋 뒤에는 약속 화면이 안 나온다 |

**강사 경로 (11-11).** 헤더 `X-Demo-Role: instructor`·`X-Demo-Actor: demo-instructor`. 아이·보호자 헤더면 403 `forbidden`. 내부는 #8·#9·#10 그대로(초안 1회·재생성 없음).

| 프론트 함수 | 경로 (`/api/v1/compat` 아래) | 내부 |
| --- | --- | --- |
| getTeacherToday | GET /teacher/today | `Student` 전체 → `TeacherToday {dateLabel, className, units[], students[{id, name, task, status, draftStatus}]}`. `units` = `TAG_NAME` 값 4개. `task` = 오늘 지정 문제의 단원 이름 또는 `null`. `status`: 지정 전 / 지정됨 / 진행 중(study·chat·bridge) / 완료(ended·crisis). `draftStatus`: 오늘 노트 없으면 `null`, draft → 승인 대기, published → 승인됨 |
| assignTask | PUT /teacher/students/{id}/task `{unit}` | 단원 이름 → 태그 → 그 태그의 id 순 첫 문제를 #10과 같이 대입. `unit: null`이면 지정 해제. 없는 단원은 422. 아이가 오늘 세션을 이미 시작했으면 그 세션 문제는 그대로. 응답은 `TeacherToday` |
| getMemo | GET /teacher/students/{id}/memo | 오늘 노트 → `{memo: {covered, stuck, homework, note}, draft: Draft \| null}`. 노트 없으면 빈 메모·`null`. 메모는 치환본 |
| saveMemo | PUT /teacher/students/{id}/memo `{covered, stuck, homework, note}` | #8 `post_note`(메모 저장 + 초안 생성 한 번, LLM 최대 20초). 오늘 노트가 이미 있으면 그대로 둔다(같은 날 메모 다시 고쳐도 반영 안 됨, 명세 3.4). 204 |
| createDraft | POST /teacher/students/{id}/draft | 생성하지 않고 오늘 노트를 `Draft`로 읽기만. 노트 없으면 409 `no_note` |
| updateDraft | PUT /teacher/students/{id}/draft `{comment}` | `draft` 상태에서만 `draft_body`를 PII 치환해 덮어씀(재생성 아님). 승인·보내지 않음 뒤면 409 `note_closed`, 빈 문장 422. 응답 `Draft` |
| approveDraft | POST /teacher/students/{id}/draft/approve | 오늘 노트의 `draft_body`를 `final_body`로 #9 `approve_note(action=publish)`. 응답 `Draft`(승인됨). 보호자 카드 `teacherComment`에 그 문장 |
| getTeacherAlerts | GET /teacher/alerts | 빈 배열(11-15는 강사 알림 없음, 결정 11-09) |

`Draft` 채우기: `studentId`·`studentName`(별명), `scope` = 오늘 지정 단원(없으면 메모 `covered`), `amount` = 오늘 세션이 있으면 `{푼 수}/1문제` 아니면 `미완료`, `mode` = `힌트 {hint_level}번`(세션 없으면 `-`), `comment` = `draft_body`(승인 뒤 `final_body`), `status` = 승인 대기 | 승인됨.

단계 대응: study → `solve`(정답이거나 hint_level 3이면 `transition`), chat → `chat`, bridge → `wrap`, ended → `done`, crisis → `crisis`.
힌트: `hintsLeft = 2 − hint_level`, `canShowSolution = hint_level == 2`. 오답이어도 힌트를 자동으로 주지 않는다(`autoHint: null`, 명세 3.2). `numeratorOk`·`denominatorOk`는 정답일 때만 `true`(부분 판정 없음).
오류: 기존 `{code, message, request_id}`에 이 라우터만 `detail`(= message)을 덧붙인다.

**프론트가 고쳐야 할 것**
1. `src/api/http.ts` `call()` — 모든 요청에 `X-Demo-Role`(child | guardian)·`X-Demo-Actor`(`demo-child-minsu` | `demo-guardian-minsu`) 헤더. 없으면 401 `no_actor`.
2. `src/screens/student/Solve.tsx` — 시드는 **나눗셈**이다. `op`가 `"÷"`로 오는데 지금은 `+`가 아니면 `−`를 그린다. `ProblemView.text`(문장) 필드를 추가해 보여 주고, `left`·`right`가 `null`인 문제(`(1 + 3/4) ÷ 2/3`)는 문장만 보여 준다. 자연수는 `[n, 1]`로 온다. `types.ts`의 `op` 유니온에 `'÷'`, `left`·`right`에 `| null`.
3. 같은 화면 — 한 세션 한 문제(`total: 1`), 힌트는 2개(점 3개 중 2개), 3단계는 「풀이 같이 보기」. 틀려도 자동 힌트 없음.
4. `Wrap.tsx` — `hardChips`가 빈 배열로 온다(어려웠던 점 칸이 명세·DB에 없음). 섹션을 숨기거나 그대로 둔다.
5. `useCountdown` — `remainingSec`(풀기)는 표시용(서버 마감 없음). 수다 10분만 서버가 판정한다.
6. 위기 화면 — `ChatReply.hotlines`(109·1388)를 추가로 준다.
7. 보호자 알림 — 응답에 `excerpt`가 있다. 프론트의 「원문 없이 분류·긴급도·행동 안내」 모양과 다르다(11-10 회의 안건 2 결정 전까지 그대로). `level`·`category`·`action`은 🔴 고정값.
8. 범위 밖 함수(로그인·학원·씨앗·상점·`getUnits`·`saveUnits`·`getResults`·`getRecords`·`ackAlert`·`closeAlert`·`/demo/settings`)는 compat에 없다 → mock 유지. 함수별로 mock/http를 섞는 장치가 필요하다. `restricted false`·`inClass true`·`seeds 0` 고정. 강사 8개와 `acceptPromise`는 이제 compat에 있다(11-11, 위 표). `needsOnboarding = not consent`.
9. **끊어 보내기(11-11)** — 수다 입력창·전송 버튼을 **전송 중에도 비활성화하지 않는다.** 1.5초 안 조각을 `texts`로 묶어 sendChat. `queued: true`면 「생각 중…」 유지, `pending: true`면 `POST /sessions/{id}/reply`를 불러 그 `reply`를 붙인다. 힌트 버튼은 답 기다리는 중이면 비활성화(누르면 409 `busy`).
10. `session.studyMin`은 이제 수다·다리 놓기 단계에서도 같이 풀기에 쓴 분을 준다(전에는 0).
11. **강사 화면(11-11)** — 강사 요청에 `X-Demo-Role: instructor`·`X-Demo-Actor: demo-instructor`. `saveMemo` 다음에 `createDraft`를 부르는 지금 순서를 지킨다(`createDraft`는 읽기만). 승인 뒤 `updateDraft`는 409 `note_closed`(mock처럼 「승인 대기」로 돌아가지 않는다). 같은 날 메모를 다시 저장해도 초안은 그대로다.

**11-11 추가 계약 (compat)**

| # | 경로 (`/api/v1/compat` 아래) | 요청 | 응답 | 오류 |
| --- | --- | --- | --- | --- |
| 1 | POST /demo/restart | 본문 없음. 토큰·역할 헤더 없음(있어도 보지 않는다) | 200 `{"ok": true, "date": "YYYY-MM-DD"}`(서울 날짜) | 없음(DB 오류만 500) |
| 2 | GET /student/home | 기존과 같음(아이 헤더) | 기존 필드 + `endedInCrisis: boolean` — 오늘 세션이 crisis로 끝났으면 `true`, 세션 없음·진행 중·정상 종료는 `false` | 기존과 같음(헤더 없으면 401 `no_actor`) |

- #1은 데모 아이(`demo-child-minsu`)만 day3로 되돌린다: 세션·메시지·🔴 알림·오개념 삭제, 연속 3일·오늘 과제·오개념 3개를 다시 만든다. **강사 노트(메모·코멘트)·아이의 캐릭터 설정(style·호칭·말투)·타이머 배율은 그대로**, 다른 학생·계정 행도 그대로. 여러 번 불러도 같은 상태. 시연자 전체 리셋은 기존 `POST /api/v1/demo/reset`(토큰 필요).
- sendChat(A1, 11-11): 수다 마감 뒤(bridge)에 온 말도 PII 치환본 저장 + 🔴 키워드 검사를 거친다. 🔴이면 수다 중과 같은 crisis 응답(`crisis: true`·`hotlines`, 보호자 알림 1건). 아니면 `reply: ""`·`source: null`(LLM 호출 없음), 빈 말은 422. study 단계에 온 말은 전처럼 빈 답.

**11-11 공개 체험 세트 (compat, 명세 4.11-2·5)**

| # | 경로 (`/api/v1/compat` 아래) | 요청 | 응답 | 오류 |
| --- | --- | --- | --- | --- |
| 3 | POST /trial | 본문 없음. 토큰·역할 헤더 없음 | 200 `{"trialId": "t-…", "actors": {"child": "t-…-child", "guardian": "t-…-guardian", "instructor": "t-…-instructor"}, "date": "YYYY-MM-DD"}`(서울 날짜) | 429 `trial_limit` 「잠시 뒤 다시 시도해 주세요.」 — 서버 전체 최근 1시간 발급 300개 이상 |

- `t-…`는 `t-` + 소문자·숫자 16자. 프론트는 응답을 localStorage에 두고 역할별로 `X-Demo-Role`(child/guardian/instructor) + `X-Demo-Actor`(위 `actors`의 같은 역할 id)로 쓴다. 「처음부터 다시 체험」은 `POST /trial`을 다시 불러 새 세트로 바꾼다(이전 세트는 그대로 버린다). 배포 화면에서 `/demo/restart`는 부르지 않는다.
- 세트 아이는 day3(연속 3일·오개념 열림 2 + 해소 1·오늘 과제 3/4 ÷ 2, 별명 「지우」)지만 **약속 동의 전**이라 `GET /student/home`의 `needsOnboarding`이 `true` → 약속·캐릭터 고르기부터.
- 보호자 `t-…-guardian`은 같은 세트 아이를 본다. 형식은 맞는데 세트가 없으면 404 `student_not_found`, 형식이 틀리면 404 `guardian_not_found`.
- 학습지도자 `t-…-instructor`는 **같은 세트 아이만** 본다: `GET /teacher/today`의 `students`는 그 아이 1명. 다른 학생 id로 `/teacher/students/{id}/…`(memo·draft·approve·task)를 부르면 404 `student_not_found`(기본 경로 `/api/v1/instructor/…`도 같다). `demo-instructor`와 그 밖의 강사 id는 전처럼 전체.
- AI 호출 상한: 한 아이의 오늘 멘토 답이 150개 이상이면 그 턴은 LLM 대신 대본 문장(`source: "scripted"`). 화면은 막지 않는다.

### 11-11 보강 (A 세션 검수)
- `POST /compat/demo/restart` **없앰** — 토큰 없이 공용 데모 아이를 지울 수 있었다. 「처음부터 다시 체험」은 `POST /compat/trial`(새 세트).
- 학습지도자: 체험 강사(`t-…-instructor`)는 같은 세트 아이만. 그 밖의 강사 id는 체험 아이(`t-…`)를 못 본다(목록에서 빠지고 직접 요청은 404).
- 체험 강사의 세트 아이가 DB에 없으면 모든 학습지도자 요청이 404 `trial_not_found` → 프론트는 세트를 버리고 새로 받는다.
- AI 상한: 아이당 하루 150 + 서버 전체 최근 1시간 1500(멘토 답 수, DB에서 셈). 넘으면 그 턴 `source: "scripted"`.
