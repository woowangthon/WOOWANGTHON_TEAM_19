// 학생 첫 실행 2/2 — 캐릭터(멘토) 고르기. "내 멘토" 탭에서 바꿀 때도 같은 화면(탭 보임).
// v0.4 (11-10 회의): 캐릭터를 앞뒤로 겹친 카드로 넘기기(가운데 크게, 뒤 카드는 작게) + 아래 빈 공간은 "옷장"
// 고르는 것: 띠 동물 + 스타일 3 + 호칭(형/언니/친구) + 반말/존댓말 (팀 기능 DB)
// 대화 중에는 캐릭터를 바꾸지 않는다 → 풀이·수다 화면에는 이 화면으로 가는 길이 없다 (11-09 회의)
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { Mascot, type Mood } from '../../components/Mascot';
import { CosmeticArt, SeedChip } from '../../components/Seed';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import { useMentor } from '../../state/mentor';
import { useAuth } from '../../state/auth';
import { ANIMAL_LABEL, type Animal, type MentorSetting, type MentorStyle, type MentorTitle, type Speech } from '../../types';

const STYLES: { style: MentorStyle; mood: Mood; casual: string; polite: string }[] = [
  { style: '같이 풀어주는', mood: 'cheer', casual: '좋아, 바로 같이 가 보자!', polite: '좋아요, 바로 같이 가 봐요!' },
  { style: '들어주는', mood: 'calm', casual: '천천히 말해 줘, 듣고 있어.', polite: '천천히 말해 주세요, 듣고 있어요.' },
  { style: '짚어주는', mood: 'promise', casual: '오늘은 이것 하나만 짚자.', polite: '오늘은 이것 하나만 짚어요.' },
];
/** 띠를 추가하면 여기와 types.ts Animal에 넣는다 */
const ANIMALS: Animal[] = ['horse', 'monkey'];
const TITLES: MentorTitle[] = ['형', '언니', '친구'];
const SPEECHES: Speech[] = ['반말', '존댓말'];

export function StudentCharacter({ editMode = false }: { editMode?: boolean }) {
  const nav = useNavigate();
  const { setting: saved, save } = useMentor();
  const { me } = useAuth();
  const [setting, setSetting] = useState<MentorSetting>({ style: '같이 풀어주는', title: '형', speech: '반말', animal: 'horse' });
  const [savedNow, setSavedNow] = useState(false);
  useEffect(() => { if (saved) setSetting(saved); }, [saved]);
  const set = (patch: Partial<MentorSetting>) => { setSavedNow(false); setSetting({ ...setting, ...patch }); };
  const submit = async () => { await save(setting); if (editMode) setSavedNow(true); else nav('/student/difficulty'); };
  const idx = Math.max(0, ANIMALS.indexOf(setting.animal));
  const go = (d: number) => set({ animal: ANIMALS[(idx + d + ANIMALS.length) % ANIMALS.length] });
  const style = STYLES.find((s) => s.style === setting.style)!;

  return (
    <Frame title={editMode ? '내 멘토' : '캐릭터 고르기'} back={editMode ? undefined : '/student/onboarding/promise'} exit={editMode}
      right={editMode && me ? undefined : <span className="pill pill--mint">2/2</span>} tabs={editMode ? 'student' : undefined}
      actions={<button className="btn btn--primary" onClick={submit}>{savedNow ? '저장했어 ✓' : editMode ? '이 친구로 바꿀래' : '이 친구로 할래'}</button>}>
      <Stack index={idx} onMove={go} labels={ANIMALS.map((a) => ANIMAL_LABEL[a])}>
        {ANIMALS.map((a) => (
          <div key={a} className="stack-card__inner">
            <Mascot animal={a} mood={a === setting.animal ? style.mood : 'wave'} size={132} outfit={editMode ? me?.outfit : null} />
            <strong>{ANIMAL_LABEL[a]}</strong>
          </div>
        ))}
      </Stack>

      <div className="seg" role="radiogroup" aria-label="멘토 스타일">
        {STYLES.map((s) => <button key={s.style} role="radio" aria-checked={s.style === setting.style} className={'seg__btn' + (s.style === setting.style ? ' seg__btn--on' : '')} onClick={() => set({ style: s.style })}>{s.style.replace('주는', '')}</button>)}
      </div>
      <div className="bubble" style={{ maxWidth: '100%' }}>“{setting.speech === '존댓말' ? style.polite : style.casual}”</div>
      <div className="row between">
        <div className="chip-row" role="radiogroup" aria-label="호칭">
          {TITLES.map((t) => <button key={t} role="radio" aria-checked={setting.title === t} className={'chip' + (setting.title === t ? ' chip--on' : '')} onClick={() => set({ title: t })}>{t}</button>)}
        </div>
        <div className="chip-row" role="radiogroup" aria-label="말투">
          {SPEECHES.map((s) => <button key={s} role="radio" aria-checked={setting.speech === s} className={'chip' + (setting.speech === s ? ' chip--on' : '')} onClick={() => set({ speech: s })}>{s}</button>)}
        </div>
      </div>
      <Wardrobe preview={!editMode} animal={setting.animal} />
    </Frame>
  );
}

/** 앞뒤로 겹친 카드 넘기기. 가운데 카드가 크게, 양옆은 작게 뒤로. 화살표·스와이프·키보드(←→) */
function Stack({ index, onMove, labels, children }: { index: number; onMove: (d: number) => void; labels: string[]; children: React.ReactNode[] }) {
  const start = useRef<number | null>(null);
  const n = children.length;
  return (
    <div className="stack3" role="group" aria-roledescription="캐릭터 넘기기" aria-label={`${labels[index]} (${index + 1}/${n})`} tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'ArrowLeft') onMove(-1); if (e.key === 'ArrowRight') onMove(1); }}
      onPointerDown={(e) => { start.current = e.clientX; }}
      onPointerUp={(e) => { if (start.current != null) { const dx = e.clientX - start.current; if (Math.abs(dx) > 40) onMove(dx < 0 ? 1 : -1); } start.current = null; }}>
      {children.map((c, i) => {
        let off = i - index;
        if (off > n / 2) off -= n; if (off < -n / 2) off += n;
        return <div key={i} className="stack-card" data-off={Math.max(-2, Math.min(2, off))} aria-hidden={off !== 0} onClick={() => off !== 0 && onMove(off)}>{c}</div>;
      })}
      <button className="stack3__arrow stack3__arrow--l" aria-label="이전" onClick={() => onMove(-1)}><Icon name="back" size={20} /></button>
      <button className="stack3__arrow stack3__arrow--r" aria-label="다음" onClick={() => onMove(1)}><Icon name="chevron" size={20} /></button>
      <div className="stack3__dots" aria-hidden>{labels.map((l, i) => <i key={l} className={i === index ? 'on' : ''} />)}</div>
    </div>
  );
}

/** 아래 빈 공간 = 옷장. 가진 옷은 바로 입히고, 없는 옷은 가격을 보여 주고 상점으로 */
function Wardrobe({ preview, animal }: { preview: boolean; animal: Animal }) {
  const nav = useNavigate();
  const { refresh } = useAuth();
  const { data, setData } = useAsync(() => api.getStudentShop());
  const { run, busy } = useAction();
  if (!data) return null;
  const outfits = data.cosmetics.filter((c) => c.kind === 'outfit');
  const equipped = outfits.find((c) => c.equipped)?.id ?? null;
  const put = (id: string | null) => run(async () => { setData(await api.equipOutfit(id)); await refresh(); });
  return (
    <section className="wardrobe" aria-label="옷장">
      <div className="row between">
        <strong className="h3">옷장</strong>
        {preview ? <span className="small muted">씨앗을 모으면 옷을 입힐 수 있어</span>
          : <button className="seed-link" onClick={() => nav('/student/shop')}><SeedChip n={data.balance} /> 상점 <Icon name="chevron" size={14} /></button>}
      </div>
      <div className="chip-row chip-row--scroll wardrobe__row">
        {!preview && (
          <button className={'ward' + (equipped === null ? ' ward--on' : '')} disabled={busy} onClick={() => put(null)}>
            <span className="ward__art ward__art--none">기본</span><span className="small">기본</span>
          </button>
        )}
        {outfits.map((c) => (
          <button key={c.id} className={'ward' + (c.equipped ? ' ward--on' : '') + (c.owned ? '' : ' ward--locked')} disabled={busy || preview}
            onClick={() => (c.owned ? put(c.equipped ? null : c.id) : nav('/student/shop'))}>
            <CosmeticArt animal={animal} kind="outfit" id={c.id} name={c.name} size={56} />
            <span className="small">{c.owned ? c.name : <><Icon name="lock" size={12} /> {c.price}</>}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
