// 수업 타이머 — 강의실 탭의 시작·끝 카드와, 정한 시점에 잠깐 떴다 사라지는 알림(성호 11-12).
// 상시 카운트다운은 없다: 카드는 「몇 시에 끝나요」만, 알림은 학원이 정한 「n분 전」과 끝에만.
// 화면 구성은 재하 TK-98(26bf538, GPT-015·016) — 강의실 카드마다 타이머 칸 + 켜기 시트.
import { useEffect, useState } from 'react';
import { api } from '../api';
import { DEFAULT_ALERTS, KIND_LABEL, TIMER_EVENT, TIMER_LENGTHS, dueAlert, loadTimer, normalizeAlerts, saveTimer, startTimer, timerPhase, timerStatusText, type TimerKind, type TimerState } from '../lib/classTimer';
import { Sheet } from './Common';
import { useAuth } from '../state/auth';
import { Icon } from './Icon';

const hhmm = (ms: number) => new Date(ms).toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' });

/** 학원이 정한 알림 시점(서버에 아직 없거나 실패하면 기본 [10, 5]) */
export function useTimerAlerts(): number[] {
  const [alerts, setAlerts] = useState<number[]>(DEFAULT_ALERTS);
  useEffect(() => { api.getTimerAlerts().then((r) => setAlerts(normalizeAlerts(r?.alertsMin))).catch(() => setAlerts(DEFAULT_ALERTS)); }, []);
  return alerts;
}

/** 이 기기의 타이머 + 상태가 바뀌도록 15초마다 다시 그림(숫자 카운트다운은 그리지 않는다) */
function useTimer(): [TimerState | null, number] {
  const [t, setT] = useState<TimerState | null>(() => loadTimer());
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const on = () => { setT(loadTimer()); setNow(Date.now()); };
    window.addEventListener(TIMER_EVENT, on);
    const iv = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => { window.removeEventListener(TIMER_EVENT, on); window.clearInterval(iv); };
  }, []);
  return [t, now];
}

/** 강의실 카드 안 타이머 칸 + 켜기/끄기(재하 GPT-015·016 화면). 동작은 11-12 결정:
 *  학원이 정한 「n분 전」·끝에 잠깐 뜨는 알림, 숫자 카운트다운 없음(끝나는 시각만), 학생 화면엔 없음 */
export function ClassroomTimer({ classId, className }: { classId: string; className: string }) {
  const [timer, now] = useTimer();
  const alerts = useTimerAlerts();
  const [open, setOpen] = useState(false);
  const mine = timer && timer.classId === classId ? timer : null;
  const other = timer && !mine && timer.endAt > now; // 다른 강의실에서 켜 둔 타이머
  const phase = timerPhase(mine, now);
  const cls = phase === 'soon' ? ' timer--soon' : phase === 'running' && mine ? (mine.kind === 'class' ? ' timer--class' : ' timer--break') : '';
  const icon = phase === 'ended' ? 'check' : phase === 'running' && mine ? (mine.kind === 'class' ? 'book' : 'cup') : 'clock';
  return (
    <>
      <div className={'timer' + cls}>
        {/* 상태 문구는 바뀔 때만 읽힌다 */}
        <div className="timer__status" role="status"><Icon name={icon} size={16} />{timerStatusText(mine, phase)}</div>
        {mine && phase !== 'ended' && <div className="timer__end">{hhmm(mine.endAt)}에 끝나요</div>}
        {phase === 'off' && <p className="small muted">타이머를 켜면 끝나기 {alerts.join('·')}분 전과 끝날 때 화면으로 잠깐 알려 드려요.</p>}
        {phase === 'running' && mine && <p className="small muted">끝나기 {mine.alertsMin.join('·')}분 전에 알려 드려요</p>}
      </div>
      {mine && phase !== 'ended'
        ? <button className="btn btn--secondary btn--small" onClick={() => saveTimer(null)}>타이머 끄기</button>
        : <button className="btn btn--secondary btn--small" disabled={!!other} onClick={() => setOpen(true)}><Icon name="clock" size={16} />{other ? '다른 강의실 타이머 진행 중' : '타이머 켜기'}</button>}
      {open && <TimerSheet title={`${className} 타이머`} alerts={alerts} onClose={() => setOpen(false)}
        onStart={(kind, minutes) => { saveTimer(startTimer(kind, minutes, alerts, Date.now(), classId)); setOpen(false); }} />}
    </>
  );
}

/** 타이머 켜기 시트(재하 GPT-016): 종류 · 길이. 알림 시점은 학원 설정(고르지 않음, 11-12) */
function TimerSheet({ title, alerts, onClose, onStart }: { title: string; alerts: number[]; onClose: () => void; onStart: (k: TimerKind, m: number) => void }) {
  const [kind, setKind] = useState<TimerKind>('class');
  const [minutes, setMinutes] = useState(TIMER_LENGTHS.class.base);
  const pickKind = (k: TimerKind) => { setKind(k); setMinutes(TIMER_LENGTHS[k].base); };
  const shown = alerts.filter((m) => m < minutes);
  return (
    <Sheet title={title} onClose={onClose}>
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
              <button key={m} type="button" className={'chip' + (minutes === m ? ' chip--on' : '')} aria-pressed={minutes === m} onClick={() => setMinutes(m)}>{minutes === m && <Icon name="check" size={14} />}{m}분</button>
            ))}
          </div>
        </fieldset>
        <p className="small muted">{shown.length ? `끝나기 ${shown.join('·')}분 전` : '끝나기 전 알림 없음'}과 끝날 때 소리 없이 화면으로 잠깐 알려 드려요 · 알림 시점은 원장님이 학원 관리에서 정해요</p>
      </div>
      <div className="sheet__actions">
        <button className="btn btn--primary" onClick={() => onStart(kind, minutes)}>시작</button>
        <button className="btn btn--ghost" onClick={onClose}>취소</button>
      </div>
    </Sheet>
  );
}

/** 앱 어디에 있든(학습지도자만) 정한 시점에 알림을 잠깐 띄웠다 사라지게 한다. 1초마다 확인(서버 푸시 없음) */
export function ClassTimerToasts() {
  const { me } = useAuth();
  const [toast, setToast] = useState<{ id: number; text: string; leaving: boolean } | null>(null);
  const teacher = me?.role === 'teacher';
  useEffect(() => {
    if (!teacher) return;
    const tick = () => {
      const t = loadTimer();
      if (!t) return;
      const a = dueAlert(t, Date.now());
      if (a) {
        saveTimer(a.end ? null : { ...t, fired: [...t.fired, a.at] });
        setToast({ id: a.at, text: a.text, leaving: false });
      } else if (Date.now() > t.endAt + 60_000) saveTimer(null); // 끝 알림 시점도 지났으면 정리
    };
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, [teacher]);
  // 4초 보이고 0.4초 동안 사라진다(움직임 줄이기면 애니메이션 없이 사라짐 — CSS)
  useEffect(() => {
    if (!toast || toast.leaving) return;
    const a = setTimeout(() => setToast((x) => (x && x.id === toast.id ? { ...x, leaving: true } : x)), 4000);
    const b = setTimeout(() => setToast((x) => (x && x.id === toast.id ? null : x)), 4400);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [toast]);
  if (!teacher || !toast) return null;
  return (
    <div className={'timer-toast' + (toast.leaving ? ' timer-toast--leave' : '')} role="status" aria-live="polite">
      <Icon name="clock" size={18} /> {toast.text}
    </div>
  );
}
