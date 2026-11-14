// 학습지도자 ③ 학생 결과 — 살펴볼 학생이 위로 온다. 힌트 수·실수 유형은 학습지도자만 본다(BRIEF 세부 확정 2).
// 초급만 계속 고르면 노란 표시 → 판단은 사람이 한다(11-09 결정).
import { useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { dateLabel } from '../../lib/date';
import { useAsync } from '../../lib/useAsync';
import { useTeacherWide } from '../../lib/wide';
import type { StudentResult } from '../../types';

const REPEAT_FLAG = 3; // 연속 초급 선택이 이 횟수 이상이면 표시

// B29: 난이도는 서버 고정값(늘 「중급」)이라 학생별 값처럼 보이지 않게 표에서 뺀다(B16과 같게)
export function TeacherResults() {
  const { data, error, loading, reload } = useAsync(() => api.getResults());
  const [talk, setTalk] = useState<StudentResult | null>(null);
  const flagged = (s: StudentResult) => s.beginnerRepeat >= REPEAT_FLAG;
  const sorted = data ? [...data].sort((a, b) => Number(flagged(b)) - Number(flagged(a)) || Number(a.done) - Number(b.done)) : [];
  const done = data?.filter((s) => s.done).length ?? 0;
  const wide = useTeacherWide(); // 넓은 화면: 카드 대신 표

  return (
    <Frame adult title="학생 결과" exit tabs="teacher">
      <div className="row between small"><span>{dateLabel()}</span>{data && <strong className="num">학습 완료 {done} / {data.length}명</strong>}</div>
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {wide && sorted.length > 0 && (
        <table className="table table--results">
          <thead><tr><th>학생</th><th>상태</th><th>단원</th><th>문제</th><th>힌트</th><th>실수</th><th>어려운 점</th><th>연속</th><th></th></tr></thead>
          <tbody>
            {sorted.map((s) => (
              <tr key={s.id}>
                <td><strong>{s.name}</strong></td>
                <td>{flagged(s) ? <span className="pill pill--accent"><Icon name="warn" size={14} /> 초급만 계속</span>
                  : <span className={s.done ? 'pill pill--solid' : 'pill'}>{s.done ? '완료' : '아직'}</span>}
                  {flagged(s) && <div className="small muted num" style={{ marginTop: 4 }}>최근 {s.beginnerRepeat}회 연속 초급</div>}</td>
                {s.done ? (
                  <>
                    <td>{s.unit}</td>
                    <td className="num">{s.solved}/{s.total}</td>
                    <td className="num">{s.hints}번</td>
                    <td>{s.mistake || '-'}</td>
                    <td>{s.hardPoint || '-'}</td>
                  </>
                ) : <td colSpan={6} className="muted">오늘은 아직 공부하지 않았어요</td>}
                <td className="num">{s.streak}일</td>
                <td>{flagged(s) && <button className="btn btn--secondary btn--small" onClick={() => setTalk(s)}>이야기 나눠 보기</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!wide && sorted.map((s) => (
        <article key={s.id} className={'card' + (flagged(s) ? ' card--warn' : '')}>
          <div className="row between">
            <h2 className="h3">{s.name}</h2>
            {flagged(s) ? <span className="pill pill--accent"><Icon name="warn" size={14} /> 초급만 계속</span>
              : <span className={s.done ? 'pill pill--solid' : 'pill'}>{s.done ? '완료' : '아직'}</span>}
          </div>
          {s.done ? (
            <>
              <div className="small num" style={{ margin: '6px 0 2px' }}>{s.unit} · {s.solved}/{s.total}문제 · 연속 {s.streak}일</div>
              <div className="small muted num">힌트 {s.hints}번{s.mistake ? ` · 실수: ${s.mistake}` : ''}</div>
              {s.hardPoint && <div className="small">학생이 고른 어려운 점: {s.hardPoint}</div>}
            </>
          ) : <div className="small muted" style={{ marginTop: 6 }}>오늘은 아직 공부하지 않았어요 · 연속 {s.streak}일</div>}
          {flagged(s) && (
            <div className="row between small" style={{ marginTop: 10 }}>
              <span className="muted num">최근 {s.beginnerRepeat}회 연속 초급</span>
              <button className="btn btn--secondary btn--small" onClick={() => setTalk(s)}>이야기 나눠 보기</button>
            </div>
          )}
        </article>
      ))}
      {talk && (
        <Sheet title={`${talk.name}와 이야기 나눠 보기`} onClose={() => setTalk(null)}>
          <p className="small muted">초급을 계속 고르는 이유는 여러 가지예요. 정말 어려운 건지, 편해서 고르는 건지는 대화로 확인해 주세요.</p>
          <ul className="list">
            <li>“요즘 문제 풀 때 어떤 게 제일 헷갈려?”</li>
            <li>“중급 한 문제만 같이 해 볼까? 막히면 내가 옆에 있을게.”</li>
          </ul>
          {talk.mistake && <div className="notice notice--plain">최근 실수: {talk.mistake}</div>}
          <button className="btn btn--primary" onClick={() => setTalk(null)}>확인</button>
        </Sheet>
      )}
    </Frame>
  );
}
