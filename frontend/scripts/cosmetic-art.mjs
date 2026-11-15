// 꾸미기 그림 목록을 빌드할 때 폴더에서 읽는다(명세 4.12 5-2-1, 성호 11-14).
// public/mascot/{띠}/{outfit|emote}-{id}.png(얼굴 크기 -face 포함) → ['horse/outfit-glasses', 'horse/outfit-glasses-face', …]
// 재하가 그림 파일만 넣으면 코드 수정 없이 나온다. tsc 밖(.mjs)에 두는 이유: node:fs 타입(@types/node)이 이 프로젝트에 없어서.
// 개발 서버(npm run dev)는 켤 때 한 번 읽는다 → 그림을 넣은 뒤엔 dev를 다시 켠다.
import { existsSync, readdirSync } from 'node:fs';

const ART = /^(outfit|emote)-[a-z0-9]+(-face)?\.png$/;

/** @param {URL} dir public/mascot 폴더(끝에 / 있는 URL) */
export function listCosmeticArt(dir) {
  if (!existsSync(dir)) return [];
  const keys = [];
  for (const animal of readdirSync(dir, { withFileTypes: true })) {
    if (!animal.isDirectory()) continue;
    for (const f of readdirSync(new URL(`${animal.name}/`, dir))) {
      if (ART.test(f)) keys.push(`${animal.name}/${f.slice(0, -4)}`);
      // 리눅스(Vercel)는 대소문자를 가린다 → 대문자·.PNG 등은 목록에서 빠지니 말없이 빠지지 않게 알린다
      else if (/^(outfit|emote)-/i.test(f)) console.warn(`[cosmetic-art] 목록에서 뺌(소문자 outfit|emote-이름.png만): mascot/${animal.name}/${f}`);
    }
  }
  return keys.sort();
}
