// 위기 연락처 묶음(1388·109·문자)과 「보호자께 도움 요청하기」 버튼 — 위기 화면과 수다 화면(1안 「수다 안에서 받기」, 성호 11-15)이 같이 쓴다.
// 문구를 두 곳에 적지 않는다. 연락처 공식 출처는 screens/student/Crisis.tsx 머리 주석(B35).
import { useState } from 'react';
import { Icon } from './Icon';
import { useMentor } from '../state/mentor';
import { api } from '../api';

/** full: 위기 화면(카카오톡·인터넷 상담·어른 한마디까지). 아니면 수다 안 카드(1388·109·문자) */
export function CrisisContacts({ full = false }: { full?: boolean }) {
  const { say } = useMentor();
  const sms = <a className="btn btn--secondary btn--small" href="sms:1388" style={{ marginTop: 8, minHeight: 44, textDecoration: 'none' }}><Icon name="talk" size={18} />1388에 문자 보내기</a>;
  return (
    <>
      {/* 11-15 성호 「가족 중심」: 주인공은 위의 보호자 줄, 1388·109는 그 아래 작은 버튼(없애지 않음, 첫 화면 안). 작아도 누르기 쉽게 높이 44px 이상(37 지적) */}
      <p className="small muted" style={{ margin: 0 }}>{say('말하기 어려우면 여기도 있어', '말하기 어려우면 여기도 있어요')}</p>
      <a className="btn btn--secondary btn--small" href="tel:1388" style={{ justifyContent: 'flex-start', gap: 8, minHeight: 44, textDecoration: 'none' }}><strong className="num">1388</strong> 청소년 상담전화</a>
      {/* B35: 휴대폰에서 1388만 누르면 안 이어질 수 있다(공식 안내: 지역번호+1388) */}
      <p className="small muted" style={{ textAlign: 'center', margin: '-4px 0 0' }}>{say('휴대폰에서 안 걸리면 지역번호를 붙여 줘 (예: 서울 02-1388)', '휴대폰에서 안 걸리면 지역번호를 붙여 주세요 (예: 서울 02-1388)')}</p>
      <a className="btn btn--secondary btn--small" href="tel:109" style={{ justifyContent: 'flex-start', gap: 8, minHeight: 44, textDecoration: 'none' }}><strong className="num">109</strong> 자살예방 상담전화</a>
      {full ? (
        <section className="card card--flat">
          <p>{say('전화가 어려우면 1388은 문자나 카카오톡으로도 이야기할 수 있어.', '전화가 어려우면 1388은 문자나 카카오톡으로도 이야기할 수 있어요.')}</p>
          {sms}
          <p className="small" style={{ marginTop: 8 }}>{say('카카오톡에서 「청소년상담1388」 채널을 추가해서 이야기해도 돼.', '카카오톡에서 「청소년상담1388」 채널을 추가해서 이야기해도 돼요.')}</p>
          <p className="small muted">인터넷 상담: <a href="https://www.1388.go.kr" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-primary-strong)' }}>www.1388.go.kr</a></p>
          <p className="small muted" style={{ marginTop: 6 }}>{say('보호자나 선생님께 “할 이야기가 있어” 한마디만 해도 충분해.', '보호자나 선생님께 “할 이야기가 있어요” 한마디만 해도 충분해요.')}</p>
        </section>
      ) : sms}
    </>
  );
}

/** 🔴 뒤 보호자께 도움 요청(11-15 성호 「아이가 스스로 요청」 + 보완 ㉠·㉡). 서버는 🔴 때 알림을 보내지 않고, 아이가 이 버튼을 눌러야 보낸다.
 *  ㉠ 버튼을 카드 맨 위·가장 크게, 바로 아래 「무엇이 가고 무엇이 안 가는지」. 누른 뒤(또는 이미 누른 세션)는 「알렸어」 줄.
 *  again: ㉡ 같은 날 오늘 화면에서 다시 권할 때 맨 위 한 줄. */
export function CrisisAsk({ sessionId, requestedAt, onAsked, again = false }: { sessionId: string; requestedAt?: string | null; onAsked?: (at: string) => void; again?: boolean }) {
  const { say } = useMentor();
  const [asked, setAsked] = useState(!!requestedAt);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  if (asked || requestedAt) return (
    <div className="notice" role="status" style={{ justifyContent: 'flex-start', alignItems: 'flex-start', padding: '14px 16px' }}>
      <Icon name="shield" size={24} />
      <strong style={{ fontSize: 18, lineHeight: 1.5 }}>{say('보호자께 알렸어. 오늘 보호자랑 꼭 이야기해 보자.', '보호자께 알렸어요. 오늘 보호자와 꼭 이야기해 봐요.')}</strong>
    </div>
  );
  const ask = () => {
    setBusy(true); setFailed(false);
    api.askGuardian(sessionId).then((r) => { setAsked(true); onAsked?.(r.requestedAt); }, () => setFailed(true)).finally(() => setBusy(false));
  };
  return (
    <div className="stack" style={{ gap: 8 }}>
      {again && <strong style={{ fontSize: 17, lineHeight: 1.5 }}>{say('아직 보호자께 말하지 않았지? 지금이라도 괜찮아.', '아직 보호자께 말하지 않았죠? 지금이라도 괜찮아요.')}</strong>}
      <button className="btn btn--primary" style={{ minHeight: 64, fontSize: 20, fontWeight: 800, gap: 8 }} disabled={busy} onClick={ask}>
        <Icon name="shield" size={24} />보호자께 도움 요청하기
      </button>
      <p className="small" style={{ margin: 0, textAlign: 'center', lineHeight: 1.5 }}>{say('누르면 보호자께 「많이 힘들어 보여요」만 가. 네가 한 말은 안 가.', '누르면 보호자께 「많이 힘들어 보여요」만 가요. 한 말은 안 가요.')}</p>
      {failed && <p className="small" role="alert" style={{ margin: 0, textAlign: 'center', color: 'var(--color-danger, #b3261e)' }}>{say('보내지 못했어. 한 번 더 눌러 줘.', '보내지 못했어요. 한 번 더 눌러 주세요.')}</p>}
    </div>
  );
}
