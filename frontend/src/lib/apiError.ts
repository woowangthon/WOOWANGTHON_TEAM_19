// 서버 오류에 상태 번호·코드를 붙인다(dev round3 #17·#5, 성호 11-14). 네트워크 끊김은 status 0.
export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string) { super(message); this.name = 'ApiError'; }
}
/** 잠깐 끊김(네트워크·서버 5xx) — 로그인이 풀린 것이 아니다. 로그아웃하지 않고 「다시 시도」를 보인다 */
export const isTransient = (e: unknown) => e instanceof ApiError && (e.status === 0 || e.status >= 500);
/** 서버가 「약속부터」(409 needs_promise)라고 막음 — 약속 화면으로 보낸다(#5) */
export const needsPromise = (e: unknown) => e instanceof ApiError && e.status === 409 && e.code === 'needs_promise';
