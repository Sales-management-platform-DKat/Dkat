import React, { useEffect, useMemo, useState } from 'react';
import { useLanguage } from '../../i18n/index.js';
import { FormDialog, FormField, notify } from '../../components/overlay/index.js';
import { EmptyState, ErrorState, LoadingState } from '../../components/states.jsx';
import { changeInventory, listInventory, listInventoryMovements } from './api.js';
import ImportDialog from './ImportDialog.jsx';

const ACTIONS = {
  import: { title: 'Nhập kho', submit: 'Xác nhận nhập kho', done: 'Nhập kho thành công', quantity: 'Số lượng nhập' },
  export: { title: 'Xuất kho', submit: 'Xác nhận xuất kho', done: 'Xuất kho thành công', quantity: 'Số lượng xuất' },
  stocktake: { title: 'Kiểm kê / điều chỉnh tồn', submit: 'Lưu số kiểm kê', done: 'Đã điều chỉnh tồn kho theo số kiểm kê', quantity: 'Số lượng thực đếm' },
};
const MOVEMENT_LABELS = { IMPORT: 'Nhập kho', EXPORT: 'Xuất kho', ADJUSTMENT: 'Điều chỉnh', SALE: 'Bán hàng', PREORDER_FULFILLMENT: 'Giao đặt trước' };

function StockForm({ action, items, branch, initialVariant, onClose, onSaved, t }) {
  const meta = ACTIONS[action];
  const [busy, setBusy] = useState(false);
  const [variantId, setVariantId] = useState(initialVariant ? String(initialVariant) : '');
  const selected = items.find((item) => String(item.variantId) === variantId);

  function validate(data) {
    const errors = {};
    const quantity = Number(data.quantity);
    if (!variantId) errors.variantId = t('Vui lòng chọn sản phẩm.');
    if (data.quantity === '' || !Number.isInteger(quantity) || quantity < (action === 'stocktake' ? 0 : 1)) errors.quantity = action === 'stocktake' ? t('Nhập số nguyên ≥ 0.') : t('Nhập số nguyên lớn hơn 0.');
    else if (action === 'export' && selected && quantity > selected.available) errors.quantity = `${t('Chỉ còn')} ${selected.available} ${t('sản phẩm khả dụng để xuất.')}`;
    else if (action === 'stocktake' && selected && quantity < selected.reserved) errors.quantity = `${t('Không thấp hơn số đang giữ cho đặt trước')} (${selected.reserved}).`;
    if (action === 'stocktake' && !String(data.note || '').trim()) errors.note = t('Vui lòng ghi lý do điều chỉnh.');
    return errors;
  }

  async function submit(data) {
    const quantity = Number(data.quantity);
    const item = action === 'stocktake' ? { variantId: Number(variantId), countedQuantity: quantity } : { variantId: Number(variantId), quantity };
    const payload = { branchId: Number(branch.id), note: String(data.note || '').trim() || null, items: [item] };
    if (action === 'export') payload.reason = data.reason;
    setBusy(true);
    try {
      const result = await changeInventory(action, payload);
      const line = result.items?.[0];
      notify.success(line ? `${t(meta.done)}: ${selected?.sku} ${line.quantityBefore} → ${line.quantityAfter}.` : t(meta.done));
      onSaved();
      return true;
    } catch (error) {
      notify.error(error, { title: t('Không thể cập nhật tồn kho') });
      return false;
    } finally { setBusy(false); }
  }

  return <FormDialog title={t(meta.title)} eyebrow={branch.name} busy={busy} validate={validate} onClose={onClose} onSubmit={submit} submitLabel={t(meta.submit)}>
    <div className="dk-field-wide"><FormField name="variantId" label={t('Sản phẩm / biến thể')} required>
      <select name="variantId" value={variantId} onChange={(event) => setVariantId(event.target.value)}>
        <option value="">{t('Chọn biến thể')}</option>
        {items.map((item) => <option key={item.variantId} value={item.variantId}>{item.productName} · {item.variantName} · {item.sku}</option>)}
      </select>
    </FormField></div>
    {selected && <div className="dk-field-wide stock-snapshot"><span>{t('Tồn thực')}: <b>{selected.quantity}</b></span><span>{t('Đang giữ')}: <b>{selected.reserved}</b></span><span>{t('Khả dụng')}: <b>{selected.available}</b></span></div>}
    <FormField name="quantity" label={t(meta.quantity)} required><input name="quantity" type="number" min={action === 'stocktake' ? 0 : 1} step="1" inputMode="numeric" /></FormField>
    {action === 'export' && <FormField name="reason" label={t('Lý do xuất')} required><select name="reason" defaultValue="HU_HONG"><option value="HU_HONG">{t('Hư hỏng')}</option><option value="MAU">{t('Hàng mẫu')}</option><option value="KHAC">{t('Khác')}</option></select></FormField>}
    <div className="dk-field-wide"><FormField name="note" label={action === 'stocktake' ? t('Lý do điều chỉnh') : t('Ghi chú')} required={action === 'stocktake'}><input name="note" maxLength={255} /></FormField></div>
  </FormDialog>;
}

export default function InventoryPage({ branchId, branch, canWrite }) {
  const { t, formatDateTime } = useLanguage();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [onlyLow, setOnlyLow] = useState(false);
  const [items, setItems] = useState([]);
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [action, setAction] = useState(null);
  const [importing, setImporting] = useState(false);

  useEffect(() => { const timer = setTimeout(() => setSearch(query.trim()), 250); return () => clearTimeout(timer); }, [query]);

  async function reload(term = search) {
    if (!branchId) { setLoading(false); return; }
    setLoading(true); setLoadError(null);
    const result = await Promise.allSettled([
      listInventory({ branchId, keyword: term, page: 1, size: 100 }),
      listInventoryMovements({ branchId, page: 1, size: 50 }),
    ]);
    const failed = result.find((item) => item.status === 'rejected');
    if (failed) { setItems([]); setMovements([]); setLoadError(failed.reason); }
    else { setItems(result[0].value || []); setMovements(result[1].value || []); }
    setLoading(false);
  }
  useEffect(() => { reload(); }, [search, branchId]);

  const visible = useMemo(() => onlyLow ? items.filter((item) => item.available <= 0) : items, [items, onlyLow]);
  const outOfStock = items.filter((item) => item.available <= 0).length;

  if (!branchId || !branch) return <section className="panel"><EmptyState title={t('Chưa chọn chi nhánh')} description={t('Chọn chi nhánh ở thanh trên cùng để xem và quản lý tồn kho.')} /></section>;

  return <>
    <div className="toolbar inventory-toolbar">
      <input aria-label={t('Tìm tồn kho')} placeholder={t('Tìm theo sản phẩm hoặc SKU')} value={query} onChange={(event) => setQuery(event.target.value)} />
      <label className="check-inline"><input type="checkbox" checked={onlyLow} onChange={(event) => setOnlyLow(event.target.checked)} />{t('Chỉ hàng hết')} ({outOfStock})</label>
      {canWrite && <div className="actions toolbar-actions">
        <button className="btn primary" onClick={() => setAction({ kind: 'import' })}>{t('Nhập kho')}</button>
        <button className="btn outline" onClick={() => setImporting(true)}>{t('Nhập từ file CSV/Excel')}</button>
        <button className="btn outline" onClick={() => setAction({ kind: 'export' })}>{t('Xuất kho')}</button>
        <button className="btn outline" onClick={() => setAction({ kind: 'stocktake' })}>{t('Kiểm kê')}</button>
      </div>}
    </div>
    <section className="panel"><div className="section-title"><h3>{t('Tồn kho chi nhánh')} · {branch.name}</h3><span className="muted small">{items.length} {t('biến thể')}</span></div>
      {loading ? <LoadingState label={t('Đang tải tồn kho…')} />
        : loadError ? <ErrorState error={loadError} onRetry={() => reload()} />
          : !visible.length ? <EmptyState title={onlyLow ? t('Không có sản phẩm hết hàng') : t('Chưa có tồn kho')} description={onlyLow ? '' : t('Tạo sản phẩm rồi nhập kho để bắt đầu bán.')} />
            : <div className="table-wrap"><table><thead><tr><th>{t('Sản phẩm')}</th><th>SKU</th><th>{t('Tồn thực')}</th><th>{t('Đã giữ')}</th><th>{t('Khả dụng')}</th><th>{t('Cập nhật lúc')}</th>{canWrite && <th>{t('Thao tác')}</th>}</tr></thead><tbody>
              {visible.map((item) => <tr key={`${item.branchId}-${item.variantId}`}>
                <td><strong>{item.productName}</strong><small className="block muted">{item.variantName}</small></td><td>{item.sku}</td><td>{item.quantity}</td><td>{item.reserved}</td>
                <td><span className={`badge ${item.available > 0 ? 'green' : 'amber'}`}>{item.available > 0 ? item.available : t('Hết hàng')}</span></td>
                <td>{item.updatedAt ? formatDateTime(new Date(item.updatedAt)) : '—'}</td>
                {canWrite && <td><div className="actions"><button className="link" onClick={() => setAction({ kind: 'import', variantId: item.variantId })}>{t('Nhập')}</button><button className="link" disabled={item.available <= 0} onClick={() => setAction({ kind: 'export', variantId: item.variantId })}>{t('Xuất')}</button><button className="link" onClick={() => setAction({ kind: 'stocktake', variantId: item.variantId })}>{t('Kiểm kê')}</button></div></td>}
              </tr>)}
            </tbody></table></div>}
    </section>
    <section className="panel"><div className="section-title"><h3>{t('Lịch sử biến động kho')}</h3><span className="muted small">{t('50 thao tác gần nhất')}</span></div>
      {!movements.length ? <p className="muted">{t('Chưa có biến động kho.')}</p> : <div className="table-wrap"><table><thead><tr><th>{t('Thời gian')}</th><th>SKU</th><th>{t('Nghiệp vụ')}</th><th>{t('Thay đổi')}</th><th>{t('Người thực hiện')}</th><th>{t('Ghi chú')}</th></tr></thead><tbody>
        {movements.map((movement) => <tr key={movement.movementId}><td>{formatDateTime(new Date(movement.createdAt))}</td><td>{movement.sku}</td><td>{t(MOVEMENT_LABELS[movement.movementType] || movement.movementType)}{movement.referenceType === 'STOCK_FILE' && <small className="block muted">{t('từ file')}</small>}</td><td className={movement.quantityChange > 0 ? 'text-positive' : 'text-negative'}>{movement.quantityChange > 0 ? '+' : ''}{movement.quantityChange}</td><td>{movement.createdByName || '—'}</td><td>{movement.note || '—'}</td></tr>)}
      </tbody></table></div>}
    </section>
    {action && <StockForm action={action.kind} initialVariant={action.variantId} items={items} branch={branch} t={t} onClose={() => setAction(null)} onSaved={() => { setAction(null); reload(); }} />}
    {importing && <ImportDialog branch={branch} t={t} onClose={() => setImporting(false)} onImported={() => reload()} />}
  </>;
}
