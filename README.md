# 친구1 (chingu1)

학원 초·중학생용 AI 멘토. 2026 AI 우왕톤 19팀 「재성합니다」.

- 무엇을 만드는지, 이미 정한 것, 작업 규칙: `CLAUDE.md`
- 명세 정본: `docs/spec_v0.4.md` (절 안내는 `.claude/skills/spec/`)
- 할 일·결정·회의는 노션 팀 허브 v3에만 적는다. 커밋·PR 제목에 `TK-n`.

## 처음 받았을 때

```bash
git config core.hooksPath .githooks        # TK 번호 없는 커밋 차단
cd backend && uv sync && uv run pytest     # 백엔드 (Python 3.12, uv)
cd frontend                                 # 프론트 (재하)
```

`.env`는 `backend/.env.example`을 복사해 만든다. 키는 커밋하지 않는다.
