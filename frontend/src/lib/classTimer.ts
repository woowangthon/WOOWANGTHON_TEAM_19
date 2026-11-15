// 수업 타이머(학습지도자 강의실 탭) — 성호 11-12 결정:
// · 알림 시점은 학원이 정한다(분 전, 기본 [10, 5]). · 상시 카운트다운은 없다. 정한 시점에 알림이 잠깐 떴다 사라진다.
// · 서버 푸시·백그라운드 큐는 없다(금지 목록) → 열려 있는 화면이 1초마다 확인한다. 학생 화면에는 안 보인다.
import { load, save } from './storage';

export type TimerKind = 'class' | 'break';
/** classId: 어느 강의실 카드에서 켰는지(재하 GPT-015 화면은 강의실 카드마다 타이머 칸). 학습지도자 한 사람이 한 번에 하나 */
export interface TimerState { kind: TimerKind; startAt: number; endAt: number; alertsMin: number[]; fired: number[]; classId?: string }
export interface TimerAlert { at: number; text: string; end: boolean }

export const DEFAULT_ALERTS = [10, 5];
const MIN = 60_000;
/** 시점이 이만큼 넘게 지났으면(앱을 닫아 두었던 경우) 띄우지 않는다. 끝 알림은 예외로 1분까지 */
const LATE_MS = 60_000;
const NAME: Record<TimerKind, string> = { class: '수업', break: '쉬는 시간' };

/** 학원 설정값: 1~60 정수, 중복 없이 큰 것부터 최대 3개. 남는 게 없으면 기본 [10, 5] */
export function normalizeAlerts(list: unknown): number[] {
  const nums = Array.isArray(list) ? list.filter((n): n is number => Number.isInteger(n) && n >= 1 && n <= 60) : [];
  const out = [...new Set(nums)].sort((a, b) => b - a).slice(0, 3);
  return out.length ? out : [...DEFAULT_ALERTS];
}

export function startTimer(kind: TimerKind, minutes: number, alertsMin: number[], now: number, classId?: string): TimerState {
  return { kind, startAt: now, endAt: now + minutes * MIN, alertsMin: normalizeAlerts(alertsMin), fired: [], ...(classId ? { classId } : {}) };
}

/** 고를 수 있는 길이(재하 TK-98 시안 값). 알림 시점은 고르지 않고 학원 설정을 쓴다(11-12) */
export const TIMER_LENGTHS: Record<TimerKind, { options: number[]; base: number }> = {
  class: { options: [20, 30, 40, 50], base: 40 },
  break: { options: [5, 10, 15], base: 10 },
};
export const KIND_LABEL: Record<TimerKind, string> = { class: '수업', break: '쉬는 시간' };

export type TimerPhase = 'off' | 'running' | 'soon' | 'ended';
/** 카드 상태. 「곧 끝남」은 첫(가장 이른) 알림 시점부터. 상시 카운트다운은 없다 */
export function timerPhase(t: TimerState | null | undefined, now: number): TimerPhase {
  if (!t) return 'off';
  if (now >= t.endAt) return 'ended';
  const first = alertMessages(t).find((a) => !a.end);
  return first && now >= first.at ? 'soon' : 'running';
}
/** 화면 상태 글자(재하 timerStatusText와 같은 문구). 바뀔 때만 화면낭독기가 읽는다 */
export function timerStatusText(t: TimerState | null | undefined, phase: TimerPhase): string {
  if (!t || phase === 'off') return '꺼짐';
  const k = KIND_LABEL[t.kind];
  if (phase === 'ended') return `${k}이 끝났어요`;
  if (phase === 'soon') return `곧 끝남 · ${k}`;
  return t.kind === 'class' ? '수업 중' : '쉬는 시간 중';
}

/** 이 타이머가 띄울 알림 전부(시각 순). 길이보다 긴 「n분 전」은 뺀다. 마지막은 끝 알림 */
export function alertMessages(t: TimerState): TimerAlert[] {
  const name = NAME[t.kind];
  const before = t.alertsMin
    .filter((m) => t.endAt - m * MIN > t.startAt)
    .map((m) => ({ at: t.endAt - m * MIN, text: `${name} 끝나기 ${m}분 전이에요`, end: false }));
  return [...before.sort((a, b) => a.at - b.at), { at: t.endAt, text: t.kind === 'class' ? '수업이 끝났어요' : '쉬는 시간이 끝났어요', end: true }];
}

/** 지금 띄울 알림 하나(없으면 null). 이미 띄운 것(fired)·1분 넘게 지난 것은 건너뛴다 */
export function dueAlert(t: TimerState, now: number): TimerAlert | null {
  return alertMessages(t).find((a) => !t.fired.includes(a.at) && a.at <= now && now - a.at <= LATE_MS) ?? null;
}

/* ---------- 이 기기에 저장(학습지도자 한 사람이 한 번에 타이머 하나) ---------- */
const KEY = 'ai-mentor-class-timer';
export const TIMER_EVENT = 'class-timer-change';
export function loadTimer(): TimerState | null { return load<TimerState | null>(KEY, null); }
export function saveTimer(t: TimerState | null) {
  save(KEY, t);
  try { window.dispatchEvent(new Event(TIMER_EVENT)); } catch { /* 테스트 등 window 없음 */ }
}
