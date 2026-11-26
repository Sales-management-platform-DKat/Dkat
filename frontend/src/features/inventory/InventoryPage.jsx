import React, { useEffect, useRef, useState } from 'react';
import { errorMessage, systemNote, useLanguage } from '../../i18n/index.js';
import { confirmAction } from '../../components/confirm.jsx';
import { Button } from '../../components/ui.jsx';
import { changeInventory, importInventoryCsv, listInventory, listInventoryMovements } from './api.js';

const STOCK_ACTIONS = {
  import: { title: 'Nhập kho', description: 'inventory.dialog.import', quantity: 'Số lượng nhập', min: 1 },
  export: { title: 'Xuất kho', description: 'inventory.dialog.export', quantity: 'Số lượng xuất', min: 1 },
  stocktake: { title: 'Kiểm kê', description: 'inventory.dialog.stocktake', quantity: 'Số lượng kiểm kê', min: 0 },
};

// One dialog for stock in / stock out / stock count. Errors stay inside the dialog with the typed values,
// a click on the backdrop never discards a filled form, and the submit button cannot be pressed twice.
function StockDialog({ action, items, busy, error, onCancel, onSubmit, t, formatNumber }) {
  const config = STOCK_ACTIONS[action];
  const [dirty, setDirty] = useState(false);
  const cancel = () => { if (!busy) onCancel(); };
  return <div className="overlay" role="presentation"
    onMouseDown={(event) => event.target === event.currentTarget && !dirty && cancel()}
    onKeyDown={(event) => { if (event.key === 'Escape' && !dirty) cancel(); }}>
    <form className="dialog stock-dialog" onSubmit={onSubmit} onChange={() => setDirty(true)} aria-labelledby="stock-dialog-title" aria-describedby="stock-dialog-description" aria-busy={busy}>
      <div className="section-title"><h2 id="stock-dialog-title">{t(config.title)}</h2><button className="link" type="button" onClick={cancel} disabled={busy} aria-label={t('Đóng')}>×</button></div>
      <p id="stock-dialog-description" className="muted dialog-description">{t(config.description)}</p>
      <fieldset className="dialog-group" disabled={busy}>
        <legend>{t('Sản phẩm')}</legend>
        <label className="field">{t('Biến thể')} *<select name="variantId" required defaultValue="" autoFocus><option value="">{t('Chọn biến thể')}</option>{items.map((item) => <option key={item.variantId} value={item.variantId}>{item.productName} · {item.sku} · {t('Tồn thực')}: {formatNumber(item.quantity)}</option>)}</select></label>
        <label className="field">{t(config.quantity)} *<input name="quantity" type="number" inputMode="numeric" min={config.min} step="1" required placeholder={t(action === 'stocktake' ? 'Số lượng đếm được thực tế' : 'Ví dụ: 10')} /></label>
      </fieldset>
      <fieldset className="dialog-group" disabled={busy}>
        <legend>{t('Lý do và ghi chú')}</legend>
        {action === 'export' && <label className="field">{t('Lý do xuất')} *<select name="reason" required><option value="HU_HONG">{t('Hư hỏng')}</option><option value="MAU">{t('Mẫu')}</option><option value="KHAC">{t('Khác')}</option></select></label>}
        <label className="field">{t(action === 'stocktake' ? 'Ghi chú kiểm kê' : 'Ghi chú')}{action === 'stocktake' ? ' *' : ''}
          <input name="note" maxLength={255} required={action === 'stocktake'} placeholder={t(action === 'stocktake' ? 'Ví dụ: Kiểm kê cuối ngày' : 'Không bắt buộc')} />
          {action === 'stocktake' && <small className="muted">{t('Bắt buộc để lưu lại lý do điều chỉnh tồn kho.')}</small>}
        </label>
      </fieldset>
      {error && <p className="notice error-state" role="alert">{t(error)}</p>}
      <div className="dialog-actions"><Button variant="outline" type="button" disabled={busy} onClick={cancel}>{t('Hủy')}</Button><Button variant="primary" type="submit" loading={busy}>{busy ? t('Đang lưu…') : t('Xác nhận')}</Button></div>
    </form>
  </div>;
}

const DISPLAYED_CSV_ERRORS = 20;

function CsvErrors({ errors, t, formatNumber }) {
  return <>
    <ul>
      {errors.slice(0, DISPLAYED_CSV_ERRORS).map(({ line, field, code }, index) => {
        const key = code === 'INVALID_VALUE' ? `inventory.csv.field.${field}` : `inventory.csv.error.${code}`;
        const message = t(key);
        return <li key={index}>{t('inventory.csv.line', { line: formatNumber(line), field, message: message === key ? t('inventory.csv.invalidField') : message })}</li>;
      })}
    </ul>
    {errors.length > DISPLAYED_CSV_ERRORS && <p>{t('inventory.csv.moreErrors', { count: formatNumber(errors.length - DISPLAYED_CSV_ERRORS) })}</p>}
  </>;
}

export default function InventoryPage({ branchId, branchState, canWrite }) {
  const { t, formatDateTime, formatNumber } = useLanguage();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState([]);
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [csvErrors, setCsvErrors] = useState([]);
  const [notice, setNotice] = useState('');
  const [action, setAction] = useState(null);
  const [dialogError, setDialogError] = useState('');
  const csvInput = useRef(null);
  const csvRequest = useRef(null);
  const hasBranch = branchState === 'ready' && Number.isSafeInteger(branchId) && branchId > 0;
  const writeDisabled = busy || !hasBranch;

  useEffect(() => { const timer = setTimeout(() => setSearch(query.trim()), 250); return () => clearTimeout(timer); }, [query]);
  useEffect(() => () => csvRequest.current?.abort(), []);

  async function reload(term = search) {
    setLoading(true); setError('');
    const result = await Promise.allSettled([
      listInventory({ branchId, keyword: term, page: 1, size: 100 }),
      listInventoryMovements({ branchId, page: 1, size: 100 }),
    ]);
    const failed = result.find((item) => item.status === 'rejected');
    if (failed) { setItems([]); setMovements([]); setError(errorMessage(failed.reason, 'Không tải được dữ liệu kho.')); }
    else { setItems(result[0].value || []); setMovements(result[1].value || []); }
    setLoading(false);
  }

  useEffect(() => { if (hasBranch) reload(); }, [search, branchId, hasBranch]);

  async function submitChange(event) {
    event.preventDefault();
    if (writeDisabled) return;
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const variantId = Number(values.variantId);
    const quantity = Number(values.quantity);
    const item = action === 'stocktake' ? { variantId, countedQuantity: quantity } : { variantId, quantity };
    const payload = { branchId, note: String(values.note || '').trim() || null, items: [item] };
    if (action === 'export') payload.reason = values.reason;
    if (busy) return;
    setBusy(true); setError(''); setDialogError(''); setCsvErrors([]);
    try { await changeInventory(action, payload); setAction(null); setNotice('Đã cập nhật tồn kho.'); await reload(); }
    catch (cause) { setDialogError(errorMessage(cause, 'Không thể cập nhật tồn kho.')); }
    finally { setBusy(false); }
  }

  async function uploadCsv(event) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    input.value = '';
    if (!file || writeDisabled || csvRequest.current) return;
    const controller = new AbortController();
    csvRequest.current = controller;
    const options = { branchId, file, signal: controller.signal };
    setError(''); setCsvErrors([]); setNotice(''); setBusy(true);
    try {
      const preview = await importInventoryCsv({ ...options, dryRun: true });
      if (controller.signal.aborted) return;
      if (!preview.valid) {
        setError('CSV có lỗi. Sửa các dòng được báo rồi thử lại.');
        setCsvErrors(preview.errors || []);
        return;
      }
      const answer = await confirmAction({ tone: 'warning', title: 'inventory.csv.confirmTitle',
        description: 'Kiểm tra CSV thành công. Bạn có muốn ghi số lượng vào kho thật không?', confirmLabel: 'Ghi vào kho' });
      if (!answer || controller.signal.aborted) return;
      await importInventoryCsv({ ...options, dryRun: false });
      if (controller.signal.aborted) return;
      setNotice('Đã nhập CSV vào kho.'); await reload();
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause.code === 'INVALID_STOCK_CSV') {
        setError('CSV có lỗi. Sửa các dòng được báo rồi thử lại.');
        setCsvErrors(cause.details?.errors || []);
      } else {
        setError(errorMessage(cause, 'Không nhập được CSV.'));
      }
    } finally {
      csvRequest.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return <>
    <div className="toolbar inventory-toolbar">
      <input aria-label={t('Tìm tồn kho')} placeholder={t('Tìm theo sản phẩm hoặc SKU')} value={query} onChange={(event) => setQuery(event.target.value)} />
      {canWrite && <>
        <button className="btn primary" disabled={writeDisabled} onClick={() => setAction('import')}>{t('Nhập kho')}</button>
        <button className="btn outline" disabled={writeDisabled} onClick={() => setAction('export')}>{t('Xuất kho')}</button>
        <button className="btn outline" disabled={writeDisabled} onClick={() => setAction('stocktake')}>{t('Kiểm kê')}</button>
        <button className="btn outline" disabled={writeDisabled} onClick={() => csvInput.current?.click()}>{t('Import CSV')}</button>
        <input ref={csvInput} type="file" accept=".csv,text/csv" hidden disabled={writeDisabled} onChange={uploadCsv} />
      </>}
    </div>
    {!hasBranch && <p className="notice" role="status">{t(branchState === 'loading' ? 'Đang tải chi nhánh…' : branchState === 'error' ? 'Không tải được danh sách chi nhánh.' : 'inventory.branchRequired')}</p>}
    {canWrite && hasBranch && <p className="muted small">{t('inventory.csv.format')}</p>}
    {error && <div className="notice error-state" role="alert">
      {t(error)}
      {csvErrors.length > 0 && <CsvErrors errors={csvErrors} t={t} formatNumber={formatNumber} />}
    </div>}
    {notice && <div className="notice success-state" role="status">{t(notice)}</div>}
    {hasBranch && <>
    <section className="panel"><div className="section-title"><h3>{t('Tồn kho chi nhánh')}</h3><span className="muted small">{t(items.length === 1 ? 'count.variant.one' : 'count.variant.other', { count: formatNumber(items.length) })}</span></div>
      {loading ? <p className="muted" role="status">{t('Đang tải tồn kho…')}</p> : items.length === 0 ? <div className="empty"><h3>{t('Chưa có tồn kho')}</h3><p>{t('Sản phẩm có tồn kho tại chi nhánh sẽ hiển thị tại đây.')}</p></div> : <div className="table-wrap"><table><thead><tr><th>{t('Sản phẩm')}</th><th>SKU</th><th>{t('Tồn thực')}</th><th>{t('Đã giữ')}</th><th>{t('Khả dụng')}</th><th>{t('Cập nhật lúc')}</th></tr></thead><tbody>{items.map((item) => <tr key={`${item.branchId}-${item.variantId}`}><td><strong>{item.productName}</strong><small className="block muted">{item.variantName}</small></td><td>{item.sku}</td><td>{item.quantity}</td><td>{item.reserved}</td><td><span className={`badge ${item.available > 0 ? 'green' : 'amber'}`}>{item.available}</span></td><td>{item.updatedAt ? formatDateTime(new Date(item.updatedAt)) : '—'}</td></tr>)}</tbody></table></div>}
    </section>
    <section className="panel"><div className="section-title"><h3>{t('Lịch sử biến động kho')}</h3></div><div className="table-wrap"><table><thead><tr><th>{t('Thời gian')}</th><th>SKU</th><th>{t('Nghiệp vụ')}</th><th>{t('Thay đổi')}</th><th>{t('Người thực hiện')}</th><th>{t('Ghi chú')}</th></tr></thead><tbody>{movements.map((movement) => <tr key={movement.movementId}><td>{formatDateTime(new Date(movement.createdAt))}</td><td>{movement.sku}</td><td>{t(movement.movementType)}</td><td>{movement.quantityChange > 0 ? '+' : ''}{movement.quantityChange}</td><td>{movement.createdByName || '—'}</td><td>{movement.note ? t(systemNote(movement.note)) : '—'}</td></tr>)}</tbody></table></div></section>
    {action && <StockDialog action={action} items={items} busy={busy} error={dialogError} onCancel={() => { setAction(null); setDialogError(''); }} onSubmit={submitChange} t={t} formatNumber={formatNumber} />}
    </>}
  </>;
}
