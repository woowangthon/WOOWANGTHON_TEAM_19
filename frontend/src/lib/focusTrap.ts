// 시트 포커스 가두기(dev round3 #23): Tab/Shift+Tab이 시트 안에서만 돈다. 요소는 누를 때마다 다시 찾는다(disabled·숨김 빼고)
export const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** n개 중 지금 cur(시트 밖이면 -1)에서 다음 포커스 자리. 하나도 없으면 -1 */
export function nextFocusIndex(n: number, cur: number, back: boolean): number {
  if (n <= 0) return -1;
  if (cur < 0) return back ? n - 1 : 0;
  return back ? (cur - 1 + n) % n : (cur + 1) % n;
}

/** 시트 안 Tab 처리: 포커스할 수 있는 요소 사이를 돈다. 없으면 시트 자체에 */
export function trapTab(root: HTMLElement, e: KeyboardEvent) {
  if (e.key !== 'Tab') return;
  const els = [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null || el === document.activeElement);
  e.preventDefault();
  const i = nextFocusIndex(els.length, els.indexOf(document.activeElement as HTMLElement), e.shiftKey);
  if (i < 0) root.focus(); else els[i].focus();
}
