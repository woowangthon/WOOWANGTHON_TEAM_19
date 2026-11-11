// 학습 엔진 규칙 테스트 — 백엔드로 옮길 때도 이 테스트의 기대값이 그대로 기준이 된다.
import { describe, expect, it } from 'vitest';
import { MAX_HINTS, PROBLEM_UNITS, detectCrisis, generateProblems, hintsFor, judge, maskPII, replyFor, solutionFor } from './engine';
import type { Difficulty } from '../types';

const LEVELS: Difficulty[] = ['초급', '중급', '고급'];

describe('문제 만들기', () => {
  it('단원·난이도마다 서로 다른 5문제를 만들고, 답은 0과 1 사이다', () => {
    for (const unit of PROBLEM_UNITS) for (const level of LEVELS) {
      const ps = generateProblems(unit, level, '2026-11-10');
      expect(ps).toHaveLength(5);
      expect(new Set(ps.map((p) => `${p.left}|${p.right}`)).size).toBe(5);
      for (const p of ps) {
        expect(p.answer[0]).toBeGreaterThan(0);
        expect(p.answer[0]).toBeLessThan(p.answer[1]);
        // 답이 실제 계산과 같은지 (통분해서 확인)
        const lhs = p.left[0] * p.right[1] + (p.op === '+' ? 1 : -1) * p.right[0] * p.left[1];
        expect(lhs * p.answer[1]).toBe(p.answer[0] * p.left[1] * p.right[1]);
        if (level === '고급') expect(p.left[1]).not.toBe(p.right[1]); else expect(p.left[1]).toBe(p.right[1]);
      }
    }
  });
  it('같은 날·같은 난이도면 같은 문제가 나온다(새로고침해도 안 바뀜)', () => {
    expect(generateProblems('분수의 덧셈', '중급', 'd1')).toEqual(generateProblems('분수의 덧셈', '중급', 'd1'));
    expect(generateProblems('분수의 덧셈', '중급', 'd1')).not.toEqual(generateProblems('분수의 덧셈', '중급', 'd2'));
  });
});

describe('정답 판정', () => {
  const p = { id: 'p1', left: [1, 4] as [number, number], right: [2, 4] as [number, number], op: '+' as const, answer: [3, 4] as [number, number], k: 1 };
  it('정답과 약분·배수 형태를 모두 정답으로 본다', () => {
    expect(judge(p, 3, 4).correct).toBe(true);
    expect(judge(p, 6, 8).correct).toBe(true);
    expect(judge({ ...p, right: [1, 4], answer: [2, 4] }, 1, 2).correct).toBe(true);
  });
  it('분모가 0이면 오답이다', () => { expect(judge(p, 0, 0).correct).toBe(false); });
  it('분모끼리 더한 실수를 알아보고, 분자는 맞았다고 알려 준다', () => {
    const j = judge(p, 3, 8);
    expect(j).toMatchObject({ correct: false, numeratorOk: true, denominatorOk: false, tag: '분모끼리 더하기' });
  });
  it('분자만 틀리면 분자 계산 실수다', () => {
    expect(judge(p, 2, 4)).toMatchObject({ correct: false, numeratorOk: false, denominatorOk: true, tag: '분자 계산' });
  });
  it('통분을 빠뜨린 실수를 알아본다', () => {
    const q = { id: 'p2', left: [1, 2] as [number, number], right: [1, 4] as [number, number], op: '+' as const, answer: [3, 4] as [number, number], k: 2 };
    expect(judge(q, 2, 4).tag).toBe('통분 빠뜨림');
  });
});

describe('힌트와 풀이', () => {
  it('힌트는 3단계이고, 어떤 힌트에도 최종 답이 그대로 나오지 않는다', () => {
    for (const unit of PROBLEM_UNITS) for (const level of LEVELS) for (const p of generateProblems(unit, level, 'seed')) {
      const hints = hintsFor(p, '반말');
      expect(hints).toHaveLength(MAX_HINTS);
      // 힌트는 계산 결과(= 답)나 '답은'이라는 말을 담지 않는다. 답은 풀이에서만 나온다
      for (const h of hints) { expect(h).not.toContain('답은'); expect(h).not.toMatch(/=\s*\d/); }
      expect(solutionFor(p, '반말').join(' ')).toContain(`${p.answer[0]}/${p.answer[1]}`);
    }
  });
  it('말투 설정에 따라 문장이 달라진다', () => {
    const p = generateProblems('분수의 덧셈', '초급', 'seed')[0];
    expect(hintsFor(p, '반말')[0]).not.toBe(hintsFor(p, '존댓말')[0]);
  });
});

describe('수다·안전', () => {
  it('같은 말이 연달아 나오지 않는다', () => { expect(replyFor('음', 0, '반말')).not.toBe(replyFor('음', 1, '반말')); });
  it('위험 표현을 감지하고, 평범한 말은 지나친다', () => {
    expect(detectCrisis('요즘 그냥 사라지고 싶어')).toBe(true);
    expect(detectCrisis('오늘 급식 맛있었어')).toBe(false);
  });
  it('전화번호와 이메일을 가린다', () => {
    expect(maskPII('내 번호는 010-1234-5678이야')).toBe('내 번호는 [전화번호]이야');
    expect(maskPII('a.b@test.com 으로 보내')).toBe('[이메일] 으로 보내');
  });
});
