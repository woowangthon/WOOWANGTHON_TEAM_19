// 위기 화면 — 조언을 멈추고 도움받을 곳을 보여 준다 (팀 기능 DB 필수 「키워드 감지 → 세션 종료」)
// 연락처(109·1388)는 배포 전에 공식 기관 안내로 다시 확인할 것.
import { useNavigate } from 'react-router-dom';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { MentorSays } from '../../components/Mascot';
import { useMentor } from '../../state/mentor';
import { RequirePhase } from '../../state/session';

export function StudentCrisis() {
  return <RequirePhase phase="crisis"><Crisis /></RequirePhase>;
}

function Crisis() {
  const nav = useNavigate();
  const { say } = useMentor();
  return (
    <Frame title="잠깐 멈출게" actions={<button className="btn btn--secondary" onClick={() => nav('/student')}>처음 화면으로</button>}>
      <MentorSays mood="calm" size={64} text={say('말해 줘서 정말 고마워.\n지금은 믿을 수 있는 어른과\n꼭 이야기했으면 좋겠어.', '말해 줘서 정말 고마워요.\n지금은 믿을 수 있는 어른과\n꼭 이야기했으면 좋겠어요.')} />
      <section className="card">
        <h2 className="h3">지금 바로 이야기할 수 있는 곳</h2>
        <ul className="list" style={{ marginTop: 10 }}>
          <li><a href="tel:109" style={{ color: 'inherit', textDecoration: 'none' }}><strong className="num" style={{ fontSize: 20, userSelect: 'all' }}>109</strong></a> 자살예방 상담전화</li>
          <li><a href="tel:1388" style={{ color: 'inherit', textDecoration: 'none' }}><strong className="num" style={{ fontSize: 20, userSelect: 'all' }}>1388</strong></a> 청소년 상담전화</li>
        </ul>
      </section>
      <div className="notice" style={{ justifyContent: 'flex-start' }}>
        <Icon name="shield" size={20} />
        <span>약속한 대로 보호자께 “확인이 필요해요”라는 알림만 보냈어. 우리 대화 내용은 보내지 않았어.</span>
      </div>
    </Frame>
  );
}
