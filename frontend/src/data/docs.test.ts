// 개인정보 처리방침·공지 문구가 결정(11-11 🔴 발췌)·실제 배포(시연 서버)와 맞는지(dev round2 #19)
import { describe, expect, it } from 'vitest';
import { DOCS } from './docs';

const text = (k: keyof typeof DOCS) => DOCS[k].body.flatMap((s) => [s.h, ...s.p]).join('\n');

describe('처리방침·공지', () => {
  it("처리방침에 '원문 없이 분류·긴급도만' 없음 — 🔴이어도 아이가 한 말은 보내지 않는다고 적는다(v0.8, 성호 11-15)", () => {
    const t = text('privacy');
    expect(t).not.toContain('원문 없이 분류·긴급도만');
    expect(t).toContain('평소 수다는 보내지 않습니다');
    expect(t).toContain('아이가 한 말은 보내지 않습니다');
    expect(t).not.toContain('앞뒤 일부');
  });
  it("'이 기기에만 저장' 없음", () => {
    for (const k of Object.keys(DOCS) as (keyof typeof DOCS)[]) expect(text(k)).not.toContain('이 기기에만 저장');
    expect(text('notice')).toContain('시연 서버에 저장되며');
  });
});
