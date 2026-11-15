// 공유 세션 맞추기(dev round2 #1·#2): 오늘 화면 sync · 수다가 0초로 열릴 때 다시 묻기 · 다시 읽기 실패 때 세션 지키기
import { describe, expect, it, vi } from 'vitest';
import { loadSession, refreshIfChatExpired, syncFromHome } from './sessionSync';
import type { SessionView } from '../types';

const s = (phase: SessionView['phase']) => ({ id: 's1', phase }) as SessionView;

describe('syncFromHome', () => {
  it('Today가 서버 세션(wrap)을 공유 세션에 sync', () => {
    const sync = vi.fn();
    syncFromHome({ session: s('wrap') }, sync);
    expect(sync).toHaveBeenCalledWith(s('wrap'));
  });
  it('서버가 세션 없음이면 null로 맞추고, 아직 못 불러왔으면 건드리지 않는다', () => {
    const sync = vi.fn();
    syncFromHome({ session: null }, sync);
    syncFromHome({}, sync);
    expect(sync.mock.calls).toEqual([[null], [null]]);
    syncFromHome(null, sync);
    expect(sync).toHaveBeenCalledTimes(2);
  });
});

describe('refreshIfChatExpired', () => {
  it('Chat이 remainingSec 0으로 열리면 refresh 호출', () => {
    const refresh = vi.fn();
    refreshIfChatExpired(0, refresh);
    expect(refresh).toHaveBeenCalledOnce();
  });
  it('시간이 남았거나 아직 못 불러왔으면 부르지 않는다', () => {
    const refresh = vi.fn();
    refreshIfChatExpired(120, refresh);
    refreshIfChatExpired(null, refresh);
    expect(refresh).not.toHaveBeenCalled();
  });
});

describe('loadSession', () => {
  it('refresh 실패 시 기존 세션 유지', async () => {
    const prev = s('chat');
    await expect(loadSession(() => Promise.reject(new Error('끊김')), prev, true)).resolves.toBe(prev);
  });
  it('clear/로그아웃 뒤에는 세션 null(실패해도 이전 세션을 남기지 않는다)', async () => {
    await expect(loadSession(() => Promise.reject(new Error('끊김')), s('chat'), false)).resolves.toBeNull();
  });
  it('성공하면 서버 값으로 바꾼다(세션 없음 null 포함)', async () => {
    await expect(loadSession(async () => s('wrap'), s('chat'), true)).resolves.toEqual(s('wrap'));
    await expect(loadSession(async () => null, s('chat'), true)).resolves.toBeNull();
  });
});
