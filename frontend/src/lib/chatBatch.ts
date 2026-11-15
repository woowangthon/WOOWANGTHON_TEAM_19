// 수다 끊어 보내기(11-11): 아이가 "음…", "3/8?", "맞아?"처럼 끊어 보낸 말을 모아 한 번에 보낸다.
// · 마지막 입력 뒤 1.5초가 지나면 보낸다. 5조각이 차면 바로 보낸다(넘치면 다음 묶음).
// · 서버 응답이 pending이면 /reply로 답을 더 받는다(최대 3번).
// 화면(Chat.tsx)과 떼어 둔 순수 로직이라 vitest로 시간까지 검사한다(chatBatch.test.ts).

export const BATCH_WAIT_MS = 1500;
export const BATCH_MAX = 5;
export const REPLY_MAX = 3;

export interface Batcher {
  /** 조각 하나 넣기. 5개가 차면 바로 보내고, 아니면 1.5초 타이머를 다시 건다 */
  push(text: string): void;
  /** 모아 둔 조각 수 */
  size(): number;
  /** 아직 보내지 않은 조각(복사본). 서버 대화를 다시 읽을 때 화면에 남겨 둔다 */
  peek(): string[];
  /** 모아 둔 조각을 1.5초를 기다리지 않고 바로 보낸다(화면을 떠날 때 — 🔴 검사를 거치게, 명세 4.11 7) */
  flush(): void;
  /** 타이머·모아 둔 조각을 버린다 */
  cancel(): void;
}

export function createBatcher(send: (texts: string[]) => void, waitMs = BATCH_WAIT_MS, max = BATCH_MAX): Batcher {
  let buf: string[] = [];
  let timer: ReturnType<typeof setTimeout> | null = null;
  const stop = () => { if (timer) { clearTimeout(timer); timer = null; } };
  const flush = () => {
    stop();
    if (!buf.length) return;
    const texts = buf;
    buf = [];
    send(texts);
  };
  return {
    push(text) {
      buf.push(text);
      if (buf.length >= max) flush();
      else { stop(); timer = setTimeout(flush, waitMs); }
    },
    size: () => buf.length,
    peek: () => [...buf],
    flush,
    cancel() { stop(); buf = []; },
  };
}

/** 앱 전환·스와이프 종료(visibilitychange hidden·pagehide) 때 onHide를 바로 부른다(명세 3.2, 성호 11-15). 떼는 함수를 돌려준다 */
export function listenHidden(win: EventTarget, doc: EventTarget & { visibilityState: string }, onHide: () => void): () => void {
  const vis = () => { if (doc.visibilityState === 'hidden') onHide(); };
  doc.addEventListener('visibilitychange', vis);
  win.addEventListener('pagehide', onHide);
  return () => { doc.removeEventListener('visibilitychange', vis); win.removeEventListener('pagehide', onHide); };
}

/**
 * 첫 응답을 넣고, pending이면 reply()로 답을 더 받는다(최대 REPLY_MAX번).
 * onReply가 false를 돌려주면(위기·단계 바뀜) 바로 멈춘다.
 */
export async function followPending<R extends { pending?: boolean }>(
  first: R,
  reply: () => Promise<R>,
  onReply: (r: R) => boolean,
  max = REPLY_MAX,
): Promise<void> {
  let r = first;
  for (let i = 0; ; i++) {
    if (!onReply(r) || !r.pending || i >= max) return;
    r = await reply();
  }
}

/** 수다 화면을 떠난 뒤 도착한 응답의 단계 → 보낼 화면. 위기면 위기 화면(아이가 109·1388을 꼭 보게), 그 밖은 null(그대로) */
export function routeAfterLeftChat(phase: string): string | null {
  return phase === 'crisis' ? '/student/crisis' : null;
}

/** 1안 「수다 안에서 받기」(성호 11-15): 수다 화면이 응답 하나를 어떻게 받을지.
 *  crisis-here = 화면에 남아 서버 문장 말풍선 + 연락처 카드(세션은 화면을 떠날 때 맞춘다),
 *  leave = 단계가 바뀜(시간 종료 등 — 지금처럼 바로 맞춰 다음 화면으로), reply = 계속 */
export function chatReplyAction(phase: string, leftAlready: boolean): 'crisis-here' | 'leave' | 'reply' {
  if (phase === 'chat') return 'reply';
  return phase === 'crisis' && !leftAlready ? 'crisis-here' : 'leave';
}
