// 강의실 수업 진행 화면 부품(11-13 재하 시나리오). 계산·저장은 lib/classSession.
// 모양은 기존 부품(timer·notice·pill·chip·card)만 썼다. 새 시안은 GPT 요청서(sorrt/GPT-DESIGN-REQUEST-2026-11-13.md)로 받는다.
import { useEffect, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Frame } from './Frame';
import { Icon } from './Icon';
import { useAuth } from '../state/auth';
import { load, save } from '../lib/storage';
import { josa } from '../lib/josa';
import {
  STEP_MIN, adjustTime, breakSession, dueNotice, endClass, giveBreak, hhmm, isJoined, joinClass, lockingSession, minutesLeft,
  noticesFor, placeOf, removeJoined, resumeClass, sessionState, sessionsForChild, startClass, useClassSessions,
  type ClassSession, type SessionState,
} from '../lib/classSession';
import type { Classroom } from '../types';

const where = (place: string | null) => (place ? ` · ${place}` : '');

/* ================= 학습지도자: 강의실 카드 안 수업 진행 ================= */
const TEACHER_STATUS: Record<SessionState, string> = {
  class: '수업 중', 'class-soon': '곧 끝남 · 수업', 'class-over': '수업 시간이 다 됐어요',
  break: '쉬는 시간', 'break-soon': '곧 끝남 · 쉬는 시간', 'break-over': '쉬는 시간이 다 됐어요', closed: '수업 전',
};

export function TeacherSessionPanel({ room }: { room: Classroom }) {
  const { sessions, defaults: d, places, now } = useClassSessions();
  const s = sessions[room.id];
  const st: SessionState = s ? sessionState(s, now) : 'closed';
  const place = placeOf(room.id, d, places);
  if (st === 'closed') {
    return (
      <>
        <div className="timer">
          <div className="timer__status"><Icon name="clock" size={16} />수업 전{where(place)}</div>
          <p className="small muted">수업을 시작하면 강의실 학생에게 알림이 가고, 「수업 참여」를 누른 학생은 공부 기능만 쓸 수 있어요.</p>
        </div>
        <button className="btn btn--primary btn--small" disabled={room.members.length === 0} onClick={() => startClass(room, d.classMin)}>
          <Icon name="book" size={16} />수업 시작 · {d.classMin}분
        </button>
      </>
    );
  }
  const inClass = s.phase === 'class';
  const soon = st === 'class-soon' || st === 'break-soon';
  const over = st === 'class-over' || st === 'break-over';
  const cls = soon ? ' timer--soon' : over ? '' : inClass ? ' timer--class' : ' timer--break';
  return (
    <>
      <div className={'timer' + cls}>
        <div className="timer__status" role="status"><Icon name={over ? 'check' : inClass ? 'book' : 'cup'} size={16} />{TEACHER_STATUS[st]}{where(place)}</div>
        {!over && <div className="timer__end">{hhmm(s.endAt)}에 끝나요 <span className="small muted">· {minutesLeft(s, now)}분 남음</span></div>}
        <div className="chip-row" role="group" aria-label="시간 조정">
          <button type="button" className="chip" disabled={over} onClick={() => adjustTime(room.id, -STEP_MIN)}>−{STEP_MIN}분</button>
          <button type="button" className="chip" onClick={() => adjustTime(room.id, STEP_MIN)}>+{STEP_MIN}분</button>
        </div>
      </div>
      <div className="btn-row">
        {inClass
          ? <button className="btn btn--secondary btn--small" onClick={() => giveBreak(room.id, d.breakMin)}><Icon name="cup" size={16} />쉬는 시간 {d.breakMin}분</button>
          : <button className="btn btn--secondary btn--small" onClick={() => resumeClass(room.id, d.classMin)}><Icon name="book" size={16} />수업 다시 시작</button>}
        <button className="btn btn--ghost btn--small" onClick={() => endClass(room.id)}>수업 끝내기</button>
      </div>
      <JoinedList s={s} />
    </>
  );
}

/** 참여 목록 — 교실에 없는 학생이 보이면 바로 뺀다(「수업 참여」는 출석이 아니다) */
function JoinedList({ s }: { s: ClassSession }) {
  const joined = new Map(s.joined.map((j) => [j.id, j]));
  return (
    <details className="fold" open>
      <summary className="row between"><strong className="small">수업 참여</strong><span className="pill pill--mint">{s.joined.length}/{s.members.length}명</span></summary>
      <ul className="list" style={{ marginTop: 8 }}>
        {s.members.map((m) => {
          const j = joined.get(m.id);
          return (
            <li key={m.id} className="between">
              <span>{m.name} <span className="small muted">{j ? `${hhmm(j.at)} 참여` : s.removed.includes(m.id) ? '참여 취소함' : '아직'}</span></span>
              {j && <button className="btn btn--ghost btn--small" onClick={() => removeJoined(s.classId, m.id)} aria-label={`${m.name} 참여 취소`}>참여 취소</button>}
            </li>
          );
        })}
      </ul>
    </details>
  );
}

/* ================= 학생: 강의실 카드 안 수업 상태 ================= */
export function StudentSessionCard({ classId }: { classId: string }) {
  const { me } = useAuth();
  const nav = useNavigate();
  const { sessions, defaults: d, places, now } = useClassSessions();
  const s = sessions[classId];
  if (!me || !s || !s.members.some((m) => m.id === me.id)) return null;
  const st = sessionState(s, now);
  if (st === 'closed') return null;
  const place = placeOf(classId, d, places);
  const joined = isJoined(s, me.id);
  if (s.phase === 'class') {
    if (st === 'class-over') return <div className="student-timer"><Icon name="check" size={16} />수업 시간이 끝났어</div>;
    return (
      <div className="stack">
        <div className="student-timer"><Icon name="book" size={16} /><span>수업 중{where(place)}</span><time>{hhmm(s.endAt)}에 끝나</time></div>
        {joined
          ? <div className="notice notice--plain"><span><span className="pill pill--mint">참여 중</span> 지금은 공부 기능만 열려 있어</span></div>
          : (
            <>
              {s.removed.includes(me.id) && <p className="small muted">선생님이 참여를 취소했어. 교실에 있다면 다시 눌러 줘.</p>}
              <button className="btn btn--primary btn--small" onClick={() => joinClass(classId, me)}><Icon name="check" size={16} />수업 참여</button>
            </>
          )}
      </div>
    );
  }
  return (
    <div className="stack">
      <div className="student-timer"><Icon name="cup" size={16} /><span>{st === 'break-over' ? '쉬는 시간이 끝났어' : '쉬는 시간'}</span>{st !== 'break-over' && <time>{hhmm(s.endAt)}까지</time>}</div>
      {joined && d.games && st !== 'break-over' && <button className="btn btn--secondary btn--small" onClick={() => nav('/student/games')}>쉬는 시간 게임</button>}
    </div>
  );
}

/* ================= 학생: 화면 위 띠 ================= */
export function ClassRibbon() {
  const { me } = useAuth();
  const { sessions, defaults: d, now } = useClassSessions();
  if (!me || me.role !== 'student') return null;
  const lock = lockingSession(me.id, now, sessions);
  const brk = lock ? null : breakSession(me.id, now, sessions);
  if (lock) return <div className="notice notice--plain class-ribbon" role="status"><Icon name="lock" size={14} /><span>수업 중 · {hhmm(lock.endAt)}에 끝나</span></div>;
  if (brk) return (
    <div className="notice class-ribbon" role="status">
      <Icon name="cup" size={14} /><span style={{ flex: 1 }}>쉬는 시간 · {hhmm(brk.endAt)}까지</span>
      {d.games && <Link className="small" to="/student/games">게임</Link>}
    </div>
  );
  return null;
}

/** 학생 하단 탭 잠금 표시용 */
export function useClassLocked(): boolean {
  const { me } = useAuth();
  const { sessions, now } = useClassSessions();
  return !!me && me.role === 'student' && !!lockingSession(me.id, now, sessions);
}

/* ================= 학생: 수업 중 잠긴 화면 ================= */
export function ClassLockGate({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  const { sessions, now } = useClassSessions();
  const lock = me ? lockingSession(me.id, now, sessions) : null;
  if (!lock) return <>{children}</>;
  return <Locked title="지금은 수업 시간이야" text={`${lock.className} · ${hhmm(lock.endAt)}에 끝나. 쉬는 시간에 다시 열려.`} />;
}

/** 쉬는 시간에만 여는 화면(게임). 원장님이 게임을 끄면 안 열린다 */
export function BreakOnlyGate({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  const { sessions, defaults: d, now } = useClassSessions();
  const brk = me ? breakSession(me.id, now, sessions) : null;
  if (brk && d.games) return <>{children}</>;
  return <Locked title="쉬는 시간에 열려" text={d.games ? '강의실에서 수업에 참여하고, 선생님이 쉬는 시간을 주면 할 수 있어.' : '우리 학원은 쉬는 시간 게임을 쓰지 않아.'} />;
}

function Locked({ title, text }: { title: string; text: string }) {
  const nav = useNavigate();
  return (
    <Frame title="" exit tabs="student" actions={<button className="btn btn--primary" onClick={() => nav('/student')}>오늘 공부로</button>}>
      <div className="spacer" />
      <div className="celebrate">
        <span className="path-card__icon" style={{ width: 64, height: 64 }}><Icon name="lock" size={30} /></span>
        <h1 className="h2">{title}</h1>
        <p className="muted small">{text}</p>
        {/* 안전: 위기 화면은 수업 중에도 항상 열려 있다 */}
        <Link className="small" to="/student/crisis">힘든 일이 있으면 여기를 눌러</Link>
      </div>
      <div className="spacer" />
    </Frame>
  );
}

/* ================= 보호자: 아이 수업 상태(픽업용) ================= */
export function GuardianClassCard() {
  const { me } = useAuth();
  const { sessions, defaults: d, places, now } = useClassSessions();
  if (!me || me.role !== 'guardian' || !d.notifyGuardian) return null;
  const rows = me.linked.flatMap((c) => sessionsForChild(c.id, now, sessions).map((s) => ({ c, s })));
  if (!rows.length) return null;
  return (
    <>
      {rows.map(({ c, s }) => {
        const st = sessionState(s, now);
        const place = placeOf(s.classId, d, places);
        const joined = isJoined(s, c.id);
        const head = st === 'closed' ? `수업이 끝났어요 · ${hhmm(s.closedAt ?? s.endAt)}`
          : st === 'class-over' ? `수업 시간이 다 됐어요 · ${hhmm(s.endAt)}`
          : st === 'class-soon' ? `끝나기 ${minutesLeft(s, now)}분 전이에요 · ${hhmm(s.endAt)}에 끝나요`
          : st === 'class' ? `수업 중이에요 · ${hhmm(s.endAt)}에 끝나요`
          : `쉬는 시간이에요 · ${hhmm(s.endAt)}까지`;
        // 앱이 확인하지 않은 사실(아이가 교실에 있음)은 말하지 않는다. 「참여」 버튼을 눌렀는지만 알린다
        const sub = st === 'closed' ? null : joined ? `${josa(c.name, '이', '가')} 수업 참여를 눌렀어요` : `${josa(c.name, '은', '는')} 아직 수업 참여를 누르지 않았어요`;
        return (
          <section key={s.classId + c.id} className={'card row between' + (st === 'class-soon' ? ' card--warn' : '')} aria-label="수업 상태">
            <span>
              <span className="small muted" style={{ display: 'block' }}>{s.className}{where(place)}</span>
              <strong>{head}</strong>
              {sub && <span className="small muted" style={{ display: 'block' }}>{sub}</span>}
            </span>
            <Icon name={st === 'closed' ? 'check' : s.phase === 'break' ? 'cup' : 'clock'} size={22} />
          </section>
        );
      })}
    </>
  );
}

/* ================= 모든 역할: 정한 시점에 잠깐 뜨는 알림 ================= */
export function SessionToasts() {
  const { me } = useAuth();
  const [toast, setToast] = useState<{ key: string; text: string; leaving: boolean } | null>(null);
  const role = me?.role === 'teacher' || me?.role === 'student' || me?.role === 'guardian' ? me.role : null;
  useEffect(() => {
    if (!me || !role) return;
    const firedKey = `ai-mentor-class-fired:${me.id}`;
    const tick = () => {
      const fired = load<string[]>(firedKey, []);
      const n = dueNotice(noticesFor(role, me.id, me.linked.map((l) => l.id)), fired, Date.now());
      if (!n) return;
      save(firedKey, [...fired, n.key].slice(-100));
      setToast({ key: n.key, text: n.text, leaving: false });
    };
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, [me, role]);
  useEffect(() => {
    if (!toast || toast.leaving) return;
    const a = setTimeout(() => setToast((x) => (x && x.key === toast.key ? { ...x, leaving: true } : x)), 4000);
    const b = setTimeout(() => setToast((x) => (x && x.key === toast.key ? null : x)), 4400);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [toast]);
  if (!toast) return null;
  return (
    <div className={'timer-toast' + (toast.leaving ? ' timer-toast--leave' : '')} role="status" aria-live="polite">
      <Icon name="clock" size={18} /> {toast.text}
    </div>
  );
}
