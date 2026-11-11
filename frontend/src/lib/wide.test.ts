// 학습지도자 넓은 화면: 폰 틀을 풀지 정하는 판단 로직 테스트
import { describe, expect, it } from 'vitest';
import { WIDE_QUERY, frameClass, isWideMatch } from './wide';

describe('frameClass — 학습지도자일 때만 frame--wide', () => {
  it('teacher면 wide 클래스를 붙인다', () => {
    expect(frameClass({ adult: true, role: 'teacher' })).toBe('frame frame--adult frame--wide');
  });
  it('아이·보호자·운영자·로그인 전에는 절대 붙지 않는다', () => {
    expect(frameClass({ role: 'student' })).toBe('frame');
    expect(frameClass({ adult: true, role: 'guardian' })).toBe('frame frame--adult');
    expect(frameClass({ adult: true, role: 'operator' })).toBe('frame frame--adult');
    expect(frameClass({ role: undefined })).toBe('frame');
  });
});

describe('isWideMatch — 넓은 화면은 학습지도자 + 1024px 이상', () => {
  const mm = (matches: boolean) => (q: string) => ({ matches: q === WIDE_QUERY && matches });
  it('학습지도자이고 창이 넓을 때만 true', () => {
    expect(isWideMatch('teacher', mm(true))).toBe(true);
    expect(isWideMatch('teacher', mm(false))).toBe(false);
    expect(isWideMatch('student', mm(true))).toBe(false);
    expect(isWideMatch(undefined, mm(true))).toBe(false);
  });
  it('matchMedia가 없는 환경(테스트·옛 브라우저)에서는 좁은 화면으로 본다', () => {
    expect(isWideMatch('teacher', undefined)).toBe(false);
  });
});
