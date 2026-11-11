// .env의 VITE_API_MODE 값으로 가짜/진짜 서버를 고른다. 기본은 mock.
// http 모드여도 서버(compat)에 있는 함수만 httpApi로 보내고, 로그인·학원·씨앗·상점 등 나머지는 mockApi를 쓴다.
import type { MentorApi } from './client';
import { httpApi, startNewTrial } from './http';
import { restartDemo } from '../lib/kidScreens';
import { mockApi } from './mock';

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

function mixed(): MentorApi {
  const m = { ...mockApi } as Record<string, unknown>;
  for (const k of HTTP_FUNCS) m[k] = httpApi[k];
  return m as unknown as MentorApi;
}

export const API_MODE: 'mock' | 'http' = import.meta.env.VITE_API_MODE === 'http' ? 'http' : 'mock';
export const api: MentorApi = API_MODE === 'http' ? mixed() : mockApi;

/** 처음부터 다시 체험: http 모드면 새 체험 세트를 받고(명세 4.11 2, 공용 /demo/restart는 쓰지 않는다) → mock(로그인·학원 등)을 되돌린다. 실패하면 오류를 던진다 */
export const restartDemoAll = () => restartDemo(API_MODE, startNewTrial, () => mockApi.resetDemo());
