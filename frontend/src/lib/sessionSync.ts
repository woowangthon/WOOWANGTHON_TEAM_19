// 공유 세션(state/session)을 서버와 맞추는 작은 규칙들. 화면 코드에서 빼서 테스트한다(dev round2 #1·#2).
import type { SessionView } from '../types';

/** 서버에 다시 물어보기. 실패하면 keepOnFail이면 이전 세션을 그대로(잠깐 끊긴 것만으로 진행 중인 세션을 잃지 않게),
 *  아니면 null(처음 불러오기·로그아웃처럼 이전 값을 믿을 수 없을 때) */
export async function loadSession(fetch: () => Promise<SessionView | null>, prev: SessionView | null, keepOnFail: boolean): Promise<SessionView | null> {
  try { return await fetch(); } catch { return keepOnFail ? prev : null; }
}

/** 오늘 화면: 서버가 준 오늘 세션으로 공유 세션을 맞춘다(그사이 수다 10분이 끝나 wrap이 됐을 수 있다) */
export function syncFromHome(home: { session?: SessionView | null } | null | undefined, sync: (s: SessionView | null) => void): void {
  if (home) sync(home.session ?? null);
}

/** 수다 화면이 이미 끝난 시간(0초)으로 열리면 카운트다운이 0을 지나지 않아 onZero가 안 불린다 → 바로 다시 묻는다 */
export function refreshIfChatExpired(remainingSec: number | null | undefined, refresh: () => void): void {
  if (remainingSec === 0) refresh();
}
