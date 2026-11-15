// 난이도 안내(D4, 명세 4.13-7, bb 검토 11-14). 서버 note·누가 정했는지 → 아이 문장. 사실대로: 「나왔다」(맞혔다 아님), 고른 건 서버 규칙(AI 말처럼 꾸미지 않음)
type Say = (casual: string, polite: string) => string;

export function difficultyNoteLine(note: string | null | undefined, chosen: string | null | undefined, difficulty: string | null | undefined, say: Say): string | null {
  if (note === 'instructor') return say('선생님이 정한 문제야', '선생님이 정한 문제예요');
  if (note === 'nearby' && chosen && difficulty) return say(`${chosen} 문제는 이미 다 나와서 ${difficulty} 문제를 냈어`, `${chosen} 문제는 이미 다 나와서 ${difficulty} 문제를 냈어요`);
  if (note === 'repeat') return say('전에 나온 문제를 다시 풀어 보자', '전에 나온 문제를 다시 풀어 봐요');
  return null;
}

/** 오늘 홈 「누가 정했나」: 선생님이면 그대로, 그 밖(서버 규칙)은 「학년과 고른 난이도에 맞춰 골랐어」 — 앱 내부 이름 「친구1」을 보이지 않는다 */
export const assignedByLine = (assignedBy: string, say: Say) =>
  assignedBy === '선생님' ? say('선생님이 정해 줬어', '선생님이 정해 줬어요') : say('학년과 고른 난이도에 맞춰 골랐어', '학년과 고른 난이도에 맞춰 골랐어요');
