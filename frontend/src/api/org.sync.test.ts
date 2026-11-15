// 학원 자동 등록(연결된 한 쌍까지만)·형제·학원 충돌 규칙 테스트 (org.ts syncAcademy 계열)
import { beforeEach, describe, expect, it } from 'vitest';
import { mockApi as api } from './mock';
import type { SignupBody } from '../types';

const as = (id: string) => api.demoLogin(id);
const AGREE = { terms: true, privacy: true, marketing: false };
const kidBody = (loginId: string): SignupBody => ({ role: 'student', loginId, password: 'abcd1234', name: loginId, grade: 5, agreements: AGREE });
const momBody = (loginId: string): SignupBody => ({ role: 'guardian', loginId, password: 'abcd1234', name: loginId, email: `${loginId}@ex.com`, agreements: AGREE });
async function signupKid(loginId: string) { const me = await api.signup(kidBody(loginId)); await api.logout(); return me; }
async function signupMom(loginId: string) { const me = await api.signup(momBody(loginId)); await api.logout(); return me; }

/** 우왕수학학원(a1) 입장 코드 */
async function codeA() { await as('own1'); const c = (await api.issueEntryCode()).entryCode!.code; await api.logout(); return c; }
/** 새싹영어학원(심사 중인 app2)을 승인해 두 번째 학원을 만들고 입장 코드를 받는다 */
async function codeB() {
  await as('op'); await api.reviewApplication('app2', '승인');
  await as('own2'); const c = (await api.issueEntryCode()).entryCode!.code; await api.logout(); return c;
}
/** 보호자가 아이 코드로 동의 연결 */
async function link(momId: string, kidCode: string) { await as(momId); await api.linkWith(kidCode, true); await api.logout(); }
async function academyOf(id: string) { await as(id); const me = await api.getMe(); await api.logout(); return me!.academy?.name ?? null; }
async function noticesOf(id: string) { await as(id); const n = (await api.getNotices()).map((x) => x.text); await api.logout(); return n; }

beforeEach(async () => { await api.resetDemo(); });

describe('한 쌍(보호자-아이 1명)', () => {
  it('아이가 코드를 넣으면 보호자도 등록된다', async () => {
    const code = await codeA();
    const k = await signupKid('pairkid1');
    const m = await signupMom('pairmom1');
    await link(m.id, k.linkCode!);
    await as(k.id);
    expect((await api.joinAcademy(code)).academy?.name).toBe('우왕수학학원');
    expect(await academyOf(m.id)).toBe('우왕수학학원');
  });

  it('보호자가 코드를 넣으면 아이(1명)도 등록된다', async () => {
    const code = await codeA();
    const k = await signupKid('pairkid2');
    const m = await signupMom('pairmom2');
    await link(m.id, k.linkCode!);
    await as(m.id);
    await api.joinAcademy(code);
    expect(await academyOf(k.id)).toBe('우왕수학학원');
  });
});

describe('형제: 보호자를 거쳐 다른 아이로 넘어가지 않는다', () => {
  it('학원 있는 아이와 연결돼도 보호자만 등록되고 형제는 그대로', async () => {
    const sib = await signupKid('sibkid1');
    const m = await signupMom('sibmom1');
    await link(m.id, sib.linkCode!);
    // 이민준(s2)은 우왕수학학원 학생
    await link(m.id, 'MJ8Q2X');
    expect(await academyOf(m.id)).toBe('우왕수학학원');
    expect(await academyOf(sib.id)).toBeNull();
  });

  it('아이 하나가 코드를 넣어도 보호자만 같이 등록되고 형제는 그대로', async () => {
    const code = await codeA();
    const k1 = await signupKid('sibkid2');
    const k2 = await signupKid('sibkid3');
    const m = await signupMom('sibmom2');
    await link(m.id, k1.linkCode!);
    await link(m.id, k2.linkCode!);
    await as(k1.id);
    await api.joinAcademy(code);
    expect(await academyOf(m.id)).toBe('우왕수학학원');
    expect(await academyOf(k2.id)).toBeNull();
  });

  it('아이가 둘인 보호자가 코드를 넣으면 아이들은 자동 등록 안 되고 보호자에게 안내', async () => {
    const code = await codeA();
    const k1 = await signupKid('sibkid4');
    const k2 = await signupKid('sibkid5');
    const m = await signupMom('sibmom3');
    await link(m.id, k1.linkCode!);
    await link(m.id, k2.linkCode!);
    await as(m.id);
    expect((await api.joinAcademy(code)).academy?.name).toBe('우왕수학학원');
    expect(await academyOf(k1.id)).toBeNull();
    expect(await academyOf(k2.id)).toBeNull();
    expect((await noticesOf(m.id)).some((t) => t.includes('아이 계정에서 학원 코드'))).toBe(true);
  });
});

describe('학원 충돌: 덮어쓰지 않고 두 사람에게 알린다', () => {
  it('보호자가 B학원일 때 아이가 A학원 코드를 넣으면 보호자는 B 그대로 + 둘 다 알림', async () => {
    const a = await codeA();
    const b = await codeB();
    const k1 = await signupKid('cfkid1');
    const k2 = await signupKid('cfkid2');
    const m = await signupMom('cfmom1');
    await link(m.id, k1.linkCode!);
    await link(m.id, k2.linkCode!);
    await as(m.id); await api.joinAcademy(b); await api.logout(); // 아이 둘 → 보호자만 B
    await as(k1.id);
    expect((await api.joinAcademy(a)).academy?.name).toBe('우왕수학학원');
    expect(await academyOf(m.id)).toBe('새싹영어학원');
    expect((await noticesOf(m.id)).some((t) => t.includes('새싹영어학원') && t.includes('자동으로'))).toBe(true);
    expect((await noticesOf(k1.id)).some((t) => t.includes('새싹영어학원') && t.includes('자동으로'))).toBe(true);
  });

  it('A학원 아이와 B학원 보호자가 연결되면 둘 다 그대로 + 둘 다 알림 (보호자가 연결 / 학생 요청 수락)', async () => {
    const b = await codeB();
    const m = await signupMom('cfmom2');
    await as(m.id); await api.joinAcademy(b);
    await api.linkWith('MJ8Q2X', true); // 이민준(s2, 우왕수학학원)
    await api.logout();
    expect(await academyOf(m.id)).toBe('새싹영어학원');
    expect(await academyOf('s2')).toBe('우왕수학학원');
    expect((await noticesOf(m.id)).some((t) => t.includes('자동으로'))).toBe(true);
    expect((await noticesOf('s2')).some((t) => t.includes('자동으로'))).toBe(true);

    // 학생이 먼저 요청 → 보호자 수락
    await as('s3'); await api.linkWith(m.linkCode!); await api.logout(); // 박서연(s3, 우왕수학학원)
    await as(m.id); await api.confirmLink('s3', true); await api.logout();
    expect(await academyOf(m.id)).toBe('새싹영어학원');
    expect(await academyOf('s3')).toBe('우왕수학학원');
    expect((await noticesOf('s3')).some((t) => t.includes('자동으로'))).toBe(true);
  });

  it('같은 학원이면 아무 알림도 없다', async () => {
    const code = await codeA();
    const m = await signupMom('samemom');
    await as(m.id); await api.joinAcademy(code); await api.logout();
    await link(m.id, 'MJ8Q2X');
    expect((await noticesOf(m.id)).some((t) => t.includes('자동으로'))).toBe(false);
  });
});
