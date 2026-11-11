// 학생 첫 실행 1/2 — 약속 (탭 숨김) + 안전 사전 고지 (BRIEF 안전 알림 정책 2)
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { MentorSays } from '../../components/Mascot';
import { useMentor } from '../../state/mentor';

const DO = ['함께 생각하기', '힌트로 돕기', '끝까지 응원하기'];
const DONT = ['답부터 알려주기', '숙제 대신하기', '개인정보 묻기'];

export function StudentPromise() {
  const nav = useNavigate();
  const { say } = useMentor();
  const agree = async () => { await api.acceptPromise(); nav('/student/onboarding/character'); };
  return (
    <Frame title="약속" back="/student" right={<span className="pill pill--mint">1/2</span>}
      actions={<button className="btn btn--primary" onClick={agree}>약속할게</button>}>
      <MentorSays mood="promise" size={64} text={say('우리, 이렇게 약속하고\n함께 공부하자!', '우리, 이렇게 약속하고\n함께 공부해요!')} />
      <section className="card stack">
        <h2 className="h3">같이 하는 것</h2>
        <ul className="list">{DO.map((t) => <li key={t}><span className="tick"><Icon name="check" size={14} /></span>{t}</li>)}</ul>
      </section>
      <section className="card stack">
        <h2 className="h3">안 하는 것</h2>
        <ul className="list muted">{DONT.map((t) => <li key={t}><span className="tick tick--no"><Icon name="close" size={12} /></span>{t}</li>)}</ul>
      </section>
      <div className="notice" style={{ justifyContent: 'flex-start' }}>
        <Icon name="shield" size={20} />
        <span>{say('걱정되는 얘기가 나오면 보호자께 알려 줄게. 우리 대화 내용은 안 보내.', '걱정되는 얘기가 나오면 보호자께 알려 드려요. 우리 대화 내용은 보내지 않아요.')}</span>
      </div>
    </Frame>
  );
}
