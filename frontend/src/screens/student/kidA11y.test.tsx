// 아이 화면 접근성(dev round2 #20·#22): 스크린리더가 채점 결과·새 힌트·힌트 점·입은 옷을 읽을 수 있게
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import type { Cosmetic, StudentShop } from '../../types';

let asyncData: unknown = null;
vi.mock('../../state/mentor', () => ({ useMentor: () => ({ say: (c: string) => c, animal: 'horse', setting: null }) }));
vi.mock('../../state/auth', () => ({ useAuth: () => ({ me: null, refresh: async () => null }), useMeOptional: () => null }));
vi.mock('../../lib/useAsync', () => ({ useAsync: () => ({ data: asyncData, setData: () => {}, error: null, loading: false, reload: () => {} }) }));

const { FeedbackTitle, HintDots, TalkArea } = await import('./Solve');
const { Wardrobe } = await import('./Character');
const html = (el: ReactNode) => renderToStaticMarkup(<MemoryRouter>{el}</MemoryRouter>);

describe('#20 같이 풀기 결과·힌트', () => {
  it('답 확인 결과 제목에 role=status', () => {
    expect(html(<FeedbackTitle text="좋아, 맞았어!" />)).toBe('<div class="feedback__title" role="status">좋아, 맞았어!</div>');
  });
  it('힌트 영역 aria-live=polite', () => {
    expect(html(<TalkArea><p>힌트 1</p></TalkArea>)).toMatch(/^<div[^>]*aria-live="polite"[^>]*><p>힌트 1<\/p><\/div>$/);
  });
  it('hint-dots role=img(받은 힌트 수를 이름으로)', () => {
    const m = html(<HintDots used={1} left={2} />);
    expect(m).toContain('role="img"');
    expect(m).toContain('aria-label="힌트 1개 사용"');
    expect(m.match(/<i/g)?.length).toBe(3);
  });
});

describe('#22 옷장 입은 옷', () => {
  const outfit = (id: string, equipped: boolean): Cosmetic => ({ id, kind: 'outfit', name: id === 'o1' ? '노란 우비' : '파란 모자', price: 3, owned: true, equipped } as Cosmetic);
  const shop = (list: Cosmetic[]): StudentShop => ({ balance: 0, stamps: 0, academyItems: [], cosmetics: list, orders: [] });
  const wardButtons = (m: string) => m.match(/<button class="ward[^"]*"[^>]*>.*?<\/button>/g) ?? [];

  it('입은 옷 버튼 aria-pressed=true와 「입는 중」 글자', () => {
    asyncData = shop([outfit('o1', true), outfit('o2', false)]);
    const b = wardButtons(html(<Wardrobe preview={false} animal="horse" />));
    const worn = b.find((x) => x.includes('노란 우비'))!;
    expect(worn).toContain('aria-pressed="true"');
    expect(worn).toContain('입는 중');
  });
  it('안 입은 옷은 aria-pressed=false, 기본 버튼은 아무것도 안 입었을 때만 true', () => {
    asyncData = shop([outfit('o1', true), outfit('o2', false)]);
    let b = wardButtons(html(<Wardrobe preview={false} animal="horse" />));
    expect(b.find((x) => x.includes('파란 모자'))).toContain('aria-pressed="false"');
    expect(b.find((x) => x.includes('파란 모자'))).not.toContain('입는 중');
    expect(b.find((x) => x.includes('기본'))).toContain('aria-pressed="false"');
    asyncData = shop([outfit('o1', false)]);
    b = wardButtons(html(<Wardrobe preview={false} animal="horse" />));
    expect(b.find((x) => x.includes('기본'))).toContain('aria-pressed="true"');
  });
});
