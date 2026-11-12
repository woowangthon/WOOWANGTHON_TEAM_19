// 학생: 쉬는 시간 게임(11-13 임시 3개, 혼자 몇 분이면 끝나는 것). 쉬는 시간에만 열린다(BreakOnlyGate).
// 여럿이 하는 게임은 서버가 필요해 성호 님께 요청(노션). 점수·기록은 저장하지 않는다(재화·순위 경쟁 없음).
import { useEffect, useRef, useState } from 'react';
import { Frame } from '../../components/Frame';
import { Icon, type IconName } from '../../components/Icon';

type Game = 'pairs' | 'updown' | 'reaction';
const GAMES: { id: Game; name: string; desc: string; icon: IconName }[] = [
  { id: 'pairs', name: '짝 맞추기', desc: '같은 그림 두 장 찾기', icon: 'copy' },
  { id: 'updown', name: '업다운 숫자', desc: '1~50 숫자 맞히기', icon: 'bulb' },
  { id: 'reaction', name: '반응 속도', desc: '초록이 되면 바로 누르기', icon: 'flame' },
];

export function StudentGames() {
  const [game, setGame] = useState<Game | null>(null);
  const g = GAMES.find((x) => x.id === game);
  return (
    <Frame title={g ? g.name : '쉬는 시간 게임'} back="/student/classes" tabs="student"
      actions={g ? <button className="btn btn--ghost" onClick={() => setGame(null)}>다른 게임 고르기</button> : undefined}>
      {!g && (
        <div className="stack">
          <p className="small muted">쉬는 시간에만 열려. 몇 분이면 끝나!</p>
          {GAMES.map((x) => (
            <button key={x.id} className="card card--flat row between" style={{ textAlign: 'left', width: '100%' }} onClick={() => setGame(x.id)}>
              <span className="row"><Icon name={x.icon} size={22} /><span><strong>{x.name}</strong><span className="small muted" style={{ display: 'block' }}>{x.desc}</span></span></span>
              <Icon name="chevron" size={18} />
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
      <div className="row between"><span className="small muted">뒤집은 횟수 {tries}</span>{win && <strong>다 찾았어!</strong>}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {cards.map((f, i) => {
          const up = open.includes(i) || done.includes(i);
          return (
            <button key={i} className={'card card--flat' + (done.includes(i) ? ' card--warn' : '')} style={{ aspectRatio: '1', display: 'grid', placeItems: 'center', padding: 0 }}
              aria-label={up ? f : '뒤집힌 카드'} onClick={() => flip(i)}>
              {up ? <Icon name={f} size={28} /> : <span className="muted">?</span>}
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
  const [answer, setAnswer] = useState(() => 1 + Math.floor(Math.random() * 50));
  const [val, setVal] = useState('');
  const [log, setLog] = useState<string[]>([]);
  const [win, setWin] = useState(false);
  const guess = () => {
    const n = Number(val);
    if (!Number.isInteger(n) || n < 1 || n > 50) return;
    setLog((l) => [`${n} → ${n === answer ? '정답!' : n < answer ? '업 ↑' : '다운 ↓'}`, ...l]);
    if (n === answer) setWin(true);
    setVal('');
  };
  return (
    <div className="stack">
      <p className="small muted">1부터 50 사이 숫자를 맞혀 봐.</p>
      {!win ? (
        <div className="row">
          <input className="input" inputMode="numeric" value={val} onChange={(e) => setVal(e.target.value.replace(/\D/g, '').slice(0, 2))} onKeyDown={(e) => e.key === 'Enter' && guess()} aria-label="숫자" />
          <button className="btn btn--primary btn--small" onClick={guess}>확인</button>
        </div>
      ) : (
        <>
          <strong>{log.length}번 만에 맞혔어!</strong>
          <button className="btn btn--secondary" onClick={() => { setAnswer(1 + Math.floor(Math.random() * 50)); setLog([]); setWin(false); }}>한 번 더</button>
        </>
      )}
      <ul className="list" aria-live="polite">{log.map((l, i) => <li key={i} className="small">{l}</li>)}</ul>
    </div>
  );
}

/* ---------- 반응 속도 ---------- */
function Reaction() {
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
  const label = { idle: '눌러서 시작', wait: '기다려…', go: '지금!', early: '너무 빨랐어! 다시 눌러', result: `${ms}ms · 다시 하려면 눌러` }[phase];
  return (
    <div className="stack">
      <button className={'card' + (phase === 'go' ? ' card--warn' : '')} style={{ minHeight: 220, display: 'grid', placeItems: 'center', fontSize: 22, fontWeight: 800, width: '100%',
        background: phase === 'go' ? 'var(--color-primary)' : undefined, color: phase === 'go' ? '#fff' : undefined }} onClick={tap} aria-live="polite">{label}</button>
      {best !== null && <p className="small muted">가장 빠른 기록 {best}ms</p>}
    </div>
  );
}
