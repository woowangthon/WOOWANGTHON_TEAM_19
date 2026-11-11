// 운영자(우리): 학원 등록 신청 심사 (11-10 확정 1A). 시연은 버튼으로 승인/반려.
// 실제 서비스: 국세청 사업자등록 상태 조회 + 서류 확인 후 승인 (백엔드 결정 사항)
import { useState } from 'react';
import { api } from '../../api';
import { Frame } from '../../components/Frame';
import { LoadError, Sheet, Thinking } from '../../components/Common';
import { useAsync } from '../../lib/useAsync';
import { useAction } from '../../lib/useAction';
import type { AcademyApplication } from '../../types';

const TONE: Record<AcademyApplication['status'], string> = { '심사 중': 'pill--accent', 승인: 'pill--mint', 반려: 'pill--danger' };

export function OperatorHome() {
  const { data, setData, error, loading, reload } = useAsync(() => api.getApplications());
  const [open, setOpen] = useState<AcademyApplication | null>(null);
  const [reason, setReason] = useState('');
  const { run, busy, error: actErr } = useAction();
  const decide = (d: '승인' | '반려') => run(async () => { setData(await api.reviewApplication(open!.id, d, reason)); setOpen(null); setReason(''); });
  return (
    <Frame adult title="학원 등록 심사" exit>
      {loading && !data && <Thinking label="불러오는 중" />}
      <LoadError error={error} onRetry={reload} />
      <p className="small muted">시연용 화면이에요. 실제로는 사업자등록 상태 조회 후 승인해요.</p>
      {data?.map((a) => (
        <button key={a.id} className="card row between" onClick={() => setOpen(a)}>
          <span style={{ minWidth: 0 }}><strong>{a.academyName}</strong><span className="small muted" style={{ display: 'block' }}>{a.ownerName} · {a.appliedAt}</span></span>
          <span className={'pill ' + TONE[a.status]}>{a.status}</span>
        </button>
      ))}
      {open && (
        <Sheet title={open.academyName} onClose={() => setOpen(null)}>
          <dl className="kv">
            <dt>사업자번호</dt><dd>{open.bizNo}</dd><dt>대표자</dt><dd>{open.ceo}</dd><dt>연락처</dt><dd>{open.phone}</dd>
            <dt>주소</dt><dd>{open.address || '-'}</dd><dt>신청자</dt><dd>{open.ownerName}</dd>
            {open.serial && <><dt>일련번호</dt><dd className="num"><strong>{open.serial}</strong></dd></>}
            {open.rejectReason && <><dt>반려 사유</dt><dd>{open.rejectReason}</dd></>}
          </dl>
          {open.status === '심사 중' && (
            <>
              <label className="field">반려할 때 사유<textarea className="input" style={{ minHeight: 64 }} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="예: 사업자등록증 확인이 안 돼요" /></label>
              <LoadError error={actErr} />
              <div className="btn-row">
                <button className="btn btn--secondary" disabled={busy || !reason.trim()} onClick={() => decide('반려')}>반려</button>
                <button className="btn btn--primary" disabled={busy} onClick={() => decide('승인')}>승인 · 일련번호 발급</button>
              </div>
            </>
          )}
        </Sheet>
      )}
    </Frame>
  );
}
