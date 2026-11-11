// 학생 ④ 수다 (선택, 최대 10분) — 학생이 '끝내기'로 조절하고, 10분 마감은 서버가 판정한다.
// 위험 표현이 감지되면 서버가 세션을 crisis로 끝내고, 화면은 위기 화면으로 넘어간다.
import { useEffect, useRef, useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { Mascot } from '../../components/Mascot';
import { LoadError, Thinking } from '../../components/Common';
import { mmss } from '../../lib/date';
import { useCountdown } from '../../lib/useCountdown';
import { useAsync } from '../../lib/useAsync';
import { RequirePhase, useSession } from '../../state/session';
import type { ChatMessage } from '../../types';

const SUGGEST = ['오늘 피곤해', '자랑할 거 있어', '그냥 얘기하고 싶어'];

export function StudentChat() {
  return <RequirePhase phase="chat"><Chat /></RequirePhase>;
}

function Chat() {
  const { session, sync, refresh } = useSession();
  const id = session!.id;
  const { data, error, reload } = useAsync(() => api.getChat(id), [id]);
  const [msgs, setMsgs] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => { if (data) setMsgs(data.messages); }, [data]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }); }, [msgs, busy]);
  const left = useCountdown(data ? data.remainingSec : null, refresh);

  const send = async (raw: string) => {
    const v = raw.trim();
    if (!v || busy) return;
    setMsgs((m) => [...m, { from: 'me', text: v }]);
    setText(''); setBusy(true); setSendError(null);
    try {
      const r = await api.sendChat(id, v);
      if (r.session.phase !== 'chat') { sync(r.session); return; } // 위기 감지·시간 종료 → 서버 단계에 맞는 화면으로
      setMsgs((m) => [...m, { from: 'mentor', text: r.reply }]);
    } catch (e) { setSendError((e as Error).message); } finally { setBusy(false); }
  };
  const end = async () => { setBusy(true); try { sync(await api.endChat(id)); } catch (e) { setSendError((e as Error).message); setBusy(false); } };

  const actions = (
    <>
      {/* BRIEF: 입력창 위 오른쪽, 회색 테두리 '오늘 수다 끝내기' */}
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <button className="btn btn--secondary btn--small" disabled={busy} onClick={end}>오늘 수다 끝내기</button>
      </div>
      <div className="chip-row chip-row--scroll">{SUGGEST.map((s) => <button key={s} className="chip" disabled={busy} onClick={() => send(s)}>{s}</button>)}</div>
      {/* 입력창 옆 + 버튼 금지 (BRIEF 공통 디자인) */}
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input id="chat-input" className="input" aria-label="메시지 입력" placeholder="메시지 입력" maxLength={200} value={text} onChange={(e) => setText(e.target.value)} />
        <button className="btn btn--primary" disabled={!text.trim() || busy} aria-label="보내기"><Icon name="send" size={20} /></button>
      </form>
    </>
  );

  return (
    <Frame title="수다" back="/student" right={<span className="pill pill--mint num"><Icon name="clock" size={14} /> {mmss(left)}</span>} actions={actions}>
      <LoadError error={error} onRetry={reload} />
      <div className="chat-log" aria-live="polite">
        {msgs.map((m, i) => m.from === 'mentor' ? (
          <div key={i} className="mentor"><Mascot mood="wave" size={40} /><div className="bubble">{m.text}</div></div>
        ) : (
          <div key={i} className="bubble bubble--me">{m.text}</div>
        ))}
        {busy && <Thinking />}
        <div ref={bottom} />
      </div>
      <LoadError error={sendError} />
    </Frame>
  );
}
