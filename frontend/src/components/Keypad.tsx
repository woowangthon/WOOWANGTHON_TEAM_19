// 숫자 키패드 0~9 + 지우기 (BRIEF: 엄지 영역에 주요 동작)
import { Icon } from './Icon';

export function Keypad({ onDigit, onDelete, disabled }: { onDigit: (d: number) => void; onDelete: () => void; disabled?: boolean }) {
  return (
    <div className="keypad">
      {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((k) => (
        <button key={k} className="key" disabled={disabled} onClick={() => onDigit(k)}>{k}</button>
      ))}
      <span aria-hidden />
      <button className="key" disabled={disabled} onClick={() => onDigit(0)}>0</button>
      <button className="key key--del" disabled={disabled} onClick={onDelete} aria-label="지우기"><Icon name="back" size={20} /></button>
    </div>
  );
}
