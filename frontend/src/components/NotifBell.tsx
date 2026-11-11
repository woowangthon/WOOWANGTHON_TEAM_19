// 오른쪽 위 알림함(종). 안 읽은 알림 수를 빨간 점 대신 머스터드 숫자로 보여 준다.
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useAsync } from '../lib/useAsync';
import { Icon } from './Icon';

export function NotifBell() {
  const nav = useNavigate();
  const { data } = useAsync(() => api.getNotices().catch(() => []));
  const n = data?.filter((x) => !x.read).length ?? 0;
  return (
    <button className="icon-btn bell" aria-label={n ? `알림 ${n}개` : '알림'} onClick={() => nav('/notifications')}>
      <Icon name="bell" />{n > 0 && <span className="bell__n num">{n > 9 ? '9+' : n}</span>}
    </button>
  );
}
