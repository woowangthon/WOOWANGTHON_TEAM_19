// 학습 엔진 — 서버가 해야 하는 "판단"을 모아 둔 순수 함수들.
// (문제 만들기, 정답 판정, 실수 유형 분류, 힌트 사다리, 풀이, 수다 응답, 위험 표현 감지)
// mock.ts가 이 함수들을 써서 가짜 서버 노릇을 한다. 백엔드를 만들 때 이 파일의 규칙을 그대로 옮기면 된다.
// 화면(screens/)에서는 이 파일을 직접 import하지 않는다 → 정답이 화면 코드로 새지 않게.
import type { Difficulty, Fraction, Speech } from '../types';

export type UnitName = '분수의 덧셈' | '분수의 뺄셈';
export const PROBLEM_UNITS: UnitName[] = ['분수의 덧셈', '분수의 뺄셈'];

export interface Problem {
  id: string;
  left: Fraction;
  right: Fraction;
  op: '+' | '-';
  answer: Fraction; // 통분한 분모 기준(약분 전). 약분한 답도 정답으로 인정한다
  k: number;        // 왼쪽 분수에 곱하는 통분 배수(분모가 같으면 1)
}

/** 반말/존댓말 중 하나 고르기 */
export const tone = (speech: Speech, casual: string, polite: string) => (speech === '존댓말' ? polite : casual);

/* ---------- 문제 만들기 ---------- */
// 같은 날·같은 난이도면 같은 문제가 나오도록 씨앗(seed)으로 만드는 난수
function rng(seed: string) {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619); }
  return () => {
    h += 0x6d2b79f5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * 난이도 규칙
 * - 초급: 분모가 같은 분수(분모 3~7)
 * - 중급: 분모가 같은 분수(분모 8~12)
 * - 고급: 분모가 다른 분수(한쪽 분모가 다른 쪽의 2~3배) → 통분 필요
 * 답은 항상 0보다 크고 1보다 작다(진분수).
 */
export function generateProblems(unit: UnitName, difficulty: Difficulty, seed: string, count = 5): Problem[] {
  const r = rng(`${seed}|${unit}|${difficulty}`);
  const int = (a: number, b: number) => a + Math.floor(r() * (b - a + 1));
  const op = unit === '분수의 뺄셈' ? '-' : '+';
  const out: Problem[] = [];
  const seen = new Set<string>();
  for (let guard = 0; out.length < count && guard < 2000; guard++) {
    let left: Fraction, right: Fraction, answer: Fraction, k = 1;
    if (difficulty === '고급') {
      const b = int(2, 5); k = int(2, 3);
      const D = b * k, a = int(1, b - 1), c = int(1, D - 1);
      const num = op === '+' ? a * k + c : a * k - c;
      if (num <= 0 || num >= D) continue;
      left = [a, b]; right = [c, D]; answer = [num, D];
    } else {
      const D = difficulty === '초급' ? int(3, 7) : int(8, 12);
      const a = int(1, D - 1), c = int(1, D - 1);
      const num = op === '+' ? a + c : a - c;
      if (num <= 0 || num >= D) continue;
      left = [a, D]; right = [c, D]; answer = [num, D];
    }
    const key = `${left}|${right}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ id: `p${out.length + 1}`, left, right, op, answer, k });
  }
  return out;
}

/* ---------- 정답 판정 + 실수 유형 ---------- */
export interface Judgement { correct: boolean; numeratorOk: boolean; denominatorOk: boolean; tag: string | null; }

export function judge(p: Problem, n: number, d: number): Judgement {
  const [num, D] = p.answer;
  if (d > 0 && n * D === num * d) return { correct: true, numeratorOk: true, denominatorOk: true, tag: null };
  const [a, b] = p.left, [c, dd] = p.right;
  const naive = p.op === '+' ? a + c : a - c; // 통분 없이 분자끼리만 계산한 값
  let tag = '기타';
  if (n === naive && d === (p.op === '+' ? b + dd : Math.abs(b - dd))) tag = p.op === '+' ? '분모끼리 더하기' : '분모끼리 빼기';
  else if (p.k > 1 && n === naive) tag = '통분 빠뜨림';
  else if (d === D) tag = '분자 계산';
  else if (n === num) tag = '분모 처리';
  return { correct: false, numeratorOk: n === num, denominatorOk: d === D, tag };
}

/** 실수 유형 → 학생이 고르는 "어려웠던 점" 칩 문구 */
export function chipForTag(tag: string): string | null {
  if (tag.startsWith('분모')) return '분모가 헷갈렸어';
  if (tag === '분자 계산') return '분자 계산이 헷갈렸어';
  if (tag === '통분 빠뜨림') return '분모 맞추기가 어려웠어';
  return null;
}

/* ---------- 힌트 사다리(최대 3개) + 풀이 ---------- */
export const MAX_HINTS = 3;

export function hintsFor(p: Problem, s: Speech): string[] {
  const [a, b] = p.left, [c, D] = p.right;
  const verb = p.op === '+' ? '더하' : '빼';
  if (p.k === 1) return [
    tone(s, `분모가 같으면 어디만 ${verb}면 될까?`, `분모가 같으면 어디만 ${verb}면 될까요?`),
    tone(s, `분자끼리만 ${verb} 봐. ${a} ${p.op} ${c}는?`, `분자끼리만 ${verb} 보세요. ${a} ${p.op} ${c}는요?`),
    tone(s, `분모 ${b}는 그대로야. 조각 크기는 바뀌지 않거든.`, `분모 ${b}는 그대로예요. 조각 크기는 바뀌지 않거든요.`),
  ];
  return [
    tone(s, '분모가 다르면 먼저 무엇을 맞춰야 할까?', '분모가 다르면 먼저 무엇을 맞춰야 할까요?'),
    tone(s, `${a}/${b}를 분모가 ${D}인 분수로 바꿔 봐. 위아래에 ${p.k}를 곱하면 돼.`, `${a}/${b}를 분모가 ${D}인 분수로 바꿔 보세요. 위아래에 ${p.k}를 곱하면 돼요.`),
    tone(s, `이제 ${a * p.k}/${D} ${p.op} ${c}/${D}야. 분자끼리만 계산해 봐.`, `이제 ${a * p.k}/${D} ${p.op} ${c}/${D}예요. 분자끼리만 계산해 보세요.`),
  ];
}

/** 풀이 같이 보기 — 힌트를 다 쓰고도 틀렸을 때만 서버가 내려 준다 */
export function solutionFor(p: Problem, s: Speech): string[] {
  const [a, b] = p.left, [c, D] = p.right, [num] = p.answer;
  const steps: string[] = [];
  if (p.k > 1) steps.push(tone(s, `분모를 ${D}로 맞춰: ${a}/${b} = ${a * p.k}/${D}`, `분모를 ${D}로 맞춰요: ${a}/${b} = ${a * p.k}/${D}`));
  else steps.push(tone(s, `분모가 ${D}로 같으니까 분모는 그대로 둬.`, `분모가 ${D}로 같으니까 분모는 그대로 둬요.`));
  steps.push(tone(s, `분자끼리 계산해: ${a * p.k} ${p.op} ${c} = ${num}`, `분자끼리 계산해요: ${a * p.k} ${p.op} ${c} = ${num}`));
  steps.push(tone(s, `그래서 답은 ${num}/${D}야.`, `그래서 답은 ${num}/${D}예요.`));
  return steps;
}

/* ---------- 멘토 말 ---------- */
const CORRECT = [['맞았어! 잘했어.', '맞았어요! 잘했어요.'], ['정답! 차근차근 잘 풀었어.', '정답이에요! 차근차근 잘 풀었어요.'], ['좋아, 바로 그거야.', '좋아요, 바로 그거예요.']];
export const correctLine = (i: number, s: Speech) => tone(s, CORRECT[i % CORRECT.length][0], CORRECT[i % CORRECT.length][1]);
export const wrongLine = (partial: boolean, s: Speech) => partial
  ? tone(s, '아깝다! 여기까지는 맞았어', '아까워요! 여기까지는 맞았어요')
  : tone(s, '괜찮아, 같이 다시 보자', '괜찮아요, 같이 다시 봐요');
export const openingLine = (allSolved: boolean, s: Speech) => allSolved
  ? tone(s, '오늘 문제 다 끝냈네!\n오늘 학원은 어땠어?', '오늘 문제 다 끝냈네요!\n오늘 학원은 어땠어요?')
  : tone(s, '오늘도 수고했어!\n오늘 학원은 어땠어?', '오늘도 수고했어요!\n오늘 학원은 어땠어요?');

/* ---------- 수다 응답(대본) ---------- */
// 실제 서비스에서는 LLM 어댑터가 문장을 만든다. 여기는 LLM 없이 도는 "대본(scripted)" 모드.
const TOPICS: { keys: string[]; lines: [string, string][] }[] = [
  { keys: ['피곤', '힘들', '졸려', '지쳤'], lines: [['오늘 많이 달렸구나. 제일 힘들었던 건 뭐였어?', '오늘 많이 달렸군요. 제일 힘들었던 건 뭐였어요?'], ['그럴 땐 푹 쉬는 것도 공부야. 오늘은 일찍 자자.', '그럴 땐 푹 쉬는 것도 공부예요. 오늘은 일찍 자요.']] },
  { keys: ['자랑', '잘했', '칭찬', '맞혔', '백점', '100점'], lines: [['오, 뭔데 뭔데? 얼른 말해 줘!', '오, 뭔데요? 얼른 말해 주세요!'], ['와, 그건 진짜 자랑할 만하다. 기분 어땠어?', '와, 그건 정말 자랑할 만해요. 기분이 어땠어요?']] },
  { keys: ['친구', '싸웠', '놀렸', '같이 놀'], lines: [['친구랑 무슨 일이 있었어? 천천히 말해 줘.', '친구랑 무슨 일이 있었어요? 천천히 말해 주세요.'], ['그랬구나. 그때 네 마음은 어땠어?', '그랬군요. 그때 마음이 어땠어요?']] },
  { keys: ['게임', '놀았', '재밌', '재미있', '웃겼'], lines: [['오 그거 재밌겠다! 어떤 점이 제일 좋았어?', '오 그거 재밌겠어요! 어떤 점이 제일 좋았어요?'], ['듣기만 해도 신난다. 그래서 어떻게 됐어?', '듣기만 해도 신나요. 그래서 어떻게 됐어요?']] },
  { keys: ['엄마', '아빠', '선생님', '혼났', '혼나'], lines: [['그랬구나. 그 얘기 조금 더 들려줄래?', '그랬군요. 그 얘기 조금 더 들려줄래요?'], ['속상했겠다. 지금은 좀 괜찮아?', '속상했겠어요. 지금은 좀 괜찮아요?']] },
];
const GENERAL: [string, string][] = [
  ['그랬구나. 조금 더 말해 줄래?', '그랬군요. 조금 더 말해 줄래요?'],
  ['응응, 듣고 있어. 그래서?', '네, 듣고 있어요. 그래서요?'],
  ['그때 기분은 어땠어?', '그때 기분은 어땠어요?'],
  ['말해 줘서 고마워. 오늘 하루 수고 많았어.', '말해 줘서 고마워요. 오늘 하루 수고 많았어요.'],
  ['오늘 제일 기억에 남는 건 뭐야?', '오늘 제일 기억에 남는 건 뭐예요?'],
];
/** turn: 지금까지 학생이 보낸 메시지 수(0부터). 같은 말이 연달아 나오지 않게 순서대로 돌린다. */
export function replyFor(text: string, turn: number, s: Speech): string {
  const topic = TOPICS.find((t) => t.keys.some((k) => text.includes(k)));
  const pool = topic ? topic.lines : GENERAL;
  const [casual, polite] = pool[turn % pool.length];
  return tone(s, casual, polite);
}

/* ---------- 안전 ---------- */
// 시연용 최소 목록. 실제 서버는 명세 부록 A의 키워드 30개를 쓴다.
const CRISIS_KEYWORDS = ['죽고싶', '죽고 싶', '사라지고싶', '사라지고 싶', '자해', '자살', '죽어버리'];
export const detectCrisis = (text: string) => CRISIS_KEYWORDS.some((k) => text.includes(k));
export const crisisLine = (s: Speech) => tone(s, '말해 줘서 정말 고마워.\n지금은 믿을 수 있는 어른과\n꼭 이야기했으면 좋겠어.', '말해 줘서 정말 고마워요.\n지금은 믿을 수 있는 어른과\n꼭 이야기했으면 좋겠어요.');

/** 저장 전에 전화번호·이메일을 가린다(개인정보 최소 보관). 이름·학교 인식은 후속. */
export const maskPII = (text: string) => text
  .replace(/01[016789][-\s]?\d{3,4}[-\s]?\d{4}/g, '[전화번호]')
  .replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g, '[이메일]');
