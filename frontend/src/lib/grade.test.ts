import { describe, expect, it } from 'vitest';
import { gradeBand, gradeLabel, splitGrade, toGrade } from './grade';
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
