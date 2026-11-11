import type { Fraction as F } from '../types';

export function FractionView({ value }: { value: F | null | undefined }) {
  if (!value) return null; // 서버가 식을 두 분수로 나누지 못한 문제(null)는 그리지 않는다
  return (
    <span className="fraction" aria-label={`${value[1]}분의 ${value[0]}`}>
      <span>{value[0]}</span>
      <span className="fraction__bar" />
      <span>{value[1]}</span>
    </span>
  );
}
