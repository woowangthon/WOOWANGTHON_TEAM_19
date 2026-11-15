// 서버에서 데이터를 불러오는 작은 도우미. loading / error / data 세 가지 상태와 다시 불러오기(reload)를 준다.
// 4차(11-14): quiet() = 로딩·오류 표시 없이 조용히 다시 읽기(실패는 무시). 「쓰기 세대」를 두어, 화면이 setData로 막 바꾼 값(도장·지정 등)이나
// 그 사이 reload를 늦게 온 옛 조용한 응답이 덮지 않게 한다(bb 검토 ②).
import { useCallback, useEffect, useRef, useState, type SetStateAction } from 'react';

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setDataRaw] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);
  const gen = useRef(0); // 화면이 값을 바꾸거나 reload할 때마다 +1
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, deps);
  const setData = useCallback((v: SetStateAction<T | null>) => { gen.current += 1; setDataRaw(v); }, []);
  const reload = useCallback(() => {
    gen.current += 1; const g = gen.current;
    setLoading(true); setError(null);
    run()
      .then((d) => { if (alive.current && g === gen.current) setDataRaw(d); })
      .catch((e: Error) => { if (alive.current) setError(e.message); })
      .finally(() => { if (alive.current) setLoading(false); });
  }, [run]);
  /** 조용히 다시 읽기: 보낸 뒤 세대가 바뀌었으면(그사이 쓰기·reload) 응답을 버린다 */
  const quiet = useCallback(async () => {
    const g = gen.current;
    try { const d = await run(); if (alive.current && g === gen.current) setDataRaw(d); } catch { /* 다음 번에 다시 */ }
  }, [run]);
  useEffect(reload, [reload]);
  return { data, setData, error, loading, reload, quiet };
}
