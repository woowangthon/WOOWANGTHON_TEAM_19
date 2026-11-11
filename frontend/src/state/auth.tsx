// 로그인 상태. 아이디·비밀번호로 로그인하고, 「자동 로그인」이면 다음에 앱을 켤 때 바로 그 역할 화면으로 들어간다.
// · 로그인 뒤에는 로그인·가입 화면으로 "뒤로가기" 할 수 없다: 그 화면들은 GuestOnly가 막고, 로그인 이동은 항상 replace.
// · 다른 계정으로 바꾸려면 「설정 → 로그아웃」.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { api } from '../api';
import { setDemoRole } from '../api/http';
import type { AccountRole, Me } from '../types';
import { useSession } from './session';
import { useMentor } from './mentor';

interface AuthCtx {
  me: Me | null;
  ready: boolean;
  /** 서버에 다시 물어보기(연결·승인 상태가 바뀌었을 수 있을 때) */
  refresh: () => Promise<Me | null>;
  /** 로그인/가입 직후: 받은 Me로 바꾸고 학습 상태도 새로 불러온다 */
  enter: (me: Me) => Promise<void>;
  logout: () => Promise<void>;
}
const Ctx = createContext<AuthCtx | null>(null);

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
  const enter = useCallback(async (m: Me) => { setDemoRole(m.role); setMe(m); await Promise.all([session.refresh(), mentor.reload()]); }, [session, mentor]);
  const logout = useCallback(async () => { await api.logout(); setDemoRole(null); setMe(null); await Promise.all([session.refresh(), mentor.reload()]); }, [session, mentor]);
  return <Ctx.Provider value={{ me, ready, refresh, enter, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error('AuthProvider 안에서만 쓸 수 있어요');
  return v;
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
export function GuestOnly({ children }: { children: ReactNode }) {
  const { me, ready } = useAuth();
  if (!ready) return <Loading />;
  if (me) return <Navigate to={homeFor(me)} replace />;
  return <>{children}</>;
}

export function RootRedirect() {
  const { me, ready } = useAuth();
  if (!ready) return <Loading />;
  return <Navigate to={homeFor(me)} replace />;
}
