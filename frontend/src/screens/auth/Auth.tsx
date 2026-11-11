// 로그인 · 회원가입(단계형) · 아이디/비밀번호 찾기 · 가입 완료 · 약관 보기
// 규칙(아이디·비밀번호 형식, 중복, 필수 약관)은 서버(org.ts)가 최종 판단한다. 화면은 미리 알려 주는 역할.
import { useState, type ReactNode } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, API_MODE } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon, type IconName } from '../../components/Icon';
import { Mascot } from '../../components/Mascot';
import { LoadError, Sheet } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import { homeFor, useAuth } from '../../state/auth';
import { DOCS } from '../../data/docs';
import { ROLE_LABEL, type Agreements, type SignupBody } from '../../types';
import { DEMO_PASSWORD, ID_RULE, PW_RULE } from '../../api/org';

/* ======================= 로그인 ======================= */
export function Login() {
  const nav = useNavigate();
  const { enter } = useAuth();
  const [id, setId] = useState('');
  const [pw, setPw] = useState('');
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(true);
  const [demo, setDemo] = useState(false);
  const { run, busy, error } = useAction();
  const submit = () => run(async () => { const me = await api.login(id, pw, remember); await enter(me); nav(homeFor(me), { replace: true }); });

  return (
    <Frame title="" header={<div style={{ height: 12 }} />}>
      <div className="login-hero">
        <Mascot mood="wave" size={96} variant="face" />
        <h1 className="h1">AI 멘토</h1>
        <p className="small muted">하루 20분, 같이 푸는 공부 친구</p>
      </div>
      <form className="stack" onSubmit={(e) => { e.preventDefault(); if (id && pw) submit(); }}>
        <input className="input" aria-label="아이디" placeholder="아이디" autoComplete="username" autoCapitalize="none" value={id} onChange={(e) => setId(e.target.value)} />
        <div className="pw-field">
          <input className="input" aria-label="비밀번호" placeholder="비밀번호" type={show ? 'text' : 'password'} autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} />
          <button type="button" className="icon-btn pw-field__eye" aria-label={show ? '비밀번호 숨기기' : '비밀번호 보기'} onClick={() => setShow(!show)}><Icon name={show ? 'eyeOff' : 'eye'} size={20} /></button>
        </div>
        <label className="check-inline"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> 자동 로그인</label>
        <LoadError error={error} />
        <button type="submit" className="btn btn--primary" disabled={!id || !pw || busy}>로그인</button>
      </form>
      <nav className="link-row" aria-label="계정 도움">
        <button onClick={() => nav('/find?tab=id')}>아이디 찾기</button><i />
        <button onClick={() => nav('/find?tab=pw')}>비밀번호 찾기</button><i />
        <button className="strong" onClick={() => nav('/signup')}>회원가입</button>
      </nav>
      <div className="spacer" />
      <button className="btn btn--ghost btn--small" style={{ alignSelf: 'center' }} onClick={() => setDemo(true)}>체험 계정으로 둘러보기 (시연)</button>
      {demo && <DemoSheet onPick={(loginId) => { setId(loginId); setPw(DEMO_PASSWORD); setDemo(false); }} onClose={() => setDemo(false)} />}
    </Frame>
  );
}

/** 심사위원용: 체험 계정을 누르면 아이디·비밀번호가 채워진다 + 시연 설정 */
function DemoSheet({ onPick, onClose }: { onPick: (loginId: string) => void; onClose: () => void }) {
  const { data: accounts } = useAsync(() => api.demoAccounts());
  const { data: settings, setData } = useAsync(() => api.getDemo());
  const [resetDone, setResetDone] = useState(false);
  return (
    <Sheet title="체험 계정 (시연용)" onClose={onClose}>
      <p className="small muted">누르면 아이디·비밀번호가 채워져요. 비밀번호는 모두 <strong className="num">{DEMO_PASSWORD}</strong></p>
      <div className="stack">
        {accounts?.map((a) => (
          <button key={a.id} className="card row between" style={{ padding: '10px 14px' }} onClick={() => onPick(a.loginId)}>
            <span><span className="pill" style={{ marginRight: 6 }}>{ROLE_LABEL[a.role]}</span><strong>{a.name}</strong>{a.note && <span className="small muted"> · {a.note}</span>}</span>
            <span className="small muted num">{a.loginId}</span>
          </button>
        ))}
      </div>
      <section className="card card--flat stack" aria-label="시연 설정">
        <div className="row between"><strong className="small">시연 설정</strong><span className="pill">{API_MODE === 'mock' ? '가짜 서버' : '실제 서버'}</span></div>
        <label className="row between small" style={{ cursor: 'pointer' }}>
          <span>빠른 시연 <span className="muted">(20분 → 1분)</span></span>
          <input type="checkbox" checked={!!settings?.fast} onChange={async () => settings && setData(await api.setDemo({ fast: !settings.fast }))} style={{ width: 20, height: 20, accentColor: 'var(--color-primary)' }} />
        </label>
        <button className="btn btn--ghost btn--small" style={{ alignSelf: 'flex-start', padding: 0 }}
          onClick={async () => { await api.resetDemo(); setResetDone(true); }}>{resetDone ? '처음 상태로 되돌렸어요 ✓' : '시연 데이터 처음으로'}</button>
      </section>
    </Sheet>
  );
}

/* ======================= 회원가입 (단계형) ======================= */
type Role = SignupBody['role'];
const ROLES: { role: Role; icon: IconName; title: string; sub: string }[] = [
  { role: 'student', icon: 'book', title: '학생이에요', sub: '매일 20분, 멘토와 같이 풀어요' },
  { role: 'guardian', icon: 'user', title: '보호자예요', sub: '아이와 연결하고 오늘 결과를 봐요' },
  { role: 'teacher', icon: 'people', title: '학습지도자예요', sub: '학원·학교 선생님 · 원장님도 여기로' },
];

export function Signup() {
  const nav = useNavigate();
  const { enter } = useAuth();
  const [step, setStep] = useState(0);
  const [role, setRole] = useState<Role | null>(null);
  const [agree, setAgree] = useState<Agreements>({ terms: false, privacy: false, marketing: false });
  const [f, setF] = useState({ loginId: '', password: '', confirm: '', name: '', email: '', grade: 4 as 4 | 5 | 6 });
  const [idOk, setIdOk] = useState<null | boolean>(null);
  const [doc, setDoc] = useState<string | null>(null);
  const { run, busy, error, setError } = useAction();
  const kid = role === 'student';
  const set = (k: keyof typeof f, v: string | number) => { setF({ ...f, [k]: v }); if (k === 'loginId') setIdOk(null); };
  const pwOk = PW_RULE.test(f.password);
  const same = f.password.length > 0 && f.password === f.confirm;
  const infoOk = idOk === true && pwOk && same && f.name.trim() && (kid || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email));
  const back = () => (step === 0 ? nav('/login') : (setError(null), setStep(step - 1)));

  const checkId = () => run(async () => setIdOk(await api.checkLoginId(f.loginId)));
  const submit = () => run(async () => {
    const me = await api.signup({ role: role!, loginId: f.loginId, password: f.password, name: f.name, agreements: agree, ...(kid ? { grade: f.grade } : { email: f.email }) });
    await enter(me); nav('/welcome', { replace: true });
  });

  const titles = ['어떤 분인가요?', '약관 동의', '정보 입력'];
  let action: ReactNode = null;
  if (step === 1) action = <button className="btn btn--primary" disabled={!agree.terms || !agree.privacy} onClick={() => setStep(2)}>다음</button>;
  if (step === 2) action = <button className="btn btn--primary" disabled={!infoOk || busy} onClick={submit}>가입하기</button>;

  return (
    <Frame adult={!!role && !kid} title="회원가입" back={false} right={<span className="pill pill--mint">{step + 1}/3</span>}
      header={<header className="topbar"><div className="topbar__side"><button className="icon-btn" aria-label="뒤로" onClick={back}><Icon name="back" /></button></div>
        <div className="topbar__center"><div className="topbar__title">회원가입</div><div className="topbar__label">{titles[step]}</div></div>
        <div className="topbar__side topbar__side--right"><span className="pill pill--mint">{step + 1}/3</span></div></header>}
      actions={action}>
      <div className="progress progress--thin" aria-hidden><div className="progress__fill" style={{ width: `${((step + 1) / 3) * 100}%` }} /></div>

      {step === 0 && (
        <>
          <h1 className="h2">어떤 분인가요?</h1>
          <div className="stack">
            {ROLES.map((r) => (
              <button key={r.role} className="card path-card" onClick={() => { setRole(r.role); setStep(1); }}>
                <span className="path-card__icon"><Icon name={r.icon} size={24} /></span>
                <span style={{ minWidth: 0, flex: 1 }}><strong>{r.title}</strong><span className="small muted" style={{ display: 'block' }}>{r.sub}</span></span>
                <Icon name="chevron" size={18} />
              </button>
            ))}
          </div>
          <p className="small muted">학원·학교를 새로 등록하려면 <strong>학습지도자</strong>로 가입한 뒤 설정 → 소속에서 신청해요.</p>
        </>
      )}

      {step === 1 && (
        <>
          <label className="agree agree--all">
            <input type="checkbox" checked={agree.terms && agree.privacy && agree.marketing} onChange={(e) => setAgree({ terms: e.target.checked, privacy: e.target.checked, marketing: e.target.checked })} />
            <strong>전체 동의</strong>
          </label>
          <div className="card card--flat" style={{ padding: 0 }}>
            <AgreeRow label="[필수] 이용약관" checked={agree.terms} onChange={(v) => setAgree({ ...agree, terms: v })} onView={() => setDoc('terms')} />
            <AgreeRow label="[필수] 개인정보 수집·이용" checked={agree.privacy} onChange={(v) => setAgree({ ...agree, privacy: v })} onView={() => setDoc('privacy')} />
            <AgreeRow label="[선택] 이벤트·소식 알림" checked={agree.marketing} onChange={(v) => setAgree({ ...agree, marketing: v })} />
          </div>
          {kid && (
            <div className="notice"><span><strong>만 14세 미만이면 보호자 동의가 필요해요.</strong> 가입한 뒤 보호자와 연결하면 보호자가 동의해 줘요. 그 전에는 학원 입장과 수다가 잠겨 있어요.</span></div>
          )}
        </>
      )}

      {step === 2 && (
        <>
          <label className="field">아이디
            <div className="row">
              <input className="input" value={f.loginId} autoCapitalize="none" autoComplete="username" placeholder="영문 소문자로 시작 4~16자" onChange={(e) => set('loginId', e.target.value.toLowerCase())} />
              <button className="btn btn--secondary btn--small" style={{ minHeight: 46 }} disabled={!f.loginId || busy} onClick={checkId}>중복 확인</button>
            </div>
            {idOk === true && <span className="hint hint--ok">쓸 수 있는 아이디예요</span>}
            {idOk === false && <span className="hint hint--bad">이미 쓰는 아이디예요</span>}
            {idOk === null && f.loginId && !ID_RULE.test(f.loginId) && <span className="hint">영문 소문자로 시작, 소문자·숫자·_ 4~16자</span>}
          </label>
          <label className="field">비밀번호
            <input className="input" type="password" autoComplete="new-password" value={f.password} placeholder="영문+숫자 8~20자" onChange={(e) => set('password', e.target.value)} />
            {f.password && <span className={'hint ' + (pwOk ? 'hint--ok' : '')}>{pwOk ? '좋아요' : '영문과 숫자를 섞어 8~20자'}</span>}
          </label>
          <label className="field">비밀번호 확인
            <input className="input" type="password" autoComplete="new-password" value={f.confirm} onChange={(e) => set('confirm', e.target.value)} />
            {f.confirm && <span className={'hint ' + (same ? 'hint--ok' : 'hint--bad')}>{same ? '같아요' : '위와 달라요'}</span>}
          </label>
          <label className="field">{kid ? '별명 (멘토가 불러 줄 이름)' : '이름'}
            <input className="input" value={f.name} maxLength={12} placeholder={kid ? '예: 지우' : '예: 김선생님'} onChange={(e) => set('name', e.target.value)} />
          </label>
          {kid ? (
            <div className="field">학년
              <div className="chip-row" role="radiogroup" aria-label="학년">
                {([4, 5, 6] as const).map((g) => <button key={g} role="radio" aria-checked={f.grade === g} className={'chip' + (f.grade === g ? ' chip--on' : '')} onClick={() => set('grade', g)}>{g}학년</button>)}
              </div>
              <span className="hint">진짜 이름·전화번호는 적지 마세요</span>
            </div>
          ) : (
            <label className="field">이메일 <span className="hint">아이디·비밀번호를 찾을 때 써요</span>
              <input className="input" type="email" inputMode="email" autoComplete="email" value={f.email} onChange={(e) => set('email', e.target.value)} />
            </label>
          )}
          {role === 'teacher' && <div className="notice notice--plain"><span>학원·학교 소속은 가입한 뒤 <strong>설정 → 소속</strong>에서 일련번호로 신청하거나, 새로 등록할 수 있어요.</span></div>}
          <LoadError error={error} />
        </>
      )}
      {doc && <DocSheet name={doc} onClose={() => setDoc(null)} />}
    </Frame>
  );
}

function AgreeRow({ label, checked, onChange, onView }: { label: string; checked: boolean; onChange: (v: boolean) => void; onView?: () => void }) {
  return (
    <div className="agree">
      <label className="agree__label"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} /> {label}</label>
      {onView && <button className="agree__view" onClick={onView}>보기</button>}
    </div>
  );
}

function DocSheet({ name, onClose }: { name: string; onClose: () => void }) {
  const d = DOCS[name];
  return (
    <Sheet title={d.title} onClose={onClose}>
      <DocBody name={name} />
      <button className="btn btn--secondary" onClick={onClose}>닫기</button>
    </Sheet>
  );
}
function DocBody({ name }: { name: string }) {
  const d = DOCS[name];
  if (!d) return <p className="muted">문서를 찾지 못했어요.</p>;
  return (
    <div className="doc">
      <p className="small muted">시행일 {d.updated}</p>
      {d.body.map((b) => <section key={b.h}><h3 className="h3">{b.h}</h3>{b.p.map((t) => <p key={t}>{t}</p>)}</section>)}
    </div>
  );
}

/** 약관·공지 등 문서 화면 (로그인 전후 모두) */
export function DocPageView() {
  const { name = '' } = useParams();
  const nav = useNavigate();
  const { me } = useAuth();
  return (
    <Frame adult={me?.role !== 'student'} title={DOCS[name]?.title ?? '문서'} back={me ? '/settings' : '/login'}>
      <DocBody name={name} />
      <button className="btn btn--ghost" onClick={() => nav(-1)}>돌아가기</button>
    </Frame>
  );
}

/* ======================= 가입 완료 ======================= */
export function Welcome() {
  const nav = useNavigate();
  const { me } = useAuth();
  if (!me) return null;
  const next: Record<string, string[]> = {
    student: [`내 연결 코드 ${me.linkCode}를 보호자에게 알려 줘`, '보호자가 동의하면 학원에 들어갈 수 있어', '선생님 강의실에 들어가면 공부 시작!'],
    guardian: ['설정 → 자녀 관리에서 아이 코드로 연결해요(보호자 동의)', '학원에서 받은 6자리 입장 코드를 넣어요', '아이의 오늘 결과를 보고 도장을 찍어 주세요'],
    teacher: ['설정 → 소속에서 원장님께 받은 일련번호를 넣어요', '새 학원·학교라면 같은 곳에서 「등록 신청」', '승인되면 강의실을 열고 학생을 초대해요'],
    operator: [],
  };
  return (
    <Frame adult={me.role !== 'student'} title="가입 완료" actions={<button className="btn btn--primary" onClick={() => nav(homeFor(me), { replace: true })}>시작하기</button>}>
      <div className="celebrate" style={{ paddingTop: 12 }}>
        <Mascot mood="cheer" size={120} />
        <h1 className="h2">{me.name}{me.role === 'student' ? ', 반가워!' : '님, 환영해요'}</h1>
        <p className="small muted">아이디 <strong>{me.loginId}</strong> · {ROLE_LABEL[me.role]}</p>
      </div>
      {me.linkCode && <section className="card row between"><span className="small muted">내 연결 코드</span><span className="code-big">{me.linkCode}</span></section>}
      <section className="card stack">
        <strong>이제 이렇게 해요</strong>
        <ol className="setup">{next[me.role].map((t, i) => <li key={t}><span className="setup__n">{i + 1}</span><span className="small">{t}</span></li>)}</ol>
      </section>
    </Frame>
  );
}

/* ======================= 아이디·비밀번호 찾기 ======================= */
export function Find() {
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'pw' ? 'pw' : 'id';
  const [email, setEmail] = useState('');
  const [loginId, setLoginId] = useState('');
  const [result, setResult] = useState<ReactNode>(null);
  const { run, busy, error, setError } = useAction();
  const switchTab = (t: 'id' | 'pw') => { setParams({ tab: t }, { replace: true }); setResult(null); setError(null); };
  return (
    <Frame adult title={tab === 'id' ? '아이디 찾기' : '비밀번호 찾기'} back="/login">
      <div className="seg" role="tablist">
        <button role="tab" aria-selected={tab === 'id'} className={'seg__btn' + (tab === 'id' ? ' seg__btn--on' : '')} onClick={() => switchTab('id')}>아이디 찾기</button>
        <button role="tab" aria-selected={tab === 'pw'} className={'seg__btn' + (tab === 'pw' ? ' seg__btn--on' : '')} onClick={() => switchTab('pw')}>비밀번호 찾기</button>
      </div>
      {tab === 'pw' && <label className="field">아이디<input className="input" autoCapitalize="none" value={loginId} onChange={(e) => setLoginId(e.target.value)} /></label>}
      <label className="field">가입할 때 적은 이메일{tab === 'pw' && <span className="hint">학생은 비워 두세요</span>}<input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
      <LoadError error={error} />
      <button className="btn btn--primary" disabled={busy || (tab === 'id' ? !email : !loginId)} onClick={() => run(async () => {
        if (tab === 'id') { const ids = await api.findLoginId(email); setResult(<>가입한 아이디: {ids.map((x) => <strong key={x} className="num"> {x}</strong>)}</>); }
        else { const r = await api.requestPasswordReset(loginId, email); setResult(r === 'sent' ? '비밀번호 재설정 메일을 보냈어요. (시연: 실제 메일은 가지 않아요)' : '학생 계정이에요. 보호자에게 비밀번호 재설정을 부탁해 주세요.'); }
      })}>{tab === 'id' ? '아이디 찾기' : '재설정 메일 받기'}</button>
      {result && <div className="notice" role="status"><span>{result}</span></div>}
      <section className="card card--flat stack">
        <strong className="small"><Icon name="help" size={16} /> 학생 계정은 이메일이 없어요</strong>
        <p className="small muted">보호자 앱 → <strong>설정 → 자녀 관리 → 비밀번호 재설정</strong>에서 보호자가 새 비밀번호를 정해 줄 수 있어요.</p>
      </section>
    </Frame>
  );
}
