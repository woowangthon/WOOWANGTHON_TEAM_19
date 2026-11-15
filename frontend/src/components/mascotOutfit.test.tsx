// 산 옷이 모든 아이 화면에 유지(11-15 페이블 감사 C②): Mascot에 outfit·animal을 안 넘기면 로그인한 아이의 me.outfit을 입힌다
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactElement } from 'react';

let outfit: string | null = 'raincoat';
vi.mock('../state/auth', () => ({ useMeOptional: () => ({ outfit }) }));
vi.mock('../state/mentor', () => ({ useMentor: () => ({ animal: 'horse', say: (a: string) => a }) }));
const { Mascot, MentorSays } = await import('./Mascot');
const src = (el: ReactElement) => renderToStaticMarkup(el).match(/src="([^"]+)"/)?.[1] ?? '';

describe('Mascot — 입은 옷 유지', () => {
  it('약속·위기 같은 화면(outfit 안 넘김)도 입은 옷 그림', () => {
    outfit = 'raincoat';
    expect(src(<Mascot mood="calm" size={64} />)).toMatch(/horse\/outfit-raincoat-face\.png$/);
    expect(src(<Mascot mood="promise" size={160} />)).toMatch(/horse\/outfit-raincoat\.png$/);
    expect(src(<MentorSays text="안녕" />)).toMatch(/horse\/outfit-raincoat-face\.png$/); // 48px(작은 그림)도 상반신 옷 그림
  });
  it('다른 띠 미리보기(animal 넘김)는 옷 없이, 옷이 없으면 기본 그림', () => {
    expect(src(<Mascot animal="tiger" size={64} />)).toMatch(/tiger\/wave-face\.png$/);
    outfit = null;
    expect(src(<Mascot mood="calm" size={64} />)).toMatch(/horse\/calm-face\.png$/);
  });
});
