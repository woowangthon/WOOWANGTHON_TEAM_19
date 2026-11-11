// 학습지도자 ① 범위 지정 — 이번 주에 다룰 단원을 고른다. 여기서 고른 단원만 "오늘 할 것"으로 지정할 수 있다.
import { useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { LoadError, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';

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
      <div className="row"><span className="pill">초등 4학년</span><span className="pill">수학</span></div>
      <h2 className="h3">단원 선택</h2>
      {loading && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {data && (
        <div className="card card--flat" style={{ padding: 0, overflow: 'hidden' }}>
          {data.map((u) => (
            <label key={u.id} className={'check-row' + (u.selected ? ' check-row--on' : '')} style={u.hasProblems ? undefined : { opacity: .55, cursor: 'default' }}>
              <span className="row"><input id={`unit-${u.id}`} type="checkbox" checked={u.selected} disabled={!u.hasProblems} onChange={() => toggle(u.id)} /> {u.name}</span>
              <span className="small muted num">{u.hasProblems ? `${u.count}문제` : '문제 준비 중'}</span>
            </label>
          ))}
        </div>
      )}
      <div className="notice notice--plain" style={{ justifyContent: 'center' }}>
        <span className="num">{selected.length}개 단원 · {selected.reduce((a, u) => a + u.count, 0)}문제 선택</span>
      </div>
      <LoadError error={saveError} />
    </Frame>
  );
}
