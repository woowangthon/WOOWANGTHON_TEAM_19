// 설정 「처음 상태로 되돌리기」(명세 4.11-10, 성호 11-15): 심사용 고정 세트(me.resettable)에서만 보인다. 학생·보호자·선생님 모두
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import type { Me } from '../../types';

let me: Partial<Me> | null = null;
vi.mock('../../state/auth', () => ({ useAuth: () => ({ me, logout: async () => {} }), useRefreshMeOnMount: () => {}, homeFor: () => '/', useMeOptional: () => me }));
vi.mock('../../state/mentor', () => ({ useMentor: () => ({ say: (c: string) => c, animal: 'horse', setting: null }) }));
vi.mock('../../components/Frame', () => ({ Frame: ({ children }: { children: ReactNode }) => <div>{children}</div> }));

const { Settings } = await import('./Settings');
const html = () => renderToStaticMarkup(<MemoryRouter><Settings /></MemoryRouter>);
const base = { id: 'u1', name: '지우', loginId: 'jiwoo_judge1', email: null, grade: null, linkCode: null, linked: [], pendingLinks: [], academy: null, membership: null, application: null, restricted: false, outfit: null };

describe('처음 상태로 되돌리기', () => {
  for (const role of ['student', 'guardian', 'teacher'] as const) {
    it(`${role}: resettable이면 보이고, 아니면 없다`, () => {
      me = { ...base, role, resettable: true } as Partial<Me>;
      expect(html()).toContain('처음 상태로 되돌리기');
      me = { ...base, role, resettable: false } as Partial<Me>;
      expect(html()).not.toContain('처음 상태로 되돌리기');
      me = { ...base, role } as Partial<Me>; // 옛 서버(필드 없음)
      expect(html()).not.toContain('처음 상태로 되돌리기');
    });
  }
});
