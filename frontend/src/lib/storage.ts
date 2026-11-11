// localStorage는 시크릿 창 등에서 막힐 수 있어 항상 try/catch로 감싼다. 막혀 있으면 메모리에만 둔다.
const memory = new Map<string, string>();

export function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key) ?? memory.get(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    const raw = memory.get(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  }
}
export function save(key: string, value: unknown): void {
  const raw = JSON.stringify(value);
  memory.set(key, raw);
  try { localStorage.setItem(key, raw); } catch { /* 저장이 막혀도 화면은 계속 동작 */ }
}
