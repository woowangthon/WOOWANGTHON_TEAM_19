// D11: 서버 오류 문구 — 무엇을 하면 되는지 한 줄(아이는 반말, 어른은 존댓말)
import { describe, expect, it } from 'vitest';
import { serverErrorText } from './serverError';

describe('serverErrorText', () => {
  it('아이: 다시 눌러 보고, 계속 안 되면 어른에게', () => {
    expect(serverErrorText(500, true)).toBe('잠깐 문제가 생겼어. 조금 뒤에 다시 눌러 줘. 계속 안 되면 선생님이나 보호자께 알려 줘. (500)');
  });
  it('어른: 잠시 뒤 다시, 계속되면 새로고침', () => {
    expect(serverErrorText(503, false)).toBe('잠시 문제가 생겼어요. 잠시 뒤 다시 눌러 주세요. 계속되면 화면을 새로고침해 주세요. (503)');
  });
});
