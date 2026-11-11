# 로그인(인증) 조사 — 11-11 회의 안건 초안

작성 2026-11-11 · 조사·정리만(코드·노션 수정 없음) · 출처 확인일은 모두 2026-11-11

## ① 한 줄 결론

**11-12 프리즈 전에는 「아이디·비밀번호 + 체험 계정 + 서명 토큰(Bearer)」만 넣고, 카카오·구글 로그인은 넣지 않는다(자리만 만든다).** 카카오·구글은 만 14세 미만 아이에게 쓰기 어렵고(계정 연령 제한·보호자 동의를 우리가 따로 받아야 함), 콜백 주소·키 등록 등 외부 설정이 많아 시연 위험만 늘린다.

---

## ② 회의에서 정할 것

| # | 정할 것 | 선택지 | 추천 | 이유 |
|---|---|---|---|---|
| 1 | 명세 5절 「로그인 대신 역할 선택」을 바꿀지 | (가) 그대로 역할 선택 (나) 아이디·비번 로그인으로 교체 + 체험 계정 버튼 | **(나)**, 단 결정 DB에 먼저 기록 | 재하 v0.5 화면이 이미 로그인·「체험 계정으로 둘러보기」 전제. 심사위원 「테스트 계정」 요구도 체험 계정으로 충족 |
| 2 | 로그인 상태를 무엇으로 들고 다닐지 | (가) 쿠키(브라우저가 자동으로 붙이는 작은 값) (나) 토큰을 요청 머리(Authorization 헤더)에 직접 실음 | **(나) Bearer 토큰** | 프론트·백 주소가 다르면 쿠키는 「남의 사이트 쿠키(서드파티 쿠키)」가 되어 아이폰 Safari가 기본 차단(2020-03~). 아이들은 폰으로 씀 |
| 3 | 토큰 종류 | (가) 무작위 문자열을 DB에 저장(불투명 토큰) (나) 서버 비밀키로 서명한 토큰(JWT 류) | **(나) 서명 토큰**, 만료 7일 | Render 무료는 15분 쉬면 DB가 비어 (가)는 **15분마다 전원 로그아웃**. 체험 계정 id를 고정하면 (나)는 재시작 뒤에도 유효 |
| 4 | 회원가입을 프리즈 전에 붙일지 | (가) 로그인·로그아웃·내 정보만 (나) 가입·아이디 찾기까지 | **(가)** | DB가 휘발성이라 가입한 계정이 15분 뒤 사라짐 → 시연에서 오히려 혼란. 가입 화면은 프론트 가짜 서버(mock)로 보여 주기 |
| 5 | 소셜 로그인(카카오 등) | (가) 11-15 이후 과제로 기록 (나) 프리즈 전 카카오만 | **(가)**. 발표에서는 「보호자·강사용으로 확장 예정」 한 줄 | ④·⑥절 참고. 아이 계정에는 소셜 로그인을 쓰지 않는 안을 권장 |

> 참고: 쿠키를 쓰고 싶다면 「프론트 빌드를 FastAPI가 같은 주소에서 서빙」(명세 10절 원안)하면 쿠키가 같은 사이트 쿠키가 되어 문제없다. 다만 재하가 프론트를 따로 배포하기로 했으므로 이번엔 2-(나)를 권한다.

---

## ③ 우리가 만들 것

### 지금(11-12 22:00 프리즈 전)

**백엔드(성호)** — 예상 0.5~1일
1. `POST /auth/login` {loginId, password, remember} → {token, me}. 비밀번호는 argon2id 해시로 비교.
2. `GET /me`, `POST /auth/logout`(서버는 200만, 프론트가 토큰 삭제).
3. `GET /demo/accounts`(체험 계정 목록: 아이디·역할·별명만).
4. 기동 시 체험 계정 자동 생성(이미 있는 `ensure_demo_actors`에 붙임). 비밀번호는 환경 변수 `DEMO_PASSWORD`.
5. `resolve_actor` 앞단을 `AUTH_MODE` 스위치로: `demo`=지금 헤더 방식(기존 테스트 그대로), `login`=Bearer 토큰.
6. 로그인 실패 제한(아이디+IP 기준 5회/15분, 메모리 카운터).
7. 테스트: 로그인 성공·실패·잠금, 토큰 없는/만료/위조 401, 보호자 토큰으로 아이 API 403.

**프론트(재하)** — 예상 반나절
1. `src/api/http.ts`의 `call()`에 `Authorization: Bearer <토큰>` 붙이기. 로그인 응답의 토큰 저장(「자동 로그인」 켬=localStorage, 끔=sessionStorage).
2. 401이면 토큰 지우고 로그인 화면으로.
3. 체험 계정 시트는 `/demo/accounts` 결과로. 비밀번호 `demo1234`를 화면·코드에 박지 말고 서버 값과 맞출 방법 정하기(아래 위험 3).
4. 가입·찾기 화면은 이번엔 mock 유지(서버 미연결 표시).

### 나중(11-15 이후)
- 영구 DB(Render Postgres 등)로 옮긴 뒤 회원가입·보호자 연결(link_code)·동의 기록.
- `auth_identities` 테이블을 채워 카카오(보호자·강사) → 구글 순으로 추가.
- 보호자 동의 확인(시행령 제17조의2 제1항 방법 중 택1), 비밀번호 재설정(메일은 범위 밖이라 보호자가 재설정).

---

## ④ 카카오·구글 절차 체크리스트(나중에 할 때)

### 카카오 로그인
- [ ] Kakao Developers에서 앱 만들기(개인 개발자 가능).
- [ ] [앱] > [플랫폼 키] > [REST API 키]에 **리다이렉트 URI**(로그인 후 돌아올 주소) 등록. 요청에 쓴 주소와 한 글자라도 다르면 KOE006 오류. 웹 도메인도 같은 키 아래에 등록.
- [ ] 카카오 로그인 「사용 설정」 ON(안 하면 KOE004).
- [ ] 클라이언트 시크릿(서버만 아는 비밀번호)이 REST API 키에 **기본 켜짐** → 토큰 요청에 넣기, 환경 변수로만 보관.
- [ ] 동의항목(사용자에게 받을 정보): **닉네임만**. 닉네임·프로필 사진은 기본 제공이라 별도 심사 불필요(카카오 운영진 답변). 이메일은 비즈 앱 전환 필요, 이름·전화번호는 비즈 앱 + 심사(3~5영업일).
- [ ] `state`(위조 방지용 무작위 값) 사용. PKCE 지원은 **확인 필요**(공식 REST 문서에서 못 찾음).
- [ ] 비용: 월 쿼터 안에서 무료.
- [ ] 테스트: 「테스트 앱」으로 앱 멤버 대상 개발·테스트 가능(공식 FAQ). 팀원 등록 절차·검수 없이 일반 사용자 공개가 되는지는 **확인 필요**(위 닉네임 답변상 기본 항목만이면 심사 없이 쓸 수 있어 보임).
- [ ] **만 14세 미만**: 카카오는 본인인증된 14세 미만 계정에 「제3자 제공」 보호자 동의만 처리. **서비스 이용에 대한 법정대리인 동의는 우리가 따로 받아야 함**(카카오 운영진 답변, 2026-08). 「만 14세 이상 연령 동의」로 막는 기능은 카카오싱크(비즈 정보 심사·채널 연결 필요)에서만 되고, 카카오가 나이를 아는 계정에만 동작.

### 구글 로그인
- [ ] Google Cloud 프로젝트 → OAuth 동의 화면 → 웹 클라이언트 ID 만들기.
- [ ] 리다이렉트 URI: **https 필수**(localhost만 예외), 정확히 일치, 와일드카드(*) 불가.
- [ ] 범위(scope)는 `openid email profile`만. 이 기본 범위만 쓰면 테스트 모드에서도 테스트 사용자 목록·경고 화면·7일 만료 제약이 적용되지 않음. 다른 범위를 하나라도 넣으면 테스트 사용자 100명·7일 만료.
- [ ] 앱 이름·로고를 동의 화면에 띄우려면 검증 필요할 수 있음(기본 범위만으로는 검증 요구 없음).
- [ ] `state` 필수(구글 문서: "The OAuth client must prevent CSRF").
- [ ] **연령**: 한국 구글 계정 최소 연령은 **만 14세**. 그 아래는 Family Link(보호자 관리 계정)이고, 보호자가 「제3자 앱 로그인」을 허용해야 함 → 초5~6 아이는 사실상 못 씀.

---

## ⑤ 기술 설계

### 테이블

| 테이블 | 열 | 지금/나중 | 비고 |
|---|---|---|---|
| accounts | id, role(child/guardian/instructor), login_id(고유), password_hash, nickname, grade(아이만), student_id(아이↔기존 students 행), created_at | 지금 | 학생은 아이디·별명·학년만. 실명·전화·이메일 없음 |
| guardian_links | guardian_account_id, student_id, consent_at | 지금(체험 1쌍) | `GUARDIAN_TO_CHILD` 상수를 대체 |
| login_attempts | 메모리 dict로 대체 | 지금 | 재시작되면 초기화돼도 무방 |
| auth_tokens | token_hash, account_id, expires_at, revoked_at | 나중(영구 DB 이후) | 지금은 서명 토큰이라 불필요 |
| auth_identities | provider(kakao/google), subject(제공자 회원번호), account_id, 고유(provider, subject) | 자리만(빈 테이블) | 소셜 붙일 때 사용 |

### 엔드포인트

| 경로 | 지금/나중 | 설명 |
|---|---|---|
| POST /auth/login | 지금 | 성공 시 서명 토큰 + me |
| POST /auth/logout | 지금 | 서명 토큰은 서버가 못 지움 → 프론트 삭제(나중에 auth_tokens로 강제 만료) |
| GET /me | 지금 | id, role, loginId, nickname, grade |
| GET /demo/accounts | 지금 | 체험 계정 목록 |
| GET /auth/{provider}/start | 나중 | state(+가능하면 PKCE) 만들고 제공자로 보냄 |
| GET /auth/{provider}/callback | 나중 | state 대조 → 코드 교환 → subject로 계정 찾기/연결 → 프론트 주소로 토큰 전달 |

### 신원 확인 교체(기존 테스트 유지)

| 항목 | 내용 |
|---|---|
| 스위치 | 환경 변수 `AUTH_MODE=demo|login`. 기본 `demo` → pytest는 지금처럼 X-Demo-Role/X-Demo-Actor 헤더로 통과 |
| login 모드 | `Authorization: Bearer` → 서명·만료 검증 → account → 기존 `resolve_actor(role, id)`에 넘김. 헤더 방식은 거부 |
| 배포 | Render에 `AUTH_MODE=login`, `AUTH_SECRET`(서명 비밀키), `DEMO_PASSWORD` 추가. 셋 다 대시보드에만, 커밋 금지 |
| 비밀번호 해시 | argon2id, OWASP 최소값 메모리 19MiB·반복 2·병렬 1 (`argon2-cffi`) |
| 시도 제한 | 아이디+IP 5회 실패 → 15분 잠금, 응답은 「아이디 또는 비밀번호가 달라요」로 통일 |
| CORS | 지금 `allow_headers=["*"]`라 Authorization 헤더 통과. 쿠키를 안 쓰므로 `allow_credentials` 불필요 |
| 체험 계정과 리셋 | 기동 때와 `/demo/reset` 때 같은 고정 id로 다시 만듦 → 이미 발급된 토큰이 리셋 뒤에도 유효. 리셋은 학습 기록만 지우고 계정은 유지 |

### 소셜 로그인 주소 고정 문제
Render 주소(`*.onrender.com`)가 바뀌면 카카오·구글 콘솔의 리다이렉트 URI도 바꿔야 한다. 콜백은 **백엔드 주소**로 받고(비밀값을 서버에만 두기 위해), 끝나면 프론트 주소로 돌려보낸다. 프론트로 토큰을 넘길 때 URL 쿼리 대신 `#fragment` 또는 한 번 쓰는 교환 코드를 쓴다(주소창·서버 로그에 토큰이 남지 않게).

---

## ⑥ 위험·법적 주의

1. **휘발성 DB**: 가입 계정·불투명 토큰은 15분 유휴/재시작 때 사라짐. 서명 토큰 + 고정 체험 계정으로 피함. 영구 저장이 필요하면 Render Postgres(무료는 생성 30일 뒤 만료).
2. **토큰 보관 위험**: localStorage는 자바스크립트로 읽혀 XSS(남의 스크립트가 끼어드는 공격) 한 번이면 토큰 유출(OWASP). 완화: 만료 7일, 「자동 로그인」 끄면 sessionStorage, 아이 글을 HTML로 그리지 않기(React 기본 이스케이프 유지, `dangerouslySetInnerHTML` 금지).
3. **체험 비밀번호 공개**: 화면에 `demo1234`를 보여 주는 것은 시연용으로 괜찮지만, 같은 값을 코드에 상수로 두면 금지 규칙과 충돌. 서버는 환경 변수, 화면 표시 값은 프론트 빌드 환경 변수(`VITE_DEMO_PASSWORD`)로 맞춘다. 체험 계정엔 실제 아이 정보 금지(합성).
4. **만 14세 미만 동의(개인정보 보호법 제22조의2)**: 아이 정보를 처리하려면 법정대리인 동의 + 확인 의무. 카카오가 받는 보호자 동의는 「카카오→우리 제3자 제공」용일 뿐 **우리 서비스 동의를 대신하지 않음**. 11-15 시연은 합성 데이터라 당장 위반은 아니나, 발표에서는 「보호자 동의 후 아이 계정 발급」 구조를 말한다(기존 `docs/llm_terms_minors_v0.1.md`·`docs/safety_secret_llm_legal_v0.1.md` 5.4절과 같은 취지).
5. **소셜 로그인 연령 장벽**: 구글은 한국 만 14세 미만 일반 계정 불가(Family Link). 카카오는 14세 미만 계정이 있어도 나이 정보를 늘 알지는 못함 → 아이는 아이디·비번, 소셜은 어른 계정에만 권장.
6. **외부 발송 금지**: 비밀번호 재설정 메일·문자는 이번 범위 밖. 아이 비밀번호는 보호자가 재설정(재하 v0.5 규칙과 일치).

---

## ⑦ 출처 (모두 2026-11-11 확인)

- WebKit, Full Third-Party Cookie Blocking (2020-03-24): https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/
- Chrome 서드파티 쿠키 폐지 철회 보도(1차 출처 아님, Chrome 공식 블로그 원문 **확인 필요**): https://digiday.com/marketing/after-years-of-uncertainty-google-says-it-wont-be-deprecating-third-party-cookies-in-chrome · https://searchengineland.com/google-third-party-cookies-chrome-reversal-444317
- OWASP HTML5 Security(localStorage에 세션 식별자 금지): https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html
- OWASP Password Storage(argon2id 19MiB/2/1): https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- Render 무료 플랜(15분 슬립, 휘발성 디스크, Postgres 30일): https://render.com/docs/free
- 카카오 로그인 설정하기: https://developers.kakao.com/docs/latest/ko/kakaologin/prerequisite
- 카카오 로그인 REST API(state·nonce·client_secret): https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api
- 카카오 로그인 FAQ(리다이렉트 URI 위치·테스트 앱·쿼터 무료): https://developers.kakao.com/docs/latest/ko/kakaologin/faq
- 카카오 보안 가이드(리다이렉트 URI 일치): https://developers.kakao.com/docs/latest/ko/getting-started/security-guideline
- 카카오 데브톡 — 14세 미만(운영진 답변 2026-08): https://devtalk.kakao.com/t/topic/151240 · 보호자 동의 범위: https://devtalk.kakao.com/t/topic/122967
- 카카오 데브톡 — 기본 항목만 쓰면 심사 불필요·비즈 앱/이메일: https://devtalk.kakao.com/t/topic/150376 · https://devtalk.kakao.com/t/faq/133989
- Google, OAuth 동의 화면·테스트 모드: https://support.google.com/cloud/answer/15549945
- Google, 웹 서버 OAuth(리다이렉트 URI 규칙·state): https://developers.google.com/identity/protocols/oauth2/web-server
- Google 계정 국가별 최소 연령(대한민국 만 14세): https://support.google.com/accounts/answer/1350409?hl=ko
- Family Link 제3자 앱 로그인 관리: https://support.google.com/families/answer/7103262
- 개인정보 보호법 제22조의2·시행령 제17조의2: 저장소 `docs/llm_terms_minors_v0.1.md` 66행의 law.go.kr 링크

### 확인 못 한 것
- 카카오 인가 요청의 PKCE(code_challenge) 지원 여부.
- 카카오 「테스트 앱」·팀원 등록의 정확한 절차와, 기본 항목만 쓸 때 일반 공개 전 검수가 정말 없는지(운영진 답변 기준, 공식 문서 문장 미확인).
- Chrome 서드파티 쿠키 정책의 공식 원문(2차 보도만 확인). 어느 쪽이든 Safari 차단만으로 쿠키 방식은 위험.
- 서명 토큰의 만료 기간(7일)·시도 제한 수치(5회/15분)는 설계 판단이지 출처 기반 아님.
