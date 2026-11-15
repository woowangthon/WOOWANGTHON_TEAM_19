// 첫 접속 지연 안내. 무료 서버(Render)는 15분 쉬면 잠들어 첫 요청이 1분쯤 걸린다.
// 서버가 깨어 있는지 모를 때(이번 실행에서 아직 응답이 없었거나, 마지막 응답 뒤 14분 넘게 지남)
// 요청이 5초를 넘으면 「깨우는 중」으로 본다. 방금 답한 서버의 긴 요청(LLM 답 기다리기)은 안내하지 않는다.
import { useSyncExternalStore } from 'react';

export const SLOW_MS = 5000;
export const AWAKE_MS = 14 * 60 * 1000;

export interface SlowWatch {
  /** 서버 요청 하나를 지켜본다. 결과·오류는 그대로 돌려준다 */
  track<T>(p: Promise<T>): Promise<T>;
  /** 지금 「깨우는 중」 안내를 보여야 하는지 */
  isSlow(): boolean;
  subscribe(fn: () => void): () => void;
}

export function createSlowWatch(now: () => number = () => Date.now()): SlowWatch {
  let lastOk: number | null = null;   // 마지막으로 서버가 응답한 시각
  let slow = 0;                        // 5초를 넘긴 채 아직 안 끝난 요청 수
  const subs = new Set<() => void>();
  const emit = () => subs.forEach((f) => f());
  const awake = () => lastOk != null && now() - lastOk <= AWAKE_MS;
  return {
    track(p) {
      let counted = false;
      const timer = awake() ? null : setTimeout(() => { counted = true; slow++; emit(); }, SLOW_MS);
      const settle = (ok: boolean) => {
        if (timer) clearTimeout(timer);
        if (ok) lastOk = now();
        if (counted) { counted = false; slow--; emit(); }
      };
      return p.then((v) => { settle(true); return v; }, (e: unknown) => { settle(false); throw e; });
    },
    isSlow: () => slow > 0,
    subscribe(fn) { subs.add(fn); return () => { subs.delete(fn); }; },
  };
}

/** 앱 전체에서 하나(api/http.ts의 fetch가 여기에 등록한다) */
export const slowWatch = createSlowWatch();

/** 화면용: 지금 서버를 깨우는 중인지 */
export function useServerWaking(): boolean {
  return useSyncExternalStore(slowWatch.subscribe, slowWatch.isSlow, () => false);
}
