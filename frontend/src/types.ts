// 앱 전체에서 쓰는 데이터 모양(타입) = 프론트와 백엔드가 주고받는 JSON 모양.
// 백엔드(FastAPI) 응답이 이 모양이면 화면 코드는 고칠 필요가 없다. → docs/API-CONTRACT.md

export type Role = 'student' | 'teacher' | 'guardian';
export type Difficulty = '초급' | '중급' | '고급';
/** 분수 [분자, 분모] */
export type Fraction = [number, number];

/* ---------- 멘토 설정 (팀 기능 DB 「캐릭터 고르기」) ---------- */
export type MentorStyle = '같이 풀어주는' | '들어주는' | '짚어주는';
export type MentorTitle = '형' | '언니' | '친구';
export type Speech = '반말' | '존댓말';
/** 학년 1~12 (초1=1 … 초6=6, 중1=7 … 중3=9, 고1=10 … 고3=12). 표시는 lib/grade의 gradeLabel */
export type Grade = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12;
/** 띠 캐릭터. 띠를 추가하려면 여기와 public/mascot/{이름}/ 폴더만 늘리면 된다 */
export type Animal = 'horse' | 'monkey';
export const ANIMAL_LABEL: Record<Animal, string> = { horse: '말띠', monkey: '원숭이띠' };
export interface MentorSetting { style: MentorStyle; title: MentorTitle; speech: Speech; animal: Animal; }

/* ---------- 학생: 하루 세션 ---------- */
/**
 * 세션 단계(서버가 관리하는 상태기계)
 * solve(같이 풀기) → transition(학습 완료) → chat(수다, 선택) → wrap(마무리) → done
 *                                          └ crisis(위험 표현 감지 시 즉시 종료)
 */
export type Phase = 'solve' | 'transition' | 'chat' | 'wrap' | 'done' | 'crisis';

export interface SessionView {
  id: string;
  phase: Phase;
  unit: string;
  difficulty: Difficulty;
  solved: number;            // 끝낸 문제 수(정답 + 풀이 같이 본 것)
  total: number;
  assisted: number;          // 풀이를 같이 본 문제 수
  hintsUsed: number;
  studyMin: number;          // 지금까지 공부한 분
  studyRemainingSec: number; // 20분 마감까지 (서버 판정)
  chatRemainingSec: number;  // 수다 10분 마감까지 (서버 판정)
  timedOut: boolean;         // 20분이 다 돼서 끝났는지
  streakDays: number;
}

export interface TaskInfo { unit: string; count: number; minutes: number; assignedBy: string; }

export interface StudentHome {
  name: string;
  dateLabel: string;         // "11월 12일 목요일"
  streakDays: number;
  attendance: boolean[];     // 이번 주 월~일
  todayIndex: number;        // 0=월
  task: TaskInfo | null;     // 학습지도자가 지정한 오늘 할 것 (없으면 null)
  needsOnboarding: boolean;  // 약속·캐릭터 고르기를 아직 안 했으면 true
  session: SessionView | null; // 오늘 진행 중이거나 끝난 세션
  doneToday: boolean;
  restricted: boolean;       // 보호자와 연결 전(제한 모드)
  inClass: boolean;          // 강의실에 들어가 있는지
  seeds: number;             // 씨앗 잔액
  earnedToday: number;       // 오늘 학습 완료로 받은 씨앗(0이면 아직)
  endedInCrisis?: boolean;   // 계약 #2 v1: 오늘 세션이 위기(🔴)로 끝났으면 true(그때 doneToday도 true)
}

/** 화면에 보내는 문제. 정답은 절대 포함하지 않는다(판정은 서버). */
export interface ProblemView {
  id: string;
  index: number;             // 0부터
  total: number;
  text?: string;             // 문제 문장(서버가 줌. 문장제는 이것만 보일 수도 있다)
  left: Fraction | null;     // 식을 두 분수로 나눌 수 없는 문제는 null → 식은 그리지 않는다
  right: Fraction | null;
  op: '+' | '-' | '÷';
  hints: string[];           // 지금까지 받은 힌트
  hintsLeft: number;         // 남은 힌트(서버가 정함. 지금 서버는 최대 2)
  canShowSolution: boolean;  // 힌트를 다 쓰고도 틀리면 true → 「풀이 같이 보기」
  remainingSec: number;
}

export interface AnswerResult {
  correct: boolean;
  numeratorOk: boolean;      // 분자는 맞았는지 → "여기까지는 맞았어"
  denominatorOk: boolean;
  message: string;           // 멘토가 하는 말
  autoHint: string | null;   // 틀리면 다음 힌트가 자동으로 나온다
  hintsLeft: number;
  canShowSolution: boolean;
  queued?: boolean;          // 서버: 앞 답을 만드는 중이라 판정만 했다 → 화면을 넘기지 않는다
  session: SessionView;
}
export interface HintResult { hints: string[]; hintsLeft: number; }
export interface Solution { steps: string[]; session: SessionView; }

export interface ChatMessage { from: 'mentor' | 'me'; text: string; }
export interface ChatState { messages: ChatMessage[]; remainingSec: number; }
// 끊어 보내기(11-11): queued = 앞 답을 만드는 중이라 받아만 둠, pending = 답 안 된 말이 남아 /reply를 불러야 함
export interface ChatReply { reply: string; crisis: boolean; session: SessionView; queued?: boolean; pending?: boolean; hotlines?: string[]; }

export interface WrapInfo {
  unit: string; solved: number; total: number; difficulty: Difficulty;
  studyMin: number; chatMin: number; streakDays: number;
  aiLine: string;            // 선생님께 보낼 한 줄(자동 요약)
  hardChips: string[];       // 어려웠던 점 칩 (마지막은 항상 '직접 쓸래')
  quizOptions: string[];     // 보호자께 낼 퀴즈 후보
}
export interface WrapBody { hardPoint: string | null; quiz: string | null; }

export interface StudyRecord { date: string; unit: string; solved: number; total: number; difficulty: Difficulty; hints: number; chatted: boolean; }

/* ---------- 학습지도자 ---------- */
export interface Unit { id: string; name: string; count: number; selected: boolean; hasProblems: boolean; }
export type TaskStatus = '지정 전' | '지정됨' | '진행 중' | '완료';
export interface StudentRow { id: string; name: string; task: string | null; status: TaskStatus; draftStatus: Draft['status'] | null; }
export interface TeacherToday { dateLabel: string; className: string; units: string[]; students: StudentRow[]; }
export interface TeacherMemo { covered: string; stuck: string; homework: string; note: string; }
export interface Draft {
  studentId: string; studentName: string;
  scope: string; amount: string; mode: string; // 사실 칸: 기록에서 자동으로 채움(AI가 쓰지 않음)
  comment: string;                              // 코멘트: 초안 → 학습지도자가 고쳐서 승인
  status: '승인 대기' | '승인됨';
}
export interface StudentResult {
  id: string; name: string; done: boolean;
  unit: string; solved: number; total: number; difficulty: Difficulty | null;
  streak: number; hints: number;
  mistake: string | null;      // 자주 한 실수 유형 (학습지도자 전용)
  hardPoint: string | null;    // 학생이 고른 어려운 점
  beginnerRepeat: number;      // 최근 연속 초급 선택 횟수(3 이상이면 노란 표시)
}
export interface TeacherAlert { id: string; studentName: string; at: string; status: SafetyAlert['status']; }

/* ---------- 보호자 ---------- */
export type AlertLevel = '주의' | '긴급';
export type AlertCategory = '마음' | '관계' | '안전';
export interface SafetyAlert {
  id: string; at: string; level: AlertLevel; category: AlertCategory;
  action: string; status: '미확인' | '확인함' | '닫음'; closeReason?: string;
  /** 🔴일 때만: 걱정된 말의 앞뒤 ±2턴(개인정보 가린 본), 최대 300자. 결정 11-11 「안전 알림 전달 수준」 */
  excerpt?: string | null;
}
export interface GuardianToday {
  childName: string; dateLabel: string; done: boolean;
  unit: string; solved: number; streak: number;
  hardPoint: string | null; line: string | null; quiz: string | null; teacherComment: string | null;
  attendance: boolean[]; todayIndex: number;
  /** 오늘 🔴로 끝났을 때 첫 화면 안내(서버가 문구를 준다, 11-11). 없으면 평소 화면 */
  alertNotice?: string | null;
}

/* ---------- 시연 ---------- */

/* =====================================================================
   v0.5 — 로그인·회원가입·설정·소속 (11-10 회의 + 사용자 추가 요청)
   ===================================================================== */
/** 역할. 학원장은 따로 없다: 학원·학교를 등록해 승인받은 학습지도자가 그곳의 원장(관리자)이 된다. operator = 우리(운영자) */
export type AccountRole = 'student' | 'guardian' | 'teacher' | 'operator';
export const ROLE_LABEL: Record<AccountRole, string> = { student: '학생', guardian: '보호자', teacher: '학습지도자', operator: '운영자' };
export type OrgType = '학원' | '학교';

export interface NotifySettings {
  studyReminder: string | null;   // 학생: 매일 공부 알림 시각 "17:00" (null = 끔)
  learnDone: boolean;             // 보호자: 아이 학습 완료 알림
  activity: boolean;              // 연결·초대·승인·교환 요청 같은 활동 알림
  marketing: boolean;             // [선택] 이벤트·소식
}

export interface Membership {
  academyId: string; name: string; orgType: OrgType;
  status: '승인 대기' | '승인됨';
  isOwner: boolean;               // 이 학원·학교의 원장(관리자)
}

export interface Me {
  id: string; role: AccountRole; name: string; loginId: string;
  email: string | null;           // 어른만(아이디·비밀번호 찾기). 학생은 받지 않음
  grade: Grade | null;
  /** 학생·보호자 고유 연동 코드(서로 연결할 때 씀) */
  linkCode: string | null;
  linked: { id: string; name: string; role: AccountRole }[];
  /** 연결 대기: 보호자에게는 "동의하고 연결" 할 학생, 학생에게는 동의를 기다리는 보호자 */
  pendingLinks: { id: string; name: string; role: AccountRole }[];
  academy: { id: string; name: string } | null;
  /** 학습지도자 소속 (없으면 null) */
  membership: Membership | null;
  /** 학습지도자: 내가 낸 학원·학교 등록 신청(최근 1건) */
  application: AcademyApplication | null;
  /** 학생: 보호자와 연결되기 전까지는 제한 모드(학원 입장·수다 막힘). 만 14세 미만 보호자 동의 */
  restricted: boolean;
  /** 학생: 입은 옷(꾸미기 id) */
  outfit: string | null;
  settings: NotifySettings;
}

export interface Agreements { terms: boolean; privacy: boolean; marketing: boolean; }
export interface SignupBody {
  role: 'student' | 'guardian' | 'teacher';
  loginId: string; password: string; name: string;
  grade?: Grade;                  // 학생 (초1~고3)
  email?: string;                 // 보호자·학습지도자
  agreements: Agreements;
}

export interface AcademyForm { orgType: OrgType; academyName: string; bizNo: string; ceo: string; phone: string; address: string; }
export type ApplicationStatus = '심사 중' | '승인' | '반려';
export interface AcademyApplication extends AcademyForm {
  id: string; status: ApplicationStatus; appliedAt: string; serial: string | null; rejectReason: string | null; ownerName: string;
}

/** 학원 입장 코드: 6자리, 10분 만료. 학생·보호자가 학원에 처음 들어올 때만 씀 */
export interface EntryCode { code: string; expiresAt: number; }

export interface PersonRow { id: string; name: string; sub?: string; }
export interface OwnerDashboard {
  academy: { id: string; name: string; serial: string; orgType: OrgType };
  entryCode: EntryCode | null;
  pendingTeachers: PersonRow[];
  teachers: PersonRow[];
  classrooms: { id: string; name: string; teacherName: string; count: number }[];
  students: PersonRow[];
}

export interface Classroom {
  id: string; name: string; plan: string; teacherName: string;
  members: PersonRow[];
  invited: PersonRow[];   // 학습지도자가 초대했고 학생이 아직 수락 안 함
  requests: PersonRow[];  // 학생이 참여 요청했고 학습지도자가 아직 수락 안 함
}
export interface TeacherClasses { classrooms: Classroom[]; academyStudents: PersonRow[]; }
export interface StudentClasses {
  joined: { id: string; name: string; teacherName: string }[];
  invites: { id: string; name: string; teacherName: string }[];
  available: { id: string; name: string; teacherName: string; requested: boolean }[];
}

/* ---------- 알림함 ---------- */
export interface AppNotice { id: string; at: string; text: string; to: string | null; read: boolean; }

/* ---------- 씨앗(재화) ---------- */
export type SeedSource = '학습 완료' | '보호자 도장' | '학습지도자 칭찬' | '상점 구매';
export interface SeedEntry { id: string; at: string; amount: number; source: SeedSource; note: string; }
export interface Wallet { balance: number; history: SeedEntry[]; }

export interface ShopItem { id: string; name: string; price: number; stock: number | null; visible: boolean; note: string; }
export type CosmeticKind = 'outfit' | 'emote';
export interface Cosmetic { id: string; kind: CosmeticKind; name: string; price: number; owned: boolean; equipped: boolean; }
export interface StudentShop { balance: number; academyItems: ShopItem[]; cosmetics: Cosmetic[]; orders: Order[]; }
export type OrderStatus = '교환 요청' | '전달 완료';
export interface Order { id: string; studentName: string; itemName: string; price: number; at: string; status: OrderStatus; }
export interface SeedBoard { students: { id: string; name: string; balance: number; earnedWeek: number; grantedToday: number }[]; orders: Order[]; items: ShopItem[]; }
export interface StampState { stampedToday: boolean; balance: number; }
