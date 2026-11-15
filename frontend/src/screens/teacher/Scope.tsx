// 학습지도자 ① 범위 지정 — 이번 주에 다룰 단원을 고른다. 여기서 고른 단원만 "오늘 할 것"으로 지정할 수 있다.
import { useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { LoadError, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import type { Unit } from '../../types';

const GRADE_LABEL: Record<number, string> = { 4: '초4', 5: '초5~6', 6: '초5~6', 8: '중2', 10: '고1' };
const SUBJECT_LABEL: Record<string, string> = { math: '수학', korean: '국어', english: '영어' };
/** 학년 → 머리글(「초4 · 수학」). grade가 없으면(mock) 머리글 없이 한 묶음 */
function groups(units: Unit[]): [string, Unit[]][] {
  const out = new Map<string, Unit[]>();
  for (const u of units) {
    const label = u.grade ? [GRADE_LABEL[u.grade] ?? `${u.grade}학년`, u.subject ? SUBJECT_LABEL[u.subject] ?? u.subject : ''].filter(Boolean).join(' · ') : '';
    out.set(label, [...(out.get(label) ?? []), u]);
  }
  return [...out.entries()].sort((a, b) => (a[1][0].grade ?? 0) - (b[1][0].grade ?? 0));
}

export function TeacherScope() {
  const { data, setData, error, loading, reload } = useAsync(() => api.getUnits());
  const [state, setState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);
  const selected = data?.filter((u) => u.selected) ?? [];
  const toggle = (id: string) => { setState('idle'); setData(data!.map((u) => (u.id === id ? { ...u, selected: !u.selected } : u))); };
  const save = async () => {
    setState('saving'); setSaveError(null);
    try { setData(await api.saveUnits(selected.map((u) => u.id))); setState('saved'); }
    catch (e) { setSaveError((e as Error).message); setState('idle'); }
  };

  return (
    <Frame adult title="범위 지정" exit tabs="teacher"
      actions={<button className="btn btn--primary" disabled={!selected.length || state === 'saving'} onClick={save}>{state === 'saved' ? '저장했어요' : '이번 주 범위 저장'}</button>}>
      <h2 className="h3">단원 선택</h2>
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {data && (
        // G4(11-14): 학년이 늘어난 단원을 학년별로 묶는다(서버 grade, 없으면 한 묶음)
        groups(data).map(([label, units]) => (
        <section key={label} className="stack" style={{ gap: 6 }}>
        {label && <h3 className="small muted" style={{ margin: 0 }}>{label}</h3>}
        <div className="card card--flat" style={{ padding: 0, overflow: 'hidden' }}>
          {units.map((u) => (
            <label key={u.id} className={'check-row' + (u.selected ? ' check-row--on' : '')} style={u.hasProblems ? undefined : { opacity: .55, cursor: 'default' }}>
              <span className="row"><input id={`unit-${u.id}`} type="checkbox" checked={u.selected} disabled={!u.hasProblems} onChange={() => toggle(u.id)} /> {u.name}</span>
              <span className="small muted num">{u.hasProblems ? `${u.count}문제` : '문제 준비 중'}</span>
            </label>
          ))}
        </div>
        </section>
        ))
      )}
      <div className="notice notice--plain" style={{ justifyContent: 'center' }}>
        <span className="num">{selected.length}개 단원 · {selected.reduce((a, u) => a + u.count, 0)}문제 선택</span>
      </div>
      <LoadError error={saveError} />
    </Frame>
  );
}
