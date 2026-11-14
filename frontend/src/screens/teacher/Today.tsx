// 학습지도자 ② 오늘 할 것 — 학생마다: 오늘 할 단원 지정 → 수업 메모(1~2분) → 초안 → 고쳐서 승인 → 보호자 카드에 공개
// 초안의 "사실 칸"(범위·문제·힌트)은 기록에서 자동으로 채워지고, 사람이 고치는 것은 코멘트뿐이다.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { api, API_MODE } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../state/auth';
import { useTeacherWide } from '../../lib/wide';
import type { Draft, StudentRow, TaskStatus, TeacherMemo, TeacherToday as TodayView } from '../../types';

const STATUS_PILL: Record<TaskStatus, string> = { '지정 전': 'pill', '지정됨': 'pill pill--accent', '진행 중': 'pill pill--mint', '완료': 'pill pill--solid' };

export function TeacherToday() {
  const { data, setData, error, loading, reload } = useAsync(() => api.getTeacherToday());
  const [open, setOpen] = useState<StudentRow | null>(null);
  const nav = useNavigate();
  const { me } = useAuth();
  const m = me?.membership;
  const wide = useTeacherWide(); // 넓은 화면: 목록 옆에 상세를 같이 보인다(시트 대신)
  const close = () => { setOpen(null); reload(); };
  const rows = data?.students.map((s) => (
    <button key={s.id} className={'card student-row' + (wide && open?.id === s.id ? ' card--selected' : '')} onClick={() => setOpen(s)}>
      <span style={{ minWidth: 0 }}>
        <strong>{s.name}</strong>
        <span className="small muted" style={{ display: 'block' }}>{s.task ?? '오늘 할 것 없음'}{s.draftStatus ? ` · 코멘트 ${s.draftStatus}` : ''}</span>
      </span>
      <span className="row"><span className={STATUS_PILL[s.status]}>{s.status}</span><Icon name="chevron" size={18} /></span>
    </button>
  ));
  return (
    // TK-74 #6: 11-15에는 🔴 알림이 보호자에게만 간다(서버 학습지도자 알림은 빈 목록) → 「긴급 알림」 입구를 숨긴다. 화면(/teacher/alerts)은 후속용으로 남김
    <Frame adult title="오늘 할 것" exit tabs="teacher">
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {me && (!m || m.status !== '승인됨') && (
        <section className={'card stack' + (m ? ' card--warn' : '')}>
          <strong>{m ? `${m.name} 소속 승인 대기 중` : me.application?.status === '심사 중' ? `${me.application.academyName} 등록 심사 중` : '아직 소속 학원·학교가 없어요'}</strong>
          <p className="small muted">{m ? '원장님이 승인하면 강의실을 열고 학생을 초대할 수 있어요.' : '설정 → 소속에서 일련번호로 소속을 신청하거나, 새 학원·학교를 등록해 주세요.'}</p>
          <button className="btn btn--primary btn--small" style={{ alignSelf: 'flex-start' }} onClick={() => nav('/settings/org')}><Icon name="building" size={16} />소속 설정</button>
        </section>
      )}
      {data && m?.status === '승인됨' && (
        <>
          <div className="row between small"><span>{data.dateLabel}</span><span className="muted">{data.className} · 학생 {data.students.length}명</span></div>
          {data.students.length === 0 && <button className="card notice" onClick={() => nav('/teacher/classes')}><span>강의실을 열고 학생을 초대해 주세요</span><Icon name="chevron" size={18} /></button>}
          {data.units.length === 0 && <div className="notice">범위 탭에서 이번 주 단원을 먼저 골라 주세요.</div>}
          {wide && data.students.length > 0 ? (
            <div className="teacher-split">
              <div className="teacher-split__list">{rows}</div>
              {open
                ? <StudentSheet key={open.id} inline student={open} view={data} onChange={setData} onClose={close} />
                : <section className="card card--flat teacher-split__panel"><p className="small muted">왼쪽에서 학생을 누르면 오늘 할 것을 정하고 보호자 코멘트를 쓸 수 있어요.</p></section>}
            </div>
          ) : (
            <>
              <div className="card-grid">{rows}</div>
              <p className="small muted">학생을 누르면 오늘 할 것을 정하고 보호자 코멘트를 쓸 수 있어요.</p>
            </>
          )}
        </>
      )}
      {!wide && open && data && <StudentSheet student={open} view={data} onChange={setData} onClose={close} />}
    </Frame>
  );
}

function StudentSheet({ student, view, onChange, onClose, inline }: { student: StudentRow; view: TodayView; onChange: (v: TodayView) => void; onClose: () => void; inline?: boolean }) {
  const [task, setTask] = useState(student.task ?? '');
  const [memo, setMemo] = useState<TeacherMemo>({ covered: '', stuck: '', homework: '', note: '' });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState<false | 'load' | 'draft' | 'save'>('load');
  const [error, setError] = useState<string | null>(null);
  const started = student.status === '진행 중' || student.status === '완료';

  useEffect(() => {
    api.getMemo(student.id)
      .then((r) => { setMemo(r.memo); setDraft(r.draft); setComment(r.draft?.comment ?? ''); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false));
  }, [student.id]);

  const run = async (kind: 'draft' | 'save', fn: () => Promise<void>) => {
    setBusy(kind); setError(null);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const assign = (unit: string) => run('save', async () => { setTask(unit); onChange(await api.assignTask(student.id, unit || null)); });
  // 초안이 새로 생기면 그 카드(코멘트·승인)로 스크롤 — 1280×800·태블릿 시트에서 화면 밖에 생겨 변화가 없어 보이던 것(D8)
  const draftCard = useRef<HTMLElement>(null);
  const [drafted, setDrafted] = useState(0);
  useEffect(() => { if (drafted) draftCard.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, [drafted]);
  const makeDraft = () => run('draft', async () => {
    await api.saveMemo(student.id, memo);
    const d = await api.createDraft(student.id);
    setDraft(d); setComment(d.comment); setDrafted((n) => n + 1);
  });
  const saveComment = () => run('save', async () => { setDraft(await api.updateDraft(student.id, comment.trim())); });
  const approve = () => run('save', async () => {
    if (draft && comment.trim() !== draft.comment) await api.updateDraft(student.id, comment.trim());
    setDraft(await api.approveDraft(student.id));
  });
  const field = (key: keyof TeacherMemo, label: string) => (
    <label className="field">{label}
      <input id={`memo-${key}`} className="input" value={memo[key]} onChange={(e) => setMemo({ ...memo, [key]: e.target.value })} />
    </label>
  );
  const edited = !!draft && comment.trim() !== draft.comment;

  const title = `${student.name} · 오늘`;
  const body: ReactNode = (
    <>
      {busy === 'load' ? <Thinking label="불러오는 중" /> : (
        <>
          <label className="field">오늘 할 것
            <select id="task-unit" className="input" value={task} disabled={started || !!busy} onChange={(e) => assign(e.target.value)}>
              <option value="">없음(쉬는 날)</option>
              {view.units.map((u) => <option key={u} value={u}>{u} · 약 20분</option>)}
            </select>
          </label>
          {started && <p className="small muted">이미 시작한 날은 바꿀 수 없어요.</p>}

          <h3 className="h3">수업 메모 <span className="small muted">(1~2분)</span></h3>
          {field('covered', '오늘 다룬 것')}
          {field('stuck', '막힌 것')}
          {field('homework', '숙제')}
          {field('note', '한 줄 메모')}
          {/* 서버(http)는 초안을 하루 한 번만 만든다(createDraft는 읽기만) → 다시 만들기 대신 이유를 보인다. 고칠 땐 아래 코멘트를 직접 고친다 */}
          {draft && API_MODE === 'http'
            ? <button className="btn btn--secondary" disabled>초안은 하루 한 번만 만들어요</button>
            : <button className="btn btn--secondary" disabled={!!busy} onClick={makeDraft}>{draft ? '초안 다시 만들기' : '보호자 코멘트 초안 만들기'}</button>}
          {busy === 'draft' && <Thinking label="초안 만드는 중" />}

          {draft && (
            <section ref={draftCard} className="card card--flat stack">
              <div className="row between"><span className="row" style={{ gap: 6 }}><span className="pill pill--mint">초안</span>{draft.source === 'template' && <span className="pill" title="AI 초안을 만들지 못해 기본 문장으로 채웠어요">기본 문장</span>}</span><span className={draft.status === '승인됨' ? 'pill pill--solid' : 'pill pill--accent'}>{draft.status}</span></div>
              <dl className="kv">
                <dt>학습</dt><dd>{draft.scope}</dd>
                <dt>문제</dt><dd>{draft.amount}</dd>
                <dt>진행</dt><dd>{draft.mode}</dd>
              </dl>
              {/* B33: 폴백을 숨기지 않는다 — 기본 문장이면 한 줄로 알린다 */}
              {draft.source === 'template' && <p className="small muted">AI 초안을 만들지 못해 기본 문장으로 채웠어요. 아이에 맞게 고쳐서 승인해 주세요.</p>}
              <label className="field">보호자에게 보일 코멘트
                <textarea id="draft-comment" className="input" value={comment} onChange={(e) => setComment(e.target.value)} />
              </label>
              <div className="btn-row">
                <button className="btn btn--secondary" disabled={!edited || !!busy} onClick={saveComment}>수정 저장</button>
                <button className="btn btn--primary" disabled={!!busy || !comment.trim() || (draft.status === '승인됨' && !edited)} onClick={approve}>{draft.status === '승인됨' && !edited ? '승인됨' : '승인'}</button>
              </div>
              <p className="small muted">승인한 코멘트만 보호자 화면에 보여요. 수다 내용은 학습지도자에게도 오지 않아요.</p>
            </section>
          )}
          <LoadError error={error} />
        </>
      )}
      <button className="btn btn--ghost" onClick={onClose}>닫기</button>
    </>
  );
  // 넓은 화면에서는 시트 대신 목록 오른쪽 칸에 같은 내용을 그린다
  return inline
    ? <section className="card card--flat teacher-split__panel" aria-label={title}><h2 className="h3">{title}</h2>{body}</section>
    : <Sheet title={title} onClose={onClose}>{body}</Sheet>;
}
