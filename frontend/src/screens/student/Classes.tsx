// 학생: 강의실 — 초대 받은 강의실은 수락, 다른 강의실은 참여 요청
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { LoadError, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import { useMentor } from '../../state/mentor';
import { StudentSessionCard } from '../../components/ClassSession';
import { StudentBoard } from '../../components/ClassBoard';

export function StudentClasses() {
  const { say } = useMentor();
  const { data, setData, error, loading, reload } = useAsync(() => api.getStudentClasses());
  const { run, busy, error: actErr } = useAction();
  return (
    <Frame title="강의실" exit tabs="student">
      {loading && !data && <Thinking label="불러오는 중" />}
      <LoadError error={error ?? actErr} onRetry={reload} />
      {data && (
        <>
          {data.invites.length > 0 && <h2 className="h3">초대 받았어</h2>}
          {data.invites.map((c) => (
            <section key={c.id} className="card card--warn row between">
              <span><strong>{c.name}</strong><span className="small muted" style={{ display: 'block' }}>{c.teacherName}</span></span>
              <span className="row">
                <button className="btn btn--ghost btn--small" disabled={busy} onClick={() => run(async () => setData(await api.acceptInvite(c.id, false)))}>나중에</button>
                <button className="btn btn--primary btn--small" disabled={busy} onClick={() => run(async () => setData(await api.acceptInvite(c.id, true)))}>들어갈래</button>
              </span>
            </section>
          ))}
          <h2 className="h3">내 강의실</h2>
          {data.joined.length === 0 && <div className="notice notice--plain"><span>{say('아직 들어간 강의실이 없어', '아직 들어간 강의실이 없어요')}</span></div>}
          {data.joined.map((c) => (
            <div key={c.id} className="card card--flat stack">
              <div className="row between"><strong>{c.name}</strong><span className="small muted">{c.teacherName}</span></div>
              {/* 선생님이 수업을 시작하면 「수업 참여」, 쉬는 시간이면 게임 입구 */}
              <StudentSessionCard classId={c.id} />
              <StudentBoard classId={c.id} />
            </div>
          ))}
          {data.available.length > 0 && <h2 className="h3">다른 강의실</h2>}
          {data.available.map((c) => (
            <div key={c.id} className="card card--flat row between">
              <span><strong>{c.name}</strong><span className="small muted" style={{ display: 'block' }}>{c.teacherName}</span></span>
              <button className="btn btn--secondary btn--small" disabled={busy || c.requested} onClick={() => run(async () => setData(await api.requestJoin(c.id)))}>{c.requested ? '요청함' : '참여 요청'}</button>
            </div>
          ))}
        </>
      )}
    </Frame>
  );
}
