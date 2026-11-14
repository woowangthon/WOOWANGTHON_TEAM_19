// 학생 ③ 학습 완료(전환) — 연속 +1은 이 순간에 이미 서버에 기록됐다. 수다는 선택.
import { useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { Mascot } from '../../components/Mascot';
import { LoadError, Stat } from '../../components/Common';
import { useMentor } from '../../state/mentor';
import { RequirePhase, useSession } from '../../state/session';
import { useAsync } from '../../lib/useAsync';

export function StudentDone() {
  return <RequirePhase phase="transition"><Done /></RequirePhase>;
}

function Done() {
  const { say } = useMentor();
  const { session, sync } = useSession();
  const s = session!;
  const [busy, setBusy] = useState(false);
  const home = useAsync(() => api.getStudentHome()); // 오늘 학습 완료로 받은 씨앗
  const restricted = !!home.data?.restricted;
  const [error, setError] = useState<string | null>(null);
  const choose = async (choice: 'chat' | 'skip') => {
    setBusy(true); setError(null);
    try { sync(await api.afterStudy(s.id, choice)); } // 단계가 바뀌면 RequirePhase가 맞는 화면으로 보낸다
    catch (e) { setError((e as Error).message); setBusy(false); }
  };
  return (
    <Frame title="학습 완료" actions={<>
      <button className="btn btn--primary" disabled={busy || restricted} onClick={() => choose('chat')}>{restricted ? '수다는 보호자 연결 후에' : '수다 할래'}</button>
      <button className="btn btn--secondary" disabled={busy} onClick={() => choose('skip')}>오늘은 끝</button>
    </>}>
      <section className="celebrate">
        <Mascot mood="cheer" size={132} />
        <span className="pill pill--accent" style={{ fontSize: 16, padding: '6px 16px' }}><Icon name="flame" size={18} fill /> 연속 {s.streakDays}일!</span>
        <h1 className="h2">{s.timedOut
          ? say('시간이 다 됐어. 오늘은 여기까지!', '시간이 다 됐어요. 오늘은 여기까지!')
          : say(`${s.streakDays}일째 같이 했어`, `${s.streakDays}일째 같이 했어요`)}</h1>
      </section>
      <div className="stats">
        <Stat label="끝낸 문제" value={`${s.solved}/${s.total}`} />
        <Stat label="공부한 시간" value={`${s.studyMin}분`} />
        <Stat label="본 힌트" value={`${s.hintsUsed}번`} />
      </div>
      <div className="row" style={{ justifyContent: 'center' }} aria-label={`${s.total}문제 중 ${s.solved}문제 완료`}>
        {Array.from({ length: s.total }, (_, i) => (
          <span key={i} className={'tick' + (i < s.solved ? '' : ' tick--no')}><Icon name="check" size={14} /></span>
        ))}
      </div>
      {/* GPT-054: 서버가 준 「오늘 받은 씨앗」을 보여 주기만 한다(화면에 들어올 때 지급하지 않음) */}
      {!!home.data?.earnedToday && (
        <div className="reward-feedback" role="status" aria-live="polite">
          <Icon name="seed" size={24} />
          <span className="reward-feedback__copy">
            <strong>{say(`씨앗 ${home.data.earnedToday}개를 받았어`, `씨앗 ${home.data.earnedToday}개를 받았어요`)}</strong>
            <small>학원 하루 학습 완료 · 학원 상품에 써요</small>
          </span>
        </div>
      )}
      {s.assisted > 0 && <p className="small muted" style={{ textAlign: 'center' }}>{s.assisted}문제는 풀이를 같이 봤어요</p>}
      <LoadError error={error} />
    </Frame>
  );
}
