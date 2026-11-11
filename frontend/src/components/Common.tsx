import { useEffect, useRef, type ReactNode } from 'react';
import { Icon } from './Icon';

/** "생각 중" 로딩 (팀 명세: 비스트리밍 + 로딩 표시) */
export function Thinking({ label = '생각 중' }: { label?: string }) {
  return (
    <span className="thinking-row" role="status">
      <span className="thinking"><span /><span /><span /></span>{label}
    </span>
  );
}

/** 불러오기 실패: 무슨 일인지 + 다시 시도 */
export function LoadError({ error, onRetry }: { error: string | null; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div className="notice notice--danger" role="alert">
      <span>{error}</span>
      {onRetry && <button className="btn btn--secondary btn--small" onClick={onRetry}><Icon name="refresh" size={16} /> 다시 시도</button>}
    </div>
  );
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
