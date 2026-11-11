// 아이 화면에서 쓰는 작은 판정들. 화면 코드에서 빼서 테스트한다.
import type { Me, StudentHome } from '../types';

/** 오늘 세션이 위기(🔴)로 끝났는지. 계약 #2 v1: 서버 endedInCrisis 우선, 없으면 세션 단계 crisis로 대신 */
export function isCrisisDay(home: Pick<StudentHome, 'endedInCrisis' | 'session'>): boolean {
  if (typeof home.endedInCrisis === 'boolean') return home.endedInCrisis;
  return home.session?.phase === 'crisis';
}

/** 시연용 데모 아이(지우, 서버에서는 demo-child-minsu)로 로그인했는지 */
export function isDemoChild(me: Pick<Me, 'role' | 'loginId'> | null): boolean {
  return me?.role === 'student' && me.loginId === 'jiwoo';
}

/** 처음부터 다시 체험: http 모드면 서버를 먼저 되돌리고, 그다음 mock(로그인·학원 등)을 되돌린다.
 *  서버가 실패하면 mock은 그대로 두고 오류를 넘긴다(화면이 ✓ 대신 오류를 보여 준다). */
export async function restartDemo(mode: 'mock' | 'http', server: () => Promise<unknown>, mock: () => Promise<void>): Promise<void> {
  if (mode === 'http') await server();
  await mock();
}

/** 같이 풀기 20분이 끝났는데 아직 이 문제를 끝내지 못했는지(서버에 풀기 마감이 없어 화면이 선택지를 보여 준다) */
export function isSolveTimeUp(leftSec: number, hasProblem: boolean, finished: boolean): boolean {
  return hasProblem && !finished && leftSec <= 0;
}

/** 서버 재시작 등으로 세션이 사라졌을 때의 오류 문구인지(서버 404 session_not_found · mock need()) */
export function isSessionGone(error: string | null): boolean {
  return !!error && /세션을 찾(을 수 없|지 못했)/.test(error);
}
