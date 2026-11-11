// 보호자 ② 안전 알림 — 대화 원문 없이 분류·긴급도·다음 행동만 (BRIEF 안전 알림 정책 3)
// 긴급은 '확인했어요' 뒤에만 '괜찮아요'로 닫을 수 있다 (BRIEF v2 검토 후 확정 1). 규칙은 서버도 다시 검사한다.
import { useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import type { SafetyAlert } from '../../types';

const REASONS = ['아이와 이야기해 봤어요', '오해였어요', '기타'];

export function GuardianAlerts() {
  const { data, setData, error, loading, reload } = useAsync(() => api.getAlerts());
  const [closing, setClosing] = useState<SafetyAlert | null>(null);
  const [reason, setReason] = useState(REASONS[0]);
  const [help, setHelp] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actError, setActError] = useState<string | null>(null);
  // 위쪽 카드: 아직 안 본 것 + 확인은 했지만 닫지 않은 긴급
  const open = data?.filter((a) => a.status === '미확인' || (a.level === '긴급' && a.status === '확인함')) ?? [];
  const history = data?.filter((a) => !open.includes(a)) ?? [];

  const act = async (fn: () => Promise<SafetyAlert>) => {
    setBusy(true); setActError(null);
    try { const a = await fn(); setData(data!.map((x) => (x.id === a.id ? a : x))); }
    catch (e) { setActError((e as Error).message); } finally { setBusy(false); setClosing(null); }
  };

  return (
    <Frame adult title="안전 알림" exit tabs="guardian">
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {data && <div className="small muted num">확인이 필요한 알림 {open.length}건</div>}
      {data && open.length === 0 && <div className="notice notice--plain">지금 확인할 알림이 없어요.</div>}
      {open.map((a) => (
        <article key={a.id} className={a.level === '긴급' ? 'card card--danger' : 'card card--warn'}>
          <div className="row between small"><span className={a.level === '긴급' ? 'pill pill--danger' : 'pill pill--accent'}>{a.level}</span><span className="muted num">{a.at}</span></div>
          <h2 className="h2" style={{ margin: '8px 0 4px' }}><Icon name="warn" size={20} /> {a.category} · 확인 필요</h2>
          <p>{a.action}</p>
          <button className="exit-btn" style={{ padding: '8px 0' }} onClick={() => setHelp(true)}>도움받을 곳 보기</button>
          <div className="stack">
            {a.status === '미확인' && <button className="btn btn--primary" disabled={busy} onClick={() => act(() => api.ackAlert(a.id))}>확인했어요</button>}
            {/* 긴급은 확인 전에는 닫기 버튼이 나오지 않는다 */}
            {(a.level === '주의' || a.status === '확인함') && <button className="btn btn--secondary" disabled={busy} onClick={() => setClosing(a)}>괜찮아요</button>}
          </div>
        </article>
      ))}
      <LoadError error={actError} />
      {history.length > 0 && <h2 className="h3">이전 알림</h2>}
      {history.map((a) => (
        <div key={a.id} className="card card--flat row between small">
          <span className="num">{a.at} · {a.level}</span><span className="muted">{a.status}{a.closeReason ? ` · ${a.closeReason}` : ''}</span>
        </div>
      ))}
      <p className="small muted" style={{ textAlign: 'center' }}>대화 원문은 표시하지 않아요</p>
      {closing && (
        <Sheet title="닫는 이유" onClose={() => setClosing(null)}>
          {REASONS.map((r, i) => (
            <label key={r} className="row"><input id={`reason-${i}`} type="radio" name="reason" checked={reason === r} onChange={() => setReason(r)} /> {r}</label>
          ))}
          <button className="btn btn--primary" disabled={busy} onClick={() => act(() => api.closeAlert(closing.id, reason))}>괜찮아요 · 닫기</button>
        </Sheet>
      )}
      {help && (
        <Sheet title="도움받을 곳" onClose={() => setHelp(false)}>
          <ul className="list">
            <li><a href="tel:109" style={{ color: 'inherit', textDecoration: 'none' }}><strong className="num" style={{ fontSize: 20, userSelect: 'all' }}>109</strong></a> 자살예방 상담전화</li>
            <li><a href="tel:1388" style={{ color: 'inherit', textDecoration: 'none' }}><strong className="num" style={{ fontSize: 20, userSelect: 'all' }}>1388</strong></a> 청소년 상담전화</li>
          </ul>
          <p className="small muted">먼저 아이의 말을 끝까지 들어 주세요. 혼내거나 캐묻기보다 “말해 줘서 고마워”가 먼저예요.</p>
          <button className="btn btn--secondary" onClick={() => setHelp(false)}>닫기</button>
        </Sheet>
      )}
    </Frame>
  );
}
