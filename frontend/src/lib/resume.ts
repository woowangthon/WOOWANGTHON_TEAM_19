// 휴대폰에서 앱을 내렸다 올리거나(화면 다시 보임) 인터넷이 끊겼다 돌아오면 서버 상태를 다시 읽기 위한 도우미.
// 화면 코드(Chat.tsx·state/session.tsx)와 떼어 둔 순수 로직이라 vitest로 검사한다(resume.test.ts).
import { useEffect, useRef } from 'react';

type Target = Pick<EventTarget, 'addEventListener' | 'removeEventListener'>;

/** 화면이 다시 보이거나(visibilitychange → visible) 인터넷이 돌아오면(online) cb를 부른다. 돌려준 함수로 뗀다 */
export function listenResume(
  cb: () => void,
  win: Target = window,
  doc: Target & { visibilityState: string } = document,
): () => void {
  const onVisible = () => { if (doc.visibilityState === 'visible') cb(); };
  doc.addEventListener('visibilitychange', onVisible);
  win.addEventListener('online', cb);
  return () => {
    doc.removeEventListener('visibilitychange', onVisible);
    win.removeEventListener('online', cb);
  };
}

/** 앞 요청이 끝나기 전에 또 부르면 새로 보내지 않고 같은 요청을 돌려준다(중복 요청 방지) */
export function onceAtATime<T>(fn: () => Promise<T>): () => Promise<T> {
  let running: Promise<T> | null = null;
  return () => {
    if (!running) running = fn().finally(() => { running = null; });
    return running;
  };
}

/** 화면에 붙어 있는 동안 listenResume. cb는 매번 최신 것을 부른다 */
export function useOnResume(cb: () => void) {
  const ref = useRef(cb);
  ref.current = cb;
  useEffect(() => listenResume(() => ref.current()), []);
}
