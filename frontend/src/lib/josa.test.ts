import { describe, expect, it } from 'vitest';
import { callName } from './josa';

describe('부르는 말(아/야)', () => {
  it('받침이 없으면 「야」', () => {
    expect(callName('지우')).toBe('지우야');
    expect(callName('하리')).toBe('하리야');
  });
  it('받침이 있으면 「아」', () => {
    expect(callName('새봄')).toBe('새봄아');
    expect(callName('민준')).toBe('민준아');
  });
  it('한글로 끝나지 않으면 조사를 붙이지 않는다', () => {
    expect(callName('Alex')).toBe('Alex');
    expect(callName('하늘3')).toBe('하늘3');
  });
  it('앞뒤 공백은 지운다', () => {
    expect(callName(' 새봄 ')).toBe('새봄아');
  });
});

describe('josa', () => {
  it('받침에 맞는 조사', async () => {
    const { josa } = await import('./josa');
    expect(josa('지우', '이', '가')).toBe('지우가');
    expect(josa('새봄', '은', '는')).toBe('새봄은');
    expect(josa('Jay', '이', '가')).toBe('Jay이(가)');
  });
});
