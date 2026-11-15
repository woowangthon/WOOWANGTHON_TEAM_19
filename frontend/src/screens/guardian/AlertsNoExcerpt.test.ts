// v0.8(성호 11-15): 보호자 화면은 아이가 한 말(발췌)을 보이지 않는다 — 서버가 excerpt를 보내도 화면이 쓰지 않는다
import { describe, expect, it } from 'vitest';

describe('보호자 🔴 알림에 발췌 없음', () => {
  it('알림 화면·긴급 팝업이 excerpt를 읽지 않는다', async () => {
    const alerts = (await import('./Alerts?raw')).default as string;
    const popup = (await import('../../components/CrisisPopup?raw')).default as string;
    for (const src of [alerts, popup]) {
      expect(src).not.toMatch(/\.excerpt\b/);
      expect(src).not.toContain('앞뒤 일부');
    }
  });
});
