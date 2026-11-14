// 가짜 서버 흐름 테스트 — 하루 세션이 단계대로 흘러가는지, 역할별 화면에 맞는 정보만 가는지 확인한다.
import { beforeEach, describe, expect, it } from 'vitest';
import { mockApi as api } from './mock';
import { generateProblems } from './engine';
import { ymd } from '../lib/date';

const answers = () => generateProblems('분수의 덧셈', '중급', ymd()).map((p) => p.answer);
async function solveAll(id: string) {
  for (const [n, d] of answers()) {
    const p = await api.getProblem(id);
    await api.submitAnswer(id, p!.id, n, d);
  }
}

const as = (id: string) => api.demoLogin(id); // s1 지우 · t1 김선생님 · g1 지우 보호자
beforeEach(async () => { await api.resetDemo(); await as('s1'); });

describe('학생 하루 세션', () => {
  it('처음에는 연속 3일, 약속·캐릭터가 필요하다', async () => {
    const home = await api.getStudentHome();
    expect(home).toMatchObject({ streakDays: 3, needsOnboarding: true, session: null, doneToday: false, endedInCrisis: false });
    expect(home.task?.unit).toBe('분수의 덧셈');
  });

  it('틀리면 힌트가 자동으로 나오고, 힌트를 다 쓴 뒤에만 풀이를 볼 수 있다', async () => {
    const s = await api.startSession('중급');
    const p = (await api.getProblem(s.id))!;
    expect(p).toMatchObject({ index: 0, total: 5, hintsLeft: 3, canShowSolution: false });
    expect(p).not.toHaveProperty('answer'); // 정답은 화면으로 내려가지 않는다
    await expect(api.showSolution(s.id, p.id)).rejects.toThrow();
    for (let i = 1; i <= 3; i++) {
      const r = await api.submitAnswer(s.id, p.id, 99, 99);
      expect(r.correct).toBe(false);
      expect(r.autoHint).toBeTruthy();
      expect(r.hintsLeft).toBe(3 - i);
    }
    const last = await api.submitAnswer(s.id, p.id, 99, 99);
    expect(last).toMatchObject({ autoHint: null, canShowSolution: true });
    const sol = await api.showSolution(s.id, p.id);
    expect(sol.steps.length).toBeGreaterThan(1);
    expect(sol.session).toMatchObject({ solved: 1, assisted: 1, phase: 'solve' });
    expect((await api.getProblem(s.id))!.index).toBe(1); // 다음 문제로 넘어감
  });

  it('다 풀면 학습 완료 단계가 되고 연속이 하루 늘어난다. 하루에 한 번만 할 수 있다', async () => {
    const s = await api.startSession('중급');
    await solveAll(s.id);
    expect(await api.getProblem(s.id)).toBeNull();
    const after = (await api.getActiveSession())!;
    expect(after).toMatchObject({ phase: 'transition', solved: 5, streakDays: 4 });
    expect((await api.afterStudy(s.id, 'skip')).phase).toBe('wrap');
    const wrap = await api.getWrap(s.id);
    expect(wrap.hardChips[wrap.hardChips.length - 1]).toBe('직접 쓸래');
    expect(wrap.quizOptions).toHaveLength(3);
    expect((await api.submitWrap(s.id, { hardPoint: '분모가 헷갈렸어', quiz: wrap.quizOptions[0] })).phase).toBe('done');
    expect((await api.getStudentHome()).doneToday).toBe(true);
    expect((await api.startSession('초급')).id).toBe(s.id); // 새 세션이 생기지 않는다
    expect((await api.getRecords())[0]).toMatchObject({ solved: 5, total: 5, difficulty: '중급' });
  });

  it('새로 불러와도 같은 문제에서 이어진다', async () => {
    const s = await api.startSession('중급');
    const [n, d] = answers()[0];
    const first = (await api.getProblem(s.id))!;
    await api.submitAnswer(s.id, first.id, n, d);
    await api.requestHint(s.id, (await api.getProblem(s.id))!.id);
    const again = (await api.getProblem((await api.getActiveSession())!.id))!;
    expect(again).toMatchObject({ index: 1, hintsLeft: 2 });
    expect(again.hints).toHaveLength(1);
  });
});

describe('역할별로 가는 정보', () => {
  it('실수 유형은 학습지도자에게만, 보호자에게는 한 줄·어려운 점·퀴즈만 간다', async () => {
    const s = await api.startSession('중급');
    const p = (await api.getProblem(s.id))!;
    await api.submitAnswer(s.id, p.id, p.left![0] + p.right![0], p.left![1] + p.right![1]); // 분모끼리 더하는 실수
    await solveAll(s.id);
    await api.afterStudy(s.id, 'skip');
    await api.submitWrap(s.id, { hardPoint: '분모가 헷갈렸어', quiz: null });
    await as('t1');
    const jiwoo = (await api.getResults()).find((r) => r.id === 's1')!;
    expect(jiwoo).toMatchObject({ done: true, hints: 1, mistake: '분모끼리 더하기 1회', hardPoint: '분모가 헷갈렸어' });
    await as('g1');
    const g = await api.getGuardianToday();
    expect(g).toMatchObject({ done: true, solved: 5, hardPoint: '분모가 헷갈렸어', teacherComment: null });
    expect(g).not.toHaveProperty('mistake');
    expect(g).not.toHaveProperty('hints');
  });

  it('학습지도자가 승인한 코멘트만 보호자에게 보인다', async () => {
    await as('t1');
    await api.saveMemo('s1', { covered: '분수의 덧셈', stuck: '', homework: '', note: '' });
    const draft = await api.createDraft('s1');
    expect(draft.status).toBe('승인 대기');
    await as('g1');
    expect((await api.getGuardianToday()).teacherComment).toBeNull();
    await as('t1');
    await api.updateDraft('s1', '오늘도 끝까지 해냈어요.');
    await api.approveDraft('s1');
    await as('g1');
    expect((await api.getGuardianToday()).teacherComment).toBe('오늘도 끝까지 해냈어요.');
  });

  it('학습지도자가 오늘 할 것을 없애면 학생은 시작할 수 없다', async () => {
    await as('t1');
    await api.assignTask('s1', null);
    await as('s1');
    expect((await api.getStudentHome()).task).toBeNull();
    await expect(api.startSession('중급')).rejects.toThrow();
  });
});

describe('안전 알림', () => {
  // 결정 11-11 「11-15 안전 알림 전달 수준」: 🔴이면 보호자 카드에 발췌(±2턴·300자). 학습지도자에게는 내용·분류 없이
  it('위험 표현 → 세션 종료, 보호자에게 발췌(300자 이하)가 담긴 긴급 알림, 학습지도자에게는 내용·분류 없이', async () => {
    const s = await api.startSession('중급');
    await solveAll(s.id);
    await api.afterStudy(s.id, 'chat');
    expect((await api.sendChat(s.id, ['오늘 피곤해'])).crisis).toBe(false);
    const r = await api.sendChat(s.id, ['그냥 사라지고 싶어']);
    expect(r).toMatchObject({ crisis: true });
    expect(r.session.phase).toBe('crisis');
    await as('g1');
    const alert = (await api.getAlerts())[0];
    expect(alert).toMatchObject({ level: '긴급', category: '안전', status: '미확인' });
    expect(alert.excerpt).toContain('사라지고');
    expect(alert.excerpt!.length).toBeLessThanOrEqual(300);
    await as('t1');
    const t = (await api.getTeacherAlerts())[0];
    expect(t).not.toHaveProperty('category');
    expect(JSON.stringify(t)).not.toContain('사라지고');
    await as('g1');
    // 긴급은 확인 전에는 닫을 수 없다
    await expect(api.closeAlert(alert.id, '오해였어요')).rejects.toThrow();
    await api.ackAlert(alert.id);
    expect(await api.closeAlert(alert.id, '아이와 이야기해 봤어요')).toMatchObject({ status: '닫음', closeReason: '아이와 이야기해 봤어요' });
  });
});
