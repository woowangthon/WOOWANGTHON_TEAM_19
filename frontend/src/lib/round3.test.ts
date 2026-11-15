// dev round3(성호 11-14): #17 오류 종류·#9 보내는 중 값·#23 시트 포커스·#5 약속 먼저
import { describe, expect, it } from 'vitest';
import { ApiError, isTransient, needsPromise } from './apiError';
import { PendingDefaults } from './pendingDefaults';
import { nextFocusIndex } from './focusTrap';

describe('#17 오류 종류', () => {
  it('네트워크(0)·5xx는 잠깐 끊김 → 로그아웃하지 않음', () => {
    expect(isTransient(new ApiError('x', 0))).toBe(true);
    expect(isTransient(new ApiError('x', 503))).toBe(true);
  });
  it('401·403·404·일반 오류는 잠깐 끊김 아님', () => {
    for (const s of [401, 403, 404, 409, 422]) expect(isTransient(new ApiError('x', s)), String(s)).toBe(false);
    expect(isTransient(new Error('x'))).toBe(false);
  });
});

describe('#5 약속 먼저', () => {
  it('409 needs_promise만', () => {
    expect(needsPromise(new ApiError('약속부터 해 줘.', 409, 'needs_promise'))).toBe(true);
    expect(needsPromise(new ApiError('x', 409, 'already_started'))).toBe(false);
    expect(needsPromise(new Error('x'))).toBe(false);
  });
});

describe('#9 원장 기본값 보내는 중 값', () => {
  const base = { classMin: 50, breakMin: 10, games: true, notifyGuardian: true, showPlace: true };
  it('연달아 바꾸면 두 번째 본문에 첫 번째 값이 들어 있다', () => {
    const p = new PendingDefaults<typeof base>();
    const a = p.patch(base, { games: false });
    const b2 = p.patch(base, { classMin: 60 });       // 서버 값(base)은 아직 옛 값
    expect(a.body.games).toBe(false);
    expect(b2.body).toEqual({ ...base, games: false, classMin: 60 });
    expect(p.view(base)).toEqual(b2.body);              // 화면은 보내는 중 값을 바로
  });
  it('마지막으로 보낸 요청의 응답만 pending을 비운다(순서가 뒤바뀌어도)', () => {
    const p = new PendingDefaults<typeof base>();
    const a = p.patch(base, { games: false }); const b2 = p.patch(base, { classMin: 60 });
    p.settle(b2.seq); expect(p.view(base)).toEqual(base);   // 마지막 응답 → 비움(이제 서버 값을 따름)
    const q = new PendingDefaults<typeof base>();
    const c = q.patch(base, { games: false }); const d = q.patch(base, { classMin: 60 });
    q.settle(c.seq); expect(q.view(base).classMin).toBe(60); // 앞 요청 응답이 늦게 와도 아직 비우지 않음
    q.settle(d.seq); expect(q.view(base)).toEqual(base);
    void a;
  });
  it('실패하면 서버 값으로 되돌린다', () => {
    const p = new PendingDefaults<typeof base>();
    const a = p.patch(base, { games: false }); p.fail(a.seq);
    expect(p.view(base)).toEqual(base);
  });
});

describe('#23 시트 포커스 돌기', () => {
  it('끝에서 Tab → 처음, 처음에서 Shift+Tab → 끝, 하나도 없으면 -1', () => {
    expect(nextFocusIndex(3, 2, false)).toBe(0);
    expect(nextFocusIndex(3, 0, true)).toBe(2);
    expect(nextFocusIndex(3, 1, false)).toBe(2);
    expect(nextFocusIndex(3, -1, false)).toBe(0);  // 시트 밖에 있던 포커스 → 처음
    expect(nextFocusIndex(0, -1, false)).toBe(-1);
  });
});
