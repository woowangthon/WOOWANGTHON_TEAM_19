// 학원 관리(원장 전용): 학원·학교를 등록해 승인받은 학습지도자 = 원장. 설정 → 학원 관리에서 들어온다.
// · 학원 일련번호: 학습지도자 가입용(고정)  · 입장 코드: 학생·보호자용 6자리, 10분 (11-10 확정 2A)
// · 학습지도자 소속 신청은 체크해서 승인
// · 11-13: 강의실 만들기·담당 학습지도자·장소(선택), 수업 기본값(수업·쉬는 시간 길이, 게임·보호자 알림·장소 표시 켜기/끄기)
import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Sheet, Stat, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import { mmss } from '../../lib/date';
import { BREAK_LENGTHS, CLASS_LENGTHS, saveDefaults, savePlace, useClassSessions, type ClassDefaults } from '../../lib/classSession';
import { ORG_MODE } from '../../api';
import type { OwnerDashboard } from '../../types';
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

          <ClassDefaultsCard />
          <OwnerClassrooms data={data} onChange={setData} />

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

/** 수업 기본값(11-13). 알림 시점은 고르지 않는다: 끝나기 5분 전 + 끝날 때(고정). 이 기기에 저장(서버 전) */
function ClassDefaultsCard() {
  const { defaults: d } = useClassSessions();
  const set = (p: Partial<ClassDefaults>) => saveDefaults({ ...d, ...p });
  const Toggle = ({ k, label, sub }: { k: 'games' | 'notifyGuardian' | 'showPlace'; label: string; sub: string }) => (
    <label className="check-row session-setting">
      <span className="session-setting__label"><strong>{label}</strong><span className="small muted">{sub}</span>
        <span className="session-setting__state">{d[k] ? '켜짐' : '꺼짐'}</span>
      </span>
      <input className="switch" type="checkbox" checked={d[k]} onChange={(e) => set({ [k]: e.target.checked })} />
    </label>
  );
  return (
    <section className="card stack class-defaults" aria-label="수업 기본값">
      <div className="row between"><strong>수업 기본값</strong><span className="small muted">학습지도자가 「수업 시작」하면 이 길이로</span></div>
      <fieldset><legend>수업 시간</legend>
      <div className="chip-row">
        {CLASS_LENGTHS.map((m) => <button key={m} type="button" aria-pressed={d.classMin === m} className={'chip' + (d.classMin === m ? ' chip--on' : '')} onClick={() => set({ classMin: m })}>{m}분</button>)}
      </div>
      </fieldset>
      <fieldset><legend>쉬는 시간</legend>
      <div className="chip-row">
        {BREAK_LENGTHS.map((m) => <button key={m} type="button" aria-pressed={d.breakMin === m} className={'chip' + (d.breakMin === m ? ' chip--on' : '')} onClick={() => set({ breakMin: m })}>{m}분</button>)}
      </div>
      </fieldset>
      <div>
        <Toggle k="games" label="쉬는 시간 게임" sub="쉬는 시간에 학생이 짧은 게임을 할 수 있어요" />
        <Toggle k="notifyGuardian" label="보호자에게 수업 상태 알리기" sub="수업 중 · 끝나기 5분 전 · 끝남 (픽업 시간 안내)" />
        <Toggle k="showPlace" label="강의실 장소 표시" sub="큰 학원이라면 켜서 「302호」처럼 보여 주세요" />
      </div>
      <p className="small muted">알림은 끝나기 5분 전과 끝날 때 학습지도자·보호자 화면에 잠깐 떠요(고정). 학습지도자가 시간을 늘리고 줄일 수 있어요.</p>
    </section>
  );
}

/** 강의실 관리(11-13): 만들기 · 담당 학습지도자 · 장소(선택). 서버가 아직 원장 강의실 만들기를 못 해서 org http 모드에선 장소만 */
function OwnerClassrooms({ data, onChange }: { data: OwnerDashboard; onChange: (d: OwnerDashboard) => void }) {
  const { defaults: d, places } = useClassSessions();
  const [create, setCreate] = useState(false);
  const [name, setName] = useState('');
  const [plan, setPlan] = useState('');
  const [teacher, setTeacher] = useState(data.teachers[0]?.id ?? '');
  const [place, setPlace] = useState('');
  const { run, busy, error } = useAction();
  const canEdit = ORG_MODE !== 'http';
  return (
    <section className="card stack" aria-label="강의실 관리">
      <div className="row between"><strong>강의실</strong><span className="pill">{data.classrooms.length}</span></div>
      {data.classrooms.length === 0 && (
        <div className="classroom-empty">
          <Icon name="building" size={28} />
          <p className="small muted">아직 강의실이 없어요{canEdit ? '. 아래에서 만들어 주세요.' : ''}</p>
        </div>
      )}
      <ul className="list">
        {data.classrooms.map((c) => (
          <li key={c.id} className="stack" style={{ alignItems: 'stretch', gap: 6 }}>
            <div className="row between"><strong>{c.name}</strong><span className="small muted">{c.count}명</span></div>
            <div className="classroom-meta">
              {canEdit && c.teacherId ? (
                <label>담당 학습지도자
                  <select value={c.teacherId} disabled={busy} onChange={(e) => run(async () => onChange(await api.ownerSetTeacher(c.id, e.target.value)))}>
                    {data.teachers.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                </label>
              ) : <span className="small muted">담당 · {c.teacherName}</span>}
              {d.showPlace && <label>강의실 장소<input placeholder="예: 302호" defaultValue={places[c.id] ?? ''} onBlur={(e) => savePlace(c.id, e.target.value)} /></label>}
            </div>
          </li>
        ))}
      </ul>
      <LoadError error={error} />
      {canEdit
        ? <button className="btn btn--secondary btn--small" style={{ alignSelf: 'flex-start' }} disabled={!data.teachers.length} onClick={() => setCreate(true)}><Icon name="plus" size={16} />강의실 만들기</button>
        : <p className="small muted">강의실 만들기·담당 바꾸기는 서버 연결 뒤에 열려요. 지금은 학습지도자가 강의실 탭에서 만들어요.</p>}
      {create && (
        <Sheet title="강의실 만들기" onClose={() => setCreate(false)}>
          <div className="classroom-form">
          <label className="field">강의실 이름<input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="예: 5학년 B반" /></label>
          <label className="field">학습 계획<input className="input" value={plan} onChange={(e) => setPlan(e.target.value)} placeholder="예: 소수의 덧셈 (12월)" /></label>
          <label className="field">담당 학습지도자
            <select className="input" value={teacher} onChange={(e) => setTeacher(e.target.value)}>
              {data.teachers.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <label className="field">장소 <span className="small muted">(선택 · 「장소 표시」를 켜면 보여요)</span><input className="input" value={place} onChange={(e) => setPlace(e.target.value)} placeholder="예: 302호" /></label>
          </div>
          <LoadError error={error} />
          <button className="btn btn--primary" disabled={!name.trim() || !teacher || busy} onClick={() => run(async () => {
            const next = await api.ownerCreateClassroom(name, plan, teacher);
            const added = next.classrooms.find((c) => !data.classrooms.some((x) => x.id === c.id));
            if (added && place.trim()) savePlace(added.id, place);
            onChange(next); setCreate(false); setName(''); setPlan(''); setPlace('');
          })}>만들기</button>
        </Sheet>
      )}
    </section>
  );
}
