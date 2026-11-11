// 버튼 하나가 서버에 요청할 때: 진행 중(busy) · 실패 메시지(error)를 같이 관리한다.
import { useCallback, useState } from 'react';

export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true); setError(null);
    try { return await fn(); } catch (e) { setError((e as Error).message); return undefined; } finally { setBusy(false); }
  }, []);
  return { busy, error, setError, run };
}
