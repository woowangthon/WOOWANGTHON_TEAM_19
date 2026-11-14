// 보호자 ② 안전 알림 — 분류·긴급도·다음 행동. 🔴(긴급)일 때만 걱정된 말의 앞뒤 일부(±2턴·300자)를 함께 보인다
// (결정 11-11 「11-15 안전 알림 전달 수준」, TK-74 #14). 평소 수다는 보이지 않는다.
// 11-09 팀 결정: 확인·오탐 닫기는 11-15에 회색 「후속」 버튼만(누를 수 없음). 서버·mock을 부르지 않는다.
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
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
  const { data, error, loading, reload } = useAsync(() => api.getAlerts());
  const [help, setHelp] = useState(false);
  // 위쪽 카드: 아직 안 본 것 + 확인은 했지만 닫지 않은 긴급
  const open = data?.filter((a) => a.status === '미확인' || (a.level === '긴급' && a.status === '확인함')) ?? [];
  const history = data?.filter((a) => !open.includes(a)) ?? [];
  // B5: 아이가 둘 이상일 때만 이름을 붙인다(하나면 생략)
  const many = new Set((data ?? []).map((a) => a.childName).filter(Boolean)).size > 1;
  const who = (a: { childName?: string }) => (many && a.childName ? `${a.childName} · ` : '');

  return (
    <Frame adult title="안전 알림" exit tabs="guardian">
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {data && <div className="small muted num">확인이 필요한 알림 {open.length}건</div>}
      {data && open.length === 0 && <div className="notice notice--plain">지금 확인할 알림이 없어요.</div>}
      {open.map((a) => (
        <article key={a.id} className={a.level === '긴급' ? 'card card--danger' : 'card card--warn'}>
          <div className="row between small"><span className={a.level === '긴급' ? 'pill pill--danger' : 'pill pill--accent'}>{a.level}</span><span className="muted num">{a.at}</span></div>
          <h2 className="h2" style={{ margin: '8px 0 4px' }}><Icon name="warn" size={20} /> {who(a)}{a.category} · 확인 필요</h2>
          <p>{a.action}</p>
          {a.excerpt && (
            <section className="card card--flat stack" aria-label="아이가 한 말의 앞뒤 일부">
              <span className="small muted">아이가 한 말의 앞뒤 일부 (개인정보는 가렸어요)</span>
              <blockquote style={{ margin: 0, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{a.excerpt}</blockquote>
              <span className="small">아이를 다그치기보다, 아이와 대화해 보세요.</span>
            </section>
          )}
          <button className="exit-btn" style={{ padding: '8px 0' }} onClick={() => setHelp(true)}>도움받을 곳 보기</button>
          <div className="stack">
            <button className="btn btn--secondary" disabled>후속</button>
            <span className="small muted">확인·닫기는 다음 버전에서 열려요</span>
          </div>
        </article>
      ))}
      {history.length > 0 && <h2 className="h3">이전 알림</h2>}
      {history.map((a) => (
        <div key={a.id} className="card card--flat row between small">
          <span className="num">{who(a)}{a.at} · {a.level}</span><span className="muted">{a.status}{a.closeReason ? ` · ${a.closeReason}` : ''}</span>
        </div>
      ))}
      <p className="small muted" style={{ textAlign: 'center' }}>평소 수다는 표시하지 않아요. 위험 신호가 있을 때만 그 앞뒤 일부를 보여 드려요</p>
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
