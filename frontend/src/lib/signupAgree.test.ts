// 가입 동의(dev round2 #6): 학생에게는 소식 알림(marketing)을 묻지 않는다(R8) → 보호자에서 「전체 동의」 뒤 학생으로 바꿔도 false로 보낸다
import { describe, expect, it } from 'vitest';
import { signupAgreements } from './signupHint';

describe('signupAgreements', () => {
  const all = { terms: true, privacy: true, marketing: true };
  it('보호자에서 전체 동의 뒤 학생으로 바꿔 가입하면 marketing false로 전송', () => {
    expect(signupAgreements(all, true)).toEqual({ terms: true, privacy: true, marketing: false });
  });
  it('어른(보호자·학습지도자)은 고른 그대로', () => {
    expect(signupAgreements(all, false)).toEqual(all);
    expect(signupAgreements({ ...all, marketing: false }, false)).toEqual({ ...all, marketing: false });
  });
});
