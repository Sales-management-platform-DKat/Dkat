import React, { useEffect, useMemo, useState } from 'react';
import { useLanguage } from '../../i18n/index.js';
import { listInventory } from '../inventory/api.js';
import { listProducts } from '../products/api.js';
import { confirmSalesOrderPayment, createSalesOrder } from '../orders/api.js';
import { quickSearchCustomers } from '../customers/api.js';

function PaymentDialog({ order, busy, onCancel, onSubmit, t, formatCurrency }) {
  return <div className="overlay" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
    <form className="dialog payment-dialog" onSubmit={onSubmit} aria-labelledby="payment-title">
      <div className="section-title"><div><h2 id="payment-title">{t('Xác nhận thanh toán')}</h2><p className="muted">{order.orderCode}</p></div></div>
      <div className="payment-total"><span>{t('Khách cần thanh toán')}</span><strong>{formatCurrency(Number(order.totalAmount))}</strong></div>
      <label className="field">{t('Phương thức thanh toán')}<select name="paymentMethod"><option value="CASH">{t('Tiền mặt')}</option><option value="BANK_TRANSFER">{t('Chuyển khoản')}</option><option value="CARD">{t('Thẻ')}</option><option value="OTHER">{t('Khác')}</option></select></label>
      <p className="notice">{t('Chỉ xác nhận sau khi bạn đã kiểm tra và nhận tiền thực tế.')}</p>
      <div className="actions"><button className="btn primary" disabled={busy}>{busy ? t('Đang lưu…') : t('Đã nhận thanh toán')}</button><button className="btn outline" type="button" onClick={onCancel}>{t('Để xử lý sau')}</button></div>
    </form>
  </div>;
}

export default function POSPage({ branchId }) {
  const { t, formatCurrency } = useLanguage();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [inventory, setInventory] = useState([]);
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState([]);
  const [discount, setDiscount] = useState('0');
  const [customerId, setCustomerId] = useState('');
  const [customerQuery, setCustomerQuery] = useState('');
  const [customerResults, setCustomerResults] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pendingOrder, setPendingOrder] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState('CASH');

  useEffect(() => { const timer = setTimeout(() => setSearch(query.trim()), 250); return () => clearTimeout(timer); }, [query]);
  useEffect(() => {
    if (customerQuery.trim().length < 2) { setCustomerResults([]); return; }
    let active = true;
    const timer = setTimeout(() => quickSearchCustomers(customerQuery.trim()).then((rows) => {
      if (active) setCustomerResults(Array.isArray(rows) ? rows : []);
    }).catch(() => { if (active) setCustomerResults([]); }), 250);
    return () => { active = false; clearTimeout(timer); };
  }, [customerQuery]);

  async function loadCatalog(term = search) {
    setLoading(true); setError('');
    const results = await Promise.allSettled([
      listInventory({ branchId, keyword: term, page: 1, size: 100 }),
      listProducts({ keyword: term, page: 1, size: 100, sort: 'name' }),
    ]);
    const failed = results.find((result) => result.status === 'rejected');
    if (failed) { setInventory([]); setProducts([]); setError(failed.reason?.message || t('Không tải được danh mục bán hàng.')); }
    else { setInventory(results[0].value || []); setProducts(results[1].value || []); }
    setLoading(false);
  }

  useEffect(() => { loadCatalog(); }, [search, branchId]);

  const catalog = useMemo(() => {
    const stockById = new Map(inventory.map((item) => [item.variantId, item]));
    return products.flatMap((product) => product.variants.map((variant) => {
      const stock = stockById.get(variant.variant_id);
      return stock ? { ...variant, ...stock } : null;
    })).filter(Boolean);
  }, [inventory, products]);
  const subtotal = cart.reduce((sum, line) => sum + Number(line.price) * line.quantity, 0);
  const total = Math.max(0, subtotal - Math.max(0, Number(discount || 0)));

  function add(item) {
    setError('');
    setCart((current) => {
      const existing = current.find((line) => line.variantId === item.variant_id);
      if (existing) {
        if (existing.quantity >= item.available) { setError(t('Số lượng vượt quá tồn khả dụng.')); return current; }
        return current.map((line) => line.variantId === item.variant_id ? { ...line, quantity: line.quantity + 1 } : line);
      }
      if (item.available < 1) { setError(t('Sản phẩm đã hết hàng tại chi nhánh này.')); return current; }
      return [...current, { variantId: item.variant_id, name: item.productName, variantName: item.variant_name, sku: item.sku, price: Number(item.price), quantity: 1, available: item.available }];
    });
  }

  function adjust(variantId, delta) {
    setCart((current) => current.flatMap((line) => {
      if (line.variantId !== variantId) return [line];
      const quantity = line.quantity + delta;
      if (quantity < 1) return [];
      if (quantity > line.available) { setError(t('Số lượng vượt quá tồn khả dụng.')); return [line]; }
      return [{ ...line, quantity }];
    }));
  }

  async function createOrder() {
    if (!cart.length) return;
    setBusy(true); setError('');
    try {
      const created = await createSalesOrder({
        branchId,
        customerId: customerId ? Number(customerId) : null,
        discountAmount: Number(discount || 0),
        items: cart.map((line) => ({ variantId: line.variantId, quantity: line.quantity })),
      });
      setPendingOrder(created); setCart([]); setDiscount('0'); setNotice(t('Đơn bán đã được tạo ở trạng thái chờ thanh toán.'));
    } catch (cause) { setError(cause.message || t('Không tạo được đơn bán.')); }
    finally { setBusy(false); }
  }

  async function submitPayment(event) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const form = new FormData(event.currentTarget);
      await confirmSalesOrderPayment(pendingOrder.salesOrderId, { paymentMethod: form.get('paymentMethod') || paymentMethod, amount: Number(pendingOrder.totalAmount) });
      setPendingOrder(null); setNotice(t('Đã ghi nhận thanh toán.')); await loadCatalog();
    } catch (cause) { setError(cause.message || t('Không xác nhận được thanh toán.')); }
    finally { setBusy(false); }
  }

  return <>
    <div className="pos-live-layout">
      <section className="panel pos-live-catalog"><div className="toolbar"><input aria-label={t('Tìm sản phẩm bán hàng')} placeholder={t('Tìm theo tên hoặc SKU')} value={query} onChange={(event) => setQuery(event.target.value)} /></div>
        {loading ? <p className="muted" role="status">{t('Đang tải sản phẩm…')}</p> : catalog.length === 0 ? <div className="empty"><h3>{t('Không có sản phẩm khả dụng')}</h3><p>{t('Kiểm tra tồn kho hoặc từ khóa tìm kiếm.')}</p></div> : <div className="pos-live-grid">{catalog.map((item) => <button className="pos-live-item" key={item.variantId} disabled={item.available < 1} onClick={() => add(item)}><span className="pos-live-item-name">{item.productName}</span><small>{item.variantName} · {item.sku}</small><strong>{formatCurrency(Number(item.price))}</strong><span className="muted small">{t('Khả dụng')}: {item.available}</span></button>)}</div>}
      </section>
      <section className="panel pos-live-checkout"><div className="section-title"><h3>{t('Đơn hàng hiện tại')}</h3><button className="link" onClick={() => { setCart([]); setCustomerId(''); setSelectedCustomer(null); setCustomerQuery(''); setDiscount('0'); }}>{t('Xóa giỏ hàng')}</button></div>
        {cart.length ? <div className="pos-live-lines">{cart.map((line) => <div className="pos-live-line" key={line.variantId}><div><strong>{line.name}</strong><small className="block muted">{line.sku} · {line.variantName}</small><small>{formatCurrency(line.price * line.quantity)}</small></div><div className="actions"><button className="icon-btn" aria-label={t('Giảm số lượng')} onClick={() => adjust(line.variantId, -1)}>−</button><span>{line.quantity}</span><button className="icon-btn" aria-label={t('Tăng số lượng')} onClick={() => adjust(line.variantId, 1)}>+</button></div></div>)}</div> : <div className="empty"><p>{t('Chọn sản phẩm để bắt đầu đơn bán.')}</p></div>}
        <label className="field">{t('Tìm khách hàng (tùy chọn)')}<input value={customerQuery} onChange={(event) => { setCustomerQuery(event.target.value); setSelectedCustomer(null); setCustomerId(''); }} placeholder={t('Tên hoặc số điện thoại')} /></label>
        {customerResults.length > 0 && <div className="customer-suggestions" role="listbox">{customerResults.map((item) => <button type="button" role="option" aria-selected={selectedCustomer?.customerId === item.customerId} key={item.customerId} onClick={() => { setSelectedCustomer(item); setCustomerId(String(item.customerId)); setCustomerQuery(`${item.fullName} · ${item.phone || ''}`); setCustomerResults([]); }}>{item.fullName} · {item.phone || item.email || item.customerId}</button>)}</div>}
        {selectedCustomer && <small className="muted">{t('Đã chọn khách hàng')}: {selectedCustomer.fullName}</small>}
        <label className="field">{t('Chiết khấu')}<input type="number" min="0" max={subtotal} step="0.01" value={discount} onChange={(event) => setDiscount(event.target.value)} /></label>
        <div className="pos-live-totals"><div className="pos-live-total"><span>{t('Tạm tính')}</span><strong>{formatCurrency(subtotal)}</strong></div><div className="pos-live-total grand-total"><span>{t('Khách cần thanh toán')}</span><strong>{formatCurrency(total)}</strong></div></div>
        <button className="btn primary pos-live-submit" disabled={busy || !cart.length} onClick={createOrder}>{busy ? t('Đang lưu…') : t('Tạo đơn chờ thanh toán')}</button>
        <p className="muted small">{t('Thanh toán chỉ được ghi nhận sau khi kiểm tra tiền thực tế.')}</p>
      </section>
    </div>
    {error && <div className="notice error-state" role="alert">{error}</div>}{notice && <div className="notice success-state" role="status">{notice}</div>}
    {pendingOrder && <PaymentDialog order={pendingOrder} busy={busy} onCancel={() => setPendingOrder(null)} onSubmit={submitPayment} t={t} formatCurrency={formatCurrency} />}
  </>;
}
