// 4차(성호 11-14): 보호자·선생님 화면을 보이는 동안 5초마다 조용히 다시 읽기(강의실 useLivePoll과는 따로, bb ①).
// 푸시·스트리밍이 아니라 화면이 묻는 방식. 탭이 숨으면 멈추고, 다시 보이면 바로 한 번. 읽는 중이면 겹쳐 보내지 않음. 소리·알림 권한 없음(bb ④)
import { useEffect, useRef } from 'react';

export const shouldPoll = (visibility: DocumentVisibilityState | string, inFlight: boolean) => visibility === 'visible' && !inFlight;

export function useQuietPoll(fns: (() => Promise<unknown>)[], ms = 5_000) {
  const ref = useRef(fns); ref.current = fns;
  const busy = useRef(false);
  useEffect(() => {
    const tick = async () => {
      if (!shouldPoll(document.visibilityState, busy.current)) return;
      busy.current = true;
      try { await Promise.all(ref.current.map((f) => f())); } finally { busy.current = false; }
    };
    const id = window.setInterval(tick, ms);
    const onVis = () => { if (document.visibilityState === 'visible') void tick(); };
    document.addEventListener('visibilitychange', onVis);
    return () => { window.clearInterval(id); document.removeEventListener('visibilitychange', onVis); };
  }, [ms]);
}
