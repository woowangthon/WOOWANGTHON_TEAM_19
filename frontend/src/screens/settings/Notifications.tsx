// 알림함: 연결 요청·초대·승인·교환 요청·도장·칭찬 등. 열면 모두 읽음 처리.
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { homeFor, useAuth } from '../../state/auth';

export function Notifications() {
  const nav = useNavigate();
  const { me, refresh } = useAuth();
  const { data, error, loading, reload } = useAsync(() => api.getNotices());
  useEffect(() => { if (data) { api.readNotices().catch(() => {}); refresh(); } }, [data, refresh]);
  return (
    <Frame adult={me?.role !== 'student'} title="알림" back={homeFor(me)}>
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {data?.length === 0 && <div className="notice notice--plain"><span>새 알림이 없어요</span></div>}
      <ul className="list">
        {data?.map((n) => (
          <li key={n.id}>
            <button className={'card notice-item' + (n.read ? ' card--flat' : '')} onClick={() => n.to && nav(n.to)} disabled={!n.to}>
              {!n.read && <i className="notice-item__dot" aria-label="새 알림" />}
              <span style={{ minWidth: 0, flex: 1 }}><span className="small" style={{ display: 'block' }}>{n.text}</span><span className="small muted">{n.at}</span></span>
              {n.to && <Icon name="chevron" size={16} />}
            </button>
          </li>
        ))}
      </ul>
    </Frame>
  );
}
