// 보호자 긴급 팝업(11-15 성호) — 결과·알림 화면이 5초마다 다시 읽다가 새 🔴 알림을 받으면 한 번 띄운다.
// 11-15 성호: 아래 시트가 아니라 화면 위쪽에 빨갛게, 「지금 확인하기」가 바로 보이게.
// 아이가 한 말(발췌)은 팝업에 싣지 않는다(발췌는 알림 화면에서만). 푸시·소리는 범위 밖.
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { SafetyAlert } from '../types';
import { loadShown, pickPopup, saveShown } from '../lib/crisisPopup';
import { useAuth } from '../state/auth';
import { trapTab } from '../lib/focusTrap';
import { Icon } from './Icon';
import { josa } from '../lib/josa';

/** silent: 알림 화면처럼 이미 카드가 보이는 곳 — 띄우지 않고 「띄운 것」으로만 남긴다 */
export function CrisisPopup({ alerts, silent = false }: { alerts: SafetyAlert[] | null; silent?: boolean }) {
  const { me } = useAuth();
  const nav = useNavigate();
  const [shown, setShown] = useState<Set<string>>(() => (me ? loadShown(me.id) : new Set()));
  const [open, setOpen] = useState<SafetyAlert | null>(null);
  useEffect(() => {
    if (!me || open) return;
    const next = silent
      ? (alerts ?? []).filter((a) => a.level === '긴급' && a.status === '미확인' && !shown.has(a.id))
      : [pickPopup(alerts, shown)].filter((a): a is SafetyAlert => a !== null);
    if (!next.length) return;
    const s = new Set(shown); for (const a of next) s.add(a.id);
    setShown(s); saveShown(me.id, s);
    if (!silent) setOpen(next[0]);
  }, [alerts, silent, me, open, shown]);
  if (!open) return null;
  return <TopAlert alert={open} onClose={() => setOpen(null)} onGo={() => { setOpen(null); nav('/guardian/alerts'); }} />;
}

function TopAlert({ alert, onClose, onGo }: { alert: SafetyAlert; onClose: () => void; onGo: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose); closeRef.current = onClose;
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>('.btn--danger')?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeRef.current(); else if (ref.current) trapTab(ref.current, e); };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); before?.focus(); };
  }, []);
  const who = alert.childName ? josa(alert.childName, '이', '가') : '아이가';
  return (
    <div className="crisis-top-backdrop" onClick={onClose}>
      <div ref={ref} className="crisis-top" role="alertdialog" aria-modal="true" aria-labelledby="crisis-top-title" aria-describedby="crisis-top-desc" onClick={(e) => e.stopPropagation()}>
        <div className="row" style={{ gap: 8, alignItems: 'center' }}><Icon name="warn" size={24} /><h2 id="crisis-top-title" className="h3" style={{ margin: 0 }}>{who} 많이 힘들어 보여요</h2></div>
        <p id="crisis-top-desc" style={{ margin: 0 }}>오늘 한번 이야기해 보는 건 어떤가요?</p>
        <span className="small num" style={{ opacity: .85 }}>{alert.at}</span>
        <button className="btn btn--danger" onClick={onGo}>지금 확인하기</button>
        <button className="btn btn--secondary btn--small" onClick={onClose}>닫기</button>
      </div>
    </div>
  );
}
