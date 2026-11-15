// 문제 글 미리보기(다리 놓기 퀴즈 칩·강사 문제 목록, bb 검토 11-14).
// 보이는 글만 줄인다 — 서버로 보내는 값은 늘 받은 문장 전체(퀴즈는 문장 전체가 같아야 서버가 찾는다).
const CHOICE = /^[①②③④⑤]/;
const GUIDE = /^\(.*\)$/; // 「(번호만 써 주세요)」 같은 답 쓰는 법 안내 줄

/** 보기(①) 앞의 줄 전부(안내 줄 빼고). 그 줄이 짧은 지시문 하나뿐이면(「어법상 틀린 문장을 고르세요.」) 첫 보기 줄까지 붙여 서로 구별되게 */
export function problemPreview(text: string, max = 80): { label: string; choices: number } {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  const choices = lines.filter((l) => CHOICE.test(l)).length;
  const first = lines.findIndex((l) => CHOICE.test(l));
  const head = (first < 0 ? lines : lines.slice(0, first)).filter((l) => !GUIDE.test(l));
  const parts = head.length === 1 && head[0].length <= 20 && first >= 0 ? [head[0], lines[first]] : head;
  const label = parts.join(' ');
  return { label: label.length > max ? label.slice(0, max - 1) + '…' : label, choices };
}
