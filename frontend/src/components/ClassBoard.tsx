// 강의실 공지·숙제 화면 부품(11-13). 계산·저장은 lib/classBoard. 모양은 기존 부품(card·pill·chip·seg·Sheet)으로 임시 조립 — 정식 시안은 GPT 요청서(3)
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from './Icon';
import { LoadError, Sheet } from './Common';
import { useAuth } from '../state/auth';
import { useMentor } from '../state/mentor';
import { shortLabel } from '../lib/date';
import {
  BODY_MAX, TITLE_MAX, addPost, daysLeft, dueChoices, dueText, isNew, openHomework, postsForStudent, postsOfClass, removePost, toggleDone, useClassPosts,
  type ClassPost, type PostKind,
} from '../lib/classBoard';
import { liveError, useClassSessions } from '../lib/classSession';
import type { Classroom } from '../types';

const KIND_LABEL: Record<PostKind, string> = { notice: '공지', homework: '숙제' };

/** 강의실 쓰기(공지·숙제 올리기·지우기, 원장 기본값·장소)가 서버에서 실패했을 때 한 줄. 요청은 기다리지 않고 보내므로(liveAct)
 *  실패 문구를 여기서 읽어 보인다 — 올렸다고 생각했는데 아무 말 없이 글이 없던 것(dev round2 #8). 다음 쓰기가 성공하면 사라진다 */
export function LiveSaveError() {
  useClassSessions(); // 실패·다시 읽기 알림에 다시 그린다
  return <LoadError error={liveError} />;
}

/* ================= 학습지도자: 강의실 카드 안 공지·숙제 ================= */
export function TeacherBoard({ room }: { room: Classroom }) {
  const { posts, now } = useClassPosts();
  const [open, setOpen] = useState(false);
  const list = postsOfClass(room.id, posts).slice(0, 3);
  return (
    <div className="stack class-board">
      <div className="row between class-board__head"><strong className="small">공지 · 숙제</strong>
        <button className="btn btn--secondary btn--small" disabled={room.members.length === 0} onClick={() => setOpen(true)}><Icon name="plus" size={16} />올리기</button>
      </div>
      {list.length === 0 && <p className="small muted">숙제나 알릴 일을 올리면 학생과 보호자가 봐요.</p>}
      {list.map((p) => (
        <div key={p.id} className="card card--flat row between board-post">
          <span className="board-post__copy">
            <span className={'pill board-kind ' + (p.kind === 'homework' ? 'pill--accent' : 'pill--mint')}><Icon name={p.kind === 'homework' ? 'book' : 'bell'} size={16} />{KIND_LABEL[p.kind]}</span>
            <strong>{p.title}</strong>
            <span className="small muted">
              {p.kind === 'homework' ? `${dueText(p.due!, now)} · 다 했어 ${p.done.length}/${p.members.length}명` : `${new Date(p.at).getMonth() + 1}/${new Date(p.at).getDate()} 올림`}
            </span>
          </span>
          <button className="btn btn--ghost btn--small board-delete" onClick={() => removePost(p.id)} aria-label={`${p.title} 지우기`}>지우기</button>
        </div>
      ))}
      <LiveSaveError />
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
      <div className="post-form">
      <div className="seg" role="group" aria-label="종류">
        {(['homework', 'notice'] as const).map((k) => (
          <button key={k} type="button" className={'seg__btn' + (kind === k ? ' seg__btn--on' : '')} aria-pressed={kind === k} onClick={() => setKind(k)}><Icon name={k === 'homework' ? 'book' : 'bell'} size={18} />{KIND_LABEL[k]}</button>
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
      <p className="small muted post-form__hint">학생과 보호자가 함께 봐요. 개인 정보는 적지 마세요.</p>
      </div>
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
    <div className="card card--flat stack student-post">
      <div className="row between student-post__meta">
        <span><span className={'pill board-kind ' + (p.kind === 'homework' ? 'pill--accent' : 'pill--mint')}><Icon name={p.kind === 'homework' ? 'book' : 'bell'} size={16} />{KIND_LABEL[p.kind]}</span>{isNew(p, now) && <span className="pill" style={{ marginLeft: 4 }}>새</span>}</span>
        {p.kind === 'homework' && <span className={'small muted' + (daysLeft(p.due!, now) < 0 ? ' homework-past' : '')}>{daysLeft(p.due!, now) < 0 && <Icon name="clock" size={14} />}{dueText(p.due!, now)}</span>}
      </div>
      <strong>{p.title}</strong>
      {p.body && <p className="small student-post__body">{p.body}</p>}
      {p.kind === 'homework' && (
        <button className={'chip homework-done' + (done ? ' chip--on' : '')} aria-pressed={done} onClick={() => toggleDone(p.id, me)}>
          <Icon name={done ? 'check' : 'book'} size={20} />{done ? say('다 했어', '다 했어요') : say('숙제 다 했어', '숙제 다 했어요')}
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
    <Link to="/student/classes" className={'card row between homework-summary' + (daysLeft(first.due!, now) <= 1 ? ' card--warn' : '')}>
      <span className="homework-summary__copy">
        <span className="small muted">{say(`숙제 ${open.length}개가 남았어`, `숙제 ${open.length}개가 남았어요`)}</span>
        <strong>{first.title}</strong><span className="small muted">{dueText(first.due!, now)}</span>
      </span>
      <Icon name="chevron" size={24} />
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
  const multi = me.linked.length > 1; // 아이가 둘 이상이면 「아직」 줄에도 누구 숙제인지 이름을 붙인다
  return (
    <section className="card stack guardian-board" aria-label="강의실 공지·숙제">
      <div className="row between"><strong>강의실 공지 · 숙제</strong>{!d.notifyGuardian && <span className="small muted">알림 꺼짐</span>}</div>
      <div className="guardian-board__disclaimer"><Icon name="info" size={20} />
        <span>아이가 직접 누른 표시예요.</span>
      </div>
      {rows.slice(0, 5).map(({ c, p }) => (
        <div key={p.id + c.id} className="row between guardian-board__row">
          <span style={{ minWidth: 0 }}>
            <span className={'pill board-kind ' + (p.kind === 'homework' ? 'pill--accent' : 'pill--mint')}><Icon name={p.kind === 'homework' ? 'book' : 'bell'} size={16} />{KIND_LABEL[p.kind]}</span> <strong className="small">{p.title}</strong>
            <span className="small muted" style={{ display: 'block' }}>{p.className}{p.kind === 'homework' ? ` · ${dueText(p.due!, now)}` : ''}</span>
          </span>
          {p.kind === 'homework' && <span className={'pill ' + (p.done.includes(c.id) ? 'pill--mint' : '')}>{p.done.includes(c.id) ? (multi ? `${c.name} · 다 했어요` : '다 했어요') : multi ? `${c.name} · 아직이에요` : '아직이에요'}</span>}
        </div>
      ))}
    </section>
  );
}
