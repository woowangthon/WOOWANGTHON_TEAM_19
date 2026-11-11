// 진짜 서버(FastAPI)에 붙는 구현.
// 경로는 임시 이름이다. 성호님 명세의 API 이름이 확정되면 여기 경로만 바꾸면 된다(화면 코드는 그대로).
import type { MentorApi } from './client';
import type { AccountRole } from '../types';

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000';

// 시연 서버의 「누구인지」 헤더(로그인 서버화 전 임시). 로그인한 계정의 역할을 state/auth.tsx가 알려 준다.
// 누구 id를 쓸지는 방문자별 체험 세트(명세 4.11 2)가 정한다: 처음 서버를 쓸 때 POST /trial로 받아 localStorage에 둔다.
type DemoRole = 'child' | 'guardian' | 'instructor';
const ROLES: DemoRole[] = ['child', 'guardian', 'instructor'];
const ROLE_KEY = 'ai-mentor-demo-role';
const TRIAL_KEY = 'ai-mentor-trial';
interface Trial { trialId: string; actors: Record<DemoRole, string>; date: string; }

function readRole(): DemoRole | null {
  try { const v = localStorage.getItem(ROLE_KEY); return v && (ROLES as string[]).includes(v) ? (v as DemoRole) : null; } catch { return null; }
}
// 새로고침 직후 getMe보다 먼저 나가는 요청(오늘 세션·멘토)도 헤더를 달도록 마지막 역할을 기억해 둔다
let demoRole: DemoRole | null = readRole();

/** 로그인·getMe·로그아웃 때 부른다. student→child, guardian→guardian, teacher→instructor, 그 밖·로그아웃은 null. 바뀌었으면 true */
export function setDemoRole(role: AccountRole | null): boolean {
  const before = demoRole;
  demoRole = role === 'student' ? 'child' : role === 'guardian' ? 'guardian' : role === 'teacher' ? 'instructor' : null;
  try { if (demoRole) localStorage.setItem(ROLE_KEY, demoRole); else localStorage.removeItem(ROLE_KEY); } catch { /* 저장이 막혀도 이번 실행은 메모리로 */ }
  return demoRole !== before;
}

/* ---------- 체험 세트 ---------- */
function readTrial(): Trial | null {
  try {
    const v = JSON.parse(localStorage.getItem(TRIAL_KEY) ?? 'null') as Trial | null;
    return v && typeof v.trialId === 'string' && ROLES.every((r) => typeof v.actors?.[r] === 'string') ? v : null;
  } catch { return null; }
}
let trial: Trial | null = readTrial();      // 저장이 막혀도(사생활 모드) 이번 실행은 이 메모리 값으로
let trialPending: Promise<Trial> | null = null; // 받는 중인 요청(동시에 여러 요청이 와도 세트는 한 번만 받는다)

function dropTrial() {
  trial = null;
  try { localStorage.removeItem(TRIAL_KEY); } catch { /* 메모리만 비운다 */ }
}

async function errorMessage(res: Response): Promise<string> {
  const detail = await res.json().then((j) => (j?.message ?? j?.detail) as string | undefined).catch(() => undefined);
  return detail ?? `서버 오류가 났어요 (${res.status})`;
}

/** 저장된 세트를 쓰고, 없으면 POST /trial(본문·헤더 없음)로 받아 둔다. 429(과부하)면 서버 문구 그대로 오류 */
function ensureTrial(): Promise<Trial> {
  if (trial) return Promise.resolve(trial);
  if (trialPending) return trialPending;
  trialPending = (async () => {
    let res: Response;
    try { res = await fetch(BASE + '/trial', { method: 'POST' }); }
    catch { throw new Error('서버에 연결하지 못했어요. 인터넷 연결을 확인해 주세요.'); }
    if (!res.ok) throw new Error(await errorMessage(res));
    const t = (await res.json()) as Trial;
    trial = t;
    try { localStorage.setItem(TRIAL_KEY, JSON.stringify(t)); } catch { /* 메모리로 */ }
    return t;
  })().finally(() => { trialPending = null; });
  return trialPending;
}

/** 「처음부터 다시 체험」: 지금 세트를 버리고 새 세트를 받는다(이전 세트는 서버에 그대로 두고 버린다). 로그인 전에도 부를 수 있다 */
export async function startNewTrial(): Promise<void> {
  dropTrial();
  await ensureTrial();
}

/** 세트가 서버에 없을 때(DB가 바뀜)의 404. 학습지도자의 student_not_found는 주소 속 학생 이야기라 제외하고,
 *  학습지도자는 서버가 따로 주는 trial_not_found(세트 아이가 없음)로 안다 */
const isTrialGone = (role: DemoRole, code: unknown) =>
  code === 'trial_not_found' ||
  (role === 'child' && code === 'student_not_found') || (role === 'guardian' && (code === 'student_not_found' || code === 'guardian_not_found'));

async function call<T>(method: 'GET' | 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown, retried = false): Promise<T> {
  // 로그인 전에는 서버가 누구인지 알 수 없어 401이 난다 → 보내지 않는다(화면은 오류를 받아 null로 둔다)
  const role = demoRole;
  if (!role) throw new Error('로그인이 필요해요.');
  const t = await ensureTrial();
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: { 'X-Demo-Role': role, 'X-Demo-Actor': t.actors[role], ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('서버에 연결하지 못했어요. 인터넷 연결을 확인해 주세요.');
  }
  if (res.status === 404 && !retried) {
    const j = await res.clone().json().catch(() => null);
    if (isTrialGone(role, j?.code)) {
      // 같은 세트로 실패한 요청이 여럿이어도 한 번만 버린다(이미 새 세트면 그걸 쓴다)
      if (trial?.trialId === t.trialId) dropTrial();
      return call<T>(method, path, body, true);
    }
  }
  if (!res.ok) throw new Error(await errorMessage(res));
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const httpApi: MentorApi = {
  getStudentHome: () => call('GET', '/student/home'),
  acceptPromise: () => call('POST', '/student/promise'),
  // 앱 시작 때 역할과 상관없이 불리는 두 함수: 학생이 아니면 mock처럼 null(서버는 403)
  getMentor: () => (demoRole === 'child' ? call('GET', '/student/mentor') : Promise.resolve(null)),
  saveMentor: (s) => call('PUT', '/student/mentor', s),

  getActiveSession: () => (demoRole === 'child' ? call('GET', '/sessions/active') : Promise.resolve(null)),
  startSession: (difficulty) => call('POST', '/sessions', { difficulty }),
  getProblem: (id) => call('GET', `/sessions/${id}/problem`),
  submitAnswer: (id, problemId, numerator, denominator) => call('POST', `/sessions/${id}/answer`, { problemId, numerator, denominator }),
  requestHint: (id, problemId) => call('POST', `/sessions/${id}/hint`, { problemId }),
  showSolution: (id, problemId) => call('POST', `/sessions/${id}/solution`, { problemId }),
  afterStudy: (id, choice) => call('POST', `/sessions/${id}/after-study`, { choice }),
  getChat: (id) => call('GET', `/sessions/${id}/chat`),
  sendChat: (id, texts) => call('POST', `/sessions/${id}/chat`, { texts }),
  replyChat: (id) => call('POST', `/sessions/${id}/reply`),
  endChat: (id) => call('POST', `/sessions/${id}/chat/end`),
  getWrap: (id) => call('GET', `/sessions/${id}/wrap`),
  submitWrap: (id, body) => call('POST', `/sessions/${id}/wrap`, body),
  getRecords: () => call('GET', '/student/records'),

  getUnits: () => call('GET', '/teacher/units'),
  saveUnits: (selectedIds) => call('PUT', '/teacher/units', { selectedIds }),
  getTeacherToday: () => call('GET', '/teacher/today'),
  assignTask: (studentId, unit) => call('PUT', `/teacher/students/${studentId}/task`, { unit }),
  getMemo: (studentId) => call('GET', `/teacher/students/${studentId}/memo`),
  saveMemo: (studentId, memo) => call('PUT', `/teacher/students/${studentId}/memo`, memo),
  createDraft: (studentId) => call('POST', `/teacher/students/${studentId}/draft`),
  updateDraft: (studentId, comment) => call('PUT', `/teacher/students/${studentId}/draft`, { comment }),
  approveDraft: (studentId) => call('POST', `/teacher/students/${studentId}/draft/approve`),
  getResults: () => call('GET', '/teacher/results'),
  getTeacherAlerts: () => call('GET', '/teacher/alerts'),

  getGuardianToday: () => call('GET', '/guardian/today'),
  getAlerts: () => call('GET', '/guardian/alerts'),
  ackAlert: (id) => call('POST', `/guardian/alerts/${id}/ack`),
  closeAlert: (id, reason) => call('POST', `/guardian/alerts/${id}/close`, { reason }),

  /* v0.4 계정·학원·강의실·씨앗 — 임시 경로. 로그인 토큰(쿠키)은 서버가 정한다 */
  getMe: () => call('GET', '/me'),
  login: (loginId, password, remember) => call('POST', '/auth/login', { loginId, password, remember }),
  checkLoginId: (loginId) => call('GET', `/auth/check-id?loginId=${encodeURIComponent(loginId)}`),
  signup: (body) => call('POST', '/auth/signup', body),
  logout: () => call('POST', '/auth/logout'),
  findLoginId: (email) => call('POST', '/auth/find-id', { email }),
  requestPasswordReset: (loginId, email) => call('POST', '/auth/reset-password', { loginId, email }),
  updateProfile: (patch) => call('PUT', '/me', patch),
  changePassword: (current, next) => call('PUT', '/me/password', { current, next }),
  saveSettings: (settings) => call('PUT', '/me/settings', settings),
  deleteAccount: (password) => call('POST', '/me/delete', { password }),
  resetChildPassword: (childId, next) => call('PUT', `/guardian/children/${childId}/password`, { next }),
  getNotices: () => call('GET', '/notices'),
  readNotices: () => call('POST', '/notices/read'),
  requestMembership: (serial) => call('POST', '/teacher/membership', { serial }),
  leaveMembership: () => call('DELETE', '/teacher/membership'),
  applyAcademy: (form) => call('POST', '/teacher/academy-applications', form),
  demoAccounts: () => call('GET', '/demo/accounts'),
  demoLogin: (userId) => call('POST', '/demo/login', { userId }),
  linkWith: (code, consent) => call('POST', '/links', { code, consent }),
  confirmLink: (studentId, consent) => call('POST', `/links/${studentId}/confirm`, { consent }),
  joinAcademy: (code) => call('POST', '/academy/join', { code }),
  getOwnerDashboard: () => call('GET', '/owner/dashboard'),
  issueEntryCode: () => call('POST', '/owner/entry-code'),
  approveTeachers: (ids) => call('POST', '/owner/teachers/approve', { ids }),
  getApplications: () => call('GET', '/operator/applications'),
  reviewApplication: (id, decision, reason) => call('POST', `/operator/applications/${id}/review`, { decision, reason }),
  getTeacherClasses: () => call('GET', '/teacher/classes'),
  createClassroom: (name, plan) => call('POST', '/teacher/classes', { name, plan }),
  inviteStudent: (classId, studentId) => call('POST', `/teacher/classes/${classId}/invites`, { studentId }),
  answerRequest: (classId, studentId, accept) => call('POST', `/teacher/classes/${classId}/requests/${studentId}`, { accept }),
  getStudentClasses: () => call('GET', '/student/classes'),
  requestJoin: (classId) => call('POST', `/student/classes/${classId}/request`),
  acceptInvite: (classId, accept) => call('POST', `/student/classes/${classId}/invite`, { accept }),
  getWallet: () => call('GET', '/student/wallet'),
  getStudentShop: () => call('GET', '/student/shop'),
  buyAcademyItem: (itemId) => call('POST', `/student/shop/items/${itemId}/buy`),
  buyCosmetic: (id) => call('POST', `/student/shop/cosmetics/${id}/buy`),
  equipOutfit: (id) => call('PUT', '/student/outfit', { id }),
  getStampState: () => call('GET', '/guardian/stamp'),
  stamp: () => call('POST', '/guardian/stamp'),
  getSeedBoard: () => call('GET', '/teacher/seeds'),
  grantSeeds: (studentId, amount, note) => call('POST', `/teacher/seeds/${studentId}`, { amount, note }),
  saveShopItem: (item) => (item.id ? call('PUT', `/teacher/shop/items/${item.id}`, item) : call('POST', '/teacher/shop/items', item)),
  deliverOrder: (orderId) => call('POST', `/teacher/orders/${orderId}/deliver`),

  resetDemo: () => call('POST', '/demo/reset'),
};
