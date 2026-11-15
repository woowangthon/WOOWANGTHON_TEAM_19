import { describe, expect, it } from 'vitest';
import { crisisLine } from './crisisLine';

describe('위기 화면 서버 문장', () => {
  it('마지막 멘토 말을 그대로', () => {
    expect(crisisLine([{ from: 'mentor', text: '앞 말' }, { from: 'me', text: 'x' }, { from: 'mentor', text: '서버 문장' }])).toBe('서버 문장');
  });
  it('없으면 null(문장 없이 지금 화면)', () => {
    expect(crisisLine([])).toBeNull(); expect(crisisLine(null)).toBeNull(); expect(crisisLine([{ from: 'me', text: 'x' }])).toBeNull();
  });
});
