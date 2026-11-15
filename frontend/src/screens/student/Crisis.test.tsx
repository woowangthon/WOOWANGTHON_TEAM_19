// 위기 화면(dev round2 #0): 수업 잠금 화면의 도움 링크(/student/crisis)는 단계와 상관없이 연락처를 보여야 한다.
// 「보호자께 … 힘들어 보인다고 알렸어」는 세션이 crisis 단계일 때만(알림을 실제로 보낸 때만) 보인다.
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import type { SessionView } from '../../types';

let session: SessionView | null = null;
vi.mock('../../state/session', () => ({
  useSession: () => ({ session, ready: true, sync: () => {}, refresh: async () => session }),
  RequirePhase: ({ phase, children }: { phase: string; children: unknown }) => (session?.phase === phase ? children : null),
}));
vi.mock('../../state/auth', () => ({ useAuth: () => ({ me: null }), useMeOptional: () => null }));

const { StudentCrisis } = await import('./Crisis');
const render = (phase: SessionView['phase'] | null) => {
  session = phase ? ({ id: 's1', phase } as SessionView) : null;
  return renderToStaticMarkup(<MemoryRouter><StudentCrisis /></MemoryRouter>);
};
const NOTIFIED = '힘들어 보인다고 알렸어';

describe('위기 화면은 단계와 상관없이 열린다', () => {
  it('잠금 화면 도움 링크 → 1388·109 보임(chat 단계 + 수업 잠금)', () => {
    const html = render('chat');
    expect(html).toContain('tel:1388');
    expect(html).toContain('tel:109');
  });
  it('세션이 없어도(solve·done·없음) 연락처가 보인다', () => {
    for (const p of ['solve', 'done', null] as const) expect(render(p)).toContain('tel:1388');
  });
  it('crisis 아닌 단계에서는 보호자 알림 문구 없음', () => {
    expect(render('chat')).not.toContain(NOTIFIED);
    expect(render(null)).not.toContain(NOTIFIED);
  });
  it('crisis 단계에서는 보호자 알림 문구 있음', () => {
    expect(render('crisis')).toContain(NOTIFIED);
  });
});
