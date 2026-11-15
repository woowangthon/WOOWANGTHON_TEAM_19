// 수다 남은 시간 표시(TK-94, 성호 11-14): 상시 타이머 대신 끝나기 3분 전부터만 보인다. 판정은 서버 deadline_at(표시용)
export const CHAT_SHOW_SEC = 180;

/** left(남은 초) → 보일지, 안내할 분(올림, 3→2→1), 1분 안쪽 강조 */
export function chatTimeShow(left: number): { show: boolean; minutes: number; urgent: boolean } {
  if (left <= 0 || left > CHAT_SHOW_SEC) return { show: false, minutes: 0, urgent: false };
  return { show: true, minutes: Math.ceil(left / 60), urgent: left <= 60 };
}
