# 프론트 ↔ 백엔드 API 계약 (v0.3, 2026-11-10)

화면이 서버에 요청하는 일의 전체 목록입니다. 원문은 `src/api/client.ts`(함수 목록)와 `src/types.ts`(JSON 모양)이고, 이 문서는 그 요약입니다.
**경로 이름은 임시**입니다. 성호님 명세 v0.4의 이름이 정해지면 `src/api/http.ts`의 경로만 바꾸면 됩니다. 응답 JSON의 필드 이름이 `types.ts`와 같으면 화면 코드는 고칠 필요가 없습니다.

## 서버가 맡는 판단 (화면은 하지 않음)
규칙의 기준 구현은 `src/api/engine.ts`(순수 함수)와 `src/api/mock.ts`(상태·시간)이고, 기대 동작은 테스트(`*.test.ts`, 20개)에 적혀 있습니다.

| 판단 | 규칙 |
|---|---|
| 세션 단계 | `solve → transition → chat(선택) → wrap → done`, 위험 표현 감지 시 `crisis`. 하루 1회. 새로 불러와도 같은 단계·같은 문제에서 이어짐 |
| 정답 판정 | 약분·배수 형태도 정답. 정답은 화면으로 내려보내지 않음 |
| 힌트 | 문제당 최대 3개. **틀리면 다음 힌트가 자동으로 나옴**. 3개를 다 쓰고도 틀려야 「풀이 같이 보기」 허용 |
| 실수 유형 | 분모끼리 더하기/빼기 · 통분 빠뜨림 · 분자 계산 · 분모 처리 · 기타 (강사 화면 전용) |
| 시간 | 풀기 20분, 수다 10분. 지나면 서버가 다음 단계로 넘김 |
| 연속 일수 | 풀기 단계가 끝나는 순간(`transition`) +1 |
| 위험 표현 | 감지 즉시 조언 중단, 세션 `crisis`, 보호자 알림 1건(원문 없음). 키워드는 명세 부록 A로 교체 |
| 개인정보 | 저장 전 전화번호·이메일 가림. 대화는 세션이 끝나면 삭제. 하루 기록에는 대화가 들어가지 않음 |

## 학생
| 함수 | 임시 경로 | 요청 → 응답 |
|---|---|---|
| getStudentHome | GET `/student/home` | → `StudentHome` (이름, 날짜, 연속, 이번 주 출석, 오늘 할 것, 온보딩 필요 여부, 오늘 세션, 오늘 끝났는지) |
| acceptPromise | POST `/student/promise` | → 204 |
| getMentor / saveMentor | GET·PUT `/student/mentor` | `MentorSetting` {style, title, speech, animal} |
| getActiveSession | GET `/sessions/active` | → `SessionView \| null` |
| startSession | POST `/sessions` | {difficulty} → `SessionView` (오늘 세션이 이미 있으면 그것을 돌려줌) |
| getProblem | GET `/sessions/{id}/problem` | → `ProblemView \| null` (null = 풀기 단계 끝) |
| submitAnswer | POST `/sessions/{id}/answer` | {problemId, numerator, denominator} → `AnswerResult` {correct, numeratorOk, denominatorOk, message, autoHint, hintsLeft, canShowSolution, session} |
| requestHint | POST `/sessions/{id}/hint` | {problemId} → {hints[], hintsLeft} |
| showSolution | POST `/sessions/{id}/solution` | {problemId} → {steps[], session} · 허용 전이면 4xx |
| afterStudy | POST `/sessions/{id}/after-study` | {choice: "chat"\|"skip"} → `SessionView` |
| getChat | GET `/sessions/{id}/chat` | → {messages[], remainingSec} |
| sendChat | POST `/sessions/{id}/chat` | {text} → {reply, crisis, session} |
| endChat | POST `/sessions/{id}/chat/end` | → `SessionView` |
| getWrap / submitWrap | GET·POST `/sessions/{id}/wrap` | → `WrapInfo` / {hardPoint, quiz} → `SessionView` |
| getRecords | GET `/student/records` | → `StudyRecord[]` |

## 강사
| 함수 | 임시 경로 | 요청 → 응답 |
|---|---|---|
| getUnits / saveUnits | GET·PUT `/teacher/units` | {selectedIds[]} → `Unit[]` (hasProblems=false면 문제 은행 없음) |
| getTeacherToday | GET `/teacher/today` | → `TeacherToday` (학생별 오늘 할 것·상태·코멘트 상태) |
| assignTask | PUT `/teacher/students/{id}/task` | {unit \| null} → `TeacherToday` |
| getMemo / saveMemo | GET·PUT `/teacher/students/{id}/memo` | `TeacherMemo` {covered, stuck, homework, note} |
| createDraft | POST `/teacher/students/{id}/draft` | → `Draft` (사실 칸은 기록에서, 코멘트만 초안. LLM 실패 시 템플릿) |
| updateDraft | PUT `/teacher/students/{id}/draft` | {comment} → `Draft` (다시 "승인 대기") |
| approveDraft | POST `/teacher/students/{id}/draft/approve` | → `Draft` · 승인된 코멘트만 보호자에게 공개 |
| getResults | GET `/teacher/results` | → `StudentResult[]` (힌트 수·실수 유형 포함) |
| getTeacherAlerts | GET `/teacher/alerts` | → `TeacherAlert[]` · **긴급만, 분류 없음** |

## 보호자
| 함수 | 임시 경로 | 요청 → 응답 |
|---|---|---|
| getGuardianToday | GET `/guardian/today` | → `GuardianToday` · **힌트·실수 상세·대화 없음** |
| getAlerts | GET `/guardian/alerts` | → `SafetyAlert[]` {level, category, action, status} · 원문 없음 |
| ackAlert | POST `/guardian/alerts/{id}/ack` | → `SafetyAlert` |
| closeAlert | POST `/guardian/alerts/{id}/close` | {reason} → `SafetyAlert` · **긴급 + 미확인이면 거절(409)** |

## 시연
| getDemo / setDemo | GET·PUT `/demo/settings` | {fast} · fast=true면 시간이 20배 빠르게(20분 → 1분) |
|---|---|---|
| resetDemo | POST `/demo/reset` | 시드 상태(어제까지 연속 3일)로 되돌림 |

## 성호님 명세와 맞출 때
1. 위 함수와 명세 v0.4의 API 12개를 짝짓기. 서버에서 여러 개를 하나로 합쳐도 `http.ts`에서 나눠 주면 화면은 그대로입니다.
2. 11-09 손 메모상 11-15 범위 밖일 수 있는 것: 강사 알림(`getTeacherAlerts`), 알림 닫기(`closeAlert`). 서버에 없으면 그 탭·버튼만 숨기면 됩니다.
3. 수다 응답은 지금 대본(scripted) 모드입니다. LLM 어댑터를 붙여도 응답 모양은 `{reply, crisis, session}` 그대로입니다.

---
## v0.4 — 계정·학원·강의실·씨앗 (11-10 회의 확정)
구현 기준: `src/api/org.ts`(가짜 서버, 규칙 포함) · 임시 경로: `src/api/http.ts` · 규칙 요약·DB: `docs/DEV-RULES.md`

| 함수 | 임시 경로 | 누가 | 하는 일 |
|---|---|---|---|
| getMe | GET /me | 모두 | 로그인한 사람(없으면 null → 첫 선택 화면) |
| signup | POST /auth/signup | 처음 | 학생(별명·학년)/보호자/학습지도자(학원 일련번호)/학원장(학원 등록 신청) |
| logout | POST /auth/logout | 모두 | |
| demoAccounts·demoLogin | GET /demo/accounts · POST /demo/login | 시연 | 체험 계정 |
| linkWith | POST /links {code, consent} | 학생·보호자 | 보호자: 동의와 함께 연결 / 학생: 동의 대기 요청 |
| confirmLink | POST /links/{studentId}/confirm | 보호자 | 학생 요청 수락(동의) |
| joinAcademy | POST /academy/join {code} | 학생·보호자 | 6자리 입장 코드, 연결된 묶음 전체 등록 |
| getOwnerDashboard·issueEntryCode·approveTeachers | /owner/... | 학원장 | 관리·코드 발급·지도자 승인 |
| getApplications·reviewApplication | /operator/... | 운영자 | 학원 등록 심사 |
| getTeacherClasses·createClassroom·inviteStudent·answerRequest | /teacher/classes... | 학습지도자 | 강의실 |
| getStudentClasses·requestJoin·acceptInvite | /student/classes... | 학생 | 강의실 |
| getWallet·getStudentShop·buyAcademyItem·buyCosmetic·equipOutfit | /student/... | 학생 | 씨앗·상점·옷 |
| getStampState·stamp | /guardian/stamp | 보호자 | 오늘 이야기 도장 |
| getSeedBoard·grantSeeds·saveShopItem·deliverOrder | /teacher/seeds·shop·orders | 학습지도자 | 씨앗 확인·칭찬·상점 편집·전달 체크 |

학습 API(v0.3)는 이제 **로그인한 학생 기준**으로 동작한다(학생마다 기록이 따로). 학습지도자 화면은 자기 강의실 학생만, 보호자는 연결된 아이만 본다.

---
## v0.5 — 로그인·가입·설정·소속·알림함
| 함수 | 임시 경로 | 누가 | 하는 일 |
|---|---|---|---|
| login | POST /auth/login {loginId, password, remember} | 모두 | 로그인 |
| checkLoginId | GET /auth/check-id | 가입 | 아이디 중복(true=사용 가능) |
| signup | POST /auth/signup | 가입 | {role, loginId, password, name, grade?/email?, agreements} |
| findLoginId · requestPasswordReset | POST /auth/find-id · /auth/reset-password | 비로그인 | 가린 아이디 / 'sent' · 'ask-guardian' |
| updateProfile · changePassword · saveSettings · deleteAccount | PUT /me · /me/password · /me/settings · POST /me/delete | 모두 | 설정 |
| resetChildPassword | PUT /guardian/children/{id}/password | 보호자 | 아이 비밀번호 재설정 |
| getNotices · readNotices | GET /notices · POST /notices/read | 모두 | 알림함 |
| requestMembership · leaveMembership · applyAcademy | /teacher/membership · /teacher/academy-applications | 학습지도자 | 소속 신청·나가기, 학원·학교 등록 신청 |
| getOwnerDashboard · issueEntryCode · approveTeachers | /owner/... | **원장(학습지도자)** | 학원 관리 |

v0.4의 `owner` 역할과 "학원장 가입"은 없어졌다. Me에 `loginId·email·grade·membership{isOwner}·settings`가 추가됐다.
