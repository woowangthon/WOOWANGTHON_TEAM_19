// 학원 상품 사진(TK-97, 명세 4.12 5-2-2): 저장 본문의 image 칸·줄일 크기·보일 주소
import { describe, expect, it } from 'vitest';
import { fitSize, shopImageSrc, withImage } from './shopImage';

describe('상품 사진', () => {
  const item = { id: 'i1', name: '과자', price: 20, stock: null, visible: true, note: '', imagePath: '/shop/images/i1?v=3' };
  it('안 건드리면 image 칸 없음(서버가 사진 그대로), imagePath는 보내지 않음', () => {
    const b = withImage(item, undefined);
    expect('image' in b).toBe(false); expect('imagePath' in b).toBe(false);
  });
  it('빼기 = 빈 문자열, 새 사진 = data URL', () => {
    expect(withImage(item, '').image).toBe('');
    expect(withImage(item, 'data:image/jpeg;base64,AAA').image).toBe('data:image/jpeg;base64,AAA');
  });
  it('긴 변을 400으로(작으면 그대로)', () => {
    expect(fitSize(4000, 3000, 400)).toEqual({ w: 400, h: 300 });
    expect(fitSize(1080, 1920, 400)).toEqual({ w: 225, h: 400 });
    expect(fitSize(300, 200, 400)).toEqual({ w: 300, h: 200 });
  });
  it('보일 주소: 서버 경로는 API 주소 뒤에, data URL(mock)은 그대로, 없으면 null', () => {
    expect(shopImageSrc('/shop/images/i1?v=3', '/api/v1/compat')).toBe('/api/v1/compat/shop/images/i1?v=3');
    expect(shopImageSrc('data:image/jpeg;base64,AAA', '/api/v1/compat')).toBe('data:image/jpeg;base64,AAA');
    expect(shopImageSrc(null, '/x')).toBeNull();
  });
});
