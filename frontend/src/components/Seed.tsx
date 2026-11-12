// 씨앗(재화) 표시: 민트 새싹 + 머스터드 테두리 칩. 돈 느낌이 나지 않게 "모아서 자라는 것"으로 표현한다.
import { Icon } from './Icon';

export function SeedChip({ n, onClick, plus }: { n: number; onClick?: () => void; plus?: boolean }) {
  const body = <><span className="seed-dot"><Icon name="seed" size={14} /></span><span className="num">{plus && n > 0 ? '+' : ''}{n}</span></>;
  return onClick
    ? <button className="seed-chip" onClick={onClick} aria-label={`씨앗 ${n}개, 상점 열기`}>{body}</button>
    : <span className="seed-chip" aria-label={`씨앗 ${n}개`}>{body}</span>;
}

/** 칭찬 도장(앱 재화) 칩 — 씨앗 칩과 같은 모양, 도장 아이콘. 옷 사는 데 쓴다(11-12 두 재화) */
export function StampChip({ n, onClick }: { n: number; onClick?: () => void }) {
  const body = <><span className="seed-dot seed-dot--stamp"><Icon name="stamp" size={14} /></span><span className="num">{n}</span></>;
  return onClick
    ? <button className="seed-chip seed-chip--stamp" onClick={onClick} aria-label={`칭찬 도장 ${n}개, 꾸미기 열기`}>{body}</button>
    : <span className="seed-chip seed-chip--stamp" aria-label={`칭찬 도장 ${n}개`}>{body}</span>;
}

/** 꾸미기 그림: public/mascot/{animal}/outfit-{id}.png · emote-{id}.png (없으면 자리표시) */
import { useState } from 'react';
import type { Animal, CosmeticKind } from '../types';
/** 실제로 있는 꾸미기 그림만 적는다(예 'horse/outfit-glasses'). 재하 GPT 전달본(eac004b) 그림 16종. 새 그림이 들어오면 여기에 추가.
 *  목록에 없으면 요청하지 않고 바로 자리표시 → 콘솔·네트워크 404가 생기지 않는다(11-12) */
export const COSMETIC_ART = new Set<string>([
  'horse/emote-best',
  'horse/emote-sleepy',
  'horse/emote-thanks',
  'horse/emote-thumbs',
  'horse/outfit-cape',
  'horse/outfit-glasses',
  'horse/outfit-raincoat',
  'horse/outfit-scarf',
  'monkey/emote-best',
  'monkey/emote-sleepy',
  'monkey/emote-thanks',
  'monkey/emote-thumbs',
  'monkey/outfit-cape',
  'monkey/outfit-glasses',
  'monkey/outfit-raincoat',
  'monkey/outfit-scarf',
]);
export const hasCosmeticArt = (animal: Animal, kind: CosmeticKind, id: string) => COSMETIC_ART.has(`${animal}/${kind}-${id}`);
export function CosmeticArt({ animal, kind, id, name, size = 72 }: { animal: Animal; kind: CosmeticKind; id: string; name: string; size?: number }) {
  const [failed, setBroken] = useState(false);
  const broken = failed || !hasCosmeticArt(animal, kind, id);
  const src = `${import.meta.env.BASE_URL}mascot/${animal}/${kind}-${id}.png`;
  return (
    <div className="cosmetic-art" style={{ width: size, height: size }}>
      {broken ? <span className="cosmetic-art__ph">{kind === 'outfit' ? '옷' : '이모티콘'}<br /><small>{name}</small></span>
        : <img key={src} src={src} alt="" onError={() => setBroken(true)} />}
    </div>
  );
}
