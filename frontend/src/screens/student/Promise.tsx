// 학생 첫 실행 1/2 — 약속 (탭 숨김) + 안전 사전 고지 (BRIEF 안전 알림 정책 2)
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { MentorSays } from '../../components/Mascot';
import { LoadError } from '../../components/Common';
import { useAction } from '../../lib/useAction';
import { useMentor } from '../../state/mentor';

const DO = ['함께 생각하기', '힌트로 돕기', '끝까지 응원하기'];
const DONT = ['답부터 알려주기', '숙제 대신하기', '개인정보 묻기'];

export function StudentPromise() {
  const nav = useNavigate();
  const { say } = useMentor();
  // 저장이 실패하면 버튼 아래에 이유를 보이고, 보내는 동안은 다시 못 누르게(N4)
  const { run, busy, error } = useAction();
  const agree = () => run(async () => { await api.acceptPromise(); nav('/student/onboarding/character'); });
  return (
    <Frame title="약속" back="/student" right={<span className="pill pill--mint">1/2</span>}
      actions={<><LoadError error={error} /><button className="btn btn--primary" disabled={busy} onClick={agree}>{busy ? '저장하는 중…' : say('약속할게', '약속할게요')}</button></>}>
      <MentorSays mood="promise" size={64} text={say('우리, 이렇게 약속하고\n함께 공부하자!', '우리, 이렇게 약속하고\n함께 공부해요!')} />
      <section className="card stack">
        <h2 className="h3">같이 하는 것</h2>
        <ul className="list">{DO.map((t) => <li key={t}><span className="tick"><Icon name="check" size={14} /></span>{t}</li>)}</ul>
      </section>
      <section className="card stack">
        <h2 className="h3">안 하는 것</h2>
        <ul className="list muted">{DONT.map((t) => <li key={t}><span className="tick tick--no"><Icon name="close" size={12} /></span>{t}</li>)}</ul>
      </section>
      {/* B6 · 결정: AI 사용 고지는 첫 실행 약속 화면에서 1회 */}
      <div className="notice notice--plain" style={{ justifyContent: 'flex-start' }}>
        <Icon name="talk" size={20} />
        <span>{say('나는 사람이 아니라 AI 멘토야. 가끔 틀릴 수 있으니, 이상하면 선생님께 물어봐.', '저는 사람이 아니라 AI 멘토예요. 가끔 틀릴 수 있으니, 이상하면 선생님께 물어봐요.')}</span>
      </div>
      <div className="notice" style={{ justifyContent: 'flex-start' }}>
        <Icon name="shield" size={20} />
        {/* TK-74 #13 · 결정(11-11): 평소 수다는 안 보내고, 🔴일 때만 앞뒤 일부가 보호자에게 간다 */}
        <span>{say('보호자께는 오늘 배운 것과 퀴즈만 가. 평소 수다는 안 보내. 다만 너를 해칠 수 있는 걱정되는 얘기가 나오면, 그 말과 앞뒤 몇 마디를 보호자께 알려 줄게.', '보호자께는 오늘 배운 것과 퀴즈만 가요. 평소 수다는 보내지 않아요. 다만 스스로를 해칠 수 있는 걱정되는 얘기가 나오면, 그 말과 앞뒤 몇 마디를 보호자께 알려 드려요.')}</span>
      </div>
    </Frame>
  );
}
