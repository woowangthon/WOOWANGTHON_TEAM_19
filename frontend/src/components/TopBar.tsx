// 상단바: 뒤로가기 / 화면 이름 / 작은 "AI 멘토" 라벨 / 오른쪽 보조 요소
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from './Icon';
import { NotifBell } from './NotifBell';
import { useAuth } from '../state/auth';

/** 시안(성호 11-15): 어른 화면은 누구용인지 상표 옆에 붙인다. 아이 화면은 그대로 「AI 멘토」 */
export function brandLabel(role?: string): string {
  if (role === 'teacher') return 'AI 멘토 · 학습지도자용';
  if (role === 'guardian') return 'AI 멘토 · 보호자용';
  return 'AI 멘토';
}

export interface TopBarProps {
  title: string;
  back?: boolean | string;   // 문자열이면 그 경로로. 탭 첫 화면은 뒤로가기 없음(BRIEF 화면 구성 6)
  right?: ReactNode;
  /** 탭 첫 화면용: 왼쪽 위 「설정」(톱니) + 오른쪽 위 「알림함」(종) */
  exit?: boolean;
}

export function TopBar({ title, back, right, exit }: TopBarProps) {
  const nav = useNavigate();
  const { me } = useAuth();
  return (
    <header className="topbar">
      <div className="topbar__side">
        {back && <button className="icon-btn" aria-label="뒤로" onClick={() => (typeof back === 'string' ? nav(back) : nav(-1))}><Icon name="back" /></button>}
        {exit && <button className="icon-btn" aria-label="설정" onClick={() => nav('/settings')}><Icon name="gear" /></button>}
      </div>
      <div className="topbar__center">
        <div className="topbar__title">{title}</div>
        <div className="topbar__label">{brandLabel(me?.role)}</div>
      </div>
      <div className="topbar__side topbar__side--right">{right}{exit && <NotifBell />}</div>
    </header>
  );
}
