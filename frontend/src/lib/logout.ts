// 로그아웃 순서(dev round2 #14, 보안 검토 반영 11-14): 서버 로그아웃이 된 뒤에만 이 기기 로그인을 지운다.
// 로그인 쿠키(HttpOnly)는 서버만 지울 수 있다 → 서버가 실패했는데 화면만 지우면 앱을 다시 열 때 그대로 로그인된다.
// 그래서 실패하면 지우지 않고 오류를 던져 화면이 「다시 눌러 주세요」를 보인다. 이미 로그아웃된 경우(401)는 http.ts onLoggedOut이 지운다.
export const LOGOUT_FAILED = '로그아웃하지 못했어요. 인터넷 연결을 확인하고 다시 눌러 주세요.';

export async function logoutThenClear(serverLogout: () => Promise<unknown>, clear: () => Promise<void>): Promise<void> {
  try { await serverLogout(); } catch { throw new Error(LOGOUT_FAILED); }
  await clear();
}
