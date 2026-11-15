// 학생 ① 오늘 시작 — 탭 첫 화면(뒤로가기 없음). 상태에 따라 버튼이 달라진다:
// 처음 → 약속부터 / 진행 중 → 이어서 하기 / 끝남 → 내일 봐 / 과제 없음 → 안내
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { Mascot } from '../../components/Mascot';
import { LoadError, Thinking, Week } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useQuietPoll } from '../../lib/quietPoll';
import { useMentor } from '../../state/mentor';
import { assignedByLine } from '../../lib/difficultyNote';
import { routeFor, useSession } from '../../state/session';
import { syncFromHome } from '../../lib/sessionSync';
import { useAuth, useRefreshMeOnMount } from '../../state/auth';
import { SeedChip, StampChip } from '../../components/Seed';
import { StudentHomeworkCard } from '../../components/ClassBoard';
import { isCrisisDay } from '../../lib/kidScreens';
import { callName } from '../../lib/josa';

export function StudentToday() {
  const nav = useNavigate();
  const { say } = useMentor();
  const { me } = useAuth();
  useRefreshMeOnMount();
  const { data, error, loading, reload, quiet } = useAsync(() => api.getStudentHome());
  // 보호자가 도장을 찍거나 연결·강의실 수락이 되면 5초 안에 저절로 바뀌게(보호자·선생님 화면과 같은 조용한 다시 읽기, 성호 11-14)
  useQuietPoll([quiet]);
  // 서버가 준 오늘 세션으로 공유 세션도 맞춘다 — 그사이 수다 10분이 끝났으면(wrap) 「이어서 하기」가 빈 수다 화면으로 돌아가지 않게
  const { sync } = useSession();
  useEffect(() => { syncFromHome(data, sync); }, [data, sync]);

  let cta: { label: string; to?: string } = { label: '시작하기', to: '/student/difficulty' };
  let line = say('왔구나! 오늘은\n이것 하나만 같이 하자', '왔군요! 오늘은\n이것 하나만 같이 해요');
  if (data) {
    const inProgress = data.session && !['done', 'crisis'].includes(data.session.phase);
    // 위기(🔴)로 끝난 날은 축하하지 않고 차분하게. 문구는 임시(성호 확인 대상)
    if (data.doneToday && isCrisisDay(data)) { cta = { label: '오늘은 여기까지' }; line = say('오늘은 여기서 쉬자. 내일 또 이야기하자.\n믿을 수 있는 어른과 꼭 이야기해 줘', '오늘은 여기서 쉬어요. 내일 또 이야기해요.\n믿을 수 있는 어른과 꼭 이야기해 주세요'); /* 명세 부록 E ④(11-14 성호 승인) */ }
    else if (data.doneToday) { cta = { label: say('오늘은 끝! 내일 봐', '오늘은 끝! 내일 봐요') }; line = say('오늘도 해냈어!\n내일 또 만나자', '오늘도 해냈어요!\n내일 또 만나요'); }
    else if (inProgress) { cta = { label: '이어서 하기', to: routeFor(data.session) }; line = say('하던 데서\n이어서 하자', '하던 데서\n이어서 해요'); }
    else if (!data.task) { cta = { label: '오늘은 쉬는 날' }; line = say('오늘은 선생님이 정한\n공부가 없어. 푹 쉬어!', '오늘은 선생님이 정한\n공부가 없어요. 푹 쉬어요!'); }
    else if (data.needsOnboarding) cta = { label: '시작하기', to: '/student/onboarding/promise' };
    // v0.4 준비 단계: 보호자 연결 → 학원 입장 → 강의실 (이게 끝나야 선생님 과제가 생긴다)
    if (data.restricted) { cta = { label: '보호자와 연결하기', to: '/settings/family' }; line = say('먼저 보호자와\n연결해 줘!', '먼저 보호자와\n연결해 주세요!'); }
    else if (me && !me.academy) { cta = { label: '학원 코드 넣기', to: '/settings/org' }; line = say('학원에서 받은 코드를\n넣어 줘', '학원에서 받은 코드를\n넣어 주세요'); }
    else if (!data.inClass) { cta = { label: '강의실 들어가기', to: '/student/classes' }; line = say('선생님 강의실에\n들어가 보자', '선생님 강의실에\n들어가 봐요'); }
  }
  const setup = data && (data.restricted || (me && !me.academy) || !data.inClass);

  return (
    <Frame title="오늘 시작" exit tabs="student"
      actions={data && <button className="btn btn--primary" disabled={!cta.to} onClick={() => cta.to && nav(cta.to)}>{cta.label}</button>}>
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {data && (
        <>
          <section className="hero">
            <div className="hero__text">
              <span className="small muted">{data.dateLabel}</span>
              <h1 className="h1">{say(`${callName(data.name)}, 안녕!`, `${data.name}, 안녕하세요!`)}</h1>
              <span className="row" style={{ gap: 6 }}>
                <span className="pill pill--accent"><Icon name="flame" size={14} fill /> 연속 {data.streakDays}일</span>
                <SeedChip n={data.seeds} onClick={() => nav('/student/shop')} />
                <StampChip n={data.stamps ?? 0} onClick={() => nav('/student/shop', { state: { tab: 'deco' } })} />
              </span>
            </div>
            <Mascot mood={data.doneToday ? (isCrisisDay(data) ? 'calm' : 'cheer') : 'wave'} size={104} variant="face" outfit={me?.outfit} />
          </section>
          <p className="wallet-help">공부하면 씨앗 3개, 보호자랑 얘기하면 도장 1개</p>
          <StudentHomeworkCard />
          <div className="week week--lift" style={{ display: 'contents' }}><Week attendance={data.attendance} todayIndex={data.todayIndex} /></div>
          <div className="bubble" style={{ maxWidth: '100%' }}>{line}</div>
          {setup ? <SetupSteps linked={!data.restricted} academy={!!me?.academy} inClass={data.inClass} code={me?.linkCode ?? null} /> : data.task ? (
            <section className="card mission">
              <div className="mission__icon"><Icon name="book" size={26} /></div>
              <div style={{ minWidth: 0 }}>
                <div className="h3">{data.task.unit} · {data.task.count}문제 · 약 {data.task.minutes}분</div>
                <div className="small muted">{assignedByLine(data.task.assignedBy, say)}</div>
              </div>
            </section>
          ) : !data.doneToday && <div className="notice notice--plain">오늘 할 것이 아직 없어요</div>}
        </>
      )}
    </Frame>
  );
}

/** 시작 준비 3단계: 보호자 연결 → 학원 → 강의실 */
export function SetupSteps({ linked, academy, inClass, code }: { linked: boolean; academy: boolean; inClass: boolean; code: string | null }) {
  const { say } = useMentor();
  const steps = [
    { done: linked, label: '보호자와 연결', sub: code ? say(`내 코드 ${code}를 보호자에게 알려 줘`, `내 코드 ${code}를 보호자에게 알려 주세요`) : '' },
    { done: academy, label: '학원 들어가기', sub: '학원에서 받은 6자리 코드' },
    { done: inClass, label: '강의실 들어가기', sub: '선생님 초대를 받거나 참여 요청' },
  ];
  return (
    <section className="card stack" aria-label="시작 준비">
      <strong>시작 준비</strong>
      <ol className="setup">
        {steps.map((s, i) => (
          <li key={s.label} className={s.done ? 'done' : ''}>
            <span className="setup__n">{s.done ? <Icon name="check" size={14} /> : i + 1}</span>
            <span><strong className="small">{s.label}</strong>{!s.done && s.sub && <span className="small muted" style={{ display: 'block' }}>{s.sub}</span>}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
