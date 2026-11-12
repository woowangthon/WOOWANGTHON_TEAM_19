// 강의실 공지·숙제(11-13 재하): 학습지도자가 강의실에 올리고, 학생·보호자는 읽기만 한다(댓글·1:1 채팅 없음 — 아이 안전).
// · 숙제는 마감일이 있고, 학생이 「다 했어」를 스스로 누른다(검사·점수 아님). 학습지도자는 몇 명이 눌렀는지만 본다
// · 알림: 학생 = 새 공지·새 숙제, 마감 전날·당일 아직 안 한 숙제 / 보호자 = 아이 숙제 마감 전날·당일(원장 「보호자 알림」 설정을 따름)
// 서버가 아직 없어 이 기기(브라우저)에만 저장한다(classSession과 같은 방식). 서버가 생기면 load/save 자리만 api로 바꾼다.
import { useEffect, useState } from 'react';
import { load, save } from './storage';
import { addDays, fromKey, shortLabel, ymd } from './date';
import { SESSION_EVENT, loadDefaults, type SessionNotice } from './classSession';

export type PostKind = 'notice' | 'homework';
export interface ClassPost {
  id: string; classId: string; className: string; teacherName: string;
  kind: PostKind; title: string; body: string;
  due: string | null;                       // 숙제 마감일 'YYYY-MM-DD'(이날까지)
  at: number;                               // 올린 시각
  members: { id: string; name: string }[];  // 올릴 때의 강의실 학생(보호자 화면이 아이를 찾는 데 쓴다)
  done: string[];                           // 숙제를 「다 했어」 누른 학생 id
}
export const TITLE_MAX = 40;
export const BODY_MAX = 300;
const NEW_DAYS = 3; // 올린 지 3일 안이면 「새」 + 알림

const KEY = 'ai-mentor-class-posts';
function emit() { try { window.dispatchEvent(new Event(SESSION_EVENT)); } catch { /* 테스트 */ } }
export function loadPosts(): ClassPost[] { return load<ClassPost[]>(KEY, []); }
function savePosts(p: ClassPost[]) { save(KEY, p); emit(); }

export function addPost(room: { id: string; name: string; teacherName: string; members: { id: string; name: string }[] },
  input: { kind: PostKind; title: string; body: string; due: string | null }, now = Date.now()): ClassPost {
  const title = input.title.trim().slice(0, TITLE_MAX);
  if (!title) throw new Error('제목을 적어 주세요.');
  if (input.kind === 'homework' && !input.due) throw new Error('숙제 마감일을 골라 주세요.');
  const p: ClassPost = {
    id: 'p' + now.toString(36) + Math.random().toString(36).slice(2, 6), classId: room.id, className: room.name, teacherName: room.teacherName,
    kind: input.kind, title, body: input.body.trim().slice(0, BODY_MAX), due: input.kind === 'homework' ? input.due : null,
    at: now, members: room.members.map((m) => ({ id: m.id, name: m.name })), done: [],
  };
  savePosts([p, ...loadPosts()]);
  return p;
}
export function removePost(id: string) { savePosts(loadPosts().filter((p) => p.id !== id)); }
export function toggleDone(id: string, studentId: string) {
  savePosts(loadPosts().map((p) => (p.id !== id ? p : { ...p, done: p.done.includes(studentId) ? p.done.filter((x) => x !== studentId) : [...p.done, studentId] })));
}

/* ---------- 고르기·읽기 ---------- */
export const postsOfClass = (classId: string, all = loadPosts()) => all.filter((p) => p.classId === classId).sort((a, b) => b.at - a.at);
export const postsForStudent = (studentId: string, all = loadPosts()) => all.filter((p) => p.members.some((m) => m.id === studentId)).sort((a, b) => b.at - a.at);
export const isNew = (p: ClassPost, now: number) => now - p.at < NEW_DAYS * 86_400_000;
/** 마감까지 남은 날(오늘 마감 = 0, 지남 = 음수) */
export function daysLeft(due: string, now: number): number {
  return Math.round((fromKey(due).getTime() - fromKey(ymd(new Date(now))).getTime()) / 86_400_000);
}
export function dueText(due: string, now: number): string {
  const n = daysLeft(due, now);
  return n < 0 ? `${shortLabel(due)}까지였어요` : n === 0 ? '오늘까지' : n === 1 ? '내일까지' : `${shortLabel(due)}까지`;
}
/** 아직 안 한, 마감이 지나지 않은 숙제(마감 가까운 순) */
export function openHomework(studentId: string, now: number, all = loadPosts()): ClassPost[] {
  return postsForStudent(studentId, all)
    .filter((p) => p.kind === 'homework' && p.due && !p.done.includes(studentId) && daysLeft(p.due, now) >= 0)
    .sort((a, b) => (a.due! < b.due! ? -1 : 1));
}
/** 마감 고르기 칩: 내일 · 모레 · 일주일 뒤 */
export const dueChoices = (now = Date.now()) => [1, 2, 7].map((n) => ({ n, key: ymd(addDays(new Date(now), n)) }));

/* ---------- 잠깐 뜨는 알림(SessionToasts가 함께 띄운다) ---------- */
/** at은 「지금」 — 조건이 맞는 동안 하루에 한 번(key에 날짜) 또는 한 번만(새 글) 뜬다 */
export function boardNotices(role: 'teacher' | 'student' | 'guardian', userId: string, linkedIds: string[], now: number, all = loadPosts()): SessionNotice[] {
  const out: SessionNotice[] = [];
  const today = ymd(new Date(now));
  if (role === 'student') {
    for (const p of postsForStudent(userId, all)) {
      if (isNew(p, now)) out.push({ key: `${p.id}:new`, at: now, text: p.kind === 'homework' ? `새 숙제: ${p.title} · ${dueText(p.due!, now)}` : `${p.className} 새 공지: ${p.title}`, to: '/student/classes' });
    }
    for (const p of openHomework(userId, now, all)) {
      const n = daysLeft(p.due!, now);
      if (n <= 1) out.push({ key: `${p.id}:due:${today}`, at: now, text: n === 0 ? `오늘까지 숙제가 있어: ${p.title}` : `내일까지 숙제가 있어: ${p.title}`, to: '/student/classes' });
    }
  } else if (role === 'guardian' && loadDefaults().notifyGuardian) {
    for (const p of all) {
      if (p.kind !== 'homework' || !p.due) continue;
      const n = daysLeft(p.due, now);
      if (n < 0 || n > 1) continue;
      for (const c of p.members.filter((m) => linkedIds.includes(m.id) && !p.done.includes(m.id))) {
        out.push({ key: `${p.id}:${c.id}:due:${today}`, at: now, text: `${c.name}의 숙제가 ${n === 0 ? '오늘' : '내일'}까지예요: ${p.title}`, to: '/guardian' });
      }
    }
  }
  return out;
}

/** 공지·숙제가 바뀌면(같은 탭·다른 탭) 다시 그린다 */
export function useClassPosts(): { posts: ClassPost[]; now: number } {
  const read = () => ({ posts: loadPosts(), now: Date.now() });
  const [v, setV] = useState(read);
  useEffect(() => {
    const on = () => setV(read());
    const onStorage = (e: StorageEvent) => { if (!e.key || e.key === KEY) on(); };
    window.addEventListener(SESSION_EVENT, on);
    window.addEventListener('storage', onStorage);
    const iv = window.setInterval(on, 60_000);
    return () => { window.removeEventListener(SESSION_EVENT, on); window.removeEventListener('storage', onStorage); window.clearInterval(iv); };
  }, []);
  return v;
}
