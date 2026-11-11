# 개발 인계 규칙 (v0.5) — 성호님·팀원용

> 이 앱은 **프론트엔드 + 가짜 서버(브라우저 안)**로 끝까지 동작한다. 백엔드는 가짜 서버의 규칙을 그대로 서버로 옮기면 된다.

## 1. 실행
| 목적 | 명령 | 결과 |
|---|---|---|
| 개발 | `cd app && npm install && npm run dev` | http://localhost:5173 |
| 검사 | `npm run typecheck && npm test` | 타입 + 규칙 테스트(엔진·학습·계정·씨앗) |
| **실행 파일 만들기** | `npm run build:single` | `release/AI-멘토.html` + `release/mascot/` → 더블클릭 실행 |
| 웹 배포용 | `npm run build` | `dist/` (정적 호스팅) — 배포는 팀 회의 후 |

- `release/` 폴더를 통째로 전달하면 설치 없이 열린다. 데이터는 그 브라우저의 localStorage에 저장된다(기기 간 공유 X).
- 처음 열면 로그인 화면 → 아래 「체험 계정으로 둘러보기」를 누르면 아이디가 채워진다. 체험 계정 비밀번호는 모두 `demo1234`.
  - 학생 `jiwoo` · 보호자 `jiwoo_mom` · 학습지도자 `kim_teacher` · 원장 `park_owner` · 학원 심사 중 `choi_owner` · 소속 승인 대기 `lee_teacher` · 소속 없음 `jung_teacher` · 운영자 `operator`

## 2. 폴더 구조
```
app/src/
  api/client.ts   ← 화면이 서버에 요청할 수 있는 일(계약). MentorApi = 학습 + AccountApi(org)
  api/mock.ts     ← 가짜 서버: 학습(세션·문제·힌트·수다·코멘트·알림)
  api/org.ts      ← 가짜 서버: 계정·학원·강의실·씨앗·상점  ★ v0.4
  api/engine.ts   ← 판단 규칙(문제 생성·채점·힌트·위기 감지·개인정보 가리기)
  api/http.ts     ← 진짜 FastAPI 연결(임시 경로)
  api/index.ts    ← VITE_API_MODE=http 이면 http, 아니면 mock
  state/          ← auth(자동 로그인) · session(오늘 세션 단계) · mentor(캐릭터·말투)
  screens/        ← auth(로그인·가입·찾기·약관) settings(설정·알림함) student teacher guardian owner(학원 관리) operator
  data/docs.ts    ← 이용약관·개인정보 처리방침·FAQ·공지 (초안, 법률 검토 필요)
```

## 3. 백엔드로 옮기는 방법
1. `api/org.ts`·`api/mock.ts`에서 `fail('...')`(=throw)하는 곳이 **서버가 막아야 하는 규칙**이다. 같은 메시지로 400을 돌려주면 화면이 그대로 보여 준다(`{ "detail": "메시지" }`).
2. `api/http.ts`의 경로를 실제 경로로 바꾼다. 화면 코드는 고치지 않는다.
3. `.env`: `VITE_API_MODE=http`, `VITE_API_BASE=https://...`
4. 응답 JSON 모양 = `src/types.ts`. 필드 이름을 바꾸려면 types.ts와 화면을 같이 고친다.

## 4. 데이터 모델(DB 테이블 제안)
| 테이블 | 주요 칸 | 비고 |
|---|---|---|
| users | id, role(student/guardian/teacher/operator), login_id(고유), password_hash, name, email(어른만), grade, link_code(6, 고유), academy_id, teacher_status(승인 대기/승인됨), agreed_at, marketing, settings(json) | 학생은 실명·전화번호·이메일 받지 않음. **비밀번호는 bcrypt/argon2** (가짜 서버의 hash는 시연용) |
| notices | id, user_id, at, text, link_to, read | 알림함 |
| links | student_id, guardian_id, status(대기/연결됨), consent_at | 보호자 동의 시각 = 법정대리인 동의 기록 |
| academy_applications | id, applicant_id(학습지도자), org_type(학원/학교), academy_name, biz_no, ceo, phone, address, status(심사 중/승인/반려), serial, reject_reason, applied_at | |
| academies | id, name, org_type, serial(XXXX-XXXX, 고유), owner_id(=원장 학습지도자) | |
| entry_codes | academy_id, code(6자리), expires_at | 10분. 학생·보호자 학원 입장 전용 |
| classrooms | id, academy_id, teacher_id, name, plan | |
| classroom_members | classroom_id, student_id, state(초대/요청/멤버) | |
| seed_ledger | id, student_id, date, amount(±), source(학습 완료/보호자 도장/학습지도자 칭찬/상점 구매), note, by_user | **잔액 = 합계**(잔액 칸을 따로 두지 않는 것을 권장) |
| shop_items | id, teacher_id, name, price, stock(null=무제한), visible, note | |
| orders | id, student_id, teacher_id, item_name, price, status(교환 요청/전달 완료), at | |
| cosmetics_owned | student_id, cosmetic_id, equipped | 꾸미기 목록은 코드 상수(COSMETICS) |
| learners / sessions / day_records / drafts / memos / alerts | (v0.3 그대로) | API-CONTRACT.md |

## 5. 서버가 지켜야 할 규칙 (v0.4)
| 규칙 | 위치 |
|---|---|
| 아이디·비밀번호 로그인, 「자동 로그인」 끄면 앱을 다시 열 때 로그아웃. 로그인 뒤 로그인·가입 화면으로 못 돌아감(GuestOnly) | org.login, state/auth.tsx |
| 가입: 필수 약관 2개, 아이디 `^[a-z][a-z0-9_]{3,15}$`·중복 불가, 비밀번호 영문+숫자 8~20자, 어른은 이메일 필수 | org.signup, ID_RULE, PW_RULE |
| 아이디 찾기=이메일, 비밀번호 찾기=아이디+이메일(재설정 메일). 학생은 이메일이 없으므로 **보호자가 재설정** | org.findLoginId / requestPasswordReset / resetChildPassword |
| 비밀번호 변경은 지금 비밀번호 확인, 탈퇴는 비밀번호 확인. 원장은 관리 넘기기 전 탈퇴 불가 | org.changePassword / deleteAccount |
| 학습지도자는 가입 후 **설정 → 소속**: 일련번호로 소속 신청(원장 승인) 또는 학원·학교 등록 신청(운영자 승인 → 신청자가 원장) | org.requestMembership / applyAcademy / reviewApplication |
| 원장 전용: 입장 코드 발급, 소속 신청 체크 승인 | org.mustOwner |
| 연결 요청·초대·승인·반려·교환 요청·전달·도장·칭찬은 상대에게 알림함으로 | org.notify |
| 학생은 **보호자와 연결되기 전 제한 모드**: 학원 입장·강의실 요청·수다 불가 | org.isRestricted, mock.afterStudy |
| 보호자가 연결할 때 만 14세 미만 **보호자 동의 필수**(consent=true). 학생이 먼저 요청하면 "대기" → 보호자 동의로 연결 | org.linkWith / confirmLink |
| 학원 입장 코드 6자리, 10분 만료. 자동 등록은 **연결된 한 쌍(학생↔보호자)까지만**: 학생이 들어가면 학원 없는 연결 보호자도 등록, 보호자가 들어가면 연결된 아이가 **1명일 때만** 아이도 등록(2명 이상이면 보호자에게 「아이 계정에서 코드」 안내). 이미 **다른 학원**이면 덮어쓰지 않고 두 사람에게 알림. 보호자는 학원 1곳만(한계) | org.joinAcademy / linkWith / confirmLink / enrollLinked |
| 학원 등록 → 운영자 승인 시 일련번호 발급. 반려는 사유 필수 | org.reviewApplication |
| 학습지도자는 일련번호로 가입 → 학원장 승인 전 강의실 개설 불가 | org.signup / createClassroom |
| 강의실 입장 = 지도자 초대(학생 수락) 또는 학생 요청(지도자 수락). 같은 학원 학생만 | org.inviteStudent / answerRequest |
| 과제는 강의실 학생에게만, 강의실이 없으면 과제 없음 | mock.task / assignTask |
| 씨앗: 학습 완료 +3(하루 1번) · 보호자 도장 +2(하루 1번) · 지도자 칭찬 1~5, 학생당 하루 10, 이유 필수 | org.SEED_RULES |
| 구매: 잔액·재고 확인, 숨긴 상품 구매 불가, 학원 상품은 교환 요청 → 지도자 전달 체크 | org.buyAcademyItem / deliverOrder |
| 학습지도자는 상점에서 사지 않음, 자기 강의실 학생의 잔액만 봄 | org.getSeedBoard |

## 6. 아직 정하지 않은 것 (백엔드와 결정)
- 소셜 로그인(카카오 등) 추가 여부. 지금은 아이디·비밀번호.
- 비밀번호 재설정 메일 발송(메일 서비스), 휴대폰 푸시 알림.
- 사업자등록번호 진위 확인(국세청 상태 조회) 여부.
- 동의 문구 최종본(개인정보 처리방침과 함께).
- 이모티콘을 수다에서 보내는 기능(상점에서 살 수는 있음, 보내기는 후속).

## 7. 작업 규칙
- 공유 폴더에서 각자 **자기 feedback 파일만** 수정(CLAUDE.md / GPT.md). 결정은 BRIEF.md, 진행 상황은 STATUS.md에 덧붙인다.
- 그림은 덮어쓰지 말고 새 버전으로 저장 후 교체.
- 비밀값(API 키·토큰·비밀번호)은 코드·노션·공유 폴더에 넣지 않는다(.env, .gitignore).
- 배포는 팀 회의에서 정한 뒤에.
