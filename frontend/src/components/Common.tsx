import { useEffect, useRef, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from './Icon';
import { useServerWaking } from '../lib/slowServer';
import { useAuth } from '../state/auth';
import { useMentor } from '../state/mentor';
import { isSessionGone } from '../lib/kidScreens';
import { useSession } from '../state/session';

/** "생각 중" 로딩 (팀 명세: 비스트리밍 + 로딩 표시) */
export function Thinking({ label = '생각 중' }: { label?: string }) {
  return (
    <>
      <span className="thinking-row" role="status">
        <span className="thinking"><span /><span /><span /></span>{label}
      </span>
      <WakeNotice />
    </>
  );
}

/** 첫 접속 지연 안내: 잠든 무료 서버를 깨우느라 요청이 5초를 넘을 때만 한 줄(lib/slowServer). 학생은 멘토 말투, 어른은 존댓말 */
export function WakeNotice() {
  const waking = useServerWaking();
  const { me } = useAuth();
  const { say } = useMentor();
  if (!waking) return null;
  const text = me?.role === 'student'
    ? say('서버를 깨우는 중이야. 처음엔 1분쯤 걸릴 수 있어.', '서버를 깨우는 중이에요. 처음엔 1분쯤 걸릴 수 있어요.')
    : '서버를 깨우는 중이에요. 처음엔 1분쯤 걸릴 수 있어요.';
  return <div className="notice notice--plain" role="status">{text}</div>;
}

/** 불러오기 실패: 무슨 일인지 + 다시 시도 */
export function LoadError({ error, onRetry }: { error: string | null; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div className="notice notice--danger" role="alert">
      <span>{error}</span>
      {isSessionGone(error) ? <GoHome /> : onRetry && <button className="btn btn--secondary btn--small" onClick={onRetry}><Icon name="refresh" size={16} /> 다시 시도</button>}
    </div>
  );
}

/** 서버가 다시 시작돼 세션이 사라졌을 때: 세션을 다시 읽고 학생 홈으로(다시 시도는 같은 오류만 난다) */
function GoHome() {
  const nav = useNavigate();
  const { refresh } = useSession();
  return <button className="btn btn--secondary btn--small" onClick={async () => { await refresh(); nav('/student', { replace: true }); }}>처음으로</button>;
}

/** 아래에서 올라오는 시트. Esc로 닫히고, 닫히면 원래 버튼으로 포커스가 돌아간다 */
export function Sheet({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>('input, button')?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeRef.current(); };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); before?.focus(); };
  }, []);
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div ref={ref} className="sheet" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <h2 className="h3">{title}</h2>
        {children}
      </div>
    </div>
  );
}

/** 아직 정하지 않은 자리 — 회의에서 정할 것 표시 */
export function Todo({ children }: { children: ReactNode }) {
  return <div className="placeholder">{children}</div>;
}

/** 월~일 출석 줄 */
export function Week({ attendance, todayIndex }: { attendance: boolean[]; todayIndex: number }) {
  const days = ['월', '화', '수', '목', '금', '토', '일'];
  return (
    <div className="week" aria-label="이번 주 출석">
      {days.map((d, i) => (
        <div key={d} className={'day' + (i === todayIndex ? ' day--today' : '')}>
          <span>{d}</span>
          <span className={'dot' + (attendance[i] ? ' dot--on' : '')} aria-label={attendance[i] ? '함' : '안 함'}>{attendance[i] && <Icon name="check" size={14} />}</span>
        </div>
      ))}
    </div>
  );
}

/** 숫자 요약 타일 */
export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return <div className="stat"><div className="stat__value">{value}</div><div className="stat__label">{label}</div></div>;
}
