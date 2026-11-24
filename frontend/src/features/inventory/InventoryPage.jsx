import React, { useEffect, useState } from 'react';
import { useLanguage } from '../../i18n/index.js';
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

export default function InventoryPage({ branchId, canWrite }) {
  const { t, formatDateTime } = useLanguage();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState([]);
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [action, setAction] = useState(null);

  useEffect(() => { const timer = setTimeout(() => setSearch(query.trim()), 250); return () => clearTimeout(timer); }, [query]);

  async function reload(term = search) {
    setLoading(true); setError('');
    const result = await Promise.allSettled([
      listInventory({ branchId, keyword: term, page: 1, size: 100 }),
      listInventoryMovements({ branchId, page: 1, size: 100 }),
    ]);
    const failed = result.find((item) => item.status === 'rejected');
    if (failed) { setItems([]); setMovements([]); setError(failed.reason?.message || t('Không tải được dữ liệu kho.')); }
    else { setItems(result[0].value || []); setMovements(result[1].value || []); }
    setLoading(false);
  }

  useEffect(() => { reload(); }, [search, branchId]);

  async function submitChange(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const variantId = Number(values.variantId);
    const quantity = Number(values.quantity);
    const item = action === 'stocktake' ? { variantId, countedQuantity: quantity } : { variantId, quantity };
    const payload = { branchId, note: String(values.note || '').trim() || null, items: [item] };
    if (action === 'export') payload.reason = values.reason;
    setBusy(true); setError('');
    try { await changeInventory(action, payload); setAction(null); setNotice(t('Đã cập nhật tồn kho.')); await reload(); }
    catch (cause) { setError(cause.message || t('Không thể cập nhật tồn kho.')); }
    finally { setBusy(false); }
  }

  async function uploadCsv(event) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;
    input.value = '';
    setError(''); setNotice(''); setBusy(true);
    try {
      const preview = await importInventoryCsv({ branchId, file, dryRun: true });
      if (!preview.valid) throw new Error(t('CSV có lỗi. Sửa các dòng được báo rồi thử lại.'));
      if (!window.confirm(t('Kiểm tra CSV thành công. Bạn có muốn ghi số lượng vào kho thật không?'))) return;
      await importInventoryCsv({ branchId, file, dryRun: false });
      setNotice(t('Đã nhập CSV vào kho.')); await reload();
    } catch (cause) { setError(cause.message || t('Không nhập được CSV.')); }
    finally { setBusy(false); }
  }

  return <>
    <div className="toolbar inventory-toolbar"><input aria-label={t('Tìm tồn kho')} placeholder={t('Tìm theo sản phẩm hoặc SKU')} value={query} onChange={(event) => setQuery(event.target.value)} />{canWrite && <><button className="btn primary" disabled={busy} onClick={() => setAction('import')}>{t('Nhập kho')}</button><button className="btn outline" disabled={busy} onClick={() => setAction('export')}>{t('Xuất kho')}</button><button className="btn outline" disabled={busy} onClick={() => setAction('stocktake')}>{t('Kiểm kê')}</button><label className="btn outline">{t('Import CSV')}<input type="file" accept=".csv,text/csv" hidden disabled={busy} onChange={uploadCsv} /></label></>}</div>
    {error && <div className="notice error-state" role="alert">{error}</div>}{notice && <div className="notice success-state" role="status">{notice}</div>}
    <section className="panel"><div className="section-title"><h3>{t('Tồn kho chi nhánh')}</h3><span className="muted small">{items.length} {t('biến thể')}</span></div>
      {loading ? <p className="muted" role="status">{t('Đang tải tồn kho…')}</p> : items.length === 0 ? <div className="empty"><h3>{t('Chưa có tồn kho')}</h3><p>{t('Sản phẩm có tồn kho tại chi nhánh sẽ hiển thị tại đây.')}</p></div> : <div className="table-wrap"><table><thead><tr><th>{t('Sản phẩm')}</th><th>SKU</th><th>{t('Tồn thực')}</th><th>{t('Đã giữ')}</th><th>{t('Khả dụng')}</th><th>{t('Cập nhật lúc')}</th></tr></thead><tbody>{items.map((item) => <tr key={`${item.branchId}-${item.variantId}`}><td><strong>{item.productName}</strong><small className="block muted">{item.variantName}</small></td><td>{item.sku}</td><td>{item.quantity}</td><td>{item.reserved}</td><td><span className={`badge ${item.available > 0 ? 'green' : 'amber'}`}>{item.available}</span></td><td>{item.updatedAt ? formatDateTime(new Date(item.updatedAt)) : '—'}</td></tr>)}</tbody></table></div>}
    </section>
    <section className="panel"><div className="section-title"><h3>{t('Lịch sử biến động kho')}</h3></div><div className="table-wrap"><table><thead><tr><th>{t('Thời gian')}</th><th>SKU</th><th>{t('Nghiệp vụ')}</th><th>{t('Thay đổi')}</th><th>{t('Người thực hiện')}</th><th>{t('Ghi chú')}</th></tr></thead><tbody>{movements.map((movement) => <tr key={movement.movementId}><td>{formatDateTime(new Date(movement.createdAt))}</td><td>{movement.sku}</td><td>{t(movement.movementType)}</td><td>{movement.quantityChange > 0 ? '+' : ''}{movement.quantityChange}</td><td>{movement.createdByName || '—'}</td><td>{movement.note || '—'}</td></tr>)}</tbody></table></div></section>
    {action && <StockDialog action={action} items={items} busy={busy} onCancel={() => setAction(null)} onSubmit={submitChange} t={t} />}
  </>;
}
