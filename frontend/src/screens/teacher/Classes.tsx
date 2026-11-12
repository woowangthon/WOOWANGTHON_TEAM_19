// 학습지도자: 강의실 — 학습 계획에 맞춰 강의실을 열고, 학생은 초대(학생 수락) 또는 참여 요청(내가 수락)으로 들어온다.
// 학원 입장 코드는 여기서 쓰지 않는다(11-10 확정).
import { useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import { mmss } from '../../lib/date';
import { KIND_LABEL, TIMER_LENGTHS, WARN_OPTIONS, fitWarn, timerState, timerStatusText, useNow, warnAllowed } from '../../lib/classTimer';
import type { Classroom, ClassTimer, ClassTimerKind, ClassTimerStart } from '../../types';

export function TeacherClasses() {
  const { data, setData, error, loading, reload } = useAsync(() => api.getTeacherClasses());
  const [create, setCreate] = useState(false);
  const [name, setName] = useState('');
  const [plan, setPlan] = useState('');
  const [inviteTo, setInviteTo] = useState<Classroom | null>(null);
  const [timerFor, setTimerFor] = useState<Classroom | null>(null);
  const { run, busy, error: actErr } = useAction();
  const now = useNow(!!data?.classrooms.some((c) => c.timer));

  return (
    <Frame adult title="강의실" exit tabs="teacher" right={<button className="icon-btn" aria-label="강의실 열기" onClick={() => setCreate(true)}><Icon name="plus" /></button>}>
      {loading && !data && <Thinking label="불러오는 중" />}
      <LoadError error={error ?? actErr} onRetry={reload} />
      {data?.classrooms.length === 0 && <div className="notice notice--plain"><span>아직 강의실이 없어요. 오른쪽 위 +로 열어 주세요.</span></div>}
      <div className="card-grid">
      {data?.classrooms.map((c) => (
        <section key={c.id} className="card stack timer-card">
          <div className="timer-card__head">
            <span><strong className="h3">{c.name}</strong><span className="small muted" style={{ display: 'block' }}>{c.plan || '학습 계획 없음'}</span></span>
            <span className="pill pill--mint">{c.members.length}명</span>
          </div>
          <TimerBlock timer={c.timer} now={now} />
          {c.timer
            ? <button className="btn btn--secondary btn--small" disabled={busy} onClick={() => run(async () => setData(await api.stopClassTimer(c.id)))}>타이머 끄기</button>
            : <button className="btn btn--secondary btn--small" onClick={() => setTimerFor(c)}><Icon name="clock" size={16} />타이머 켜기</button>}
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
      </div>

      {timerFor && (
        <TimerSheet room={timerFor} busy={busy} error={actErr} onClose={() => setTimerFor(null)}
          onStart={(s) => run(async () => { setData(await api.startClassTimer(timerFor.id, s)); setTimerFor(null); })} />
      )}
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

/** 강의실 카드 안 타이머 상태(GPT-015): 꺼짐 · 수업 중 · 쉬는 시간 중 · 곧 끝남 · 끝남. 아이콘+글자+시간으로 */
function TimerBlock({ timer, now }: { timer: ClassTimer | null | undefined; now: number }) {
  const { phase, leftSec } = timerState(timer, now);
  const cls = phase === 'soon' ? ' timer--soon' : phase === 'running' && timer ? (timer.kind === 'class' ? ' timer--class' : ' timer--break') : '';
  const icon = phase === 'ended' ? 'check' : phase === 'running' && timer ? (timer.kind === 'class' ? 'book' : 'cup') : 'clock';
  return (
    <div className={'timer' + cls}>
      {/* 상태 문구는 바뀔 때만 읽힌다(매초 읽지 않게 시간은 live 영역 밖) */}
      <div className="timer__status" role="status"><Icon name={icon} size={16} />{timerStatusText(timer, phase)}</div>
      <time className="timer__time" aria-label={phase === 'off' ? '꺼짐' : `남은 시간 ${Math.floor(leftSec / 60)}분 ${leftSec % 60}초`}>{phase === 'off' ? '— : —' : mmss(leftSec)}</time>
      {phase === 'off' && <p className="small muted">타이머를 켜면 끝나기 전에 화면으로 알려 드려요.</p>}
      {(phase === 'running') && timer && <p className="small muted">끝나기 {timer.warnMin}분 전에 알려 드려요</p>}
      {phase === 'soon' && <div className="notice"><Icon name="info" size={16} /><span>{Math.ceil(leftSec / 60)}분 뒤 끝나요</span></div>}
    </div>
  );
}

/** 타이머 켜기 시트(GPT-016): 종류 · 길이 · 몇 분 전 알림. 시트 안 주요 버튼은 「시작」 하나 */
function TimerSheet({ room, busy, error, onClose, onStart }: {
  room: Classroom; busy: boolean; error: string | null; onClose: () => void; onStart: (s: ClassTimerStart) => void;
}) {
  const [kind, setKind] = useState<ClassTimerKind>('class');
  const [minutes, setMinutes] = useState(TIMER_LENGTHS.class.base);
  const [warnMin, setWarnMin] = useState(TIMER_LENGTHS.class.warn);
  const [fitted, setFitted] = useState(false); // 길이 때문에 알림 시점이 바뀌었는지(글자로 알린다)
  const pickKind = (k: ClassTimerKind) => { setKind(k); setMinutes(TIMER_LENGTHS[k].base); setWarnMin(TIMER_LENGTHS[k].warn); setFitted(false); };
  const pickLen = (m: number) => { const w = fitWarn(m, warnMin); setFitted(w !== warnMin); setMinutes(m); setWarnMin(w); };
  return (
    <Sheet title={`${room.name} 타이머`} onClose={onClose}>
      <div className="timer-setup">
        <fieldset><legend>종류</legend>
          <div className="seg">
            {(['class', 'break'] as const).map((k) => (
              <button key={k} type="button" className={'seg__btn' + (kind === k ? ' seg__btn--on' : '')} aria-pressed={kind === k} onClick={() => pickKind(k)}>
                <Icon name={k === 'class' ? 'book' : 'cup'} size={18} />{KIND_LABEL[k]}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset><legend>길이</legend>
          <div className="chip-row">
            {TIMER_LENGTHS[kind].options.map((m) => (
              <button key={m} type="button" className={'chip' + (minutes === m ? ' chip--on' : '')} aria-pressed={minutes === m} onClick={() => pickLen(m)}>{minutes === m && <Icon name="check" size={14} />}{m}분</button>
            ))}
          </div>
        </fieldset>
        <fieldset><legend>몇 분 전 알림</legend>
          <div className="chip-row">
            {WARN_OPTIONS.map((w) => {
              const ok = warnAllowed(minutes, w);
              return <button key={w} type="button" className={'chip' + (warnMin === w ? ' chip--on' : '')} aria-pressed={warnMin === w} disabled={!ok} onClick={() => { setWarnMin(w); setFitted(false); }}>{warnMin === w && <Icon name="check" size={14} />}{w}분 전</button>;
            })}
          </div>
          {fitted && <p className="hint" role="status">{KIND_LABEL[kind]}보다 짧게 골라야 해서 {warnMin}분 전으로 바꿨어요</p>}
        </fieldset>
        <p className="small muted">소리 없이 화면으로 알려 드려요.</p>
      </div>
      <LoadError error={error} />
      <div className="sheet__actions">
        <button className="btn btn--primary" disabled={busy} onClick={() => onStart({ kind, minutes, warnMin })}>시작</button>
        <button className="btn btn--ghost" onClick={onClose}>취소</button>
      </div>
    </Sheet>
  );
}
