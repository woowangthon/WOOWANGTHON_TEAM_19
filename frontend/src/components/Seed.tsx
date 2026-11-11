// 씨앗(재화) 표시: 민트 새싹 + 머스터드 테두리 칩. 돈 느낌이 나지 않게 "모아서 자라는 것"으로 표현한다.
import { Icon } from './Icon';

export function SeedChip({ n, onClick, plus }: { n: number; onClick?: () => void; plus?: boolean }) {
  const body = <><span className="seed-dot"><Icon name="seed" size={14} /></span><span className="num">{plus && n > 0 ? '+' : ''}{n}</span></>;
  return onClick
    ? <button className="seed-chip" onClick={onClick} aria-label={`씨앗 ${n}개, 상점 열기`}>{body}</button>
    : <span className="seed-chip" aria-label={`씨앗 ${n}개`}>{body}</span>;
}

/** 꾸미기 그림: public/mascot/{animal}/outfit-{id}.png · emote-{id}.png (없으면 자리표시) */
import { useState } from 'react';
import type { Animal, CosmeticKind } from '../types';
export function CosmeticArt({ animal, kind, id, name, size = 72 }: { animal: Animal; kind: CosmeticKind; id: string; name: string; size?: number }) {
  const [broken, setBroken] = useState(false);
  const src = `${import.meta.env.BASE_URL}mascot/${animal}/${kind}-${id}.png`;
  return (
    <div className="cosmetic-art" style={{ width: size, height: size }}>
      {broken ? <span className="cosmetic-art__ph">{kind === 'outfit' ? '옷' : '이모티콘'}<br /><small>{name}</small></span>
        : <img key={src} src={src} alt="" onError={() => setBroken(true)} />}
    </div>
  );
}
