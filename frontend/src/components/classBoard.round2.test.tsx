// 강의실 공지·숙제·원장 기본값(dev round2 #8·#12) — org http 모드(서버 /class-live)
// #8 올리기·지우기·기본값 저장이 실패하면(liveAct) 화면에 오류 한 줄 · #12 아이가 둘 이상이면 숙제 줄마다 아이 이름
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import type { Me } from '../types';

const FAIL = '저장하지 못했어요. 잠시 뒤 다시 눌러 주세요. (503)';
let failing = true;
vi.mock('../api/http', async (orig) => ({
  ...(await orig<typeof import('../api/http')>()),
  ORG_HTTP: true,
  classLiveCall: vi.fn(async () => { if (failing) throw new Error(FAIL); return { sessions: {}, defaults: {}, places: {}, posts: [] }; }),
}));
let me: Me | null = null;
vi.mock('../state/auth', () => ({ useAuth: () => ({ me }), useMeOptional: () => null }));

const cs = await import('../lib/classSession');
const { TeacherBoard, GuardianHomeworkCard } = await import('./ClassBoard');
const { ClassDefaultsCard } = await import('../screens/owner/Owner');
const html = (el: ReactNode) => renderToStaticMarkup(<MemoryRouter>{el}</MemoryRouter>);
const room = { id: 'c1', name: '5학년 A반', teacherName: '김선생', plan: '', members: [{ id: 'k1', name: '지우' }] } as never;

afterEach(() => { vi.unstubAllGlobals(); failing = true; });

describe('#8 강의실 쓰기 실패를 보인다', () => {
  it('liveAct 실패 시 TeacherBoard에 오류 문구', async () => {
    await cs.liveAct('POST', '/class-live/c1/posts', { kind: 'notice', title: '공지' });
    expect(cs.liveError).toBe(FAIL);
    expect(html(<TeacherBoard room={room} />)).toContain(FAIL);
  });
  it('Owner 기본값 저장 실패 시 오류 문구', async () => {
    cs.saveDefaults({ ...cs.DEFAULTS, games: false });
    await vi.waitFor(() => expect(cs.liveError).toBe(FAIL));
    expect(html(<ClassDefaultsCard />)).toContain(FAIL);
  });
  it('실패하면 다시 읽기도 실패해도 화면을 다시 그리게 알린다', async () => {
    const win = new EventTarget();
    vi.stubGlobal('window', win);
    const on = vi.fn();
    win.addEventListener(cs.SESSION_EVENT, on);
    await cs.liveAct('DELETE', '/class-live/posts/p1');
    expect(on).toHaveBeenCalled();
  });
  it('다음 쓰기가 성공하면 오류 문구가 사라진다', async () => {
    failing = false;
    await cs.liveAct('DELETE', '/class-live/posts/p1');
    expect(cs.liveError).toBeNull();
    expect(html(<TeacherBoard room={room} />)).not.toContain(FAIL);
  });
});

describe('#12 보호자 숙제 카드 아이 이름', () => {
  const post = (id: string, kid: { id: string; name: string }) => ({
    id, classId: 'c1', className: '5학년 A반', teacherName: '김선생', kind: 'homework', title: `숙제 ${id}`, body: '',
    due: '2999-01-01', at: Date.now(), members: [kid], done: [],
  });
  const kids = [{ id: 'k1', name: '지우' }, { id: 'k2', name: '새봄' }];
  const guardian = (linked: { id: string; name: string }[]) => ({ id: 'g1', role: 'guardian', loginId: 'g', name: '보호자', linked }) as unknown as Me;
  it('아이 둘 연결 시 「아직」 줄에 아이 이름', () => {
    me = guardian(kids);
    cs.setRemoteLive({ sessions: {}, defaults: cs.DEFAULTS, places: {}, posts: [post('a', kids[0]), post('b', kids[1])] });
    const m = html(<GuardianHomeworkCard />);
    expect(m).toContain('지우 · 아직');
    expect(m).toContain('새봄 · 아직');
  });
  it('아이 하나면 지금과 같음', () => {
    me = guardian([kids[0]]);
    cs.setRemoteLive({ sessions: {}, defaults: cs.DEFAULTS, places: {}, posts: [post('a', kids[0])] });
    const m = html(<GuardianHomeworkCard />);
    expect(m).toContain('>아직이에요<');
    expect(m).not.toContain('지우 · 아직');
  });
});
