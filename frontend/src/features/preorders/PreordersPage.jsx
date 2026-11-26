import React, { useEffect, useMemo, useState } from 'react';
import { useLanguage } from '../../i18n/index.js';
import { confirmAction, Dialog, notify } from '../../components/overlay/index.js';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../../components/states.jsx';
import { listInventory } from '../inventory/api.js';
import { listProducts } from '../products/api.js';
import { cancelPreorder, confirmPreorderPayment, fulfillPreorder, listPreorderNotifications, listPreorders, resendNotification } from './api.js';
import PreorderDialog from './PreorderDialog.jsx';

const STATUS_OPTIONS = ['WAITING_STOCK', 'READY', 'NOTIFIED', 'FULFILLED', 'CANCELLED', 'EXPIRED'];
const STATUS_LABELS = { WAITING_STOCK: 'Chờ hàng', READY: 'Sẵn sàng', NOTIFIED: 'Đã thông báo', FULFILLED: 'Đã nhận hàng', CANCELLED: 'Đã hủy', EXPIRED: 'Hết hạn' };

// Inventory rows carry stock; product rows carry prices of active variants.
export function preorderOptions(inventory, products) {
  const prices = new Map((products || []).flatMap((product) => product.variants.map((variant) => [variant.variant_id, variant.price])));
  return (inventory || []).filter((item) => prices.has(item.variantId)).map((item) => ({
    variantId: item.variantId, productName: item.productName, variantName: item.variantName, sku: item.sku,
    price: prices.get(item.variantId), available: item.available,
  }));
}

export default function PreordersPage({ branchId, branch }) {
  const { t, formatCurrency, formatDateTime } = useLanguage();
  const [rows, setRows] = useState([]);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [options, setOptions] = useState([]);

  async function reload() {
    setLoading(true); setLoadError(null);
    try { setRows(await listPreorders({ branchId, keyword: query.trim(), status: status || undefined })); }
    catch (error) { setRows([]); setLoadError(error); }
    finally { setLoading(false); }
  }
  useEffect(() => { const timer = setTimeout(reload, 250); return () => clearTimeout(timer); }, [branchId, query, status]);

  async function openCreate() {
    try {
      const [inventory, products] = await Promise.all([listInventory({ branchId, page: 1, size: 100 }), listProducts({ page: 1, size: 100, sort: 'name' })]);
      setOptions(preorderOptions(inventory, products));
      setCreating(true);
    } catch (error) {
      notify.error(error, { title: t('Không tải được tồn kho') });
    }
  }

  async function act(row, kind) {
    const label = `${row.preorderCode} · ${row.customer?.fullName || ''}`;
    let reason = '';
    if (kind === 'cancel') {
      const result = await confirmAction({
        title: t('Hủy đơn đặt trước?'), description: label, confirmLabel: t('Hủy đơn'), requireReason: true,
        reasonLabel: t('Lý do hủy'), reasonPlaceholder: t('VD: Khách đổi ý'),
      });
      if (!result) return;
      reason = result.reason;
    } else {
      const ok = await confirmAction(kind === 'pay'
        ? { title: t('Xác nhận đã nhận đủ tiền?'), description: `${label} · ${formatCurrency(Number(row.totalAmount))}`, confirmLabel: t('Đã nhận tiền'), tone: 'primary' }
        : { title: t('Xác nhận khách đã nhận hàng?'), description: `${label}. ${t('Thao tác này trừ tồn kho.')}`, confirmLabel: t('Xác nhận giao'), tone: 'primary' });
      if (!ok) return;
    }
    setBusyId(row.preorderId);
    try {
      if (kind === 'cancel') await cancelPreorder(row.preorderId, reason);
      if (kind === 'pay') await confirmPreorderPayment(row.preorderId, { paymentMethod: 'CASH', amount: Number(row.totalAmount) });
      if (kind === 'fulfill') await fulfillPreorder(row.preorderId, {});
      notify.success({ cancel: t('Đã hủy đơn đặt trước.'), pay: t('Đã ghi nhận thanh toán.'), fulfill: t('Đã xác nhận giao hàng.') }[kind]);
      await reload();
    } catch (error) {
      notify.error(error, { title: t('Không cập nhật được đơn đặt trước') });
    } finally {
      setBusyId(null);
    }
  }

  // SMS/email history for a pre-order (FR-09), with resend for failed deliveries.
  const [history, setHistory] = useState(null);
  async function openHistory(row) {
    setHistory({ row, items: null });
    try {
      const data = await listPreorderNotifications(row.preorderId);
      setHistory({ row, items: data.items || [] });
    } catch (error) {
      setHistory({ row, items: [] });
      notify.error(error, { title: t('Không tải được lịch sử thông báo') });
    }
  }
  async function resend(item) {
    setBusyId(history.row.preorderId);
    try {
      await resendNotification(item.id);
      notify.success(t('Đã gửi lại thông báo.'));
    } catch (error) {
      notify.error(error, { title: t('Không gửi lại được thông báo') });
    } finally {
      setBusyId(null);
    }
    await openHistory(history.row);
    await reload();
  }

  const counts = useMemo(() => rows.reduce((acc, row) => ({ ...acc, [row.status]: (acc[row.status] || 0) + 1 }), {}), [rows]);

  return <>
    <div className="toolbar">
      <input aria-label={t('Tìm đơn đặt trước')} placeholder={t('Tìm mã đơn, khách hàng hoặc số điện thoại')} value={query} onChange={(event) => setQuery(event.target.value)} />
      <select aria-label={t('Trạng thái')} value={status} onChange={(event) => setStatus(event.target.value)}><option value="">{t('Mọi trạng thái')}</option>{STATUS_OPTIONS.map((value) => <option key={value} value={value}>{t(STATUS_LABELS[value])}{counts[value] && !status ? ` (${counts[value]})` : ''}</option>)}</select>
      <button className="btn primary" disabled={!branch} onClick={openCreate}>{t('+ Tạo đơn đặt trước')}</button>
    </div>
    <section className="panel">
      {loading ? <LoadingState label={t('Đang tải đơn đặt trước…')} />
        : loadError ? <ErrorState error={loadError} onRetry={reload} />
          : !rows.length ? <EmptyState title={t('Chưa có đơn đặt trước')} description={t('Khách có thể đặt trước sản phẩm đang hết hàng; hàng nhập về sẽ được phân bổ theo thứ tự đặt.')} />
            : <div className="table-wrap"><table><thead><tr>{['Mã đơn', 'Khách hàng', 'Sản phẩm', 'Ngày tạo', 'Tổng tiền', 'Trạng thái', 'Thanh toán', 'Thao tác'].map((x) => <th key={x}>{t(x)}</th>)}</tr></thead><tbody>
              {rows.map((row) => <tr key={row.preorderId}>
                <td><strong>{row.preorderCode}</strong></td>
                <td>{row.customer?.fullName}<small className="block muted">{row.customer?.phone}</small></td>
                <td>{(row.items || []).map((item) => <small key={item.variantId} className="block">{item.productName} × {item.quantity}<span className="muted"> ({t('đã giữ')} {item.allocatedQuantity ?? 0})</span></small>)}</td>
                <td>{row.createdAt ? formatDateTime(new Date(row.createdAt)) : '—'}</td>
                <td>{formatCurrency(Number(row.totalAmount))}</td>
                <td><StatusBadge status={row.status} /></td>
                <td><StatusBadge status={row.paymentStatus} /></td>
                <td><div className="actions wrap">
                  {row.paymentStatus === 'UNPAID' && !['CANCELLED', 'EXPIRED'].includes(row.status) && <button className="link" disabled={busyId === row.preorderId} onClick={() => act(row, 'pay')}>{t('Ghi nhận tiền')}</button>}
                  {['READY', 'NOTIFIED'].includes(row.status) && row.paymentStatus === 'PAID' && <button className="link" disabled={busyId === row.preorderId} onClick={() => act(row, 'fulfill')}>{t('Xác nhận giao')}</button>}
                  {row.status !== 'WAITING_STOCK' && <button className="link" onClick={() => openHistory(row)}>{t('Thông báo')}</button>}
                  {!['CANCELLED', 'FULFILLED', 'EXPIRED'].includes(row.status) && <button className="link danger" disabled={busyId === row.preorderId} onClick={() => act(row, 'cancel')}>{t('Hủy')}</button>}
                </div></td>
              </tr>)}
            </tbody></table></div>}
    </section>
    {history && <Dialog open size="lg" title={t('Lịch sử thông báo')} description={`${history.row.preorderCode} · ${history.row.customer?.fullName || ''}`} onClose={() => setHistory(null)}>
      {history.items === null ? <LoadingState /> : !history.items.length ? <p className="muted">{t('Chưa có lần gửi nào.')}</p>
        : <div className="table-wrap"><table><thead><tr>{['Kênh', 'Người nhận', 'Trạng thái', 'Thời gian', 'Ghi chú', ''].map((x) => <th key={x}>{t(x)}</th>)}</tr></thead><tbody>
          {history.items.map((n) => <tr key={n.id}>
            <td>{n.channel === 'SMS' ? 'SMS' : 'Email'}</td><td>{n.recipient}</td>
            <td>{n.status === 'SENT' ? t('Đã gửi') : n.status === 'FAILED' ? t('Lỗi') : t('Đang gửi')}{n.retryCount ? ` · ${t('gửi lại')} ${n.retryCount}` : ''}</td>
            <td>{formatDateTime(new Date(n.sentAt || n.lastAttemptAt || n.createdAt))}</td>
            <td><small className="muted">{n.errorMessage ? n.errorMessage.split(':')[0] : ''}</small></td>
            <td>{n.canResend && <button className="link" disabled={busyId === history.row.preorderId} onClick={() => resend(n)}>{t('Gửi lại')}</button>}</td>
          </tr>)}
        </tbody></table></div>}
    </Dialog>}
    {creating && branch && <PreorderDialog branch={branch} options={options} t={t} formatCurrency={formatCurrency}
      onClose={() => setCreating(false)} onCreated={() => reload()} />}
  </>;
}
