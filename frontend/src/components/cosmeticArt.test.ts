// 꾸미기 그림 목록·크기별 선택·「그림 준비 중」 문구 (명세 4.12 5-2-1, 성호 11-14)
import { describe, expect, it } from 'vitest';
import { COSMETIC_ART, hasCosmeticArt, missingArtLine, outfitArtSrc } from './Seed';

// 11-14 저장소에 실제로 있는 24파일(재하 GPT 전달본 eac004b). 목록을 만드는 함수와 따로 적은 고정 기대값
const NOW = ['horse', 'monkey'].flatMap((a) => [
  ...['best', 'sleepy', 'thanks', 'thumbs'].map((e) => `${a}/emote-${e}`),
  ...['cape', 'glasses', 'raincoat', 'scarf'].flatMap((o) => [`${a}/outfit-${o}`, `${a}/outfit-${o}-face`]),
]);

describe('꾸미기 그림 목록(빌드 때 폴더에서)', () => {
  it('지금 있는 24파일이 모두 목록에 있다', () => {
    expect(NOW).toHaveLength(24);
    for (const k of NOW) expect(COSMETIC_ART.has(k), k).toBe(true);
  });
  // 11-14 재하 6491956(GPT-049~053)으로 12종 옷 8벌·이모티콘 10개가 들어왔다 → 「있는 예」에 더하고,
  // 「없는 예」는 앞으로도 없을 이름으로(돼지 목도리·망토·옛 이모티콘 8장은 곧 들어온다 — 성호 11-14. 들어와도 이 테스트는 그대로)
  it('11-14 새 그림(12종 옷·이모티콘)도 목록에 있다', () => {
    for (const k of ['tiger/outfit-glasses', 'tiger/outfit-glasses-face', 'horse/outfit-hanbok', 'horse/outfit-cap-face', 'rat/emote-hello', 'pig/outfit-hanbok', 'pig/emote-congrats'])
      expect(COSMETIC_ART.has(k), k).toBe(true);
  });
  it('없는 그림은 목록에 없다', () => {
    for (const k of ['horse/outfit-unicorn', 'pig/outfit-unicorn-face', 'tiger/emote-nope', 'horse/wave', 'horse/outfit-glasses-avatar', 'cat/outfit-glasses'])
      expect(COSMETIC_ART.has(k), k).toBe(false);
  });
  it('hasCosmeticArt는 전신 그림 기준', () => {
    expect(hasCosmeticArt('horse', 'outfit', 'glasses')).toBe(true);
    expect(hasCosmeticArt('tiger', 'outfit', 'glasses')).toBe(true);
    expect(hasCosmeticArt('pig', 'outfit', 'unicorn')).toBe(false);
  });
});

describe('옷 입은 그림 고르기(크기별로 있는 것만)', () => {
  it('전신·얼굴 각각 있으면 그 파일', () => {
    expect(outfitArtSrc('/m/horse/', 'horse', 'glasses', 'full')).toBe('/m/horse/outfit-glasses.png');
    expect(outfitArtSrc('/m/horse/', 'horse', 'glasses', 'face')).toBe('/m/horse/outfit-glasses-face.png');
  });
  it('작은 아바타·옷 없음·그림 없는 띠·옷은 null(요청 안 함)', () => {
    expect(outfitArtSrc('/m/horse/', 'horse', 'glasses', 'avatar')).toBeNull();
    expect(outfitArtSrc('/m/horse/', 'horse', null, 'face')).toBeNull();
    expect(outfitArtSrc('/m/pig/', 'pig', 'unicorn', 'face')).toBeNull();
    expect(outfitArtSrc('/m/horse/', 'horse', 'unicorn', 'full')).toBeNull();
    expect(outfitArtSrc('/m/tiger/', 'tiger', 'glasses', 'face')).toBe('/m/tiger/outfit-glasses-face.png');
  });
  it('전신만 있고 얼굴이 없으면 얼굴은 null → 기본 얼굴(404 없음)', () => {
    const only = new Set(['horse/outfit-cap']);
    expect(outfitArtSrc('/m/horse/', 'horse', 'cap', 'full', only)).toBe('/m/horse/outfit-cap.png');
    expect(outfitArtSrc('/m/horse/', 'horse', 'cap', 'face', only)).toBeNull();
  });
});

describe('그림 없는 옷을 입었을 때 한 줄', () => {
  it('받침에 따라 은/는, 반말·존댓말', () => {
    expect(missingArtLine('색동 한복', false)).toBe('색동 한복은 아직 그림 준비 중이야');
    expect(missingArtLine('야구 모자', true)).toBe('야구 모자는 아직 그림 준비 중이에요');
  });
});
