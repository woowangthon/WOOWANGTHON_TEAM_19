// 보호자 긴급 팝업(11-15 성호) — 새 🔴(긴급·미확인) 알림을 한 번만 띄운다. 띄운 알림 id는 이 기기에 남겨 같은 알림으로 다시 띄우지 않는다.
// 닫아도 확인한 것으로 치지 않는다(확인은 알림 화면의 「확인했어요」만).
import type { SafetyAlert } from '../types';

const key = (guardianId: string) => `ai-mentor-crisis-popup:${guardianId}`;

/** 아직 띄운 적 없는 긴급·미확인 알림 하나(없으면 null) */
export function pickPopup(alerts: SafetyAlert[] | null | undefined, shown: ReadonlySet<string>): SafetyAlert | null {
  return alerts?.find((a) => a.level === '긴급' && a.status === '미확인' && !shown.has(a.id)) ?? null;
}

export function loadShown(guardianId: string): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(key(guardianId)) ?? '[]') as string[]); } catch { return new Set(); }
}

export function saveShown(guardianId: string, shown: ReadonlySet<string>): void {
  try { localStorage.setItem(key(guardianId), JSON.stringify([...shown].slice(-50))); } catch { /* 저장 못 하면 이번 화면에서만 기억 */ }
}
