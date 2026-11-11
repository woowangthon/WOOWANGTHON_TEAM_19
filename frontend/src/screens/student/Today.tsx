// 학생 ① 오늘 시작 — 탭 첫 화면(뒤로가기 없음). 상태에 따라 버튼이 달라진다:
// 처음 → 약속부터 / 진행 중 → 이어서 하기 / 끝남 → 내일 봐 / 과제 없음 → 안내
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, restartDemoAll } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { Mascot } from '../../components/Mascot';
import { LoadError, Thinking, Week } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useMentor } from '../../state/mentor';
import { routeFor } from '../../state/session';
import { useAuth } from '../../state/auth';
import { SeedChip } from '../../components/Seed';
import { isCrisisDay, isDemoChild } from '../../lib/kidScreens';

export function StudentToday() {
  const nav = useNavigate();
  const { say } = useMentor();
  const { me, enter } = useAuth();
  const { data, error, loading, reload } = useAsync(() => api.getStudentHome());
  const [restarting, setRestarting] = useState(false);
  const [restartError, setRestartError] = useState<string | null>(null);
  // 시연용: 데모 아이만 「처음부터 다시 체험」. 서버·mock을 되돌리면 mock 로그인도 풀리므로 같은 계정으로 다시 들어온다
  const restart = async () => {
    if (!me) return;
    setRestarting(true); setRestartError(null);
    try { await restartDemoAll(); await enter(await api.demoLogin(me.id)); reload(); }
    catch (e) { setRestartError(`되돌리지 못했어요. ${(e as Error).message}`); }
    finally { setRestarting(false); }
  };

  let cta: { label: string; to?: string } = { label: '시작하기', to: '/student/difficulty' };
  let line = say('왔구나! 오늘은\n이것 하나만 같이 하자', '왔군요! 오늘은\n이것 하나만 같이 해요');
  if (data) {
    const inProgress = data.session && !['done', 'crisis'].includes(data.session.phase);
    // 위기(🔴)로 끝난 날은 축하하지 않고 차분하게. 문구는 임시(성호 확인 대상)
    if (data.doneToday && isCrisisDay(data)) { cta = { label: '오늘은 여기까지' }; line = say('오늘은 여기까지 할게.\n믿을 수 있는 어른과 꼭 이야기해 줘', '오늘은 여기까지 할게요.\n믿을 수 있는 어른과 꼭 이야기해 주세요'); }
    else if (data.doneToday) { cta = { label: '오늘은 끝! 내일 봐' }; line = say('오늘도 해냈어!\n내일 또 만나자', '오늘도 해냈어요!\n내일 또 만나요'); }
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
              <h1 className="h1">{say(`${data.name}야, 안녕!`, `${data.name}, 안녕하세요!`)}</h1>
              <span className="row" style={{ gap: 6 }}>
                <span className="pill pill--accent"><Icon name="flame" size={14} fill /> 연속 {data.streakDays}일</span>
                <SeedChip n={data.seeds} onClick={() => nav('/student/shop')} />
              </span>
            </div>
            <Mascot mood={data.doneToday ? (isCrisisDay(data) ? 'calm' : 'cheer') : 'wave'} size={104} variant="face" outfit={me?.outfit} />
          </section>
          <div className="week week--lift" style={{ display: 'contents' }}><Week attendance={data.attendance} todayIndex={data.todayIndex} /></div>
          <div className="bubble" style={{ maxWidth: '100%' }}>{line}</div>
          {setup ? <SetupSteps linked={!data.restricted} academy={!!me?.academy} inClass={data.inClass} code={me?.linkCode ?? null} /> : data.task ? (
            <section className="card mission">
              <div className="mission__icon"><Icon name="book" size={26} /></div>
              <div style={{ minWidth: 0 }}>
                <div className="h3">{data.task.unit} · {data.task.count}문제 · 약 {data.task.minutes}분</div>
                <div className="small muted">{data.task.assignedBy}이 정해 줬어요</div>
              </div>
            </section>
          ) : !data.doneToday && <div className="notice notice--plain">오늘 할 것이 아직 없어요</div>}
          {isDemoChild(me) && (
            <button className="exit-btn" style={{ alignSelf: 'center' }} disabled={restarting} onClick={restart}>{restarting ? '되돌리는 중…' : '처음부터 다시 체험'}</button>
          )}
          <LoadError error={restartError} />
        </>
      )}
    </Frame>
  );
}

/** 시작 준비 3단계: 보호자 연결 → 학원 → 강의실 */
function SetupSteps({ linked, academy, inClass, code }: { linked: boolean; academy: boolean; inClass: boolean; code: string | null }) {
  const steps = [
    { done: linked, label: '보호자와 연결', sub: code ? `내 코드 ${code}를 보호자에게 알려 줘` : '' },
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
