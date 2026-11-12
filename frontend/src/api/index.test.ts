// 빌드 플래그별로 어떤 함수가 진짜 서버(httpApi)로 가는지 검사한다. org 함수는 VITE_API_MODE·VITE_ORG_MODE가 둘 다 http일 때만.
import { afterEach, describe, expect, it, vi } from 'vitest';

async function load() {
  vi.resetModules();
  const [idx, http, mock, org] = await Promise.all([import('./index'), import('./http'), import('./mock'), import('./org')]);
  return { idx, http, mock, org };
}
afterEach(() => { vi.unstubAllEnvs(); });

const LEARNING_ORG = ['getRecords', 'getUnits', 'saveUnits', 'getResults'] as const;
const STAY = ['ackAlert', 'closeAlert', 'resetDemo'] as const;

describe('api 고르기', () => {
  it('둘 다 http면 orgApi 전부 + 학습 4개가 httpApi, ackAlert·closeAlert·resetDemo는 mock', async () => {
    vi.stubEnv('VITE_API_MODE', 'http'); vi.stubEnv('VITE_ORG_MODE', 'http');
    const { idx, http, mock, org } = await load();
    expect(idx.ORG_MODE).toBe('http');
    for (const k of [...Object.keys(org.orgApi), ...LEARNING_ORG] as (keyof typeof http.httpApi)[]) expect(idx.api[k], k).toBe(http.httpApi[k]);
    for (const k of STAY) expect(idx.api[k], k).toBe(mock.mockApi[k]);
    expect(idx.api.getStudentHome).toBe(http.httpApi.getStudentHome);
  });

  it('API만 http면 지금처럼 org·학습 4개는 mock', async () => {
    vi.stubEnv('VITE_API_MODE', 'http');
    const { idx, http, mock, org } = await load();
    expect(idx.ORG_MODE).toBe('mock');
    for (const k of [...Object.keys(org.orgApi), ...LEARNING_ORG, ...STAY] as (keyof typeof mock.mockApi)[]) expect(idx.api[k], k).toBe(mock.mockApi[k]);
    expect(idx.api.getStudentHome).toBe(http.httpApi.getStudentHome);
  });

  it('ORG만 http여도 API가 mock이면 전부 mock', async () => {
    vi.stubEnv('VITE_API_MODE', 'mock'); vi.stubEnv('VITE_ORG_MODE', 'http');
    const { idx, mock } = await load();
    expect(idx.ORG_MODE).toBe('mock');
    expect(idx.api).toBe(mock.mockApi);
  });
});
