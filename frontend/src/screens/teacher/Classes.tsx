// 학습지도자: 강의실 — 학습 계획에 맞춰 강의실을 열고, 학생은 초대(학생 수락) 또는 참여 요청(내가 수락)으로 들어온다.
// 학원 입장 코드는 여기서 쓰지 않는다(11-10 확정).
import { useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import type { Classroom } from '../../types';

export function TeacherClasses() {
  const { data, setData, error, loading, reload } = useAsync(() => api.getTeacherClasses());
  const [create, setCreate] = useState(false);
  const [name, setName] = useState('');
  const [plan, setPlan] = useState('');
  const [inviteTo, setInviteTo] = useState<Classroom | null>(null);
  const { run, busy, error: actErr } = useAction();

  return (
    <Frame adult title="강의실" exit tabs="teacher" right={<button className="icon-btn" aria-label="강의실 열기" onClick={() => setCreate(true)}><Icon name="plus" /></button>}>
      {loading && !data && <Thinking label="불러오는 중" />}
      <LoadError error={error ?? actErr} onRetry={reload} />
      {data?.classrooms.length === 0 && <div className="notice notice--plain"><span>아직 강의실이 없어요. 오른쪽 위 +로 열어 주세요.</span></div>}
      {data?.classrooms.map((c) => (
        <section key={c.id} className="card stack">
          <div className="row between">
            <span><strong className="h3">{c.name}</strong><span className="small muted" style={{ display: 'block' }}>{c.plan || '학습 계획 없음'}</span></span>
            <span className="pill pill--mint">{c.members.length}명</span>
          </div>
          {c.requests.length > 0 && (
            <div className="stack">
              <div className="small muted">참여 요청</div>
              {c.requests.map((r) => (
                <div key={r.id} className="row between">
                  <strong>{r.name}</strong>
                  <span className="row">
                    <button className="btn btn--ghost btn--small" disabled={busy} onClick={() => run(async () => setData(await api.answerRequest(c.id, r.id, false)))}>거절</button>
                    <button className="btn btn--primary btn--small" disabled={busy} onClick={() => run(async () => setData(await api.answerRequest(c.id, r.id, true)))}>수락</button>
                  </span>
                </div>
              ))}
            </div>
          )}
          <div className="chip-row">
            {c.members.map((m) => <span key={m.id} className="pill">{m.name}</span>)}
            {c.invited.map((m) => <span key={m.id} className="pill pill--accent">{m.name} · 초대함</span>)}
          </div>
          <button className="btn btn--secondary btn--small" style={{ alignSelf: 'flex-start' }} onClick={() => setInviteTo(c)}><Icon name="plus" size={16} />학생 초대</button>
        </section>
      ))}

      {create && (
        <Sheet title="강의실 열기" onClose={() => setCreate(false)}>
          <label className="field">강의실 이름<input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="예: 5학년 B반" /></label>
          <label className="field">학습 계획<input className="input" value={plan} onChange={(e) => setPlan(e.target.value)} placeholder="예: 소수의 덧셈 (12월)" /></label>
          <LoadError error={actErr} />
          <button className="btn btn--primary" disabled={!name.trim() || busy} onClick={() => run(async () => { setData(await api.createClassroom(name, plan)); setCreate(false); setName(''); setPlan(''); })}>열기</button>
        </Sheet>
      )}
      {inviteTo && data && (
        <Sheet title={`${inviteTo.name}에 초대`} onClose={() => setInviteTo(null)}>
          <p className="small muted">같은 학원 학생만 보여요. 학생이 수락하면 들어와요.</p>
          {(() => {
            const cur = data.classrooms.find((c) => c.id === inviteTo.id)!;
            const taken = new Set([...cur.members, ...cur.invited].map((m) => m.id));
            const list = data.academyStudents.filter((s) => !taken.has(s.id));
            if (!list.length) return <div className="notice notice--plain"><span>초대할 학생이 없어요</span></div>;
            return list.map((s) => (
              <div key={s.id} className="row between">
                <span><strong>{s.name}</strong> <span className="small muted">{s.sub}</span></span>
                <button className="btn btn--secondary btn--small" disabled={busy} onClick={() => run(async () => setData(await api.inviteStudent(inviteTo.id, s.id)))}>{cur.requests.some((r) => r.id === s.id) ? '수락' : '초대'}</button>
              </div>
            ));
          })()}
        </Sheet>
      )}
    </Frame>
  );
}
