// 학년 안내 시안 스위치(A·B·C) 판단 로직 테스트
import { describe, expect, it } from 'vitest';
import { gradeOpen, parseGradeUi, showGradeNote, showToneNote } from './gradeUi';

describe('parseGradeUi — 주소의 grade-ui 값을 읽고 없으면 저장값, 그것도 없으면 A', () => {
  it('주소 ?grade-ui=b 를 읽는다 (해시 앞·뒤 모두)', () => {
    expect(parseGradeUi('?grade-ui=b', '', null)).toBe('b');
    expect(parseGradeUi('', '#/signup?grade-ui=c', null)).toBe('c');
  });
  it('이상한 값은 무시하고 저장값 → 기본 A', () => {
    expect(parseGradeUi('?grade-ui=z', '', 'c')).toBe('c');
    expect(parseGradeUi('', '', null)).toBe('a');
    expect(parseGradeUi('', '', 'x')).toBe('a');
  });
});

describe('시안별 화면 차이', () => {
  it('A·C는 오늘 할 일에 체험 문제 안내, B는 없음', () => {
    expect(showGradeNote('a')).toBe(true);
    expect(showGradeNote('b')).toBe(false);
    expect(showGradeNote('c')).toBe(true);
  });
  it('C만 학년 고르는 화면에 말투 안내', () => {
    expect(['a', 'b', 'c'].map((v) => showToneNote(v as 'a'))).toEqual([false, false, true]);
  });
  it('B는 초5·6만 고를 수 있고 나머지는 준비 중', () => {
    expect(gradeOpen('b', 4)).toBe(false);
    expect(gradeOpen('b', 5)).toBe(true);
    expect(gradeOpen('b', 6)).toBe(true);
    expect(gradeOpen('b', 1)).toBe(false);
    expect(gradeOpen('b', 9)).toBe(false);
    expect(gradeOpen('a', 4)).toBe(true);
    expect(gradeOpen('c', 12)).toBe(true);
  });
});
