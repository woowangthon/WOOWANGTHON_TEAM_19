# Vercel + Supabase 배포 안내 v0.1 (TK-56, 명세 4.11-1)

성호가 대시보드에서 할 일만 순서대로 적었다. 설정은 저장소 루트 `vercel.json`에 있다.
Render 배포(`render.yaml`, `docs/deploy_render_v0.1.md`)는 **버림**(11-11, 명세 4.11-1) — 파일은 기록용으로만 둔다.

**모양.** Vercel 프로젝트 **하나**, 주소 **하나**. 안에 서비스 두 개가 같이 배포된다.

| 요청 경로 | 가는 곳 |
| --- | --- |
| `/api/...`, `/healthz` | `backend` 서비스 = `backend/app/main.py`의 FastAPI(파이썬 함수) |
| 그 밖 전부(`/`, `/assets/...`, `/mascot/...`) | `frontend` 서비스 = `frontend/` Vite 빌드(정적 파일) |

- 화면은 같은 주소의 `/api/v1/compat/...`를 부른다(빌드 때 `VITE_API_BASE=/api/v1/compat`). CORS 설정 필요 없다.
- 앱은 해시 라우팅(`/#/...`)이라 새로고침해도 404가 없다. SPA 폴백 규칙은 넣지 않았다.
- DB는 Supabase Postgres. 서버가 켜질 때마다 테이블이 없으면 만들고, 시드 20문제와 데모 배우를 채운다(이미 있으면 그대로). 함수 여러 개가 동시에 켜져도 Postgres 잠금으로 한 줄로 선다.

## 1. Supabase (DB) — 처음 한 번

1. supabase.com → **New project**.
   - Region: **Northeast Asia (Seoul) `ap-northeast-2`**.
   - Database password: 길게 아무렇게나. 비밀번호 관리자에만 적는다(노션·채팅·코드 금지). 영문·숫자만 쓰면 아래 주소에 그대로 넣을 수 있다(`@ : / ? #` 같은 기호가 있으면 URL 인코딩이 필요하다).
2. 프로젝트 화면 위쪽 **Connect** → **Connection string** → **Transaction pooler**(포트 **6543**)를 고른다.
   - 모양: `postgresql://postgres.<프로젝트ref>:<비밀번호>@<풀러호스트>:6543/postgres`
   - `<비밀번호>` 자리를 1번 비밀번호로 바꾼 전체 문자열이 Vercel의 `DATABASE_URL`이다.
   - 왜 이것: 서버리스 함수는 짧은 연결을 많이 연다 → Supabase가 서버리스용으로 권하는 것이 트랜잭션 모드다. 공유 풀러는 IPv4라 Vercel에서 바로 붙는다(Direct connection은 IPv6라 쓰지 않는다).
   - 코드가 알아서 하는 것: `postgres://`·`postgresql://`를 `postgresql+asyncpg://`로 바꾸고, prepared statement 캐시를 끄고(트랜잭션 모드는 지원 안 함), 연결 풀을 쓰지 않고(NullPool), TLS를 요구한다. 주소 뒤에 `?sslmode=require`가 붙어 와도 된다.
3. 테이블은 직접 만들지 않는다. 첫 배포가 켜질 때 생긴다(7개: problems·students·sessions·messages·misconceptions·instructor_notes·alerts).
4. (권장) **Project Settings → Data API**에서 Data API를 끈다. 이 앱은 Supabase 클라이언트(anon 키)를 쓰지 않는다. 코드가 테이블마다 RLS를 켜 두어(정책 없음) anon 키로는 어차피 0행이지만, 한 겹 더.

## 2. Vercel — 처음 한 번

1. vercel.com → **Add New → Project** → GitHub 저장소 `chingu1` **Import**.
2. **Root Directory는 비워 둔다**(저장소 루트). `vercel.json`의 `services`가 `frontend`·`backend`를 각각 잡는다. Framework Preset·Build Command는 대시보드에서 바꾸지 않는다(서비스 설정이 `vercel.json`에 있다).
3. **Environment Variables**(Production·Preview 둘 다 체크):

   | 이름 | 값 | 비고 |
   | --- | --- | --- |
   | `DATABASE_URL` | 1-2의 Transaction pooler 주소(비밀번호 넣은 것) | 비밀 |
   | `LLM_API_KEY` | Anthropic 키 | 비밀 |
   | `LLM_MODE` | `live` | 키가 없으면 자동으로 대본(scripted) |
   | `DEMO_TOKEN` | **비워 두기 권장** | 배포는 방문자별 체험 세트를 쓰고 `/demo/reset`은 테스트·영상용(명세 4.11-2). 없으면 리셋이 403으로 막힌다. 꼭 필요할 때만 긴 무작위 문자열 |

   넣지 않는 것: `TIMER_SCALE`(배포는 실제 시간, 4.11-3), `FRONTEND_DIST`(Vercel에선 프론트가 별도 서비스), `CORS_ORIGINS`(같은 주소), `LLM_MODEL`(기본 `claude-haiku-5-5`).
   `VITE_*`에는 비밀을 절대 넣지 않는다 — 화면 번들에 그대로 박혀 누구나 본다. 프론트 빌드 값(`VITE_API_MODE=http`, `VITE_API_BASE=/api/v1/compat`)은 비밀이 아니라 `vercel.json`에 적혀 있다.
4. **Deploy**. 몇 분 걸린다.
5. 배포 뒤 **Settings → Functions → Function Regions**를 **Seoul (icn1)** 하나로 바꾸고 다시 배포한다. 기본값은 미국 동부(`iad1`)라 서울 DB까지 매 쿼리가 태평양을 건넌다. (Hobby는 지역 1개만 고를 수 있다.)
6. 지출 한도
   - Anthropic 콘솔 → Billing/Limits에서 월 지출 한도를 건다(명세 4.11-5, 성호).
   - Vercel Hobby는 결제 수단이 없어 초과 과금이 없다(한도를 넘으면 멈춘다). Pro로 올렸다면 **Settings → Billing → Spend Management**에서 한도를 건다.
   - Supabase Free는 과금이 없다. 무료 프로젝트는 오래 쓰지 않으면 일시 정지될 수 있다 → 11-15 심사 기간엔 대시보드에서 상태를 한 번씩 본다(정지 조건 세부는 미확인).

## 3. 잘 떴는지 확인

```bash
curl https://<배포주소>/healthz
# {"db":"ok","llm_key":true,"llm_mode":"live","tz":"Asia/Seoul"} 이면 정상
curl -s https://<배포주소>/ | head -3
# <!doctype html> ... 이면 화면도 정상
```

- `db`가 `ok`가 아니거나 500 → Vercel **Deployments → 해당 배포 → Logs(Runtime)**에서 오류를 본다. 흔한 원인: 비밀번호 자리 그대로(`[YOUR-PASSWORD]`), 포트 5432/6543 혼동, 비밀번호의 기호 미인코딩.
- `llm_key`가 `false` → `LLM_API_KEY`가 비었다. 넣고 **Redeploy**.
- `llm_mode`는 키가 「있는지」만 본다. 실제로 AI가 답했는지는 대화 응답의 `source`(`live`/`scripted`)로 본다. 폰으로 아이 세션 한 턴을 보내고 브라우저 개발자 도구 Network 또는 Vercel 런타임 로그의 `source=` 줄을 확인한다.
- Supabase **Table Editor**에 테이블 7개, `problems` 20행이 보이면 기동 준비가 끝난 것이다.

## 4. 되돌리기(롤백)

- 코드: Vercel **Deployments**에서 앞서 잘 되던 Production 배포 → **⋯ → Instant Rollback**(또는 Promote to Production). 프론트·백엔드가 한 배포라 같이 돌아간다. Hobby에서 고를 수 있는 범위는 미확인(직전 배포만일 수 있다).
- DB: 롤백해도 DB는 그대로다. 테이블을 지우는 코드는 없다.
- **함정 — 칸 추가.** 기동 시 테이블 생성은 「없는 테이블만」 만든다. 모델에 칸이 추가된 코드를 배포하면 이미 있는 Postgres 테이블엔 그 칸이 안 생겨 500이 난다. 11-15 전에는 체험 데이터만 있으니, 그때는 Supabase **SQL Editor**에서 테이블을 지우고(`drop table alerts, messages, instructor_notes, misconceptions, sessions, students, problems cascade;`) 다시 배포하면 새로 만든다. 지우기 전에 성호 확인.
- 완전히 Render로 돌아가는 길은 버렸다(휘발성 DB). 급하면 로컬 대본 모드로 시연.

## 5. 꼭 알아 둘 것

- **서버 메모리에 상태를 두지 않는다**(4.11-1). 함수 인스턴스는 여러 개이고 수시로 바뀐다. `/demo/reset`의 `timer_scale`은 프로세스 메모리라 배포에선 그 인스턴스에만 먹는다 → 배포에서 쓰지 않는다(`DEMO_TOKEN` 비우면 아예 막힌다). 남은 메모리 상태는 LLM 클라이언트·대본 파일 캐시(`lru_cache`, 읽기 전용)뿐이라 인스턴스가 달라도 결과가 같다.
- **로그 레벨 DEBUG 금지.** DEBUG에선 DB 드라이버가 SQL 값(아이 문장 치환본)까지 찍는다. 기본(INFO) 그대로.
- **시드 파일.** `backend` 서비스 빌드가 `seed/seed_v0.1.json`을 `backend/app/_seed/`로 복사한다(서비스 루트 밖 파일이 함수에 실리는지 문서로 확인 못 해서). 빌드 로그에 `cp: ../seed/...: No such file`이 나오면 이 단계가 실패한 것 → 알려 줄 것.
- **SQLite와 다른 점.** Postgres는 외래 키와 글자 수 제한(`String(n)`)을 실제로 지킨다. 로컬 SQLite 테스트는 통과해도 Postgres에서만 나는 오류가 있을 수 있다 → 배포 뒤 시연 대본 한 바퀴를 꼭 돌린다.

## 6. 확인한 사실과 출처 (2026-11-11 조회)

| 사실 | 출처 |
| --- | --- |
| Services(베타, 모든 플랜): 한 프로젝트에 프론트·백엔드, 최상위 `rewrites`의 `destination: {"service": ...}`로 공개. 서비스는 원래 경로를 그대로 받는다(`/api/x` → `/api/x`). 빌드 설정(`buildCommand`·`outputDirectory`·`framework`)은 서비스 안에 둔다 | https://vercel.com/docs/services , https://vercel.com/docs/services/routing , https://vercel.com/docs/services/config-reference |
| 파이썬 `entrypoint`는 `module:app` 형식(예 `main:app`) | 위 config-reference |
| FastAPI는 함수 1개가 된다. lifespan(시작·종료) 지원, 종료 정리는 SIGTERM 뒤 500ms | https://vercel.com/docs/frameworks/backend/fastapi |
| 파이썬 버전: `pyproject.toml`·`.python-version`(이 저장소 `backend/.python-version` = 3.12). 지원 3.12(기본)·3.13·3.14 | https://vercel.com/docs/functions/runtimes/python/python-version |
| 의존성: `pyproject.toml`(uv.lock 있어도 없어도) 인식. 묶음 한도 500MB | https://vercel.com/docs/functions/runtimes/python |
| 함수 기본 지역 `iad1`, 대시보드 Settings → Functions에서 변경, Hobby는 1개. 서울 `icn1` | https://vercel.com/docs/functions/configuring-functions/region , https://vercel.com/docs/regions |
| Supabase 연결 문자열 3종, 서버리스는 Transaction 모드(6543), 공유 풀러는 IPv4, 사용자명 `postgres.<ref>`, 트랜잭션 모드는 prepared statement 미지원 | https://supabase.com/docs/guides/database/connecting-to-postgres |
| asyncpg는 `statement_cache_size=0` | https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL |
| SQLAlchemy asyncpg + PgBouncer류: `NullPool` + `prepared_statement_name_func`(uuid) + `prepared_statement_cache_size=0` | SQLAlchemy 2.1 asyncpg 방언 문서(설치본 `sqlalchemy/dialects/postgresql/asyncpg.py` 독스트링 「Prepared Statement Name with PGBouncer」) |
| Supabase 서울 지역 `ap-northeast-2` | https://supabase.com/docs/guides/platform/regions |

**미확인**(배포 뒤 눈으로 확인할 것)
- 서비스 경로로 넘어갈 때 커스텀 요청 헤더(`X-Demo-Role`·`X-Demo-Actor`)가 그대로 가는지 — 문서에 명시는 없다(일반 rewrite는 요청 헤더를 그대로 넘긴다). 확인: 아이 화면에서 오늘 화면이 뜨면 된 것(헤더가 없으면 401).
- 백엔드 서비스(루트 `backend/`) 빌드에서 `../seed`가 보이는지 — 위 복사 단계가 실패하면 드러난다.
- `uv.lock`의 dev 그룹(pyright 등)이 함수에 안 실리는지.
- 서비스 모드에서 최상위 `regions` 키가 허용되는지 — 그래서 지역은 대시보드에서 바꾼다.
- 실제 Supabase 풀러(Supavisor) 상대로의 동작 — 로컬에서는 Postgres 16(풀러 없음)으로만 확인했다(아래).

## 7. 로컬에서 확인한 것

- Postgres 16.2(`pgserver` 휠의 바이너리, 스크래치 폴더)를 띄워 백엔드 테스트 전체를 Postgres로 돌림: 701개 중 698 통과. 실패 2·오류 1은 전부 테스트 쪽 사정(SQLite는 외래 키를 안 지켜서 없는 세션·문제 id로 행을 넣는 픽스처 2개, `sqlite3`로 직접 끼어드는 경합 테스트 1개). 앱 코드 오류는 없었다.
- 빈 Postgres에 기동(lifespan)을 동시에 8개 돌림 → 모두 성공, `problems` 20·데모 아이 1·오개념 3, 테이블 7개 모두 RLS 켜짐. anon 흉내 역할로 읽으면 0행, 테이블 주인(앱)은 그대로 읽힘.
- 프론트 `VITE_API_MODE=http VITE_API_BASE=/api/v1/compat npm run build` 통과, 번들에 `localhost:8000` 없음.
