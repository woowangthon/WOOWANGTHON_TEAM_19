// .env의 VITE_API_MODE 값으로 가짜/진짜 서버를 고른다. 기본은 mock.
// http 모드여도 서버(compat)에 있는 함수만 httpApi로 보내고, 로그인·학원·씨앗·상점 등 나머지는 mockApi를 쓴다.
// VITE_ORG_MODE=http까지 켜면 그 나머지(ORG_HTTP_FUNCS)도 httpApi로 보낸다.
import type { MentorApi } from './client';
import { httpApi, startNewTrial } from './http';
import { restartDemo } from '../lib/kidScreens';
import { mockApi } from './mock';
import { orgApi } from './org';

export const HTTP_FUNCS: (keyof MentorApi)[] = [
  // 학생
  'getStudentHome', 'acceptPromise', 'getMentor', 'saveMentor', 'getActiveSession', 'startSession', 'getProblem',
  'submitAnswer', 'requestHint', 'showSolution', 'afterStudy', 'getChat', 'sendChat', 'replyChat', 'endChat',
  'getWrap', 'submitWrap',
  // 보호자
  'getGuardianToday', 'getAlerts',
  // 학습지도자
  'getTeacherToday', 'assignTask', 'getMemo', 'saveMemo', 'createDraft', 'updateDraft', 'approveDraft', 'getTeacherAlerts',
];

/** VITE_ORG_MODE=http일 때 더 보내는 것: 계정·학원·씨앗(orgApi 전부) + 로그인 계정을 읽는 학습 4개(명세 4.12).
 *  ackAlert·closeAlert·resetDemo는 화면이 안 부르거나 mock 되돌리기라 그대로 둔다 */
export const ORG_HTTP_FUNCS: (keyof MentorApi)[] = [
  ...(Object.keys(orgApi) as (keyof MentorApi)[]),
  'getRecords', 'getUnits', 'saveUnits', 'getResults',
];

export function mixed(orgHttp = false): MentorApi {
  const m = { ...mockApi } as Record<string, unknown>;
  for (const k of HTTP_FUNCS) m[k] = httpApi[k];
  if (orgHttp) for (const k of ORG_HTTP_FUNCS) m[k] = httpApi[k];
  return m as unknown as MentorApi;
}

export const API_MODE: 'mock' | 'http' = import.meta.env.VITE_API_MODE === 'http' ? 'http' : 'mock';
/** 'http'는 VITE_API_MODE=http 그리고 VITE_ORG_MODE=http일 때만. 그 밖은 지금처럼 mock */
export const ORG_MODE: 'mock' | 'http' = API_MODE === 'http' && import.meta.env.VITE_ORG_MODE === 'http' ? 'http' : 'mock';
export const api: MentorApi = API_MODE === 'http' ? mixed(ORG_MODE === 'http') : mockApi;

/** 처음부터 다시 체험: http 모드면 새 체험 세트를 받고(명세 4.11 2, 공용 /demo/restart는 쓰지 않는다) → mock(로그인·학원 등)을 되돌린다. 실패하면 오류를 던진다 */
export const restartDemoAll = () => restartDemo(API_MODE, startNewTrial, () => mockApi.resetDemo());
