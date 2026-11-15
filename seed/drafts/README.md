# 문제 은행 초안 (seed/drafts) — 시연 시드 아님

**시연 정본은 `seed/seed_v0.1.json`(초6 분수 20문제)이다. 이 폴더는 서버에 넣지 않은 초안이다.**

- `bank/v2_blueprint_{math,korean,english}.json`: 49단원 설계도(초4·중2·고1 × 수학·국어·영어). 시범 3단원은 검토를 반영해 고쳤다.
- `bank/problems_v2/`: **시범 60문제 현재본**(초4 수학 큰 수, 중2 국어 품사, 고1 영어 관계사). `bank/problems/`는 처음 만든 판(v1)으로, 비교용이다.
- `bank/gen_prompt_v2.md`, `bank/v2_generation_rules_v2.md`: 생성 지시와 규칙(현재본). `*_v1`·이름에 v2가 없는 것은 옛 판이다.
- 검토:
  - `bank/blueprint_review.md`: 설계도 검토
  - `bank/pilot_review.md`: 시범 검토와 11-13 재검사
  - `bank/pilot_fix_log.md`: 고친 내역
  - `bank/primary_check.md`: 성취기준 1차 대조
- `server_todo.md`: 학년별 문제를 서버에서 쓰려면 남은 일.
- 검사(이 폴더에서 실행):
  - `python3 -I tools/check_bank.py bank/problems_v2/*.json --blueprint bank/v2_blueprint_*.json`
    - 저장소 `backend/app/judge.py`와 `seed/validate_seed.py`를 불러 쓴다. 저장소 경로가 파일 안에 고정돼 있다.
  - `python3 -I tools/check_v2_extra.py bank/problems_v2/*.json --blueprint bank/v2_blueprint_*.json`
- 다시 만들기: `tools/build_pilot_v2.py`(시범 v2 생성), `tools/patch_pilot_blueprints.py`(설계도 반영).
- 모든 문제는 AI 생성(Claude)이다. 지문과 예문은 새로 썼다. 교사 검수와 유사성 대조는 하지 않았다(`docs/problem_pipeline_v0.1.md`).
