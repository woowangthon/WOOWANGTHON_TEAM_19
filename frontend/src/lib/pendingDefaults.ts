// 원장 수업 기본값 「보내는 중 값」(dev round3 #9, bb 검토 반영). 서버는 5칸 전체를 받는다 →
// 응답 전에 또 바꾸면 보내는 중 값 위에 덮어 전체를 보낸다. 마지막으로 보낸 요청(seq)의 응답이 왔을 때만 비우고, 실패하면 서버 값으로 되돌린다.
export class PendingDefaults<T extends object> {
  private value: T | null = null;
  private seq = 0;
  patch(server: T, p: Partial<T>): { seq: number; body: T } {
    const body = { ...(this.value ?? server), ...p } as T;
    this.value = body; this.seq += 1;
    return { seq: this.seq, body };
  }
  /** 응답 도착: 마지막 요청이면 비운다(앞 요청 응답이 늦게 와도 지금 값을 지우지 않음) */
  settle(seq: number) { if (seq === this.seq) this.value = null; }
  /** 실패: 마지막 요청이면 서버 값으로 되돌린다 */
  fail(seq: number) { if (seq === this.seq) this.value = null; }
  view(server: T): T { return this.value ?? server; }
}
