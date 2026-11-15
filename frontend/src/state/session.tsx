// 학생의 "오늘 세션"을 화면끼리 나눠 쓰는 저장소.
// 단계(phase)는 서버가 정한다. 화면은 서버가 준 단계에 맞는 주소로만 간다(RequirePhase).
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { api } from '../api';
import { onceAtATime, useOnResume } from '../lib/resume';
import { loadSession } from '../lib/sessionSync';
import { WakeNotice } from '../components/Common';
import type { Phase, SessionView } from '../types';

interface SessionCtx {
  session: SessionView | null;
  ready: boolean;                                // 처음 불러오기가 끝났는지
  sync: (s: SessionView | null) => void;         // 서버 응답에 들어 있는 최신 세션으로 맞추기
  refresh: () => Promise<SessionView | null>;    // 서버에 다시 물어보기(실패하면 지금 세션을 그대로 둔다)
  reset: () => Promise<SessionView | null>;      // 로그인·로그아웃·세션 사라짐 때: 실패하면 null
}
const Ctx = createContext<SessionCtx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionView | null>(null);
  const [ready, setReady] = useState(false);
  const current = useRef<SessionView | null>(null);
  current.current = session;
  // 화면에서 부르는 갱신(풀기 20분 끝·수다 마감 뒤 등)은 인터넷이 잠깐 끊겨도 세션을 지우지 않는다(아래 resync와 같은 원칙).
  // 처음 불러오기와 로그인·로그아웃(reset)은 실패하면 null — 이전 값을 믿을 수 없다
  const load = useCallback(async (keepOnFail: boolean) => {
    const s = await loadSession(() => api.getActiveSession(), current.current, keepOnFail);
    current.current = s; setSession(s); setReady(true);
    return s;
  }, []);
  const refresh = useCallback(() => load(true), [load]);
  const reset = useCallback(() => load(false), [load]);
  useEffect(() => { reset(); }, [reset]);
  // 앱을 내렸다 올리거나 인터넷이 돌아오면 서버 단계를 다시 읽는다(그사이 수다 시간이 끝났을 수 있다).
  // 실패하면 지금 화면을 그대로 둔다(아직 인터넷이 안 붙었을 때 첫 화면으로 튕기지 않게). 겹치면 한 번만.
  const [resync] = useState(() => onceAtATime(() => api.getActiveSession().then(setSession, () => {})));
  useOnResume(() => { void resync(); });
  return <Ctx.Provider value={{ session, ready, sync: setSession, refresh, reset }}>{children}</Ctx.Provider>;
}

export function useSession() {
  const v = useContext(Ctx);
  if (!v) throw new Error('SessionProvider 안에서만 쓸 수 있어요');
  return v;
}

/** 단계마다 갈 화면 */
export function routeFor(s: SessionView | null): string {
  switch (s?.phase) {
    case 'solve': return '/student/solve';
    case 'transition': return '/student/done';
    case 'chat': return '/student/chat';
    case 'wrap': return '/student/wrap';
    case 'crisis': return '/student/crisis';
    default: return '/student';
  }
}

/** 이 화면이 지금 단계와 맞지 않으면 맞는 화면으로 보낸다(주소를 직접 쳐도, 시간이 끝나도 안전) */
export function RequirePhase({ phase, children }: { phase: Phase; children: ReactNode }) {
  const { session, ready } = useSession();
  if (!ready) return <div className="frame"><main className="screen-body center muted">불러오는 중…<WakeNotice /></main></div>;
  if (!session || session.phase !== phase) return <Navigate to={routeFor(session)} replace />;
  return <>{children}</>;
}
