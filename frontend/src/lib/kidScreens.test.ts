// 아이 화면 판정 함수 테스트 — 위기로 끝난 날 · 데모 아이 · 처음부터 다시 · 시간 끝 · 세션 없음
import { describe, expect, it, vi } from 'vitest';
import { isCrisisDay, isDemoChild, isSessionGone, isSolveTimeUp, restartDemo } from './kidScreens';
import type { Me, SessionView } from '../types';

const session = (phase: SessionView['phase']) => ({ phase }) as SessionView;
const me = (role: Me['role'], loginId: string) => ({ role, loginId }) as Me;

describe('isCrisisDay', () => {
  it('서버 endedInCrisis를 먼저 본다', () => {
    expect(isCrisisDay({ endedInCrisis: true, session: null })).toBe(true);
    expect(isCrisisDay({ endedInCrisis: false, session: session('crisis') })).toBe(false);
  });
  it('필드가 없으면 세션 단계 crisis로 대신 판정한다', () => {
    expect(isCrisisDay({ session: session('crisis') })).toBe(true);
    expect(isCrisisDay({ session: session('done') })).toBe(false);
    expect(isCrisisDay({ session: null })).toBe(false);
  });
});

describe('isDemoChild', () => {
  it('데모 아이 계정(jiwoo)일 때만 true', () => {
    expect(isDemoChild(me('student', 'jiwoo'))).toBe(true);
    expect(isDemoChild(me('student', 'minjun'))).toBe(false);
    expect(isDemoChild(me('guardian', 'jiwoo'))).toBe(false);
    expect(isDemoChild(null)).toBe(false);
  });
});

describe('restartDemo', () => {
  it('http 모드는 서버를 먼저 되돌리고 그다음 mock', async () => {
    const order: string[] = [];
    await restartDemo('http', async () => { order.push('server'); }, async () => { order.push('mock'); });
    expect(order).toEqual(['server', 'mock']);
  });
  it('mock 모드는 mock만 되돌린다', async () => {
    const server = vi.fn(async () => {});
    const mock = vi.fn(async () => {});
    await restartDemo('mock', server, mock);
    expect(server).not.toHaveBeenCalled();
    expect(mock).toHaveBeenCalledOnce();
  });
  it('서버가 실패하면 mock은 건드리지 않고 오류를 넘긴다', async () => {
    const mock = vi.fn(async () => {});
    await expect(restartDemo('http', async () => { throw new Error('서버 오류'); }, mock)).rejects.toThrow('서버 오류');
    expect(mock).not.toHaveBeenCalled();
  });
});

describe('isSolveTimeUp', () => {
  it('문제가 있고 남은 시간이 0이면 true', () => {
    expect(isSolveTimeUp(0, true, false)).toBe(true);
  });
  it('시간이 남았거나 문제를 아직 못 불렀거나 이미 끝낸 문제면 false', () => {
    expect(isSolveTimeUp(30, true, false)).toBe(false);
    expect(isSolveTimeUp(0, false, false)).toBe(false);
    expect(isSolveTimeUp(0, true, true)).toBe(false);
  });
});

describe('isSessionGone', () => {
  it('서버·mock의 「세션 없음」 문구를 알아본다', () => {
    expect(isSessionGone('세션을 찾을 수 없어요.')).toBe(true);
    expect(isSessionGone('오늘 세션을 찾지 못했어요. 처음 화면에서 다시 시작해 주세요.')).toBe(true);
    expect(isSessionGone('서버 오류가 났어요 (500)')).toBe(false);
    expect(isSessionGone(null)).toBe(false);
  });
});
