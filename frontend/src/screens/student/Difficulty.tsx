// 학생 — 난이도 고르기 (11-09 결정: 범위는 학습지도자, 난이도 3단계는 학생이 고른다)
import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { MentorSays } from '../../components/Mascot';
import { LoadError } from '../../components/Common';
import { useMentor } from '../../state/mentor';
import { routeFor, useSession } from '../../state/session';
import type { Difficulty } from '../../types';

const LEVELS: { d: Difficulty; sub: string; h: number }[] = [
  { d: '초급', sub: '천천히', h: 96 },
  { d: '중급', sub: '차근차근', h: 128 },
  { d: '고급', sub: '도전해 봐', h: 160 },
];

export function StudentDifficulty() {
  const nav = useNavigate();
  const { say } = useMentor();
  const { session, sync } = useSession();
  const [pick, setPick] = useState<Difficulty>('중급');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (session) return <Navigate to={routeFor(session)} replace />; // 하루 1회: 이미 시작했으면 그 단계로

  const start = async () => {
    setBusy(true); setError(null);
    try { sync(await api.startSession(pick)); nav('/student/solve'); }
    catch (e) { setError((e as Error).message); setBusy(false); }
  };

  return (
    <Frame title="난이도 고르기" back="/student" tabs="student"
      actions={<button className="btn btn--primary" disabled={busy} onClick={start}>이 난이도로 시작</button>}>
      <MentorSays mood="think" size={64} text={say('오늘 컨디션에 맞게\n골라 봐', '오늘 컨디션에 맞게\n골라 보세요')} />
      <div className="spacer" />
      {/* 계단형 카드: 아래 기준선은 같고 높이만 다르다 */}
      <div className="stairs" role="radiogroup" aria-label="난이도">
        {LEVELS.map((l) => (
          <button key={l.d} role="radio" aria-checked={pick === l.d} className={'card stair' + (pick === l.d ? ' card--selected' : '')} style={{ height: l.h }} onClick={() => setPick(l.d)}>
            <strong>{l.d}</strong><span className="small muted">{l.sub}</span>
          </button>
        ))}
      </div>
      <LoadError error={error} />
    </Frame>
  );
}
