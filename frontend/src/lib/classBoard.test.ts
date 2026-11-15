import { beforeEach, describe, expect, it } from 'vitest';
import { addPost, boardNotices, daysLeft, dueText, loadPosts, openHomework, removePost, toggleDone } from './classBoard';
import { DEFAULTS, saveDefaults } from './classSession';
import { save } from './storage';
import { addDays, ymd } from './date';

const T0 = new Date(2026, 10, 13, 16, 0).getTime(); // 11-13(금) 16:00
const day = (n: number) => ymd(addDays(new Date(T0), n));
const room = { id: 'c1', name: '4학년 A반', teacherName: '김선생님', members: [{ id: 's1', name: '지우' }, { id: 's2', name: '이민준' }] };

beforeEach(() => { save('ai-mentor-class-posts', []); saveDefaults({ ...DEFAULTS }); });

describe('강의실 공지·숙제', () => {
  it('숙제는 제목·마감이 있어야 하고, 학생이 다 했어를 누르면 남은 숙제에서 빠진다', () => {
    expect(() => addPost(room, { kind: 'homework', title: ' ', body: '', due: day(1) }, T0)).toThrow('제목');
    expect(() => addPost(room, { kind: 'homework', title: '3쪽', body: '', due: null }, T0)).toThrow('마감');
    const p = addPost(room, { kind: 'homework', title: '3쪽 풀기', body: '', due: day(1) }, T0);
    expect(openHomework('s1', T0).map((x) => x.id)).toEqual([p.id]);
    toggleDone(p.id, 's1');
    expect(openHomework('s1', T0)).toHaveLength(0);
    expect(openHomework('s2', T0)).toHaveLength(1);
    expect(openHomework('s9', T0)).toHaveLength(0); // 다른 강의실 학생
    removePost(p.id);
    expect(loadPosts()).toHaveLength(0);
  });

  it('마감 글자: 오늘·내일·날짜·지남', () => {
    expect(dueText(day(0), T0)).toBe('오늘까지');
    expect(dueText(day(1), T0)).toBe('내일까지');
    expect(daysLeft(day(-1), T0)).toBe(-1);
  });

  it('알림: 학생 새 글 + 마감 전날 / 보호자 마감 전날(아이가 안 했을 때만, 보호자 알림 끄면 없음)', () => {
    const p = addPost(room, { kind: 'homework', title: '3쪽 풀기', body: '', due: day(1) }, T0);
    const kid = boardNotices('student', 's1', [], T0).map((n) => n.text);
    expect(kid).toContain('새 숙제: 3쪽 풀기 · 내일까지');
    expect(kid).toContain('내일까지 숙제가 있어: 3쪽 풀기');
    expect(boardNotices('guardian', 'g1', ['s1'], T0).map((n) => n.text)).toEqual(['지우의 숙제가 내일까지예요: 3쪽 풀기']);
    toggleDone(p.id, 's1');
    expect(boardNotices('guardian', 'g1', ['s1'], T0)).toHaveLength(0);
    toggleDone(p.id, 's1');
    saveDefaults({ ...DEFAULTS, notifyGuardian: false });
    expect(boardNotices('guardian', 'g1', ['s1'], T0)).toHaveLength(0);
    expect(boardNotices('student', 's1', [], T0 + 3 * 86_400_000).some((n) => n.text.startsWith('새 숙제'))).toBe(false); // 3일 지나면 「새」 아님
  });
});
