// 서버에서 데이터를 불러오는 작은 도우미. loading / error / data 세 가지 상태와 다시 불러오기(reload)를 준다.
import { useCallback, useEffect, useRef, useState } from 'react';

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, deps);
  const reload = useCallback(() => {
    setLoading(true); setError(null);
    run()
      .then((d) => { if (alive.current) setData(d); })
      .catch((e: Error) => { if (alive.current) setError(e.message); })
      .finally(() => { if (alive.current) setLoading(false); });
  }, [run]);
  useEffect(reload, [reload]);
  return { data, setData, error, loading, reload };
}
