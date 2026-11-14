// 로그인 상태. 아이디·비밀번호로 로그인하고, 「자동 로그인」이면 다음에 앱을 켤 때 바로 그 역할 화면으로 들어간다.
// · 로그인 뒤에는 로그인·가입 화면으로 "뒤로가기" 할 수 없다: 그 화면들은 GuestOnly가 막고, 로그인 이동은 항상 replace.
// · 다른 계정으로 바꾸려면 「설정 → 로그아웃」.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { api } from '../api';
import { setDemoRole, setLoggedOutHandler } from '../api/http';
import type { AccountRole, Me } from '../types';
import { useOnResume } from '../lib/resume';
import { useSession } from './session';
import { useMentor } from './mentor';

interface AuthCtx {
  me: Me | null;
  ready: boolean;
  /** 서버에 다시 물어보기(연결·승인 상태가 바뀌었을 수 있을 때) */
  refresh: () => Promise<Me | null>;
  /** 다시 열기·화면 진입 때: 요청이 실패하면(인터넷 끊김 등) 지금 로그인을 그대로 둔다. 로그인 만료(401)는 따로 처리됨 */
  refreshQuiet: () => Promise<void>;
  /** 로그인/가입 직후: 받은 Me로 바꾸고 학습 상태도 새로 불러온다 */
  enter: (me: Me) => Promise<void>;
  logout: () => Promise<void>;
}
const Ctx = createContext<AuthCtx | null>(null);
const EXPIRED_KEY = 'ai-mentor-expired';
/** 로그인이 서버에서 끝나 풀렸는지(한 번 읽으면 지움) — 로그인 화면 안내용 */
export function takeLoginExpired(): boolean {
  try { const v = sessionStorage.getItem(EXPIRED_KEY) === '1'; sessionStorage.removeItem(EXPIRED_KEY); return v; } catch { return false; }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const session = useSession();
  const mentor = useMentor();
  const reloadSession = session.refresh; // 둘 다 useCallback이라 바뀌지 않는다(refresh 효과가 반복되지 않게)
  const reloadMentor = mentor.reload;
  // 서버 요청의 역할 헤더는 로그인한 계정의 역할로 정한다(api/http.ts). 역할이 바뀌면 학습 상태도 그 역할로 다시 읽는다
  const refresh = useCallback(async () => {
    const m = await api.getMe().catch(() => null);
    const changed = setDemoRole(m?.role ?? null);
    if (changed && m) await Promise.all([reloadSession(), reloadMentor()]);
    setMe(m); setReady(true); return m;
  }, [reloadSession, reloadMentor]);
  useEffect(() => { refresh(); }, [refresh]);
  const refreshQuiet = useCallback(async () => {
    let m: Me | null;
    try { m = await api.getMe(); } catch { return; }
    const changed = setDemoRole(m?.role ?? null);
    if (changed && m) await Promise.all([reloadSession(), reloadMentor()]);
    setMe(m);
  }, [reloadSession, reloadMentor]);
  // 다른 기기에서 연결·학원이 바뀌었을 수 있다 → 앱을 다시 열면(화면 다시 보임·인터넷 복귀) 로그인한 사람의 정보를 다시 읽는다
  useOnResume(() => { if (me) void refreshQuiet(); });
  const enter = useCallback(async (m: Me) => { setDemoRole(m.role); setMe(m); await Promise.all([session.refresh(), mentor.reload()]); }, [session, mentor]);
  // 로그아웃과 같은 정리(서버 호출만 빼고). 서버가 「로그인 안 됨」이라 할 때도 쓴다 → me가 null이면 RequireRole이 로그인 화면으로 보낸다
  const clear = useCallback(async () => { setDemoRole(null); setMe(null); await Promise.all([session.refresh(), mentor.reload()]); }, [session, mentor]);
  const logout = useCallback(async () => { await api.logout(); await clear(); }, [clear]);
  // 서버가 「로그인 안 됨」이라 해서 풀린 경우: 로그인 화면이 「다시 로그인해 주세요」를 한 번 보여 주게 표시
  useEffect(() => { setLoggedOutHandler(() => { try { sessionStorage.setItem(EXPIRED_KEY, '1'); } catch { /* 막혀도 안내만 빠짐 */ } void clear(); }); return () => setLoggedOutHandler(null); }, [clear]);
  return <Ctx.Provider value={{ me, ready, refresh, refreshQuiet, enter, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error('AuthProvider 안에서만 쓸 수 있어요');
  return v;
}

/** 화면이 열릴 때 내 정보(연결·학원 상태)를 서버에서 다시 읽는다 — 다른 기기에서 바뀐 것이 바로 보이게 */
export function useRefreshMeOnMount() {
  const { refreshQuiet } = useAuth();
  useEffect(() => { void refreshQuiet(); }, [refreshQuiet]);
}

/** 역할별 첫 화면 */
export function homeFor(me: Me | null): string {
  if (!me) return '/login';
  switch (me.role) {
    case 'student': return '/student';
    case 'guardian': return '/guardian';
    case 'teacher': return '/teacher/today'; // 소속이 없거나 승인 대기면 할 일 화면이 안내한다
    case 'operator': return '/operator';
  }
}

const Loading = () => <div className="frame"><main className="screen-body center muted">불러오는 중…</main></div>;

/** 로그인한 사람만, 그리고 맞는 역할만 들어오게 한다 */
export function RequireRole({ role, children }: { role: AccountRole | AccountRole[]; children: ReactNode }) {
  const { me, ready } = useAuth();
  if (!ready) return <Loading />;
  if (!me) return <Navigate to="/login" replace />;
  const roles = Array.isArray(role) ? role : [role];
  if (!roles.includes(me.role)) return <Navigate to={homeFor(me)} replace />;
  return <>{children}</>;
}

/** 로그인·가입·찾기 화면: 이미 로그인했으면 자기 화면으로 보낸다(뒤로가기로 돌아와도) */
/** 가입 직후 표시: 가입 화면(GuestOnly)이 로그인된 것을 보고 홈으로 보내기 전에 「가입 완료」로 보내게 한다 */
let justSignedUp = false;
export function markJustSignedUp() { justSignedUp = true; }
/** 「가입 완료」에 도착하면 표시를 지운다(다음 로그인이 /welcome으로 가지 않게) */
export function clearJustSignedUp() { justSignedUp = false; }

export function GuestOnly({ children }: { children: ReactNode }) {
  const { me, ready } = useAuth();
  if (!ready) return <Loading />;
  if (me && justSignedUp) { justSignedUp = false; return <Navigate to="/welcome" replace />; }
  if (me) return <Navigate to={homeFor(me)} replace />;
  return <>{children}</>;
}

export function RootRedirect() {
  const { me, ready } = useAuth();
  if (!ready) return <Loading />;
  return <Navigate to={homeFor(me)} replace />;
}
