// 1안 「수다 안에서 받기」(성호 11-15): 수다 중 🔴 응답이면 화면에 남아 서버 문장 + 연락처, 시간 종료는 지금처럼 넘어간다.
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { chatReplyAction } from '../../lib/chatBatch';

vi.mock('../../state/auth', () => ({ useAuth: () => ({ me: null }), useMeOptional: () => null }));
const { CrisisInChat } = await import('./Chat');

describe('수다 응답 받기', () => {
  it('수다 중 crisis → 화면에 남음, 시간 종료(wrap) → 지금처럼 넘어감, 떠난 뒤 온 crisis → 위기 화면으로', () => {
    expect(chatReplyAction('chat', false)).toBe('reply');
    expect(chatReplyAction('crisis', false)).toBe('crisis-here');
    expect(chatReplyAction('wrap', false)).toBe('leave');
    expect(chatReplyAction('crisis', true)).toBe('leave');
  });
  it('수다 안 카드는 같은 렌더에 1388·109·문자·알림 줄, 입력창 없음', () => {
    const html = renderToStaticMarkup(<MemoryRouter><CrisisInChat /></MemoryRouter>);
    for (const h of ['tel:1388', 'tel:109', 'sms:1388']) expect(html).toContain(h);
    expect(html).toContain('힘들어 보인다고 알렸어');
    // v0.8(성호 11-15): 보호자 얘기가 먼저, 1388은 그 아래 일반 크기. 아이에게 「앞뒤 몇 마디가 갔다」고 말하지 않는다(발췌 없음)
    expect(html.indexOf('힘들어 보인다고 알렸어')).toBeLessThan(html.indexOf('tel:1388'));
    expect(html).not.toContain('앞뒤');
    expect(html).not.toContain('<input');
  });
  it('고정 문장을 화면 코드에 적지 않는다(서버 reply만)', async () => {
    const src = (await import('./Chat?raw')).default as string;
    expect(src).not.toContain('혼자 견디지 않아도');
    expect(src).not.toContain('말해 줘서 정말 고마워');
  });
});
