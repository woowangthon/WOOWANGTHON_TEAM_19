// 강사 학생 시트·씨앗 화면(dev round2 #7·#11·#21)
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { Draft, TeacherMemo } from '../../types';

vi.mock('../../state/auth', () => ({ useAuth: () => ({ me: null }), useMeOptional: () => null }));
const { CommentBox, MemoFields } = await import('./Today');
const { PhotoPick } = await import('./Seeds');

const draft = (status: Draft['status']) => ({ studentId: 's1', studentName: '지우', scope: '', amount: '', mode: '', comment: '잘했어요.', status }) as Draft;
const tag = (m: string, re: string) => m.match(new RegExp(`<${re}[^>]*>`))?.[0] ?? '';
const button = (m: string, label: string) => m.match(new RegExp(`<button[^>]*>${label}`))?.[0] ?? '';

describe('#7 승인한 코멘트', () => {
  it('승인됨 코멘트는 readOnly이고 수정 저장·승인 버튼 비활성', () => {
    // 고친 글(edited)이 있어도 다시 켜지지 않는다 — 서버가 늘 409를 준다
    const m = renderToStaticMarkup(<CommentBox draft={draft('승인됨')} comment="고친 글" busy={false} onComment={() => {}} onSave={() => {}} onApprove={() => {}} />);
    expect(tag(m, 'textarea')).toContain('readOnly');
    expect(button(m, '수정 저장')).toContain('disabled');
    expect(button(m, '승인됨')).toContain('disabled');
  });
  it('안내 문구 보임', () => {
    const m = renderToStaticMarkup(<CommentBox draft={draft('승인됨')} comment="잘했어요." busy={false} onComment={() => {}} onSave={() => {}} onApprove={() => {}} />);
    expect(m).toContain('승인한 코멘트는 고칠 수 없어요');
  });
  it('승인 전 초안은 지금처럼 고칠 수 있다', () => {
    const m = renderToStaticMarkup(<CommentBox draft={draft('승인 대기')} comment="고친 글" busy={false} onComment={() => {}} onSave={() => {}} onApprove={() => {}} />);
    expect(tag(m, 'textarea')).not.toContain('readOnly');
    expect(button(m, '수정 저장')).not.toContain('disabled');
    expect(button(m, '승인')).not.toContain('disabled');
    expect(m).not.toContain('승인한 코멘트는 고칠 수 없어요');
  });
});

describe('#11 초안 뒤 메모', () => {
  const memo: TeacherMemo = { covered: '분수', stuck: '', homework: '3쪽', note: '' };
  it('http 모드 + draft 있으면 메모 입력 readOnly와 안내 문구', () => {
    const m = renderToStaticMarkup(<MemoFields memo={memo} onMemo={() => {}} locked />);
    expect(m.match(/<input[^>]*>/g)!.every((t) => t.includes('readOnly'))).toBe(true);
    expect(m).toContain('초안을 만든 뒤에는 메모를 고칠 수 없어요');
  });
  it('잠기지 않았으면 지금처럼 입력', () => {
    const m = renderToStaticMarkup(<MemoFields memo={memo} onMemo={() => {}} locked={false} />);
    expect(m).not.toContain('readOnly');
    expect(m).not.toContain('초안을 만든 뒤에는');
    expect(m.match(/<input/g)!.length).toBe(4);
  });
});

describe('#21 사진 고르기', () => {
  it('사진 고르기가 button이고 file input은 Tab 순서에서 빠진 숨은 칸', () => {
    const m = renderToStaticMarkup(<PhotoPick onFile={() => {}} />);
    expect(button(m, '사진 고르기')).toContain('type="button"');
    expect(m).not.toContain('<label');
    expect(tag(m, 'input')).toContain('type="file"');
    expect(tag(m, 'input')).toContain('hidden');
  });
});
