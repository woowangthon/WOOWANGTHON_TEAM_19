// 4차(성호 11-14): 보호자·선생님 화면을 보이는 동안 5초마다 조용히 다시 읽기 — 언제 부를지
import { describe, expect, it } from 'vitest';
import { shouldPoll } from './quietPoll';

describe('조용히 다시 읽기', () => {
  it('보이고, 읽는 중이 아닐 때만', () => {
    expect(shouldPoll('visible', false)).toBe(true);
    expect(shouldPoll('hidden', false)).toBe(false);
    expect(shouldPoll('visible', true)).toBe(false);
  });
});
