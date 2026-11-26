import React, { useEffect, useState } from 'react';
import { errorMessage, useLanguage } from '../../i18n/index.js';
import { cancelSalesOrder, confirmSalesOrderPayment, getSalesOrder, listSalesOrders, refundSalesOrder } from './api.js';

const stateText = { PENDING: 'Chờ thanh toán', PAID: 'Đã thanh toán', CANCELLED: 'Đã hủy', REFUNDED: 'Đã hoàn tiền' };
export default function SalesOrdersPage({ branchId, canRefund = false }) {
  const { t, formatCurrency, formatDateTime } = useLanguage();
  const [orders, setOrders] = useState([]); const [query, setQuery] = useState(''); const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [selected, setSelected] = useState(null);
  async function reload() { setLoading(true); setError(''); try { setOrders(await listSalesOrders({ branchId, keyword: query.trim(), status: status || undefined })); } catch (e) { setOrders([]); setError(errorMessage(e, 'Không tải được đơn bán.')); } finally { setLoading(false); } }
  useEffect(() => { const timer = setTimeout(reload, 250); return () => clearTimeout(timer); }, [branchId, query, status]);
  async function open(order) { setError(''); try { setSelected(await getSalesOrder(order.salesOrderId)); } catch (e) { setError(errorMessage(e, 'Không tải được chi tiết đơn.')); } }
  async function act(action) {
    if (!selected) return; let reason = '';
    if (action === 'cancel' || action === 'refund') { reason = window.prompt(t(action === 'refund' ? 'Nhập lý do hoàn tiền' : 'Nhập lý do hủy')); if (!reason?.trim()) return; }
    setBusy(true); setError('');
    try {
      let result;
      if (action === 'pay') result = await confirmSalesOrderPayment(selected.salesOrderId, { paymentMethod: 'CASH', amount: Number(selected.totalAmount) });
      if (action === 'cancel') result = await cancelSalesOrder(selected.salesOrderId, reason.trim());
      if (action === 'refund') result = await refundSalesOrder(selected.salesOrderId, reason.trim());
      setSelected(result); await reload();
    } catch (e) { setError(errorMessage(e, 'Không cập nhật được đơn bán.')); } finally { setBusy(false); }
  }
  return <>
    <div className="toolbar"><input aria-label={t('Tìm đơn bán')} placeholder={t('Tìm mã đơn hoặc khách hàng')} value={query} onChange={e => setQuery(e.target.value)} /><select value={status} onChange={e => setStatus(e.target.value)}><option value="">{t('Mọi trạng thái')}</option><option value="PENDING">{t(stateText.PENDING)}</option><option value="PAID">{t(stateText.PAID)}</option><option value="CANCELLED">{t(stateText.CANCELLED)}</option></select></div>
    {error && <div className="notice error-state" role="alert">{t(error)}</div>}
    <section className="panel">{loading ? <p role="status" className="muted">{t('Đang tải đơn bán…')}</p> : !orders.length ? <div className="empty"><h3>{t('Chưa có đơn bán')}</h3><p>{t('Các đơn được tạo từ quầy bán hàng sẽ hiển thị tại đây.')}</p></div> : <div className="table-wrap"><table><thead><tr>{['Mã đơn','Chi nhánh','Khách hàng','Ngày tạo','Tổng tiền','Trạng thái',''].map(x => <th key={x}>{t(x)}</th>)}</tr></thead><tbody>{orders.map(o => <tr key={o.salesOrderId}><td><strong>{o.orderCode}</strong></td><td>{o.branchName}</td><td>{o.customerName || t('Khách vãng lai')}</td><td>{o.createdAt ? formatDateTime(new Date(o.createdAt)) : '—'}</td><td>{formatCurrency(Number(o.totalAmount))}</td><td>{t(stateText[o.status] || o.status)}</td><td><button className="link" onClick={() => open(o)}>{t('Chi tiết')}</button></td></tr>)}</tbody></table></div>}</section>
    {selected && <div className="overlay" role="presentation" onMouseDown={e => e.target === e.currentTarget && setSelected(null)}><section className="dialog" role="dialog" aria-modal="true" aria-labelledby="sales-detail-title"><div className="section-title"><div><h2 id="sales-detail-title">{selected.orderCode}</h2><p className="muted">{selected.branchName} · {t(stateText[selected.status] || selected.status)}</p></div><button className="link" onClick={() => setSelected(null)} aria-label={t('Đóng')}>×</button></div><div className="table-wrap"><table><thead><tr><th>{t('Sản phẩm')}</th><th>SKU</th><th>{t('Số lượng')}</th><th>{t('Thành tiền')}</th></tr></thead><tbody>{(selected.items || []).map(line => <tr key={line.variantId}><td>{line.productName}</td><td>{line.sku}</td><td>{line.quantity}</td><td>{formatCurrency(Number(line.lineTotal))}</td></tr>)}</tbody></table></div><p>{t('Tạm tính')}: {formatCurrency(Number(selected.subtotal))} · {t('Chiết khấu')}: {formatCurrency(Number(selected.discountAmount))}</p><p><strong>{t('Tổng tiền')}: {formatCurrency(Number(selected.totalAmount))}</strong></p>{selected.payments?.map(p => <p key={p.paymentId}>{t('Thanh toán')}: {t(p.paymentMethod)} · {t(p.status)} · {formatCurrency(Number(p.amount))}</p>)}<div className="actions wrap">{selected.status === 'PENDING' && <><button className="btn primary" disabled={busy} onClick={() => act('pay')}>{t('Xác nhận đã nhận tiền mặt')}</button><button className="btn outline" disabled={busy} onClick={() => act('cancel')}>{t('Hủy đơn')}</button></>}{selected.status === 'PAID' && canRefund && <button className="btn outline" disabled={busy} onClick={() => act('refund')}>{t('Hoàn tiền')}</button>}</div></section></div>}
  </>;
}
