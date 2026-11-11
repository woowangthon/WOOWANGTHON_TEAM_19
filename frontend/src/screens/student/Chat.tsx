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
import { createBatcher, followPending } from '../../lib/chatBatch';
import type { ChatMessage, ChatReply } from '../../types';

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
  // 끊어 보내기(11-11): 입력은 막지 않는다. 모은 말은 1.5초 뒤(5개면 바로) 한 번에 보낸다(lib/chatBatch).
  const [waiting, setWaiting] = useState(0);     // 서버에 나가 있는 요청 수 → 이 동안 「생각 중」
  const [buffered, setBuffered] = useState(0);   // 아직 보내지 않고 모아 둔 조각 수
  const [ending, setEnding] = useState(false);
  const stopped = useRef(false);                 // 위기·단계 바뀜 뒤 늦게 온 답은 버린다
  const [sendError, setSendError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => { if (data) setMsgs(data.messages); }, [data]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }); }, [msgs, waiting]);
  const left = useCountdown(data ? data.remainingSec : null, refresh);

  /** 응답 하나 처리. 계속 받아도 되면 true */
  const take = (r: ChatReply): boolean => {
    if (stopped.current) return false;
    if (r.session.phase !== 'chat') { stopped.current = true; sync(r.session); return false; } // 위기 감지·시간 종료 → 서버 단계에 맞는 화면으로
    if (!r.queued && r.reply) setMsgs((m) => [...m, { from: 'mentor', text: r.reply }]); // queued면 앞 요청이 답을 가져온다
    return true;
  };
  const sendBatch = async (texts: string[]) => {
    setBuffered(0); setWaiting((n) => n + 1); setSendError(null);
    try { await followPending(await api.sendChat(id, texts), () => api.replyChat(id), take); }
    catch (e) { if (!stopped.current) setSendError((e as Error).message); }
    finally { setWaiting((n) => n - 1); }
  };
  const sendRef = useRef(sendBatch);
  sendRef.current = sendBatch;
  const [batcher] = useState(() => createBatcher((texts) => { void sendRef.current(texts); }));
  useEffect(() => () => batcher.cancel(), [batcher]);

  const send = (raw: string) => {
    const v = raw.trim();
    if (!v || stopped.current || ending) return;
    setMsgs((m) => [...m, { from: 'me', text: v }]);
    setText('');
    batcher.push(v);
    setBuffered(batcher.size());
  };
  const end = async () => { setEnding(true); try { sync(await api.endChat(id)); } catch (e) { setSendError((e as Error).message); setEnding(false); } };
  const busy = waiting > 0 || buffered > 0 || ending; // 「끝내기」는 보낼 말·답이 남아 있으면 막는다

  const actions = (
    <>
      {/* BRIEF: 입력창 위 오른쪽, 회색 테두리 '오늘 수다 끝내기' */}
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <button className="btn btn--secondary btn--small" disabled={busy} onClick={end}>오늘 수다 끝내기</button>
      </div>
      <div className="chip-row chip-row--scroll">{SUGGEST.map((s) => <button key={s} className="chip" disabled={ending} onClick={() => send(s)}>{s}</button>)}</div>
      {/* 입력창 옆 + 버튼 금지 (BRIEF 공통 디자인) */}
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input id="chat-input" className="input" aria-label="메시지 입력" placeholder="메시지 입력" maxLength={200} value={text} onChange={(e) => setText(e.target.value)} />
        <button className="btn btn--primary" disabled={!text.trim() || ending} aria-label="보내기"><Icon name="send" size={20} /></button>
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
        {waiting > 0 && <Thinking />}
        <div ref={bottom} />
      </div>
      <LoadError error={sendError} />
    </Frame>
  );
}
