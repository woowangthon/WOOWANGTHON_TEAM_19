// 가입 정보 입력에서 「가입하기」가 막힌 이유를 한 줄로. 위에서부터 첫 번째로 빠진 것만 알려 준다(R3).
export interface SignupState {
  loginId: string; idOk: boolean | null; pwOk: boolean; same: boolean;
  name: string; kid: boolean; grade: number | null; emailOk: boolean;
}

/** 별명 칸에 전화번호처럼 숫자가 4개 넘게 이어지는지(띄어쓰기·하이픈은 무시) — R1, 원문 PII를 처음부터 덜 받게 */
export const looksLikePhone = (name: string) => /\d{4,}/.test(name.replace(/[\s-]/g, ''));

export function signupMissing(s: SignupState): string | null {
  if (!s.loginId) return '아이디를 넣어 주세요';
  if (s.idOk === false) return '이미 있는 아이디예요. 다른 아이디로 바꿔 주세요';
  if (s.idOk !== true) return '아이디 옆 「중복 확인」을 눌러 주세요';
  if (!s.pwOk) return '비밀번호는 영문과 숫자를 섞어 8~20자로 해 주세요';
  if (!s.same) return '비밀번호 확인이 위와 같아야 해요';
  if (!s.name.trim()) return s.kid ? '별명을 넣어 주세요' : '이름을 넣어 주세요';
  if (s.kid && looksLikePhone(s.name)) return '별명에 전화번호는 넣지 말아 줘';
  if (s.kid && s.grade === null) return '학년을 골라 주세요';
  if (!s.kid && !s.emailOk) return '이메일 주소를 확인해 주세요';
  return null;
}

/** 비밀번호 칸 아래 한 줄 — 지금 몇 자인지 보여 준다(성호 11-14: 7자로 넣고 왜 막혔는지 몰랐음). 규칙은 org.ts PW_RULE과 같다 */
export function pwHint(pw: string): { ok: boolean; text: string } {
  const n = [...pw].length;
  if (n < 8) return { ok: false, text: `지금 ${n}자예요. ${8 - n}자 더 넣어 주세요 (영문+숫자 8~20자)` };
  if (n > 20) return { ok: false, text: `지금 ${n}자예요. 20자까지 쓸 수 있어요` };
  if (!/[A-Za-z]/.test(pw)) return { ok: false, text: `지금 ${n}자예요. 영문도 하나 넣어 주세요` };
  if (!/\d/.test(pw)) return { ok: false, text: `지금 ${n}자예요. 숫자도 하나 넣어 주세요` };
  return { ok: true, text: '좋아요' };
}

/** 가입 때 보낼 동의. 학생에게는 소식 알림을 묻지 않으므로(R8) 화면 값이 남아 있어도 marketing은 false로 보낸다
 *  (보호자에서 「전체 동의」 뒤 뒤로 가서 학생으로 바꾸면 숨은 행의 true가 남는다) */
export function signupAgreements<A extends { marketing: boolean }>(agree: A, kid: boolean): A {
  return kid ? { ...agree, marketing: false } : agree;
}
