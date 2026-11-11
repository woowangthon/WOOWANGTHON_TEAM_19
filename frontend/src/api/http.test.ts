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

type Call = { url: string; method: string; actor: string | null };
let calls: Call[];
let trials: number;
/** 서버 대역: /trial은 세트를 하나씩 새로 주고, 그 밖은 handler에 맡긴다 */
function server(handler: (c: Call) => Response | Promise<Response> = () => json(200, { ok: true }), trialRes?: () => Response) {
  calls = []; trials = 0;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const c = { url: String(url).replace(BASE, ''), method: init?.method ?? 'GET', actor: headers['X-Demo-Actor'] ?? null };
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
afterEach(() => { vi.unstubAllGlobals(); });

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
