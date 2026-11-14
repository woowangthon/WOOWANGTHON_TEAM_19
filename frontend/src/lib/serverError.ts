// D11: 서버가 문구 없이 오류만 줄 때 보이는 한 줄 — 무엇을 하면 되는지까지(아이는 반말, 어른은 존댓말). 끝의 숫자는 문의할 때 쓰라고 남긴다
export function serverErrorText(status: number, kid: boolean): string {
  return kid
    ? `잠깐 문제가 생겼어. 조금 뒤에 다시 눌러 줘. 계속 안 되면 선생님이나 보호자께 알려 줘. (${status})`
    : `잠시 문제가 생겼어요. 잠시 뒤 다시 눌러 주세요. 계속되면 화면을 새로고침해 주세요. (${status})`;
}
