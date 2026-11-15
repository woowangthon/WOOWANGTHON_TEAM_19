// dev round2 #15·#16·#18 — 로그인 세대(바뀐 뒤 늦게 온 401은 무시) · 새 체험 세트를 먼저 받기 · 500·없는 경로 문구는 D11로
// fetch·localStorage는 가짜로 바꾼다(http.test.ts와 같은 방식). 모듈 안 상태가 있어 테스트마다 모듈을 새로 읽는다.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { serverErrorText } from '../lib/serverError';

const BASE = 'http://localhost:8000';
const trialBody = (n: number) => ({
  trialId: `t-set${n}`,
  actors: { child: `t-set${n}-child`, guardian: `t-set${n}-guardian`, instructor: `t-set${n}-instructor` },
  date: '2026-11-14',
});
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
function fakeStorage() {
  const m = new Map<string, string>();
  return { map: m, getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => { m.set(k, v); }, removeItem: (k: string) => { m.delete(k); } };
}
type Call = { url: string; method: string; trialId: string | undefined };
let calls: Call[];
function server(handler: (c: Call) => Response | Promise<Response>, trialRes?: () => Response) {
  calls = [];
  let n = 0;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const c: Call = { url: String(url).replace(BASE, ''), method: init?.method ?? 'GET', trialId: headers['X-Trial-Id'] };
    calls.push(c);
    if (c.url === '/trial') return trialRes ? trialRes() : json(200, trialBody(++n));
    return handler(c);
  }));
}
async function load(storage = fakeStorage(), org = true) {
  if (org) { vi.stubEnv('VITE_API_MODE', 'http'); vi.stubEnv('VITE_ORG_MODE', 'http'); }
  vi.stubGlobal('localStorage', storage);
  vi.resetModules();
  return import('./http');
}
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
const notLoggedIn = () => json(401, { code: 'not_logged_in', message: '로그인이 필요해요.' });

describe('#15 로그인 세대', () => {
  it('요청 중 로그인 세대가 바뀌면 401이 와도 onLoggedOut 안 부름', async () => {
    let answer!: (r: Response) => void;
    server((c) => (c.url === '/class-live' ? new Promise<Response>((ok) => { answer = ok; }) : json(200, {})));
    const http = await load();
    const out = vi.fn();
    http.setLoggedOutHandler(out);
    http.setDemoRole('student');
    const req = http.classLiveCall('GET', '/class-live');
    await vi.waitFor(() => expect(answer).toBeTypeOf('function'));
    http.setDemoRole('student'); // 그사이 다시 로그인(enter) — 같은 역할이어도 세대는 바뀐다
    answer(notLoggedIn());
    await expect(req).rejects.toThrow('로그인이 필요해요.');
    expect(out).not.toHaveBeenCalled();
  });
  it('처음부터 다시 체험(새 세트로 바꿈) 중이던 요청의 401도 무시한다', async () => {
    let answer!: (r: Response) => void;
    server((c) => (c.url === '/class-live' ? new Promise<Response>((ok) => { answer = ok; }) : json(200, {})));
    const st = fakeStorage();
    st.map.set('ai-mentor-trial', JSON.stringify(trialBody(9)));
    const http = await load(st);
    const out = vi.fn();
    http.setLoggedOutHandler(out);
    http.setDemoRole('student');
    const req = http.classLiveCall('GET', '/class-live');
    await vi.waitFor(() => expect(answer).toBeTypeOf('function'));
    await http.startNewTrial();
    answer(notLoggedIn());
    await expect(req).rejects.toThrow();
    expect(out).not.toHaveBeenCalled();
  });
  it('세대가 같으면 지금처럼 부름', async () => {
    server(() => notLoggedIn());
    const http = await load();
    const out = vi.fn();
    http.setLoggedOutHandler(out);
    http.setDemoRole('student');
    await expect(http.classLiveCall('GET', '/class-live')).rejects.toThrow();
    expect(out).toHaveBeenCalledOnce();
  });
});

describe('#16 처음부터 다시 체험: 새 세트를 먼저 받는다', () => {
  it('POST /trial 실패 시 옛 로그인·세트 유지(로그아웃도 하지 않음)', async () => {
    server(() => json(200, { ok: 1 }), () => json(429, { code: 'trial_limit', message: '잠시 뒤 다시 시도해 주세요.' }));
    const st = fakeStorage();
    st.map.set('ai-mentor-trial', JSON.stringify(trialBody(9)));
    const http = await load(st);
    await expect(http.startNewTrial()).rejects.toThrow('잠시 뒤 다시 시도해 주세요.');
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(['POST /trial']);
    expect(JSON.parse(st.map.get('ai-mentor-trial')!).trialId).toBe('t-set9');
    await http.httpApi.getMe();
    expect(calls.at(-1)!.trialId).toBe('t-set9');
  });
  it('성공 시 새 세트로 교체(옛 세트 쿠키는 그 뒤에 로그아웃)', async () => {
    server(() => json(200, { ok: 1 }));
    const st = fakeStorage();
    st.map.set('ai-mentor-trial', JSON.stringify(trialBody(9)));
    const http = await load(st);
    await http.startNewTrial();
    expect(calls.map((c) => `${c.method} ${c.url} ${c.trialId ?? ''}`.trim())).toEqual(['POST /trial', 'POST /auth/logout t-set9']);
    expect(JSON.parse(st.map.get('ai-mentor-trial')!).trialId).toBe('t-set1');
    await http.httpApi.getMe();
    expect(calls.at(-1)!.trialId).toBe('t-set1');
  });
});

describe('#18 서버 오류 문구', () => {
  it('500 internal_error → D11 문구', async () => {
    server(() => json(500, { code: 'internal_error', message: '잠깐 문제가 생겼어요.' }));
    const http = await load();
    http.setDemoRole('student');
    await expect(http.httpApi.getStudentHome()).rejects.toThrow(serverErrorText(500, true));
  });
  it('404 http_error → D11 문구(영어 없음)', async () => {
    server(() => json(404, { code: 'http_error', message: 'Not Found', detail: 'Not Found' }));
    const http = await load();
    http.setDemoRole('guardian');
    const e = await http.httpApi.getGuardianToday().catch((x: Error) => x);
    expect((e as Error).message).toBe(serverErrorText(404, false));
    expect((e as Error).message).not.toMatch(/[A-Za-z]{3,}/);
  });
  it('409 등 업무 오류는 서버 message 그대로', async () => {
    server(() => json(409, { code: 'already_done', message: '이미 처리한 코멘트예요.' }));
    const http = await load();
    http.setDemoRole('teacher');
    await expect(http.httpApi.approveDraft('s1')).rejects.toThrow('이미 처리한 코멘트예요.');
  });
});
