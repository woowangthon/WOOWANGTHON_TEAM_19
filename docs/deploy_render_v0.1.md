# Render 배포 안내 v0.1 (TK-56, 화면+API 한 주소)

성호가 Render 대시보드에서 직접 하는 일만 적었다. 설정은 저장소 루트 `render.yaml`에 있다.

웹 서비스 **하나**가 화면(재하 프론트 `frontend/` 빌드)과 API를 같은 주소에서 낸다. 심사위원은 `https://<서비스주소>/` 하나로 들어온다. 화면은 같은 주소의 `/api/v1/compat/...`를 부르므로 CORS 설정이 필요 없다.

- 빌드: `backend`에서 `uv sync` → `../frontend`에서 `npm ci` → `VITE_API_MODE=http VITE_API_BASE=/api/v1/compat npm run build`(결과 `frontend/dist`).
- 실행: FastAPI가 `/api/*`·`/healthz`를 먼저 받고, 나머지 경로는 `FRONTEND_DIST`(= `../frontend/dist`)의 정적 파일. 앱은 해시 라우팅(`/#/...`)이라 새로고침해도 404가 없다.
- `FRONTEND_DIST`가 없거나 폴더가 없으면 정적 서빙을 안 한다(로컬 개발·테스트는 예전 그대로).

## 1. 처음 한 번

1. Render 대시보드 → **New → Blueprint** → GitHub 저장소 `chingu1`을 고른다. Render가 `render.yaml`을 읽어 웹 서비스 `chingu1-backend`(무료 플랜, 폴더 `backend`)를 보여 준다. 이미 만들어 둔 서비스가 있으면 **Blueprint → Manual Sync**로 바뀐 빌드 명령·`FRONTEND_DIST`를 반영한다.
2. 값을 물어보는 환경 변수를 채운다(`sync: false`라 Render가 처음 만들 때만 묻는다).
   - `LLM_API_KEY` — LLM 키. 다른 곳(코드·노션·채팅)에는 적지 않는다.
   - `DEMO_TOKEN` — 리셋용 비밀 문자열. 길게 아무렇게나 정하고 시연자만 안다.
   - `CORS_ORIGINS` — **비워 둔다.** 다른 주소의 프론트가 붙을 때만 그 주소를 쉼표로.
3. **Apply**를 누르면 빌드(파이썬 + 프론트, 몇 분)와 실행이 시작된다.
4. 끝나면 서비스 주소(예: `https://chingu1-backend.onrender.com`)가 곧 심사용 URL이다.

환경 변수 전체: `PYTHON_VERSION`·`LLM_MODE`·`DATABASE_URL`·`FRONTEND_DIST`는 `render.yaml`에 값이 있다. `LLM_API_KEY`·`DEMO_TOKEN`·`CORS_ORIGINS`는 대시보드에서 넣는다. 키·토큰은 `VITE_*`에 절대 넣지 않는다(`VITE_*` 값은 화면 번들에 그대로 박혀 누구나 본다).

## 2. 잘 떴는지 확인

```bash
curl https://<서비스주소>/healthz
# {"db":"ok","llm_key":true,"llm_mode":"live","tz":"Asia/Seoul"} 이면 정상
curl -s https://<서비스주소>/ | head -5
# <!doctype html> ... 이면 화면도 정상
```

브라우저로 `https://<서비스주소>/`를 열어 화면이 뜨는지 본다. 빌드 로그에 `npm` 오류가 있으면 화면만 빠진 채 API는 뜰 수 있다(이때 `/`는 404).

`llm_key`가 `false`면 `LLM_API_KEY`가 비었다 → 대시보드 **Environment**에서 넣고 다시 배포.

## 3. 시연 직전 리셋

```bash
curl -X POST https://<서비스주소>/api/v1/demo/reset \
  -H "X-Demo-Token: <DEMO_TOKEN 값>" \
  -H "Content-Type: application/json" \
  -d '{"style":"EBSP","honorific":"hyung","polite":false}'
```

`{"ok":true,...}`가 오면 데모 아이·보호자·강사가 day3 상태가 된다. 토큰 값은 명령 기록·화면 녹화에 남지 않게 조심한다.

## 4. 꼭 알아 둘 것

- **DB는 사라진다.** 무료 플랜은 디스크가 휘발성이라 재시작·재배포·15분 무접속 슬립 뒤에 `/tmp/chingu1.db`가 빈다. 서버가 켜질 때 시드 20문제와 데모 배우(day3)를 자동으로 다시 만들어 바로 쓸 수는 있지만, 그날 대화·강사 메모·알림은 없어진다. 시연 전에는 리셋을 한 번 더 한다. 슬립에서 깨어나는 첫 요청은 30초~1분 걸릴 수 있다.
- **워커는 1개.** 시작 명령의 `--workers 1`을 늘리지 않는다. 여러 개면 빈 DB에 동시에 테이블·시드를 만들다 깨지고, 리셋의 `timer_scale`도 워커마다 달라진다.
- **로그 레벨 DEBUG 금지.** DEBUG에서는 DB 드라이버(aiosqlite)가 SQL 값(아이 문장 치환본)까지 로그에 찍는다. 기본(INFO)으로 둔다. `--log-level debug`·`LOG_LEVEL=DEBUG` 같은 설정을 넣지 않는다.
- **키는 환경 변수로만.** `render.yaml`에는 비밀 값을 적지 않는다. 키를 바꾸면 대시보드 Environment에서 바꾸고 다시 배포한다.
- 같은 세션에 메시지를 동시에 보내면 늦은 쪽은 409 `busy`가 간다(저장 안 됨). 프론트는 전송 중 버튼을 막아 두면 된다.
