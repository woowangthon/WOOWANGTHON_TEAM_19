// 학생 상점: ① 학원 상품(씨앗 — 학원 재화) ② 꾸미기(칭찬 도장 — 앱 재화, 옷·이모티콘) ③ 내역. 두 재화는 따로 보인다(11-12 결정)
// 규칙(서버): 씨앗이 모자라면 못 산다 · 학원 상품은 "교환 요청" → 학습지도자가 전달하면 "전달 완료"
// 아이 대상이라 넣지 않는 것: 랜덤 뽑기, 현금 충전, 친구와 씨앗 비교(랭킹)
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { CosmeticArt, StampChip } from '../../components/Seed';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import { useMentor } from '../../state/mentor';
import { useAuth } from '../../state/auth';
import { ANIMALS, ANIMAL_LABEL, type Animal, type Cosmetic, type ShopItem } from '../../types';

type Tab = 'academy' | 'deco' | 'history';

export function StudentShop() {
  const nav = useNavigate();
  const loc = useLocation();
  const { say, animal } = useMentor();
  const { refresh } = useAuth();
  const [tab, setTab] = useState<Tab>((loc.state as { tab?: Tab } | null)?.tab ?? 'academy'); // GPT-010: 도장 칩 → 꾸미기 탭
  const { data, setData, error, loading, reload } = useAsync(() => api.getStudentShop());
  const wallet = useAsync(() => api.getWallet(), [tab === 'history']);
  const [buy, setBuy] = useState<{ kind: 'item'; item: ShopItem } | { kind: 'deco'; item: Cosmetic } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  // 꾸미기 검색(11-13): 어떤 캐릭터에 입혀 볼지 + 이름. 산 옷·이모티콘은 캐릭터를 바꿔도 그대로다(id 기준)
  const [look, setLook] = useState<Animal | null>(null);
  const [q, setQ] = useState('');
  const preview: Animal = look ?? animal;
  const match = (c: Cosmetic) => !q.trim() || c.name.replace(/\s/g, '').includes(q.replace(/\s/g, ''));
  const { run, busy, error: actErr, setError } = useAction();

  const confirm = () => run(async () => {
    if (!buy) return;
    if (buy.kind === 'item') { setData(await api.buyAcademyItem(buy.item.id)); setToast(say('선생님께 교환 요청을 보냈어!', '선생님께 교환 요청을 보냈어요!')); }
    else { setData(await api.buyCosmetic(buy.item.id)); await refresh(); setToast(buy.item.kind === 'outfit' ? say('새 옷을 입었어!', '새 옷을 입었어요!') : say('이모티콘이 생겼어!', '이모티콘이 생겼어요!')); }
    setBuy(null);
  });

  return (
    <Frame title="상점" back="/student/mentor">
      {loading && !data && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      {data && (
        <>
          {/* 두 재화: 씨앗(학원 공부·선생님 칭찬 → 학원 상품) · 칭찬 도장(보호자 도장 → 옷·이모티콘) */}
          {/* GPT-011: 두 잔액을 한 카드에 나눠 보이고, 합계는 만들지 않는다 */}
          <section className="seed-hero seed-hero--dual" aria-label="재화 잔액과 얻는 방법">
            <div className="wallet-account">
              <div className="wallet-account__head"><Icon name="seed" size={20} />씨앗 <strong className="num">{data.balance}</strong></div>
              <p className="small">학원 상품에 써</p>
              <p className="seed-hero__how">학원 하루 학습 완료 +3 · 선생님 칭찬</p>
            </div>
            <div className="wallet-account">
              <div className="wallet-account__head"><Icon name="stamp" size={20} />칭찬 도장 <strong className="num">{data.stamps ?? 0}</strong></div>
              <p className="small">옷 · 이모티콘에 써</p>
              <p className="seed-hero__how">보호자와 이야기한 날 하루 1번</p>
            </div>
          </section>
          <div className="seg" role="tablist">
            {([['academy', '학원 상품'], ['deco', '꾸미기'], ['history', '내역']] as [Tab, string][]).map(([k, l]) => (
              <button key={k} role="tab" aria-selected={tab === k} className={'seg__btn' + (tab === k ? ' seg__btn--on' : '')} onClick={() => setTab(k)}>{l}</button>
            ))}
          </div>
          {toast && <div className="notice" role="status"><span>{toast}</span><button className="icon-btn" style={{ width: 32, height: 32 }} aria-label="닫기" onClick={() => setToast(null)}><Icon name="close" size={16} /></button></div>}

          {tab === 'academy' && (
            <>
              <p className="currency-note"><Icon name="seed" size={14} />{say('씨앗으로 바꿔 · 선생님이 정한 상품', '씨앗으로 바꿔요 · 선생님이 정한 상품')}</p>
              {data.academyItems.length === 0 && <div className="notice notice--plain"><span>{say('강의실에 들어가면 선생님 상품이 보여', '강의실에 들어가면 선생님 상품이 보여요')}</span></div>}
              {data.academyItems.map((it) => {
                const soldOut = it.stock === 0;
                const short = it.price - data.balance;
                return (
                  <section key={it.id} className="card shop-row">
                    <span className="shop-row__icon"><Icon name="bag" size={22} /></span>
                    <span style={{ minWidth: 0, flex: 1 }}>
                      <strong>{it.name}</strong>
                      <span className="small muted" style={{ display: 'block' }}>{it.note}{it.stock !== null && ` · 남은 ${it.stock}개`}</span>
                    </span>
                    <button className="price-btn" disabled={soldOut || short > 0} onClick={() => { setError(null); setBuy({ kind: 'item', item: it }); }}>
                      {soldOut ? '다 팔림' : short > 0 ? `${short}개 더` : <><Icon name="seed" size={14} />{it.price}</>}
                    </button>
                  </section>
                );
              })}
              {data.orders.length > 0 && (
                <>
                  <h2 className="h3">바꾼 상품</h2>
                  {data.orders.map((o) => (
                    <div key={o.id} className="card card--flat row between">
                      <span><strong>{o.itemName}</strong><span className="small muted" style={{ display: 'block' }}>{o.at}</span></span>
                      <span className={'pill ' + (o.status === '전달 완료' ? 'pill--mint' : 'pill--accent')}>{o.status === '교환 요청' ? '받기 전' : '받음'}</span>
                    </div>
                  ))}
                </>
              )}
            </>
          )}

          {tab === 'deco' && <p className="currency-note"><Icon name="stamp" size={14} />{say('칭찬 도장으로 꾸며', '칭찬 도장으로 꾸며요')}</p>}
          {tab === 'deco' && (
            <div className="row" style={{ flexWrap: 'wrap', gap: 8 }} role="search" aria-label="꾸미기 찾기">
              <label className="field" style={{ flex: '1 1 140px', margin: 0 }}>캐릭터
                <select className="input" value={preview} onChange={(e) => setLook(e.target.value as Animal)}>
                  {ANIMALS.map((a) => <option key={a} value={a}>{ANIMAL_LABEL[a]}{a === animal ? ' (내 멘토)' : ''}</option>)}
                </select>
              </label>
              <label className="field" style={{ flex: '1 1 140px', margin: 0 }}>이름
                <input className="input" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={say('예: 모자, 힘내', '예: 모자, 힘내')} />
              </label>
            </div>
          )}
          {tab === 'deco' && preview !== animal && <p className="small muted">{say(`${ANIMAL_LABEL[preview]}에게 입혀 본 모습이야. 산 옷은 어떤 캐릭터로 바꿔도 그대로 있어.`, `${ANIMAL_LABEL[preview]}에게 입혀 본 모습이에요. 산 옷은 어떤 캐릭터로 바꿔도 그대로 있어요.`)}</p>}
          {tab === 'deco' && !data.cosmetics.some(match) && <div className="notice notice--plain"><span>{say(`「${q}」 꾸미기가 없어`, `「${q}」 꾸미기가 없어요`)}</span></div>}
          {tab === 'deco' && (['outfit', 'emote'] as const).filter((kind) => data.cosmetics.some((c) => c.kind === kind && match(c))).map((kind) => (
            <section key={kind} className="stack">
              <h2 className="h3">{kind === 'outfit' ? '옷' : '이모티콘'} <span className="small muted">{kind === 'emote' ? say('모아 두는 그림이야', '모아 두는 그림이에요') : ''}</span></h2>
              <div className="deco-grid">
                {data.cosmetics.filter((c) => c.kind === kind && match(c)).map((c) => { const lack = c.owned ? 0 : c.price - (data.stamps ?? 0); return (
                  <button key={c.id} className={'card deco' + (c.equipped ? ' card--selected' : '')} disabled={lack > 0}
                    onClick={() => (c.owned ? (c.kind === 'outfit' ? run(async () => { setData(await api.equipOutfit(c.equipped ? null : c.id)); await refresh(); }) : undefined) : (setError(null), setBuy({ kind: 'deco', item: c })))}>
                    <CosmeticArt animal={preview} kind={c.kind} id={c.id} name={c.name} size={64} />
                    <strong className="small">{c.name}</strong>
                    {c.equipped ? <span className="pill pill--solid">입는 중</span> : c.owned ? <span className="pill pill--mint">{c.kind === 'outfit' ? '입기' : '가짐'}</span> : lack > 0 ? <span className="pill">도장 {lack}개 더</span> : <StampChip n={c.price} />}
                  </button>
                ); })}
              </div>
            </section>
          ))}

          {tab === 'history' && (
            <ul className="list">
              {wallet.data?.history.map((h) => (
                <li key={h.id} className="card card--flat between" style={{ padding: '10px 12px' }}>
                  <span style={{ minWidth: 0 }}><strong className="small"><Icon name={h.currency === 'stamp' ? 'stamp' : 'seed'} size={14} /> {h.source}</strong><span className="small muted" style={{ display: 'block' }}>{h.note} · {h.at}</span></span>
                  <strong className={'num ' + (h.amount > 0 ? 'plus' : 'minus')}>{h.amount > 0 ? '+' : ''}{h.amount}</strong>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {buy && data && (
        <Sheet title={say('이걸로 바꿀까?', '이걸로 바꿀까요?')} onClose={() => setBuy(null)}>
          <div className="row" style={{ gap: 12 }}>
            {buy.kind === 'deco' ? <CosmeticArt animal={preview} kind={buy.item.kind} id={buy.item.id} name={buy.item.name} size={64} /> : <span className="shop-row__icon"><Icon name="bag" size={22} /></span>}
            <div><strong>{buy.item.name}</strong><div className="small muted">{buy.kind === 'deco' ? `칭찬 도장 ${data.stamps ?? 0} → ${(data.stamps ?? 0) - buy.item.price}` : `씨앗 ${data.balance} → ${data.balance - buy.item.price}`}</div></div>
          </div>
          {buy.kind === 'item' && <p className="small muted">{say('선생님께 교환 요청이 가. 학원에서 받으면 돼!', '선생님께 교환 요청이 가요. 학원에서 받으면 돼요!')}</p>}
          <LoadError error={actErr} />
          <div className="btn-row">
            <button className="btn btn--secondary" onClick={() => setBuy(null)}>{say('안 바꿀래', '안 바꿀래요')}</button>
            <button className="btn btn--primary" disabled={busy || (buy.kind === 'deco' ? (data.stamps ?? 0) : data.balance) < buy.item.price} onClick={confirm}><Icon name={buy.kind === 'deco' ? 'stamp' : 'seed'} size={16} />{buy.item.price}개로 바꾸기</button>
          </div>
        </Sheet>
      )}
      {!data && !loading && <button className="btn btn--secondary" onClick={() => nav('/student')}>처음으로</button>}
    </Frame>
  );
}
