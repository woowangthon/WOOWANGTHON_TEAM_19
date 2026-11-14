// 강의실 수업 진행(11-13 재하 시나리오) — 학습지도자가 「수업 시작」, 학생은 「수업 참여」, 쉬는 시간엔 잠금이 풀린다.
// · 원장(학원 관리): 수업·쉬는 시간 기본 길이, 쉬는 시간 게임 허용, 보호자에게 수업 상태 알리기, 강의실 장소 표시
// · 알림 시점은 고정: 끝나기 5분 전 + 끝날 때(원장이 고르지 않는다). 보호자는 수업 5분 전 · 예정 시각 · 「수업 끝내기」. 쉬는 시간은 학생에게 1분 전도 알린다
// · 「수업 참여」는 출석이 아니다(학원 출결과 헷갈리지 않게). 교실에 없는 학생은 학습지도자가 참여 목록에서 바로 뺀다
// · 위기 화면·1388·안전 단어는 수업 중에도 절대 잠그지 않는다(잠그는 화면 목록 LOCKED_IN_CLASS에 넣지 않음)
// 저장: org http 모드(VITE_ORG_MODE=http)면 서버(명세 4.12 5-4, /class-live)에, 아니면 이 기기(브라우저)에(mock).
// 서버 모드는 앱이 5초마다 다시 읽어 강사 PC ↔ 학생·보호자 폰이 이어진다(서버 푸시 없음). 시각은 서버가 정한다.
import { useEffect, useState } from 'react';
import { load, save } from './storage';
import { ORG_HTTP, classLiveCall } from '../api/http';

export type SessionPhase = 'class' | 'break';
export interface Joined { id: string; name: string; at: number; }
export interface ClassSession {
  classId: string; className: string; teacherName: string;
  phase: SessionPhase;
  startAt: number;              // 지금 단계(수업 또는 쉬는 시간)가 시작된 시각
  endAt: number;                // 지금 단계가 끝나는 시각(늘리기·줄이기로 바뀐다)
  members: { id: string; name: string }[];  // 수업 시작 때의 강의실 학생(보호자 화면이 아이를 찾는 데 쓴다)
  joined: Joined[];             // 「수업 참여」를 누른 학생
  removed: string[];            // 학습지도자가 참여 목록에서 뺀 학생(다시 누르면 다시 들어온다)
  closedAt: number | null;      // 「수업 끝내기」를 누른 시각(보호자에게 「끝났어요」를 잠깐 보여 준다)
}
export interface ClassDefaults { classMin: number; breakMin: number; games: boolean; notifyGuardian: boolean; showPlace: boolean; alertsMin?: number[]; }
/** 수업 끝나기 알림 시점(학원 설정 timer-alerts, 기본 10·5분 전 — 성호 11-13) */
export const DEFAULT_ALERTS_MIN = [10, 5];

export const DEFAULTS: ClassDefaults = { classMin: 50, breakMin: 10, games: true, notifyGuardian: true, showPlace: false };
export const CLASS_LENGTHS = [40, 50, 60];
export const BREAK_LENGTHS = [5, 10, 15];
export const SOON_MIN = 5;          // 끝나기 5분 전 알림(고정)
export const BREAK_SOON_MIN = 1;    // 학생: 쉬는 시간 끝나기 1분 전
export const STEP_MIN = 5;          // 늘리기·줄이기 한 번에 5분
const MIN = 60_000;
/** 끝낸 수업을 보호자에게 「끝났어요」로 보여 주는 시간 */
const ENDED_SHOW_MS = 30 * MIN;

/* ---------- 저장 ---------- */
const K_SESSIONS = 'ai-mentor-class-sessions';
const K_DEFAULTS = 'ai-mentor-class-defaults';
const K_PLACES = 'ai-mentor-class-places';
export const SESSION_EVENT = 'class-session-change';

function emit() { try { window.dispatchEvent(new Event(SESSION_EVENT)); } catch { /* 테스트 등 window 없음 */ } }

/* ---------- 서버 모드(org http): 마지막으로 받은 /class-live 응답을 들고 있는다 ---------- */
export interface LiveState { sessions: Record<string, ClassSession>; defaults: ClassDefaults; places: Record<string, string>; posts: unknown[]; }
let remote: LiveState | null = null;
export const remoteLive = () => remote;
/** 로그아웃·계정 바뀜이면 null로 비운다 */
export function setRemoteLive(v: LiveState | null) { remote = v; emit(); }
export async function refreshClassLive(): Promise<void> {
  if (!ORG_HTTP) return;
  try { setRemoteLive(await classLiveCall<LiveState>('GET', '/class-live')); } catch { /* 다음 주기에 다시 */ }
}
/** 쓰기: 서버가 돌려준 전체로 바꾼다. 실패하면 서버 문구를 들고 있다가 다시 읽는다 */
export let liveError: string | null = null;
export async function liveAct(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown): Promise<void> {
  try { liveError = null; setRemoteLive(await classLiveCall<LiveState>(method, path, body)); }
  catch (e) { liveError = (e as Error).message; await refreshClassLive(); }
}
// 화면 여러 곳이 같이 써도 서버 읽기는 한 줄만(5초마다)
let pollers = 0; let pollTimer: number | undefined;
export function useLivePoll(enabled = true) {
  useEffect(() => {
    if (!ORG_HTTP || !enabled) return;
    if (pollers++ === 0) { void refreshClassLive(); pollTimer = window.setInterval(() => void refreshClassLive(), 5_000); }
    return () => { if (--pollers === 0) window.clearInterval(pollTimer); };
  }, [enabled]);
}

export function loadSessions(): Record<string, ClassSession> { return ORG_HTTP ? remote?.sessions ?? {} : load<Record<string, ClassSession>>(K_SESSIONS, {}); }
function saveSessions(s: Record<string, ClassSession>) { save(K_SESSIONS, s); emit(); }
export function loadDefaults(): ClassDefaults { return { ...DEFAULTS, ...(ORG_HTTP ? remote?.defaults : load<Partial<ClassDefaults>>(K_DEFAULTS, {})) }; }
export function saveDefaults(d: ClassDefaults) {
  if (ORG_HTTP) { const { alertsMin: _skip, ...rest } = d; void _skip; void liveAct('PUT', '/class-live/defaults', rest); return; }
  save(K_DEFAULTS, d); emit();
}
export function loadPlaces(): Record<string, string> { return ORG_HTTP ? remote?.places ?? {} : load<Record<string, string>>(K_PLACES, {}); }
export function savePlace(classId: string, place: string) {
  if (ORG_HTTP) { void liveAct('PUT', `/class-live/${encodeURIComponent(classId)}/place`, { place }); return; }
  const p = loadPlaces(); const v = place.trim();
  if (v) p[classId] = v.slice(0, 20); else delete p[classId];
  save(K_PLACES, p); emit();
}
/** 원장이 「장소 표시」를 켠 경우에만 장소를 돌려준다 */
export function placeOf(classId: string, d: ClassDefaults = loadDefaults(), places = loadPlaces()): string | null {
  return d.showPlace ? places[classId] ?? null : null;
}

function update(classId: string, fn: (s: ClassSession) => ClassSession | null) {
  const all = loadSessions(); const cur = all[classId];
  if (!cur) return;
  const next = fn(cur);
  if (next) all[classId] = next; else delete all[classId];
  saveSessions(all);
}

/* ---------- 학습지도자 ---------- */
export function startClass(room: { id: string; name: string; teacherName: string; members: { id: string; name: string }[] }, minutes: number, now = Date.now()) {
  if (ORG_HTTP) { void liveAct('POST', `/class-live/${encodeURIComponent(room.id)}/start`, { minutes }); return; }
  const all = loadSessions();
  all[room.id] = { classId: room.id, className: room.name, teacherName: room.teacherName, phase: 'class', startAt: now, endAt: now + minutes * MIN,
    members: room.members.map((m) => ({ id: m.id, name: m.name })), joined: [], removed: [], closedAt: null };
  saveSessions(all);
}
/** 늘리기(+)·줄이기(−). 줄여도 지금부터 1분은 남긴다 */
export function adjustTime(classId: string, deltaMin: number, now = Date.now()) {
  if (ORG_HTTP) { void liveAct('POST', `/class-live/${encodeURIComponent(classId)}/adjust`, { deltaMin }); return; }
  update(classId, (s) => ({ ...s, endAt: Math.max(now + MIN, s.endAt + deltaMin * MIN) }));
}
export function giveBreak(classId: string, minutes: number, now = Date.now()) {
  if (ORG_HTTP) { void liveAct('POST', `/class-live/${encodeURIComponent(classId)}/break`, { minutes }); return; }
  update(classId, (s) => ({ ...s, phase: 'break', startAt: now, endAt: now + minutes * MIN }));
}
export function resumeClass(classId: string, minutes: number, now = Date.now()) {
  if (ORG_HTTP) { void liveAct('POST', `/class-live/${encodeURIComponent(classId)}/resume`, { minutes }); return; }
  update(classId, (s) => ({ ...s, phase: 'class', startAt: now, endAt: now + minutes * MIN }));
}
export function endClass(classId: string, now = Date.now()) {
  if (ORG_HTTP) { void liveAct('POST', `/class-live/${encodeURIComponent(classId)}/end`); return; }
  update(classId, (s) => ({ ...s, endAt: Math.min(s.endAt, now), closedAt: now }));
}
export function removeJoined(classId: string, studentId: string) {
  if (ORG_HTTP) { void liveAct('POST', `/class-live/${encodeURIComponent(classId)}/remove`, { studentId }); return; }
  update(classId, (s) => ({ ...s, joined: s.joined.filter((j) => j.id !== studentId), removed: [...new Set([...s.removed, studentId])] }));
}

/* ---------- 학생 ---------- */
export function joinClass(classId: string, student: { id: string; name: string }, now = Date.now()) {
  if (ORG_HTTP) { void liveAct('POST', `/class-live/${encodeURIComponent(classId)}/join`); return; }
  update(classId, (s) => (s.joined.some((j) => j.id === student.id) ? s
    : { ...s, joined: [...s.joined, { id: student.id, name: student.name, at: now }], removed: s.removed.filter((x) => x !== student.id) }));
}

/* ---------- 상태 계산 ---------- */
export type SessionState = 'class' | 'class-soon' | 'class-over' | 'break' | 'break-soon' | 'break-over' | 'closed';
/** class-over: 수업 시간이 다 됐지만 학습지도자가 아직 쉬는 시간·끝내기를 안 누름(잠금은 풀린다) */
export function sessionState(s: ClassSession, now: number): SessionState {
  if (s.closedAt) return 'closed';
  const left = s.endAt - now;
  if (s.phase === 'class') return left <= 0 ? 'class-over' : left <= SOON_MIN * MIN ? 'class-soon' : 'class';
  return left <= 0 ? 'break-over' : left <= BREAK_SOON_MIN * MIN ? 'break-soon' : 'break';
}
export const minutesLeft = (s: ClassSession, now: number) => Math.max(0, Math.ceil((s.endAt - now) / MIN));
export const hhmm = (ms: number) => new Date(ms).toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' });
export const isJoined = (s: ClassSession, studentId: string) => s.joined.some((j) => j.id === studentId);

/** 지금 이 학생이 수업 모드(공부 외 기능 잠금)인지: 참여했고, 수업 단계이고, 시간이 남아 있을 때 */
export function lockingSession(studentId: string, now: number, all = loadSessions()): ClassSession | null {
  return Object.values(all).find((s) => isJoined(s, studentId) && (sessionState(s, now) === 'class' || sessionState(s, now) === 'class-soon')) ?? null;
}
/** 이 학생의 쉬는 시간(게임을 열 수 있는지) */
export function breakSession(studentId: string, now: number, all = loadSessions()): ClassSession | null {
  return Object.values(all).find((s) => isJoined(s, studentId) && (sessionState(s, now) === 'break' || sessionState(s, now) === 'break-soon')) ?? null;
}
/** 보호자: 아이가 들어 있는 강의실의 수업(끝낸 지 30분 안 지난 것까지) */
export function sessionsForChild(childId: string, now: number, all = loadSessions()): ClassSession[] {
  return Object.values(all).filter((s) => s.members.some((m) => m.id === childId) && !(s.closedAt && now - s.closedAt > ENDED_SHOW_MS));
}

/** 수업 중 잠그는 학생 화면(공부 외 기능). 오늘·풀이·마무리·기록·강의실·위기·설정은 열려 있다 */
export const LOCKED_IN_CLASS = ['/student/chat', '/student/shop', '/student/mentor'];

/* ---------- 잠깐 뜨는 알림(이 기기에서 한 번씩) ---------- */
export interface SessionNotice { key: string; at: number; text: string; to: string | null; }
const LATE_MS = 60_000;
/** 이 사람에게 지금까지 생긴 알림 전부. key는 단계·끝 시각이 바뀌면 달라져서(늘리기 등) 새 시점에 다시 알린다 */
export function noticesFor(role: 'teacher' | 'student' | 'guardian', userId: string, linkedIds: string[], all = loadSessions(), d = loadDefaults()): SessionNotice[] {
  const out: SessionNotice[] = [];
  for (const s of Object.values(all)) {
    const myChild = role === 'guardian' && d.notifyGuardian && s.members.some((m) => linkedIds.includes(m.id));
    // 보호자: 선생님이 「수업 끝내기」를 누른 순간 → 픽업 안내(11-13 GPT 검수에서 빠진 것 발견)
    if (s.closedAt) {
      if (myChild) out.push({ key: `${s.classId}:closed:${s.closedAt}`, at: s.closedAt, text: `${s.className} 수업이 끝났어요 (${hhmm(s.closedAt)})`, to: '/guardian' });
      continue;
    }
    const k = `${s.classId}:${s.phase}:${s.startAt}:${s.endAt}`;
    const name = s.phase === 'class' ? '수업' : '쉬는 시간';
    // 수업 끝나기 알림은 학원이 고른 시점(timer-alerts, 기본 10·5분 전), 쉬는 시간은 5분 전 고정
    const soonList = s.phase === 'class' ? (d.alertsMin?.length ? d.alertsMin : DEFAULT_ALERTS_MIN) : [SOON_MIN];
    if (role === 'teacher') {
      for (const m of soonList) if (s.endAt - m * MIN > s.startAt) out.push({ key: `${k}:soon:${m}`, at: s.endAt - m * MIN, text: `${s.className} ${name} 끝나기 ${m}분 전이에요`, to: '/teacher/classes' });
      out.push({ key: k + ':end', at: s.endAt, text: `${s.className} ${name} 시간이 다 됐어요`, to: '/teacher/classes' });
    } else if (role === 'student') {
      const member = s.members.some((m) => m.id === userId);
      if (!member) continue;
      if (s.phase === 'class' && !isJoined(s, userId)) out.push({ key: `${s.classId}:class:${s.startAt}:start`, at: s.startAt, text: `${s.className} 수업이 시작됐어! 강의실에서 「수업 참여」를 눌러`, to: '/student/classes' });
      if (s.phase === 'break') {
        out.push({ key: `${s.classId}:break:${s.startAt}:start`, at: s.startAt, text: '쉬는 시간이야! 잠깐 쉬어 가자', to: null });
        if (s.endAt - BREAK_SOON_MIN * MIN > s.startAt) out.push({ key: k + ':soon', at: s.endAt - BREAK_SOON_MIN * MIN, text: '곧 수업 다시 시작해요', to: null });
      }
    } else if (myChild && s.phase === 'class') {
      for (const m of soonList) if (s.endAt - m * MIN > s.startAt) out.push({ key: `${k}:soon:${m}`, at: s.endAt - m * MIN, text: `${s.className} 수업이 ${m}분 뒤 끝나요 (${hhmm(s.endAt)})`, to: '/guardian' });
      // 예정 시각이 됐을 때(선생님이 늘리면 key가 바뀌어 새 시각에 다시 알림)
      out.push({ key: k + ':end', at: s.endAt, text: `${s.className} 수업 시간이 다 됐어요 (${hhmm(s.endAt)})`, to: '/guardian' });
    }
  }
  return out.sort((a, b) => a.at - b.at);
}
/** 지금 띄울 것 하나(이미 띄운 것·1분 넘게 지난 것은 건너뜀) */
export function dueNotice(list: SessionNotice[], fired: string[], now: number): SessionNotice | null {
  return list.find((n) => !fired.includes(n.key) && n.at <= now && now - n.at <= LATE_MS) ?? null;
}

/* ---------- 화면 훅 ---------- */
/** 세션·기본값이 바뀌거나(같은 탭·다른 탭) 시간이 지나면 다시 그린다. 상태 변화만 보이면 되니 5초마다 */
export function useClassSessions(tickMs = 5_000): { sessions: Record<string, ClassSession>; defaults: ClassDefaults; places: Record<string, string>; now: number } {
  const read = () => ({ sessions: loadSessions(), defaults: loadDefaults(), places: loadPlaces(), now: Date.now() });
  const [v, setV] = useState(read);
  useLivePoll();
  useEffect(() => {
    const on = () => setV(read());
    const onStorage = (e: StorageEvent) => { if (!e.key || e.key.startsWith('ai-mentor-class-')) on(); };
    window.addEventListener(SESSION_EVENT, on);
    window.addEventListener('storage', onStorage);
    const iv = window.setInterval(on, tickMs);
    return () => { window.removeEventListener(SESSION_EVENT, on); window.removeEventListener('storage', onStorage); window.clearInterval(iv); };
  }, [tickMs]);
  return v;
}
