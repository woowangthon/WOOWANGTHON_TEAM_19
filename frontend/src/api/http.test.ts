// 방문자별 체험 세트(명세 4.11 2): http.ts가 trial 세트를 받아 두고 X-Demo-Actor로 쓰는지 검사한다.
// fetch·localStorage는 가짜로 바꾼다. 모듈 안 상태(세트·역할)가 있어 테스트마다 모듈을 새로 읽는다.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const BASE = 'http://localhost:8000';
const trialBody = (n: number) => ({
  trialId: `t-set${n}`,
  actors: { child: `t-set${n}-child`, guardian: `t-set${n}-guardian`, instructor: `t-set${n}-instructor` },
  date: '2026-11-11',
});
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

/** 간단한 localStorage 대역. blocked면 모든 접근이 던진다(사생활 모드) */
function fakeStorage(blocked = false) {
  const m = new Map<string, string>();
  const guard = () => { if (blocked) throw new Error('blocked'); };
  return {
    map: m,
    getItem: (k: string) => { guard(); return m.get(k) ?? null; },
    setItem: (k: string, v: string) => { guard(); m.set(k, v); },
    removeItem: (k: string) => { guard(); m.delete(k); },
  };
}

type Call = { url: string; method: string; actor: string | null; headers: Record<string, string>; credentials?: RequestCredentials };
let calls: Call[];
let trials: number;
/** 서버 대역: /trial은 세트를 하나씩 새로 주고, 그 밖은 handler에 맡긴다 */
function server(handler: (c: Call) => Response | Promise<Response> = () => json(200, { ok: true }), trialRes?: () => Response) {
  calls = []; trials = 0;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const c: Call = { url: String(url).replace(BASE, ''), method: init?.method ?? 'GET', actor: headers['X-Demo-Actor'] ?? null, headers, credentials: init?.credentials };
    calls.push(c);
    if (c.url === '/trial') { if (trialRes) return trialRes(); trials++; return json(200, trialBody(trials)); }
    return handler(c);
  }));
}

async function load(storage = fakeStorage()) {
  vi.stubGlobal('localStorage', storage);
  vi.resetModules();
  return import('./http');
}

beforeEach(() => { server(); });
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe('체험 세트 받기', () => {
  it('세트가 없으면 처음 요청 전에 POST /trial로 한 번 받아 그 아이 id로 보낸다', async () => {
    const st = fakeStorage();
    const http = await load(st);
    http.setDemoRole('student');
    await http.httpApi.getStudentHome();
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(['POST /trial', 'GET /student/home']);
    expect(calls[1].actor).toBe('t-set1-child');
    expect(JSON.parse(st.map.get('ai-mentor-trial')!).trialId).toBe('t-set1');
  });

  it('동시에 여러 요청이 와도 세트는 한 번만 받는다', async () => {
    const http = await load();
    http.setDemoRole('student');
    await Promise.all([http.httpApi.getStudentHome(), http.httpApi.getRecords(), http.httpApi.getChat('s1')]);
    expect(trials).toBe(1);
    expect(calls.filter((c) => c.url !== '/trial').every((c) => c.actor === 't-set1-child')).toBe(true);
  });

  it('저장된 세트가 있으면 다시 받지 않고, 역할에 맞는 id를 쓴다', async () => {
    const st = fakeStorage();
    st.map.set('ai-mentor-trial', JSON.stringify(trialBody(7)));
    const http = await load(st);
    http.setDemoRole('guardian');
    await http.httpApi.getGuardianToday();
    http.setDemoRole('teacher');
    await http.httpApi.getTeacherToday();
    expect(trials).toBe(0);
    expect(calls.map((c) => c.actor)).toEqual(['t-set7-guardian', 't-set7-instructor']);
  });

  it('저장이 막혀도(사생활 모드) 메모리로 같은 세트를 계속 쓴다', async () => {
    const http = await load(fakeStorage(true));
    http.setDemoRole('student');
    await http.httpApi.getStudentHome();
    await http.httpApi.getStudentHome();
    expect(trials).toBe(1);
    expect(calls.filter((c) => c.url !== '/trial').map((c) => c.actor)).toEqual(['t-set1-child', 't-set1-child']);
  });

  it('429면 서버 문구를 그대로 오류로 낸다', async () => {
    server(undefined, () => json(429, { code: 'trial_limit', message: '잠시 뒤 다시 시도해 주세요.', detail: '잠시 뒤 다시 시도해 주세요.' }));
    const http = await load();
    http.setDemoRole('student');
    await expect(http.httpApi.getStudentHome()).rejects.toThrow('잠시 뒤 다시 시도해 주세요.');
  });
});

describe('세트가 서버에 없을 때(DB가 바뀜)', () => {
  it('404 student_not_found면 세트를 버리고 한 번만 새로 받아 다시 보낸다', async () => {
    server((c) => (c.actor === 't-set1-child' ? json(404, { code: 'student_not_found', message: '학생을 찾을 수 없어요.', detail: '학생을 찾을 수 없어요.' }) : json(200, { ok: 1 })));
    const st = fakeStorage();
    const http = await load(st);
    http.setDemoRole('student');
    await expect(http.httpApi.getStudentHome()).resolves.toEqual({ ok: 1 });
    expect(calls.map((c) => `${c.url} ${c.actor ?? ''}`.trim())).toEqual(['/trial', '/student/home t-set1-child', '/trial', '/student/home t-set2-child']);
    expect(JSON.parse(st.map.get('ai-mentor-trial')!).trialId).toBe('t-set2');
  });

  it('보호자 guardian_not_found도 같다. 동시에 여러 개가 404여도 새 세트는 한 번', async () => {
    server((c) => (c.actor === 't-set1-guardian' ? json(404, { code: 'guardian_not_found', message: '보호자를 찾을 수 없어요.' }) : json(200, { ok: 1 })));
    const http = await load();
    http.setDemoRole('guardian');
    await Promise.all([http.httpApi.getGuardianToday(), http.httpApi.getAlerts()]);
    expect(trials).toBe(2);
  });

  it('새 세트로도 404면 더 받지 않고 오류를 낸다', async () => {
    server(() => json(404, { code: 'student_not_found', message: '학생을 찾을 수 없어요.' }));
    const http = await load();
    http.setDemoRole('student');
    await expect(http.httpApi.getStudentHome()).rejects.toThrow('학생을 찾을 수 없어요.');
    expect(trials).toBe(2);
  });

  it('학습지도자의 student_not_found(주소 속 학생)는 세트를 바꾸지 않는다', async () => {
    server(() => json(404, { code: 'student_not_found', message: '학생을 찾을 수 없어요.' }));
    const http = await load();
    http.setDemoRole('teacher');
    await expect(http.httpApi.getMemo('x')).rejects.toThrow('학생을 찾을 수 없어요.');
    expect(trials).toBe(1);
  });

  it('학습지도자는 trial_not_found(세트 아이가 없음)면 새 세트를 받아 다시 보낸다', async () => {
    server((c) => (c.actor === 't-set1-instructor' ? json(404, { code: 'trial_not_found', message: '체험이 끝났어요.' }) : json(200, { ok: 1 })));
    const http = await load();
    http.setDemoRole('teacher');
    await expect(http.httpApi.getTeacherToday()).resolves.toEqual({ ok: 1 });
    expect(trials).toBe(2);
  });
});

describe('처음부터 다시 체험 = 새 세트', () => {
  it('공용 /demo/restart를 부르지 않고 새 세트를 받아 저장한다(로그인 전에도)', async () => {
    const st = fakeStorage();
    st.map.set('ai-mentor-trial', JSON.stringify(trialBody(9)));
    const http = await load(st);
    await http.startNewTrial();
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(['POST /trial']);
    expect(JSON.parse(st.map.get('ai-mentor-trial')!).trialId).toBe('t-set1');
    http.setDemoRole('student');
    await http.httpApi.getStudentHome();
    expect(calls[1].actor).toBe('t-set1-child');
  });
});

describe('org http 모드(VITE_API_MODE=http + VITE_ORG_MODE=http, 명세 4.12)', () => {
  const orgEnv = () => { vi.stubEnv('VITE_API_MODE', 'http'); vi.stubEnv('VITE_ORG_MODE', 'http'); };
  const notLoggedIn = () => json(401, { code: 'not_logged_in', message: '로그인이 필요해요.', detail: '로그인이 필요해요.' });

  it('쿠키(credentials include)와 X-Trial-Id만 보내고 X-Demo-*는 보내지 않는다', async () => {
    orgEnv();
    const http = await load();
    expect(http.ORG_HTTP).toBe(true);
    http.setDemoRole('student');
    await http.httpApi.getSeedBoard();
    const c = calls[1];
    expect(c.url).toBe('/teacher/seeds');
    expect(c.credentials).toBe('include');
    expect(c.headers['X-Trial-Id']).toBe('t-set1');
    expect(Object.keys(c.headers).filter((k) => k.startsWith('X-Demo'))).toEqual([]);
  });

  it('로그인 전에도(역할 없음) 로그인·가입·체험 계정 요청을 보낸다', async () => {
    orgEnv();
    const http = await load();
    await http.httpApi.demoAccounts();
    await http.httpApi.login('jiwoo_k7p2', 'demo1234', true);
    await http.httpApi.checkLoginId('newkid');
    await http.httpApi.getMe();
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(['POST /trial', 'GET /demo/accounts', 'POST /auth/login', 'GET /auth/check-id?loginId=newkid', 'GET /me']);
    expect(calls.slice(1).every((c) => c.headers['X-Trial-Id'] === 't-set1' && c.credentials === 'include')).toBe(true);
  });

  it('401 not_logged_in·no_actor면 로그아웃 처리를 부르고 오류를 낸다', async () => {
    orgEnv();
    server((c) => (c.url === '/me' ? json(401, { code: 'no_actor', message: '누구인지 알 수 없어요.' }) : notLoggedIn()));
    const http = await load();
    const out = vi.fn();
    http.setLoggedOutHandler(out);
    http.setDemoRole('student');
    await expect(http.httpApi.getWallet()).rejects.toThrow('로그인이 필요해요.');
    await expect(http.httpApi.getMe()).rejects.toThrow();
    expect(out).toHaveBeenCalledTimes(2);
    expect(trials).toBe(1);
  });

  it('다른 401(비밀번호 틀림 등)은 로그아웃 처리를 하지 않는다', async () => {
    orgEnv();
    server(() => json(401, { code: 'bad_credentials', message: '아이디 또는 비밀번호가 맞지 않아요.' }));
    const http = await load();
    const out = vi.fn();
    http.setLoggedOutHandler(out);
    await expect(http.httpApi.login('x', 'y', true)).rejects.toThrow('아이디 또는 비밀번호가 맞지 않아요.');
    expect(out).not.toHaveBeenCalled();
  });

  it('404 not_linked는 세트를 새로 받지 않고 그대로 오류', async () => {
    orgEnv();
    server(() => json(404, { code: 'not_linked', message: '아직 아이와 연결되지 않았어요.' }));
    const http = await load();
    const out = vi.fn();
    http.setLoggedOutHandler(out);
    http.setDemoRole('guardian');
    await expect(http.httpApi.getGuardianToday()).rejects.toThrow('아직 아이와 연결되지 않았어요.');
    expect(trials).toBe(1);
    expect(out).not.toHaveBeenCalled();
  });

  it('404 trial_not_found면 새 세트로 한 번 다시 보낸다', async () => {
    orgEnv();
    server((c) => (c.headers['X-Trial-Id'] === 't-set1' ? json(404, { code: 'trial_not_found', message: '체험이 끝났어요.' }) : json(200, { ok: 1 })));
    const http = await load();
    await expect(http.httpApi.demoAccounts()).resolves.toEqual({ ok: 1 });
    expect(trials).toBe(2);
  });

  it('처음부터 다시 체험: 옛 세트로 POST /auth/logout(쿠키 포함) 뒤 새 세트, 로그아웃이 실패해도 계속', async () => {
    orgEnv();
    const st = fakeStorage();
    st.map.set('ai-mentor-trial', JSON.stringify(trialBody(9)));
    server(() => json(500, { message: '서버 오류' }));
    const http = await load(st);
    await http.startNewTrial();
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(['POST /auth/logout', 'POST /trial']);
    expect(calls[0].headers['X-Trial-Id']).toBe('t-set9');
    expect(calls[0].credentials).toBe('include');
    expect(JSON.parse(st.map.get('ai-mentor-trial')!).trialId).toBe('t-set1');
  });

  it('VITE_ORG_MODE가 없으면(기본 mock) 지금처럼 역할 없이는 보내지 않고 X-Demo-*를 쓴다', async () => {
    vi.stubEnv('VITE_API_MODE', 'http');
    const http = await load();
    expect(http.ORG_HTTP).toBe(false);
    await expect(http.httpApi.demoAccounts()).rejects.toThrow('로그인이 필요해요.');
    http.setDemoRole('student');
    await http.httpApi.getStudentHome();
    expect(calls[1].headers['X-Demo-Role']).toBe('child');
    expect(calls[1].headers['X-Trial-Id']).toBeUndefined();
    expect(calls[1].credentials).toBeUndefined();
  });
});

describe('답 보내기(분수 칸 / 그 밖의 답 칸)', () => {
  const bodies = async (send: (h: Awaited<ReturnType<typeof load>>['httpApi']) => Promise<unknown>) => {
    const sent: unknown[] = [];
    const http = await load();
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).endsWith('/answer')) sent.push(JSON.parse(String(init?.body)));
      return String(url).endsWith('/trial') ? json(200, trialBody(1)) : json(200, { correct: true });
    }));
    http.setDemoRole('student');
    await send(http.httpApi);
    return sent;
  };

  it('분수 칸은 지금처럼 numerator·denominator만 보낸다', async () => {
    expect(await bodies((h) => h.submitAnswer('s1', 'p1', 3, 8))).toEqual([{ problemId: 'p1', numerator: 3, denominator: 8 }]);
  });

  it('숫자 한 칸·보기·낱말은 answer 글자로 보낸다', async () => {
    expect(await bodies((h) => h.submitAnswer('s1', 'p1', 0, 0, '②'))).toEqual([{ problemId: 'p1', answer: '②' }]);
  });
});
