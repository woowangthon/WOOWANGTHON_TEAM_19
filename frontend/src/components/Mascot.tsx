// 멘토 캐릭터 그림.
// 파일: public/mascot/{animal}/{mood}.png(전신) · {mood}-face.png(상반신) · {mood}-avatar.png(머리)
// 크기에 맞춰 자동으로 고른다: 56px 이하 → 머리, 96px 이하 → 상반신, 그보다 크면 → 전신
// 그림체가 바뀌어도 같은 이름으로 파일만 교체하면 된다.
import { useState } from 'react';
import { useMentor } from '../state/mentor';
import type { Animal } from '../types';

export type Mood = 'wave' | 'think' | 'cheer' | 'promise' | 'calm' | 'read';
type Variant = 'avatar' | 'face' | 'full';

const pick = (size: number): Variant => (size <= 56 ? 'avatar' : size <= 96 ? 'face' : 'full');

/**
 * outfit: 입은 옷 id. 옷 그림은 인사(wave) 자세만 만든다 → public/mascot/{animal}/outfit-{id}.png · outfit-{id}-face.png
 * 옷 그림 파일이 아직 없으면 기본 그림을 쓴다(오류 없이).
 */
export function Mascot({ mood = 'wave', size = 72, animal, variant, outfit }: { mood?: Mood; size?: number; animal?: Animal; variant?: Variant; outfit?: string | null }) {
  const ctx = useMentor();
  const a = animal ?? ctx.animal;
  const v = variant ?? pick(size);
  const [broken, setBroken] = useState(false);
  const [outfitBroken, setOutfitBroken] = useState<string | null>(null);
  const base = `${import.meta.env.BASE_URL}mascot/${a}/`;
  const plain = `${base}${mood}${v === 'full' ? '' : '-' + v}.png`;
  const dressed = outfit && v !== 'avatar' ? `${base}outfit-${outfit}${v === 'full' ? '' : '-' + v}.png` : null;
  const src = dressed && outfitBroken !== dressed ? dressed : plain;
  return (
    <div className={'mascot mascot--' + v} style={{ width: size, height: size }} aria-hidden>
      {broken ? <span className="mascot__fallback">멘토</span>
        : <img key={src} src={src} alt="" onError={() => (src === dressed ? setOutfitBroken(dressed) : setBroken(true))} />}
    </div>
  );
}

/** 캐릭터 + 말풍선 한 줄 */
export function MentorSays({ text, mood, size = 48, label }: { text: string; mood?: Mood; size?: number; label?: string }) {
  return (
    <div className="mentor">
      <Mascot mood={mood} size={size} />
      <div className="bubble">{label && <span className="bubble__label">{label}</span>}{text}</div>
    </div>
  );
}
