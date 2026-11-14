// 학년 도우미 — 초1~고3을 숫자 하나(1~12)로 저장하고, 화면에는 「초4」「중1」처럼 보인다.
// 숫자 하나로 두는 이유: 예전 데이터(4·5·6 = 초4~초6)가 그대로 맞고, 비교·정렬이 쉽다.
import type { Grade } from '../types';

export type SchoolLevel = '초' | '중' | '고';

/** 학교급마다 학년 수와 시작 번호(초1=1, 중1=7, 고1=10) */
export const SCHOOL_LEVELS: { level: SchoolLevel; label: string; years: number; start: number }[] = [
  { level: '초', label: '초등학교', years: 6, start: 1 },
  { level: '중', label: '중학교', years: 3, start: 7 },
  { level: '고', label: '고등학교', years: 3, start: 10 },
];

const info = (level: SchoolLevel) => SCHOOL_LEVELS.find((s) => s.level === level)!;

/** 학교급 + 그 학교 안의 학년(1부터) → 저장용 숫자. 범위 밖이면 null */
export function toGrade(level: SchoolLevel, year: number): Grade | null {
  const s = info(level);
  if (!Number.isInteger(year) || year < 1 || year > s.years) return null;
  return (s.start + year - 1) as Grade;
}

/** 저장용 숫자 → 학교급과 그 학교 안의 학년 */
export function splitGrade(grade: Grade): { level: SchoolLevel; year: number } {
  const s = [...SCHOOL_LEVELS].reverse().find((x) => grade >= x.start)!;
  return { level: s.level, year: grade - s.start + 1 };
}

/** 화면 표시: 4 → 「초4」, 7 → 「중1」. 없으면 「-」 */
export function gradeLabel(grade: Grade | null | undefined): string {
  if (!grade) return '-';
  const { level, year } = splitGrade(grade);
  return `${level}${year}`;
}

/**
 * AI 말투를 맞출 학년대. 서버 프롬프트의 grade_band 값으로 쓰려고 만든 것(백엔드 요청서 참고).
 * 발달 단계가 비슷한 학년끼리 묶는다: 초1-2 · 초3-4 · 초5-6 · 중 · 고
 */
export function gradeBand(grade: Grade): string {
  const { level, year } = splitGrade(grade);
  if (level !== '초') return level;
  const from = year % 2 === 1 ? year : year - 1;
  return `초${from}-${from + 1}`;
}
