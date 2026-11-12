// 하단 탭. 역할마다 구성이 다르다 (BRIEF 11-10 확정: 학습지도자 4탭 → v0.4 씨앗 추가 5탭, 보호자 2탭)
// 11-11: 선생님·학생 모두 「강의실」 탭 추가. 선생님은 5칸 유지를 위해 「알림」(긴급)을 할 일 화면 오른쪽 위로 옮김
import { Link, NavLink } from 'react-router-dom';
import { Icon, type IconName } from './Icon';
import { useClassLocked } from './ClassSession';
import { LOCKED_IN_CLASS } from '../lib/classSession';

export type TabSet = 'student' | 'teacher' | 'guardian';

const TABS: Record<TabSet, { to: string; label: string; icon: IconName }[]> = {
  student: [
    { to: '/student', label: '오늘', icon: 'home' },
    { to: '/student/records', label: '기록', icon: 'records' },
    { to: '/student/classes', label: '강의실', icon: 'people' },
    { to: '/student/mentor', label: '내 멘토', icon: 'mentor' },
  ],
  teacher: [
    { to: '/teacher/scope', label: '범위', icon: 'scope' },
    { to: '/teacher/today', label: '할 일', icon: 'todo' },
    { to: '/teacher/classes', label: '강의실', icon: 'people' },
    { to: '/teacher/results', label: '결과', icon: 'records' },
    { to: '/teacher/seeds', label: '씨앗', icon: 'seed' },
  ],
  guardian: [
    { to: '/guardian', label: '결과', icon: 'records' },
    { to: '/guardian/alerts', label: '알림', icon: 'bell' },
  ],
};

export function TabBar({ set }: { set: TabSet }) {
  const locked = useClassLocked(); // 학생 수업 중: 잠긴 탭은 자물쇠로 보인다(누르면 잠금 안내)
  return (
    <nav className="tabbar" aria-label="하단 탭">
      {/* GPT-019: 태블릿 레일은 얼굴, PC 사이드바는 얼굴+글자. 휴대폰 하단 탭에서는 CSS로 숨김 */}
      <Link className="brand-logo brand-logo--nav" to={TABS[set][0].to} aria-label="AI 멘토 홈">
        <img src={`${import.meta.env.BASE_URL}mascot/horse/wave-avatar.png`} alt="" /><span>AI 멘토</span>
      </Link>
      {TABS[set].map((t) => (
        <NavLink key={t.to} to={t.to} end className={({ isActive }) => 'tab' + (isActive ? ' tab--active' : '')}>
          <Icon name={locked && LOCKED_IN_CLASS.includes(t.to) ? 'lock' : t.icon} size={22} />
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
