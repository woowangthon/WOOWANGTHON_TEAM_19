// 위기 화면 맨 위 멘토 말(11-15 성호 「A안 완성」) — 서버가 위기 때 남긴 고정 문장(반말·존댓말은 서버가 고름)을 그대로 보인다.
// 화면 코드에 문장을 적지 않는다. 서버가 주지 않으면(빈 대화·72시간 만료) null → 문장 없이 지금 화면.
import type { ChatMessage } from '../types';

export function crisisLine(messages: ChatMessage[] | null | undefined): string | null {
  const last = [...(messages ?? [])].reverse().find((m) => m.from === 'mentor');
  return last?.text?.trim() || null;
}
