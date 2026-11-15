// 첫 접속 지연(서버가 잠에서 깨는 중) 판정 테스트. 시간은 가짜 타이머로 돌린다.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AWAKE_MS, SLOW_MS, createSlowWatch } from './slowServer';

function deferred() {
  let resolve!: () => void;
  let reject!: (e: Error) => void;
  const p = new Promise<void>((res, rej) => { resolve = res; reject = rej; });
  return { p, resolve, reject };
}

describe('createSlowWatch — 깨어 있는지 모를 때 5초 넘는 요청이면 안내', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('첫 요청이 5초를 넘으면 slow, 응답이 오면 꺼진다', async () => {
    const w = createSlowWatch();
    const seen: boolean[] = [];
    w.subscribe(() => seen.push(w.isSlow()));
    const d = deferred();
    const tracked = w.track(d.p);
    vi.advanceTimersByTime(SLOW_MS - 1);
    expect(w.isSlow()).toBe(false);
    vi.advanceTimersByTime(1);
    expect(w.isSlow()).toBe(true);
    d.resolve();
    await tracked;
    expect(w.isSlow()).toBe(false);
    expect(seen).toEqual([true, false]);
  });

  it('5초 안에 끝나면 안내하지 않는다', async () => {
    const w = createSlowWatch();
    const d = deferred();
    const tracked = w.track(d.p);
    vi.advanceTimersByTime(SLOW_MS - 100);
    d.resolve();
    await tracked;
    vi.advanceTimersByTime(SLOW_MS);
    expect(w.isSlow()).toBe(false);
  });

  it('방금 서버가 답했으면 긴 요청(LLM 답 기다리기)은 깨우는 중이 아니다', async () => {
    const w = createSlowWatch();
    const first = deferred();
    const t1 = w.track(first.p);
    first.resolve();
    await t1;
    const llm = deferred();
    void w.track(llm.p);
    vi.advanceTimersByTime(SLOW_MS * 4);
    expect(w.isSlow()).toBe(false);
  });

  it('오래 쉬었으면(서버가 다시 잠들었을 수 있음) 다시 안내한다', async () => {
    const w = createSlowWatch();
    const first = deferred();
    const t1 = w.track(first.p);
    first.resolve();
    await t1;
    vi.advanceTimersByTime(AWAKE_MS + 1);
    const later = deferred();
    void w.track(later.p);
    vi.advanceTimersByTime(SLOW_MS);
    expect(w.isSlow()).toBe(true);
  });

  it('실패해도 안내는 꺼지고 「깨어 있음」으로 치지 않는다', async () => {
    const w = createSlowWatch();
    const d = deferred();
    const tracked = w.track(d.p);
    vi.advanceTimersByTime(SLOW_MS);
    expect(w.isSlow()).toBe(true);
    d.reject(new Error('끊김'));
    await expect(tracked).rejects.toThrow('끊김');
    expect(w.isSlow()).toBe(false);
    const next = deferred();
    void w.track(next.p);
    vi.advanceTimersByTime(SLOW_MS);
    expect(w.isSlow()).toBe(true);
  });
});
