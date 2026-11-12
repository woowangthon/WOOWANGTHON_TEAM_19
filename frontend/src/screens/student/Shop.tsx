// 학생 상점: ① 학원 상품(씨앗 — 학원 재화) ② 꾸미기(칭찬 도장 — 앱 재화, 옷·이모티콘) ③ 내역. 두 재화는 따로 보인다(11-12 결정)
// 규칙(서버): 씨앗이 모자라면 못 산다 · 학원 상품은 "교환 요청" → 학습지도자가 전달하면 "전달 완료"
// 아이 대상이라 넣지 않는 것: 랜덤 뽑기, 현금 충전, 친구와 씨앗 비교(랭킹)
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { CosmeticArt, StampChip } from '../../components/Seed';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import { useMentor } from '../../state/mentor';
import { useAuth } from '../../state/auth';
import type { Cosmetic, ShopItem } from '../../types';

type Tab = 'academy' | 'deco' | 'history';

export function StudentShop() {
  const nav = useNavigate();
  const { say, animal } = useMentor();
  const { refresh } = useAuth();
  const [tab, setTab] = useState<Tab>('academy');
  const { data, setData, error, loading, reload } = useAsync(() => api.getStudentShop());
  const wallet = useAsync(() => api.getWallet(), [tab === 'history']);
  const [buy, setBuy] = useState<{ kind: 'item'; item: ShopItem } | { kind: 'deco'; item: Cosmetic } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
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
          <div className="wallet-pair">
            <section className="seed-hero" aria-label="씨앗">
              <div><div className="small">씨앗</div><div className="seed-hero__n num"><Icon name="seed" size={24} />{data.balance}</div></div>
              <div className="small seed-hero__how">학원 공부·선생님 칭찬<br />→ 학원 상품</div>
            </section>
            <section className="seed-hero seed-hero--stamp" aria-label="칭찬 도장">
              <div><div className="small">칭찬 도장</div><div className="seed-hero__n num"><Icon name="stamp" size={24} />{data.stamps ?? 0}</div></div>
              <div className="small seed-hero__how">보호자 도장<br />→ 옷·이모티콘</div>
            </section>
          </div>
          <div className="seg" role="tablist">
            {([['academy', '학원 상품'], ['deco', '꾸미기'], ['history', '내역']] as [Tab, string][]).map(([k, l]) => (
              <button key={k} role="tab" aria-selected={tab === k} className={'seg__btn' + (tab === k ? ' seg__btn--on' : '')} onClick={() => setTab(k)}>{l}</button>
            ))}
          </div>
          {toast && <div className="notice" role="status"><span>{toast}</span><button className="icon-btn" style={{ width: 32, height: 32 }} aria-label="닫기" onClick={() => setToast(null)}><Icon name="close" size={16} /></button></div>}

          {tab === 'academy' && (
            <>
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

          {tab === 'deco' && (['outfit', 'emote'] as const).map((kind) => (
            <section key={kind} className="stack">
              <h2 className="h3">{kind === 'outfit' ? '옷' : '이모티콘'} <span className="small muted">{kind === 'emote' ? '수다에서 보낼 수 있어' : ''}</span></h2>
              <div className="deco-grid">
                {data.cosmetics.filter((c) => c.kind === kind).map((c) => { const lack = c.owned ? 0 : c.price - (data.stamps ?? 0); return (
                  <button key={c.id} className={'card deco' + (c.equipped ? ' card--selected' : '')} disabled={lack > 0}
                    onClick={() => (c.owned ? (c.kind === 'outfit' ? run(async () => { setData(await api.equipOutfit(c.equipped ? null : c.id)); await refresh(); }) : undefined) : (setError(null), setBuy({ kind: 'deco', item: c })))}>
                    <CosmeticArt animal={animal} kind={c.kind} id={c.id} name={c.name} size={64} />
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
            {buy.kind === 'deco' ? <CosmeticArt animal={animal} kind={buy.item.kind} id={buy.item.id} name={buy.item.name} size={64} /> : <span className="shop-row__icon"><Icon name="bag" size={22} /></span>}
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
