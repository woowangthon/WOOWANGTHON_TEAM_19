// 학생이 고른 멘토(띠 동물·호칭·말투)를 모든 화면이 함께 쓰는 저장소.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api } from '../api';
import { load, save as store } from '../lib/storage';
import type { Animal, MentorSetting } from '../types';

const DEFAULT_ANIMAL: Animal = 'horse'; // 기본 동물은 팀 회의에서 확정 → 여기만 바꾸면 된다
// 서버(http 모드)에는 그림(띠) 저장 칸이 없어 animal이 null로 온다 → 그림은 이 기기에 저장해 둔다
const ANIMAL_KEY = 'ai-mentor-animal';

interface MentorCtx {
  setting: MentorSetting | null;
  animal: Animal;
  /** 말투에 맞는 문장 고르기: say('안녕!', '안녕하세요!') */
  say: (casual: string, polite: string) => string;
  save: (s: MentorSetting) => Promise<void>;
  reload: () => Promise<void>;
}
const Ctx = createContext<MentorCtx>({ setting: null, animal: DEFAULT_ANIMAL, say: (c) => c, save: async () => {}, reload: async () => {} });

export function MentorProvider({ children }: { children: ReactNode }) {
  const [setting, setSetting] = useState<MentorSetting | null>(null);
  const reload = useCallback(async () => {
    const s = await api.getMentor().catch(() => null);
    setSetting(s && !s.animal ? { ...s, animal: load<Animal>(ANIMAL_KEY, DEFAULT_ANIMAL) } : s);
  }, []);
  useEffect(() => { reload(); }, [reload]);
  const save = useCallback(async (s: MentorSetting) => { await api.saveMentor(s); store(ANIMAL_KEY, s.animal); setSetting(s); }, []);
  const say = useCallback((casual: string, polite: string) => (setting?.speech === '존댓말' ? polite : casual), [setting]);
  return <Ctx.Provider value={{ setting, animal: setting?.animal ?? DEFAULT_ANIMAL, say, save, reload }}>{children}</Ctx.Provider>;
}
export const useMentor = () => useContext(Ctx);
