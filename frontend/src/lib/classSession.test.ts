import { beforeEach, describe, expect, it } from 'vitest';
import {
  adjustTime, breakSession, dueNotice, endClass, giveBreak, joinClass, loadSessions, lockingSession, noticesFor, removeJoined,
  saveDefaults, DEFAULTS, sessionState, sessionsForChild, startClass,
} from './classSession';
import { save } from './storage';

const MIN = 60_000;
const T0 = new Date('2026-11-13T16:00:00+09:00').getTime();
const room = { id: 'c1', name: '5학년 A반', teacherName: '김선생', members: [{ id: 's1', name: '지우' }, { id: 's2', name: '새봄' }] };

beforeEach(() => { save('ai-mentor-class-sessions', {}); saveDefaults({ ...DEFAULTS }); });

describe('수업 진행', () => {
  it('참여한 학생만 수업 중 잠기고, 쉬는 시간이면 풀린다', () => {
    startClass(room, 50, T0);
    expect(lockingSession('s1', T0 + MIN)).toBeNull(); // 참여 전에는 잠그지 않음
    joinClass('c1', { id: 's1', name: '지우' }, T0 + MIN);
    expect(lockingSession('s1', T0 + 2 * MIN)?.classId).toBe('c1');
    expect(lockingSession('s2', T0 + 2 * MIN)).toBeNull();
    giveBreak('c1', 10, T0 + 50 * MIN);
    expect(lockingSession('s1', T0 + 51 * MIN)).toBeNull();
    expect(breakSession('s1', T0 + 51 * MIN)?.classId).toBe('c1');
  });

  it('참여 목록에서 빼면 잠금이 풀린다', () => {
    startClass(room, 50, T0);
    joinClass('c1', { id: 's1', name: '지우' }, T0);
    removeJoined('c1', 's1');
    expect(lockingSession('s1', T0 + MIN)).toBeNull();
    expect(loadSessions().c1.removed).toEqual(['s1']);
  });

  it('늘리기·줄이기는 5분 전 알림 시점도 함께 옮기고, 줄여도 1분은 남는다', () => {
    startClass(room, 50, T0);
    adjustTime('c1', 5, T0);
    const s = loadSessions().c1;
    expect(s.endAt).toBe(T0 + 55 * MIN);
    expect(sessionState(s, T0 + 50 * MIN + 1)).toBe('class-soon');
    adjustTime('c1', -60, T0 + 10 * MIN);
    expect(loadSessions().c1.endAt).toBe(T0 + 11 * MIN);
    const n = noticesFor('teacher', 't1', []);
    expect(n.map((x) => x.at)).toEqual([T0 + 6 * MIN, T0 + 11 * MIN]);
  });

  it('보호자: 아이 강의실 수업만, 끝낸 뒤 30분까지 보이고, 알리기를 끄면 알림 없음', () => {
    startClass(room, 50, T0);
    expect(sessionsForChild('s2', T0)).toHaveLength(1);
    expect(sessionsForChild('s9', T0)).toHaveLength(0);
    expect(dueNotice(noticesFor('guardian', 'g1', ['s2']), [], T0 + 45 * MIN)?.text).toContain('5분 뒤 끝나요');
    endClass('c1', T0 + 50 * MIN);
    expect(sessionState(loadSessions().c1, T0 + 50 * MIN)).toBe('closed');
    expect(sessionsForChild('s2', T0 + 79 * MIN)).toHaveLength(1);
    expect(sessionsForChild('s2', T0 + 81 * MIN)).toHaveLength(0);
    saveDefaults({ ...DEFAULTS, notifyGuardian: false });
    startClass(room, 50, T0);
    expect(noticesFor('guardian', 'g1', ['s2'])).toHaveLength(0);
  });
});
