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
