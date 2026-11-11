// 화면 주소(라우트) 목록. 화면이 늘면 여기에 한 줄씩 추가한다.
// v0.5: 아이디·비밀번호 로그인(자동 로그인 선택) → 역할 화면. 역할마다 RequireRole, 로그인·가입·찾기는 GuestOnly(로그인하면 못 돌아감).
import { HashRouter, MemoryRouter, Navigate, Route, Routes } from 'react-router-dom';
import { SessionProvider } from './state/session';
import { MentorProvider } from './state/mentor';
import { AuthProvider, GuestOnly, RequireRole, RootRedirect } from './state/auth';
import { DocPageView, Find, Login, Signup, Welcome } from './screens/auth/Auth';
import { Settings, SettingsDelete, SettingsFamily, SettingsNotify, SettingsOrg, SettingsPassword, SettingsProfile } from './screens/settings/Settings';
import { Notifications } from './screens/settings/Notifications';
import { StudentToday } from './screens/student/Today';
import { StudentPromise } from './screens/student/Promise';
import { StudentCharacter } from './screens/student/Character';
import { StudentDifficulty } from './screens/student/Difficulty';
import { StudentSolve } from './screens/student/Solve';
import { StudentDone } from './screens/student/Done';
import { StudentChat } from './screens/student/Chat';
import { StudentCrisis } from './screens/student/Crisis';
import { StudentWrap } from './screens/student/Wrap';
import { StudentRecords } from './screens/student/Records';
import { StudentShop } from './screens/student/Shop';
import { StudentClasses } from './screens/student/Classes';
import { TeacherScope } from './screens/teacher/Scope';
import { TeacherToday } from './screens/teacher/Today';
import { TeacherResults } from './screens/teacher/Results';
import { TeacherAlerts } from './screens/teacher/Alerts';
import { TeacherClasses } from './screens/teacher/Classes';
import { TeacherSeeds } from './screens/teacher/Seeds';
import { GuardianResult } from './screens/guardian/Result';
import { GuardianAlerts } from './screens/guardian/Alerts';
import { OwnerHome } from './screens/owner/Owner';
import { OperatorHome } from './screens/operator/Operator';
import { Component, type ReactNode } from 'react';
import { LoadError } from './components/Common';
import type { AccountRole } from './types';

// HashRouter: 정적 호스팅·파일 더블클릭에서도 새로고침 404가 없다 / 미리보기(임베드)는 MemoryRouter: VITE_ROUTER=memory
const Router = import.meta.env.VITE_ROUTER === 'memory' ? MemoryRouter : HashRouter;
const as = (role: AccountRole | AccountRole[], el: ReactNode) => <RequireRole role={role}>{el}</RequireRole>;
const guest = (el: ReactNode) => <GuestOnly>{el}</GuestOnly>;
const ALL: AccountRole[] = ['student', 'guardian', 'teacher', 'operator'];

/** 화면 하나가 그리다 깨져도 앱 전체가 하얗게 되지 않게 막는다. 「다시 시도」는 첫 화면으로 돌아가 다시 그린다 */
class ScreenErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="frame"><main className="screen-body">
        <LoadError error="화면을 그리다가 문제가 생겼어요." onRetry={() => { location.hash = '#/'; this.setState({ failed: false }); }} />
      </main></div>
    );
  }
}

export default function App() {
  return (
    <SessionProvider>
      <MentorProvider>
      <AuthProvider>
      <Router>
        <ScreenErrorBoundary>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={guest(<Login />)} />
          <Route path="/signup" element={guest(<Signup />)} />
          <Route path="/find" element={guest(<Find />)} />
          <Route path="/docs/:name" element={<DocPageView />} />
          <Route path="/welcome" element={as(ALL, <Welcome />)} />
          <Route path="/notifications" element={as(ALL, <Notifications />)} />
          <Route path="/settings" element={as(ALL, <Settings />)} />
          <Route path="/settings/profile" element={as(ALL, <SettingsProfile />)} />
          <Route path="/settings/password" element={as(ALL, <SettingsPassword />)} />
          <Route path="/settings/notify" element={as(ALL, <SettingsNotify />)} />
          <Route path="/settings/delete" element={as(ALL, <SettingsDelete />)} />
          <Route path="/settings/family" element={as(['student', 'guardian'], <SettingsFamily />)} />
          <Route path="/settings/org" element={as(['student', 'guardian', 'teacher'], <SettingsOrg />)} />

          <Route path="/student" element={as('student', <StudentToday />)} />
          <Route path="/student/onboarding/promise" element={as('student', <StudentPromise />)} />
          <Route path="/student/onboarding/character" element={as('student', <StudentCharacter />)} />
          <Route path="/student/difficulty" element={as('student', <StudentDifficulty />)} />
          <Route path="/student/solve" element={as('student', <StudentSolve />)} />
          <Route path="/student/done" element={as('student', <StudentDone />)} />
          <Route path="/student/chat" element={as('student', <StudentChat />)} />
          <Route path="/student/crisis" element={as('student', <StudentCrisis />)} />
          <Route path="/student/wrap" element={as('student', <StudentWrap />)} />
          <Route path="/student/records" element={as('student', <StudentRecords />)} />
          <Route path="/student/mentor" element={as('student', <StudentCharacter editMode />)} />
          <Route path="/student/shop" element={as('student', <StudentShop />)} />
          <Route path="/student/classes" element={as('student', <StudentClasses />)} />

          <Route path="/teacher/scope" element={as('teacher', <TeacherScope />)} />
          <Route path="/teacher/today" element={as('teacher', <TeacherToday />)} />
          <Route path="/teacher/results" element={as('teacher', <TeacherResults />)} />
          <Route path="/teacher/seeds" element={as('teacher', <TeacherSeeds />)} />
          <Route path="/teacher/alerts" element={as('teacher', <TeacherAlerts />)} />
          <Route path="/teacher/classes" element={as('teacher', <TeacherClasses />)} />

          <Route path="/guardian" element={as('guardian', <GuardianResult />)} />
          <Route path="/guardian/alerts" element={as('guardian', <GuardianAlerts />)} />

          <Route path="/owner" element={as('teacher', <OwnerHome />)} />
          <Route path="/operator" element={as('operator', <OperatorHome />)} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </ScreenErrorBoundary>
      </Router>
      </AuthProvider>
      </MentorProvider>
    </SessionProvider>
  );
}
