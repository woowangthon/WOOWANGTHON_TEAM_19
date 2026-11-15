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
import { josa } from '../lib/josa';
/** 실제로 있는 꾸미기 그림 = 빌드 때 public/mascot 폴더에서 읽은 목록(예 'horse/outfit-glasses', 얼굴 크기 'horse/outfit-glasses-face').
 *  그림 파일만 넣으면 코드 수정 없이 나온다. 목록에 없으면 요청하지 않고 자리표시 → 404 없음(명세 4.12 5-2-1, 11-14) */
export const COSMETIC_ART: ReadonlySet<string> = new Set<string>(__COSMETIC_ART__);
export const hasCosmeticArt = (animal: Animal, kind: CosmeticKind, id: string) => COSMETIC_ART.has(`${animal}/${kind}-${id}`);
/** 옷 입은 캐릭터 그림 주소. 그 크기(전신·얼굴) 파일이 있을 때만, 작은 아바타엔 옷을 입히지 않는다 → 없으면 null(기본 그림) */
export function outfitArtSrc(base: string, animal: Animal, outfit: string | null | undefined, v: 'full' | 'face' | 'avatar', art: ReadonlySet<string> = COSMETIC_ART): string | null {
  if (!outfit || v === 'avatar') return null;
  const name = `outfit-${outfit}${v === 'full' ? '' : '-' + v}`;
  return art.has(`${animal}/${name}`) ? `${base}${name}.png` : null;
}
/** 그 띠에 입은 옷 그림이 없을 때 한 줄(사실대로, 명세 4.12 5-2-1) */
export const missingArtLine = (name: string, polite: boolean) => `${josa(name, '은', '는')} 아직 그림 준비 중${polite ? '이에요' : '이야'}`;
export function CosmeticArt({ animal, kind, id, name, size = 72 }: { animal: Animal; kind: CosmeticKind; id: string; name: string; size?: number }) {
  const [failed, setBroken] = useState(false);
  const broken = failed || !hasCosmeticArt(animal, kind, id);
  const src = `${import.meta.env.BASE_URL}mascot/${animal}/${kind}-${id}.png`;
  return (
    <div className="cosmetic-art" style={{ width: size, height: size }}>
      {broken ? <span className="cosmetic-art__ph" title={name}>그림<br />준비 중</span>
        : <img key={src} src={src} alt="" onError={() => setBroken(true)} />}
    </div>
  );
}
