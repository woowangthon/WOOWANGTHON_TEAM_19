// 학습지도자 화면: 학습지도자는 어느 폭에서도 폰 틀 없이 창 전체를 쓰고(CSS), 창 1024px 이상에서는 2열·표로 보인다.
// 아이·보호자·로그인 화면에는 절대 붙지 않는다(역할이 teacher일 때만).
import { useEffect, useState } from 'react';
import { useAuth } from '../state/auth';
import type { AccountRole } from '../types';

export const WIDE_QUERY = '(min-width: 1024px)';

/** Frame 바깥 클래스. 넓이 판단은 CSS 미디어쿼리(global.css 「학습지도자 넓은 화면」)가 한다 */
export function frameClass({ adult, role }: { adult?: boolean; role?: AccountRole }): string {
  return 'frame' + (adult ? ' frame--adult' : '') + (role === 'teacher' ? ' frame--wide' : '');
}

type MatchMedia = (q: string) => { matches: boolean };

/** 화면 구조(2열·표)를 바꿀지: 학습지도자 + 넓은 창. matchMedia가 없으면 좁은 화면 */
export function isWideMatch(role: AccountRole | undefined, mm: MatchMedia | undefined): boolean {
  return role === 'teacher' && !!mm && mm(WIDE_QUERY).matches;
}

const mmOf = (): MatchMedia | undefined => (typeof window !== 'undefined' && window.matchMedia ? (q) => window.matchMedia(q) : undefined);

/** 학습지도자 넓은 화면 여부(창 크기를 바꾸면 따라 바뀐다) */
export function useTeacherWide(): boolean {
  const role = useAuth().me?.role;
  const [wide, setWide] = useState(() => isWideMatch(role, mmOf()));
  useEffect(() => {
    const mm = mmOf();
    setWide(isWideMatch(role, mm));
    if (!mm || role !== 'teacher') return;
    const mql = window.matchMedia(WIDE_QUERY);
    const on = () => setWide(isWideMatch(role, mm));
    mql.addEventListener('change', on);
    return () => mql.removeEventListener('change', on);
  }, [role]);
  return wide;
}
