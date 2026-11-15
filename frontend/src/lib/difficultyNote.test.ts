// 풀기 화면 난이도 안내 한 줄(D4, 명세 4.13-7): 서버 note → 아이 문장(반말·존댓말)
import { describe, expect, it } from 'vitest';
import { assignedByLine, difficultyNoteLine } from './difficultyNote';

const say = (polite: boolean) => (c: string, p: string) => (polite ? p : c);

describe('난이도 안내 한 줄', () => {
  it('선생님이 정한 문제', () => {
    expect(difficultyNoteLine('instructor', '초급', '고급', say(false))).toBe('선생님이 정한 문제야');
    expect(difficultyNoteLine('instructor', '초급', '고급', say(true))).toBe('선생님이 정한 문제예요');
  });
  it('고른 난이도를 다 풀어 가까운 난이도', () => {
    expect(difficultyNoteLine('nearby', '고급', '중급', say(false))).toBe('고급 문제는 이미 다 나와서 중급 문제를 냈어');
    expect(difficultyNoteLine('nearby', '고급', '중급', say(true))).toBe('고급 문제는 이미 다 나와서 중급 문제를 냈어요');
  });
  it('다시 풀기·없음', () => {
    expect(difficultyNoteLine('repeat', '중급', '중급', say(false))).toBe('전에 나온 문제를 다시 풀어 보자');
    expect(difficultyNoteLine(null, '중급', '중급', say(false))).toBeNull();
    expect(difficultyNoteLine(undefined, null, '중급', say(true))).toBeNull();
  });
  it('오늘 홈 「누가 정했나」: 선생님 아니면 규칙대로 골랐다고(앱 내부 이름·AI 말처럼 안 보임)', () => {
    expect(assignedByLine('선생님', say(false))).toBe('선생님이 정해 줬어');
    expect(assignedByLine('친구1', say(false))).toBe('학년과 고른 난이도에 맞춰 골랐어');
    expect(assignedByLine('친구1', say(true))).toBe('학년과 고른 난이도에 맞춰 골랐어요');
  });
});
