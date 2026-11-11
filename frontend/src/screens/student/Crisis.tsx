// 위기 화면 — 조언을 멈추고 도움받을 곳을 보여 준다 (팀 기능 DB 필수 「키워드 감지 → 세션 종료」)
// 연락처(109·1388)는 배포 전에 공식 기관 안내로 다시 확인할 것. 1388 문자 번호(#1388/1388)는 출처마다 달라 번호를 적지 않는다(11-12).
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
      <MentorSays mood="calm" size={64} text={say('말해 줘서 정말 고마워.\n혼자 버티지 않아도 돼.\n지금 한 번만 전화해 보자.', '말해 줘서 정말 고마워요.\n혼자 버티지 않아도 돼요.\n지금 한 번만 전화해 봐요.')} />
      {/* 11-12 결정: 연락하게 미는 배치 — 1388을 가장 크게, 109는 그 아래 */}
      <a className="btn btn--primary" href="tel:1388" style={{ flexDirection: 'column', gap: 2, minHeight: 72, textDecoration: 'none' }}>
        <strong className="num" style={{ fontSize: 28 }}>1388</strong>
        <span>청소년 상담전화 · 24시간 · 지금 전화하기</span>
      </a>
      <a className="btn btn--secondary" href="tel:109" style={{ justifyContent: 'flex-start', gap: 12, textDecoration: 'none' }}><strong className="num" style={{ fontSize: 20 }}>109</strong> 자살예방 상담전화 전화하기</a>
      <section className="card card--flat">
        <p>{say('전화가 어려우면 1388은 문자나 카카오톡으로도 이야기할 수 있어.', '전화가 어려우면 1388은 문자나 카카오톡으로도 이야기할 수 있어요.')}</p>
        <p className="small muted" style={{ marginTop: 6 }}>{say('보호자나 선생님께 “할 이야기가 있어” 한마디만 해도 충분해.', '보호자나 선생님께 “할 이야기가 있어요” 한마디만 해도 충분해요.')}</p>
      </section>
      <div className="notice" style={{ justifyContent: 'flex-start' }}>
        <Icon name="shield" size={20} />
        <span>약속한 대로 보호자께 “확인이 필요해요”라는 알림만 보냈어. 우리 대화 내용은 보내지 않았어.</span>
      </div>
    </Frame>
  );
}
