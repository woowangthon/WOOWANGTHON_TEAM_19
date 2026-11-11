# Render 배포 안내 v0.1 (TK-56, 백엔드)

성호가 Render 대시보드에서 직접 하는 일만 적었다. 설정은 저장소 루트 `render.yaml`에 있다.

## 1. 처음 한 번

1. Render 대시보드 → **New → Blueprint** → GitHub 저장소 `chingu1`을 고른다. Render가 `render.yaml`을 읽어 웹 서비스 `chingu1-backend`(무료 플랜, 폴더 `backend`)를 보여 준다.
2. 값을 물어보는 환경 변수 3개를 채운다(`sync: false`라 Render가 처음 만들 때만 묻는다).
   - `LLM_API_KEY` — LLM 키. 다른 곳(코드·노션·채팅)에는 적지 않는다.
   - `DEMO_TOKEN` — 리셋용 비밀 문자열. 길게 아무렇게나 정하고 시연자만 안다.
   - `CORS_ORIGINS` — 배포된 프론트 주소(예: `https://프론트주소`). 여러 개면 쉼표로.
3. **Apply**를 누르면 빌드(`uv sync`)와 실행이 시작된다. 몇 분 걸린다.
4. 끝나면 서비스 주소(예: `https://chingu1-backend.onrender.com`)를 재하에게 준다.

## 2. 잘 떴는지 확인

```bash
curl https://<서비스주소>/healthz
# {"db":"ok","llm_key":true,"llm_mode":"live","tz":"Asia/Seoul"} 이면 정상
```

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
