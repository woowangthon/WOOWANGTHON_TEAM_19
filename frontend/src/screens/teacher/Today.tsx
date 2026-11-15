// 학습지도자 ② 오늘 할 것 — 학생마다: 오늘 할 단원 지정 → 수업 메모(1~2분) → 초안 → 고쳐서 승인 → 보호자 카드에 공개
// 초안의 "사실 칸"(범위·문제·힌트)은 기록에서 자동으로 채워지고, 사람이 고치는 것은 코멘트뿐이다.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { api, API_MODE } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useQuietPoll } from '../../lib/quietPoll';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../state/auth';
import { useTeacherWide } from '../../lib/wide';
import { memoLocked, withRollback } from '../../lib/teacherUi';
import { josa } from '../../lib/josa';
import type { Draft, StudentRow, TaskStatus, TeacherMemo, TeacherToday as TodayView } from '../../types';

const STATUS_PILL: Record<TaskStatus, string> = { '지정 전': 'pill', '지정됨': 'pill pill--accent', '진행 중': 'pill pill--mint', '완료': 'pill pill--solid' };
/** 화면에 보이는 상태 말(서버 값 「지정 전·지정됨」은 그대로 두고 보이는 낱말만 — 말투 표 규칙 ⑥, 성호 11-15 07:0x) */
const STATUS_LABEL: Record<TaskStatus, string> = { '지정 전': '정하기 전', '지정됨': '정했어요', '진행 중': '진행 중', '완료': '완료' };

export function TeacherToday() {
  const { data, setData, error, loading, reload, quiet } = useAsync(() => api.getTeacherToday());
  useQuietPoll([quiet]); // 4차: 학생 상태(진행 중·완료)가 새로고침 없이. 시트는 open 객체를 그대로 써서 입력이 날아가지 않음(bb ③)
  const [open, setOpen] = useState<StudentRow | null>(null);
  const [multi, setMulti] = useState(false);
  const nav = useNavigate();
  const { me } = useAuth();
  const m = me?.membership;
  const wide = useTeacherWide(); // 넓은 화면: 목록 옆에 상세를 같이 보인다(시트 대신)
  const close = () => { setOpen(null); reload(); };
  const rows = data?.students.map((s) => (
    <button key={s.id} className={'card student-row' + (wide && open?.id === s.id ? ' card--selected' : '')} onClick={() => setOpen(s)}>
      <span style={{ minWidth: 0 }}>
        <strong>{s.name}</strong>
        <span className="small muted" style={{ display: 'block' }}>{s.task ?? '아직 단원이 없어요'}{s.draftStatus ? ` · 코멘트 ${s.draftStatus}` : ''}</span>
      </span>
      <span className="row"><span className={STATUS_PILL[s.status]}>{STATUS_LABEL[s.status]}</span><Icon name="chevron" size={18} /></span>
    </button>
  ));
  return (
    // TK-74 #6: 11-15에는 🔴 알림이 보호자에게만 간다(서버 학습지도자 알림은 빈 목록) → 「긴급 알림」 입구를 숨긴다. 화면(/teacher/alerts)은 후속용으로 남김
    <Frame adult title="할 일" exit tabs="teacher">
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
          {data.units.length > 0 && data.students.length > 1 && <button className="btn btn--secondary btn--small" style={{ alignSelf: 'flex-start' }} onClick={() => setMulti(true)}>여러 명에게 정하기</button>}
          {wide && data.students.length > 0 ? (
            <div className="teacher-split">
              <div className="teacher-split__list">{rows}</div>
              {open
                ? <StudentSheet key={open.id} inline student={open} view={data} onChange={setData} onClose={close} />
                : <section className="card card--flat teacher-split__panel"><p className="small muted">학생을 눌러 오늘 공부를 정하고 코멘트를 써 보세요.</p></section>}
            </div>
          ) : (
            <>
              <div className="card-grid">{rows}</div>
              <p className="small muted">학생을 눌러 오늘 공부를 정하고 코멘트를 써 보세요.</p>
            </>
          )}
        </>
      )}
      {!wide && open && data && <StudentSheet student={open} view={data} onChange={setData} onClose={close} />}
      {multi && data && <MultiAssign view={data} onChange={setData} onClose={() => { setMulti(false); reload(); }} />}
    </Frame>
  );
}

/** 수업 메모 네 칸. locked면(http 모드에서 초안을 만든 뒤) 읽기만 — 고쳐도 저장할 길이 없어 말없이 사라진다 */
export function MemoFields({ memo, onMemo, locked }: { memo: TeacherMemo; onMemo: (m: TeacherMemo) => void; locked: boolean }) {
  const field = (key: keyof TeacherMemo, label: string) => (
    <label className="field">{label}
      <input id={`memo-${key}`} className="input" value={memo[key]} readOnly={locked} onChange={(e) => onMemo({ ...memo, [key]: e.target.value })} />
    </label>
  );
  return (
    <>
      {field('covered', '오늘 다룬 것')}
      {field('stuck', '막힌 것')}
      {field('homework', '숙제')}
      {field('note', '한 줄 메모')}
      {locked && <p className="small muted">초안을 만든 뒤에는 메모를 고칠 수 없어요</p>}
    </>
  );
}

/** 보호자에게 보일 코멘트 + 수정 저장·승인. 승인한 코멘트는 서버가 다시 받지 않으므로(409) 읽기만 */
export function CommentBox({ draft, comment, busy, onComment, onSave, onApprove }: { draft: Draft; comment: string; busy: boolean; onComment: (v: string) => void; onSave: () => void; onApprove: () => void }) {
  const locked = draft.status === '승인됨';
  const edited = comment.trim() !== draft.comment;
  return (
    <>
      <label className="field">보호자에게 보일 코멘트
        <textarea id="draft-comment" className="input" value={comment} readOnly={locked} onChange={(e) => onComment(e.target.value)} />
      </label>
      {locked && <p className="small muted">승인한 코멘트는 고칠 수 없어요</p>}
      <div className="btn-row">
        <button className="btn btn--secondary" disabled={locked || !edited || busy} onClick={onSave}>수정 저장</button>
        <button className="btn btn--primary" disabled={locked || busy || !comment.trim()} onClick={onApprove}>{locked ? '승인됨' : '승인'}</button>
      </div>
    </>
  );
}

function StudentSheet({ student, view, onChange, onClose, inline }: { student: StudentRow; view: TodayView; onChange: (v: TodayView) => void; onClose: () => void; inline?: boolean }) {
  const [task, setTask] = useState(student.task ?? '');
  // 11-15 성호 「선생님은 단원만」(명세 4.13-7 D3-2): 문제는 서버가 그 단원에서 아이가 고른 난이도로 고른다 → 첫 문제 고르기 없음
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
  // 고른 값을 먼저 보이고, 저장이 실패하면 이전 값으로 되돌린다(저장 실패를 저장된 것으로 착각하지 않게)
  const assign = (unit: string) => run('save', async () => {
    const before = task;
    const r = await withRollback(() => setTask(unit), () => setTask(before), () => api.assignTask(student.id, unit || null));
    onChange(r);
  });
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

  const title = `${student.name} · 오늘`;
  const body: ReactNode = (
    <>
      {busy === 'load' ? <Thinking label="불러오는 중" /> : (
        <>
          <label className="field">오늘 공부할 단원
            <select id="task-unit" className="input" value={task} disabled={started || !!busy} onChange={(e) => assign(e.target.value)}>
              <option value="">정하지 않기</option>
              {view.units.map((u) => <option key={u} value={u}>{u} · 약 20분</option>)}
            </select>
          </label>
          {task && !started && <p className="small">{josa(student.name, '이', '가')} 고른 난이도로 이 단원 문제가 나와요</p>}
          {started && <p className="small muted">오늘 공부를 시작했어요. 내일 문제부터 바꿀 수 있어요.</p>}

          <h3 className="h3">수업 메모</h3>
          <MemoFields memo={memo} onMemo={setMemo} locked={memoLocked(!!draft, API_MODE)} />
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
              <CommentBox draft={draft} comment={comment} busy={!!busy} onComment={setComment} onSave={saveComment} onApprove={approve} />
              <p className="small muted">승인해야 보호자에게 보여요. 수다 내용은 선생님도 볼 수 없어요.</p>
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

/** 여러 명에게 한 번에(TK-101 「특정 몇 명 또는 전원」). 이미 시작한 학생은 오늘 바뀌지 않으니 목록에서 뺀다 */
function MultiAssign({ view, onChange, onClose }: { view: TodayView; onChange: (v: TodayView) => void; onClose: () => void }) {
  const open = view.students.filter((s) => s.status === '지정 전' || s.status === '지정됨');
  const [ids, setIds] = useState<string[]>([]);
  const [unit, setUnit] = useState(view.units[0] ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string[] | null>(null);
  const all = ids.length === open.length && open.length > 0;
  const toggle = (id: string) => setIds(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);
  const submit = async () => {
    setBusy(true); setError(null);
    try {
      const r = await api.assignTasks(ids, unit);
      onChange(r);
      setDone(ids.map((id) => open.find((s) => s.id === id)?.name ?? ''));
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <Sheet title="여러 명에게 정하기" onClose={onClose}>
      {done ? (
        <>
          <p className="small">{done.length}명에게 「{unit}」을(를) 정했어요.</p>
          <ul className="stack small" style={{ margin: 0, paddingLeft: 18 }}>{done.map((n) => <li key={n}>{n}</li>)}</ul>
          <button className="btn btn--primary" onClick={onClose}>닫기</button>
        </>
      ) : (
        <>
          {open.length < view.students.length && <p className="small muted">오늘 공부를 이미 시작한 학생은 목록에 없어요.</p>}
          {open.length === 0 ? <p className="small">정할 수 있는 학생이 없어요.</p> : (
            <div className="card card--flat" style={{ padding: 0, overflow: 'hidden' }}>
              <label className={'check-row' + (all ? ' check-row--on' : '')}><span className="row"><input type="checkbox" checked={all} onChange={() => setIds(all ? [] : open.map((s) => s.id))} /> 전체 선택</span><span className="small muted num">{open.length}명</span></label>
              {open.map((s) => (
                <label key={s.id} className={'check-row' + (ids.includes(s.id) ? ' check-row--on' : '')}><span className="row"><input type="checkbox" checked={ids.includes(s.id)} onChange={() => toggle(s.id)} /> {s.name}</span><span className="small muted">{s.task ?? '아직 단원이 없어요'}</span></label>
              ))}
            </div>
          )}
          <label className="field">단원
            <select className="input" value={unit} onChange={(e) => setUnit(e.target.value)}>
              {view.units.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </label>
          <p className="small muted">문제는 학생마다 고른 난이도로 나와요.</p>
          <LoadError error={error} />
          <button className="btn btn--primary" disabled={busy || !ids.length || !unit} onClick={submit}>{busy ? '정하는 중…' : `${ids.length}명에게 정하기`}</button>
          <button className="btn btn--ghost" onClick={onClose}>닫기</button>{/* X3: 학생 상세 시트처럼 */}
        </>
      )}
    </Sheet>
  );
}
