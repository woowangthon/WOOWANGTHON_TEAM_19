// 강사 화면 작은 규칙들. 화면 코드에서 빼서 테스트한다(dev round2 #10·#11·#13).

/** 학생 시트 「지정한 문제」 글을 서버 값(시트를 연 순간의 assignedProblemId)으로 채울지.
 *  처음 열 때 단원 목록이 늦게 오면 한 번만 — 강사가 고른 뒤(touched)에는 옛 값으로 되살리지 않는다(「없음」을 골랐는데 다시 보이던 것) */
export function shouldFillPicked(s: { touched: boolean; picked: string | null; assignedId: string | null | undefined; units: unknown[] | null }): boolean {
  return !s.touched && !s.picked && !!s.assignedId && !!s.units;
}

/** 화면 값을 먼저 바꾸고(apply) 서버에 보낸다. 실패하면 이전 값으로 되돌리고(revert) 오류를 넘긴다 — 저장 실패를 저장된 것으로 착각하지 않게 */
export async function withRollback<T>(apply: () => void, revert: () => void, call: () => Promise<T>): Promise<T> {
  apply();
  try { return await call(); } catch (e) { revert(); throw e; }
}

/** 서버(http)는 초안을 하루 한 번만 만들고 메모를 따로 고치는 길이 없다 → 초안이 있으면 메모 입력을 잠근다(고쳐도 말없이 사라지지 않게) */
export function memoLocked(hasDraft: boolean, mode: 'mock' | 'http'): boolean {
  return hasDraft && mode === 'http';
}

/** 칭찬 씨앗 시트의 처음 개수: 보통 2개, 오늘 남은 개수(하루 10개까지)가 그보다 적으면 남은 만큼 */
export function grantDefault(grantedToday: number): number {
  return Math.min(2, 10 - grantedToday);
}

/** 단원을 바꾸면 문제 고르기는 「처음 문제부터」('')로 — 옛 단원의 문제 id가 새 단원과 같이 가면 서버 422(11-14 실측) */
export const pickForUnit = (prevUnit: string, nextUnit: string, pick: string) => (prevUnit === nextUnit ? pick : '');
