// 화면이 백엔드에 요청할 수 있는 일의 목록(계약).
// mock.ts(가짜 서버)와 http.ts(진짜 FastAPI)가 둘 다 이 모양을 따른다 → 화면 코드는 어느 쪽인지 몰라도 된다.
import type {
  AnswerResult, ChatReply, ChatState, Difficulty, Draft, GuardianToday, HintResult, MentorSetting,
  ProblemView, SafetyAlert, SessionView, Solution, StudentHome, StudentResult, StudyRecord, TeacherAlert, TeacherMemo,
  TeacherToday, Unit, WrapBody, WrapInfo,
} from '../types';

import type { OrgApi } from './org';

/** v0.4 계정·학원·강의실·씨앗 API는 org.ts(orgApi)의 모양을 그대로 쓴다 → docs/API-CONTRACT.md "v0.4" 표 */
export type AccountApi = OrgApi;

export interface MentorApi extends AccountApi {
  /* 학생 — 준비 */
  getStudentHome(): Promise<StudentHome>;
  acceptPromise(): Promise<void>;
  getMentor(): Promise<MentorSetting | null>;
  saveMentor(setting: MentorSetting): Promise<void>;

  /* 학생 — 하루 세션 (서버가 단계·시간·정답을 관리) */
  getActiveSession(): Promise<SessionView | null>;            // 새로고침해도 이어서 할 수 있게
  startSession(difficulty: Difficulty): Promise<SessionView>;
  getProblem(sessionId: string): Promise<ProblemView | null>; // null이면 풀기 단계가 끝난 것
  /** 분수 칸은 numerator·denominator, 그 밖의 답 칸(숫자 한 칸·보기·낱말)은 answer 글자로 보낸다 */
  submitAnswer(sessionId: string, problemId: string, numerator: number, denominator: number, answer?: string): Promise<AnswerResult>;
  requestHint(sessionId: string, problemId: string): Promise<HintResult>;
  showSolution(sessionId: string, problemId: string): Promise<Solution>;
  afterStudy(sessionId: string, choice: 'chat' | 'skip'): Promise<SessionView>; // 수다 할래 / 오늘은 끝
  getChat(sessionId: string): Promise<ChatState>;
  sendChat(sessionId: string, texts: string[]): Promise<ChatReply>; // 끊어 보낸 말 묶음(1~5조각, 11-11)
  replyChat(sessionId: string): Promise<ChatReply>;                 // pending이면 답 더 받기(서버 #4a)
  endChat(sessionId: string): Promise<SessionView>;
  getWrap(sessionId: string): Promise<WrapInfo>;
  submitWrap(sessionId: string, body: WrapBody): Promise<SessionView>;
  getRecords(): Promise<StudyRecord[]>;

  /* 학습지도자 */
  getUnits(): Promise<Unit[]>;
  saveUnits(selectedIds: string[]): Promise<Unit[]>;
  getTeacherToday(): Promise<TeacherToday>;
  assignTask(studentId: string, unit: string | null): Promise<TeacherToday>;
  getMemo(studentId: string): Promise<{ memo: TeacherMemo; draft: Draft | null }>;
  saveMemo(studentId: string, memo: TeacherMemo): Promise<void>;
  createDraft(studentId: string): Promise<Draft>;
  updateDraft(studentId: string, comment: string): Promise<Draft>;
  approveDraft(studentId: string): Promise<Draft>;
  getResults(): Promise<StudentResult[]>;
  getTeacherAlerts(): Promise<TeacherAlert[]>;

  /* 보호자 */
  getGuardianToday(): Promise<GuardianToday>;
  getAlerts(): Promise<SafetyAlert[]>;
  ackAlert(id: string): Promise<SafetyAlert>;
  closeAlert(id: string, reason: string): Promise<SafetyAlert>;

  /* 시연 */
  resetDemo(): Promise<void>;
}
