// 학원 상품 사진(TK-97, 명세 4.12 5-2-2, 성호 11-14). 서버는 data URL 하나(JPG·PNG·WEBP, 512KB)를 받고 imagePath만 돌려준다.
import type { ShopItem } from '../types';

export const MAX_SIDE = 400;
export const MAX_UPLOAD = 512 * 1024;      // 서버 상한(줄인 결과)
export const MAX_SOURCE = 15 * 1024 * 1024; // 원본 상한 — 큰 폰 사진으로 탭이 죽지 않게(bb 11-14)

/** 긴 변을 max로(작으면 그대로) */
export function fitSize(w: number, h: number, max = MAX_SIDE): { w: number; h: number } {
  const s = Math.min(1, max / Math.max(w, h));
  return { w: Math.round(w * s), h: Math.round(h * s) };
}

/** 저장 본문: 사진을 안 건드렸으면(undefined) image 칸을 아예 빼서 서버가 그대로 두게, imagePath는 보내지 않는다 */
export function withImage<T extends Partial<ShopItem>>(item: T, image: string | undefined): Omit<T, 'imagePath'> & { image?: string } {
  const { imagePath: _drop, ...rest } = item; void _drop;
  return image === undefined ? rest : { ...rest, image };
}

/** 보일 주소: 서버 경로는 API 주소 뒤에, mock의 data URL은 그대로 */
export const shopImageSrc = (imagePath: string | null | undefined, base: string) =>
  !imagePath ? null : imagePath.startsWith('data:') ? imagePath : base + imagePath;

/** 브라우저에서 줄이기: 긴 변 400px, 흰 바탕(투명 PNG가 검게 나오지 않게) 위에 그려 JPEG 0.8. EXIF·위치 정보는 다시 그리며 빠진다 */
export async function resizeImage(file: File): Promise<string> {
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) throw new Error('사진은 JPG·PNG·WEBP 파일만 올릴 수 있어요.');
  if (file.size > MAX_SOURCE) throw new Error('사진이 너무 커요. 더 작은 사진을 골라 주세요.');
  const bmp = await createImageBitmap(file, { imageOrientation: 'from-image' }); // 폰 세로 사진 방향
  const { w, h } = fitSize(bmp.width, bmp.height);
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const ctx = c.getContext('2d')!;
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, w, h); ctx.drawImage(bmp, 0, 0, w, h); bmp.close();
  const url = c.toDataURL('image/jpeg', 0.8);
  if (url.length * 0.75 > MAX_UPLOAD) throw new Error('사진이 너무 커요. 더 작은 사진을 골라 주세요.');
  return url;
}
