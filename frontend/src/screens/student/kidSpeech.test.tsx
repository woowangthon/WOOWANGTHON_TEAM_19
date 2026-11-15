// 아이 화면 말투·수업 잠금(dev round2 #3·#4)
// #3 수업 잠금 중에는 「수다 할래」(학습 완료)·「수다로 갈까?」(풀기 시간 끝)를 끄고 한 줄 안내 — 잠금 중에 수다 10분이 흘러가지 않게
// #4 한쪽 말투로 고정돼 있던 문구를 say(반말, 존댓말)로
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import type { SessionView, StudentShop } from '../../types';

let polite = false;
let locked = false;
let asyncData: unknown = null;
const session = { id: 's1', phase: 'transition', streakDays: 3, solved: 5, total: 5, studyMin: 18, hintsUsed: 2, assisted: 2, timedOut: false } as unknown as SessionView;

vi.mock('../../state/mentor', () => ({
  useMentor: () => ({ say: (c: string, p: string) => (polite ? p : c), animal: 'horse', setting: null }),
}));
vi.mock('../../state/session', () => ({
  useSession: () => ({ session, ready: true, sync: () => {}, refresh: async () => session, reset: async () => null }),
  RequirePhase: ({ children }: { children: ReactNode }) => children,
}));
vi.mock('../../state/auth', () => ({ useAuth: () => ({ me: null, refresh: async () => null }), useMeOptional: () => null }));
vi.mock('../../components/ClassSession', () => ({ useClassLocked: () => locked }));
vi.mock('../../components/Frame', () => ({
  Frame: ({ header, actions, children }: { header?: ReactNode; actions?: ReactNode; children: ReactNode }) => <div>{header}<div data-actions="">{actions}</div>{children}</div>,
}));
vi.mock('../../lib/useAsync', () => ({ useAsync: () => ({ data: asyncData, setData: () => {}, error: null, loading: false, reload: () => {} }) }));

const { StudentDone } = await import('./Done');
const { TimeUpActions } = await import('./Solve');
const { StudentShop: Shop } = await import('./Shop');
const { upDownWinLine } = await import('./Games');
const { SetupSteps } = await import('./Today');

const html = (el: ReactNode) => renderToStaticMarkup(<MemoryRouter>{el}</MemoryRouter>);
/** 이름(글자)이 들어 있는 버튼 태그 하나 */
const button = (markup: string, label: string) => markup.match(new RegExp(`<button[^>]*>[^<]*${label}`))?.[0] ?? '';
const LOCK_NOTE = '수업 끝나고 수다할 수 있어';

describe('#3 수업 잠금 중 수다로 가는 버튼', () => {
  it('잠금 중 Done의 「수다 할래」 비활성 + 안내 한 줄', () => {
    locked = true; polite = false; asyncData = { restricted: false };
    const m = html(<StudentDone />);
    expect(button(m, '수다 할래')).toContain('disabled');
    expect(m).toContain(LOCK_NOTE);
  });
  it('잠금 중 Solve 시간 끝 「수다로 갈까?」 비활성 + 안내 한 줄(풀이 보기는 그대로)', () => {
    locked = true; polite = true;
    const m = html(<TimeUpActions busy={false} onSolution={() => {}} onChat={() => {}} />);
    expect(button(m, '수다로 갈까\\?')).toContain('disabled');
    expect(button(m, '풀이 같이 보기')).not.toContain('disabled');
    expect(m).toContain('수업 끝나고 수다할 수 있어요');
  });
  it('잠금 아닐 때는 그대로 켜짐', () => {
    locked = false; polite = false; asyncData = { restricted: false };
    const d = html(<StudentDone />);
    expect(button(d, '수다 할래')).not.toContain('disabled');
    expect(d).not.toContain(LOCK_NOTE);
    const s = html(<TimeUpActions busy={false} onSolution={() => {}} onChat={() => {}} />);
    expect(button(s, '수다로 갈까\\?')).not.toContain('disabled');
    expect(s).not.toContain(LOCK_NOTE);
  });
});

describe('#4 말투 짝', () => {
  const shop: StudentShop = { balance: 10, stamps: 2, academyItems: [], cosmetics: [], orders: [] };
  it('존댓말 아이 — 상점·게임·시작 준비 문구가 존댓말', () => {
    polite = true; locked = false; asyncData = shop;
    const m = html(<Shop />);
    expect(m).toContain('학원 상품을 살 수 있어요');
    expect(m).toContain('옷이랑 이모티콘을 살 수 있어요');
    expect(upDownWinLine(4, (c, p) => (polite ? p : c))).toBe('4번 만에 맞혔어요!');
    const setup = html(<SetupSteps linked={false} academy={false} inClass={false} code="AB12" />);
    expect(setup).toContain('내 코드 AB12를 보호자에게 알려 주세요');
  });
  it('반말 아이 — 같은 문구가 반말(지금과 같음)', () => {
    polite = false; asyncData = shop;
    const m = html(<Shop />);
    expect(m).toContain('학원 상품을 살 수 있어<');
    expect(m).toContain('옷이랑 이모티콘을 살 수 있어<');
    expect(upDownWinLine(4, (c, p) => (polite ? p : c))).toBe('4번 만에 맞혔어!');
    expect(html(<SetupSteps linked={false} academy={false} inClass={false} code="AB12" />)).toContain('내 코드 AB12를 보호자에게 알려 줘<');
  });
  it('반말 아이 — 학습 완료 assisted 문구가 반말', () => {
    polite = false; locked = false; asyncData = { restricted: false };
    const m = html(<StudentDone />);
    expect(m).toContain('2문제는 풀이를 같이 봤어<');
    polite = true;
    expect(html(<StudentDone />)).toContain('2문제는 풀이를 같이 봤어요');
  });
});
