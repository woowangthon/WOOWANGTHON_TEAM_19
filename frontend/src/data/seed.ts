// 시연용 가상 데이터. 실제 학생 기록이 아니다.
import type { StudentResult, Unit } from '../types';

export const CLASS_NAME = '4학년 A반';
export const TEACHER_NAME = '김선생님';
export const STUDENT = { id: 's1', name: '지우', fullName: '김지우' };

/** 문제 은행이 있는 단원은 hasProblems=true (지금은 분수 두 단원) */
export const SEED_UNITS: Unit[] = [
  { id: 'u1', name: '큰 수', count: 8, selected: false, hasProblems: false },
  { id: 'u2', name: '각도', count: 6, selected: false, hasProblems: false },
  { id: 'u3', name: '곱셈과 나눗셈', count: 10, selected: false, hasProblems: false },
  { id: 'u4', name: '분수의 덧셈', count: 5, selected: true, hasProblems: true },
  { id: 'u5', name: '분수의 뺄셈', count: 5, selected: true, hasProblems: true },
  { id: 'u6', name: '소수의 덧셈', count: 6, selected: false, hasProblems: false },
];

/** 지우 외 다른 학생(고정 데이터) */
export const OTHER_RESULTS: StudentResult[] = [
  { id: 's2', name: '이민준', done: true, unit: '분수의 덧셈', solved: 5, total: 5, difficulty: '초급', streak: 7, hints: 3, mistake: '분자 계산 2회', hardPoint: null, beginnerRepeat: 5 },
  { id: 's3', name: '박서연', done: true, unit: '분수의 덧셈', solved: 5, total: 5, difficulty: '고급', streak: 3, hints: 1, mistake: '통분 빠뜨림 1회', hardPoint: '다 쉬웠어', beginnerRepeat: 0 },
];
