// 강의실 수업 진행 화면 부품(11-13 재하 시나리오). 계산·저장은 lib/classSession.
// 모양: GPT-037~048(AI-Mentor-Design-GPT-2026-11-13) — 표시만 바꿨고 훅·핸들러·상태 분기는 그대로.
import { useEffect, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Frame } from './Frame';
import { Icon } from './Icon';
import { useAuth } from '../state/auth';
import { useMentor } from '../state/mentor';
import { load, save } from '../lib/storage';
import { josa } from '../lib/josa';
import {
  STEP_MIN, adjustTime, breakSession, dueNotice, endClass, giveBreak, hhmm, isJoined, joinClass, lockingSession, minutesLeft,
  noticesFor, placeOf, removeJoined, resumeClass, sessionState, sessionsForChild, startClass, useClassSessions,
  setRemoteLive, useLivePoll,
  type ClassSession, type SessionState,
} from '../lib/classSession';
import { boardNotices } from '../lib/classBoard';
import type { Classroom } from '../types';

const where = (place: string | null) => (place ? ` · ${place}` : '');

/* ================= 학습지도자: 강의실 카드 안 수업 진행 (GPT-039·040) ================= */
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
          <div className="timer__status"><Icon name="clock" size={20} />수업 전{where(place)}</div>
          <p className="small muted">수업을 시작하면 강의실 학생에게 알림이 가고, 「수업 참여」를 누른 학생은 공부 기능만 쓸 수 있어요.</p>
        </div>
        <button className="btn btn--primary btn--small session-start" disabled={room.members.length === 0} onClick={() => startClass(room, d.classMin)}>
          <Icon name="book" size={20} />수업 시작 · {d.classMin}분
        </button>
        {room.members.length === 0 && <p className="small muted">학생이 들어온 강의실에서 시작할 수 있어요.</p>}
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
        <div className="timer__status" role="status"><Icon name={over ? 'check' : inClass ? 'book' : 'cup'} size={20} />{TEACHER_STATUS[st]}{where(place)}</div>
        {over
          ? <div className="timer__end">{hhmm(s.endAt)}<small>예정 시각이 지났어요 · 늘리거나 끝내 주세요</small></div>
          : <div className="timer__end">{hhmm(s.endAt)}에 끝나요<small>{minutesLeft(s, now)}분 남음</small></div>}
        <div className="chip-row session-adjust" role="group" aria-label="시간 조정">
          <button type="button" className="chip" disabled={over} onClick={() => adjustTime(room.id, -STEP_MIN)}>−{STEP_MIN}분</button>
          <button type="button" className="chip" onClick={() => adjustTime(room.id, STEP_MIN)}>+{STEP_MIN}분</button>
        </div>
        <div className="btn-row session-actions">
          {inClass
            ? <button className="btn btn--secondary btn--small" onClick={() => giveBreak(room.id, d.breakMin)}><Icon name="cup" size={20} />쉬는 시간 · {d.breakMin}분</button>
            : <button className="btn btn--secondary btn--small" onClick={() => resumeClass(room.id, d.classMin)}><Icon name="book" size={20} />수업 다시 시작</button>}
          <div className="session-end"><button className="btn btn--ghost btn--small" onClick={() => endClass(room.id)}>수업 끝내기</button></div>
        </div>
      </div>
      <JoinedList s={s} />
    </>
  );
}

/** 참여 목록(GPT-041) — 교실에 없는 학생이 보이면 바로 뺀다(「수업 참여」는 출석이 아니다) */
function JoinedList({ s }: { s: ClassSession }) {
  const joined = new Map(s.joined.map((j) => [j.id, j]));
  return (
    <details className="fold joined-list" open>
      <summary><strong className="small">수업 참여</strong><span className="pill pill--mint">{s.joined.length}/{s.members.length}명</span></summary>
      <ul className="list">
        {s.members.map((m) => {
          const j = joined.get(m.id);
          const removed = s.removed.includes(m.id);
          return (
            <li key={m.id} className="between joined-row">
              <span className="joined-row__person"><strong>{m.name}</strong>
                <span className="small muted joined-row__state">
                  <Icon name={j ? 'check' : removed ? 'refresh' : 'clock'} size={16} />
                  {j ? `${hhmm(j.at)} 참여` : removed ? '참여 취소함' : '아직'}
                </span>
              </span>
              {j && <button className="btn btn--ghost btn--small" onClick={() => removeJoined(s.classId, m.id)} aria-label={`${m.name} 참여 취소`}>참여 취소</button>}
            </li>
          );
        })}
      </ul>
    </details>
  );
}

/* ================= 학생: 강의실 카드 안 수업 상태 (GPT-042) ================= */
export function StudentSessionCard({ classId }: { classId: string }) {
  const { me } = useAuth();
  const { say } = useMentor();
  const nav = useNavigate();
  const { sessions, defaults: d, places, now } = useClassSessions();
  const s = sessions[classId];
  if (!me || !s || !s.members.some((m) => m.id === me.id)) return null;
  const st = sessionState(s, now);
  if (st === 'closed') return null;
  const place = placeOf(classId, d, places);
  const joined = isJoined(s, me.id);
  const t = hhmm(s.endAt);
  if (s.phase === 'class') {
    if (st === 'class-over') return <div className="student-timer student-session"><div className="timer__status"><Icon name="check" size={20} />{say('수업 시간이 끝났어', '수업 시간이 끝났어요')}</div></div>;
    return (
      <div className="student-timer student-session">
        <div className="timer__status"><Icon name="book" size={20} />수업 중{where(place)} · {say(`${t}에 끝나`, `${t}에 끝나요`)}</div>
        {joined
          ? <p className="small"><span className="pill pill--mint">참여 중</span> {say('지금은 공부 기능만 열려 있어.', '지금은 공부 기능만 열려 있어요.')}</p>
          : (
            <>
              <p className="small">{s.removed.includes(me.id)
                ? say('선생님이 참여를 취소했어. 교실에 있다면 다시 눌러 줘.', '선생님이 참여를 취소했어요. 교실에 있다면 다시 눌러 주세요.')
                : say('준비됐으면 수업에 참여해 줘.', '준비되면 수업에 참여해 주세요.')}</p>
              <button className="btn btn--primary session-start" onClick={() => joinClass(classId, me)}>수업 참여</button>
            </>
          )}
      </div>
    );
  }
  return (
    <div className="student-timer student-session">
      <div className="timer__status"><Icon name="cup" size={20} />{st === 'break-over' ? say('쉬는 시간이 끝났어', '쉬는 시간이 끝났어요') : `쉬는 시간 · ${t}까지`}</div>
      {joined && d.games && st !== 'break-over' && <button className="btn btn--secondary" onClick={() => nav('/student/games')}>쉬는 시간 게임</button>}
    </div>
  );
}

/* ================= 학생: 화면 위 띠 (GPT-043) ================= */
export function ClassRibbon() {
  const { me } = useAuth();
  const { say } = useMentor();
  const { sessions, defaults: d, now } = useClassSessions();
  if (!me || me.role !== 'student') return null;
  const lock = lockingSession(me.id, now, sessions);
  const brk = lock ? null : breakSession(me.id, now, sessions);
  if (lock) return <div className="notice notice--plain class-ribbon" role="status"><Icon name="lock" size={20} /><span>수업 중 · {say(`${hhmm(lock.endAt)}에 끝나`, `${hhmm(lock.endAt)}에 끝나요`)}</span></div>;
  if (brk) return (
    <div className="notice class-ribbon" role="status">
      <Icon name="cup" size={20} /><span>쉬는 시간 · {hhmm(brk.endAt)}까지</span>
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

/* ================= 학생: 수업 중 잠긴 화면 (GPT-045) ================= */
export function ClassLockGate({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  const { say } = useMentor();
  const { sessions, now } = useClassSessions();
  const lock = me ? lockingSession(me.id, now, sessions) : null;
  if (!lock) return <>{children}</>;
  const t = hhmm(lock.endAt);
  return <Locked title={say('지금은 수업 시간이야', '지금은 수업 시간이에요')}
    text={say(`${lock.className} 수업은 ${t}에 끝나. 쉬는 시간에 다시 열려.`, `${lock.className} 수업은 ${t}에 끝나요. 쉬는 시간에 다시 열려요.`)} />;
}

/** 쉬는 시간에만 여는 화면(게임). 원장님이 게임을 끄면 안 열린다 */
export function BreakOnlyGate({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  const { say } = useMentor();
  const { sessions, defaults: d, now } = useClassSessions();
  const brk = me ? breakSession(me.id, now, sessions) : null;
  if (brk && d.games) return <>{children}</>;
  return <Locked title={say('쉬는 시간에 열려', '쉬는 시간에 열려요')} text={d.games
    ? say('강의실에서 수업에 참여하고, 선생님이 쉬는 시간을 주면 할 수 있어.', '강의실에서 수업에 참여하고, 선생님이 쉬는 시간을 주면 할 수 있어요.')
    : say('우리 학원은 쉬는 시간 게임을 쓰지 않아.', '우리 학원은 쉬는 시간 게임을 쓰지 않아요.')} />;
}

function Locked({ title, text }: { title: string; text: string }) {
  const nav = useNavigate();
  const { say, animal } = useMentor();
  return (
    <Frame title="" exit tabs="student" actions={<button className="btn btn--primary" onClick={() => nav('/student')}>오늘 공부로</button>}>
      <div className="locked-mentor">
        <img src={`${import.meta.env.BASE_URL}mascot/${animal}/wave-face.png`} alt="인사하는 멘토" />
        <h2>{title}</h2>
        <p>{text}</p>
      </div>
      {/* 안전: 위기 화면은 수업 중에도 항상 열려 있다 — 세 가지 잠금 화면 모두에 둔다 */}
      <Link className="small safety-link" to="/student/crisis"><Icon name="shield" size={20} />{say('힘든 일이 있으면 여기를 눌러', '힘든 일이 있으면 여기를 눌러 주세요')}</Link>
    </Frame>
  );
}

/* ================= 보호자: 아이 수업 상태(픽업용, GPT-047) ================= */
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
        const state = st === 'closed' ? '수업이 끝났어요'
          : st === 'class-over' ? '수업 시간이 다 됐어요'
          : st === 'class-soon' ? `${minutesLeft(s, now)}분 뒤 수업이 끝나요`
          : st === 'class' ? '수업 중이에요'
          : st === 'break-over' ? '쉬는 시간이 끝났어요'
          : '쉬는 시간이에요';
        const time = hhmm(st === 'closed' ? (s.closedAt ?? s.endAt) : s.endAt);
        const label = st === 'closed' ? '수업을 끝낸 시각'
          : st === 'class-over' ? '예정 종료 시각 · 선생님이 아직 수업을 끝내지 않았어요'
          : s.phase === 'break' ? '쉬는 시간 종료 · 픽업 시각이 아니에요'
          : '수업 예정 종료';
        // 앱이 확인하지 않은 사실(아이가 교실에 있음)은 말하지 않는다. 「참여」 버튼을 눌렀는지만 알린다
        const sub = st === 'closed' ? null : joined ? `${josa(c.name, '이', '가')} 수업 참여를 눌렀어요.` : `${josa(c.name, '은', '는')} 아직 수업 참여를 누르지 않았어요.`;
        return (
          <section key={s.classId + c.id} className={'card guardian-session' + (st === 'class-soon' ? ' card--warn' : '')} aria-label="수업 상태">
            <span className="small muted">{s.className}{where(place)}</span>
            <div className="guardian-session__state"><Icon name={st === 'closed' ? 'check' : s.phase === 'break' ? 'cup' : 'clock'} size={20} />{state}</div>
            <div><time className="guardian-session__time">{time}</time><div className="small muted">{label}</div></div>
            {sub && <p className="guardian-session__note">{sub}</p>}
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
  // 서버 모드: 계정이 바뀌면 받아 둔 강의실 상태를 비우고, 로그인해 있는 동안 5초마다 다시 읽는다(알림이 다른 기기의 변화를 따라오게)
  useEffect(() => { setRemoteLive(null); }, [me?.id]);
  useLivePoll(!!me && !!role);
  useEffect(() => {
    if (!me || !role) return;
    const firedKey = `ai-mentor-class-fired:${me.id}`;
    const tick = () => {
      const fired = load<string[]>(firedKey, []);
      const now = Date.now(), linked = me.linked.map((l) => l.id);
      // 수업 진행 알림 + 공지·숙제 알림(새 글, 마감 전날·당일)
      const n = dueNotice([...noticesFor(role, me.id, linked), ...boardNotices(role, me.id, linked, now)], fired, now);
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
