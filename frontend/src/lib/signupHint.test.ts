// 가입 정보 입력 — 「가입하기」가 왜 막혔는지 한 줄(R3)
import { describe, expect, it } from 'vitest';
import { looksLikePhone, signupMissing } from './signupHint';

const ok = { loginId: 'haneul01', idOk: true as boolean | null, pwOk: true, same: true, name: '하늘', kid: true, grade: 5 as number | null, emailOk: false };

describe('signupMissing — 위에서부터 첫 번째로 빠진 것 하나', () => {
  it('다 채우면 null', () => {
    expect(signupMissing(ok)).toBeNull();
    expect(signupMissing({ ...ok, kid: false, grade: null, emailOk: true })).toBeNull();
  });
  it('중복 확인을 안 눌렀으면 그것부터 알려 준다(아이가 가장 많이 막히는 곳)', () => {
    expect(signupMissing({ ...ok, idOk: null })).toBe('아이디 옆 「중복 확인」을 눌러 주세요');
    expect(signupMissing({ ...ok, idOk: false })).toBe('이미 있는 아이디예요. 다른 아이디로 바꿔 주세요');
  });
  it('순서: 아이디 → 비밀번호 → 확인 → 별명 → 학년/이메일', () => {
    expect(signupMissing({ ...ok, loginId: '', idOk: null })).toBe('아이디를 넣어 주세요');
    expect(signupMissing({ ...ok, pwOk: false, same: false })).toBe('비밀번호는 영문과 숫자를 섞어 8~20자로 해 주세요');
    expect(signupMissing({ ...ok, same: false })).toBe('비밀번호 확인이 위와 같아야 해요');
    expect(signupMissing({ ...ok, name: ' ' })).toBe('별명을 넣어 주세요');
    expect(signupMissing({ ...ok, kid: false, name: '' })).toBe('이름을 넣어 주세요');
    expect(signupMissing({ ...ok, grade: null })).toBe('학년을 골라 주세요');
    expect(signupMissing({ ...ok, kid: false, grade: null, emailOk: false })).toBe('이메일 주소를 확인해 주세요');
  });
});

describe('별명에 전화번호(R1)', () => {
  const base = { loginId: 'haneul1', idOk: true, pwOk: true, same: true, kid: true, grade: 5, emailOk: false };
  it('숫자가 4개 넘게 이어지면(띄어쓰기·하이픈 무시) 막는다', () => {
    expect(looksLikePhone('하늘 010-1234')).toBe(true);
    expect(looksLikePhone('별똥별2026')).toBe(true);
    expect(looksLikePhone('하늘3')).toBe(false);
    expect(signupMissing({ ...base, name: '김하늘 010-1234' })).toBe('별명에 전화번호는 넣지 말아 줘');
    expect(signupMissing({ ...base, name: '하늘' })).toBeNull();
  });
  it('어른 이름 칸은 검사하지 않는다', () => {
    expect(signupMissing({ ...base, kid: false, emailOk: true, name: '김선생님1234' })).toBeNull();
  });
});
