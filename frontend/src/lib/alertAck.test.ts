import { describe, expect, it } from 'vitest';
import type { SafetyAlert } from '../types';
import { applyAck, needsAckCount, topAlerts } from './alertAck';

const A = (id: string, level: SafetyAlert['level'], status: SafetyAlert['status']): SafetyAlert =>
  ({ id, at: '11-15 00:10', level, category: '안전', action: '지금 아이와 직접 이야기해 주세요.', status });

describe('보호자 알림 확인', () => {
  const list = [A('a1', '긴급', '미확인'), A('a2', '주의', '확인함'), A('a3', '긴급', '닫음')];
  it('미확인만 「확인이 필요한 알림」으로 센다', () => { expect(needsAckCount(list)).toBe(1); });
  it('확인한 긴급 카드는 위에 남고 수에서는 빠진다', () => {
    const after = applyAck(list, { ...list[0], status: '확인함', ackedAt: '11-15 00:12' });
    expect(topAlerts(after).map((a) => a.id)).toEqual(['a1']);
    expect(topAlerts(after)[0]).toMatchObject({ status: '확인함', ackedAt: '11-15 00:12' });
    expect(needsAckCount(after)).toBe(0);
  });
  it('다른 알림은 그대로', () => {
    const after = applyAck(list, { ...list[0], status: '확인함', ackedAt: 'x' });
    expect(after[1]).toBe(list[1]); expect(after[2]).toBe(list[2]);
  });
});
