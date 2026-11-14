# 문제 생성 지시 (공통, v1)

너는 「친구1」(학원 초·중학생용 AI 멘토 앱) 문제 은행의 문제를 만든다. 아이는 폰 채팅으로 문제를 풀고, AI 멘토가 힌트 0→1→2→(3: 풀이)를 단계적으로 준다. 정답은 서버 코드만 판정한다.

## 입력
- 단원 설계도: `bank/v2_blueprint_<subject>.json`에서 지정된 `unit_id` 한 개. **problem_types의 유형·개수·난이도, core_concepts, misconceptions, out_of_scope, answer_rules, notes를 그대로 따른다.**
- 공통 규칙: `bank/v2_generation_rules.md` 전부(반드시 읽기).
(경로 기준: `seed/drafts/`(저장소 안))

## 출력
`bank/problems/<unit_id>.json` — JSON 배열, 설계도 count 합만큼(보통 20). 각 문제:

```json
{
  "id": "<unit_id>-01",
  "unit_id": "<unit_id>",
  "tag": "<unit_id>",
  "subject": "math|korean|english",
  "grade": 4,
  "standard": {"code": "[4수01-01]", "curriculum": "2022", "unit": "<설계도 unit_name>"},
  "difficulty": "easy|medium|hard",
  "problem_type": "<설계도 problem_types[].type 그대로>",
  "targets_misconception": "<겨냥하는 오개념 한 줄, 없으면 빈 문자열>",
  "text": "<문제. 객관식이면 보기 ①~④를 줄바꿈으로 포함. 수학은 끝에 (숫자만)>",
  "expr": "<수학만: 정답을 계산하는 파이썬 산술식. 정수·+ - * / 괄호만. 예: '3/4 / 2', '12*100+5'>",
  "answer": {"kind": "value|choice|text", "value": "<정답>", "accepted": ["<허용 표기>"]},
  "hint1": "<방향만. 정답·정답 기호·정답 낱말 금지>",
  "hint2": "<더 구체적. 그래도 정답 금지>",
  "solution": "<풀이(힌트 3단계에서 보여 줌). 정답 포함 가능>",
  "forbidden": ["<멘토 응답에 나오면 안 되는 정답 표기들>"],
  "source": "ai",
  "generator": "claude-opus-5-5",
  "review": "none"
}
```

## 규칙 요약 (상세는 v2_generation_rules.md)
1. **답은 하나.** 열린 질문 금지.
2. **수학**: `answer.kind="value"`, value는 양의 정수·기약분수(a/b)·유한소수·대분수 중 하나. `expr`를 계산하면 value와 같아야 한다. accepted에는 현재 채점기가 읽는 표기만(정수, a/b, 소수, 「b분의 a」, 「n a/b」). 단위·쉼표·음수·식 답 금지. forbidden에는 value의 기약분수·소수·「b분의 a」 표기를 넣는다.
3. **객관식**: `kind="choice"`, value는 ①~④ 중 하나, accepted = [기호, 숫자, "n번", 보기 문구]. **단원 안에서 정답 위치를 ①②③④ 고르게**(각 25% 안팎). 오답 보기는 misconceptions에서.
4. **단답(text)**: 한 단어. accepted에 대소문자 변형 불필요(서버가 무시 예정), 철자 변형은 넣지 않는다.
5. **힌트**: hint1·hint2에 정답 값·정답 기호·정답 낱말이 들어가면 안 된다. 수학에서 정답이 한 자리 수면 힌트에 그 숫자를 아예 쓰지 않는다(누설 검사가 잡는다).
6. **지문·예문은 전부 새로 쓴다.** 교과서·기출·수능·실제 문학 작품·실존 인물·상표 금지. 설계도의 지문 길이 상한을 지킨다.
7. **out_of_scope 개념은 풀이에도 쓰지 않는다.** 그림 없이 글만으로 풀려야 한다.
8. 같은 단원 안에서 같은 수·같은 문장 틀을 반복하지 않는다(문제 글 중복은 FAIL).

## 끝내기 전에 (필수)
```
python3 -I tools/check_bank.py bank/problems/<unit_id>.json --blueprint bank/v2_blueprint_<subject>.json
```
(scratchpad 폴더에서 실행.) **FAIL 0**이 될 때까지 고친다. WARN은 고치거나, 안 고치는 이유를 최종 답에 적는다. 저장소(코드·seed/) 파일은 고치지 않는다.

## 최종 답
파일 경로, 검사 결과 마지막 줄(총 n문제 · FAIL · WARN), 남은 WARN과 이유, 설계도대로 만들기 어려웠던 점(→ 규칙 보정 재료). 한국어.
