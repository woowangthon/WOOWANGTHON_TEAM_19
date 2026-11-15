// 문제 글 미리보기(퀴즈 칩·강사 문제 목록) — 보내는 값은 늘 문장 전체(bb 검토 11-14)
import { describe, expect, it } from 'vitest';
import { problemPreview } from './problemPreview';

const ENG_FILL = '빈칸에 알맞은 말을 고르세요.\nThe girl ___ is sitting next to Mina is my cousin.\n① which\n② who\n③ whose\n④ where\n(번호만 써 주세요)';
const ENG_WRITE = '빈칸에 들어갈 관계사를 쓰세요.\nI have a friend ___ dog can open the door by itself.\n(영어 한 단어로 써 주세요)';
const ENG_WRONG = "어법상 틀린 문장을 고르세요.\n① What I need now is a long rest.\n② The movie that we watched last night was boring.\n③ I can't believe that he won the race.\n④ This is the novel.\n(번호만 써 주세요)";
const KOR = "「동생이 '새' 운동화를 신고 나갔다.」에서 '새'의 품사는 무엇일까요?\n① 형용사\n② 관형사\n③ 부사\n④ 명사\n(번호만 써 주세요)";
const FRAC = '3/4 ÷ 2 를 계산해 보세요.';
const MATH4 = '58274163에서 숫자 7이 나타내는 값은 얼마인가요?\n(쉼표 없이 숫자만)';

describe('문제 글 미리보기', () => {
  it('보기(①) 앞의 줄 전부, 괄호 안내 줄은 뺌', () => {
    expect(problemPreview(ENG_FILL)).toEqual({ label: '빈칸에 알맞은 말을 고르세요. The girl ___ is sitting next to Mina is my cousin.', choices: 4 });
    expect(problemPreview(ENG_WRITE)).toEqual({ label: '빈칸에 들어갈 관계사를 쓰세요. I have a friend ___ dog can open the door by itself.', choices: 0 });
    expect(problemPreview(KOR).choices).toBe(4);
    expect(problemPreview(FRAC)).toEqual({ label: FRAC, choices: 0 });
    expect(problemPreview(MATH4)).toEqual({ label: '58274163에서 숫자 7이 나타내는 값은 얼마인가요?', choices: 0 });
  });
  it('보기 앞이 지시문 한 줄뿐이면 첫 보기 줄까지(서로 구별되게)', () => {
    expect(problemPreview(ENG_WRONG).label).toBe('어법상 틀린 문장을 고르세요. ① What I need now is a long rest.');
  });
  it('길면 말줄임', () => {
    const p = problemPreview('가'.repeat(200), 50);
    expect(p.label).toHaveLength(50); expect(p.label.endsWith('…')).toBe(true);
  });
});
