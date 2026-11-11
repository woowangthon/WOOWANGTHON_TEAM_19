// 학생 ② 같이 풀기 (+ 다시 도전 · 풀이 같이 보기)
// 화면은 입력과 표시만 한다. 정답 판정·힌트 순서·20분 마감은 전부 서버(api)가 정한다.
// 흐름: 답 확인 → 맞으면 "계속" / 틀리면 다음 힌트가 자동으로 나오고 "다시 해 보기"
//       힌트 3개를 다 쓰고도 틀리면 「풀이 같이 보기」가 열린다 (답부터 주지 않는다)
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { MentorSays } from '../../components/Mascot';
import { FractionView } from '../../components/Fraction';
import { Keypad } from '../../components/Keypad';
import { LoadError, Thinking } from '../../components/Common';
import { useCountdown } from '../../lib/useCountdown';
import { useMentor } from '../../state/mentor';
import { RequirePhase, useSession } from '../../state/session';
import type { AnswerResult, ProblemView, Solution } from '../../types';

type Field = 'num' | 'den';

export function StudentSolve() {
  return <RequirePhase phase="solve"><Solve /></RequirePhase>;
}

function Solve() {
  const nav = useNavigate();
  const { say } = useMentor();
  const { session, sync, refresh } = useSession();
  const id = session!.id;
  const [p, setP] = useState<ProblemView | null>(null);
  const [num, setNum] = useState('');
  const [den, setDen] = useState('');
  const [field, setField] = useState<Field>('num');
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [solution, setSolution] = useState<Solution | null>(null);
  const [busy, setBusy] = useState<false | 'load' | 'answer' | 'hint'>('load');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy('load'); setError(null);
    try {
      const next = await api.getProblem(id);
      if (!next) { await refresh(); return; } // 풀기 단계가 끝남(다 풀었거나 시간 끝) → 서버 단계에 맞는 화면으로
      setP(next); setNum(''); setDen(''); setField('num'); setResult(null); setSolution(null);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }, [id, refresh]);
  useEffect(() => { load(); }, [load]);
  const left = useCountdown(p ? p.remainingSec : null, refresh);

  const act = async (kind: 'answer' | 'hint', fn: () => Promise<void>) => {
    setBusy(kind); setError(null);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const type = (d: number) => (field === 'num' ? setNum : setDen)((v) => (v.length >= 2 ? v : v + d));
  const del = () => (field === 'num' ? setNum : setDen)((v) => v.slice(0, -1));

  const check = () => p && act('answer', async () => {
    const r = await api.submitAnswer(id, p.id, Number(num), Number(den));
    if (!r.correct && !r.message) { await refresh(); return; } // 그사이 시간이 끝난 경우
    setResult(r);
    if (!r.correct) setP({ ...p, hints: r.autoHint ? [...p.hints, r.autoHint] : p.hints, hintsLeft: r.hintsLeft, canShowSolution: r.canShowSolution });
  });
  const askHint = () => p && act('hint', async () => {
    const h = await api.requestHint(id, p.id);
    setP({ ...p, hints: h.hints, hintsLeft: h.hintsLeft });
  });
  const showSolution = () => p && act('hint', async () => { setSolution(await api.showSolution(id, p.id)); });
  const retry = () => {
    if (!result) return;
    if (!result.numeratorOk) setNum('');
    if (!result.denominatorOk) setDen('');
    setField(!result.numeratorOk ? 'num' : 'den');
    setResult(null);
  };
  /** 정답 또는 풀이를 본 뒤: 서버가 이미 다음 단계로 넘겨 둔 세션에 맞춘다 */
  const next = () => {
    const s = solution?.session ?? result?.session;
    if (!s) return;
    sync(s);
    if (s.phase === 'solve') load();
  };

  const wrong = !!result && !result.correct;
  const boxClass = (f: Field) => {
    if (result) return 'answer-box ' + ((f === 'num' ? result.numeratorOk : result.denominatorOk) ? 'answer-box--ok' : 'answer-box--retry');
    return 'answer-box' + (field === f && !solution ? ' answer-box--focus' : '');
  };
  const lastHint = p && p.hints.length > 0 ? p.hints[p.hints.length - 1] : null;
  const isLast = !!p && p.index + 1 >= p.total;

  const header = (
    <header className="lessonbar">
      <button className="icon-btn" aria-label="나가기(이어서 할 수 있어요)" onClick={() => nav('/student')}><Icon name="close" /></button>
      <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={p?.total ?? 5} aria-valuenow={p?.index ?? 0}>
        <div className="progress__fill" style={{ width: p ? `${((p.index + (result?.correct || solution ? 1 : 0)) / p.total) * 100}%` : '0%' }} />
      </div>
      <span className="pill num"><Icon name="clock" size={14} /> {Math.ceil(left / 60)}분</span>
    </header>
  );

  let actions: React.ReactNode = null;
  let tone: 'ok' | 'retry' | undefined;
  if (p && solution) {
    actions = <button className="btn btn--primary" onClick={next}>{isLast ? '끝내기' : '다음 문제'}</button>;
  } else if (p && result?.correct) {
    tone = 'ok';
    actions = <><div className="feedback__title">{result.message}</div><button className="btn btn--primary" onClick={next}>계속</button></>;
  } else if (p && wrong) {
    tone = 'retry';
    actions = (
      <>
        <div className="feedback__title">{result!.message}</div>
        <div className="btn-row">
          {p.canShowSolution && <button className="btn btn--secondary" disabled={!!busy} onClick={showSolution}>풀이 같이 보기</button>}
          <button className="btn btn--accent" onClick={retry}>다시 해 보기</button>
        </div>
      </>
    );
  } else if (p) {
    actions = (
      <>
        <div className="btn-row">
          <button className="btn btn--secondary" disabled={!!busy || p.hintsLeft === 0} onClick={askHint}>
            <Icon name="bulb" size={18} /> 힌트 {p.hintsLeft}개 남음
          </button>
          {/* 분자·분모를 다 넣기 전에는 누를 수 없다 */}
          <button className="btn btn--primary" disabled={!num || !den || !!busy} onClick={check}>답 확인</button>
        </div>
        <Keypad onDigit={type} onDelete={del} disabled={!!busy} />
      </>
    );
  }

  return (
    <Frame header={header} actions={actions} tone={tone}>
      {busy === 'load' && !p && <Thinking label="문제 불러오는 중" />}
      <LoadError error={error} onRetry={p ? undefined : load} />
      {p && (
        <>
          <div className="row between small">
            <strong className="num">{p.index + 1} / {p.total} 문제</strong>
            <span className="hint-dots" aria-label={`힌트 ${p.hints.length}개 사용`}>
              {[0, 1, 2].map((i) => <i key={i} className={i < p.hints.length ? 'on' : ''} />)}
            </span>
          </div>
          <section className="card problem">
            <div className="equation">
              <FractionView value={p.left} /> {p.op === '+' ? '+' : '−'} <FractionView value={p.right} /> ={' '}
              {solution ? '?' : (
                <span className="answer">
                  <button className={boxClass('num')} disabled={!!result} onClick={() => setField('num')} aria-label={`분자 입력${num ? ': ' + num : ''}`}>{num}</button>
                  <span className="answer__bar" />
                  <button className={boxClass('den')} disabled={!!result} onClick={() => setField('den')} aria-label={`분모 입력${den ? ': ' + den : ''}`}>{den}</button>
                </span>
              )}
            </div>
          </section>
          {solution ? (
            <>
              <MentorSays mood="calm" text={say('괜찮아, 같이 풀이를 보자', '괜찮아요, 같이 풀이를 봐요')} />
              <ol className="steps card card--flat">{solution.steps.map((s) => <li key={s}>{s}</li>)}</ol>
            </>
          ) : busy === 'answer' || busy === 'hint' ? (
            <Thinking />
          ) : result?.correct ? (
            <MentorSays mood="cheer" text={say('이 느낌 그대로 가자!', '이 느낌 그대로 가요!')} />
          ) : lastHint ? (
            <MentorSays mood={wrong ? 'calm' : 'think'} label={`힌트 ${p.hints.length}`} text={lastHint} />
          ) : wrong ? (
            <MentorSays mood="calm" text={say('표시된 칸만 다시 생각해 봐', '표시된 칸만 다시 생각해 보세요')} />
          ) : (
            <MentorSays mood="think" text={say('천천히 생각해 봐.\n막히면 힌트를 눌러', '천천히 생각해 보세요.\n막히면 힌트를 눌러요')} />
          )}
        </>
      )}
    </Frame>
  );
}
