import React, { useEffect, useState } from 'react';
import { errorMessage, useLanguage } from '../../i18n/index.js';
import { createCustomer, getCustomerPurchaseHistory, listCustomers, updateCustomer } from './api.js';

const emptyForm = { fullName: '', phone: '', email: '', address: '', note: '' };

function CustomerForm({ initial, busy, onCancel, onSubmit, t }) {
  return <div className="overlay" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
    <form className="dialog customer-dialog" onSubmit={onSubmit} aria-labelledby="customer-form-title">
      <div className="section-title"><h2 id="customer-form-title">{initial ? t('Sửa khách hàng') : t('Thêm khách hàng')}</h2><button className="link" type="button" onClick={onCancel} aria-label={t('Đóng')}>×</button></div>
      <label className="field">{t('Họ tên')}<input name="fullName" required maxLength={150} defaultValue={initial?.fullName || ''} autoFocus /></label>
      <label className="field">{t('Số điện thoại')}<input name="phone" maxLength={20} defaultValue={initial?.phone || ''} /></label>
      <label className="field">{t('Email')}<input name="email" type="email" maxLength={255} defaultValue={initial?.email || ''} /></label>
      <label className="field">{t('Địa chỉ')}<input name="address" maxLength={255} defaultValue={initial?.address || ''} /></label>
      <label className="field">{t('Ghi chú')}<textarea name="note" maxLength={255} defaultValue={initial?.note || ''} rows={3} /></label>
      <div className="actions"><button className="btn primary" disabled={busy}>{busy ? t('Đang lưu…') : t('Lưu thay đổi')}</button><button className="btn outline" type="button" onClick={onCancel}>{t('Hủy')}</button></div>
    </form>
  </div>;
}

const statusLabels = {
  PAID: 'Đã thanh toán', UNPAID: 'Chưa thanh toán', PENDING: 'Chờ thanh toán', PROCESSING: 'Đang xử lý', COMPLETED: 'Hoàn tất',
  FULFILLED: 'Đã nhận hàng', READY: 'Sẵn sàng', NOTIFIED: 'Đã thông báo', WAITING_STOCK: 'Chờ hàng', CANCELLED: 'Đã hủy',
  REFUNDED: 'Đã hoàn tiền', EXPIRED: 'Hết hạn',
};

export default function CustomersPage({ canEdit = true }) {
  const { t, formatCurrency, formatDateTime } = useLanguage();
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editing, setEditing] = useState(null);
  const [historyCustomer, setHistoryCustomer] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);

  async function reload(search = debouncedQuery) {
    setLoading(true);
    setError('');
    try {
      const result = await listCustomers({ query: search });
      setCustomers(Array.isArray(result) ? result : []);
    } catch (cause) {
      setCustomers([]);
      setError(errorMessage(cause, 'Không tải được danh sách khách hàng.'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { reload(); }, [debouncedQuery]);

  async function saveCustomer(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    const payload = Object.fromEntries(Object.entries({ ...emptyForm, ...values }).map(([key, value]) => [key, String(value).trim() || null]));
    payload.fullName = String(values.fullName || '').trim();
    setBusy(true);
    setError('');
    try {
      if (editing?.customerId) {
        const saved = await updateCustomer(editing.customerId, payload);
        setNotice({ key: 'customer.notice.updated', values: { name: saved?.fullName || payload.fullName } });
      } else {
        // The backend returns the existing profile (and creates nothing) when the phone
        // number is already registered, so say that instead of "added".
        const known = new Set(customers.map((item) => item.customerId));
        const saved = await createCustomer(payload);
        const existed = saved?.customerId && (known.has(saved.customerId) || (payload.phone && saved.fullName !== payload.fullName));
        setNotice(existed
          ? { key: 'customer.notice.phoneExists', values: { phone: saved.phone || payload.phone, name: saved.fullName } }
          : { key: 'customer.notice.created', values: { name: saved?.fullName || payload.fullName } });
      }
      setEditing(null);
      await reload();
    } catch (cause) {
      setError(errorMessage(cause, 'Không lưu được khách hàng.'));
    } finally {
      setBusy(false);
    }
  }

  async function showHistory(customer) {
    setHistoryCustomer(customer);
    setHistory([]);
    setHistoryLoading(true);
    setError('');
    try {
      const result = await getCustomerPurchaseHistory(customer.customerId);
      setHistory(Array.isArray(result) ? result : []);
    } catch (cause) {
      setError(errorMessage(cause, 'Không tải được lịch sử mua.'));
    } finally {
      setHistoryLoading(false);
    }
  }

  return <>
    <div className="toolbar customer-toolbar">
      <input aria-label={t('Tìm khách hàng')} placeholder={t('Tìm theo tên, số điện thoại hoặc email')} value={query} onChange={(event) => setQuery(event.target.value)} />
      <button className="btn primary" onClick={() => { setNotice(''); setEditing({}); }}>{t('+ Thêm khách hàng')}</button>
      <span className="muted small" aria-live="polite">{t('Khách hàng')}: {customers.length}</span>
    </div>
    {error && <div className="notice error-state" role="alert">{t(error)}</div>}
    {notice && <div className={`notice ${notice.key === 'customer.notice.phoneExists' ? 'warning-state' : 'success-state'}`} role="status">{t(notice)}</div>}
    <section className="panel">
      {loading ? <p className="muted" role="status">{t('Đang tải khách hàng…')}</p> : customers.length === 0 ? <div className="empty"><h3>{t('Chưa có khách hàng')}</h3><p>{query ? t('Thử từ khóa tìm kiếm khác.') : t('Khách hàng được tạo sẽ hiển thị tại đây.')}</p></div> :
        <div className="table-wrap"><table><thead><tr><th>{t('Khách hàng')}</th><th>{t('Điện thoại')}</th><th>{t('Email')}</th><th title={t('customer.stats.hint')}>{t('Số đơn')}</th><th title={t('customer.stats.hint')}>{t('Tổng đã mua')}</th><th>{t('Thao tác')}</th></tr></thead><tbody>
          {customers.map((customer) => <tr key={customer.customerId}>
            <td><strong>{customer.fullName}</strong><small className="block muted">{customer.address || '—'}</small></td>
            <td>{customer.phone || '—'}</td><td>{customer.email || '—'}</td><td>{customer.orderCount ?? 0}</td>
            <td>{formatCurrency(Number(customer.totalSpent || 0))}</td>
            <td><div className="actions wrap">{canEdit && <button className="link" onClick={() => { setNotice(''); setEditing(customer); }}>{t('Sửa')}</button>}<button className="link" onClick={() => showHistory(customer)}>{t('Lịch sử mua')}</button></div></td>
          </tr>)}
        </tbody></table></div>}
    </section>

    {editing && <CustomerForm initial={editing.customerId ? editing : null} busy={busy} onCancel={() => setEditing(null)} onSubmit={saveCustomer} t={t} />}
    {historyCustomer && <div className="overlay" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setHistoryCustomer(null)}>
      <section className="dialog customer-dialog" role="dialog" aria-modal="true" aria-labelledby="customer-history-title">
        <div className="section-title"><div><h2 id="customer-history-title">{t('Lịch sử mua')}</h2><p className="muted">{historyCustomer.fullName}</p></div><button className="link" onClick={() => setHistoryCustomer(null)} aria-label={t('Đóng')}>×</button></div>
        {historyLoading ? <p className="muted" role="status">{t('Đang tải lịch sử…')}</p> : history.length === 0 ? <div className="empty"><h3>{t('Chưa có giao dịch')}</h3><p>{t('customer.history.emptyHint')}</p></div> :
          <div className="table-wrap"><table><thead><tr><th>{t('Mã đơn')}</th><th>{t('Loại')}</th><th>{t('Chi nhánh')}</th><th>{t('Thời gian')}</th><th>{t('Trạng thái')}</th><th>{t('Giá trị')}</th></tr></thead><tbody>
            {history.map((item) => <tr key={`${item.type}-${item.id}`}><td>{item.orderCode}</td><td>{item.type === 'SALE' ? t('Bán hàng') : t('Đặt trước')}</td><td>{item.branchName}</td><td>{item.createdAt ? formatDateTime(new Date(item.createdAt)) : '—'}</td><td>{t(statusLabels[item.status] || item.status)}</td><td>{formatCurrency(Number(item.totalAmount || 0))}</td></tr>)}
          </tbody></table></div>}
        <div className="actions customer-dialog-actions"><button className="btn outline" onClick={() => setHistoryCustomer(null)}>{t('Đóng')}</button></div>
      </section>
    </div>}
  </>;
}
