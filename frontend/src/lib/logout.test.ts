// 로그아웃(dev round2 #14, 보안 검토 반영 11-14): 서버 로그아웃이 실패하면 이 기기 로그인도 지우지 않고 오류를 알린다.
// 로그인 쿠키는 서버만 지울 수 있어서, 화면만 지우면 앱을 다시 열 때 그대로 로그인돼 버린다(같은 폰을 보호자·아이가 바꿔 쓸 때 위험).
// 이미 로그아웃된 경우(401 not_logged_in)는 http.ts의 onLoggedOut이 로컬을 지운다.
import { describe, expect, it, vi } from 'vitest';
import { LOGOUT_FAILED, logoutThenClear } from './logout';

describe('logoutThenClear', () => {
  it('서버 로그아웃이 실패하면 로컬을 지우지 않고 오류를 던진다', async () => {
    const clear = vi.fn(async () => {});
    await expect(logoutThenClear(() => Promise.reject(new Error('서버에 연결하지 못했어요.')), clear)).rejects.toThrow(LOGOUT_FAILED);
    expect(clear).not.toHaveBeenCalled();
  });
  it('성공하면 서버 → 로컬 순서로', async () => {
    const order: string[] = [];
    await logoutThenClear(async () => { order.push('server'); }, async () => { order.push('clear'); });
    expect(order).toEqual(['server', 'clear']);
  });
});
