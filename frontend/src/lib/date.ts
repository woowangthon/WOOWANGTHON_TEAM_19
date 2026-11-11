// 날짜·시간 표시 도우미
const W = ['일', '월', '화', '수', '목', '금', '토'];
const pad = (n: number) => String(n).padStart(2, '0');

/** 2026-11-12 같은 날짜 키 (기기 시간 기준) */
export const ymd = (d = new Date()) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
export const fromKey = (key: string) => { const [y, m, d] = key.split('-').map(Number); return new Date(y, m - 1, d); };
export const dateLabel = (d = new Date()) => `${d.getMonth() + 1}월 ${d.getDate()}일 ${W[d.getDay()]}요일`;
export const shortLabel = (key: string) => { const d = fromKey(key); return `${d.getMonth() + 1}월 ${d.getDate()}일 (${W[d.getDay()]})`; };
export const stampLabel = (ms: number) => { const d = new Date(ms); return `${d.getMonth() + 1}월 ${d.getDate()}일 · ${pad(d.getHours())}:${pad(d.getMinutes())}`; };
/** 월요일=0 … 일요일=6 */
export const mondayIndex = (d = new Date()) => (d.getDay() + 6) % 7;
export const weekKeys = (d = new Date()) => { const mon = addDays(d, -mondayIndex(d)); return Array.from({ length: 7 }, (_, i) => ymd(addDays(mon, i))); };
/** 초 → "7:05" */
export const mmss = (s: number) => `${Math.floor(Math.max(0, s) / 60)}:${pad(Math.max(0, s) % 60)}`;
