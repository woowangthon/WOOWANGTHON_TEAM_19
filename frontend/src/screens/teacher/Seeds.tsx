// 학습지도자: 씨앗 — 학생별 씨앗 확인·칭찬 지급 / 상점 관리(상품 만들기·고치기·숨기기) / 교환 요청 전달 체크
// 학습지도자는 상점에서 사지 않는다(11-10 확정).
import { useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { Icon } from '../../components/Icon';
import { SeedChip } from '../../components/Seed';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import type { ShopItem } from '../../types';

type Tab = 'students' | 'shop' | 'orders';
const REASONS = ['칭찬', '테스트 좋은 점수', '끝까지 노력', '친구를 도와줌'];
const EMPTY: Omit<ShopItem, 'id'> & { id?: string } = { name: '', price: 20, stock: null, visible: true, note: '' };

export function TeacherSeeds() {
  const { data, setData, error, loading, reload } = useAsync(() => api.getSeedBoard());
  const [tab, setTab] = useState<Tab>('students');
  const [grant, setGrant] = useState<{ id: string; name: string; left: number } | null>(null);
  const [amount, setAmount] = useState(2);
  const [reason, setReason] = useState(REASONS[0]);
  const [custom, setCustom] = useState('');
  const [edit, setEdit] = useState<(Omit<ShopItem, 'id'> & { id?: string }) | null>(null);
  const { run, busy, error: actErr, setError } = useAction();
  const waiting = data?.orders.filter((o) => o.status === '교환 요청').length ?? 0;

  return (
    <Frame adult title="씨앗" exit tabs="teacher" right={tab === 'shop' && <button className="icon-btn" aria-label="상품 추가" onClick={() => { setError(null); setEdit({ ...EMPTY }); }}><Icon name="plus" /></button>}>
      <div className="seg" role="tablist">
        {([['students', '학생별'], ['shop', '상점 관리'], ['orders', `교환 요청${waiting ? ` ${waiting}` : ''}`]] as [Tab, string][]).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={'seg__btn' + (tab === k ? ' seg__btn--on' : '')} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {loading && !data && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />

      {data && tab === 'students' && (
        <>
          <p className="small muted">씨앗(학원 재화)은 학습 완료 +3과 선생님 칭찬으로 모아 학원 상품에 써요(칭찬 한 번 1~5, 하루 10까지). 칭찬 도장(보호자 도장)은 따로 모아 캐릭터 옷에 써요.</p>
          <table className="table">
            <thead><tr><th>학생</th><th>씨앗</th><th>이번 주</th><th>도장</th><th /></tr></thead>
            <tbody>
              {data.students.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong></td>
                  <td className="num">{s.balance}</td>
                  <td className="num muted">+{s.earnedWeek}</td>
                  <td className="num">{s.stamps ?? 0}</td>
                  <td style={{ textAlign: 'right' }}><button className="btn btn--secondary btn--small" disabled={s.grantedToday >= 10}
                    onClick={() => { setError(null); setAmount(2); setGrant({ id: s.id, name: s.name, left: 10 - s.grantedToday }); }}>칭찬</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.students.length === 0 && <div className="notice notice--plain"><span>강의실에 학생이 없어요</span></div>}
        </>
      )}

      {data && tab === 'shop' && (
        <>
          <p className="small muted">내 강의실 학생에게만 보여요. 숨긴 상품은 학생에게 안 보여요.</p>
          {data.items.map((it) => (
            <button key={it.id} className={'card shop-row' + (it.visible ? '' : ' shop-row--hidden')} onClick={() => { setError(null); setEdit(it); }}>
              <span style={{ minWidth: 0, flex: 1 }}>
                <strong>{it.name}</strong> {!it.visible && <span className="pill">숨김</span>}
                <span className="small muted" style={{ display: 'block' }}>{it.note || '설명 없음'} · {it.stock === null ? '수량 제한 없음' : `남은 ${it.stock}개`}</span>
              </span>
              <SeedChip n={it.price} />
            </button>
          ))}
        </>
      )}

      {data && tab === 'orders' && (
        <>
          {data.orders.length === 0 && <div className="notice notice--plain"><span>교환 요청이 없어요</span></div>}
          {data.orders.map((o) => (
            <section key={o.id} className={'card row between' + (o.status === '전달 완료' ? ' card--flat' : '')}>
              <span><strong>{o.studentName}</strong> · {o.itemName}<span className="small muted" style={{ display: 'block' }}>{o.at} · 씨앗 {o.price}</span></span>
              {o.status === '교환 요청'
                ? <button className="btn btn--primary btn--small" disabled={busy} onClick={() => run(async () => setData(await api.deliverOrder(o.id)))}>전달 완료</button>
                : <span className="pill pill--mint"><Icon name="check" size={14} />전달함</span>}
            </section>
          ))}
        </>
      )}

      {grant && (
        <Sheet title={`${grant.name}에게 칭찬 씨앗`} onClose={() => setGrant(null)}>
          <div className="row between">
            <span className="small muted">개수 (오늘 {grant.left}개까지)</span>
            <div className="stepper">
              <button className="icon-btn" aria-label="줄이기" disabled={amount <= 1} onClick={() => setAmount(amount - 1)}>−</button>
              <strong className="num">{amount}</strong>
              <button className="icon-btn" aria-label="늘리기" disabled={amount >= Math.min(5, grant.left)} onClick={() => setAmount(amount + 1)}><Icon name="plus" size={18} /></button>
            </div>
          </div>
          <div className="chip-row" role="radiogroup" aria-label="이유">
            {[...REASONS, '직접 쓰기'].map((r) => <button key={r} role="radio" aria-checked={reason === r} className={'chip' + (reason === r ? ' chip--on' : '')} onClick={() => setReason(r)}>{r}</button>)}
          </div>
          {reason === '직접 쓰기' && <input className="input" maxLength={30} value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="예: 숙제를 먼저 해 왔어요" />}
          <LoadError error={actErr} />
          <button className="btn btn--primary" disabled={busy || (reason === '직접 쓰기' && !custom.trim())}
            onClick={() => run(async () => { setData(await api.grantSeeds(grant.id, amount, reason === '직접 쓰기' ? custom : reason)); setGrant(null); setCustom(''); })}>
            <Icon name="seed" size={16} />{amount}개 주기
          </button>
        </Sheet>
      )}

      {edit && (
        <Sheet title={edit.id ? '상품 고치기' : '상품 만들기'} onClose={() => setEdit(null)}>
          <label className="field">이름<input className="input" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} placeholder="예: 칭찬 간식 쿠폰" /></label>
          <label className="field">설명<input className="input" value={edit.note} onChange={(e) => setEdit({ ...edit, note: e.target.value })} placeholder="예: 수업 끝나고 과자 1개" /></label>
          <div className="btn-row">
            <label className="field" style={{ flex: 1 }}>가격(씨앗)<input className="input" type="number" min={1} max={200} value={edit.price} onChange={(e) => setEdit({ ...edit, price: Number(e.target.value) })} /></label>
            <label className="field" style={{ flex: 1 }}>수량{' '}
              <input className="input" type="number" min={0} disabled={edit.stock === null} value={edit.stock ?? ''} placeholder="제한 없음" onChange={(e) => setEdit({ ...edit, stock: Number(e.target.value) })} />
            </label>
          </div>
          <label className="check-row card card--flat"><span className="small">수량 제한 없음</span><input type="checkbox" checked={edit.stock === null} onChange={(e) => setEdit({ ...edit, stock: e.target.checked ? null : 5 })} /></label>
          <label className="check-row card card--flat"><span className="small">학생에게 보이기</span><input type="checkbox" checked={edit.visible} onChange={(e) => setEdit({ ...edit, visible: e.target.checked })} /></label>
          <LoadError error={actErr} />
          <button className="btn btn--primary" disabled={busy} onClick={() => run(async () => { setData(await api.saveShopItem(edit)); setEdit(null); })}>저장</button>
        </Sheet>
      )}
    </Frame>
  );
}
