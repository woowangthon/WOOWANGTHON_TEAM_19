// 학원 관리(원장 전용): 학원·학교를 등록해 승인받은 학습지도자 = 원장. 설정 → 학원 관리에서 들어온다.
// · 학원 일련번호: 학습지도자 가입용(고정)  · 입장 코드: 학생·보호자용 6자리, 10분 (11-10 확정 2A)
// · 학습지도자 소속 신청은 체크해서 승인
import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Stat, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import { mmss } from '../../lib/date';
import { useAuth } from '../../state/auth';

export function OwnerHome() {
  const { me } = useAuth();
  if (!me) return null;
  if (!me.membership?.isOwner) return <Navigate to="/settings/org" replace />;
  return <Dashboard />;
}

function Dashboard() {
  const { data, setData, error, loading, reload } = useAsync(() => api.getOwnerDashboard());
  const [pick, setPick] = useState<string[]>([]);
  const { run, busy, error: actErr } = useAction();
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const left = data?.entryCode ? Math.max(0, Math.round((data.entryCode.expiresAt - now) / 1000)) : 0;

  return (
    <Frame adult title="학원 관리" back="/settings">
      {loading && !data && <Thinking label="불러오는 중" />}
      <LoadError error={error ?? actErr} onRetry={reload} />
      {data && (
        <>
          <div><h1 className="h2">{data.academy.name}</h1><div className="small muted">{data.academy.orgType} 일련번호 <strong className="num">{data.academy.serial}</strong> · 학습지도자 소속 신청용</div></div>
          <div className="stats">
            <Stat label="학습지도자" value={data.teachers.length} />
            <Stat label="강의실" value={data.classrooms.length} />
            <Stat label="학생" value={data.students.length} />
          </div>

          <section className="card stack" aria-label="학원 입장 코드">
            <div className="row between"><strong>학원 입장 코드</strong><span className="small muted">학생·보호자용</span></div>
            {data.entryCode && left > 0 ? (
              <>
                <div className="row between"><span className="code-big code-big--digits">{data.entryCode.code}</span><span className="pill pill--accent num"><Icon name="clock" size={14} />{mmss(left)}</span></div>
                <p className="small muted">이 코드를 알려 주세요. 연결된 학생·보호자 중 한 명만 넣어도 둘 다 등록돼요.</p>
              </>
            ) : <p className="small muted">코드를 만들면 10분 동안 쓸 수 있어요.</p>}
            <button className="btn btn--primary btn--small" style={{ alignSelf: 'flex-start' }} disabled={busy} onClick={() => run(async () => setData(await api.issueEntryCode()))}>{data.entryCode && left > 0 ? '새 코드 만들기' : '코드 만들기'}</button>
          </section>

          <section className="card card--flat stack" style={{ padding: 0 }} aria-label="학습지도자 소속 신청">
            <div className="row between" style={{ padding: '12px 14px 0' }}><strong>학습지도자 소속 신청</strong><span className="pill">{data.pendingTeachers.length}</span></div>
            {data.pendingTeachers.length === 0 ? <p className="small muted" style={{ padding: '0 14px 12px' }}>새 요청이 없어요</p> : (
              <>
                {data.pendingTeachers.map((t) => (
                  <label key={t.id} className={'check-row' + (pick.includes(t.id) ? ' check-row--on' : '')}>
                    <span><strong>{t.name}</strong> <span className="small muted">{t.sub}</span></span>
                    <input type="checkbox" checked={pick.includes(t.id)} onChange={(e) => setPick(e.target.checked ? [...pick, t.id] : pick.filter((x) => x !== t.id))} />
                  </label>
                ))}
                <div style={{ padding: 12 }}>
                  <button className="btn btn--primary btn--small" disabled={!pick.length || busy} onClick={() => run(async () => { setData(await api.approveTeachers(pick)); setPick([]); })}>선택한 {pick.length}명 승인</button>
                </div>
              </>
            )}
          </section>

          <People title="학습지도자" rows={data.teachers} />
          <People title="강의실" rows={data.classrooms.map((c) => ({ id: c.id, name: c.name, sub: `${c.teacherName} · ${c.count}명` }))} />
          <People title="학생" rows={data.students} />
        </>
      )}
    </Frame>
  );
}

function People({ title, rows }: { title: string; rows: { id: string; name: string; sub?: string }[] }) {
  return (
    <details className="card card--flat fold">
      <summary className="row between"><strong>{title}</strong><span className="pill">{rows.length}</span></summary>
      <ul className="list" style={{ marginTop: 8 }}>
        {rows.map((r) => <li key={r.id} className="between"><span>{r.name}</span><span className="small muted">{r.sub}</span></li>)}
        {rows.length === 0 && <li className="small muted">아직 없어요</li>}
      </ul>
    </details>
  );
}
