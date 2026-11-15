// 보호자 안전 알림 — 「확인했어요」 뒤 보이기 규칙(11-15 성호: 회색 「후속」 대신 확인 버튼). 화면에서 빼서 테스트한다.
import type { SafetyAlert } from '../types';

/** 위쪽 카드로 보일 것: 아직 안 본 것 + 확인은 했지만 닫지 않은 긴급(카드는 남고 「확인함」으로 바뀐다) */
export function topAlerts(list: SafetyAlert[]): SafetyAlert[] {
  return list.filter((a) => a.status === '미확인' || (a.level === '긴급' && a.status === '확인함'));
}

/** 「확인이 필요한 알림 n건」 — 미확인만 센다(확인한 긴급 카드는 남아도 수에서 빠진다) */
export function needsAckCount(list: SafetyAlert[]): number {
  return list.filter((a) => a.status === '미확인').length;
}

/** 서버가 준 확인 결과로 목록의 그 알림만 바꾼다 */
export function applyAck(list: SafetyAlert[], acked: SafetyAlert): SafetyAlert[] {
  return list.map((a) => (a.id === acked.id ? { ...a, ...acked } : a));
}
