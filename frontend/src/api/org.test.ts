// 계정·학원·강의실·씨앗 규칙 테스트 (BRIEF "v0.4 회의 확정" · "v0.5")
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mockApi as api } from './mock';
import { DEMO_PASSWORD, SEED_RULES } from './org';
import { generateProblems } from './engine';
import { ymd } from '../lib/date';
import type { SignupBody } from '../types';

const as = (id: string) => api.demoLogin(id);
const AGREE = { terms: true, privacy: true, marketing: false };
const kid = (loginId: string, name = '하늘'): SignupBody => ({ role: 'student', loginId, password: 'abcd1234', name, grade: 5, agreements: AGREE });
const adult = (role: 'guardian' | 'teacher', loginId: string, name = '어른'): SignupBody => ({ role, loginId, password: 'abcd1234', name, email: `${loginId}@ex.com`, agreements: AGREE });
beforeEach(async () => { await api.resetDemo(); });

describe('로그인·가입·찾기', () => {
  it('TK-76: 같은 ms에 같은 역할로 두 명이 가입해도 id가 겹치지 않는다', async () => {
    const now = vi.spyOn(Date, 'now').mockReturnValue(1_800_000_000_000);
    try {
      const a = await api.signup(kid('same1')); await api.logout();
      const b = await api.signup(kid('same2')); await api.logout();
      expect(a.id).not.toBe(b.id);
    } finally { now.mockRestore(); }
  });

  it('아이디/비밀번호로 로그인, 틀리면 거절. 자동 로그인 꺼도 이번 실행에서는 로그인 상태', async () => {
    expect(await api.getMe()).toBeNull();
    await expect(api.login('jiwoo', 'wrong123')).rejects.toThrow('맞지 않아요');
    const me = await api.login('jiwoo', DEMO_PASSWORD, false);
    expect(me).toMatchObject({ role: 'student', loginId: 'jiwoo' });
    expect((await api.getMe())?.id).toBe('s1');
    await api.logout();
    expect(await api.getMe()).toBeNull();
  });

  it('가입: 필수 약관·아이디 규칙·중복·비밀번호 규칙·어른 이메일을 검사한다', async () => {
    await expect(api.signup({ ...kid('sky1'), agreements: { ...AGREE, privacy: false } })).rejects.toThrow('약관');
    await expect(api.signup(kid('1sky'))).rejects.toThrow('아이디');
    expect(await api.checkLoginId('jiwoo')).toBe(false);
    await expect(api.signup(kid('jiwoo'))).rejects.toThrow('이미');
    await expect(api.signup({ ...kid('sky1'), password: 'abcdefgh' })).rejects.toThrow('비밀번호');
    await expect(api.signup({ ...adult('guardian', 'mom7'), email: 'x' })).rejects.toThrow('이메일');
    const me = await api.signup(kid('sky1'));
    expect(me).toMatchObject({ role: 'student', loginId: 'sky1', restricted: true, academy: null, email: null });
    expect(me.linkCode).toMatch(/^[A-Z2-9]{6}$/);
    await api.logout();
    expect((await api.login('sky1', 'abcd1234')).name).toBe('하늘');
  });

  it('아이디 찾기는 이메일, 학생 비밀번호는 보호자가 재설정한다', async () => {
    expect(await api.findLoginId('mom@example.com')).toEqual(['jiw******']);
    expect(await api.requestPasswordReset('jiwoo_mom', 'mom@example.com')).toBe('sent');
    expect(await api.requestPasswordReset('jiwoo', '')).toBe('ask-guardian');
    await as('g1');
    await api.resetChildPassword('s1', 'newpass12');
    await api.logout();
    expect((await api.login('jiwoo', 'newpass12')).id).toBe('s1');
    await as('g1');
    await expect(api.resetChildPassword('s2', 'newpass12')).rejects.toThrow('연결된');
  });

  it('비밀번호 변경·프로필·알림 설정·탈퇴', async () => {
    await as('t1');
    await expect(api.changePassword('nope', 'abcd1234')).rejects.toThrow();
    await api.changePassword(DEMO_PASSWORD, 'teach9876');
    expect((await api.updateProfile({ name: '김쌤' })).name).toBe('김쌤');
    const me = await api.saveSettings({ studyReminder: null, learnDone: false, activity: false, marketing: true });
    expect(me.settings.marketing).toBe(true);
    await as('s3');
    await expect(api.deleteAccount('wrong')).rejects.toThrow();
    await api.deleteAccount(DEMO_PASSWORD);
    expect(await api.getMe()).toBeNull();
    await expect(api.login('seoyeon', DEMO_PASSWORD)).rejects.toThrow();
  });
});

describe('학생 ⇄ 보호자 연동과 학원 입장', () => {
  it('학생 혼자서는 학원에 못 들어간다(제한 모드) → 보호자가 동의하고 연결 → 한 명이 코드를 넣으면 둘 다 등록', async () => {
    await as('own1');
    const code = (await api.issueEntryCode()).entryCode!.code;
    expect(code).toMatch(/^\d{6}$/);
    const k = await api.signup(kid('sky2'));
    await expect(api.joinAcademy(code)).rejects.toThrow('보호자');
    await api.logout();
    await api.signup(adult('guardian', 'sky_mom'));
    await expect(api.linkWith(k.linkCode!)).rejects.toThrow('동의');
    const linked = await api.linkWith(k.linkCode!, true);
    expect(linked.linked[0]).toMatchObject({ id: k.id, role: 'student' });
    expect((await api.joinAcademy(code)).academy?.name).toBe('우왕수학학원');
    await as(k.id);
    expect(await api.getMe()).toMatchObject({ restricted: false, academy: { name: '우왕수학학원' } });
    expect((await api.getNotices()).some((n) => n.text.includes('연결'))).toBe(true);
  });

  it('학생이 먼저 보호자 코드를 넣으면 "동의 대기" → 보호자가 동의해야 연결된다', async () => {
    const mom = await api.signup(adult('guardian', 'mom8'));
    await api.logout();
    const k = await api.signup(kid('star8', '별'));
    expect(await api.linkWith(mom.linkCode!)).toMatchObject({ restricted: true, pendingLinks: [{ id: mom.id }] });
    await as(mom.id);
    expect((await api.getMe())!.pendingLinks[0].id).toBe(k.id);
    await expect(api.confirmLink(k.id, false)).rejects.toThrow();
    await api.confirmLink(k.id, true);
    await as(k.id);
    expect((await api.getMe())!.restricted).toBe(false);
  });

  it('입장 코드는 10분이 지나면 쓸 수 없다', async () => {
    await as('own1');
    const code = (await api.issueEntryCode()).entryCode!.code;
    await api.logout();
    await api.signup(adult('guardian', 'mom9'));
    const realNow = Date.now;
    Date.now = () => realNow() + (SEED_RULES.entryCodeMin + 1) * 60_000;
    try { await expect(api.joinAcademy(code)).rejects.toThrow('시간'); } finally { Date.now = realNow; }
  });
});

describe('학습지도자 소속 · 학원 등록(원장)', () => {
  it('학습지도자로 가입 → 설정에서 학원 등록 신청 → 운영자 승인 → 그 사람이 원장 → 다른 지도자 소속 신청 → 원장 체크 승인 → 강의실', async () => {
    const owner = await api.signup(adult('teacher', 'star_owner', '정원장'));
    expect(owner.membership).toBeNull();
    await expect(api.applyAcademy({ orgType: '학원', academyName: '별빛학원', bizNo: '12345', ceo: '정원장', phone: '010', address: '' })).rejects.toThrow('사업자');
    const applied = await api.applyAcademy({ orgType: '학원', academyName: '별빛학원', bizNo: '111-22-33333', ceo: '정원장', phone: '010-0000-0000', address: '청주' });
    expect(applied.application?.status).toBe('심사 중');
    await expect(api.getOwnerDashboard()).rejects.toThrow('원장');

    await as('op');
    const serial = (await api.reviewApplication(applied.application!.id, '승인')).find((a) => a.id === applied.application!.id)!.serial!;
    expect(serial).toMatch(/^[A-Z2-9]{4}-[A-Z2-9]{4}$/);
    await as(owner.id);
    expect((await api.getMe())!.membership).toMatchObject({ name: '별빛학원', isOwner: true, status: '승인됨' });

    await api.logout();
    const t = await api.signup(adult('teacher', 'han_t', '한쌤'));
    await expect(api.requestMembership('XXXX-XXXX')).rejects.toThrow('일련번호');
    expect((await api.requestMembership(serial.toLowerCase())).membership).toMatchObject({ status: '승인 대기', isOwner: false });
    await expect(api.createClassroom('5학년반', '')).rejects.toThrow('승인');
    await expect(api.getOwnerDashboard()).rejects.toThrow('원장');

    await as(owner.id);
    expect((await api.getOwnerDashboard()).pendingTeachers.map((x) => x.id)).toEqual([t.id]);
    await api.approveTeachers([t.id]);
    await as(t.id);
    expect((await api.createClassroom('5학년반', '소수의 덧셈')).classrooms[0]).toMatchObject({ name: '5학년반', members: [] });
    expect((await api.getNotices())[0].text).toContain('승인');
  });

  it('반려는 사유가 필요하고, 신청자에게 알린다', async () => {
    await as('op');
    await expect(api.reviewApplication('app2', '반려')).rejects.toThrow('사유');
    await api.reviewApplication('app2', '반려', '사업자등록증 확인 불가');
    await as('own2');
    expect((await api.getMe())!.application).toMatchObject({ status: '반려', rejectReason: '사업자등록증 확인 불가' });
  });

  it('강의실은 초대(학생 수락) 또는 참여 요청(지도자 수락)으로 들어간다', async () => {
    await as('t1');
    let tc = await api.getTeacherClasses();
    const deep = tc.classrooms.find((c) => c.name === '5학년 심화반')!;
    expect(deep.requests.map((r) => r.id)).toEqual(['s4']);
    tc = await api.answerRequest(deep.id, 's4', true);
    expect(tc.classrooms.find((c) => c.id === deep.id)!.members.map((m) => m.id)).toEqual(['s4']);
    await api.inviteStudent(deep.id, 's1');
    await as('s1');
    expect((await api.getStudentClasses()).invites.map((c) => c.id)).toEqual([deep.id]);
    expect((await api.acceptInvite(deep.id, true)).joined.map((c) => c.id)).toContain(deep.id);
  });
});

describe('씨앗', () => {
  it('학습 완료 씨앗 +3(하루 1번) · 보호자 도장 → 칭찬 도장 +1(하루 1번, 씨앗과 따로) · 지도자 칭찬 씨앗(1~5, 하루 10)', async () => {
    await as('s1');
    const start = (await api.getWallet()).balance;
    const startStamps = (await api.getWallet()).stamps!;
    await api.acceptPromise();
    const s = await api.startSession('중급');
    for (const [n, d] of generateProblems('분수의 덧셈', '중급', ymd()).map((p) => p.answer)) {
      const p = await api.getProblem(s.id); await api.submitAnswer(s.id, p!.id, n, d);
    }
    expect((await api.getWallet()).balance).toBe(start + SEED_RULES.studyDone);
    expect((await api.getStudentHome()).earnedToday).toBe(SEED_RULES.studyDone);
    await as('g1');
    await api.stamp();
    await expect(api.stamp()).rejects.toThrow('이미');
    await as('t1');
    await expect(api.grantSeeds('s1', 6, '칭찬')).rejects.toThrow();
    await expect(api.grantSeeds('s1', 3, '')).rejects.toThrow('이유');
    await api.grantSeeds('s1', 5, '단원평가 100점');
    await api.grantSeeds('s1', 5, '친구를 도와줬어요');
    await expect(api.grantSeeds('s1', 1, '성실')).rejects.toThrow('하루');
    await expect(api.grantSeeds('s4', 1, '칭찬')).rejects.toThrow('내 강의실');
    const row = (await api.getSeedBoard()).students.find((x) => x.id === 's1')!;
    expect(row.balance).toBe(start + 3 + 10); // 씨앗: 학습 완료 + 칭찬
    expect(row.stamps).toBe(startStamps + SEED_RULES.guardianStamp); // 도장은 따로
  });

  it('학원 상품 구매 → 씨앗 차감·교환 요청 → 지도자가 전달 체크. 숨긴 상품은 안 보인다', async () => {
    await as('s1');
    const shop = await api.getStudentShop();
    expect(shop.academyItems.map((i) => i.name)).not.toContain('겨울방학 특별 선물');
    const after = await api.buyAcademyItem('i2');
    expect(after.balance).toBe(shop.balance - 15);
    expect(after.orders[0]).toMatchObject({ itemName: '자리 고르기권', status: '교환 요청' });
    await expect(api.buyAcademyItem('i4')).rejects.toThrow();
    await expect(api.buyAcademyItem('i3')).rejects.toThrow('모자라');
    await as('t1');
    const b = await api.getSeedBoard();
    const mine = b.orders.find((o) => o.itemName === '자리 고르기권')!;
    expect((await api.deliverOrder(mine.id)).orders.find((o) => o.id === mine.id)!.status).toBe('전달 완료');
    await api.saveShopItem({ ...b.items.find((i) => i.id === 'i4')!, visible: true });
    await as('s1');
    expect((await api.getStudentShop()).academyItems.map((i) => i.name)).toContain('겨울방학 특별 선물');
  });

  it('꾸미기: 사면 바로 입고, 이미 산 건 다시 못 산다', async () => {
    await as('s1');
    const before = await api.getStudentShop();
    const s = await api.buyCosmetic('thumbs');
    expect(s.cosmetics.find((c) => c.id === 'thumbs')!.owned).toBe(true);
    expect(s.stamps).toBe(before.stamps! - 1); // 꾸미기는 칭찬 도장으로
    expect(s.balance).toBe(before.balance); // 씨앗은 그대로
    await expect(api.buyCosmetic('thumbs')).rejects.toThrow('이미');
    await api.equipOutfit('glasses');
    expect((await api.getMe())!.outfit).toBe('glasses');
    await expect(api.equipOutfit('cape')).rejects.toThrow();
  });
});
