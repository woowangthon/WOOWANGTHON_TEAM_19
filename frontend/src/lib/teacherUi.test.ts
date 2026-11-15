// 강사 화면 작은 규칙(dev round2 #10·#11·#13)
import { describe, expect, it, vi } from 'vitest';
import { grantDefault, memoLocked, shouldFillPicked, withRollback } from './teacherUi';

describe('#10 지정한 문제 글 다시 채우기', () => {
  const units = [{ name: '분수의 나눗셈', problems: [] }];
  it('처음 열 때 단원 목록이 늦게 오면 한 번 채운다', () => {
    expect(shouldFillPicked({ touched: false, picked: null, assignedId: 'p16', units })).toBe(true);
    expect(shouldFillPicked({ touched: false, picked: null, assignedId: 'p16', units: null })).toBe(false);
  });
  it('「없음」 고른 뒤 지정한 문제 글이 다시 나타나지 않음', () => {
    // 강사가 고른 뒤(touched)에는 시트를 연 순간의 옛 assignedProblemId로 되살리지 않는다
    expect(shouldFillPicked({ touched: true, picked: null, assignedId: 'p16', units })).toBe(false);
  });
  it('이미 채웠거나 지정이 없으면 채우지 않는다', () => {
    expect(shouldFillPicked({ touched: false, picked: '16번 · …', assignedId: 'p16', units })).toBe(false);
    expect(shouldFillPicked({ touched: false, picked: null, assignedId: null, units })).toBe(false);
  });
});

describe('#10 지정 실패 되돌리기', () => {
  it('지정 실패 시 select가 이전 값으로 돌아감', async () => {
    let value = '분수의 나눗셈';
    const apply = vi.fn(() => { value = ''; });
    await expect(withRollback(apply, () => { value = '분수의 나눗셈'; }, () => Promise.reject(new Error('저장하지 못했어요.')))).rejects.toThrow('저장하지 못했어요.');
    expect(apply).toHaveBeenCalledOnce();
    expect(value).toBe('분수의 나눗셈');
  });
  it('성공하면 바꾼 값 그대로, 결과를 돌려준다', async () => {
    let value = 'a';
    await expect(withRollback(() => { value = 'b'; }, () => { value = 'a'; }, async () => 7)).resolves.toBe(7);
    expect(value).toBe('b');
  });
});

describe('#11 초안 뒤 메모', () => {
  it('http 모드 + draft 있으면 메모 입력 readOnly', () => {
    expect(memoLocked(true, 'http')).toBe(true);
    expect(memoLocked(false, 'http')).toBe(false);
    expect(memoLocked(true, 'mock')).toBe(false); // mock은 「초안 다시 만들기」로 메모를 다시 반영한다
  });
});

describe('#13 칭찬 씨앗 기본 개수', () => {
  it('grantedToday 9이면 시트 기본값 1개', () => {
    expect(grantDefault(9)).toBe(1);
  });
  it('여유가 있으면 지금처럼 2개', () => {
    expect(grantDefault(0)).toBe(2);
    expect(grantDefault(8)).toBe(2);
  });
});

// 11-14 실측: 지정 문제(분수)가 골라진 채 단원을 「큰 수」로 바꾸면 옛 단원 문제 id가 같이 가서 서버 422
import { pickForUnit } from './teacherUi';
describe('단원을 바꾸면 문제 고르기는 처음으로', () => {
  it('같은 단원이면 고른 문제 그대로, 다른 단원이면 \'\'(처음 문제부터)', () => {
    expect(pickForUnit('분수 ÷ 자연수', '분수 ÷ 자연수', 'frac-div-nat-01')).toBe('frac-div-nat-01');
    expect(pickForUnit('분수 ÷ 자연수', '큰 수 (초4)', 'frac-div-nat-01')).toBe('');
    expect(pickForUnit('분수 ÷ 자연수', '큰 수 (초4)', 'random')).toBe('');
  });
});
