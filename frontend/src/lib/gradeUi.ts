// 학년 선택 vs 체험 문제(초5~6 분수 나눗셈) 안내 시안 A·B·C — 11-14 성호 결정: C(기본). A·B는 스위치로만 남긴다.
// 학년 숫자는 grade.ts(초1=1 … 고3=12). B는 초5·6(5·6)만 연다.
// 바꾸는 법: 주소에 ?grade-ui=a|b|c (예: /?grade-ui=b#/signup 또는 #/signup?grade-ui=b). 한 번 넣으면 이 브라우저에 기억.
// A: 학년은 말투에만, 오늘 할 일에 안내 한 줄 / B: 학년은 초5·6만 열고 나머지 「준비 중」 / C: A + 학년 고르는 곳에 말투 안내
import { load, save } from './storage';

export type GradeUi = 'a' | 'b' | 'c';
// 11-14 성호 결정으로 기본이 C → 예전에 기본값(A)이 저절로 저장된 브라우저도 C를 보게 키 이름을 바꾼다
const KEY = 'chingu1.gradeUi.v2';
const isGradeUi = (v: unknown): v is GradeUi => v === 'a' || v === 'b' || v === 'c';

export const GRADE_NOTE = '체험 문제는 초5~6 분수 나눗셈이에요';
export const TONE_NOTE = '다른 학년은 말투만 바뀌어요';

/** 주소(해시 앞 ?·해시 뒤 ?) → 저장값 → 기본 C(성호 결정 11-14) 순서로 고른다 */
export function parseGradeUi(search: string, hash: string, stored: unknown): GradeUi {
  const q = new URLSearchParams(search).get('grade-ui') ?? new URLSearchParams(hash.split('?')[1] ?? '').get('grade-ui');
  if (isGradeUi(q)) return q;
  return isGradeUi(stored) ? stored : 'c';
}

export function currentGradeUi(): GradeUi {
  if (typeof window === 'undefined') return 'a';
  const v = parseGradeUi(window.location.search, window.location.hash, load<unknown>(KEY, null));
  save(KEY, v);
  return v;
}

export const showGradeNote = (v: GradeUi) => v !== 'b';
export const showToneNote = (v: GradeUi) => v === 'c';
export const gradeOpen = (v: GradeUi, grade: number) => v !== 'b' || grade === 5 || grade === 6;
