// 수다 남은 시간 표시(TK-94, 명세 4.x 수다 행): 3분 전부터만, 「n분 남았어」(올림 분)
import { describe, expect, it } from 'vitest';
import { chatTimeShow } from './chatTime';

describe('수다 남은 시간 표시', () => {
  it('3분 넘게 남으면 숨김', () => {
    for (const s of [600, 300, 181]) expect(chatTimeShow(s), String(s)).toEqual({ show: false, minutes: 0, urgent: false });
  });
  it('3분 전부터 올림 분으로(3→2→1), 1분 안쪽은 강조', () => {
    expect(chatTimeShow(180)).toEqual({ show: true, minutes: 3, urgent: false });
    expect(chatTimeShow(179)).toEqual({ show: true, minutes: 3, urgent: false });
    expect(chatTimeShow(121)).toEqual({ show: true, minutes: 3, urgent: false });
    expect(chatTimeShow(120)).toEqual({ show: true, minutes: 2, urgent: false });
    expect(chatTimeShow(61)).toEqual({ show: true, minutes: 2, urgent: false });
    expect(chatTimeShow(60)).toEqual({ show: true, minutes: 1, urgent: true });
    expect(chatTimeShow(1)).toEqual({ show: true, minutes: 1, urgent: true });
  });
  it('0초(끝)는 안내 없음 — 끝 안내가 따로 뜬다', () => {
    expect(chatTimeShow(0)).toEqual({ show: false, minutes: 0, urgent: false });
  });
});
