// 가짜 서버 — 백엔드 없이도 앱이 끝까지 돌도록, 서버가 할 일을 브라우저 안에서 대신한다.
// · "DB"는 localStorage 한 칸(KEY)에 저장한다 → 새로고침해도 이어진다.
// · 판단 규칙(정답·힌트·수다 응답)은 engine.ts에 있다.
// · 실제 서버로 바꿀 때: .env에서 VITE_API_MODE=http, 이 파일의 각 함수가 곧 엔드포인트 하나다.
import type { MentorApi } from './client';
import type {
  ChatMessage, Difficulty, Draft, MentorSetting, Phase, SafetyAlert, SessionView, Speech, StudentResult,
  TaskInfo, TaskStatus, TeacherMemo, Unit,
} from '../types';
import {
  MAX_HINTS, PROBLEM_UNITS, chipForTag, correctLine, crisisLine, detectCrisis, generateProblems, hintsFor, judge,
  maskPII, openingLine, replyFor, solutionFor, wrongLine, type Problem, type UnitName,
} from './engine';
import { OTHER_RESULTS, SEED_UNITS, TEACHER_NAME } from '../data/seed';
import {
  balanceOf, childOf, currentRole, currentUserId, earnStudySeeds, isRestricted, nameOf, orgApi, resetOrg, roomsOfStudent,
  roomsOfTeacher, studySeedsToday, teacherOfStudent,
} from './org';
import { addDays, dateLabel, mondayIndex, shortLabel, stampLabel, weekKeys, ymd } from '../lib/date';
import { load, save } from '../lib/storage';

/* ================= "DB" ================= */
interface ProblemState { wrong: number; hints: number; done: 'correct' | 'assisted' | null; canSolution: boolean; tags: string[]; }
interface SessionState {
  id: string; date: string; phase: Phase; unit: UnitName; difficulty: Difficulty;
  problems: Problem[]; index: number; per: Record<string, ProblemState>;
  startedAt: number; studyEndedAt: number | null; timedOut: boolean;
  chatStartedAt: number | null; chatEndedAt: number | null; messages: ChatMessage[];
}
/** 하루 기록(학습지도자·보호자 화면이 읽는 것). 대화 내용은 여기에 들어가지 않는다. */
interface DayRecord {
  date: string; unit: string; difficulty: Difficulty; solved: number; total: number;
  hints: number; retries: number; assisted: number; tags: Record<string, number>;
  studyMin: number; chatMin: number; line: string | null; hardPoint: string | null; quiz: string | null;
}
/** 학생 1명의 학습 기록 (학생마다 따로) */
interface Learner { promise: boolean; mentor: MentorSetting | null; days: DayRecord[]; session: SessionState | null; }
interface DB {
  version: 4;
  settings: { fast: boolean };
  learners: Record<string, Learner>;      // 학생 id → 학습 기록
  units: Unit[];
  tasks: Record<string, string | null>;   // 학생 id → 오늘 할 단원
  memos: Record<string, TeacherMemo>;
  drafts: Record<string, Draft>;
  alerts: (SafetyAlert & { studentId: string; studentName: string })[];
}

const KEY = 'aimentor:db';
const STUDY_SEC = 20 * 60;
const CHAT_SEC = 10 * 60;
const EMPTY_MEMO: TeacherMemo = { covered: '', stuck: '', homework: '', note: '' };

function seed(): DB {
  const past = (n: number, difficulty: Difficulty, hints: number, solved = 5): DayRecord => ({
    date: ymd(addDays(new Date(), -n)), unit: '분수의 덧셈', difficulty, solved, total: 5, hints, retries: hints, assisted: 0,
    tags: { '분모끼리 더하기': 1 }, studyMin: 18, chatMin: n === 2 ? 0 : 6,
    line: '분수의 덧셈 5문제를 풀었어요.', hardPoint: null, quiz: null,
  });
  return {
    version: 4,
    settings: { fast: false },
    learners: { s1: { promise: false, mentor: null, session: null, days: [past(3, '초급', 4, 4), past(2, '초급', 1), past(1, '중급', 3)] } }, // 지우: 어제까지 연속 3일
    units: SEED_UNITS,
    tasks: { s1: '분수의 덧셈', s2: '분수의 덧셈', s3: '분수의 덧셈' },
    memos: {}, drafts: {},
    alerts: [{ id: 'a0', studentId: 's1', studentName: '김지우', at: stampLabel(addDays(new Date(), -1).setHours(17, 2)), level: '주의', category: '마음', action: '오늘 저녁 편하게 하루 얘기를 물어봐 주세요.', status: '확인함' }],
  };
}

let db: DB = (() => { const stored = load<DB | null>(KEY, null); return stored && stored.version === 4 ? stored : seed(); })();
const commit = () => save(KEY, db);
/** 네트워크 지연 흉내 → 화면의 "생각 중" 상태를 확인할 수 있다 */
const wait = (ms = 200) => (import.meta.env.MODE === 'test' ? Promise.resolve() : new Promise((r) => setTimeout(r, ms))); // 테스트에서는 기다리지 않는다

/* ================= 누구의 기록인가 ================= */
const fail = (msg: string): never => { throw new Error(msg); };
const learner = (id: string): Learner => (db.learners[id] ??= { promise: false, mentor: null, days: [], session: null });
/** 지금 로그인한 학생 id (학생 화면 전용) */
function sid(): string {
  if (currentRole() !== 'student') fail('학생 계정으로 들어와야 해요.');
  return currentUserId()!;
}
const me = () => learner(sid());
/** 보호자가 보는 아이 id */
const childId = () => { if (currentRole() !== 'guardian') fail('보호자 계정으로 들어와야 해요.'); return childOf(currentUserId()!) ?? fail('아직 연결된 아이가 없어요. 내 정보에서 아이와 연결해 주세요.'); };
/** 학습지도자의 강의실 학생 id들 */
const myStudents = () => { if (currentRole() !== 'teacher') fail('학습지도자 계정으로 들어와야 해요.'); return [...new Set(roomsOfTeacher(currentUserId()!).flatMap((r) => r.members))]; };
const fullName = (id: string) => (id === 's1' ? '김지우' : nameOf(id));

/* ================= 계산 도우미 ================= */
const speech = (): Speech => me().mentor?.speech ?? '반말';
const scale = () => (db.settings.fast ? 20 : 1);
const today = () => ymd();

function streak(days: DayRecord[] = me().days): number {
  const set = new Set(days.map((d) => d.date));
  let d = new Date();
  if (!set.has(ymd(d))) d = addDays(d, -1); // 오늘 아직 안 했어도 어제까지 이어졌으면 유지
  let n = 0;
  while (set.has(ymd(d))) { n++; d = addDays(d, -1); }
  return n;
}
const studyRemaining = (s: SessionState) => Math.max(0, Math.round(STUDY_SEC - ((s.studyEndedAt ?? Date.now()) - s.startedAt) / 1000 * scale()));
const chatRemaining = (s: SessionState) => s.chatStartedAt == null ? CHAT_SEC
  : Math.max(0, Math.round(CHAT_SEC - ((s.chatEndedAt ?? Date.now()) - s.chatStartedAt) / 1000 * scale()));
const states = (s: SessionState) => s.problems.map((p) => s.per[p.id]);
const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);
/** 받침이 있으면 '을', 없으면 '를' (한글이 아니면 '을(를)') */
function objectParticle(word: string): string {
  const code = word.trim().charCodeAt(word.trim().length - 1) - 0xac00;
  if (code < 0 || code > 11171) return '을(를)';
  return code % 28 === 0 ? '를' : '을';
}

function stats(s: SessionState) {
  const st = states(s);
  const tags: Record<string, number> = {};
  st.forEach((x) => x.tags.forEach((t) => { tags[t] = (tags[t] ?? 0) + 1; }));
  const studySec = STUDY_SEC - studyRemaining(s);
  const chatSec = s.chatStartedAt == null ? 0 : CHAT_SEC - chatRemaining(s);
  return {
    solved: st.filter((x) => x.done).length, assisted: st.filter((x) => x.done === 'assisted').length,
    hints: sum(st.map((x) => x.hints)), retries: sum(st.map((x) => x.wrong)), tags,
    studyMin: Math.max(1, Math.ceil(studySec / 60)), chatMin: chatSec === 0 ? 0 : Math.max(1, Math.round(chatSec / 60)),
  };
}

function summaryLine(s: SessionState): string {
  const x = stats(s);
  const parts = [`${s.unit} ${x.solved}문제를 풀었어요`];
  if (x.hints > 0) parts.push(`힌트를 ${x.hints}번 보고 다시 도전했어요`);
  if (x.assisted > 0) parts.push(`${x.assisted}문제는 풀이를 같이 봤어요`);
  return parts.join(', ') + '.';
}

/** 하루 기록을 만들거나 고친다. 출석(연속 +1)은 "학습 완료" 순간에 생긴다. */
function upsertDay(s: SessionState, extra: Partial<DayRecord> = {}, id = sid()) {
  const x = stats(s);
  const L = learner(id);
  const prev = L.days.find((d) => d.date === s.date);
  const rec: DayRecord = {
    date: s.date, unit: s.unit, difficulty: s.difficulty, solved: x.solved, total: s.problems.length,
    hints: x.hints, retries: x.retries, assisted: x.assisted, tags: x.tags, studyMin: x.studyMin, chatMin: x.chatMin,
    line: prev?.line ?? null, hardPoint: prev?.hardPoint ?? null, quiz: prev?.quiz ?? null, ...extra,
  };
  L.days = [...L.days.filter((d) => d.date !== s.date), rec];
}

/** 학습 완료: 출석(연속 +1)과 씨앗(하루 1번)이 이 순간에 생긴다 */
function toTransition(s: SessionState, id = sid()) {
  s.phase = 'transition'; s.studyEndedAt = Date.now(); upsertDay(s, {}, id);
  if (stats(s).solved > 0) earnStudySeeds(id, s.unit);
}

/** 요청이 올 때마다 시간을 확인해 단계를 넘긴다(서버의 마감 판정) */
function tick(id = sid()): SessionState | null {
  const L = db.learners[id]; // 없으면 만들지 않는다(시연용 고정 학생 s2·s3 보호)
  if (!L) return null;
  const s = L.session;
  if (!s) return null;
  if (s.date !== today()) { L.session = null; commit(); return null; } // 날짜가 바뀌면 어제 세션은 닫는다
  if (s.phase === 'solve' && studyRemaining(s) <= 0) { s.timedOut = true; toTransition(s, id); }
  if (s.phase === 'chat' && chatRemaining(s) <= 0) { s.chatEndedAt = Date.now(); s.phase = 'wrap'; upsertDay(s, {}, id); }
  commit();
  return s;
}

function view(s: SessionState): SessionView {
  const x = stats(s);
  return {
    id: s.id, phase: s.phase, unit: s.unit, difficulty: s.difficulty, solved: x.solved, total: s.problems.length,
    assisted: x.assisted, hintsUsed: x.hints, studyMin: x.studyMin, studyRemainingSec: studyRemaining(s),
    chatRemainingSec: chatRemaining(s), timedOut: s.timedOut, streakDays: streak(),
  };
}

function need(sessionId: string): SessionState {
  const s = tick();
  if (!s || s.id !== sessionId) throw new Error('오늘 세션을 찾지 못했어요. 처음 화면에서 다시 시작해 주세요.');
  return s;
}
function currentProblem(s: SessionState, problemId: string) {
  const p = s.problems[s.index];
  if (s.phase !== 'solve' || !p || p.id !== problemId) return null; // 시간이 끝났거나 이미 지나간 문제
  return { p, st: s.per[p.id] };
}
function advance(s: SessionState) { s.index += 1; if (s.index >= s.problems.length) toTransition(s); }

const task = (studentId: string): TaskInfo | null => {
  if (roomsOfStudent(studentId).length === 0) return null; // 강의실에 들어가야 과제가 생긴다
  const unit = db.tasks[studentId];
  return unit ? { unit, count: 5, minutes: 20, assignedBy: teacherOfStudent(studentId) ?? TEACHER_NAME } : null;
};

function topMistake(tags: Record<string, number>): string | null {
  const top = Object.entries(tags).filter(([t]) => t !== '기타').sort((a, b) => b[1] - a[1])[0];
  return top ? `${top[0]} ${top[1]}회` : null;
}
function beginnerRun(days: DayRecord[]): number {
  const sorted = [...days].sort((a, b) => b.date.localeCompare(a.date));
  let n = 0;
  for (const d of sorted) { if (d.difficulty === '초급') n++; else break; }
  return n;
}
/** 이 앱에서 한 번도 공부하지 않은 시연용 학생(s2·s3)은 고정 결과를 쓴다 */
const fixed = (id: string) => (db.learners[id] ? undefined : OTHER_RESULTS.find((r) => r.id === id));
function resultOf(id: string): StudentResult {
  const f = fixed(id);
  if (f) return f;
  const L = learner(id);
  const d = L.days.find((x) => x.date === today());
  return {
    id, name: fullName(id), done: !!d, unit: d?.unit ?? db.tasks[id] ?? '-', solved: d?.solved ?? 0, total: d?.total ?? 5,
    difficulty: d?.difficulty ?? null, streak: streak(L.days), hints: d?.hints ?? 0,
    mistake: d ? topMistake(d.tags) : null, hardPoint: d?.hardPoint ?? null, beginnerRepeat: beginnerRun(L.days),
  };
}
const allResults = (): StudentResult[] => myStudents().map(resultOf);

function statusOf(id: string): TaskStatus {
  if (fixed(id)) return db.tasks[id] ? '완료' : '지정 전';
  const L = learner(id);
  const s = L.session && L.session.date === today() ? L.session : null;
  if (L.days.some((d) => d.date === today()) && (!s || s.phase !== 'solve')) return '완료';
  if (s) return '진행 중';
  return db.tasks[id] ? '지정됨' : '지정 전';
}
function teacherToday() {
  const rooms = roomsOfTeacher(currentUserId()!);
  return {
    dateLabel: dateLabel(), className: rooms.length ? rooms.map((r) => r.name).join(' · ') : '강의실 없음',
    units: db.units.filter((u) => u.selected).map((u) => u.name),
    students: allResults().map((r) => ({ id: r.id, name: r.name, task: db.tasks[r.id] ?? null, status: statusOf(r.id), draftStatus: db.drafts[r.id]?.status ?? null })),
  };
}

/* ================= API 구현 ================= */
export const mockApi: MentorApi = {
  /* ---------- 학생: 준비 ---------- */
  async getStudentHome() {
    await wait();
    const id = sid();
    const s = tick();
    const L = me();
    const keys = weekKeys();
    const done = new Set(L.days.map((d) => d.date));
    return {
      name: nameOf(id), dateLabel: dateLabel(), streakDays: streak(),
      attendance: keys.map((k) => done.has(k)), todayIndex: mondayIndex(),
      task: task(id), needsOnboarding: !L.promise || !L.mentor,
      session: s ? view(s) : null,
      doneToday: done.has(today()) && (!s || s.phase === 'done' || s.phase === 'crisis'),
      restricted: isRestricted(id), inClass: roomsOfStudent(id).length > 0,
      seeds: balanceOf(id), earnedToday: studySeedsToday(id),
    };
  },
  async acceptPromise() { await wait(80); me().promise = true; commit(); },
  async getMentor() { return currentRole() === 'student' ? me().mentor : null; },
  async saveMentor(setting) { await wait(80); me().mentor = setting; commit(); },

  /* ---------- 학생: 세션 ---------- */
  async getActiveSession() { if (currentRole() !== 'student') return null; const s = tick(); return s ? view(s) : null; },

  async startSession(difficulty) {
    await wait();
    const existing = tick();
    if (existing) return view(existing); // 하루 1회: 이미 있으면 그 세션을 돌려준다
    const t = task(sid());
    if (!t) throw new Error('오늘은 선생님이 정한 공부가 없어요.');
    const unit = (PROBLEM_UNITS as string[]).includes(t.unit) ? (t.unit as UnitName) : '분수의 덧셈';
    const problems = generateProblems(unit, difficulty, today(), t.count);
    const s: SessionState = {
      id: 'sess-' + Date.now(), date: today(), phase: 'solve', unit, difficulty, problems, index: 0,
      per: Object.fromEntries(problems.map((p) => [p.id, { wrong: 0, hints: 0, done: null, canSolution: false, tags: [] }])),
      startedAt: Date.now(), studyEndedAt: null, timedOut: false, chatStartedAt: null, chatEndedAt: null, messages: [],
    };
    me().session = s; commit();
    return view(s);
  },

  async getProblem(sessionId) {
    await wait(120);
    const s = need(sessionId);
    const p = s.problems[s.index];
    if (s.phase !== 'solve' || !p) return null;
    const st = s.per[p.id];
    return {
      id: p.id, index: s.index, total: s.problems.length, left: p.left, right: p.right, op: p.op,
      hints: hintsFor(p, speech()).slice(0, st.hints), hintsLeft: MAX_HINTS - st.hints,
      canShowSolution: st.canSolution, remainingSec: studyRemaining(s),
    };
  },

  async submitAnswer(sessionId, problemId, numerator, denominator) {
    await wait(350);
    const s = need(sessionId);
    const cur = currentProblem(s, problemId);
    if (!cur) return { correct: false, numeratorOk: false, denominatorOk: false, message: '', autoHint: null, hintsLeft: 0, canShowSolution: false, session: view(s) };
    const { p, st } = cur;
    const j = judge(p, numerator, denominator);
    if (j.correct) {
      st.done = 'correct';
      const message = correctLine(s.index, speech());
      advance(s); commit();
      return { correct: true, numeratorOk: true, denominatorOk: true, message, autoHint: null, hintsLeft: MAX_HINTS - st.hints, canShowSolution: false, session: view(s) };
    }
    // 틀렸을 때: 힌트가 남았으면 다음 힌트가 자동으로 나오고, 다 썼으면 「풀이 같이 보기」가 열린다
    st.wrong += 1;
    if (j.tag) st.tags.push(j.tag);
    let autoHint: string | null = null;
    if (st.hints < MAX_HINTS) { st.hints += 1; autoHint = hintsFor(p, speech())[st.hints - 1]; }
    else st.canSolution = true;
    commit();
    return {
      correct: false, numeratorOk: j.numeratorOk, denominatorOk: j.denominatorOk,
      message: wrongLine(j.numeratorOk || j.denominatorOk, speech()), autoHint,
      hintsLeft: MAX_HINTS - st.hints, canShowSolution: st.canSolution, session: view(s),
    };
  },

  async requestHint(sessionId, problemId) {
    await wait(300);
    const s = need(sessionId);
    const cur = currentProblem(s, problemId);
    if (!cur) return { hints: [], hintsLeft: 0 };
    if (cur.st.hints < MAX_HINTS) cur.st.hints += 1;
    commit();
    return { hints: hintsFor(cur.p, speech()).slice(0, cur.st.hints), hintsLeft: MAX_HINTS - cur.st.hints };
  },

  async showSolution(sessionId, problemId) {
    await wait(300);
    const s = need(sessionId);
    const cur = currentProblem(s, problemId);
    if (!cur || !cur.st.canSolution) throw new Error('아직 풀이를 볼 수 없어요. 힌트를 먼저 써 보세요.');
    cur.st.done = 'assisted'; // 풀이를 같이 본 문제도 "끝낸 문제"로 센다
    const steps = solutionFor(cur.p, speech());
    advance(s); commit();
    return { steps, session: view(s) };
  },

  async afterStudy(sessionId, choice) {
    await wait(120);
    const s = need(sessionId);
    if (s.phase === 'transition') {
      if (choice === 'chat') {
        if (isRestricted(sid())) fail('보호자와 연결된 뒤에 수다를 할 수 있어요.');
        s.phase = 'chat'; s.chatStartedAt = Date.now();
        s.messages = [{ from: 'mentor', text: openingLine(stats(s).solved === s.problems.length, speech()) }];
      } else s.phase = 'wrap';
      commit();
    }
    return view(s);
  },

  async getChat(sessionId) { await wait(100); const s = need(sessionId); return { messages: s.messages, remainingSec: chatRemaining(s) }; },

  // 가짜 서버는 답을 늘 바로 만들므로 queued·pending이 없다 → 더 받을 답도 없다
  async replyChat(sessionId) { return { reply: '', crisis: false, session: view(need(sessionId)) }; },
  async sendChat(sessionId, texts) {
    const text = texts.join(' '); // 묶음은 한 말로 본다
    await wait(600);
    const s = need(sessionId);
    if (s.phase !== 'chat') return { reply: '', crisis: false, session: view(s) };
    const turn = s.messages.filter((m) => m.from === 'me').length;
    s.messages.push({ from: 'me', text: maskPII(text) });
    if (detectCrisis(text)) {
      // 🔴 조언을 멈추고 세션을 끝낸다. 보호자에게는 원문 없이 분류·긴급도·행동 안내만 간다
      s.phase = 'crisis'; s.chatEndedAt = Date.now();
      upsertDay(s);
      db.alerts = [{ id: 'a' + Date.now(), studentId: sid(), studentName: fullName(sid()), at: stampLabel(Date.now()), level: '긴급', category: '안전', action: '지금 아이와 직접 이야기해 주세요.', status: '미확인' }, ...db.alerts];
      commit();
      return { reply: crisisLine(speech()), crisis: true, session: view(s) };
    }
    const reply = replyFor(text, turn, speech());
    s.messages.push({ from: 'mentor', text: reply });
    commit();
    return { reply, crisis: false, session: view(s) };
  },

  async endChat(sessionId) {
    await wait(100);
    const s = need(sessionId);
    if (s.phase === 'chat') { s.chatEndedAt = Date.now(); s.phase = 'wrap'; upsertDay(s); commit(); }
    return view(s);
  },

  async getWrap(sessionId) {
    await wait();
    const s = need(sessionId);
    const x = stats(s);
    const fromMistakes = Object.keys(x.tags).map(chipForTag).filter((c): c is string => !!c);
    const hardChips = [...new Set([...fromMistakes, '시간이 모자랐어', '다 쉬웠어'])].slice(0, 3).concat('직접 쓸래');
    const quizOptions = s.problems.slice(0, 3).map((p) => `${p.left[0]}/${p.left[1]} ${p.op} ${p.right[0]}/${p.right[1]}은 얼마일까요?`);
    return { unit: s.unit, solved: x.solved, total: s.problems.length, difficulty: s.difficulty, studyMin: x.studyMin, chatMin: x.chatMin, streakDays: streak(), aiLine: summaryLine(s), hardChips, quizOptions };
  },

  async submitWrap(sessionId, body) {
    await wait();
    const s = need(sessionId);
    if (s.phase === 'wrap') {
      upsertDay(s, { line: summaryLine(s), hardPoint: body.hardPoint ? maskPII(body.hardPoint).slice(0, 30) : null, quiz: body.quiz });
      s.phase = 'done'; s.messages = []; // 대화 내용은 끝나면 지운다
      commit();
    }
    return view(s);
  },

  async getRecords() {
    await wait();
    return [...me().days].sort((a, b) => b.date.localeCompare(a.date))
      .map((d) => ({ date: shortLabel(d.date), unit: d.unit, solved: d.solved, total: d.total, difficulty: d.difficulty, hints: d.hints, chatted: d.chatMin > 0 }));
  },

  /* ---------- 학습지도자 ---------- */
  async getUnits() { await wait(); return db.units; },
  async saveUnits(selectedIds) {
    await wait();
    db.units = db.units.map((u) => ({ ...u, selected: selectedIds.includes(u.id) }));
    commit();
    return db.units;
  },
  async getTeacherToday() { await wait(); myStudents().forEach((id) => tick(id)); return teacherToday(); },
  async assignTask(studentId, unit) {
    await wait(120);
    if (!myStudents().includes(studentId)) fail('내 강의실 학생에게만 과제를 줄 수 있어요.');
    db.tasks[studentId] = unit; commit(); return teacherToday();
  },
  async getMemo(studentId) { await wait(100); return { memo: db.memos[studentId] ?? EMPTY_MEMO, draft: db.drafts[studentId] ?? null }; },
  async saveMemo(studentId, memo) { await wait(100); db.memos[studentId] = memo; commit(); },

  async createDraft(studentId) {
    await wait(800); // 초안 생성 시간 흉내 (실제로는 LLM, 실패하면 아래 템플릿으로 폴백)
    const r = allResults().find((x) => x.id === studentId)!;
    const m = db.memos[studentId] ?? EMPTY_MEMO;
    const lines: string[] = [];
    if (m.covered) lines.push(`오늘 수업에서는 ${m.covered}${objectParticle(m.covered)} 다뤘어요.`);
    if (r.done) lines.push(`앱에서는 ${r.unit} ${r.solved}문제를 ${r.difficulty} 난이도로 풀었고, 힌트는 ${r.hints}번 봤어요.`);
    else lines.push('오늘 앱 학습은 아직 하지 않았어요.');
    if (m.stuck) lines.push(`${m.stuck} 부분을 조금 어려워했어요.`);
    if (m.homework) lines.push(`숙제는 ${m.homework}입니다.`);
    if (m.note) lines.push(m.note);
    const d: Draft = {
      studentId, studentName: r.name, scope: r.unit,
      amount: r.done ? `${r.solved}/${r.total}문제 · ${r.difficulty}` : '미완료',
      mode: r.done ? `힌트 ${r.hints}번` : '-', comment: lines.join(' '), status: '승인 대기',
    };
    db.drafts[studentId] = d; commit();
    return d;
  },
  async updateDraft(studentId, comment) {
    await wait(100);
    db.drafts[studentId] = { ...db.drafts[studentId], comment, status: '승인 대기' };
    commit();
    return db.drafts[studentId];
  },
  async approveDraft(studentId) {
    await wait(150);
    db.drafts[studentId] = { ...db.drafts[studentId], status: '승인됨' };
    commit();
    return db.drafts[studentId];
  },
  async getResults() { await wait(); myStudents().forEach((id) => tick(id)); return allResults(); },
  // 학습지도자에게는 긴급만, 분류 없이 (BRIEF 안전 알림 정책 1, 화면 구성 2)
  async getTeacherAlerts() { await wait(); const mine = new Set(myStudents()); return db.alerts.filter((a) => a.level === '긴급' && mine.has(a.studentId)).map((a) => ({ id: a.id, studentName: a.studentName, at: a.at, status: a.status })); },

  /* ---------- 보호자 ---------- */
  async getGuardianToday() {
    await wait();
    const cid = childId();
    const L = learner(cid);
    const d = L.days.find((x) => x.date === today());
    const keys = weekKeys();
    const done = new Set(L.days.map((x) => x.date));
    const draft = db.drafts[cid];
    return {
      childName: fullName(cid), dateLabel: dateLabel(), done: !!d, unit: d?.unit ?? db.tasks[cid] ?? '-', solved: d?.solved ?? 0,
      streak: streak(L.days), hardPoint: d?.hardPoint ?? null, line: d?.line ?? null, quiz: d?.quiz ?? null,
      teacherComment: draft?.status === '승인됨' ? draft.comment : null, // 승인된 코멘트만 공개
      attendance: keys.map((k) => done.has(k)), todayIndex: mondayIndex(),
    };
  },
  async getAlerts() { await wait(); const cid = childOf(currentUserId() ?? '') ; return db.alerts.filter((a) => a.studentId === cid).map(({ studentName: _n, studentId: _i, ...a }) => a); },
  async ackAlert(id) {
    await wait(120);
    db.alerts = db.alerts.map((a) => (a.id === id && a.status === '미확인' ? { ...a, status: '확인함' } : a));
    commit();
    const { studentName: _n, studentId: _i, ...a } = db.alerts.find((x) => x.id === id)!;
    return a;
  },
  async closeAlert(id, reason) {
    await wait(120);
    const a = db.alerts.find((x) => x.id === id)!;
    // 긴급은 '확인했어요' 뒤에만 닫을 수 있다 (BRIEF v2 검토 후 확정 1)
    if (a.level === '긴급' && a.status === '미확인') throw new Error('긴급 알림은 먼저 확인해 주세요.');
    db.alerts = db.alerts.map((x) => (x.id === id ? { ...x, status: '닫음', closeReason: reason } : x));
    commit();
    const { studentName: _n, studentId: _i, ...rest } = db.alerts.find((x) => x.id === id)!;
    return rest;
  },

  /* ---------- 시연 ---------- */
  async getDemo() { return db.settings; },
  async setDemo(settings) { db.settings = settings; commit(); return db.settings; },
  async resetDemo() { db = seed(); commit(); resetOrg(); },

  /* ---------- v0.4 계정·학원·강의실·씨앗 (org.ts) ---------- */
  ...orgApi,
};
