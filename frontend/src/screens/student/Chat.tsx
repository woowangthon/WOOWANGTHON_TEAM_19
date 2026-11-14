// 학생 ④ 수다 (선택, 최대 10분) — 학생이 '끝내기'로 조절하고, 10분 마감은 서버가 판정한다.
// 위험 표현이 감지되면 서버가 세션을 crisis로 끝내고, 화면은 위기 화면으로 넘어간다.
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { Mascot } from '../../components/Mascot';
import { LoadError, Thinking } from '../../components/Common';
import { mmss } from '../../lib/date';
import { useCountdown } from '../../lib/useCountdown';
import { useAsync } from '../../lib/useAsync';
import { RequirePhase, useSession } from '../../state/session';
import { useMentor } from '../../state/mentor';
import { createBatcher, followPending, routeAfterLeftChat } from '../../lib/chatBatch';
import { onceAtATime, useOnResume } from '../../lib/resume';
import type { ChatMessage, ChatReply } from '../../types';

const SUGGEST = ['오늘 피곤해', '자랑할 거 있어', '그냥 얘기하고 싶어'];

export function StudentChat() {
  return <RequirePhase phase="chat"><Chat /></RequirePhase>;
}

function Chat() {
  const { session, sync, refresh } = useSession();
  const { say } = useMentor();
  const id = session!.id;
  const { data, setData, error, reload } = useAsync(() => api.getChat(id), [id]);
  const [msgs, setMsgs] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  // 끊어 보내기(11-11): 입력은 막지 않는다. 모은 말은 1.5초 뒤(5개면 바로) 한 번에 보낸다(lib/chatBatch).
  const [waiting, setWaiting] = useState(0);     // 서버에 나가 있는 요청 수 → 이 동안 「생각 중」
  const [buffered, setBuffered] = useState(0);   // 아직 보내지 않고 모아 둔 조각 수
  const [ending, setEnding] = useState(false);
  const [closing, setClosing] = useState(false);  // U9: 끝난 뒤 2초 안내를 보이고 넘어간다(서버 판정·단계는 그대로)
  const stopped = useRef(false);                 // 위기·단계 바뀜 뒤 늦게 온 답은 버린다
  const [sendError, setSendError] = useState<string | null>(null);
  const inflight = useRef(0);                    // 다시 읽기용: 나가 있는 요청 수(렌더를 기다리지 않는 값)
  const sends = useRef(0);                       // 다시 읽기용: 지금까지 보낸 묶음 수
  const endingRef = useRef(false);
  endingRef.current = ending;
  const sendRef = useRef<(texts: string[]) => Promise<void>>(async () => {});
  const [batcher] = useState(() => createBatcher((texts) => { void sendRef.current(texts); }));
  const bottom = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const left_ = useRef(false);                   // 화면을 떠났는지(떠난 뒤 온 위기 응답은 위기 화면으로 보낸다)
  // 서버 대화 + 아직 안 보낸(묶여 있는) 내 말. 다시 읽어도 묶인 말은 버리지 않는다
  useEffect(() => { if (data) setMsgs([...data.messages, ...batcher.peek().map((t): ChatMessage => ({ from: 'me', text: t }))]); }, [data, batcher]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }); }, [msgs, waiting]);
  // U9: 10분이 다 되면 바로 넘기지 않고 안내 한 줄을 2초 보인 뒤 서버에 다시 묻는다
  const left = useCountdown(data ? data.remainingSec : null, () => { setClosing(true); window.setTimeout(refresh, 2000); });

  /** 응답 하나 처리. 계속 받아도 되면 true */
  const take = (r: ChatReply): boolean => {
    if (stopped.current) return false;
    if (r.session.phase !== 'chat') {
      stopped.current = true; sync(r.session); // 위기 감지·시간 종료 → 서버 단계에 맞는 화면으로
      // 떠난 뒤라 RequirePhase가 옮겨 주지 못한다. 위기면 직접 위기 화면으로(홈이 예전 상태로 남지 않게)
      const to = left_.current ? routeAfterLeftChat(r.session.phase) : null;
      if (to) navigate(to, { replace: true });
      return false;
    }
    if (!r.queued && r.reply) setMsgs((m) => [...m, { from: 'mentor', text: r.reply }]); // queued면 앞 요청이 답을 가져온다
    return true;
  };
  const sendBatch = async (texts: string[]) => {
    setBuffered(0); setWaiting((n) => n + 1); setSendError(null);
    inflight.current++; sends.current++;
    try { await followPending(await api.sendChat(id, texts), () => api.replyChat(id), take); }
    catch (e) { if (!stopped.current) setSendError((e as Error).message); }
    finally { inflight.current--; setWaiting((n) => n - 1); }
  };
  sendRef.current = sendBatch;
  // 화면을 떠날 때 모아 둔 말은 버리지 않고 먼저 보낸다(🔴 검사를 거치게, 명세 4.11 7). 이동은 막지 않고,
  // 요청은 화면이 사라진 뒤에도 끝까지 간다(위기면 sync로 세션이 바뀐다). 마감 뒤라 빈 답이 와도 정상
  useEffect(() => () => { left_.current = true; batcher.flush(); }, [batcher]);

  // 앱을 내렸다 올리거나 인터넷이 돌아오면 서버 대화·남은 시간을 다시 읽는다(겹치면 한 번만).
  // 서버에 나가 있는 요청이 있으면 그 응답이 답을 가져오니 건너뛰고, 위기·단계 바뀜·끝내는 중이면 읽지 않는다.
  const [resync] = useState(() => onceAtATime(async () => {
    if (stopped.current || inflight.current > 0) return;
    const before = sends.current;
    const c = await api.getChat(id).catch(() => null);
    // 읽는 사이에 새 묶음을 보냈으면 이 결과는 옛것이라 버린다(그 응답이 화면을 채운다)
    if (c && !stopped.current && sends.current === before) setData(c);
  }));
  useOnResume(() => { if (!endingRef.current) void resync(); });

  const send = (raw: string) => {
    const v = raw.trim();
    if (!v || stopped.current || ending || closing) return;
    setMsgs((m) => [...m, { from: 'me', text: v }]);
    setText('');
    batcher.push(v);
    setBuffered(batcher.size());
  };
  const end = async () => {
    setEnding(true);
    try { const s = await api.endChat(id); setClosing(true); window.setTimeout(() => sync(s), 2000); } // U9: 같은 안내 뒤 다리 놓기로
    catch (e) { setSendError((e as Error).message); setEnding(false); }
  };
  const busy = waiting > 0 || buffered > 0 || ending || closing; // 「끝내기」는 보낼 말·답이 남아 있으면 막는다

  const actions = (
    <>
      {/* BRIEF: 입력창 위 오른쪽, 회색 테두리 '오늘 수다 끝내기' */}
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <button className="btn btn--secondary btn--small" disabled={busy} onClick={end}>오늘 수다 끝내기</button>
      </div>
      {/* 빠른 답은 첫마디를 돕는 것 — 대화를 불러온 뒤, 아직 아무 말도 없을 때만 */}
      {data && msgs.length === 0 && <div className="chip-row chip-row--scroll">{SUGGEST.map((s) => <button key={s} className="chip" disabled={ending || closing} onClick={() => send(s)}>{s}</button>)}</div>}
      {/* 입력창 옆 + 버튼 금지 (BRIEF 공통 디자인) */}
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input id="chat-input" className="input" aria-label="메시지 입력" placeholder="메시지 입력" maxLength={200} value={text} onChange={(e) => setText(e.target.value)} />
        <button className="btn btn--primary" disabled={!text.trim() || ending || closing} aria-label="보내기"><Icon name="send" size={20} /></button>
      </form>
    </>
  );

  return (
    <Frame title="수다" back="/student" right={<span className={'pill num ' + (data && left <= 60 ? 'pill--accent' : 'pill--mint')} aria-label={`남은 시간 ${mmss(left)}`}><Icon name="clock" size={14} /> {mmss(left)}</span>} actions={actions}>
      <LoadError error={error} onRetry={reload} />
      <div className="chat-log" role="log" aria-live="polite">
        {/* TK-74 #8: 서버는 첫 인사 없이 빈 대화로 시작한다 → 화면에만 보이는 첫 인사(서버로 보내지 않음).
            11-14: 대화를 불러오는 동안·말을 시작한 뒤에도 맨 위에 남긴다(배포본에서 인사 없이 칩만 보이던 것) */}
        {(
          <div className="mentor"><Mascot mood="wave" size={40} /><div className="bubble">{say('수다 시간이야! 오늘 하루 어땠어? 아무 얘기나 해도 돼.', '수다 시간이에요! 오늘 하루 어땠어요? 아무 얘기나 해도 돼요.')}</div></div>
        )}
        {msgs.map((m, i) => m.from === 'mentor' ? (
          <div key={i} className="mentor"><Mascot mood="wave" size={40} /><div className="bubble">{m.text}</div></div>
        ) : (
          <div key={i} className="bubble bubble--me">{m.text}</div>
        ))}
        {!data && !error && <Thinking label="불러오는 중" />}
        {/* U8: 묶어 보내기 1.5초 동안 「듣고 있어」, 서버를 기다리는 동안 「생각 중」 */}
        {waiting > 0 ? <Thinking /> : buffered > 0 ? <Thinking label={say('듣고 있어', '듣고 있어요')} /> : null}
        {/* U9: 1분 남았을 때·끝났을 때 화면 안내(멘토 말풍선이 아님 — AI 말처럼 꾸미지 않는다) */}
        {data && !closing && left > 0 && left <= 60 && <p className="small muted" role="status" style={{ textAlign: 'center' }}>{say('1분 남았어', '1분 남았어요')}</p>}
        {closing && <div className="notice notice--plain" role="status">{say('수다 시간이 끝났어. 마무리하러 가자!', '수다 시간이 끝났어요. 마무리하러 가요!')}</div>}
        <div ref={bottom} />
      </div>
      <LoadError error={sendError} />
    </Frame>
  );
}
