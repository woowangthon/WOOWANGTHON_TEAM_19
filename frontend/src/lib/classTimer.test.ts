// 수업 타이머(학습지도자 강의실) — 알림 시점 계산(성호 11-12: 학원이 시점을 정함, 상시 카운트다운 없음)
import { describe, expect, it } from 'vitest';
import { DEFAULT_ALERTS, alertMessages, dueAlert, normalizeAlerts, startTimer, timerPhase, timerStatusText } from './classTimer';

const MIN = 60_000;

describe('normalizeAlerts — 학원 설정값 다듬기', () => {
  it('1~60 정수만, 중복 없이, 큰 것부터, 최대 3개', () => {
    expect(normalizeAlerts([5, 10, 10, 0, 61, 2.5, 3, 1])).toEqual([10, 5, 3]);
  });
  it('비거나 이상하면 기본 [10, 5]', () => {
    expect(normalizeAlerts([])).toEqual(DEFAULT_ALERTS);
    expect(normalizeAlerts(undefined)).toEqual(DEFAULT_ALERTS);
  });
});

describe('startTimer · alertMessages', () => {
  it('수업 50분, 알림 [10,5] → 40분·45분·50분(끝)에 세 번', () => {
    const t = startTimer('class', 50, [10, 5], 0);
    expect(alertMessages(t).map((a) => [a.at / MIN, a.text])).toEqual([
      [40, '수업 끝나기 10분 전이에요'],
      [45, '수업 끝나기 5분 전이에요'],
      [50, '수업이 끝났어요'],
    ]);
  });
  it('길이보다 긴 알림 시점은 뺀다(쉬는 시간 5분에 10분 전 알림 없음)', () => {
    const t = startTimer('break', 5, [10, 3], 0);
    expect(alertMessages(t).map((a) => a.text)).toEqual(['쉬는 시간 끝나기 3분 전이에요', '쉬는 시간이 끝났어요']);
  });
});

describe('dueAlert — 지금 띄울 알림 하나', () => {
  const t = startTimer('class', 50, [10, 5], 0);
  it('시점 전에는 없음, 지나면 그 알림, 한 번 띄운 것은 다시 안 띄움', () => {
    expect(dueAlert(t, 39 * MIN)).toBeNull();
    const a = dueAlert(t, 40 * MIN + 1000)!;
    expect(a.text).toBe('수업 끝나기 10분 전이에요');
    expect(dueAlert({ ...t, fired: [a.at] }, 40 * MIN + 2000)).toBeNull();
  });
  it('앱을 오래 닫았다 열면 지난 알림은 건너뛰고(1분 넘게 지난 것) 끝 알림만', () => {
    expect(dueAlert(t, 47 * MIN)).toBeNull(); // 40분·45분 알림은 1분 넘게 지남
    expect(dueAlert(t, 50 * MIN + 30_000)!.text).toBe('수업이 끝났어요');
  });
});

describe('timerPhase — 강의실 카드 상태(재하 GPT-015 화면, 동작은 11-12 결정)', () => {
  const t = { ...startTimer('class', 40, [10, 5], 0), classId: 'c1' };
  it('없음 → 꺼짐, 첫 알림 전 → 수업 중, 첫 알림부터 → 곧 끝남, 끝 → 끝남', () => {
    expect(timerPhase(null, 0)).toBe('off');
    expect(timerPhase(t, 29 * MIN)).toBe('running');
    expect(timerPhase(t, 30 * MIN)).toBe('soon');
    expect(timerPhase(t, 40 * MIN)).toBe('ended');
  });
  it('상태 글자: 수업 중 / 쉬는 시간 중 / 곧 끝남 · 수업 / 수업이 끝났어요', () => {
    expect(timerStatusText(t, 'running')).toBe('수업 중');
    expect(timerStatusText({ ...t, kind: 'break' }, 'running')).toBe('쉬는 시간 중');
    expect(timerStatusText(t, 'soon')).toBe('곧 끝남 · 수업');
    expect(timerStatusText(t, 'ended')).toBe('수업이 끝났어요');
    expect(timerStatusText(null, 'off')).toBe('꺼짐');
  });
});
