# AI 멘토 앱 v0.5

> **v0.5**: 아이디·비밀번호 로그인(자동 로그인)·3단계 회원가입·아이디/비밀번호 찾기·설정(프로필·비밀번호·알림·소속·자녀 관리·약관·탈퇴)·알림함, 학습지도자 소속 신청/학원·학교 등록(승인되면 원장)
>
> **v0.4 (11-10 회의 반영)**: 학원 등록/운영자 심사/학원장 관리 · 학습지도자(명칭 변경) 승인·강의실 · 학생⇄보호자 연동(보호자 동의) · 학원 입장 코드 · 씨앗(재화)·상점·보호자 도장 · 캐릭터 넘기기+옷장
>
> - 바로 실행: `npm run build:single` → `release/AI-멘토.html` 더블클릭 → 체험 계정(비밀번호 `demo1234`)
> - 규칙 문서: [디자인 규칙](docs/DESIGN-RULES.md) · [개발 인계 규칙](docs/DEV-RULES.md) · [API 계약](docs/API-CONTRACT.md)


화면 흐름과 **서버가 해야 할 판단 규칙**까지 들어 있는 뼈대입니다. 백엔드 없이 가짜 서버(mock)로 하루 세션이 끝까지 돌고, 새로고침해도 이어집니다.

## 실행
```bash
npm install
npm run dev        # http://localhost:5173  (폰 크기 360×640 프레임)
npm test           # 규칙 테스트 20개 (정답 판정·힌트·단계·안전 알림)
npm run build      # 타입 검사 + 배포용 빌드(dist/)
```
Node 20 이상 필요. 역할 선택 화면의 「빠른 시연」을 켜면 20분이 1분으로 줄어 시간 마감을 바로 볼 수 있습니다.

## 성호님 FastAPI에 붙이기
1. `.env.example`을 `.env`로 복사 → `VITE_API_MODE=http`, `VITE_API_BASE=http://서버주소`
2. `src/api/http.ts`의 경로(임시 이름)를 명세의 API 이름으로 바꾸기
3. 응답 JSON이 `src/types.ts` 모양이면 화면은 그대로 동작 → `docs/API-CONTRACT.md`

## 폴더 구조
```
src/
  types.ts     프론트와 백엔드가 주고받는 JSON 모양
  api/
    client.ts  화면이 서버에 요청하는 일의 목록(계약)
    engine.ts  판단 규칙(순수 함수): 문제 만들기·정답 판정·실수 유형·힌트·풀이·수다 대본·위험 감지
    mock.ts    가짜 서버: 세션 상태·시간 마감·기록·알림 (localStorage에 저장)
    http.ts    진짜 서버 연결   index.ts  mock/http 전환
    *.test.ts  규칙 테스트
  state/       session.tsx(오늘 세션 + 단계별 화면 보호) · mentor.tsx(띠·말투)
  components/  Frame·TopBar·TabBar·Icon·Mascot·Keypad·Fraction·Common
  screens/     role/ · student/ · teacher/ · guardian/
  styles/      tokens.css(디자인 값) · global.css(공통 모양)
public/mascot/{horse,monkey}/  띠 캐릭터: {mood}.png 전신 · -face 상반신 · -avatar 머리
```

## 화면 디자인에 참고한 것
- 틀리면 도움이 **자동으로** 나온다: 학생은 스스로 힌트를 잘 누르지 않는다는 Khanmigo 연구·개편 방향 → 오답 시 다음 힌트 자동 표시, 3단계 뒤에 풀이.
- 한 화면에 한 가지 일, 하단 큰 버튼, 정답/다시 도전을 하단 색 띠로 알림(Duolingo 수업 화면 방식). 틀려도 빨강·X 없이 머스터드.
- 상자와 장식을 줄이고 여백으로 구분(Duolingo 탭 개편).
- 연속 기록은 압박 없이: 숫자보다 "4일째 같이 했어" 문장, 죄책감 알림 없음.

## 화면 목록 (주소는 `#/...`)
| 역할 | 화면 | 주소 | 상태 |
|---|---|---|---|
| 공통 | 역할 선택(=테스트 계정) | `/` | 동작 |
| 학생 | 오늘 시작 | `/student` | 동작 |
| 학생 | 약속 1/2 · 캐릭터 고르기 2/2 (탭 숨김) | `/student/onboarding/*` | 동작 |
| 학생 | 난이도 고르기 | `/student/difficulty` | 동작 |
| 학생 | 같이 풀기 · 다시 도전 · 풀이 같이 보기 | `/student/solve` | 동작 (힌트 자동·20분 마감) |
| 학생 | 학습 완료(전환) | `/student/done` | 동작 |
| 학생 | 수다 · 🔴 위기 화면 | `/student/chat`, `/student/crisis` | 동작 (mock 키워드) |
| 학생 | 마무리(한 줄·어려웠던 점·퀴즈) | `/student/wrap` | 동작 |
| 학생 | 기록 · 내 멘토(띠 바꾸기) | `/student/records`, `/student/mentor` | 동작 |
| 강사 | 범위 · 오늘 할 것(지정→메모→초안→수정·승인) · 결과 · 알림(긴급만) | `/teacher/*` | 동작 |
| 보호자 | 결과 · 안전 알림(확인→닫기 사유) | `/guardian`, `/guardian/alerts` | 동작 |

점선 상자는 아직 정하지 않은 자리입니다(회의 안건).

## 지킨 원칙
- 정답 판정·힌트 단계·위험 감지는 **서버 일**. `mock.ts`는 개발용 흉내이며 실제 배포에서는 정답·키워드를 프론트에 두지 않습니다.
- 대화 원문은 보호자·강사 화면에 표시하지 않음.
- 긴급 알림은 “확인했어요” 뒤에만 “괜찮아요”로 닫기.
- 탭 첫 화면은 뒤로가기 없음, 첫 실행(약속·캐릭터)은 탭 숨김.
- 입력창 옆 `+` 버튼 없음.

## 회의용 문서
- `docs/API-CONTRACT.md` — 성호님 백엔드와 맞출 요청·응답 목록과 서버 판단 규칙
- `docs/WORK-SPLIT.md` — 기능별 남은 일과 담당 칸

## 확인 필요
- 위기 연락처(109·1388)는 배포 전 공식 기관 안내로 다시 확인.
- 캐릭터: B 플랫(GPT 제작)을 Claude가 알파 정리·256px(머리 128px)로 내보냄. 기본 동물은 `src/state/mentor.tsx`의 DEFAULT_ANIMAL 한 줄.
