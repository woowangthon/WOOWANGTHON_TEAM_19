// 위기 화면 — 조언을 멈추고 도움받을 곳을 보여 준다 (팀 기능 DB 필수 「키워드 감지 → 세션 종료」)
// 연락처 공식 출처(11-14 bb 확인, 수정 명세 B35 · 성호 승인):
//  - 1388 청소년상담: 성평등가족부 https://www.mogef.go.kr/cc/ccy/cc_ccy_f001.do — 휴대전화는 「지역번호+1388」,
//    문자는 「수신번호에 1388 입력 후 고민 전송」, 카카오톡 「청소년상담1388」 채널, 웹 https://www.1388.go.kr
//  - 109 자살예방 상담전화: 보건복지부 — 국번 없이 109
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { crisisLine } from '../../lib/crisisLine';
import { Frame } from '../../components/Frame';
import { MentorSays } from '../../components/Mascot';
import { CrisisAsk, CrisisContacts } from '../../components/CrisisHelp';
import { useMentor } from '../../state/mentor';
import { useSession } from '../../state/session';
import type { SessionView } from '../../types';

// 단계로 막지 않는다: 수업 잠금 화면의 「힘든 일이 있으면」 링크는 수다·풀기 중에도, 세션이 없어도 여기로 온다(연락처는 늘 보인다).
// 「보호자께 도움 요청하기」는 세션이 실제로 crisis 단계일 때만 보인다(서버가 그 세션에만 요청을 받는다)
export function StudentCrisis() {
  const { session, sync } = useSession();
  const crisisId = session?.phase === 'crisis' ? session.id : null;
  // 11-15 성호 「A안 완성」: 서버가 위기 때 남긴 고정 문장을 맨 위에(위기 세션일 때만, 실패·없음이면 문장 없이)
  const [line, setLine] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    if (crisisId) api.getChat(crisisId).then((c) => { if (alive) setLine(crisisLine(c.messages)); }, () => {});
    return () => { alive = false; };
  }, [crisisId]);
  const crisis = session?.phase === 'crisis' ? session : null;
  return <Crisis crisis={crisis} line={crisisId ? line : null} onAsked={(at) => { if (crisis) sync({ ...crisis, guardianRequestedAt: at }); }} />;
}

function Crisis({ crisis, line, onAsked }: { crisis: SessionView | null; line: string | null; onAsked: (at: string) => void }) {
  const nav = useNavigate();
  const { say } = useMentor();
  // 명세 부록 E(11-14 성호 A안, 11-15 완성): 고마움·위로는 서버 고정 문장이 맨 위에서, 그 아래 멘토 말은 연락 쪽만
  return (
    <Frame title={say('네 마음, 잘 들었어', '마음, 잘 들었어요')} actions={<button className="btn btn--secondary" onClick={() => nav('/student')}>처음 화면으로</button>}>
      {line && <div role="status"><MentorSays mood="calm" size={64} text={line} /></div>}
      {/* 11-15 성호: 보호자께 도움 요청(아이가 눌러야 감) 먼저, 연락처는 그 아래 */}
      {crisis ? <CrisisAsk sessionId={crisis.id} requestedAt={crisis.guardianRequestedAt} onAsked={onAsked} /> : !line && <MentorSays mood="calm" size={64} text={say('지금 한 번만 연락해 보자.', '지금 한 번만 연락해 봐요.')} />}
      <CrisisContacts full />
    </Frame>
  );
}
