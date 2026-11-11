// 모든 화면의 바깥 틀: 상단바(또는 직접 넣은 머리) + 내용 + 하단 버튼 영역 + (선택) 하단 탭
import type { ReactNode } from 'react';
import { TopBar, type TopBarProps } from './TopBar';
import { TabBar, type TabSet } from './TabBar';
import { useAuth } from '../state/auth';
import { frameClass } from '../lib/wide';

interface Props extends Partial<TopBarProps> {
  header?: ReactNode;     // 넣으면 기본 상단바 대신 이것을 쓴다(문제 풀이 화면의 진행 막대 등)
  tabs?: TabSet;          // 없으면 하단 탭을 숨긴다(첫 실행·풀이 중)
  adult?: boolean;        // 학습지도자·보호자: 저채도 팔레트
  actions?: ReactNode;    // 엄지 영역(하단) 버튼
  tone?: 'ok' | 'retry';  // 하단 영역 배경(정답/다시 도전 피드백)
  children: ReactNode;
}

export function Frame({ header, tabs, adult, actions, tone, children, title = '', ...top }: Props) {
  const role = useAuth().me?.role; // 학습지도자면 넓은 창에서 폰 틀을 푼다(lib/wide)
  return (
    <div className={frameClass({ adult, role })}>
      {header ?? <TopBar title={title} {...top} />}
      <main className="screen-body">{children}</main>
      {actions && <div className={'bottom-actions' + (tone ? ` bottom-actions--${tone}` : '')}>{actions}</div>}
      {tabs && <TabBar set={tabs} />}
    </div>
  );
}
