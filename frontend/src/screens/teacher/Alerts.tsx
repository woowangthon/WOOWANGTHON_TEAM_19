// 학습지도자 ④ 알림 — 긴급일 때만, 분류 없이 (BRIEF 안전 알림 정책 1 · 화면 구성 2)
// 11-09 팀 메모: 11-15 시연 범위에서는 학습지도자 알림이 후속일 수 있음 → 서버에 없으면 이 탭만 숨기면 된다.
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';

export function TeacherAlerts() {
  const { data, error, loading, reload } = useAsync(() => api.getTeacherAlerts());
  return (
    <Frame adult title="알림" exit tabs="teacher">
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {data?.length === 0 && <div className="notice notice--plain">긴급 알림이 없어요.</div>}
      {data?.map((a) => (
        <article key={a.id} className="card card--danger">
          <div className="row between small"><span className="pill pill--danger">긴급</span><span className="muted num">{a.at}</span></div>
          <h2 className="h3" style={{ margin: '8px 0 4px' }}>{a.studentName}</h2>
          <div className="row"><Icon name="warn" size={18} /> 긴급 확인 필요 · 보호자에게도 전달됨</div>
          <p className="small muted" style={{ marginTop: 6 }}>보호자 상태: {a.status}. 대화 내용과 분류는 학습지도자에게 표시하지 않아요.</p>
        </article>
      ))}
    </Frame>
  );
}
