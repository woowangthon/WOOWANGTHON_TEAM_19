// 끊어 보내기 묶음 규칙 테스트. 문장은 전부 합성(아이 원문 아님).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createBatcher, followPending } from './chatBatch';

describe('createBatcher — 1.5초 묶기, 최대 5조각', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('마지막 입력 뒤 1.5초가 지나야 한 번에 보낸다', () => {
    const sent: string[][] = [];
    const b = createBatcher((t) => sent.push(t));
    b.push('가');
    vi.advanceTimersByTime(1000);
    b.push('나'); // 타이머가 다시 걸린다
    vi.advanceTimersByTime(1400);
    expect(sent).toEqual([]);
    expect(b.size()).toBe(2);
    vi.advanceTimersByTime(100);
    expect(sent).toEqual([['가', '나']]);
    expect(b.size()).toBe(0);
  });

  it('5조각이 차면 기다리지 않고 바로 보내고, 그 뒤 조각은 다음 묶음', () => {
    const sent: string[][] = [];
    const b = createBatcher((t) => sent.push(t));
    ['1', '2', '3', '4', '5', '6'].forEach((t) => b.push(t));
    expect(sent).toEqual([['1', '2', '3', '4', '5']]);
    vi.advanceTimersByTime(1500);
    expect(sent).toEqual([['1', '2', '3', '4', '5'], ['6']]);
  });

  it('cancel이면 모아 둔 조각을 보내지 않는다', () => {
    const send = vi.fn();
    const b = createBatcher(send);
    b.push('가');
    b.cancel();
    vi.advanceTimersByTime(5000);
    expect(send).not.toHaveBeenCalled();
  });

  it('peek은 아직 안 보낸 조각을 순서대로 보여 주고, 묶음은 그대로 둔다(다시 읽기 때 버리지 않게)', () => {
    const sent: string[][] = [];
    const b = createBatcher((t) => sent.push(t));
    b.push('가');
    b.push('나');
    const seen = b.peek();
    seen.push('다'); // 복사본이라 묶음에 영향 없음
    expect(b.peek()).toEqual(['가', '나']);
    vi.advanceTimersByTime(1500);
    expect(sent).toEqual([['가', '나']]);
    expect(b.peek()).toEqual([]);
  });
});

describe('followPending — pending이면 /reply 최대 3번', () => {
  it('pending이 아니면 reply를 부르지 않는다', async () => {
    const reply = vi.fn();
    const seen: unknown[] = [];
    await followPending({ pending: false }, reply, (r) => { seen.push(r); return true; });
    expect(reply).not.toHaveBeenCalled();
    expect(seen).toHaveLength(1);
  });

  it('pending이 계속되어도 3번까지만 부른다', async () => {
    const reply = vi.fn(async () => ({ pending: true }));
    await followPending({ pending: true }, reply, () => true);
    expect(reply).toHaveBeenCalledTimes(3);
  });

  it('pending이 끝나면 멈추고, onReply가 false(위기·단계 바뀜)면 바로 멈춘다', async () => {
    const reply = vi.fn().mockResolvedValueOnce({ pending: true }).mockResolvedValueOnce({ pending: false });
    await followPending({ pending: true }, reply, () => true);
    expect(reply).toHaveBeenCalledTimes(2);

    const reply2 = vi.fn(async () => ({ pending: true }));
    await followPending({ pending: true }, reply2, () => false);
    expect(reply2).not.toHaveBeenCalled();
  });
});
