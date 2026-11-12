// 보호자 ① 결과(내 아이만) — 대화 내용·힌트 수·실수 상세는 보이지 않는다(BRIEF 세부 확정 2).
// v0.4: 아이와 연결 전이면 연결 안내 / "오늘 이야기 나눴어요" 도장(하루 1번, 씨앗 +2)
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { SeedChip, StampChip } from '../../components/Seed';
import { LoadError, Stat, Thinking, Week } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import { useAuth } from '../../state/auth';
import { GuardianClassCard } from '../../components/ClassSession';
import { GuardianHomeworkCard } from '../../components/ClassBoard';

export function GuardianResult() {
  const { me } = useAuth();
  if (!me) return null;
  if (me.linked.length === 0) return <NotLinked pending={me.pendingLinks.map((p) => p.name)} />;
  return <Linked />;
}

function NotLinked({ pending }: { pending: string[] }) {
  const nav = useNavigate();
  return (
    <Frame adult title="학습 결과" exit tabs="guardian"
      actions={<button className="btn btn--primary" onClick={() => nav('/settings/family')}><Icon name="link" size={18} />아이와 연결하기</button>}>
      <div className="spacer" />
      <div className="celebrate">
        <span className="path-card__icon" style={{ width: 64, height: 64 }}><Icon name="link" size={30} /></span>
        <h1 className="h2">아직 연결된 아이가 없어요</h1>
        <p className="muted small">{pending.length ? `${pending.join(', ')} 학생이 연결을 요청했어요. 동의하면 연결돼요.` : '아이의 연결 코드 6자리를 받아 넣어 주세요.'}</p>
      </div>
      <div className="spacer" />
    </Frame>
  );
}

function Linked() {
  const nav = useNavigate();
  const { data, error, loading, reload } = useAsync(() => api.getGuardianToday());
  const stamp = useAsync(() => api.getStampState());
  const { run, busy, error: actErr } = useAction();
  return (
    <Frame adult title="학습 결과" exit tabs="guardian">
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error ?? actErr} onRetry={reload} />
      {data && (
        <>
          <div className="row between">
            <div><h1 className="h2">{data.childName}</h1><div className="small muted">{data.dateLabel} · 내 아이의 오늘</div></div>
            {stamp.data && <><SeedChip n={stamp.data.balance} /><StampChip n={stamp.data.stamps ?? 0} /></>}
          </div>
          {/* 강의실 수업 상태(픽업용, 11-13). 원장님이 「보호자에게 알리기」를 끄면 안 보인다 */}
          <GuardianClassCard />
          <GuardianHomeworkCard />
          {data.alertNotice ? (
            <section className="card card--warn row between">
              <strong>{data.alertNotice}</strong>
              <button className="btn btn--primary btn--small" onClick={() => nav('/guardian/alerts')}><Icon name="bell" size={16} />알림 보기</button>
            </section>
          ) : data.done ? (
            <>
              <div className="stats" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <Stat label={`${data.unit} · 푼 문제`} value={`${data.solved}문제`} />
                <Stat label="연속" value={`${data.streak}일`} />
              </div>
              {data.line && <section className="card"><div className="small muted">오늘 한 줄</div><div>{data.line}</div></section>}
              {data.hardPoint && <section className="card"><div className="small muted">아이가 고른 어려운 점</div><span className="pill pill--mint" style={{ fontSize: 14, marginTop: 4 }}>{data.hardPoint}</span></section>}
              {data.quiz && <section className="card card--warn"><div className="small muted">아이가 낸 퀴즈</div><strong>{data.quiz}</strong></section>}
            </>
          ) : <div className="notice notice--plain">아직 오늘 공부 전이에요 · 연속 {data.streak}일</div>}

          <section className={'card stamp-card' + (stamp.data?.stampedToday ? ' stamp-card--done' : '')}>
            <span className="stamp-card__mark"><Icon name="stamp" size={28} /></span>
            <div className="stamp-card__body" style={{ minWidth: 0, flex: 1 }}>
              <strong>{stamp.data?.stampedToday ? '오늘 도장을 찍었어요' : '오늘 하루 이야기를 나눴나요?'}</strong>
              <div className="small">이야기의 내용을 평가하지 않고, 함께 이야기한 것에 도장을 줘요.</div>
              <div className="small muted">하루 1번 · 칭찬 도장 1개 · 옷과 이모티콘 꾸미기에 써요</div>
              <span className={'pill ' + (stamp.data?.stampedToday ? 'pill--mint' : 'pill--accent')}>{stamp.data?.stampedToday ? '오늘 찍음' : '아직 찍지 않음'}</span>
            </div>
            {stamp.data && !stamp.data.stampedToday && (
              <button className="btn btn--primary btn--small" disabled={busy} onClick={() => run(async () => stamp.setData(await api.stamp()))}>도장 찍기</button>
            )}
          </section>

          <section className="card">
            <div className="small muted">선생님 코멘트</div>
            <div>{data.teacherComment ?? '아직 승인된 코멘트가 없어요.'}</div>
          </section>
          <h2 className="h3">이번 주 함께한 날</h2>
          <Week attendance={data.attendance} todayIndex={data.todayIndex} />
          <p className="small muted" style={{ textAlign: 'center' }}>대화 내용은 표시하지 않아요</p>
        </>
      )}
    </Frame>
  );
}
