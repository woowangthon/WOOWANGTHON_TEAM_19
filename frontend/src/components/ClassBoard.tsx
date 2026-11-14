// 강의실 공지·숙제 화면 부품(11-13). 계산·저장은 lib/classBoard. 모양은 기존 부품(card·pill·chip·seg·Sheet)으로 임시 조립 — 정식 시안은 GPT 요청서(3)
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from './Icon';
import { LoadError, Sheet } from './Common';
import { useAuth } from '../state/auth';
import { useMentor } from '../state/mentor';
import { josa } from '../lib/josa';
import { shortLabel } from '../lib/date';
import {
  BODY_MAX, TITLE_MAX, addPost, daysLeft, dueChoices, dueText, isNew, openHomework, postsForStudent, postsOfClass, removePost, toggleDone, useClassPosts,
  type ClassPost, type PostKind,
} from '../lib/classBoard';
import { useClassSessions } from '../lib/classSession';
import type { Classroom } from '../types';

const KIND_LABEL: Record<PostKind, string> = { notice: '공지', homework: '숙제' };

/* ================= 학습지도자: 강의실 카드 안 공지·숙제 ================= */
export function TeacherBoard({ room }: { room: Classroom }) {
  const { posts, now } = useClassPosts();
  const [open, setOpen] = useState(false);
  const list = postsOfClass(room.id, posts).slice(0, 3);
  return (
    <div className="stack">
      <div className="row between"><strong className="small">공지 · 숙제</strong>
        <button className="btn btn--secondary btn--small" disabled={room.members.length === 0} onClick={() => setOpen(true)}><Icon name="plus" size={16} />올리기</button>
      </div>
      {list.length === 0 && <p className="small muted">숙제나 알릴 일을 올리면 학생과 보호자가 봐요.</p>}
      {list.map((p) => (
        <div key={p.id} className="card card--flat row between" style={{ padding: '10px 12px' }}>
          <span style={{ minWidth: 0 }}>
            <span className={'pill ' + (p.kind === 'homework' ? 'pill--accent' : 'pill--mint')}>{KIND_LABEL[p.kind]}</span> <strong className="small">{p.title}</strong>
            <span className="small muted" style={{ display: 'block' }}>
              {p.kind === 'homework' ? `${dueText(p.due!, now)} · 다 했어 ${p.done.length}/${p.members.length}명` : `${new Date(p.at).getMonth() + 1}/${new Date(p.at).getDate()} 올림`}
            </span>
          </span>
          <button className="btn btn--ghost btn--small" onClick={() => removePost(p.id)} aria-label={`${p.title} 지우기`}>지우기</button>
        </div>
      ))}
      {open && <PostSheet room={room} onClose={() => setOpen(false)} />}
    </div>
  );
}

function PostSheet({ room, onClose }: { room: Classroom; onClose: () => void }) {
  const [kind, setKind] = useState<PostKind>('homework');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const choices = dueChoices();
  const [due, setDue] = useState(choices[0].key);
  const [error, setError] = useState<string | null>(null);
  const submit = () => {
    try { addPost(room, { kind, title, body, due: kind === 'homework' ? due : null }); onClose(); }
    catch (e) { setError((e as Error).message); }
  };
  return (
    <Sheet title={`${room.name}에 올리기`} onClose={onClose}>
      <div className="seg" role="group" aria-label="종류">
        {(['homework', 'notice'] as const).map((k) => (
          <button key={k} type="button" className={'seg__btn' + (kind === k ? ' seg__btn--on' : '')} aria-pressed={kind === k} onClick={() => setKind(k)}>{KIND_LABEL[k]}</button>
        ))}
      </div>
      <label className="field">제목<input className="input" value={title} maxLength={TITLE_MAX} onChange={(e) => setTitle(e.target.value)} placeholder={kind === 'homework' ? '예: 분수의 나눗셈 3쪽 풀기' : '예: 금요일은 30분 일찍 끝나요'} /></label>
      <label className="field">내용 <span className="small muted">(선택 · {BODY_MAX}자까지)</span>
        <textarea className="input" rows={3} value={body} maxLength={BODY_MAX} onChange={(e) => setBody(e.target.value)} /></label>
      {kind === 'homework' && (
        <fieldset style={{ border: 0, padding: 0, margin: 0 }}><legend className="small">마감 · 다음 수업 전까지</legend>
          <div className="chip-row">
            {choices.map((c) => (
              <button key={c.key} type="button" className={'chip' + (due === c.key ? ' chip--on' : '')} aria-pressed={due === c.key} onClick={() => setDue(c.key)}>
                {c.n === 1 ? '내일' : c.n === 2 ? '모레' : '일주일 뒤'} · {shortLabel(c.key)}
              </button>
            ))}
          </div>
        </fieldset>
      )}
      <p className="small muted">학생과 연결된 보호자가 읽을 수 있어요. 답글은 받지 않아요. 아이 개인 정보는 적지 말아 주세요.</p>
      <LoadError error={error} />
      <div className="sheet__actions">
        <button className="btn btn--primary" disabled={!title.trim()} onClick={submit}>올리기</button>
        <button className="btn btn--ghost" onClick={onClose}>취소</button>
      </div>
    </Sheet>
  );
}

/* ================= 학생: 강의실 카드 안 공지·숙제 ================= */
export function StudentBoard({ classId }: { classId: string }) {
  const { me } = useAuth();
  const { say } = useMentor();
  const { posts, now } = useClassPosts();
  if (!me) return null;
  const list = postsOfClass(classId, posts).filter((p) => p.members.some((m) => m.id === me.id) && !(p.kind === 'homework' && daysLeft(p.due!, now) < -7)).slice(0, 5);
  if (!list.length) return null;
  return (
    <div className="stack">
      {list.map((p) => <PostRow key={p.id} p={p} now={now} me={me.id} say={say} />)}
    </div>
  );
}

function PostRow({ p, now, me, say }: { p: ClassPost; now: number; me: string; say: (a: string, b: string) => string }) {
  const done = p.done.includes(me);
  return (
    <div className="card card--flat stack" style={{ padding: '10px 12px', gap: 6 }}>
      <div className="row between">
        <span><span className={'pill ' + (p.kind === 'homework' ? 'pill--accent' : 'pill--mint')}>{KIND_LABEL[p.kind]}</span>{isNew(p, now) && <span className="pill" style={{ marginLeft: 4 }}>새</span>}</span>
        {p.kind === 'homework' && <span className="small muted">{dueText(p.due!, now)}</span>}
      </div>
      <strong>{p.title}</strong>
      {p.body && <p className="small" style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{p.body}</p>}
      {p.kind === 'homework' && (
        <button className={'chip' + (done ? ' chip--on' : '')} style={{ alignSelf: 'flex-start' }} aria-pressed={done} onClick={() => toggleDone(p.id, me)}>
          {done && <Icon name="check" size={14} />}{done ? say('다 했어', '다 했어요') : say('다 하면 눌러', '다 하면 눌러요')}
        </button>
      )}
    </div>
  );
}

/* ================= 학생: 오늘 화면 숙제 알림 카드 ================= */
export function StudentHomeworkCard() {
  const { me } = useAuth();
  const { say } = useMentor();
  const { posts, now } = useClassPosts();
  if (!me || me.role !== 'student') return null;
  const open = openHomework(me.id, now, posts);
  if (!open.length) return null;
  const first = open[0];
  return (
    <Link to="/student/classes" className={'card row between' + (daysLeft(first.due!, now) <= 1 ? ' card--warn' : '')} style={{ textDecoration: 'none', color: 'inherit' }}>
      <span style={{ minWidth: 0 }}>
        <span className="small muted" style={{ display: 'block' }}>{say(`숙제 ${open.length}개가 남았어`, `숙제 ${open.length}개가 남았어요`)}</span>
        <strong>{first.title}</strong> <span className="small muted">· {dueText(first.due!, now)}</span>
      </span>
      <Icon name="chevron" size={20} />
    </Link>
  );
}

/* ================= 보호자: 아이 숙제(아이가 스스로 표시한 것) ================= */
export function GuardianHomeworkCard() {
  const { me } = useAuth();
  const { posts, now } = useClassPosts();
  const { defaults: d } = useClassSessions();
  if (!me || me.role !== 'guardian') return null;
  const rows = me.linked.flatMap((c) => postsForStudent(c.id, posts)
    .filter((p) => (p.kind === 'homework' ? daysLeft(p.due!, now) >= 0 : isNew(p, now)))
    .map((p) => ({ c, p })));
  if (!rows.length) return null;
  return (
    <section className="card stack" aria-label="강의실 공지·숙제">
      <div className="row between"><strong>강의실 공지 · 숙제</strong>{!d.notifyGuardian && <span className="small muted">알림 꺼짐(학원 설정)</span>}</div>
      {rows.slice(0, 5).map(({ c, p }) => (
        <div key={p.id + c.id} className="row between">
          <span style={{ minWidth: 0 }}>
            <span className={'pill ' + (p.kind === 'homework' ? 'pill--accent' : 'pill--mint')}>{KIND_LABEL[p.kind]}</span> <strong className="small">{p.title}</strong>
            <span className="small muted" style={{ display: 'block' }}>{p.className}{p.kind === 'homework' ? ` · ${dueText(p.due!, now)}` : ''}</span>
          </span>
          {p.kind === 'homework' && <span className={'pill ' + (p.done.includes(c.id) ? 'pill--mint' : '')}>{p.done.includes(c.id) ? `${josa(c.name, '이', '가')} 했다고 표시` : '아직'}</span>}
        </div>
      ))}
      <p className="small muted">「했다고 표시」는 아이가 스스로 누른 거예요. 선생님이 검사한 결과가 아니에요.</p>
    </section>
  );
}
