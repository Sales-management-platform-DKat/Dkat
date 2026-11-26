import React, { useMemo, useRef, useState } from 'react';
import { Dialog, notify } from '../../components/overlay/index.js';
import { importInventoryCsv } from './api.js';

const ACCEPT = '.csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const MAX_BYTES = 5 * 1024 * 1024;
const TEMPLATE_BASE = `${import.meta.env.BASE_URL}templates/`;
const STEPS = ['Chọn file', 'Kiểm tra & xem trước', 'Kết quả'];

function csvCell(value) {
  const text = String(value ?? '');
  return /[",;\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function downloadErrorReport(fileName, issues) {
  const lines = [['dong', 'cot', 'ma_loi', 'mo_ta'].join(','), ...issues.map((item) => [item.line, item.field, item.code, item.message].map(csvCell).join(','))];
  const blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement('a'), { href: url, download: `loi-nhap-kho-${fileName.replace(/\.[^.]+$/, '')}.csv` });
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Stock import: choose file -> server validation (dry run) with per-row preview
 * -> confirm -> commit. Nothing is written until the user confirms a fully
 * valid file; the whole file is applied in one transaction.
 */
export default function ImportDialog({ branch, onClose, onImported, t }) {
  const [step, setStep] = useState(0);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [fileError, setFileError] = useState('');
  const [confirmDuplicate, setConfirmDuplicate] = useState(false);
  const submitting = useRef(false);
  const input = useRef(null);

  const lines = useMemo(() => {
    if (!preview) return [];
    const byLine = new Map();
    for (const row of preview.rows) byLine.set(row.line, { line: row.line, row, errors: [], warnings: [] });
    for (const issue of preview.errors) {
      const entry = byLine.get(issue.line) || { line: issue.line, row: null, errors: [], warnings: [] };
      entry.errors.push(issue);
      byLine.set(issue.line, entry);
    }
    for (const issue of preview.warnings || []) byLine.get(issue.line)?.warnings.push(issue);
    return [...byLine.values()].sort((a, b) => a.line - b.line);
  }, [preview]);
  const fileLevelErrors = preview?.errors.filter((issue) => ['file', 'header'].includes(issue.field)) || [];
  const totalQuantity = preview?.rows.reduce((sum, row) => sum + row.quantity, 0) || 0;

  async function check(selected) {
    setFileError('');
    if (!selected) return;
    const name = selected.name.toLowerCase();
    if (!name.endsWith('.csv') && !name.endsWith('.xlsx')) {
      setFileError(name.endsWith('.xls') ? t('File .xls (Excel 97-2003) chưa được hỗ trợ. Hãy lưu lại dưới dạng .xlsx hoặc CSV UTF-8.') : t('Chỉ hỗ trợ file .csv hoặc .xlsx.'));
      return;
    }
    if (selected.size > MAX_BYTES) { setFileError(t('File tối đa 5 MB.')); return; }
    setFile(selected);
    setBusy(true);
    try {
      const data = await importInventoryCsv({ branchId: branch.id, file: selected, dryRun: true });
      setPreview(data);
      setConfirmDuplicate(false);
      setStep(1);
    } catch (error) {
      notify.error(error, { title: t('Không kiểm tra được file') });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  }

  async function commit() {
    if (submitting.current || !preview?.valid) return;
    submitting.current = true;
    setBusy(true);
    try {
      const data = await importInventoryCsv({ branchId: branch.id, file, dryRun: false, allowDuplicate: confirmDuplicate });
      setResult(data);
      setStep(2);
      notify.success(`${t('Nhập kho thành công')}: ${data.items.length} SKU, +${totalQuantity} ${t('sản phẩm')}${data.created?.length ? ` (${data.created.length} ${t('SKU mới')})` : ''}.`);
      onImported?.();
    } catch (error) {
      if (error.code === 'INVALID_STOCK_CSV' && error.detail?.errors) {
        setPreview({ ...preview, ...error.detail, valid: false });
        notify.error(t('Dữ liệu kho vừa thay đổi; một số dòng không còn hợp lệ. Hãy xem lại.'), { title: t('Chưa nhập kho') });
      } else if (error.code === 'DUPLICATE_STOCK_IMPORT') {
        setPreview({ ...preview, duplicateOfImportAt: error.detail?.importedAt || new Date().toISOString() });
        notify.warning(t('Dữ liệu này đã được nhập trong 24 giờ qua. Xác nhận nếu đây là lô hàng mới.'));
      } else {
        notify.error(error, { title: t('Không thể nhập kho') });
      }
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  function restart() {
    setStep(0); setFile(null); setPreview(null); setResult(null); setConfirmDuplicate(false); setFileError('');
  }

  const footer = step === 0
    ? <button className="btn outline" type="button" onClick={onClose}>{t('Đóng')}</button>
    : step === 1
      ? <>
        <button className="btn outline" type="button" disabled={busy} onClick={restart}>{t('← Chọn file khác')}</button>
        {preview && !preview.valid && preview.errors.length > 0 && <button className="btn outline" type="button" onClick={() => downloadErrorReport(file.name, preview.errors)}>{t('Tải báo cáo lỗi')}</button>}
        <button className="btn primary" type="button" disabled={busy || !preview?.valid || (preview.duplicateOfImportAt && !confirmDuplicate)} onClick={commit}>{busy ? t('Đang nhập kho…') : `${t('Xác nhận nhập')} ${preview?.validRows || 0} ${t('dòng')}`}</button>
      </>
      : <><button className="btn outline" type="button" onClick={restart}>{t('Nhập file khác')}</button><button className="btn primary" type="button" onClick={onClose}>{t('Hoàn tất')}</button></>;

  return <Dialog open size="xl" title={t('Nhập kho từ file CSV / Excel')} eyebrow={branch.name} busy={busy} onClose={onClose} footer={footer} className="import-dialog">
    <ol className="stepper" aria-label={t('Các bước nhập kho')}>{STEPS.map((label, index) => <li key={label} className={index === step ? 'is-current' : index < step ? 'is-done' : ''} aria-current={index === step ? 'step' : undefined}><span>{index < step ? '✓' : index + 1}</span>{t(label)}</li>)}</ol>

    {step === 0 && <div className="import-start">
      <label className={`dropzone${busy ? ' is-busy' : ''}`} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); if (!busy) check(event.dataTransfer.files?.[0]); }}>
        <input ref={input} type="file" accept={ACCEPT} hidden disabled={busy} onChange={(event) => check(event.target.files?.[0])} />
        <strong>{busy ? t('Đang đọc và kiểm tra file…') : t('Kéo thả file vào đây hoặc bấm để chọn')}</strong>
        <small>{t('Hỗ trợ .csv (UTF-8) và .xlsx · tối đa 1.000 dòng · 5 MB')}</small>
      </label>
      {fileError && <p className="dk-field-error" role="alert">{fileError}</p>}
      <div className="import-guide">
        <h3>{t('Định dạng dữ liệu')}</h3>
        <table className="guide-table"><thead><tr><th>{t('Cột')}</th><th>{t('Bắt buộc')}</th><th>{t('Mô tả')}</th></tr></thead><tbody>
          <tr><td><code>sku</code></td><td>✓</td><td>{t('SKU của biến thể. SKU đã có sẽ được cộng thêm tồn; SKU mới sẽ được tạo thành sản phẩm mới.')}</td></tr>
          <tr><td><code>quantity</code></td><td>✓</td><td>{t('Số lượng nhập, số nguyên lớn hơn 0.')}</td></tr>
          <tr><td><code>note</code></td><td></td><td>{t('Ghi chú (tối đa 255 ký tự).')}</td></tr>
          <tr><td><code>product_name</code></td><td>{t('SKU mới')}</td><td>{t('Tên sản phẩm. Các SKU mới cùng tên được gộp thành một sản phẩm.')}</td></tr>
          <tr><td><code>price</code></td><td>{t('SKU mới')}</td><td>{t('Giá bán, ví dụ 199000 hoặc 199.000.')}</td></tr>
          <tr><td><code>variant_name</code></td><td></td><td>{t('Tên biến thể, ví dụ Đen / M (mặc định: Mặc định).')}</td></tr>
          <tr><td><code>category</code></td><td></td><td>{t('Danh mục; chưa có sẽ được tạo (mặc định: Chưa phân loại).')}</td></tr>
        </tbody></table>
        <p className="muted small">{t('Tiêu đề tiếng Việt như "Mã SKU", "Số lượng", "Tên sản phẩm", "Giá bán", "Danh mục" cũng được chấp nhận; các cột khác được bỏ qua. SKU lặp lại sẽ được cộng dồn. Các cột sản phẩm chỉ cần cho SKU mới.')}</p>
        <div className="actions"><a className="btn outline" href={`${TEMPLATE_BASE}mau-nhap-kho.csv`} download>{t('Tải file mẫu CSV')}</a><a className="btn outline" href={`${TEMPLATE_BASE}mau-nhap-kho.xlsx`} download>{t('Tải file mẫu Excel')}</a></div>
      </div>
    </div>}

    {step === 1 && preview && <div className="import-preview">
      <div className="import-summary">
        <div><small>{t('File')}</small><b>{file?.name}</b></div>
        <div><small>{t('Tổng dòng')}</small><b>{preview.totalRows}</b></div>
        <div className="ok"><small>{t('Hợp lệ')}</small><b>{preview.validRows}</b></div>
        <div><small>{t('SKU mới / đã có')}</small><b>{preview.newSkus || 0} / {preview.existingSkus || 0}</b></div>
        <div className={preview.errors.length ? 'bad' : ''}><small>{t('Lỗi')}</small><b>{preview.errors.length}</b></div>
        <div><small>{t('Tổng số lượng nhập')}</small><b>+{totalQuantity}</b></div>
      </div>
      {preview.valid ? <div className="notice success-state">{t('File hợp lệ. Kiểm tra bảng bên dưới rồi bấm "Xác nhận nhập" để ghi vào kho.')}{preview.newSkus > 0 && <> {t('Sẽ tạo')} <b>{preview.newSkus}</b> {t('SKU mới cùng sản phẩm tương ứng.')}</>}</div>
        : <div className="notice error-state" role="alert">{t('File còn lỗi nên chưa thể nhập. Sửa các dòng tô đỏ (hoặc tải báo cáo lỗi), lưu file và chọn lại. Hệ thống không nhập một phần dữ liệu.')}</div>}
      {preview.duplicateOfImportAt && <label className="notice warning-state duplicate-confirm"><input type="checkbox" checked={confirmDuplicate} onChange={(event) => setConfirmDuplicate(event.target.checked)} />
        <span>{t('Dữ liệu giống hệt đã được nhập vào chi nhánh lúc')} <b>{new Date(preview.duplicateOfImportAt).toLocaleString('vi-VN')}</b>. {t('Đánh dấu nếu đây là một lô hàng mới và bạn muốn nhập thêm lần nữa.')}</span></label>}
      {fileLevelErrors.map((issue) => <p key={issue.code + issue.line} className="dk-field-error" role="alert">{issue.message}</p>)}
      {lines.length > 0 && <div className="table-wrap import-table"><table><thead><tr><th>{t('Dòng')}</th><th>SKU</th><th>{t('Trạng thái')}</th><th>{t('Sản phẩm')}</th><th>{t('Tồn hiện tại')}</th><th>{t('Nhập')}</th><th>{t('Tồn sau nhập')}</th><th>{t('Ghi chú / Lỗi')}</th></tr></thead><tbody>
        {lines.map((entry) => <tr key={entry.line} className={entry.errors.length ? 'row-error' : entry.warnings.length ? 'row-warning' : ''}>
          <td>{entry.line}</td>
          <td>{entry.row?.sku || '—'}</td>
          <td>{!entry.row ? <span className="badge red">{t('Lỗi')}</span> : entry.row.status === 'NEW' ? <span className="badge amber" title={t('SKU chưa có: sẽ tạo sản phẩm và biến thể mới')}>{t('SKU mới · tạo mới')}</span> : <span className="badge green" title={t('SKU đã tồn tại: cộng thêm vào tồn kho')}>{t('Đã tồn tại · cộng tồn')}</span>}</td>
          <td>{entry.row ? <>{entry.row.productName}<small className="block muted">{entry.row.variantName}{entry.row.status === 'NEW' && ` · ${entry.row.category} · ${Number(entry.row.price).toLocaleString('vi-VN')} ₫`}</small></> : '—'}</td>
          <td>{entry.row?.quantityBefore ?? '—'}</td>
          <td>{entry.row ? `+${entry.row.quantity}` : '—'}</td>
          <td>{entry.row ? entry.row.quantityBefore + entry.row.quantity : '—'}</td>
          <td>{entry.errors.map((issue) => <small key={issue.field + issue.code} className="block dk-field-error">{issue.message}</small>)}{entry.warnings.map((issue) => <small key={issue.code} className="block warning-text">{issue.message}</small>)}{!entry.errors.length && !entry.warnings.length && (entry.row?.note || '')}</td>
        </tr>)}
      </tbody></table></div>}
    </div>}

    {step === 2 && result && <div className="import-result">
      <span className="import-result-icon" aria-hidden="true">✓</span>
      <h3>{t('Đã nhập kho thành công')}</h3>
      <p className="muted">{result.items.length} SKU · +{totalQuantity} {t('sản phẩm')} · {branch.name}. {t('Mọi thay đổi đã được ghi vào lịch sử biến động kho.')}</p>
      {result.created?.length > 0 && <div className="notice warning-state import-created"><b>{t('Đã tạo')} {result.created.length} {t('SKU mới')}:</b> {result.created.map((item) => `${item.sku} (${item.productName} · ${item.variantName})`).join(', ')}</div>}
      <div className="table-wrap"><table><thead><tr><th>SKU</th><th>{t('Trạng thái')}</th><th>{t('Trước')}</th><th>{t('Thay đổi')}</th><th>{t('Sau')}</th></tr></thead><tbody>
        {result.items.map((item) => { const row = result.rows.find((line) => line.variantId === item.variantId) || result.created?.find((line) => line.variantId === item.variantId); const isNew = result.created?.some((line) => line.variantId === item.variantId); return <tr key={item.variantId}><td>{row?.sku || item.variantId}</td><td>{isNew ? <span className="badge amber">{t('SKU mới')}</span> : <span className="badge green">{t('Đã tồn tại')}</span>}</td><td>{item.quantityBefore}</td><td>+{item.quantityChange}</td><td><b>{item.quantityAfter}</b></td></tr>; })}
      </tbody></table></div>
    </div>}
  </Dialog>;
}
