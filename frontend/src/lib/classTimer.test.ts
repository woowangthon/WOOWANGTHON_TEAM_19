import { describe, expect, it } from 'vitest';
import { fitWarn, timerState, timerStatusText, warnAllowed } from './classTimer';
import type { ClassTimer } from '../types';

const T0 = 1_000_000;
const t = (kind: ClassTimer['kind'], minutes: number, warnMin: number): ClassTimer =>
  ({ kind, minutes, warnMin, startedAt: T0, endsAt: T0 + minutes * 60_000 });

describe('수업 타이머 계산', () => {
  it('꺼짐 → 진행 → 곧 끝남 → 끝남, 0 아래로 안 내려감', () => {
    const c = t('class', 40, 5);
    expect(timerState(null, T0).phase).toBe('off');
    expect(timerState(c, T0)).toEqual({ phase: 'running', leftSec: 2400 });
    expect(timerState(c, T0 + 35 * 60_000 - 1000).phase).toBe('running');
    expect(timerState(c, T0 + 35 * 60_000).phase).toBe('soon');
    expect(timerState(c, T0 + 40 * 60_000)).toEqual({ phase: 'ended', leftSec: 0 });
    expect(timerState(c, T0 + 99 * 60_000).leftSec).toBe(0);
  });

  it('알림 시점은 길이보다 짧아야 한다 — 5분 쉬는 시간이면 3분 전으로 맞춘다', () => {
    expect(warnAllowed(5, 5)).toBe(false);
    expect(warnAllowed(10, 5)).toBe(true);
    expect(fitWarn(5, 5)).toBe(3);
    expect(fitWarn(40, 5)).toBe(5);
  });

  it('상태 문구', () => {
    expect(timerStatusText(null, 'off')).toBe('꺼짐');
    expect(timerStatusText(t('class', 40, 5), 'running')).toBe('수업 중');
    expect(timerStatusText(t('break', 10, 3), 'running')).toBe('쉬는 시간 중');
    expect(timerStatusText(t('break', 10, 3), 'soon')).toBe('곧 끝남 · 쉬는 시간');
    expect(timerStatusText(t('class', 40, 5), 'ended')).toBe('수업이 끝났어요');
  });
});
