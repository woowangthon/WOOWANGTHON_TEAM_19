import type { Fraction as F } from '../types';

export function FractionView({ value }: { value: F }) {
  return (
    <span className="fraction" aria-label={`${value[1]}분의 ${value[0]}`}>
      <span>{value[0]}</span>
      <span className="fraction__bar" />
      <span>{value[1]}</span>
    </span>
  );
}
