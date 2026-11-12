// 조사 도우미 — 이름을 부를 때 받침에 따라 「아/야」를 고른다 (새봄아, 지우야).

/** 반말로 부르는 말. 한글로 끝나지 않으면 조사 없이 이름만 */
export function callName(name: string): string {
  const n = name.trim();
  const code = n.charCodeAt(n.length - 1) - 0xac00;
  if (Number.isNaN(code) || code < 0 || code > 11171) return n;
  return n + (code % 28 === 0 ? '야' : '아');
}
