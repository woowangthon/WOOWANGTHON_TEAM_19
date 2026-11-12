// 가짜 서버(2) — 계정(로그인·가입·설정·알림)·학원·강의실·씨앗·상점. (BRIEF "v0.4 회의 확정"·"v0.5", docs/DEV-RULES.md)
// · 학습(문제·수다)은 mock.ts, 사람·조직·재화는 이 파일. 둘 다 "서버가 판단할 규칙"을 그대로 담고 있다.
// · 백엔드(성호님)는 이 파일의 규칙(throw 하는 곳)을 그대로 서버 검증으로 옮기면 된다.
// · 한계: User.academyId가 하나라 보호자는 학원 1곳에만 속한다(아이 둘이 서로 다른 학원이면 보호자는 먼저 들어간 곳). 자세한 건 enrollLinked 위 주석.
import type {
  AcademyApplication, AcademyForm, AccountRole, AppNotice, Classroom, ClassTimer, ClassTimerStart, Cosmetic, EntryCode, Grade, Me, NotifySettings, Order, OrgType, OwnerDashboard, PersonRow,
  SeedBoard, SeedEntry, SeedSource, ShopItem, SignupBody, StampState, StudentClasses, StudentShop, TeacherClasses, Wallet,
} from '../types';
import { ymd, stampLabel, weekKeys } from '../lib/date';
import { load, save } from '../lib/storage';
import { gradeLabel } from '../lib/grade';

/** 학년 값 검사: 1~12 정수만 (가짜 서버도 진짜 서버처럼 입력을 믿지 않는다) */
const isGrade = (g: unknown): g is Grade => Number.isInteger(g) && (g as number) >= 1 && (g as number) <= 12;

/* ================= 규칙 숫자 (한곳에서 조정) ================= */
export const SEED_RULES = {
  studyDone: 3,          // 하루 학습 완료 (하루 1번)
  guardianStamp: 2,      // 보호자 도장 (하루 1번, 아이 1명당)
  teacherMax: 5,         // 학습지도자 칭찬 1번에 최대
  teacherDailyCap: 10,   // 학습지도자 칭찬 학생 1명 하루 최대
  entryCodeMin: 10,      // 학원 입장 코드 유효 시간(분)
};
/** 아이디·비밀번호 규칙 (화면 안내 문구와 같이 바꿀 것) */
export const ID_RULE = /^[a-z][a-z0-9_]{3,15}$/;           // 영문 소문자로 시작, 4~16자(소문자·숫자·_)
export const PW_RULE = /^(?=.*[A-Za-z])(?=.*\d).{8,20}$/;  // 8~20자, 영문+숫자
const DEFAULT_SETTINGS: NotifySettings = { studyReminder: '17:00', learnDone: true, activity: true, marketing: false };

/* ================= "DB" ================= */
interface User {
  id: string; role: AccountRole; name: string;
  loginId: string; pw: string;               // pw: 가짜 해시. 진짜 서버는 bcrypt/argon2로 저장할 것
  email?: string;
  settings: NotifySettings;
  agreedAt?: string; marketing?: boolean;
  grade?: Grade;
  linkCode: string | null;
  academyId: string | null;
  teacherStatus?: '승인 대기' | '승인됨';
  applicationId?: string;
}
interface Link { studentId: string; guardianId: string; status: '대기' | '연결됨'; consentAt: string | null; }
interface Academy { id: string; name: string; orgType: OrgType; serial: string; ownerId: string; entryCode: EntryCode | null; }
interface Notice { id: string; userId: string; at: string; text: string; to: string | null; read: boolean; }
interface Room { id: string; academyId: string; teacherId: string; name: string; plan: string; members: string[]; invited: string[]; requests: string[]; timer?: ClassTimer | null; }
interface Ledger { id: string; studentId: string; date: string; at: string; amount: number; source: SeedSource; note: string; by: string; }
interface Item extends ShopItem { teacherId: string; }
interface OrderRow { id: string; studentId: string; teacherId: string; itemName: string; price: number; at: string; status: Order['status']; }
interface CosmeticDef { id: string; kind: Cosmetic['kind']; name: string; price: number; }

interface OrgDB {
  version: 2;
  me: string | null;                     // 이 기기에 로그인한 사람
  remember: boolean;                     // 자동 로그인: false면 앱을 다시 열 때 로그아웃
  notices: Notice[];                     // 알림함
  users: User[];
  links: Link[];
  applications: (AcademyApplication & { ownerId: string })[];
  academies: Academy[];
  rooms: Room[];
  ledger: Ledger[];
  items: Item[];
  orders: OrderRow[];
  owned: Record<string, string[]>;       // 학생 id → 가진 꾸미기 id
  equipped: Record<string, string | null>; // 학생 id → 입은 옷 id
}

const KEY = 'aimentor:org';

/** 우리가 파는 꾸미기(옷·이모티콘). 그림은 public/mascot/{animal}/outfit-{id}.png · emote-{id}.png (GPT 제작 예정) */
export const COSMETICS: CosmeticDef[] = [
  { id: 'glasses', kind: 'outfit', name: '공부 안경', price: 10 },
  { id: 'raincoat', kind: 'outfit', name: '노란 우비', price: 15 },
  { id: 'scarf', kind: 'outfit', name: '겨울 목도리', price: 20 },
  { id: 'cape', kind: 'outfit', name: '별 망토', price: 25 },
  { id: 'thumbs', kind: 'emote', name: '엄지 척', price: 8 },
  { id: 'thanks', kind: 'emote', name: '고마워', price: 8 },
  { id: 'sleepy', kind: 'emote', name: '졸려', price: 8 },
  { id: 'best', kind: 'emote', name: '최고야', price: 12 },
];

/** 시연 계정 비밀번호(모두 같음) — 체험 계정 시트에 표시 */
export const DEMO_PASSWORD = 'demo1234';
function U(id: string, role: AccountRole, name: string, loginId: string, extra: Partial<User> = {}): User {
  return { id, role, name, loginId, pw: hash(DEMO_PASSWORD), linkCode: null, academyId: null, settings: { ...DEFAULT_SETTINGS }, ...extra };
}
/** 가짜 해시(시연용). 진짜 서버에서는 절대 이렇게 하지 말 것 */
function hash(pw: string) { let h = 7; for (const c of pw) h = (h * 31 + c.charCodeAt(0)) >>> 0; return 'h' + h.toString(36); }

function seed(): OrgDB {
  const d = (n: number) => { const x = new Date(); x.setDate(x.getDate() - n); return x; };
  const L = (n: number, amount: number, source: SeedSource, note: string, by: string, i: number): Ledger =>
    ({ id: `l${i}`, studentId: 's1', date: ymd(d(n)), at: stampLabel(d(n).setHours(18, 10)), amount, source, note, by });
  return {
    version: 2,
    me: null, remember: true,
    notices: [
      { id: 'n1', userId: 'g1', at: stampLabel(new Date().setHours(9, 0)), text: '김선생님이 지우의 이번 주 범위를 정했어요: 분수의 덧셈·뺄셈', to: null, read: false },
      { id: 'n2', userId: 's1', at: stampLabel(new Date().setHours(9, 0)), text: '보호자가 어제 도장을 찍어 줬어! 씨앗 +2', to: '/student/shop', read: false },
      { id: 'n3', userId: 'own1', at: stampLabel(new Date().setHours(10, 0)), text: '이선생님이 소속을 신청했어요', to: '/owner', read: false },
      { id: 'n4', userId: 't1', at: stampLabel(new Date().setHours(16, 40)), text: '이민준이 「칭찬 간식 쿠폰」 교환을 요청했어요', to: '/teacher/seeds', read: false },
    ],
    users: [
      U('op', 'operator', '우왕 운영팀', 'operator', { email: 'ops@example.com' }),
      U('own1', 'teacher', '박원장', 'park_owner', { academyId: 'a1', teacherStatus: '승인됨', applicationId: 'app1', email: 'park@example.com' }),
      U('own2', 'teacher', '최원장', 'choi_owner', { applicationId: 'app2', email: 'choi@example.com' }),
      U('t1', 'teacher', '김선생님', 'kim_teacher', { academyId: 'a1', teacherStatus: '승인됨', email: 'kim@example.com' }),
      U('t2', 'teacher', '이선생님', 'lee_teacher', { academyId: 'a1', teacherStatus: '승인 대기', email: 'lee@example.com' }),
      U('t3', 'teacher', '정선생님', 'jung_teacher', { email: 'jung@example.com' }),
      U('s1', 'student', '지우', 'jiwoo', { grade: 4, linkCode: 'JW4K7P', academyId: 'a1' }),
      U('s2', 'student', '이민준', 'minjun', { grade: 4, linkCode: 'MJ8Q2X', academyId: 'a1' }),
      U('s3', 'student', '박서연', 'seoyeon', { grade: 4, linkCode: 'SY3N6R', academyId: 'a1' }),
      U('s4', 'student', '최하린', 'harin', { grade: 4, linkCode: 'HR5T9W', academyId: 'a1' }),
      U('g1', 'guardian', '지우 보호자', 'jiwoo_mom', { linkCode: 'PG2M8C', academyId: 'a1', email: 'mom@example.com' }),
    ],
    links: [{ studentId: 's1', guardianId: 'g1', status: '연결됨', consentAt: ymd(d(20)) }],
    applications: [
      { id: 'app1', ownerId: 'own1', ownerName: '박원장', orgType: '학원', academyName: '우왕수학학원', bizNo: '123-45-67890', ceo: '박원장', phone: '043-000-0000', address: '충북 청주시 서원구', status: '승인', appliedAt: stampLabel(d(30).getTime()), serial: 'WW7K-3P9Q', rejectReason: null },
      { id: 'app2', ownerId: 'own2', ownerName: '최원장', orgType: '학원', academyName: '새싹영어학원', bizNo: '234-56-78901', ceo: '최원장', phone: '043-111-1111', address: '충북 청주시 흥덕구', status: '심사 중', appliedAt: stampLabel(d(0).setHours(9, 30)), serial: null, rejectReason: null },
    ],
    academies: [{ id: 'a1', name: '우왕수학학원', orgType: '학원', serial: 'WW7K-3P9Q', ownerId: 'own1', entryCode: null }],
    rooms: [
      { id: 'c1', academyId: 'a1', teacherId: 't1', name: '4학년 A반', plan: '분수의 덧셈·뺄셈 (11월)', members: ['s1', 's2', 's3'], invited: [], requests: [] },
      { id: 'c2', academyId: 'a1', teacherId: 't1', name: '4학년 심화반', plan: '분수 응용 문제', members: [], invited: [], requests: ['s4'] },
    ],
    ledger: [
      L(3, 3, '학습 완료', '분수의 덧셈', 'system', 1), L(3, 2, '보호자 도장', '오늘 이야기를 나눴어요', 'g1', 2),
      L(2, 3, '학습 완료', '분수의 덧셈', 'system', 3), L(2, 5, '학습지도자 칭찬', '단원평가 100점', 't1', 4),
      L(1, 3, '학습 완료', '분수의 덧셈', 'system', 5), L(1, 2, '보호자 도장', '오늘 이야기를 나눴어요', 'g1', 6),
      { id: 'l7', studentId: 's2', date: ymd(d(1)), at: stampLabel(d(1).getTime()), amount: 24, source: '학습 완료', note: '지난 기록', by: 'system' },
      { id: 'l8', studentId: 's2', date: ymd(d(0)), at: stampLabel(d(0).getTime()), amount: -20, source: '상점 구매', note: '칭찬 간식 쿠폰', by: 's2' },
      { id: 'l9', studentId: 's3', date: ymd(d(1)), at: stampLabel(d(1).getTime()), amount: 11, source: '학습 완료', note: '지난 기록', by: 'system' },
    ],
    items: [
      { id: 'i1', teacherId: 't1', name: '칭찬 간식 쿠폰', price: 20, stock: 10, visible: true, note: '수업 끝나고 과자 1개' },
      { id: 'i2', teacherId: 't1', name: '자리 고르기권', price: 15, stock: null, visible: true, note: '다음 수업 자리를 내가 골라요' },
      { id: 'i3', teacherId: 't1', name: '보드게임 10분', price: 25, stock: 5, visible: true, note: '금요일 수업 끝에' },
      { id: 'i4', teacherId: 't1', name: '겨울방학 특별 선물', price: 40, stock: 3, visible: false, note: '12월에 공개 예정' },
    ],
    orders: [{ id: 'o1', studentId: 's2', teacherId: 't1', itemName: '칭찬 간식 쿠폰', price: 20, at: stampLabel(d(0).setHours(16, 40)), status: '교환 요청' }],
    owned: { s1: ['glasses'] },
    equipped: { s1: null },
  };
}

let db: OrgDB = (() => {
  const s = load<OrgDB | null>(KEY, null);
  if (!s || s.version !== 2) return seed();
  if (!s.remember) s.me = null; // 자동 로그인을 끈 채로 앱을 다시 열면 로그인 화면부터
  return s;
})();
const commit = () => save(KEY, db);
export function resetOrg(keepLogin = false) { const me = db.me; db = seed(); if (keepLogin) db.me = me; commit(); }

/* ================= 도우미 ================= */
const CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // 헷갈리는 0·O·1·I 제외
function rand(n: number, chars = CODE_CHARS) {
  const a = new Uint32Array(n);
  try { crypto.getRandomValues(a); } catch { for (let i = 0; i < n; i++) a[i] = Math.floor(Math.random() * 1e9); }
  return Array.from(a, (x) => chars[x % chars.length]).join('');
}
function uniqueLinkCode() { let c = rand(6); while (db.users.some((u) => u.linkCode === c)) c = rand(6); return c; }
function uniqueSerial() { let c = `${rand(4)}-${rand(4)}`; while (db.academies.some((a) => a.serial === c)) c = `${rand(4)}-${rand(4)}`; return c; }
const norm = (s: string) => s.replace(/[\s-]/g, '').toUpperCase();
const today = () => ymd();
const fail = (msg: string): never => { throw new Error(msg); };
/** 알림함에 넣기 */
function notify(userId: string, text: string, to: string | null = null) {
  db.notices.unshift({ id: 'n' + Date.now().toString(36) + rand(3), userId, at: stampLabel(Date.now()), text, to, read: false });
}
const ownedAcademy = (u: User) => db.academies.find((a) => a.ownerId === u.id) ?? null;
/** 원장 = 자기가 등록해 승인받은 학원·학교가 있는 학습지도자 */
function mustOwner(): User { const u = must('teacher'); if (!ownedAcademy(u)) fail('학원·학교 관리자(원장)만 쓸 수 있어요.'); return u; }

export const userById = (id: string) => db.users.find((u) => u.id === id);
export const nameOf = (id: string) => userById(id)?.name ?? '알 수 없음';
function meUser(): User { const u = db.me ? userById(db.me) : undefined; return u ?? fail('로그인이 필요해요.'); }
function must(role: AccountRole | AccountRole[]): User {
  const u = meUser();
  const roles = Array.isArray(role) ? role : [role];
  if (!roles.includes(u.role)) fail('이 기능은 ' + roles.join('·') + ' 화면에서만 쓸 수 있어요.');
  return u;
}
const connected = (u: User) => db.links.filter((l) => l.status === '연결됨' && (l.studentId === u.id || l.guardianId === u.id))
  .map((l) => userById(l.studentId === u.id ? l.guardianId : l.studentId)!).filter(Boolean);

/** 학생: 연결된 보호자가 없으면 제한 모드 (만 14세 미만 → 보호자 동의 전에는 학원·수다 막음) */
export const isRestricted = (studentId: string) => { const u = userById(studentId); return !!u && u.role === 'student' && connected(u).length === 0; };

function meView(u: User): Me {
  const ac = u.academyId ? db.academies.find((a) => a.id === u.academyId) : null;
  const pending = db.links.filter((l) => l.status === '대기' && (l.studentId === u.id || l.guardianId === u.id))
    .map((l) => userById(l.studentId === u.id ? l.guardianId : l.studentId)!).filter(Boolean);
  const app = u.applicationId ? db.applications.find((a) => a.id === u.applicationId) ?? null : null;
  return {
    id: u.id, role: u.role, name: u.name, loginId: u.loginId, email: u.email ?? null, grade: u.grade ?? null, linkCode: u.linkCode,
    linked: connected(u).map((x) => ({ id: x.id, name: x.name, role: x.role })),
    pendingLinks: pending.map((x) => ({ id: x.id, name: x.name, role: x.role })),
    academy: ac && (u.role !== 'teacher' || u.teacherStatus === '승인됨') ? { id: ac.id, name: ac.name } : null,
    membership: u.role === 'teacher' && ac ? { academyId: ac.id, name: ac.name, orgType: ac.orgType, status: u.teacherStatus ?? '승인 대기', isOwner: ac.ownerId === u.id } : null,
    application: app ? (({ ownerId: _o, ...rest }) => rest)(app) : null,
    restricted: u.role === 'student' && isRestricted(u.id),
    outfit: u.role === 'student' ? db.equipped[u.id] ?? null : null,
    settings: u.settings,
  };
}

/* ---------- 학원 자동 등록 ("학생·보호자 중 한 명만 넣어도 연결된 쪽도 등록", 11-10 회의 → 11-11 수정) ----------
 * · 자동 등록은 연결된 한 쌍(학생 ↔ 보호자)까지만. 보호자를 거쳐 다른 아이(형제)로 넘어가지 않는다.
 * · 학생 → 보호자: 그 학생과 연결된 보호자 중 학원이 없는 사람만 같이 등록.
 * · 보호자 → 아이: 그 보호자에게 연결된 아이가 딱 1명일 때만. 2명 이상이면 아이는 그대로 두고 보호자에게 안내 알림.
 * · 충돌: 대상이 이미 다른 학원이면 덮어쓰지 않고, 대상과 시작한 사람 둘 다에게 알림. 같은 학원이면 아무 일 없음.
 * · 한계: User.academyId가 하나라 보호자는 학원 1곳에만 속한다(아이 둘이 다른 학원이면 보호자는 먼저 들어간 학원).
 *   서버로 옮길 때 보호자-학원을 여러 개로 둘지 결정할 것. */
const academyName = (id: string) => db.academies.find((a) => a.id === id)?.name ?? '다른 학원';
/** 학생에겐 반말, 어른에겐 존댓말 */
const say = (u: User, kid: string, adult: string) => (u.role === 'student' ? kid : adult);
/** target을 academyId에 자동 등록. 이미 다른 학원이면 바꾸지 않고 target·starter 둘 다에게 알림 */
function enrollLinked(target: User, academyId: string, starter: User) {
  if (target.academyId === academyId) return;
  if (!target.academyId) { target.academyId = academyId; return; }
  const have = academyName(target.academyId), want = academyName(academyId);
  notify(target.id, say(target,
    `이미 「${have}」에 등록되어 있어서 「${want}」에 자동으로 옮기지 않았어.`,
    `이미 「${have}」에 등록되어 있어 「${want}」에 자동으로 옮기지 않았어요.`));
  const who = target.role === 'student' ? `아이 ${target.name}은(는)` : `보호자 ${target.name}님은`;
  notify(starter.id, say(starter,
    `${who} 이미 「${have}」에 등록되어 있어서 「${want}」에 자동으로 옮기지 않았어.`,
    `${who} 이미 「${have}」에 등록되어 있어 「${want}」에 자동으로 옮기지 않았어요.`));
}
/** 학생 → 연결된 보호자들 */
function spreadFromStudent(s: User, academyId: string) {
  connected(s).filter((x) => x.role === 'guardian').forEach((g) => enrollLinked(g, academyId, s));
}
/** 보호자 → 아이: 연결된 아이가 1명일 때만. 2명 이상이면 안내만 */
function spreadFromGuardian(g: User, academyId: string) {
  const kids = connected(g).filter((x) => x.role === 'student');
  if (kids.length === 1) enrollLinked(kids[0], academyId, g);
  else if (kids.some((k) => k.academyId !== academyId))
    notify(g.id, `아이가 여러 명이라 아이들의 학원은 자동으로 등록하지 않았어요. 아이마다 아이 계정에서 학원 코드를 넣어 주세요.`, '/settings/family');
}
/** 새로 연결된 한 쌍의 학원 맞추기: 학생에게 학원이 있으면 학생 → 보호자, 없으면 보호자 → 아이 규칙 */
function syncLinkedPair(s: User, g: User) {
  if (s.academyId) enrollLinked(g, s.academyId, s);
  else if (g.academyId) spreadFromGuardian(g, g.academyId);
}

/* ---------- 학습(mock.ts)에서 쓰는 연결점 ---------- */
export const currentUserId = () => db.me;
export const currentRole = () => (db.me ? userById(db.me)?.role ?? null : null);
/** 보호자가 보는 아이: 연결된 첫 학생 */
export const childOf = (guardianId: string) => { const g = userById(guardianId); return g ? connected(g).find((x) => x.role === 'student')?.id ?? null : null; };
export const roomsOfTeacher = (teacherId: string) => db.rooms.filter((r) => r.teacherId === teacherId);
export const roomsOfStudent = (studentId: string) => db.rooms.filter((r) => r.members.includes(studentId));
export const teacherOfStudent = (studentId: string) => { const r = roomsOfStudent(studentId)[0]; return r ? nameOf(r.teacherId) : null; };
export const balanceOf = (studentId: string) => db.ledger.filter((l) => l.studentId === studentId).reduce((a, b) => a + b.amount, 0);
const earnedOn = (studentId: string, source: SeedSource, date = today()) =>
  db.ledger.filter((l) => l.studentId === studentId && l.source === source && l.date === date).reduce((a, b) => a + b.amount, 0);
function addSeed(studentId: string, amount: number, source: SeedSource, note: string, by: string) {
  db.ledger.push({ id: 'l' + Date.now() + rand(3), studentId, date: today(), at: stampLabel(Date.now()), amount, source, note, by });
}
/** 하루 학습 완료 → 씨앗 (하루 1번). 받은 양을 돌려준다 */
export function earnStudySeeds(studentId: string, unit: string): number {
  if (earnedOn(studentId, '학습 완료') > 0) return 0;
  addSeed(studentId, SEED_RULES.studyDone, '학습 완료', unit, 'system'); commit();
  return SEED_RULES.studyDone;
}
export const studySeedsToday = (studentId: string) => earnedOn(studentId, '학습 완료');

/* ---------- 화면 조각 ---------- */
const row = (id: string, sub?: string): PersonRow => ({ id, name: nameOf(id), sub });
function classroomView(r: Room): Classroom {
  return { id: r.id, name: r.name, plan: r.plan, teacherName: nameOf(r.teacherId), members: r.members.map((i) => row(i)), invited: r.invited.map((i) => row(i)), requests: r.requests.map((i) => row(i)), timer: r.timer ?? null };
}
function myTeacherItems(t: User) { return db.items.filter((i) => i.teacherId === t.id).map(({ teacherId: _t, ...i }) => i); }
const orderView = (o: OrderRow): Order => ({ id: o.id, studentName: nameOf(o.studentId), itemName: o.itemName, price: o.price, at: o.at, status: o.status });

function seedBoard(t: User): SeedBoard {
  const ids = [...new Set(roomsOfTeacher(t.id).flatMap((r) => r.members))];
  const week = new Set(weekKeys());
  return {
    students: ids.map((id) => ({
      id, name: nameOf(id), balance: balanceOf(id),
      earnedWeek: db.ledger.filter((l) => l.studentId === id && l.amount > 0 && week.has(l.date)).reduce((a, b) => a + b.amount, 0),
      grantedToday: earnedOn(id, '학습지도자 칭찬'),
    })),
    orders: db.orders.filter((o) => o.teacherId === t.id).sort((a, b) => (a.status === b.status ? b.id.localeCompare(a.id) : a.status === '교환 요청' ? -1 : 1)).map(orderView),
    items: myTeacherItems(t),
  };
}
function studentShop(s: User): StudentShop {
  const teacherIds = new Set(roomsOfStudent(s.id).map((r) => r.teacherId));
  const owned = db.owned[s.id] ?? [];
  return {
    balance: balanceOf(s.id),
    academyItems: db.items.filter((i) => teacherIds.has(i.teacherId) && i.visible).map(({ teacherId: _t, ...i }) => i),
    cosmetics: COSMETICS.map((c) => ({ ...c, owned: owned.includes(c.id), equipped: db.equipped[s.id] === c.id })),
    orders: db.orders.filter((o) => o.studentId === s.id).sort((a, b) => b.id.localeCompare(a.id)).map(orderView),
  };
}
function ownerDash(o: User): OwnerDashboard {
  const ac = ownedAcademy(o) ?? fail('아직 학원 승인 전이에요.');
  const inAc = db.users.filter((u) => u.academyId === ac.id);
  const code = ac.entryCode && ac.entryCode.expiresAt > Date.now() ? ac.entryCode : null;
  return {
    academy: { id: ac.id, name: ac.name, serial: ac.serial, orgType: ac.orgType },
    entryCode: code,
    pendingTeachers: inAc.filter((u) => u.role === 'teacher' && u.teacherStatus === '승인 대기').map((u) => row(u.id, '소속 신청')),
    teachers: inAc.filter((u) => u.role === 'teacher' && u.teacherStatus === '승인됨').map((u) => row(u.id, `${u.id === o.id ? '원장 · ' : ''}강의실 ${roomsOfTeacher(u.id).length}개`)),
    classrooms: db.rooms.filter((r) => r.academyId === ac.id).map((r) => ({ id: r.id, name: r.name, teacherName: nameOf(r.teacherId), count: r.members.length })),
    students: inAc.filter((u) => u.role === 'student').map((u) => row(u.id, `${gradeLabel(u.grade)} · ${roomsOfStudent(u.id).map((r) => r.name).join(', ') || '강의실 없음'}`)),
  };
}

/* ================= API ================= */
export const orgApi = {
  /* ---------- 계정: 로그인·가입·찾기 ---------- */
  async getMe(): Promise<Me | null> { const u = db.me ? userById(db.me) : undefined; return u ? meView(u) : null; },

  /** 아이디·비밀번호 로그인. remember=false면 앱을 다시 열 때 로그인 화면부터 */
  async login(loginId: string, password: string, remember = true): Promise<Me> {
    const u = db.users.find((x) => x.loginId === loginId.trim().toLowerCase());
    if (!u || u.pw !== hash(password)) fail('아이디 또는 비밀번호가 맞지 않아요.');
    db.me = u!.id; db.remember = remember; commit();
    return meView(u!);
  },
  /** 아이디 중복 확인: true = 쓸 수 있음 */
  async checkLoginId(loginId: string): Promise<boolean> {
    const id = loginId.trim().toLowerCase();
    if (!ID_RULE.test(id)) fail('아이디는 영문 소문자로 시작하는 4~16자(소문자·숫자·_)예요.');
    return !db.users.some((u) => u.loginId === id);
  },
  async signup(body: SignupBody): Promise<Me> {
    const name = body.name.trim();
    const loginId = body.loginId.trim().toLowerCase();
    if (!body.agreements.terms || !body.agreements.privacy) fail('필수 약관에 동의해 주세요.');
    if (!ID_RULE.test(loginId)) fail('아이디는 영문 소문자로 시작하는 4~16자(소문자·숫자·_)예요.');
    if (db.users.some((u) => u.loginId === loginId)) fail('이미 쓰는 아이디예요.');
    if (!PW_RULE.test(body.password)) fail('비밀번호는 영문과 숫자를 섞어 8~20자로 만들어 주세요.');
    if (!name) fail('이름을 적어 주세요.');
    if (name.length > 12) fail('이름은 12자까지 쓸 수 있어요.');
    if (body.role === 'student' && !isGrade(body.grade)) fail('학년을 골라 주세요.');
    if (body.role !== 'student' && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(body.email ?? '')) fail('이메일을 바르게 적어 주세요. 아이디·비밀번호를 찾을 때 써요.');
    const id = body.role[0] + Date.now().toString(36);
    const u: User = {
      id, role: body.role, name, loginId, pw: hash(body.password), linkCode: null, academyId: null,
      settings: { ...DEFAULT_SETTINGS, marketing: body.agreements.marketing, studyReminder: body.role === 'student' ? '17:00' : null },
      agreedAt: today(), marketing: body.agreements.marketing,
    };
    if (body.role === 'student') { u.grade = body.grade; u.linkCode = uniqueLinkCode(); }
    else u.email = body.email!.trim();
    if (body.role === 'guardian') u.linkCode = uniqueLinkCode();
    db.users.push(u); db.me = id; db.remember = true; commit();
    return meView(u);
  },
  async logout() { db.me = null; commit(); },
  /** 아이디 찾기(어른): 이메일 → 가린 아이디 */
  async findLoginId(email: string): Promise<string[]> {
    const list = db.users.filter((u) => u.email && u.email.toLowerCase() === email.trim().toLowerCase());
    if (!list.length) fail('그 이메일로 가입한 계정이 없어요.');
    return list.map((u) => u.loginId.slice(0, 3) + '*'.repeat(Math.max(1, u.loginId.length - 3)));
  },
  /** 비밀번호 찾기(어른): 아이디+이메일이 맞으면 재설정 메일(시연: 메일 대신 안내만). 학생은 보호자가 재설정 */
  async requestPasswordReset(loginId: string, email: string): Promise<'sent' | 'ask-guardian'> {
    const u = db.users.find((x) => x.loginId === loginId.trim().toLowerCase()) ?? fail('아이디를 찾지 못했어요.');
    if (u.role === 'student') return 'ask-guardian';
    if ((u.email ?? '').toLowerCase() !== email.trim().toLowerCase()) fail('아이디와 이메일이 맞지 않아요.');
    return 'sent';
  },
  /** 시연용 체험 계정 (아이디 + 공통 비밀번호) */
  async demoAccounts() {
    const pick: [string, string][] = [['s1', ''], ['g1', ''], ['t1', ''], ['own1', '원장'], ['own2', '학원 심사 중'], ['t2', '소속 승인 대기'], ['t3', '소속 없음'], ['op', '학원 심사']];
    return pick.map(([id, note]) => { const u = userById(id)!; return { id: u.id, name: u.name, role: u.role, loginId: u.loginId, note }; });
  },
  async demoLogin(userId: string): Promise<Me> { const u = userById(userId) ?? fail('계정을 찾지 못했어요.'); db.me = u.id; db.remember = true; commit(); return meView(u); },

  /* ---------- 설정 ---------- */
  async updateProfile(patch: { name?: string; email?: string }): Promise<Me> {
    const u = meUser();
    if (patch.name !== undefined) { const n = patch.name.trim(); if (!n || n.length > 12) fail('이름은 1~12자로 적어 주세요.'); u.name = n; }
    if (patch.email !== undefined) {
      if (u.role === 'student') fail('학생은 이메일을 받지 않아요.');
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(patch.email)) fail('이메일을 바르게 적어 주세요.');
      u.email = patch.email.trim();
    }
    commit(); return meView(u);
  },
  async changePassword(current: string, next: string): Promise<void> {
    const u = meUser();
    if (u.pw !== hash(current)) fail('지금 비밀번호가 맞지 않아요.');
    if (!PW_RULE.test(next)) fail('새 비밀번호는 영문과 숫자를 섞어 8~20자로 만들어 주세요.');
    if (current === next) fail('지금과 다른 비밀번호로 바꿔 주세요.');
    u.pw = hash(next); commit();
  },
  async saveSettings(settings: NotifySettings): Promise<Me> { const u = meUser(); u.settings = settings; commit(); return meView(u); },
  /** 회원 탈퇴: 비밀번호 확인 후 계정과 연결을 지운다(시연: 기록 일부는 남음) */
  async deleteAccount(password: string): Promise<void> {
    const u = meUser();
    if (u.pw !== hash(password)) fail('비밀번호가 맞지 않아요.');
    if (u.role === 'teacher' && ownedAcademy(u)) fail('원장은 탈퇴 전에 학원 관리를 다른 학습지도자에게 넘겨야 해요(운영자 문의).');
    db.links = db.links.filter((l) => l.studentId !== u.id && l.guardianId !== u.id);
    db.rooms.forEach((r) => { r.members = r.members.filter((x) => x !== u.id); r.invited = r.invited.filter((x) => x !== u.id); r.requests = r.requests.filter((x) => x !== u.id); });
    db.users = db.users.filter((x) => x.id !== u.id); db.me = null; commit();
  },
  /** 보호자: 연결된 아이의 비밀번호 재설정(아이는 이메일이 없으므로) */
  async resetChildPassword(childId: string, next: string): Promise<void> {
    const g = must('guardian');
    if (!connected(g).some((x) => x.id === childId)) fail('연결된 아이만 바꿀 수 있어요.');
    if (!PW_RULE.test(next)) fail('비밀번호는 영문과 숫자를 섞어 8~20자로 만들어 주세요.');
    userById(childId)!.pw = hash(next);
    notify(childId, '보호자가 비밀번호를 새로 정해 줬어.'); commit();
  },

  /* ---------- 알림함 ---------- */
  async getNotices(): Promise<AppNotice[]> { const u = meUser(); return db.notices.filter((n) => n.userId === u.id).map(({ userId: _u, ...n }) => n); },
  async readNotices(): Promise<void> { const u = meUser(); db.notices.forEach((n) => { if (n.userId === u.id) n.read = true; }); commit(); },

  /* ---------- 학습지도자: 소속 (설정 → 소속) ---------- */
  /** 일련번호로 학원·학교 소속 신청 → 원장 승인 대기 */
  async requestMembership(serial: string): Promise<Me> {
    const t = must('teacher');
    if (t.academyId && t.teacherStatus === '승인됨') fail('이미 소속이 있어요. 옮기려면 지금 소속을 먼저 나가 주세요.');
    const ac = db.academies.find((a) => norm(a.serial) === norm(serial)) ?? fail('일련번호를 찾지 못했어요. 원장님께 다시 확인해 주세요.');
    t.academyId = ac.id; t.teacherStatus = '승인 대기';
    notify(ac.ownerId, `${t.name}님이 소속을 신청했어요`, '/owner'); commit();
    return meView(t);
  },
  async leaveMembership(): Promise<Me> {
    const t = must('teacher');
    if (ownedAcademy(t)) fail('원장은 소속을 나갈 수 없어요(운영자 문의).');
    if (roomsOfTeacher(t.id).length && t.teacherStatus === '승인됨') fail('내 강의실이 남아 있어요. 강의실을 정리한 뒤 나갈 수 있어요.');
    t.academyId = null; t.teacherStatus = undefined; commit();
    return meView(t);
  },
  /** 학원·학교 등록 신청 → 운영자 심사 → 승인되면 신청한 학습지도자가 원장 */
  async applyAcademy(f: AcademyForm): Promise<Me> {
    const t = must('teacher');
    if (t.academyId && t.teacherStatus === '승인됨') fail('이미 소속이 있어요. 새 학원을 등록하려면 지금 소속을 먼저 나가 주세요.');
    const prev = t.applicationId ? db.applications.find((a) => a.id === t.applicationId) : null;
    if (prev?.status === '심사 중') fail('이미 심사 중인 신청이 있어요.');
    if (!f.academyName.trim()) fail('이름을 적어 주세요.');
    if (f.orgType === '학원' && !/^\d{3}-?\d{2}-?\d{5}$/.test(f.bizNo.trim())) fail('사업자등록번호는 숫자 10자리예요 (예: 123-45-67890).');
    if (!f.ceo.trim() || !f.phone.trim()) fail('대표자와 연락처를 적어 주세요.');
    const appId = 'app' + Date.now().toString(36);
    db.applications.push({ id: appId, ownerId: t.id, ownerName: t.name, ...f, academyName: f.academyName.trim(), status: '심사 중', appliedAt: stampLabel(Date.now()), serial: null, rejectReason: null });
    t.applicationId = appId; commit();
    return meView(t);
  },

  /* ---------- 학생 ⇄ 보호자 연동 ---------- */
  /** 상대 코드로 연결. 보호자가 하면 동의(consent)와 함께 바로 연결, 학생이 하면 보호자 동의 대기 */
  async linkWith(code: string, consent = false): Promise<Me> {
    const me = must(['student', 'guardian']);
    const other = db.users.find((u) => u.linkCode === norm(code)) ?? fail('코드를 찾지 못했어요. 6자리를 다시 확인해 주세요.');
    if (other.id === me.id) fail('내 코드는 넣을 수 없어요.');
    if (other.role === me.role || !['student', 'guardian'].includes(other.role)) fail(me.role === 'student' ? '보호자의 코드를 넣어 주세요.' : '아이의 코드를 넣어 주세요.');
    const studentId = me.role === 'student' ? me.id : other.id;
    const guardianId = me.role === 'guardian' ? me.id : other.id;
    const ex = db.links.find((l) => l.studentId === studentId && l.guardianId === guardianId);
    if (ex?.status === '연결됨') fail('이미 연결되어 있어요.');
    if (me.role === 'guardian') {
      if (!consent) fail('만 14세 미만 아이는 보호자 동의가 있어야 연결할 수 있어요.');
      if (ex) { ex.status = '연결됨'; ex.consentAt = today(); } else db.links.push({ studentId, guardianId, status: '연결됨', consentAt: today() });
      syncLinkedPair(other, me);
      notify(other.id, `${me.name}님과 연결됐어!`);
    } else if (!ex) { db.links.push({ studentId, guardianId, status: '대기', consentAt: null }); notify(guardianId, `${me.name} 학생이 연결을 요청했어요. 동의하면 연결돼요.`, '/settings/family'); }
    commit();
    return meView(me);
  },
  /** 보호자: 학생이 보낸 연결 요청을 동의와 함께 수락 */
  async confirmLink(studentId: string, consent: boolean): Promise<Me> {
    const g = must('guardian');
    if (!consent) fail('보호자 동의에 체크해 주세요.');
    const l = db.links.find((x) => x.studentId === studentId && x.guardianId === g.id && x.status === '대기') ?? fail('연결 요청을 찾지 못했어요.');
    l.status = '연결됨'; l.consentAt = today();
    const s = userById(studentId)!;
    notify(studentId, `${g.name}님이 동의해서 연결됐어! 이제 학원에 들어갈 수 있어.`);
    syncLinkedPair(s, g);
    commit();
    return meView(g);
  },

  /* ---------- 학원 입장 (학생·보호자, 학원장이 준 6자리 코드) ---------- */
  async joinAcademy(code: string): Promise<Me> {
    const me = must(['student', 'guardian']);
    if (me.role === 'student' && isRestricted(me.id)) fail('보호자와 먼저 연결해야 학원에 들어갈 수 있어요.');
    if (me.academyId) fail('이미 학원에 등록되어 있어요.');
    const c = code.replace(/\D/g, '');
    const ac = db.academies.find((a) => a.entryCode?.code === c) ?? fail('코드가 맞지 않아요. 학원에서 받은 6자리를 확인해 주세요.');
    if (ac.entryCode!.expiresAt < Date.now()) fail('코드 시간이 지났어요. 학원에 새 코드를 요청해 주세요.');
    me.academyId = ac.id;
    if (me.role === 'student') spreadFromStudent(me, ac.id); else spreadFromGuardian(me, ac.id);
    commit();
    return meView(me);
  },

  /* ---------- 원장(학원·학교 관리자) ---------- */
  async getOwnerDashboard(): Promise<OwnerDashboard> { return ownerDash(mustOwner()); },
  async issueEntryCode(): Promise<OwnerDashboard> {
    const o = mustOwner();
    const ac = ownedAcademy(o)!;
    ac.entryCode = { code: rand(6, '0123456789'), expiresAt: Date.now() + SEED_RULES.entryCodeMin * 60_000 };
    commit();
    return ownerDash(o);
  },
  async approveTeachers(ids: string[]): Promise<OwnerDashboard> {
    const o = mustOwner();
    const ac = ownedAcademy(o)!;
    ids.forEach((id) => { const t = userById(id); if (t && t.role === 'teacher' && t.academyId === ac.id && t.teacherStatus === '승인 대기') { t.teacherStatus = '승인됨'; notify(t.id, `${ac.name} 소속이 승인됐어요. 이제 강의실을 열 수 있어요.`, '/teacher/classes'); } });
    commit();
    return ownerDash(o);
  },

  /* ---------- 운영자(우리): 학원 등록 심사 ---------- */
  async getApplications(): Promise<AcademyApplication[]> {
    must('operator');
    return [...db.applications].sort((a, b) => (a.status === '심사 중' ? -1 : 1) - (b.status === '심사 중' ? -1 : 1)).map(({ ownerId: _o, ...a }) => a);
  },
  async reviewApplication(id: string, decision: '승인' | '반려', reason = ''): Promise<AcademyApplication[]> {
    must('operator');
    const app = db.applications.find((a) => a.id === id) ?? fail('신청서를 찾지 못했어요.');
    if (app.status !== '심사 중') fail('이미 처리한 신청이에요.');
    if (decision === '반려') {
      if (!reason.trim()) fail('반려 사유를 적어 주세요.');
      app.status = '반려'; app.rejectReason = reason.trim();
      notify(app.ownerId, `${app.academyName} 등록이 반려됐어요: ${app.rejectReason}`, '/settings/org');
    } else {
      app.status = '승인'; app.serial = uniqueSerial();
      const acId = 'a' + Date.now().toString(36);
      db.academies.push({ id: acId, name: app.academyName, orgType: app.orgType, serial: app.serial, ownerId: app.ownerId, entryCode: null });
      const owner = userById(app.ownerId); if (owner) { owner.academyId = acId; owner.teacherStatus = '승인됨'; }
      notify(app.ownerId, `${app.academyName} 등록이 승인됐어요. 일련번호 ${app.serial}`, '/owner');
    }
    commit();
    return orgApi.getApplications();
  },

  /* ---------- 학습지도자: 강의실 ---------- */
  async getTeacherClasses(): Promise<TeacherClasses> {
    const t = must('teacher');
    const rooms = roomsOfTeacher(t.id);
    const inAny = new Set(rooms.flatMap((r) => [...r.members]));
    return {
      classrooms: rooms.map(classroomView),
      academyStudents: t.teacherStatus !== '승인됨' ? [] : db.users.filter((u) => u.role === 'student' && u.academyId === t.academyId).map((u) => row(u.id, inAny.has(u.id) ? '내 강의실' : gradeLabel(u.grade))),
    };
  },
  async createClassroom(name: string, plan: string): Promise<TeacherClasses> {
    const t = must('teacher');
    if (!t.academyId || t.teacherStatus !== '승인됨') fail('소속 학원·학교의 승인을 받은 뒤에 강의실을 열 수 있어요.');
    if (!name.trim()) fail('강의실 이름을 적어 주세요.');
    db.rooms.push({ id: 'c' + Date.now().toString(36), academyId: t.academyId!, teacherId: t.id, name: name.trim(), plan: plan.trim(), members: [], invited: [], requests: [] });
    commit();
    return orgApi.getTeacherClasses();
  },
  async inviteStudent(classId: string, studentId: string): Promise<TeacherClasses> {
    const t = must('teacher');
    const r = db.rooms.find((x) => x.id === classId && x.teacherId === t.id) ?? fail('강의실을 찾지 못했어요.');
    const s = userById(studentId);
    if (!s || s.role !== 'student' || s.academyId !== t.academyId) fail('같은 학원 학생만 초대할 수 있어요.');
    if (r.members.includes(studentId)) fail('이미 들어와 있어요.');
    if (r.requests.includes(studentId)) { r.requests = r.requests.filter((x) => x !== studentId); r.members.push(studentId); } // 요청이 있었으면 바로 입장
    else if (!r.invited.includes(studentId)) { r.invited.push(studentId); notify(studentId, `${t.name}이 「${r.name}」에 초대했어!`, '/student/classes'); }
    commit();
    return orgApi.getTeacherClasses();
  },
  async answerRequest(classId: string, studentId: string, accept: boolean): Promise<TeacherClasses> {
    const t = must('teacher');
    const r = db.rooms.find((x) => x.id === classId && x.teacherId === t.id) ?? fail('강의실을 찾지 못했어요.');
    if (!r.requests.includes(studentId)) fail('요청을 찾지 못했어요.');
    r.requests = r.requests.filter((x) => x !== studentId);
    if (accept) { r.members.push(studentId); notify(studentId, `「${r.name}」에 들어왔어!`, '/student'); }
    commit();
    return orgApi.getTeacherClasses();
  },
  /** 수업 타이머 켜기(TK-98). 이미 켜져 있으면 새로 시작. 알림 시점은 길이보다 짧아야 한다 */
  async startClassTimer(classId: string, start: ClassTimerStart): Promise<TeacherClasses> {
    const t = must('teacher');
    const r = db.rooms.find((x) => x.id === classId && x.teacherId === t.id) ?? fail('강의실을 찾지 못했어요.');
    const { kind, minutes, warnMin } = start;
    if (kind !== 'class' && kind !== 'break') fail('수업 또는 쉬는 시간을 골라 주세요.');
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 180) fail('길이를 골라 주세요.');
    if (!Number.isInteger(warnMin) || warnMin < 1 || warnMin >= minutes) fail('알림은 길이보다 짧게 골라 주세요.');
    const now = Date.now();
    r.timer = { kind, minutes, warnMin, startedAt: now, endsAt: now + minutes * 60_000 };
    commit();
    return orgApi.getTeacherClasses();
  },
  async stopClassTimer(classId: string): Promise<TeacherClasses> {
    const t = must('teacher');
    const r = db.rooms.find((x) => x.id === classId && x.teacherId === t.id) ?? fail('강의실을 찾지 못했어요.');
    r.timer = null;
    commit();
    return orgApi.getTeacherClasses();
  },

  /* ---------- 학생: 강의실 ---------- */
  async getStudentClasses(): Promise<StudentClasses> {
    const s = must('student');
    const ofAc = db.rooms.filter((r) => r.academyId === s.academyId);
    const v = (r: Room) => ({ id: r.id, name: r.name, teacherName: nameOf(r.teacherId) });
    return {
      joined: ofAc.filter((r) => r.members.includes(s.id)).map((r) => ({ ...v(r), timer: r.timer ?? null })), // 학생은 보기만(TK-98)
      invites: ofAc.filter((r) => r.invited.includes(s.id)).map(v),
      available: ofAc.filter((r) => !r.members.includes(s.id) && !r.invited.includes(s.id)).map((r) => ({ ...v(r), requested: r.requests.includes(s.id) })),
    };
  },
  async requestJoin(classId: string): Promise<StudentClasses> {
    const s = must('student');
    if (isRestricted(s.id)) fail('보호자와 먼저 연결해 주세요.');
    const r = db.rooms.find((x) => x.id === classId && x.academyId === s.academyId) ?? fail('강의실을 찾지 못했어요.');
    if (!r.requests.includes(s.id) && !r.members.includes(s.id)) { r.requests.push(s.id); notify(r.teacherId, `${s.name} 학생이 「${r.name}」 참여를 요청했어요`, '/teacher/classes'); }
    commit();
    return orgApi.getStudentClasses();
  },
  async acceptInvite(classId: string, accept: boolean): Promise<StudentClasses> {
    const s = must('student');
    const r = db.rooms.find((x) => x.id === classId && x.invited.includes(s.id)) ?? fail('초대를 찾지 못했어요.');
    r.invited = r.invited.filter((x) => x !== s.id);
    if (accept) r.members.push(s.id);
    commit();
    return orgApi.getStudentClasses();
  },

  /* ---------- 씨앗: 학생 ---------- */
  async getWallet(): Promise<Wallet> {
    const s = must('student');
    const history: SeedEntry[] = db.ledger.filter((l) => l.studentId === s.id).sort((a, b) => b.id.localeCompare(a.id))
      .map((l) => ({ id: l.id, at: l.at, amount: l.amount, source: l.source, note: l.note }));
    return { balance: balanceOf(s.id), history };
  },
  async getStudentShop(): Promise<StudentShop> { return studentShop(must('student')); },
  async buyAcademyItem(itemId: string): Promise<StudentShop> {
    const s = must('student');
    const teacherIds = new Set(roomsOfStudent(s.id).map((r) => r.teacherId));
    const it = db.items.find((i) => i.id === itemId && i.visible && teacherIds.has(i.teacherId)) ?? fail('상품을 찾지 못했어요.');
    if (it.stock !== null && it.stock <= 0) fail('다 팔렸어요.');
    if (balanceOf(s.id) < it.price) fail('씨앗이 모자라요.');
    if (it.stock !== null) it.stock -= 1;
    addSeed(s.id, -it.price, '상점 구매', it.name, s.id);
    db.orders.push({ id: 'o' + Date.now().toString(36), studentId: s.id, teacherId: it.teacherId, itemName: it.name, price: it.price, at: stampLabel(Date.now()), status: '교환 요청' });
    notify(it.teacherId, `${s.name} 학생이 「${it.name}」 교환을 요청했어요`, '/teacher/seeds');
    commit();
    return studentShop(s);
  },
  async buyCosmetic(id: string): Promise<StudentShop> {
    const s = must('student');
    const c = COSMETICS.find((x) => x.id === id) ?? fail('상품을 찾지 못했어요.');
    const owned = db.owned[s.id] ?? [];
    if (owned.includes(id)) fail('이미 가지고 있어요.');
    if (balanceOf(s.id) < c.price) fail('씨앗이 모자라요.');
    addSeed(s.id, -c.price, '상점 구매', c.name, s.id);
    db.owned[s.id] = [...owned, id];
    if (c.kind === 'outfit') db.equipped[s.id] = id; // 사면 바로 입어 본다
    commit();
    return studentShop(s);
  },
  async equipOutfit(id: string | null): Promise<StudentShop> {
    const s = must('student');
    if (id && !(db.owned[s.id] ?? []).includes(id)) fail('아직 없는 옷이에요.');
    db.equipped[s.id] = id; commit();
    return studentShop(s);
  },

  /* ---------- 씨앗: 보호자 도장 ---------- */
  async getStampState(): Promise<StampState> {
    const g = must('guardian');
    const child = childOf(g.id);
    return { stampedToday: !!child && earnedOn(child, '보호자 도장') > 0, balance: child ? balanceOf(child) : 0 };
  },
  async stamp(): Promise<StampState> {
    const g = must('guardian');
    const child = childOf(g.id) ?? fail('먼저 아이와 연결해 주세요.');
    if (earnedOn(child, '보호자 도장') > 0) fail('오늘 도장은 이미 찍었어요. 내일 또 찍어 주세요.');
    addSeed(child, SEED_RULES.guardianStamp, '보호자 도장', '오늘 이야기를 나눴어요', g.id);
    notify(child, `보호자가 도장을 찍어 줬어! 씨앗 +${SEED_RULES.guardianStamp}`, '/student/shop'); commit();
    return orgApi.getStampState();
  },

  /* ---------- 씨앗: 학습지도자 ---------- */
  async getSeedBoard(): Promise<SeedBoard> { return seedBoard(must('teacher')); },
  async grantSeeds(studentId: string, amount: number, note: string): Promise<SeedBoard> {
    const t = must('teacher');
    if (!roomsOfTeacher(t.id).some((r) => r.members.includes(studentId))) fail('내 강의실 학생에게만 줄 수 있어요.');
    if (!Number.isInteger(amount) || amount < 1 || amount > SEED_RULES.teacherMax) fail(`한 번에 1~${SEED_RULES.teacherMax}개까지 줄 수 있어요.`);
    if (!note.trim()) fail('칭찬 이유를 골라 주세요.');
    if (earnedOn(studentId, '학습지도자 칭찬') + amount > SEED_RULES.teacherDailyCap) fail(`한 학생에게 하루 ${SEED_RULES.teacherDailyCap}개까지 줄 수 있어요.`);
    addSeed(studentId, amount, '학습지도자 칭찬', note.trim().slice(0, 30), t.id);
    notify(studentId, `${t.name}이 칭찬 씨앗 ${amount}개를 줬어! (${note.trim().slice(0, 30)})`, '/student/shop'); commit();
    return seedBoard(t);
  },
  async saveShopItem(item: Omit<ShopItem, 'id'> & { id?: string }): Promise<SeedBoard> {
    const t = must('teacher');
    if (!item.name.trim()) fail('상품 이름을 적어 주세요.');
    if (!Number.isInteger(item.price) || item.price < 1 || item.price > 200) fail('가격은 1~200 씨앗으로 정해 주세요.');
    if (item.stock !== null && (!Number.isInteger(item.stock) || item.stock < 0)) fail('수량은 0 이상으로 적어 주세요.');
    if (item.id) {
      const it = db.items.find((i) => i.id === item.id && i.teacherId === t.id) ?? fail('상품을 찾지 못했어요.');
      Object.assign(it, { ...item, name: item.name.trim() });
    } else db.items.push({ ...item, name: item.name.trim(), id: 'i' + Date.now().toString(36), teacherId: t.id });
    commit();
    return seedBoard(t);
  },
  async deliverOrder(orderId: string): Promise<SeedBoard> {
    const t = must('teacher');
    const o = db.orders.find((x) => x.id === orderId && x.teacherId === t.id) ?? fail('교환 요청을 찾지 못했어요.');
    o.status = '전달 완료';
    notify(o.studentId, `「${o.itemName}」을 받았어!`, '/student/shop'); commit();
    return seedBoard(t);
  },
};
export type OrgApi = typeof orgApi;
/** 학생이 입은 옷 (캐릭터 그림에 씀) */
export const equippedOf = (studentId: string) => db.equipped[studentId] ?? null;
