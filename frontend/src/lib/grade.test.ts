import { describe, expect, it } from 'vitest';
import { GRADE_OPTIONS, gradeBand, gradeLabel, splitGrade, toGrade } from './grade';
import type { Grade } from '../types';

describe('학년 도우미', () => {
  it('학교급+학년 → 1~12 숫자', () => {
    expect(toGrade('초', 1)).toBe(1);
    expect(toGrade('초', 6)).toBe(6);
    expect(toGrade('중', 1)).toBe(7);
    expect(toGrade('고', 3)).toBe(12);
  });

  it('학교급 범위 밖 학년은 null', () => {
    expect(toGrade('중', 4)).toBeNull();
    expect(toGrade('초', 0)).toBeNull();
    expect(toGrade('고', 1.5)).toBeNull();
  });

  it('숫자 → 학교급+학년 (toGrade와 왕복)', () => {
    for (let g = 1; g <= 12; g++) {
      const { level, year } = splitGrade(g as Grade);
      expect(toGrade(level, year)).toBe(g);
    }
  });

  it('예전 데이터 4·5·6은 초4~초6으로 보인다', () => {
    expect(gradeLabel(4)).toBe('초4');
    expect(gradeLabel(6)).toBe('초6');
    expect(gradeLabel(9)).toBe('중3');
    expect(gradeLabel(null)).toBe('-');
  });

  it('학년대: 초등은 두 학년씩, 중·고는 하나로', () => {
    expect(gradeBand(1)).toBe('초1-2');
    expect(gradeBand(2)).toBe('초1-2');
    expect(gradeBand(5)).toBe('초5-6');
    expect(gradeBand(6)).toBe('초5-6');
    expect(gradeBand(8)).toBe('중');
    expect(gradeBand(11)).toBe('고');
  });
});

describe('GRADE_OPTIONS — 가입 학년을 초1~고3 한 목록으로(성호 11-14 「스크롤로 초1부터 고3까지」)', () => {
  it('12개, 1~12 순서, 이름은 「초등학교 1학년」 꼴', () => {
    expect(GRADE_OPTIONS.map((o) => o.grade)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    expect(GRADE_OPTIONS[0].label).toBe('초등학교 1학년');
    expect(GRADE_OPTIONS[6].label).toBe('중학교 1학년');
    expect(GRADE_OPTIONS[11].label).toBe('고등학교 3학년');
  });
});
