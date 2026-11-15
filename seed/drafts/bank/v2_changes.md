# v2 설계도 변경 내역

45단원 → **49단원**(수학 19 · 국어 15 · 영어 15). 원본 3개는 그대로 두었다. 검증: 단원마다 문제 수 합 20, difficulty_mix 합 20(유형 개수와 일치), unit_id 중복 없음, 수학은 성취기준마다 2문제 이상(`covers` 기준) — `python3 -I`로 확인.

## 모든 단원에 공통으로 한 것

- **수학 19단원**: `answer_rules` 칸 추가(문제 끝 「(숫자만 써 주세요)」, 쉼표·단위·음수·식·좌표·구간 답 금지, 단원별 주의). 문제 유형마다 `covers`(덮는 성취기준 코드) 추가. `needs_judge`는 아이가 실제로 칠 형식만 남김(`unit_suffix`·`thousands_comma`·`korean_mixed_number`). 문제 설계로 피한 형식(expr·negative·interval·tuple·complex·set·matrix·choice·symbolic)은 지웠다.
- 공통 규칙은 `v2_generation_rules.md`로 따로 저장(검토 10개 + 추가 10개).

## 고1 수학을 9단원으로 한 이유

성호 결정(1년 전체)에 따라 검토 수정안 ①~⑤에 ⑥ 여러 가지 방정식 ⑦ 행렬을 더했다. ⑧ 집합과 명제(성취기준 8개)에 함수(5개)를 합치면 13개로 원래 과밀 단원과 같아져 기준당 2문제가 안 되므로, 함수를 따로 떼어 **9단원**이 되었다. 9단원 성취기준 수는 3·3·6·2·3·2·7·8·5개로 모두 20문제 안에서 기준당 2문제 이상.

## 수학

| unit_id | 변경 |
|---|---|
| g4-math-large-numbers | needs_judge `thousands_comma`, 「쉼표 없이 숫자만」 안내, 답 10자리 이하 |
| g4-math-multiply-divide | 어림셈 2문제 → 나누어떨어지는 나눗셈 문장제 2문제, 성취기준 [4수01-08] 제외(어림셈 학년 1차 확인 대기), `unit_suffix` |
| g4-math-fraction-decimal-add-sub | 「답은 가분수로」 삭제, 대분수 「1 2/3」·가분수 모두 정답, 입력 예 한 번 보여 주기, needs_judge `mixed_number` → `korean_mixed_number`(「1과 3분의 2」) |
| g4-math-angles-polygons | 오개념 「변이 길면 각이 크다」 → 「평행사변형 이웃한 각도 같다고 봄」, 빠져 있던 [4수03-09] 예각·둔각삼각형 개수 2문제 추가(합·차와 사각형 각 1문제씩 감소), answer_form의 「(도)」 삭제, `unit_suffix` |
| g4-math-patterns-graphs | 「두 시각 사이 값 어림」 삭제 → 변화량만, `unit_suffix` |
| g8-math-repeating-decimals-exponents | 이름 서술형, 순환소수 표기 「0.1666…(6이 되풀이)」로 통일(오개념 문구 포함), `expr` 삭제 |
| g8-math-inequalities-systems | 이름 서술형, interval·tuple·negative 삭제 → `unit_suffix` |
| g8-math-linear-functions | 이름 「일차함수의 기울기·절편 구하고 활용하기」, negative·tuple·expr 삭제 → `unit_suffix` |
| g8-math-triangles-similarity-pythagoras | 이름 서술형, 넓이비 2문제 추가(닮음비 대응변 3→1), 무게중심·부피비 「범위 밖」 → 「이번엔 제외, 1차 확인 대기」, 피타고라스 메모 오류 수정(2015부터 중2), `unit_suffix` |
| g8-math-counting-probability | 이름 「경우의 수 세기와 확률 구하기」, 약분 안 한 분수 정답 처리 확정, `unit_suffix`(「가지」) |
| g10-math-polynomials | 이름 「다항식을 계산하고 나머지·인수 찾기」, expr·negative 삭제 |
| g10-math-complex-quadratic-equations | **신설**(구 complex-quadratics 분할 ①): 02-01~03, 답이 하나뿐이도록 '양수인' 조건 명시 |
| g10-math-quadratic-functions-inequalities | **신설**(분할 ②): 02-04~06·09~11, 구간 답 대신 정수 해 개수·a + b, `unit_suffix` |
| g10-math-higher-degree-equations | **신설**(분할 ③, 성호 결정): 02-07~08 삼·사차·연립이차, 공통수학1 포함은 research v0.2 표([2차]) 근거, 1차 확인 대기, ω 성질은 이번엔 제외 |
| g10-math-counting | **id 변경**(구 counting-matrices): 행렬 5문제 분리, 이름 「순열·조합으로 경우의 수 세기」, 빈자리는 기본 줄 세우기·대표 뽑기·길 찾기로 |
| g10-math-matrices | **신설**(구 counting-matrices에서 분리): 04-01~02 20문제, 행렬 글 표기 규칙 |
| g10-math-coordinate-geometry | 이름 서술형, 평행이동·대칭이동 2문제씩 분리(점·직선 거리 3→2), tuple·negative·symbolic 삭제, √ 안 남게 규칙 |
| g10-math-sets-propositions | **신설**(구 sets-propositions-functions 분할 ①): 02-01~08, 명제는 「참인 것의 개수」, 증명은 번호 고르기 2문제 |
| g10-math-functions | **신설**(분할 ②): 03-01~05, 함수식 답 대신 함숫값·상수·p + q |

삭제된 unit_id: `g10-math-complex-quadratics`, `g10-math-counting-matrices`, `g10-math-sets-propositions-functions`.

## 국어

| unit_id | 변경 |
|---|---|
| g4-kor-word-relations | verified 「1차(교육청)」, 사전 순서 쌍자음·겹모음 확인 메모 |
| g4-kor-main-idea | verified 「1차(교육청)」 |
| g4-kor-fact-opinion | verified 「1차(교육청)」, 사실/의견 단답 정답 2:2로 섞기 |
| g4-kor-honorific-connective | verified 「1차(교육청)」, 높임 바른 문장 고르기에서 물건 높임 오답 제외(hard 2문제 몫) |
| g4-kor-sensory-character | verified 「1차(교육청)」, 「마음 한 낱말 쓰기」 2문제 → 객관식 |
| g8-kor-parts-of-speech | 이름 「낱말을 품사로 나누기」, `grade_band` 중1~3·학교별 진도 다름, 코드 1차 확인 대기 |
| g8-kor-word-formation | `grade_band`, 코드 1차 확인 대기 |
| g8-kor-spelling-basics | `grade_band`, 표준국어대사전 대조 필수·needs_review, 코드 1차 확인 대기 |
| g8-kor-explain-argue-methods | `grade_band`, 코드 1차 확인 대기 |
| g8-kor-figurative-speaker | `grade_band`(운율·비유 중1 가능), 코드 1차 확인 대기 |
| g10-kor-phonological-change | 변경 없음 |
| g10-kor-grammar-expression-effect | 변경 없음 |
| g10-kor-spelling-principles | 중2 맞춤법 낱말 겹침 금지, 다음 판 비문학 교체 후보 메모 |
| g10-kor-argument-validity | 변경 없음(띄어쓰기 변형 허용은 원본에 있음) |
| g10-kor-genre-representation | 변경 없음 |

## 영어 (15단원 모두 verified 「2차」 → 「1차(NCIC 대조)」)

| unit_id | 변경 |
|---|---|
| g4-eng-everyday-words | verified만 |
| g4-eng-age-time-numbers | 숫자 단답 one~ten만 3문제, eleven~twenty는 객관식 2문제로 |
| g4-eng-weather-feelings | verified만 |
| g4-eng-commands | 어법 판단 hard 4 → 「3줄 대화 상황에 맞는 지시·금지 표현 고르기」, 형식 오개념 2개 → 의미 오개념으로 |
| g4-eng-can-ability | 오개념 「He can swims」 삭제, easy 9→7(대답 고르기 2문제를 medium 3줄 대화로) |
| g8-eng-to-infinitive-gerund | 단답을 「enjoy ___」 3 + 「want to ___」 2로 섞음, `standards_basis`(별표 4), `grade_band` |
| g8-eng-comparison | `standards_basis`, `grade_band` |
| g8-eng-conjunctions-logic | `standards_basis`, `grade_band` |
| g8-eng-passive-basic | `standards_basis`, `grade_band`(중3일 수 있음) |
| g8-eng-main-idea-detail | `grade_band` |
| g10-eng-main-idea-title | verified만 |
| g10-eng-logical-flow | easy 0 → 4(두 문장 연결어 고르기), 연결어 단답은 후보 4개 중 하나 치기 |
| g10-eng-participle-adjectives | `standards_basis`, `grade_band` 중2~고1 [추측] |
| g10-eng-relative-clauses | `standards_basis`, `grade_band` 중3~고1 [추측] |
| g10-eng-tense-voice-verbals | 「바른 문장 개수 고르기」 → 「틀린 것 고르기」, 현재완료 단답은 have 뒤 과거분사 한 단어, `standards_basis`, `grade_band` 중2~고1 [추측] |

## 11-12 원문 확인 반영 (primary_check.md)
- g8-math-triangles-similarity-pythagoras: 넓이비 2문제 → 무게중심 2문제(원문 용어 목록·지학사 중2 차례에 있음, 넓이비는 원문 명시 없음). 오개념·범위 밖 목록 맞춤.
- g8-kor-explain-argue-methods: [9국02-02](요약) 제거, [9국02-05]만.
- 공통수학1·2 코드 전부, 국어 확인 코드 12개, [9수03-12]·[9수03-15] → verified 1차. 고1 수학 notes의 「1차 확인 대기」 → 「1차 확인됨」.
- 초4 어림셈 삭제는 원문으로 맞음([6수01-03] 올림·버림·반올림은 5~6학년군).
