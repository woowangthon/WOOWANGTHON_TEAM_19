// 위기 화면(dev round2 #0): 수업 잠금 화면의 도움 링크(/student/crisis)는 단계와 상관없이 연락처를 보여야 한다.
// 「보호자께 도움 요청하기」는 세션이 crisis 단계일 때만, 이미 요청했으면 「보호자께 알렸어」(11-15 성호).
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
const render = (phase: SessionView['phase'] | null, requestedAt: string | null = null) => {
  session = phase ? ({ id: 's1', phase, guardianRequestedAt: requestedAt } as SessionView) : null;
  return renderToStaticMarkup(<MemoryRouter><StudentCrisis /></MemoryRouter>);
};
const ASK = '보호자께 도움 요청하기';
const NOTIFIED = '보호자께 알렸어';

describe('위기 화면은 단계와 상관없이 열린다', () => {
  it('잠금 화면 도움 링크 → 1388·109 보임(chat 단계 + 수업 잠금)', () => {
    const html = render('chat');
    expect(html).toContain('tel:1388');
    expect(html).toContain('tel:109');
  });
  it('세션이 없어도(solve·done·없음) 연락처가 보인다', () => {
    for (const p of ['solve', 'done', null] as const) expect(render(p)).toContain('tel:1388');
  });
  it('crisis 아닌 단계에서는 요청 버튼·알림 문구 없음', () => {
    for (const p of ['chat', null] as const) { expect(render(p)).not.toContain(ASK); expect(render(p)).not.toContain(NOTIFIED); }
  });
  it('crisis 단계: 요청 전에는 버튼(「알렸어」 없음), 요청 뒤에는 「알렸어」', () => {
    expect(render('crisis')).toContain(ASK);
    expect(render('crisis')).not.toContain(NOTIFIED);
    expect(render('crisis', '2026-11-15T07:00:00Z')).toContain(NOTIFIED);
    expect(render('crisis', '2026-11-15T07:00:00Z')).not.toContain(ASK);
  });
});
