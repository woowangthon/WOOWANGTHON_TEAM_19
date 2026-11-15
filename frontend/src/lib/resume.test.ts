// 「다시 보일 때 다시 읽기」 규칙 테스트. 브라우저 대신 EventTarget으로 window·document를 흉내 낸다.
import { describe, expect, it } from 'vitest';
import { listenResume, onceAtATime } from './resume';

function fakeDoc(state: 'visible' | 'hidden') {
  const d = new EventTarget() as EventTarget & { visibilityState: string };
  d.visibilityState = state;
  return d;
}

describe('listenResume — 화면이 다시 보이거나 인터넷이 돌아오면 부른다', () => {
  it('visibilitychange는 visible일 때만, online은 항상', () => {
    const win = new EventTarget();
    const doc = fakeDoc('hidden');
    let n = 0;
    const off = listenResume(() => { n++; }, win, doc);
    doc.dispatchEvent(new Event('visibilitychange')); // 내려갈 때 → 안 부름
    expect(n).toBe(0);
    doc.visibilityState = 'visible';
    doc.dispatchEvent(new Event('visibilitychange')); // 다시 올라옴
    expect(n).toBe(1);
    win.dispatchEvent(new Event('online'));
    expect(n).toBe(2);
    off();
    win.dispatchEvent(new Event('online'));
    doc.dispatchEvent(new Event('visibilitychange'));
    expect(n).toBe(2); // 떼면 더 안 부름
  });
});

describe('onceAtATime — 앞 요청이 끝나기 전 다시 부르면 같은 요청을 돌려준다', () => {
  it('동시에 여러 번 불러도 서버 요청은 한 번, 끝난 뒤엔 다시 나간다', async () => {
    let calls = 0;
    let done!: (v: number) => void;
    const f = onceAtATime(() => { calls++; return new Promise<number>((r) => { done = r; }); });
    const a = f();
    const b = f();
    expect(calls).toBe(1);
    expect(a).toBe(b);
    done(7);
    await expect(a).resolves.toBe(7);
    void f();
    expect(calls).toBe(2);
  });

  it('실패해도 다음 호출은 막히지 않는다', async () => {
    let calls = 0;
    const f = onceAtATime(() => { calls++; return Promise.reject(new Error('끊김')); });
    await expect(f()).rejects.toThrow('끊김');
    await expect(f()).rejects.toThrow('끊김');
    expect(calls).toBe(2);
  });
});
