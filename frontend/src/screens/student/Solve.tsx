// 학생 ② 같이 풀기 (+ 다시 도전 · 풀이 같이 보기)
// 화면은 입력과 표시만 한다. 정답 판정·힌트 순서·20분 마감은 전부 서버(api)가 정한다.
// 흐름: 답 확인 → 맞으면 "계속" / 틀리면 다음 힌트가 자동으로 나오고 "다시 해 보기"
//       힌트 3개를 다 쓰고도 틀리면 「풀이 같이 보기」가 열린다 (답부터 주지 않는다)
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { MentorSays } from '../../components/Mascot';
import { FractionView } from '../../components/Fraction';
import { Keypad } from '../../components/Keypad';
import { LoadError, Thinking } from '../../components/Common';
import { useCountdown } from '../../lib/useCountdown';
import { isSolveTimeUp } from '../../lib/kidScreens';
import { useMentor } from '../../state/mentor';
import { RequirePhase, useSession } from '../../state/session';
import type { AnswerResult, ProblemView, Solution } from '../../types';

type Field = 'num' | 'den';
const CIRCLED = ['①', '②', '③', '④'];
const NUMBER_MAX = 12; // 숫자 한 칸: 큰 수(억 단위)까지

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
  const [ans, setAns] = useState(''); // 분수 밖 답 칸(숫자 한 칸·보기 기호·낱말)
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
      setP(next); setNum(''); setDen(''); setAns(''); setField('num'); setResult(null); setSolution(null);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }, [id, refresh]);
  useEffect(() => { load(); }, [load]);
  // 20분이 0이 되면 서버에 다시 묻되(refresh), 서버에 풀기 마감이 없어 단계가 안 바뀌므로 화면이 선택지를 보여 준다.
  // 20분 뒤에는 서버가 「풀이 보기」·「수다로 넘어가기」를 힌트 수와 무관하게 허용한다(명세 4.11 4) → 두 버튼 모두 성공 경로
  const [zero, setZero] = useState(false);
  const left = useCountdown(p ? p.remainingSec : null, () => { setZero(true); refresh(); });

  const act = async (kind: 'answer' | 'hint', fn: () => Promise<void>) => {
    setBusy(kind); setError(null);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const kind = p?.answerKind ?? 'fraction';
  const type = (d: number) => kind === 'number'
    ? setAns((v) => (v.length >= NUMBER_MAX || (v === '' && d === 0) ? v : v + d))
    : (field === 'num' ? setNum : setDen)((v) => (v.length >= 2 ? v : v + d));
  const del = () => (kind === 'number' ? setAns : field === 'num' ? setNum : setDen)((v) => v.slice(0, -1));
  const ready = kind === 'fraction' ? !!num && !!den : ans.trim() !== '';
  const lang = kind === 'text' ? p?.answerLang ?? null : null;
  // 영어 낱말 문제에 한글(또는 그 반대)을 쓰면 채점하지 않고 다시 쓰게 한다
  const wrongScript = !!lang && (lang === 'en' ? /[ㄱ-ㅎㅏ-ㅣ가-힣]/ : /[A-Za-z]/).test(ans);

  const check = () => p && !wrongScript && act('answer', async () => {
    const r = kind === 'fraction'
      ? await api.submitAnswer(id, p.id, Number(num), Number(den))
      : await api.submitAnswer(id, p.id, 0, 0, ans.trim());
    if (r.queued) { // 서버가 앞 답을 만드는 중: 화면을 넘기지 않고 「생각 중」으로 기다렸다가 서버 상태로 다시 읽는다
      await new Promise((ok) => setTimeout(ok, 1500));
      await load(); return;
    }
    if (!r.correct && !r.message) { await refresh(); return; } // 그사이 시간이 끝난 경우
    setResult(r);
    if (!r.correct) setP({ ...p, hints: r.autoHint ? [...p.hints, r.autoHint] : p.hints, hintsLeft: r.hintsLeft, canShowSolution: r.canShowSolution });
  });
  const askHint = () => p && act('hint', async () => {
    const h = await api.requestHint(id, p.id);
    setP({ ...p, hints: h.hints, hintsLeft: h.hintsLeft });
  });
  const showSolution = () => p && act('hint', async () => { setSolution(await api.showSolution(id, p.id)); });
  /** 시간이 끝났을 때 「수다로 갈까?」: 학습 완료 화면의 「수다 할래」와 같은 경로 */
  const toChat = () => act('hint', async () => { sync(await api.afterStudy(id, 'chat')); });
  const retry = () => {
    if (!result) return;
    if (kind !== 'fraction') { setAns(''); setResult(null); return; }
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
  const timeUp = isSolveTimeUp(zero ? 0 : (p?.remainingSec ?? 1), !!p, !!solution || !!result?.correct);
  // 짧은 폰(높이 ~667 이하)에서는 새 힌트·채점 말풍선이 숫자판 뒤에 숨는다 → 새 말이 나오면 맨 아래로 (Chat과 같은 방식)
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }); }, [lastHint, result, solution, timeUp, busy]);

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
  if (p && timeUp) {
    actions = (
      <div className="btn-row">
        <button className="btn btn--secondary" disabled={!!busy} onClick={showSolution}>풀이 같이 보기</button>
        <button className="btn btn--primary" disabled={!!busy} onClick={toChat}>수다로 갈까?</button>
      </div>
    );
  } else if (p && solution) {
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
    // GPT-008: 키패드를 먼저, 힌트·답 확인을 맨 아래(엄지 영역)에 둔다 — 320×568에서 문제 카드와 겹치지 않게
    actions = (
      <>
        {(kind === 'fraction' || kind === 'number') && <Keypad onDigit={type} onDelete={del} disabled={!!busy} />}
        <div className="btn-row">
          <button className="btn btn--secondary" disabled={!!busy || p.hintsLeft === 0} onClick={askHint}>
            <Icon name="bulb" size={18} /> 힌트 {p.hintsLeft}개 남음
          </button>
          {/* 분자·분모를 다 넣기 전에는 누를 수 없다 */}
          <button className="btn btn--primary" disabled={!ready || wrongScript || !!busy} onClick={check}>답 확인</button>
        </div>
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
              {/* 점 개수 = 받은 힌트 + 남은 힌트(서버가 정함) */}
              {Array.from({ length: p.hints.length + p.hintsLeft }, (_, i) => <i key={i} className={i < p.hints.length ? 'on' : ''} />)}
            </span>
          </div>
          <section className="card problem">
            {p.text && <p style={{ whiteSpace: 'pre-line' }}>{p.text}</p>}
            {kind === 'number' && !solution && (
              <button className={'answer-box' + (result ? (result.correct ? ' answer-box--ok' : ' answer-box--retry') : ' answer-box--focus')}
                style={{ width: 'auto', minWidth: 160, padding: '0 14px' }} disabled={!!result} aria-label={`답 입력${ans ? ': ' + ans : ''}`}>{ans}</button>
            )}
            {kind === 'choice' && p.choices && ( /* 풀이를 볼 때도 보기를 남겨 둔다(풀이가 ①~④를 가리킨다) */
              <div role="radiogroup" aria-label="보기" style={{ display: 'grid', gap: 8, width: '100%' }}>
                {p.choices.map((c, i) => (
                  <button key={c} role="radio" aria-checked={ans === CIRCLED[i]} disabled={!!result || !!busy || !!solution}
                    className={'btn ' + (ans === CIRCLED[i] ? (result && !result.correct ? 'btn--accent' : 'btn--primary') : 'btn--secondary')}
                    style={{ justifyContent: 'flex-start', textAlign: 'left' }} onClick={() => setAns(CIRCLED[i])}>
                    {CIRCLED[i]} {c}
                  </button>
                ))}
              </div>
            )}
            {(kind === 'text' || (kind === 'choice' && !p.choices)) && !solution && (
              <input className="input" value={ans} maxLength={20} disabled={!!result || !!busy}
                autoComplete="off" autoCapitalize="none" spellCheck={false} enterKeyHint="done"
                lang={lang ?? undefined}
                placeholder={kind === 'choice' ? say('번호를 써 줘 (예: 2)', '번호를 써 주세요 (예: 2)')
                  : lang === 'en' ? say('영어 낱말로 써 줘', '영어 낱말로 써 주세요')
                  : lang === 'ko' ? say('한글 낱말로 써 줘', '한글 낱말로 써 주세요')
                  : say('답을 낱말로 써 줘', '답을 낱말로 써 주세요')}
                aria-label="답 입력" onChange={(e) => setAns(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && ans.trim() && !busy && !result) check(); }} />
            )}
            {wrongScript && !result && (
              <p className="small" role="alert">{lang === 'en' ? say('영어로 써 줘', '영어로 써 주세요') : say('한글로 써 줘', '한글로 써 주세요')}</p>
            )}
            {kind === 'fraction' && <div className="equation">
              {/* 기호는 서버가 준 op 그대로. 식을 두 분수로 나눌 수 없는 문제(left·right가 null)는 식을 생략하고 답 칸만 */}
              {p.left && p.right && <><FractionView value={p.left} /> {p.op === '-' ? '−' : p.op} <FractionView value={p.right} /> ={' '}</>}
              {solution ? '?' : (
                <span className="answer">
                  <button className={boxClass('num')} disabled={!!result} onClick={() => setField('num')} aria-label={`분자 입력${num ? ': ' + num : ''}`}>{num}</button>
                  <span className="answer__bar" />
                  <button className={boxClass('den')} disabled={!!result} onClick={() => setField('den')} aria-label={`분모 입력${den ? ': ' + den : ''}`}>{den}</button>
                </span>
              )}
            </div>}
            {!solution && kind === 'fraction' && <p className="small muted">{say('답이 자연수면 분모에 1을 넣어 (3 → 3/1)', '답이 자연수면 분모에 1을 넣어요 (3 → 3/1)')}</p>}
          </section>
          {solution ? (
            <>
              <MentorSays mood="calm" text={say('괜찮아, 같이 풀이를 보자', '괜찮아요, 같이 풀이를 봐요')} />
              <ol className="steps card card--flat">{solution.steps.map((s) => <li key={s}>{s}</li>)}</ol>
            </>
          ) : busy === 'answer' || busy === 'hint' ? (
            <Thinking />
          ) : timeUp ? (
            <MentorSays mood="calm" text={say('20분이 다 됐어.\n풀이를 같이 볼까, 수다로 갈까?', '20분이 다 됐어요.\n풀이를 같이 볼까요, 수다로 갈까요?')} />
          ) : result?.correct ? (
            <MentorSays mood="cheer" text={say('이 느낌 그대로 가자!', '이 느낌 그대로 가요!')} />
          ) : lastHint ? (
            <MentorSays mood={wrong ? 'calm' : 'think'} label={`힌트 ${p.hints.length}`} text={lastHint} />
          ) : wrong ? (
            <MentorSays mood="calm" text={kind === 'fraction' ? say('표시된 칸만 다시 생각해 봐', '표시된 칸만 다시 생각해 보세요') : say('다시 한번 생각해 봐', '다시 한번 생각해 보세요')} />
          ) : (
            <MentorSays mood="think" text={say('천천히 생각해 봐.\n막히면 힌트를 눌러', '천천히 생각해 보세요.\n막히면 힌트를 눌러요')} />
          )}
          <div ref={bottom} />
        </>
      )}
    </Frame>
  );
}
