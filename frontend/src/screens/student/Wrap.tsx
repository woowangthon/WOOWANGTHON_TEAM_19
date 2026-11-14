// 학생 ⑤ 마무리 — 오늘 요약 + 보호자께 보낼 한 줄(미리보기) + 어려웠던 점 + 보호자께 낼 퀴즈
// 요약 숫자와 칩은 서버가 오늘 기록에서 만든다(지어내지 않는다).
import { useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { MentorSays, Mascot } from '../../components/Mascot';
import { LoadError, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useMentor } from '../../state/mentor';
import { RequirePhase, useSession } from '../../state/session';

const CUSTOM = '직접 쓸래';

export function StudentWrap() {
  return <RequirePhase phase="wrap"><Wrap /></RequirePhase>;
}

function Wrap() {
  const { say } = useMentor();
  const { session, sync } = useSession();
  const id = session!.id;
  const { data, error, reload } = useAsync(() => api.getWrap(id), [id]);
  const [hard, setHard] = useState<string | null>(null);
  const [custom, setCustom] = useState('');
  const [quiz, setQuiz] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const send = async () => {
    setBusy(true); setSendError(null);
    try { sync(await api.submitWrap(id, { hardPoint: hard === CUSTOM ? custom.trim() || null : hard, quiz })); } // done → 오늘 화면으로
    catch (e) { setSendError((e as Error).message); setBusy(false); }
  };

  return (
    <Frame title="마무리" actions={<button className="btn btn--primary" disabled={!data || busy} onClick={send}>보내고 끝내기</button>}>
      {!data && !error && <Thinking />}
      <LoadError error={error} onRetry={reload} />
      {data && (
        <>
          <MentorSays mood="read" size={64} text={say('오늘도 해냈어', '오늘도 해냈어요')} />
          <section className="card">
            <h2 className="h3">오늘 푼 것</h2>
            <dl className="kv" style={{ marginTop: 8 }}>
              <dt>단원</dt><dd>{data.unit}</dd>
              <dt>문제</dt><dd className="num">{data.solved}/{data.total}문제</dd>{/* B16: 난이도는 서버가 고른 값을 저장하지 않아 늘 「중급」 → 표시하지 않음 */}
              <dt>시간</dt><dd className="num">학습 {data.studyMin}분{data.chatMin > 0 ? ` · 수다 ${data.chatMin}분` : ''}</dd>
              <dt>연속</dt><dd className="num">{data.streakDays}일</dd>
            </dl>
          </section>
          <section className="stack">
            <div className="row between"><h2 className="h3">보호자께 보낼 한 줄</h2><span className="pill pill--mint">미리보기</span></div>
            <div className="mentor"><Mascot mood="wave" size={40} /><div className="bubble">{data.aiLine}</div></div>
            <p className="small muted">{say('수다 내용은 보내지 않아.', '수다 내용은 보내지 않아요.')}</p>
          </section>
          {data.hardChips.length > 0 && <section className="stack">
            <h2 className="h3">오늘 어려웠던 건? <span className="small muted">(선택)</span></h2>
            <div className="chip-row">
              {data.hardChips.map((c) => (
                <button key={c} className={'chip' + (hard === c ? ' chip--on' : '')} aria-pressed={hard === c} onClick={() => setHard(hard === c ? null : c)}>{c}</button>
              ))}
            </div>
            {hard === CUSTOM && <input id="wrap-custom" className="input" aria-label="어려웠던 점 직접 쓰기" maxLength={30} placeholder="한 줄로 써 줘 (30자까지)" value={custom} onChange={(e) => setCustom(e.target.value)} />}
          </section>}{/* 서버는 어려웠던 점 칩을 빈 목록으로 준다 → 비면 섹션을 숨긴다 */}
          <section className="stack">
            <h2 className="h3">보호자께 낼 퀴즈 하나 <span className="small muted">(선택)</span></h2>
            {/* GPT-001: 긴 퀴즈 문장도 화면 안에서 줄바꿈 */}
            <div className="chip-row quiz-chips">
              {data.quizOptions.map((q) => (
                <button key={q} className={'chip' + (quiz === q ? ' chip--on' : '')} aria-pressed={quiz === q} onClick={() => setQuiz(quiz === q ? null : q)}>{q}</button>
              ))}
            </div>
          </section>
          <LoadError error={sendError} />
        </>
      )}
    </Frame>
  );
}
