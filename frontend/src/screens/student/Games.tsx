// 학생: 쉬는 시간 게임(11-13 임시 3개, 혼자 몇 분이면 끝나는 것). 쉬는 시간에만 열린다(BreakOnlyGate).
// 여럿이 하는 게임은 서버가 필요해 성호 님께 요청(노션). 점수·기록은 저장하지 않는다(재화·순위 경쟁 없음).
import { useEffect, useRef, useState } from 'react';
import { Frame } from '../../components/Frame';
import { Icon, type IconName } from '../../components/Icon';
import { useMentor } from '../../state/mentor';

type Game = 'pairs' | 'updown' | 'reaction';
const GAMES: { id: Game; name: string; desc: string; icon: IconName }[] = [
  { id: 'pairs', name: '짝 맞추기', desc: '같은 그림 두 장 찾기', icon: 'copy' },
  { id: 'updown', name: '업다운 숫자', desc: '1~50 숫자 맞히기', icon: 'bulb' },
  { id: 'reaction', name: '반응 속도', desc: '초록이 되면 바로 누르기', icon: 'flame' },
];

export function StudentGames() {
  const { say } = useMentor();
  const [game, setGame] = useState<Game | null>(null);
  const g = GAMES.find((x) => x.id === game);
  return (
    <Frame title={g ? g.name : '쉬는 시간 게임'} back="/student/classes" tabs="student"
      actions={g ? <button className="btn btn--ghost" onClick={() => setGame(null)}>다른 게임 고르기</button> : undefined}>
      {!g && (
        <div className="game-list">
          <p className="small muted">{say('잠깐 쉬며 가볍게 놀아 볼까?', '잠깐 쉬며 가볍게 놀아 볼까요?')}</p>
          {GAMES.map((x) => (
            <button key={x.id} className="card card--flat game-choice" style={{ width: '100%' }} onClick={() => setGame(x.id)}>
              <Icon name={x.icon} size={28} />
              <span style={{ flex: 1 }}><strong>{x.name}</strong><small className="muted">{x.desc}</small></span>
              <Icon name="chevron" size={20} />
            </button>
          ))}
        </div>
      )}
      {game === 'pairs' && <Pairs />}
      {game === 'updown' && <UpDown />}
      {game === 'reaction' && <Reaction />}
    </Frame>
  );
}

/* ---------- 짝 맞추기: 4쌍 8장 ---------- */
const FACES: IconName[] = ['seed', 'book', 'cup', 'stamp'];
const shuffle = <T,>(a: T[]) => { const b = [...a]; for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [b[i], b[j]] = [b[j], b[i]]; } return b; };
function Pairs() {
  const { say } = useMentor();
  const [cards, setCards] = useState(() => shuffle([...FACES, ...FACES]));
  const [open, setOpen] = useState<number[]>([]);
  const [done, setDone] = useState<number[]>([]);
  const [tries, setTries] = useState(0);
  useEffect(() => {
    if (open.length !== 2) return;
    const [a, b] = open;
    const t = setTimeout(() => { if (cards[a] === cards[b]) setDone((d) => [...d, a, b]); setOpen([]); }, 600);
    return () => clearTimeout(t);
  }, [open, cards]);
  const flip = (i: number) => { if (open.length < 2 && !open.includes(i) && !done.includes(i)) { if (open.length === 1) setTries((n) => n + 1); setOpen([...open, i]); } };
  const win = done.length === cards.length;
  return (
    <div className="stack">
      <div className="row between"><span className="small muted">{say('같은 그림 두 개를 찾아봐.', '같은 그림 두 개를 찾아보세요.')} · 뒤집은 횟수 {tries}</span>{win && <strong>{say('다 찾았어!', '다 찾았어요!')}</strong>}</div>
      <div className="pairs-grid">
        {cards.map((f, i) => {
          const up = open.includes(i) || done.includes(i);
          return (
            <button key={i} className={'pairs-card' + (done.includes(i) ? ' pairs-card--done' : open.includes(i) ? ' pairs-card--open' : '')}
              aria-label={done.includes(i) ? `${f} 맞춤` : up ? f : '뒤집힌 카드'} onClick={() => flip(i)}>
              {up ? <span style={{ display: 'grid', justifyItems: 'center', gap: 2 }}><Icon name={f} size={28} />{done.includes(i) && <span className="pairs-card__done">맞춤</span>}</span> : <span className="muted">?</span>}
            </button>
          );
        })}
      </div>
      {win && <button className="btn btn--secondary" onClick={() => { setCards(shuffle([...FACES, ...FACES])); setDone([]); setTries(0); }}>한 번 더</button>}
    </div>
  );
}

/* ---------- 업다운 숫자 ---------- */
function UpDown() {
  const { say } = useMentor();
  const [answer, setAnswer] = useState(() => 1 + Math.floor(Math.random() * 50));
  const [val, setVal] = useState('');
  const [log, setLog] = useState<string[]>([]);
  const [win, setWin] = useState(false);
  const guess = () => {
    const n = Number(val);
    if (!Number.isInteger(n) || n < 1 || n > 50) return;
    setLog((l) => [`${n} → ${n === answer ? '정답!' : n < answer ? `업 ↑ · ${say('더 큰 수야', '더 큰 수예요')}` : `다운 ↓ · ${say('더 작은 수야', '더 작은 수예요')}`}`, ...l]);
    if (n === answer) setWin(true);
    setVal('');
  };
  return (
    <div className="stack">
      <p className="small muted">{say('1부터 50 사이 숫자를 찾아봐.', '1부터 50 사이 숫자를 찾아보세요.')}</p>
      {!win ? (
        <div className="guess-form">
          <input className="input" inputMode="numeric" value={val} onChange={(e) => setVal(e.target.value.replace(/\D/g, '').slice(0, 2))} onKeyDown={(e) => e.key === 'Enter' && guess()} aria-label="숫자" />
          <button className="btn btn--primary btn--small" onClick={guess}>확인</button>
        </div>
      ) : (
        <>
          <strong>{log.length}번 만에 맞혔어!</strong>
          <button className="btn btn--secondary" onClick={() => { setAnswer(1 + Math.floor(Math.random() * 50)); setLog([]); setWin(false); }}>한 번 더</button>
        </>
      )}
      {log.length > 0 && <ul className="guess-log card card--flat" aria-live="polite">{log.map((l, i) => <li key={i} className="small">{l}</li>)}</ul>}
    </div>
  );
}

/* ---------- 반응 속도 ---------- */
function Reaction() {
  const { say } = useMentor();
  const [phase, setPhase] = useState<'idle' | 'wait' | 'go' | 'early' | 'result'>('idle');
  const [ms, setMs] = useState(0);
  const [best, setBest] = useState<number | null>(null);
  const goAt = useRef(0);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const start = () => {
    setPhase('wait');
    timer.current = window.setTimeout(() => { goAt.current = performance.now(); setPhase('go'); }, 1500 + Math.random() * 2500);
  };
  const tap = () => {
    if (phase === 'idle' || phase === 'result' || phase === 'early') return start();
    if (phase === 'wait') { window.clearTimeout(timer.current); return setPhase('early'); }
    const t = Math.round(performance.now() - goAt.current);
    setMs(t); setBest((b) => (b === null || t < b ? t : b)); setPhase('result');
  };
  const label = { idle: '눌러서 시작', wait: say('기다려…', '기다려 주세요…'), go: '지금!', early: say('너무 빨랐어! 다시 눌러', '너무 빨랐어요! 다시 눌러 주세요'), result: `${ms}ms · ${say('다시 하려면 눌러', '다시 하려면 눌러 주세요')}` }[phase];
  const icon: IconName = phase === 'result' ? 'check' : phase === 'early' ? 'refresh' : 'clock';
  return (
    <div className="stack">
      <button className={'reaction-pad' + (phase === 'go' ? ' reaction-pad--go' : phase === 'early' ? ' reaction-pad--early' : '')} onClick={tap} aria-live="polite">
        <Icon name={icon} size={32} /><span>{label}</span>
      </button>
      {best !== null && <p className="small muted">가장 빠른 기록 {best}ms</p>}
    </div>
  );
}
