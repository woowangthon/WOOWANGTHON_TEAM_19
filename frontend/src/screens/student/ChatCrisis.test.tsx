// 1안 「수다 안에서 받기」(성호 11-15): 수다 중 🔴 응답이면 화면에 남아 서버 문장 + 연락처, 시간 종료는 지금처럼 넘어간다.
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { chatReplyAction } from '../../lib/chatBatch';
import type { SessionView } from '../../types';

vi.mock('../../state/auth', () => ({ useAuth: () => ({ me: null }), useMeOptional: () => null }));
const { CrisisInChat } = await import('./Chat');

describe('수다 응답 받기', () => {
  it('수다 중 crisis → 화면에 남음, 시간 종료(wrap) → 지금처럼 넘어감, 떠난 뒤 온 crisis → 위기 화면으로', () => {
    expect(chatReplyAction('chat', false)).toBe('reply');
    expect(chatReplyAction('crisis', false)).toBe('crisis-here');
    expect(chatReplyAction('wrap', false)).toBe('leave');
    expect(chatReplyAction('crisis', true)).toBe('leave');
  });
  const crisis = (at: string | null) => ({ id: 's1', phase: 'crisis', guardianRequestedAt: at }) as SessionView;
  it('수다 안 카드: 맨 위 「보호자께 도움 요청하기」 + 무엇이 가는지, 그 아래 1388·109·문자, 입력창 없음', () => {
    const html = renderToStaticMarkup(<MemoryRouter><CrisisInChat session={crisis(null)} /></MemoryRouter>);
    for (const h of ['tel:1388', 'tel:109', 'sms:1388']) expect(html).toContain(h);
    expect(html).toContain('보호자께 도움 요청하기');
    expect(html).toContain('많이 힘들어 보여요」만 가');
    expect(html).not.toContain('알렸어'); // 요청 전에는 「알렸어」라고 말하지 않는다(사실과 다름)
    expect(html.indexOf('보호자께 도움 요청하기')).toBeLessThan(html.indexOf('tel:1388'));
    expect(html).not.toContain('앞뒤');
    expect(html).not.toContain('<input');
  });
  it('이미 요청한 세션(새로고침 뒤 등)은 버튼 대신 「보호자께 알렸어」', () => {
    const html = renderToStaticMarkup(<MemoryRouter><CrisisInChat session={crisis('2026-11-15T07:00:00Z')} /></MemoryRouter>);
    expect(html).toContain('보호자께 알렸어');
    expect(html).not.toContain('보호자께 도움 요청하기');
    expect(html).toContain('tel:1388');
  });
  it('고정 문장을 화면 코드에 적지 않는다(서버 reply만)', async () => {
    const src = (await import('./Chat?raw')).default as string;
    expect(src).not.toContain('혼자 견디지 않아도');
    expect(src).not.toContain('말해 줘서 정말 고마워');
  });
});
