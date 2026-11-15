// 보호자 ② 안전 알림 — 긴급도·다음 행동. 🔴이어도 아이가 한 말(발췌)은 보이지 않는다(성호 11-15 v0.8)
// (결정 11-11 「11-15 안전 알림 전달 수준」, TK-74 #14). 평소 수다는 보이지 않는다.
// 11-15 성호: 회색 「후속」 대신 「확인했어요」 — 누르면 서버에 확인 시각을 남기고 카드는 「확인함 · 시각」으로 남는다(도움받을 곳 그대로).
// 오탐 닫기·만료 바꾸기·삭제는 여전히 후속(11-09 결정 중 확인만 바꿈).
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useQuietPoll } from '../../lib/quietPoll';
import { applyAck, needsAckCount, topAlerts } from '../../lib/alertAck';
import { CrisisPopup } from '../../components/CrisisPopup';
import { josa } from '../../lib/josa';
import { useAuth } from '../../state/auth';

export function GuardianAlerts() {
  const { me } = useAuth();
  const nav = useNavigate();
  if (!me) return null;
  // 아이와 연결 전에는 서버가 not_linked를 돌려준다 → 오류 대신 연결 안내
  if (me.linked.length === 0) return (
    <Frame adult title="안전 알림" exit tabs="guardian"
      actions={<button className="btn btn--primary" onClick={() => nav('/settings/family')}><Icon name="link" size={18} />아이와 연결하기</button>}>
      <div className="notice notice--plain">아이와 연결하면 확인이 필요한 일이 생겼을 때 여기에 알림이 와요.</div>
    </Frame>
  );
  return <AlertList />;
}

function AlertList() {
  const { data, setData, error, loading, reload, quiet } = useAsync(() => api.getAlerts());
  useQuietPoll([quiet]); // 4차: 🔴 알림이 새로고침 없이 뜨게
  const [help, setHelp] = useState(false);
  const [acking, setAcking] = useState<string | null>(null);
  const [ackError, setAckError] = useState<string | null>(null);
  const ack = async (id: string) => {
    setAcking(id); setAckError(null);
    try { const a = await api.ackAlert(id); setData((cur) => (cur ? applyAck(cur, a) : cur)); }
    catch { setAckError(id); }
    finally { setAcking(null); }
  };
  // 위쪽 카드: 아직 안 본 것 + 확인은 했지만 닫지 않은 긴급
  const open = data ? topAlerts(data) : [];
  const history = data?.filter((a) => !open.includes(a)) ?? [];
  // B5: 아이가 둘 이상일 때만 이름을 붙인다(하나면 생략)
  const many = new Set((data ?? []).map((a) => a.childName).filter(Boolean)).size > 1;
  const who = (a: { childName?: string }) => (many && a.childName ? `${a.childName} · ` : '');

  return (
    <Frame adult title="안전 알림" exit tabs="guardian">
      <CrisisPopup alerts={data} silent />{/* 카드가 이미 보이는 곳 — 띄우지 않고 「띄운 것」으로만 */}
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {data && <div className="small muted num">확인이 필요한 알림 {needsAckCount(data)}건</div>}
      {data && open.length === 0 && <div className="notice notice--plain">지금 확인할 알림이 없어요.</div>}
      {open.map((a) => (
        <article key={a.id} className={a.level === '긴급' ? 'card card--danger' : 'card card--warn'}>
          <div className="row between small"><span className={a.level === '긴급' ? 'pill pill--danger' : 'pill pill--accent'}>{a.level}</span><span className="muted num">{a.at}</span></div>
          <h2 className="h2" style={{ margin: '8px 0 4px' }}><Icon name="warn" size={20} /> {a.childName ? josa(a.childName, '이', '가') : '아이가'} 많이 힘들어 보여요</h2>
          <p>오늘 대화에서 걱정되는 신호가 있었어요. 오늘 한번 이야기해 보는 건 어떤가요?</p>
          {/* 11-15 성호 v0.8: 발췌(아이가 한 말)는 서버가 보내도 보이지 않는다 */}
          <button className="exit-btn" style={{ padding: '8px 0' }} onClick={() => setHelp(true)}>도움받을 곳 보기</button>
          {a.status === '미확인' ? (
            <div className="stack">
              <button className="btn btn--primary" disabled={acking === a.id} onClick={() => void ack(a.id)}>
                <Icon name="check" size={18} />{acking === a.id ? '보내는 중…' : '확인했어요'}
              </button>
              {ackError === a.id && <span className="small" role="alert">확인하지 못했어요. 다시 눌러 주세요</span>}
            </div>
          ) : (
            <div className="row small muted num" role="status"><Icon name="check" size={16} />확인함{a.ackedAt ? ` · ${a.ackedAt}` : ''}</div>
          )}
        </article>
      ))}
      {history.length > 0 && <h2 className="h3">이전 알림</h2>}
      {history.map((a) => (
        <div key={a.id} className="card card--flat row between small">
          <span className="num">{who(a)}{a.at} · {a.level}</span><span className="muted">{a.status}{a.closeReason ? ` · ${a.closeReason}` : ''}</span>
        </div>
      ))}
      <p className="small muted" style={{ textAlign: 'center' }}>걱정되는 신호가 있을 때만 알려 드려요.</p>
      {help && (
        <Sheet title="도움받을 곳" onClose={() => setHelp(false)}>
          <ul className="list">
            <li><a href="tel:109" style={{ color: 'inherit', textDecoration: 'none' }}><strong className="num" style={{ fontSize: 20, userSelect: 'all' }}>109</strong></a> 자살예방 상담전화</li>
            <li><a href="tel:1388" style={{ color: 'inherit', textDecoration: 'none' }}><strong className="num" style={{ fontSize: 20, userSelect: 'all' }}>1388</strong></a> 청소년 상담전화</li>
          </ul>
          <button className="btn btn--secondary" onClick={() => setHelp(false)}>닫기</button>
        </Sheet>
      )}
    </Frame>
  );
}
