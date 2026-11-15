import { describe, expect, it } from 'vitest';
import type { SafetyAlert } from '../types';
import { pickPopup } from './crisisPopup';

const A = (id: string, level: SafetyAlert['level'], status: SafetyAlert['status']): SafetyAlert =>
  ({ id, at: '11월 15일 · 01:00', level, category: '안전', action: '지금 아이와 직접 이야기해 주세요.', status });

describe('보호자 긴급 팝업', () => {
  it('긴급·미확인만 띄운다', () => {
    expect(pickPopup([A('a', '주의', '미확인'), A('b', '긴급', '확인함'), A('c', '긴급', '닫음')], new Set())).toBeNull();
    expect(pickPopup([A('a', '주의', '미확인'), A('d', '긴급', '미확인')], new Set())?.id).toBe('d');
  });
  it('한 번 띄운 알림은 다시 띄우지 않는다(닫아도 미확인 그대로)', () => {
    expect(pickPopup([A('d', '긴급', '미확인')], new Set(['d']))).toBeNull();
  });
  it('목록이 아직 없으면 띄우지 않는다', () => { expect(pickPopup(null, new Set())).toBeNull(); });
});
