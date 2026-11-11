// 설정 — 모든 역할 공통 틀 + 역할별 항목
//   학생: 보호자 연결 · 학원·강의실 · 내 멘토      보호자: 자녀 관리 · 학원
//   학습지도자: 소속(일련번호 신청 / 학원·학교 등록) · 학원 관리(원장) · 강의실      운영자: 학원 등록 심사
//   공통: 프로필 · 비밀번호 · 알림 · 공지/FAQ/문의 · 약관 · 앱 정보 · 로그아웃 · 회원 탈퇴
import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon, type IconName } from '../../components/Icon';
import { LoadError, Sheet } from '../../components/Common';
import { useAction } from '../../lib/useAction';
import { homeFor, useAuth } from '../../state/auth';
import { ROLE_LABEL, type AcademyForm, type Me, type NotifySettings } from '../../types';
import { PW_RULE } from '../../api/org';

export const APP_VERSION = '0.5.0';

function Item({ icon, label, sub, to, onClick, badge }: { icon: IconName; label: string; sub?: string; to?: string; onClick?: () => void; badge?: ReactNode }) {
  const nav = useNavigate();
  return (
    <button className="set-item" onClick={() => (to ? nav(to) : onClick?.())}>
      <Icon name={icon} size={20} />
      <span className="set-item__label">{label}{sub && <span className="small muted">{sub}</span>}</span>
      {badge}
      <Icon name="chevron" size={16} />
    </button>
  );
}
const Group = ({ title, children }: { title: string; children: ReactNode }) => (
  <section className="set-group"><h2 className="set-group__title">{title}</h2><div className="set-group__box">{children}</div></section>
);

export function Settings() {
  const nav = useNavigate();
  const { me, logout } = useAuth();
  const [bye, setBye] = useState(false);
  const [ask, setAsk] = useState(false);
  if (!me) return null;
  const kid = me.role === 'student';
  const m = me.membership;
  return (
    <Frame adult={!kid} title="설정" back={homeFor(me)}>
      <button className="card profile-card" onClick={() => nav('/settings/profile')}>
        <span className="path-card__icon"><Icon name="user" size={26} /></span>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span className="row"><strong className="h3">{me.name}</strong><span className="pill pill--mint">{ROLE_LABEL[me.role]}{m?.isOwner ? ' · 원장' : ''}</span></span>
          <span className="small muted" style={{ display: 'block' }}>{me.loginId}{me.academy ? ` · ${me.academy.name}` : m ? ` · ${m.name} (${m.status})` : ''}</span>
        </span>
        <Icon name="chevron" size={16} />
      </button>

      {me.role === 'student' && (
        <Group title="연결·학원">
          <Item icon="link" label="보호자 연결" sub={me.linked.length ? me.linked.map((x) => x.name).join(', ') : me.pendingLinks.length ? '동의 기다리는 중' : '아직 없음'} to="/settings/family" badge={me.restricted ? <span className="pill pill--accent">필요</span> : undefined} />
          <Item icon="building" label="학원·강의실" sub={me.academy?.name ?? '아직 없음'} to="/settings/org" />
          <Item icon="mentor" label="내 멘토" sub="캐릭터·말투·옷장" to="/student/mentor" />
        </Group>
      )}
      {me.role === 'guardian' && (
        <Group title="자녀·학원">
          <Item icon="people" label="자녀 관리" sub={me.linked.length ? me.linked.map((x) => x.name).join(', ') : '연결된 아이 없음'} to="/settings/family" badge={me.pendingLinks.length ? <span className="pill pill--accent">요청 {me.pendingLinks.length}</span> : undefined} />
          <Item icon="building" label="학원" sub={me.academy?.name ?? '아직 없음'} to="/settings/org" />
        </Group>
      )}
      {me.role === 'teacher' && (
        <Group title="소속·수업">
          <Item icon="building" label="소속 학원·학교" sub={m ? `${m.name} · ${m.isOwner ? '원장' : m.status}` : me.application?.status === '심사 중' ? `${me.application.academyName} 등록 심사 중` : '소속 없음'} to="/settings/org" badge={!m ? <span className="pill pill--accent">필요</span> : undefined} />
          {m?.isOwner && <Item icon="key" label="학원 관리" sub="입장 코드 · 소속 승인 · 현황" to="/owner" />}
          <Item icon="people" label="강의실 관리" to="/teacher/classes" />
        </Group>
      )}
      {me.role === 'operator' && (
        <Group title="운영"><Item icon="shield" label="학원·학교 등록 심사" to="/operator" /></Group>
      )}

      <Group title="계정">
        <Item icon="user" label="프로필 수정" to="/settings/profile" />
        <Item icon="key" label="비밀번호 변경" to="/settings/password" />
        <Item icon="bell" label="알림 설정" to="/settings/notify" />
      </Group>
      <Group title="고객 지원">
        <Item icon="bell" label="공지사항" to="/docs/notice" />
        <Item icon="help" label="자주 묻는 질문" to="/docs/faq" />
        <Item icon="mail" label="문의하기" onClick={() => setAsk(true)} />
      </Group>
      <Group title="약관·정보">
        <Item icon="doc" label="이용약관" to="/docs/terms" />
        <Item icon="shield" label="개인정보 처리방침" to="/docs/privacy" />
        <div className="set-item set-item--static"><Icon name="info" size={20} /><span className="set-item__label">앱 버전</span><span className="small muted num">{APP_VERSION} (시연)</span></div>
      </Group>
      <div className="btn-row">
        <button className="btn btn--secondary" onClick={() => setBye(true)}><Icon name="logout" size={18} />로그아웃</button>
      </div>
      <button className="btn btn--ghost btn--small" style={{ alignSelf: 'center' }} onClick={() => nav('/settings/delete')}>회원 탈퇴</button>

      {bye && (
        <Sheet title="로그아웃할까요?" onClose={() => setBye(false)}>
          <p className="small muted">다시 들어오려면 아이디와 비밀번호로 로그인해요.</p>
          <div className="btn-row">
            <button className="btn btn--secondary" onClick={() => setBye(false)}>취소</button>
            <button className="btn btn--primary" onClick={async () => { await logout(); nav('/login', { replace: true }); }}>로그아웃</button>
          </div>
        </Sheet>
      )}
      {ask && (
        <Sheet title="문의하기" onClose={() => setAsk(false)}>
          <p className="small">궁금한 점이나 불편한 점을 보내 주세요. 영업일 기준 1~2일 안에 답해요.</p>
          <div className="card card--flat row between"><span className="small muted">이메일</span><strong>help@aimentor.example</strong></div>
          <p className="small muted">시연 버전이라 실제로 접수되지는 않아요. 주소는 팀에서 정해 바꿔 주세요.</p>
          <button className="btn btn--secondary" onClick={() => setAsk(false)}>닫기</button>
        </Sheet>
      )}
    </Frame>
  );
}

/* ---------------- 프로필 ---------------- */
export function SettingsProfile() {
  const { me, enter } = useAuth();
  const [name, setName] = useState(me?.name ?? '');
  const [email, setEmail] = useState(me?.email ?? '');
  const [saved, setSaved] = useState(false);
  const { run, busy, error } = useAction();
  if (!me) return null;
  const kid = me.role === 'student';
  return (
    <Frame adult={!kid} title="프로필 수정" back="/settings"
      actions={<button className="btn btn--primary" disabled={busy || !name.trim()} onClick={() => run(async () => { await enter(await api.updateProfile(kid ? { name } : { name, email })); setSaved(true); })}>{saved ? '저장했어요 ✓' : '저장'}</button>}>
      <label className="field">아이디<input className="input" value={me.loginId} disabled /></label>
      <label className="field">{kid ? '별명' : '이름'}<input className="input" maxLength={12} value={name} onChange={(e) => { setName(e.target.value); setSaved(false); }} /></label>
      {kid ? <label className="field">학년<input className="input" value={`${me.grade}학년`} disabled /></label>
        : <label className="field">이메일<input className="input" type="email" value={email} onChange={(e) => { setEmail(e.target.value); setSaved(false); }} /></label>}
      <LoadError error={error} />
    </Frame>
  );
}

/* ---------------- 비밀번호 ---------------- */
export function SettingsPassword() {
  const { me } = useAuth();
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [conf, setConf] = useState('');
  const [done, setDone] = useState(false);
  const { run, busy, error } = useAction();
  const ok = PW_RULE.test(next) && next === conf && cur;
  return (
    <Frame adult={me?.role !== 'student'} title="비밀번호 변경" back="/settings"
      actions={<button className="btn btn--primary" disabled={!ok || busy} onClick={() => run(async () => { await api.changePassword(cur, next); setDone(true); setCur(''); setNext(''); setConf(''); })}>변경</button>}>
      {done && <div className="notice" role="status"><span>비밀번호를 바꿨어요.</span><Icon name="check" size={18} /></div>}
      <label className="field">지금 비밀번호<input className="input" type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} /></label>
      <label className="field">새 비밀번호<input className="input" type="password" autoComplete="new-password" placeholder="영문+숫자 8~20자" value={next} onChange={(e) => setNext(e.target.value)} />
        {next && <span className={'hint ' + (PW_RULE.test(next) ? 'hint--ok' : '')}>{PW_RULE.test(next) ? '좋아요' : '영문과 숫자를 섞어 8~20자'}</span>}</label>
      <label className="field">새 비밀번호 확인<input className="input" type="password" autoComplete="new-password" value={conf} onChange={(e) => setConf(e.target.value)} />
        {conf && <span className={'hint ' + (next === conf ? 'hint--ok' : 'hint--bad')}>{next === conf ? '같아요' : '위와 달라요'}</span>}</label>
      <LoadError error={error} />
    </Frame>
  );
}

/* ---------------- 알림 설정 ---------------- */
export function SettingsNotify() {
  const { me, enter } = useAuth();
  const [s, setS] = useState<NotifySettings | null>(me?.settings ?? null);
  const { run, error } = useAction();
  if (!me || !s) return null;
  const save = (patch: Partial<NotifySettings>) => { const n = { ...s, ...patch }; setS(n); run(async () => enter(await api.saveSettings(n))); };
  const Toggle = ({ label, sub, on, onChange, locked }: { label: string; sub?: string; on: boolean; onChange?: (v: boolean) => void; locked?: boolean }) => (
    <label className="set-item set-item--static">
      <span className="set-item__label">{label}{sub && <span className="small muted">{sub}</span>}</span>
      <input type="checkbox" role="switch" className="switch" checked={on} disabled={locked} onChange={(e) => onChange?.(e.target.checked)} />
    </label>
  );
  return (
    <Frame adult={me.role !== 'student'} title="알림 설정" back="/settings">
      <Group title="알림">
        {me.role === 'student' && (
          <div className="set-item set-item--static">
            <span className="set-item__label">매일 공부 알림<span className="small muted">이 시간에 멘토가 불러 줘</span></span>
            <select className="input" style={{ width: 110, minHeight: 40 }} value={s.studyReminder ?? ''} onChange={(e) => save({ studyReminder: e.target.value || null })}>
              <option value="">끄기</option>{['15:00', '16:00', '17:00', '18:00', '19:00', '20:00'].map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
        )}
        {me.role === 'guardian' && <Toggle label="아이 학습 완료" sub="오늘 공부를 끝내면 알려 드려요" on={s.learnDone} onChange={(v) => save({ learnDone: v })} />}
        <Toggle label="활동 알림" sub={me.role === 'teacher' ? '소속 신청·참여 요청·교환 요청' : '연결·초대·승인·씨앗'} on={s.activity} onChange={(v) => save({ activity: v })} />
        {me.role === 'guardian' && <Toggle label="안전 알림" sub="위험 신호가 있으면 항상 알려요(끌 수 없음)" on locked />}
        <Toggle label="이벤트·소식 [선택]" on={s.marketing} onChange={(v) => save({ marketing: v })} />
      </Group>
      <p className="small muted">시연 버전은 앱 안 알림함에만 쌓여요. 휴대폰 푸시는 앱 출시 때 연결해요.</p>
      <LoadError error={error} />
    </Frame>
  );
}

/* ---------------- 회원 탈퇴 ---------------- */
export function SettingsDelete() {
  const nav = useNavigate();
  const { me, logout } = useAuth();
  const [pw, setPw] = useState('');
  const [ok, setOk] = useState(false);
  const { run, busy, error } = useAction();
  return (
    <Frame adult={me?.role !== 'student'} title="회원 탈퇴" back="/settings"
      actions={<button className="btn btn--secondary" disabled={!ok || !pw || busy} onClick={() => run(async () => { await api.deleteAccount(pw); await logout(); nav('/login', { replace: true }); })}>탈퇴하기</button>}>
      <div className="card card--warn stack">
        <strong>탈퇴하면 되돌릴 수 없어요</strong>
        <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
          <li>계정과 연결(보호자·자녀·강의실)이 사라져요</li>
          <li>모은 씨앗과 꾸미기도 사라져요</li>
          <li>원장은 먼저 학원 관리를 넘겨야 해요(운영자 문의)</li>
        </ul>
      </div>
      <label className="check-inline"><input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} /> 위 내용을 확인했어요</label>
      <label className="field">비밀번호 확인<input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} /></label>
      <LoadError error={error} />
    </Frame>
  );
}

/* ---------------- 연결: 학생 = 보호자 연결 / 보호자 = 자녀 관리 ---------------- */
export function SettingsFamily() {
  const { me, enter } = useAuth();
  const [code, setCode] = useState('');
  const [consentFor, setConsentFor] = useState<{ kind: 'code'; code: string } | { kind: 'confirm'; id: string; name: string } | null>(null);
  const [resetFor, setResetFor] = useState<{ id: string; name: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const { run, busy, error } = useAction();
  if (!me) return null;
  const kid = me.role === 'student';
  const apply = async (p: Promise<Me>, msg: string) => { await enter(await p); setDone(msg); };
  return (
    <Frame adult={!kid} title={kid ? '보호자 연결' : '자녀 관리'} back="/settings">
      {done && <div className="notice" role="status"><span>{done}</span><Icon name="check" size={18} /></div>}
      <section className="card stack">
        <div className="small muted">내 연결 코드 {kid ? '(보호자에게 알려 줘)' : '(아이 앱에 넣어도 돼요)'}</div>
        <div className="row between">
          <span className="code-big">{me.linkCode}</span>
          <button className="btn btn--secondary btn--small" onClick={async () => { try { await navigator.clipboard.writeText(me.linkCode ?? ''); setCopied(true); } catch { /* 복사 막힘 */ } }}><Icon name="copy" size={16} />{copied ? '복사됨' : '복사'}</button>
        </div>
      </section>

      <h2 className="h3">{kid ? '연결된 보호자' : '연결된 아이'}</h2>
      {me.linked.length === 0 && me.pendingLinks.length === 0 && <div className="notice notice--plain"><span>아직 연결된 {kid ? '보호자가' : '아이가'} 없어요</span></div>}
      {me.linked.map((p) => (
        <div key={p.id} className="card card--flat row between">
          <span><strong>{p.name}</strong> <span className="pill pill--mint"><Icon name="link" size={12} />연결됨</span></span>
          {!kid && <button className="btn btn--secondary btn--small" onClick={() => setResetFor({ id: p.id, name: p.name })}><Icon name="key" size={14} />비밀번호 재설정</button>}
        </div>
      ))}
      {me.pendingLinks.map((p) => (
        <div key={p.id} className="card card--warn row between">
          <span><strong>{p.name}</strong><span className="small muted" style={{ display: 'block' }}>{kid ? '보호자의 동의를 기다리는 중' : '연결을 요청했어요'}</span></span>
          {!kid && <button className="btn btn--primary btn--small" onClick={() => setConsentFor({ kind: 'confirm', id: p.id, name: p.name })}>동의하고 연결</button>}
        </div>
      ))}

      <h2 className="h3">{kid ? '보호자 코드로 연결' : '아이 추가'}</h2>
      <div className="row">
        <input className="input code-input" aria-label="상대 연결 코드" placeholder={kid ? '보호자 코드 6자리' : '아이 코드 6자리'} maxLength={6} value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} />
        <button className="btn btn--primary btn--small" style={{ minHeight: 46 }} disabled={code.length < 6 || busy}
          onClick={() => (kid ? run(async () => { await apply(api.linkWith(code), '보호자에게 연결을 요청했어. 동의하면 연결돼!'); setCode(''); }) : setConsentFor({ kind: 'code', code }))}>연결</button>
      </div>
      <LoadError error={error} />

      {consentFor && (
        <ConsentSheet name={consentFor.kind === 'confirm' ? consentFor.name : null} busy={busy} onClose={() => setConsentFor(null)}
          onAgree={() => run(async () => {
            await apply(consentFor.kind === 'confirm' ? api.confirmLink(consentFor.id, true) : api.linkWith(consentFor.code, true), '아이와 연결했어요.');
            setConsentFor(null); setCode('');
          })} />
      )}
      {resetFor && <ResetChildSheet child={resetFor} onClose={() => setResetFor(null)} onDone={() => { setResetFor(null); setDone(`${resetFor.name}의 비밀번호를 바꿨어요. 아이에게 알려 주세요.`); }} />}
    </Frame>
  );
}

function ResetChildSheet({ child, onClose, onDone }: { child: { id: string; name: string }; onClose: () => void; onDone: () => void }) {
  const [pw, setPw] = useState('');
  const { run, busy, error } = useAction();
  return (
    <Sheet title={`${child.name} 비밀번호 재설정`} onClose={onClose}>
      <p className="small muted">아이 계정은 이메일이 없어서 보호자가 새 비밀번호를 정해 줘요.</p>
      <input className="input" type="text" placeholder="영문+숫자 8~20자" value={pw} onChange={(e) => setPw(e.target.value)} />
      <LoadError error={error} />
      <button className="btn btn--primary" disabled={!PW_RULE.test(pw) || busy} onClick={() => run(async () => { await api.resetChildPassword(child.id, pw); onDone(); })}>바꾸기</button>
    </Sheet>
  );
}

/** 만 14세 미만 아동 개인정보 — 법정대리인(보호자) 동의 */
function ConsentSheet({ name, onAgree, onClose, busy }: { name: string | null; onAgree: () => void; onClose: () => void; busy: boolean }) {
  const [ok, setOk] = useState(false);
  return (
    <Sheet title="보호자 동의" onClose={onClose}>
      <p className="small">{name ? `${name} 학생과 연결해요. ` : ''}만 14세 미만 아이의 개인정보는 보호자 동의가 있어야 처리할 수 있어요.</p>
      <dl className="kv">
        <dt>받는 정보</dt><dd>아이 아이디·별명·학년, 학습 기록(푼 문제·시간·힌트)</dd>
        <dt>수다</dt><dd>원문은 보관하지 않고, 위험 신호의 분류만 보호자에게 알려요</dd>
        <dt>쓰는 곳</dt><dd>학습 도움, 보호자·학습지도자에게 결과 공유</dd>
        <dt>보관</dt><dd>탈퇴하면 지워요</dd>
      </dl>
      <label className="check-row card card--flat" style={{ padding: '0 12px' }}>
        <span className="small"><strong>[필수]</strong> 법정대리인으로서 위 내용에 동의합니다</span>
        <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} />
      </label>
      <button className="btn btn--primary" disabled={!ok || busy} onClick={onAgree}>동의하고 연결</button>
    </Sheet>
  );
}

/* ---------------- 소속·학원 ---------------- */
export function SettingsOrg() {
  const { me } = useAuth();
  if (!me) return null;
  return me.role === 'teacher' ? <TeacherOrg /> : <FamilyOrg />;
}

/** 학생·보호자: 학원 입장(6자리, 10분) */
function FamilyOrg() {
  const nav = useNavigate();
  const { me, enter } = useAuth();
  const [entry, setEntry] = useState('');
  const [done, setDone] = useState(false);
  const { run, busy, error } = useAction();
  if (!me) return null;
  const kid = me.role === 'student';
  return (
    <Frame adult={!kid} title={kid ? '학원·강의실' : '학원'} back="/settings">
      {done && <div className="notice" role="status"><span>학원에 등록했어요. 연결된 가족도 함께 등록됐어요.</span><Icon name="check" size={18} /></div>}
      {me.academy ? (
        <section className="card row between"><span><span className="small muted" style={{ display: 'block' }}>내 학원</span><strong className="h3">{me.academy.name}</strong></span><span className="pill pill--mint">등록됨</span></section>
      ) : (
        <section className="card stack">
          {me.restricted && <div className="notice"><span>보호자와 연결된 뒤에 학원에 들어갈 수 있어.</span></div>}
          <strong>학원 들어가기</strong>
          <div className="small muted">학원에서 받은 6자리 코드 (10분 동안만 쓸 수 있어요)</div>
          <div className="row">
            <input className="input code-input" inputMode="numeric" aria-label="학원 입장 코드" placeholder="000000" maxLength={6} value={entry} disabled={me.restricted} onChange={(e) => setEntry(e.target.value.replace(/\D/g, ''))} />
            <button className="btn btn--primary btn--small" style={{ minHeight: 46 }} disabled={entry.length !== 6 || busy || me.restricted}
              onClick={() => run(async () => { await enter(await api.joinAcademy(entry)); setDone(true); setEntry(''); })}>들어가기</button>
          </div>
          {me.linked.length > 0 && <p className="small muted">연결된 {kid ? '보호자' : '아이'}도 함께 등록돼요.</p>}
        </section>
      )}
      {kid && me.academy && <button className="btn btn--secondary" onClick={() => nav('/student/classes')}><Icon name="people" size={18} />강의실 보기·참여 요청</button>}
      <LoadError error={error} />
    </Frame>
  );
}

/** 학습지도자: 소속 신청(일련번호 → 원장 승인) / 학원·학교 등록 신청(운영자 심사 → 원장) */
function TeacherOrg() {
  const nav = useNavigate();
  const { me, enter, refresh } = useAuth();
  const [serial, setSerial] = useState('');
  const [apply, setApply] = useState(false);
  const [leave, setLeave] = useState(false);
  const { run, busy, error } = useAction();
  if (!me) return null;
  const m = me.membership;
  const app = me.application;
  return (
    <Frame adult title="소속 학원·학교" back="/settings" right={<button className="icon-btn" aria-label="새로고침" onClick={() => refresh()}><Icon name="refresh" size={20} /></button>}>
      {m ? (
        <section className={'card stack' + (m.status === '승인 대기' ? ' card--warn' : '')}>
          <div className="row between">
            <span><span className="small muted" style={{ display: 'block' }}>{m.orgType}</span><strong className="h3">{m.name}</strong></span>
            <span className={'pill ' + (m.status === '승인됨' ? 'pill--mint' : 'pill--accent')}>{m.isOwner ? '원장' : m.status}</span>
          </div>
          {m.status === '승인 대기' && <p className="small muted">원장님이 승인하면 강의실을 열 수 있어요.</p>}
          {m.isOwner ? <button className="btn btn--primary btn--small" style={{ alignSelf: 'flex-start' }} onClick={() => nav('/owner')}><Icon name="key" size={16} />학원 관리</button>
            : <button className="btn btn--ghost btn--small" style={{ alignSelf: 'flex-start', padding: 0 }} onClick={() => setLeave(true)}>{m.status === '승인 대기' ? '신청 취소' : '소속 나가기'}</button>}
        </section>
      ) : (
        <>
          <section className="card stack">
            <strong>일련번호로 소속 신청</strong>
            <p className="small muted">원장님께 받은 학원·학교 일련번호를 넣으면 원장님이 승인해요.</p>
            <div className="row">
              <input className="input code-input" placeholder="XXXX-XXXX" maxLength={9} value={serial} onChange={(e) => setSerial(e.target.value.toUpperCase())} />
              <button className="btn btn--primary btn--small" style={{ minHeight: 46 }} disabled={serial.replace(/\W/g, '').length < 8 || busy}
                onClick={() => run(async () => { await enter(await api.requestMembership(serial)); setSerial(''); })}>신청</button>
            </div>
            <span className="hint">체험: WW7K-3P9Q (우왕수학학원)</span>
          </section>
          <section className="card stack">
            <strong>새 학원·학교 등록</strong>
            <p className="small muted">운영자가 확인한 뒤 승인되면 일련번호가 나오고, 신청한 분이 <strong>원장(관리자)</strong>이 돼요.</p>
            {app && (
              <div className={'notice ' + (app.status === '반려' ? 'notice--danger' : app.status === '승인' ? '' : 'notice--plain')}>
                <span><strong>{app.academyName}</strong> · {app.status}{app.rejectReason ? ` — ${app.rejectReason}` : ''}</span>
              </div>
            )}
            <button className="btn btn--secondary btn--small" style={{ alignSelf: 'flex-start' }} disabled={app?.status === '심사 중'} onClick={() => setApply(true)}>
              {app?.status === '심사 중' ? '심사 중이에요' : '등록 신청서 쓰기'}
            </button>
          </section>
        </>
      )}
      <LoadError error={error} />
      {apply && <ApplySheet onClose={() => setApply(false)} />}
      {leave && (
        <Sheet title={m?.status === '승인 대기' ? '소속 신청을 취소할까요?' : '소속을 나갈까요?'} onClose={() => setLeave(false)}>
          <p className="small muted">내 강의실이 남아 있으면 먼저 정리해야 해요.</p>
          <div className="btn-row">
            <button className="btn btn--secondary" onClick={() => setLeave(false)}>아니요</button>
            <button className="btn btn--primary" disabled={busy} onClick={() => run(async () => { await enter(await api.leaveMembership()); setLeave(false); })}>네</button>
          </div>
        </Sheet>
      )}
    </Frame>
  );
}

function ApplySheet({ onClose }: { onClose: () => void }) {
  const { enter } = useAuth();
  const [f, setF] = useState<AcademyForm>({ orgType: '학원', academyName: '', bizNo: '', ceo: '', phone: '', address: '' });
  const set = (k: keyof AcademyForm) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const { run, busy, error } = useAction();
  const school = f.orgType === '학교';
  return (
    <Sheet title="학원·학교 등록 신청" onClose={onClose}>
      <ol className="flow-steps" aria-label="진행 순서"><li className="on">신청</li><li>운영자 심사</li><li>일련번호 발급</li></ol>
      <div className="seg" role="radiogroup" aria-label="종류">
        {(['학원', '학교'] as const).map((t) => <button key={t} role="radio" aria-checked={f.orgType === t} className={'seg__btn' + (f.orgType === t ? ' seg__btn--on' : '')} onClick={() => setF({ ...f, orgType: t })}>{t}</button>)}
      </div>
      <label className="field">{school ? '학교 이름' : '학원 이름'}<input className="input" value={f.academyName} onChange={set('academyName')} placeholder={school ? '예: 우왕초등학교' : '예: 우왕수학학원'} /></label>
      <label className="field">{school ? '학교 코드(선택)' : '사업자등록번호'}<input className="input" inputMode="numeric" value={f.bizNo} onChange={set('bizNo')} placeholder={school ? '나이스 학교 코드' : '123-45-67890'} /></label>
      <div className="btn-row">
        <label className="field" style={{ flex: 1 }}>{school ? '담당자' : '대표자'}<input className="input" value={f.ceo} onChange={set('ceo')} /></label>
        <label className="field" style={{ flex: 1 }}>연락처<input className="input" inputMode="tel" value={f.phone} onChange={set('phone')} /></label>
      </div>
      <label className="field">주소 (선택)<input className="input" value={f.address} onChange={set('address')} /></label>
      <p className="small muted">시연에서는 진위 확인 없이 운영자 화면의 「승인」으로 심사를 대신해요.</p>
      <LoadError error={error} />
      <button className="btn btn--primary" disabled={busy} onClick={() => run(async () => { await enter(await api.applyAcademy(f)); onClose(); })}>신청하기</button>
    </Sheet>
  );
}
