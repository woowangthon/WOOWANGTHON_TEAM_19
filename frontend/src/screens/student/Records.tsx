// 학생 "기록" 탭 — 지난 학습을 한 줄씩(서버 기록 그대로). 점수·순위는 보여 주지 않는다.
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { LoadError, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';

export function StudentRecords() {
  const { data, error, loading, reload } = useAsync(() => api.getRecords());
  return (
    <Frame title="기록" exit tabs="student">
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {data?.length === 0 && <div className="notice notice--plain">아직 기록이 없어요. 오늘 첫 공부를 시작해 봐요.</div>}
      {data?.map((r) => (
        <article key={r.date} className="card">
          <div className="row between"><strong>{r.date}</strong></div>{/* B16: 난이도 늘 「중급」이라 표시하지 않음 */}
          <div className="small muted num" style={{ marginTop: 4 }}>{r.unit} · {r.solved}/{r.total}문제 · 힌트 {r.hints}번{r.chatted ? ' · 수다함' : ''}</div>
        </article>
      ))}
    </Frame>
  );
}
