// 강의실 수업 타이머(TK-98) — 화면에서 쓰는 계산만 모은 곳. 시안: GPT-015~018
import { useEffect, useState } from 'react';
import type { ClassTimer, ClassTimerKind } from '../types';

/** 고를 수 있는 길이(분)와 기본값. 회의: 수업·쉬는 시간, 끝나기 3분/5분 전 알림 */
export const TIMER_LENGTHS: Record<ClassTimerKind, { options: number[]; base: number; warn: number }> = {
  class: { options: [20, 30, 40, 50], base: 40, warn: 5 },
  break: { options: [5, 10, 15], base: 10, warn: 3 },
};
export const WARN_OPTIONS = [3, 5];

/** 알림 시점은 길이보다 짧아야 한다(5분 쉬는 시간에 5분 전 알림은 안 됨) */
export const warnAllowed = (minutes: number, warnMin: number) => warnMin < minutes;
/** 길이를 바꿨을 때 고른 알림이 안 맞으면 맞는 것 중 가장 늦은 것으로 */
export function fitWarn(minutes: number, warnMin: number): number {
  if (warnAllowed(minutes, warnMin)) return warnMin;
  return [...WARN_OPTIONS].reverse().find((w) => warnAllowed(minutes, w)) ?? WARN_OPTIONS[0];
}

export type TimerPhase = 'off' | 'running' | 'soon' | 'ended';
/** 지금 상태와 남은 초. 0 아래로 내려가지 않는다 */
export function timerState(t: ClassTimer | null | undefined, now: number): { phase: TimerPhase; leftSec: number } {
  if (!t) return { phase: 'off', leftSec: 0 };
  const leftSec = Math.max(0, Math.ceil((t.endsAt - now) / 1000));
  if (leftSec === 0) return { phase: 'ended', leftSec };
  return { phase: leftSec <= t.warnMin * 60 ? 'soon' : 'running', leftSec };
}

export const KIND_LABEL: Record<ClassTimerKind, string> = { class: '수업', break: '쉬는 시간' };

/** 화면용 문구. 같은 문구가 이어지면 화면낭독기는 다시 읽지 않는다(상태가 바뀔 때만 안내) */
export function timerStatusText(t: ClassTimer | null | undefined, phase: TimerPhase): string {
  if (!t || phase === 'off') return '꺼짐';
  const k = KIND_LABEL[t.kind];
  if (phase === 'ended') return `${k}이 끝났어요`; // 「수업이」「쉬는 시간이」
  if (phase === 'soon') return `곧 끝남 · ${k}`;
  return t.kind === 'class' ? '수업 중' : '쉬는 시간 중';
}

/** 1초마다 지금 시각(타이머가 켜져 있을 때만 돈다) */
export function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);
  return now;
}
