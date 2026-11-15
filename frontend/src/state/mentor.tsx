// 학생이 고른 멘토(띠 동물·호칭·말투)를 모든 화면이 함께 쓰는 저장소.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api } from '../api';
import { load, save as store } from '../lib/storage';
import type { Animal, MentorSetting } from '../types';

const DEFAULT_ANIMAL: Animal = 'horse'; // 기본 동물은 팀 회의에서 확정 → 여기만 바꾸면 된다
// 11-14부터 서버가 띠(animal)·가진 띠를 저장한다(명세 4.12-5). 서버가 띠를 안 주면(옛 계정·mock) 이 기기 저장값을 쓴다
const ANIMAL_KEY = 'ai-mentor-animal';

interface MentorCtx {
  setting: MentorSetting | null;
  animal: Animal;
  /** 말투에 맞는 문장 고르기: say('안녕!', '안녕하세요!') */
  say: (casual: string, polite: string) => string;
  save: (s: MentorSetting) => Promise<void>;
  reload: () => Promise<void>;
  /** 띠 사기(도장) → 가진 띠가 늘어난 설정으로 바꿔 둔다 */
  buy: (a: Animal) => Promise<void>;
}
const Ctx = createContext<MentorCtx>({ setting: null, animal: DEFAULT_ANIMAL, say: (c) => c, save: async () => {}, reload: async () => {}, buy: async () => {} });

export function MentorProvider({ children }: { children: ReactNode }) {
  const [setting, setSetting] = useState<MentorSetting | null>(null);
  const reload = useCallback(async () => {
    const s = await api.getMentor().catch(() => null);
    setSetting(s && !s.animal ? { ...s, animal: load<Animal>(ANIMAL_KEY, DEFAULT_ANIMAL) } : s);
  }, []);
  useEffect(() => { reload(); }, [reload]);
  const save = useCallback(async (s: MentorSetting) => { await api.saveMentor(s); store(ANIMAL_KEY, s.animal); setSetting(s); }, []);
  const buy = useCallback(async (a: Animal) => { const r = await api.buyAnimal(a); setSetting((cur) => (cur ? { ...cur, ownedAnimals: r?.ownedAnimals ?? cur.ownedAnimals } : cur)); }, []);
  const say = useCallback((casual: string, polite: string) => (setting?.speech === '존댓말' ? polite : casual), [setting]);
  return <Ctx.Provider value={{ setting, animal: setting?.animal ?? DEFAULT_ANIMAL, say, save, reload, buy }}>{children}</Ctx.Provider>;
}
export const useMentor = () => useContext(Ctx);
