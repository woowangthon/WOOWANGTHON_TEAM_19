// 남은 시간 표시용 카운트다운. 마감 판정은 서버가 하고, 화면은 보여 주기만 한다.
// 0이 되면 onZero로 서버에 다시 물어본다(서버가 단계를 넘긴다).
import { useEffect, useRef, useState } from 'react';

export function useCountdown(serverSec: number | null, onZero: () => void) {
  const [sec, setSec] = useState(serverSec ?? 0);
  const cb = useRef(onZero);
  cb.current = onZero;
  useEffect(() => { if (serverSec != null) setSec(serverSec); }, [serverSec]);
  const active = serverSec != null;
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => setSec((s) => {
      const next = Math.max(0, s - 1);
      if (next === 0 && s > 0) setTimeout(() => cb.current(), 0);
      return next;
    }), 1000);
    return () => clearInterval(t);
  }, [active]);
  return sec;
}
