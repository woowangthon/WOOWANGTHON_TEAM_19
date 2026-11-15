// 멘토 캐릭터 그림.
// 파일: public/mascot/{animal}/{mood}.png(전신) · {mood}-face.png(상반신) · {mood}-avatar.png(머리)
// 크기에 맞춰 자동으로 고른다: 56px 이하 → 머리, 96px 이하 → 상반신, 그보다 크면 → 전신
// 그림체가 바뀌어도 같은 이름으로 파일만 교체하면 된다.
import { useState } from 'react';
import { useMentor } from '../state/mentor';
import { useMeOptional } from '../state/auth';
import { FULL_ART_ANIMALS, type Animal } from '../types';
import { outfitArtSrc } from './Seed';

export type Mood = 'wave' | 'think' | 'cheer' | 'promise' | 'calm' | 'read';
type Variant = 'avatar' | 'face' | 'full';

const pick = (size: number): Variant => (size <= 56 ? 'avatar' : size <= 96 ? 'face' : 'full');

/**
 * outfit: 입은 옷 id. 옷 그림은 인사(wave) 자세만 만든다 → public/mascot/{animal}/outfit-{id}.png · outfit-{id}-face.png
 * 옷 그림 파일이 아직 없으면 기본 그림을 쓴다(오류 없이).
 * outfit도 animal도 안 넘기면 = 「내 멘토」 → 로그인한 아이가 입은 옷(me.outfit)을 쓴다. 산 옷이 모든 아이 화면에 유지되게(11-15 페이블 감사 C②, 성호)
 * 작은 머리 그림(56px 이하)은 옷 파일이 없어서 옷을 입었으면 상반신 옷 그림을 쓴다.
 */
export function Mascot({ mood = 'wave', size = 72, animal, variant, outfit }: { mood?: Mood; size?: number; animal?: Animal; variant?: Variant; outfit?: string | null }) {
  const ctx = useMentor();
  const me = useMeOptional();
  const a = animal ?? ctx.animal;
  const v = variant ?? pick(size);
  const wear = outfit !== undefined ? outfit : animal ? null : (me?.outfit ?? null);
  const [broken, setBroken] = useState(false);
  const [outfitBroken, setOutfitBroken] = useState<string | null>(null);
  const base = `${import.meta.env.BASE_URL}mascot/${a}/`;
  // 새 띠 10종은 인사(wave) 그림만 있다 → 다른 표정은 인사 그림으로(없는 파일을 요청하지 않게, 11-13)
  const m: Mood = FULL_ART_ANIMALS.includes(a) ? mood : 'wave';
  const plain = `${base}${m}${v === 'full' ? '' : '-' + v}.png`;
  // 옷 그림은 그 크기(전신·얼굴) 파일이 있을 때만 요청(없으면 맨 캐릭터) — 404 없이(11-12, 크기별 11-14)
  const dressed = outfitArtSrc(base, a, wear, v === 'avatar' ? 'face' : v);
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
