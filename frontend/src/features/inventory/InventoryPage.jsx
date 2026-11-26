import React, { useEffect, useRef, useState } from 'react';
import { errorMessage, useLanguage } from '../../i18n/index.js';
import { changeInventory, importInventoryCsv, listInventory, listInventoryMovements } from './api.js';

function StockDialog({ action, items, busy, onCancel, onSubmit, t }) {
  return <div className="overlay" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
    <form className="dialog stock-dialog" onSubmit={onSubmit} aria-labelledby="stock-dialog-title">
      <div className="section-title"><h2 id="stock-dialog-title">{t(action === 'import' ? 'Nhập kho' : action === 'export' ? 'Xuất kho' : 'Kiểm kê')}</h2><button className="link" type="button" onClick={onCancel} aria-label={t('Đóng')}>×</button></div>
      <label className="field">{t('Biến thể')}<select name="variantId" required defaultValue=""><option value="">{t('Chọn biến thể')}</option>{items.map((item) => <option key={item.variantId} value={item.variantId}>{item.productName} · {item.sku} · {t('Tồn thực')}: {item.quantity}</option>)}</select></label>
      <label className="field">{t(action === 'stocktake' ? 'Số lượng kiểm kê' : 'Số lượng')}<input name="quantity" type="number" min={action === 'stocktake' ? 0 : 1} step="1" required /></label>
      {action === 'export' && <label className="field">{t('Lý do xuất')}<select name="reason" required><option value="HU_HONG">{t('Hư hỏng')}</option><option value="MAU">{t('Mẫu')}</option><option value="KHAC">{t('Khác')}</option></select></label>}
      <label className="field">{t('Ghi chú')}<input name="note" maxLength={255} /></label>
      <div className="actions"><button className="btn primary" disabled={busy}>{busy ? t('Đang lưu…') : t('Xác nhận')}</button><button className="btn outline" type="button" onClick={onCancel}>{t('Hủy')}</button></div>
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
    setBusy(true); setError(''); setCsvErrors([]);
    try { await changeInventory(action, payload); setAction(null); setNotice('Đã cập nhật tồn kho.'); await reload(); }
    catch (cause) { setError(errorMessage(cause, 'Không thể cập nhật tồn kho.')); }
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
      if (!window.confirm(t('Kiểm tra CSV thành công. Bạn có muốn ghi số lượng vào kho thật không?'))) return;
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
    <section className="panel"><div className="section-title"><h3>{t('Tồn kho chi nhánh')}</h3><span className="muted small">{items.length} {t('biến thể')}</span></div>
      {loading ? <p className="muted" role="status">{t('Đang tải tồn kho…')}</p> : items.length === 0 ? <div className="empty"><h3>{t('Chưa có tồn kho')}</h3><p>{t('Sản phẩm có tồn kho tại chi nhánh sẽ hiển thị tại đây.')}</p></div> : <div className="table-wrap"><table><thead><tr><th>{t('Sản phẩm')}</th><th>SKU</th><th>{t('Tồn thực')}</th><th>{t('Đã giữ')}</th><th>{t('Khả dụng')}</th><th>{t('Cập nhật lúc')}</th></tr></thead><tbody>{items.map((item) => <tr key={`${item.branchId}-${item.variantId}`}><td><strong>{item.productName}</strong><small className="block muted">{item.variantName}</small></td><td>{item.sku}</td><td>{item.quantity}</td><td>{item.reserved}</td><td><span className={`badge ${item.available > 0 ? 'green' : 'amber'}`}>{item.available}</span></td><td>{item.updatedAt ? formatDateTime(new Date(item.updatedAt)) : '—'}</td></tr>)}</tbody></table></div>}
    </section>
    <section className="panel"><div className="section-title"><h3>{t('Lịch sử biến động kho')}</h3></div><div className="table-wrap"><table><thead><tr><th>{t('Thời gian')}</th><th>SKU</th><th>{t('Nghiệp vụ')}</th><th>{t('Thay đổi')}</th><th>{t('Người thực hiện')}</th><th>{t('Ghi chú')}</th></tr></thead><tbody>{movements.map((movement) => <tr key={movement.movementId}><td>{formatDateTime(new Date(movement.createdAt))}</td><td>{movement.sku}</td><td>{t(movement.movementType)}</td><td>{movement.quantityChange > 0 ? '+' : ''}{movement.quantityChange}</td><td>{movement.createdByName || '—'}</td><td>{movement.note || '—'}</td></tr>)}</tbody></table></div></section>
    {action && <StockDialog action={action} items={items} busy={busy} onCancel={() => setAction(null)} onSubmit={submitChange} t={t} />}
    </>}
  </>;
}
