import React, { useEffect, useMemo, useRef, useState } from 'react';
import { apiAssetUrl } from '../../auth-client.js';
import { useLanguage } from '../../i18n/index.js';
import { confirmAction, Dialog, notify } from '../../components/overlay/index.js';
import { EmptyState, ErrorState, LoadingState } from '../../components/states.jsx';
import { listInventory } from '../inventory/api.js';
import { listProducts } from '../products/api.js';
import { cancelSalesOrder, confirmSalesOrderPayment, createSalesOrder } from '../orders/api.js';
import { quickSearchCustomers } from '../customers/api.js';
import { displayState } from '../customer-display/channel.js';
import { useCustomerDisplay } from '../customer-display/useCustomerDisplay.js';
import PreorderDialog from '../preorders/PreorderDialog.jsx';

const METHODS = [['CASH', 'Tiền mặt'], ['BANK_TRANSFER', 'Chuyển khoản'], ['CARD', 'Thẻ'], ['OTHER', 'Khác']];
const QUICK_CASH = [50000, 100000, 200000, 500000];

function PaymentDialog({ order, method, setMethod, tendered, setTendered, busy, onConfirm, onLater, onCancelOrder, t, formatCurrency }) {
  const total = Number(order.totalAmount);
  const cash = method === 'CASH';
  const given = Number(tendered);
  const short = cash && tendered !== '' && given < total;
  const change = cash && tendered !== '' && given >= total ? given - total : null;
  const suggestions = [total, ...QUICK_CASH.map((note) => Math.ceil(total / note) * note)].filter((value, index, all) => value >= total && all.indexOf(value) === index).slice(0, 4);
  return <Dialog open size="md" title={t('Thanh toán')} eyebrow={order.orderCode} busy={busy} onClose={onLater} className="payment-dialog"
    footer={<>
      <button className="btn outline danger" type="button" disabled={busy} onClick={onCancelOrder}>{t('Hủy đơn')}</button>
      <button className="btn outline" type="button" disabled={busy} onClick={onLater}>{t('Để xử lý sau')}</button>
      <button className="btn primary" type="button" disabled={busy || short || (cash && tendered === '')} onClick={onConfirm}>{busy ? t('Đang lưu…') : t('Đã nhận thanh toán')}</button>
    </>}>
    <div className="payment-total"><span>{t('Khách cần thanh toán')}</span><strong>{formatCurrency(total)}</strong></div>
    <div className="segmented-methods" role="radiogroup" aria-label={t('Phương thức thanh toán')}>
      {METHODS.map(([value, label]) => <button key={value} type="button" role="radio" aria-checked={method === value} className={method === value ? 'is-active' : ''} onClick={() => setMethod(value)}>{t(label)}</button>)}
    </div>
    {cash && <>
      <label className="dk-field"><span className="dk-field-label">{t('Tiền khách đưa')}</span><input type="number" min={total} step="1000" inputMode="numeric" value={tendered} autoFocus onChange={(event) => setTendered(event.target.value)} aria-invalid={short || undefined} /></label>
      <div className="quick-cash">{suggestions.map((value) => <button key={value} type="button" className="btn outline" onClick={() => setTendered(String(value))}>{formatCurrency(value)}</button>)}</div>
      {short && <p className="dk-field-error" role="alert">{t('Số tiền khách đưa chưa đủ.')}</p>}
      {change !== null && <div className="payment-change"><span>{t('Tiền thừa trả khách')}</span><strong>{formatCurrency(change)}</strong></div>}
    </>}
    {!cash && <p className="notice">{t('Chỉ xác nhận sau khi đã kiểm tra tiền về tài khoản / máy POS. Hệ thống chưa tích hợp cổng thanh toán hay mã QR.')}</p>}
  </Dialog>;
}

export default function POSPage({ branchId, branch, storeName }) {
  const { t, formatCurrency } = useLanguage();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [inventory, setInventory] = useState([]);
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState([]);
  const [discount, setDiscount] = useState('');
  const [customerQuery, setCustomerQuery] = useState('');
  const [customerResults, setCustomerResults] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [pendingOrder, setPendingOrder] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState('CASH');
  const [tendered, setTendered] = useState('');
  const [paidOrder, setPaidOrder] = useState(null);
  const [preorderFor, setPreorderFor] = useState(null);
  const creating = useRef(false);

  useEffect(() => { const timer = setTimeout(() => setSearch(query.trim()), 250); return () => clearTimeout(timer); }, [query]);
  useEffect(() => {
    if (customerQuery.trim().length < 2 || selectedCustomer) { setCustomerResults([]); return undefined; }
    let active = true;
    const timer = setTimeout(() => quickSearchCustomers(customerQuery.trim()).then((rows) => active && setCustomerResults(Array.isArray(rows) ? rows : [])).catch(() => active && setCustomerResults([])), 250);
    return () => { active = false; clearTimeout(timer); };
  }, [customerQuery, selectedCustomer]);

  async function loadCatalog(term = search) {
    if (!branchId) { setLoading(false); return; }
    setLoading(true); setLoadError(null);
    const results = await Promise.allSettled([
      listInventory({ branchId, keyword: term, page: 1, size: 100 }),
      listProducts({ keyword: term, page: 1, size: 100, sort: 'name' }),
    ]);
    const failed = results.find((result) => result.status === 'rejected');
    if (failed) { setInventory([]); setProducts([]); setLoadError(failed.reason); }
    else { setInventory(results[0].value || []); setProducts(results[1].value || []); }
    setLoading(false);
  }
  useEffect(() => { loadCatalog(); }, [search, branchId]);
  useEffect(() => { setCart([]); setPendingOrder(null); }, [branchId]);

  const catalog = useMemo(() => {
    const stockById = new Map(inventory.map((item) => [item.variantId, item]));
    return products.flatMap((product) => product.variants.map((variant) => {
      const stock = stockById.get(variant.variant_id);
      return stock ? { ...variant, ...stock, imageUrl: product.image_url } : null;
    })).filter(Boolean);
  }, [inventory, products]);

  const subtotal = cart.reduce((sum, line) => sum + Number(line.price) * line.quantity, 0);
  const discountValue = Math.min(Math.max(0, Number(discount || 0)), subtotal);
  const total = subtotal - discountValue;

  // What the customer sees on the second screen.
  const display = useMemo(() => {
    if (paidOrder) return displayState({ status: 'paid', storeName, branchName: branch?.name, items: paidOrder.items, discount: paidOrder.discount, tendered: paidOrder.tendered, orderCode: paidOrder.orderCode, paymentMethod: paidOrder.method });
    if (pendingOrder) return displayState({ status: 'paying', storeName, branchName: branch?.name, items: pendingOrder.lines, discount: Number(pendingOrder.discountAmount || 0), tendered: paymentMethod === 'CASH' ? tendered : null, orderCode: pendingOrder.orderCode, paymentMethod });
    return displayState({ storeName, branchName: branch?.name, items: cart, discount: discountValue });
  }, [cart, discountValue, pendingOrder, paidOrder, tendered, paymentMethod, storeName, branch?.name]);
  const customerDisplay = useCustomerDisplay(display);

  function openDisplay() {
    const result = customerDisplay.open();
    if (result.blocked) notify.warning(t('Trình duyệt đã chặn cửa sổ bật lên. Hãy cho phép popup cho trang này hoặc dùng liên kết "Mở trong tab mới".'), { title: t('Không mở được màn hình khách hàng'), duration: 9000 });
    else if (!result.reused) notify.info(t('Đã mở màn hình khách hàng. Kéo cửa sổ sang màn hình phụ và bấm ⛶ để hiển thị toàn màn hình.'));
  }

  const warnLimit = (available) => notify.warning(`${t('Chỉ còn')} ${available} ${t('sản phẩm khả dụng')}.`);

  // Scanners can fire faster than React re-renders: decide inside the state
  // updater so every click sees the latest cart.
  function add(item) {
    if (paidOrder) setPaidOrder(null);
    if (item.available < 1) { setPreorderFor(item.variant_id); return; }
    setCart((current) => {
      const existing = current.find((line) => line.variantId === item.variant_id);
      if (existing) {
        if (existing.quantity >= item.available) { queueMicrotask(() => warnLimit(item.available)); return current; }
        return current.map((line) => line.variantId === item.variant_id ? { ...line, quantity: line.quantity + 1 } : line);
      }
      return [...current, { variantId: item.variant_id, name: item.productName, variantName: item.variant_name, sku: item.sku, price: Number(item.price), quantity: 1, available: item.available, imageUrl: item.imageUrl }];
    });
  }

  function adjust(variantId, delta) {
    setCart((current) => current.flatMap((line) => {
      if (line.variantId !== variantId) return [line];
      const quantity = line.quantity + delta;
      if (quantity < 1) return [];
      if (quantity > line.available) { queueMicrotask(() => warnLimit(line.available)); return [line]; }
      return [{ ...line, quantity }];
    }));
  }

  function clearCart() {
    setCart([]); setSelectedCustomer(null); setCustomerQuery(''); setDiscount('');
  }

  async function createOrder() {
    if (!cart.length || creating.current) return;
    if (Number(discount || 0) > subtotal) { notify.warning(t('Chiết khấu không được lớn hơn tạm tính.')); return; }
    creating.current = true;
    setBusy(true);
    try {
      const created = await createSalesOrder({
        branchId: Number(branchId), customerId: selectedCustomer?.customerId || null,
        discountAmount: discountValue, items: cart.map((line) => ({ variantId: line.variantId, quantity: line.quantity })),
      });
      setPendingOrder({ ...created, lines: cart });
      setPaymentMethod('CASH');
      setTendered('');
      setPaidOrder(null);
    } catch (error) {
      notify.error(error, { title: t('Không tạo được đơn bán') });
      if (error.status === 409) loadCatalog();
    } finally {
      creating.current = false;
      setBusy(false);
    }
  }

  async function confirmPayment() {
    if (!pendingOrder || busy) return;
    setBusy(true);
    try {
      await confirmSalesOrderPayment(pendingOrder.salesOrderId, { paymentMethod, amount: Number(pendingOrder.totalAmount) });
      notify.success(`${t('Đã thanh toán đơn')} ${pendingOrder.orderCode}.`);
      setPaidOrder({ orderCode: pendingOrder.orderCode, items: pendingOrder.lines, discount: Number(pendingOrder.discountAmount || 0), tendered: paymentMethod === 'CASH' ? tendered : null, method: paymentMethod });
      setPendingOrder(null);
      clearCart();
      await loadCatalog();
    } catch (error) {
      notify.error(error, { title: t('Không xác nhận được thanh toán') });
    } finally {
      setBusy(false);
    }
  }

  async function cancelOrder() {
    const result = await confirmAction({ title: t('Hủy đơn chờ thanh toán?'), description: pendingOrder.orderCode, confirmLabel: t('Hủy đơn'), requireReason: true, reasonLabel: t('Lý do hủy') });
    if (!result) return;
    setBusy(true);
    try {
      await cancelSalesOrder(pendingOrder.salesOrderId, result.reason);
      notify.success(`${t('Đã hủy đơn')} ${pendingOrder.orderCode}.`);
      setPendingOrder(null);
      await loadCatalog();
    } catch (error) {
      notify.error(error, { title: t('Không hủy được đơn') });
    } finally {
      setBusy(false);
    }
  }

  if (!branchId || !branch) return <section className="panel"><EmptyState title={t('Chưa chọn chi nhánh')} description={t('Chọn chi nhánh ở thanh trên cùng để bán hàng.')} /></section>;

  return <>
    <div className="pos-topbar">
      <div className="pos-display-control">
        <button type="button" className="btn outline" onClick={openDisplay}><span aria-hidden="true">🖥</span> {t('Màn hình khách hàng')}</button>
        <span className={`display-status${customerDisplay.connected ? ' is-on' : ''}`}><i aria-hidden="true" />{customerDisplay.connected ? t('Đã kết nối') : t('Chưa kết nối')}</span>
        {customerDisplay.blockedUrl && <a className="link" href={customerDisplay.blockedUrl} target="dkat-customer-display" rel="opener" onClick={customerDisplay.dismissBlocked}>{t('Mở trong tab mới')}</a>}
      </div>
    </div>
    <div className="pos-live-layout">
      <section className="panel pos-live-catalog">
        <div className="toolbar"><input aria-label={t('Tìm sản phẩm bán hàng')} placeholder={t('Tìm theo tên hoặc SKU')} value={query} onChange={(event) => setQuery(event.target.value)} autoFocus /></div>
        {loading ? <LoadingState label={t('Đang tải sản phẩm…')} />
          : loadError ? <ErrorState error={loadError} onRetry={() => loadCatalog()} />
            : !catalog.length ? <EmptyState title={t('Không có sản phẩm')} description={t('Kiểm tra từ khóa tìm kiếm hoặc thêm sản phẩm ở màn hình Sản phẩm.')} />
              : <div className="pos-live-grid">{catalog.map((item) => {
                const out = item.available < 1;
                return <div className={`pos-live-item${out ? ' is-out' : ''}`} key={item.variantId}>
                  <button type="button" className="pos-live-item-main" onClick={() => add(item)} aria-label={`${item.productName} ${item.variantName}`}>
                    {item.imageUrl ? <img className="pos-live-thumb" src={apiAssetUrl(item.imageUrl)} alt="" loading="lazy" onError={(event) => { event.currentTarget.hidden = true; }} /> : <span className="pos-live-thumb is-empty" aria-hidden="true">{item.productName.slice(0, 1)}</span>}
                    <span className="pos-live-item-name">{item.productName}</span>
                    <small>{item.variantName} · {item.sku}</small>
                    <strong>{formatCurrency(Number(item.price))}</strong>
                    <span className={`badge ${out ? 'amber' : 'green'}`}>{out ? t('Hết hàng') : `${t('Còn')} ${item.available}`}</span>
                  </button>
                  {out && <button type="button" className="btn outline pos-preorder-btn" onClick={() => setPreorderFor(item.variantId)}>{t('Đặt trước')}</button>}
                </div>;
              })}</div>}
      </section>
      <section className="panel pos-live-checkout">
        <div className="section-title"><h3>{t('Đơn hàng hiện tại')}</h3>{cart.length > 0 && <button className="link danger" onClick={clearCart}>{t('Xóa giỏ hàng')}</button>}</div>
        {paidOrder && !cart.length && <div className="notice success-state">{t('Đã thanh toán')} {paidOrder.orderCode}. {t('Chọn sản phẩm để bắt đầu đơn mới.')}</div>}
        {cart.length ? <div className="pos-live-lines">{cart.map((line) => <div className="pos-live-line" key={line.variantId}>
          <div><strong>{line.name}</strong><small className="block muted">{line.variantName} · {line.sku}</small><small>{formatCurrency(line.price)} × {line.quantity} = <b>{formatCurrency(line.price * line.quantity)}</b></small></div>
          <div className="actions stepper-actions"><button className="icon-btn" aria-label={t('Giảm số lượng')} onClick={() => adjust(line.variantId, -1)}>−</button><span>{line.quantity}</span><button className="icon-btn" aria-label={t('Tăng số lượng')} onClick={() => adjust(line.variantId, 1)}>+</button></div>
        </div>)}</div> : !paidOrder && <EmptyState title={t('Giỏ hàng trống')} description={t('Chọn sản phẩm bên trái để bắt đầu đơn bán.')} icon="⊞" />}
        <label className="field">{t('Khách hàng (tùy chọn)')}<input value={customerQuery} onChange={(event) => { setCustomerQuery(event.target.value); setSelectedCustomer(null); }} placeholder={t('Tìm tên hoặc số điện thoại')} /></label>
        {customerResults.length > 0 && <div className="customer-suggestions" role="listbox">{customerResults.map((item) => <button type="button" role="option" aria-selected={false} key={item.customerId} onClick={() => { setSelectedCustomer(item); setCustomerQuery(`${item.fullName} · ${item.phone || ''}`); setCustomerResults([]); }}>{item.fullName} · {item.phone || item.email || item.customerId}</button>)}</div>}
        <label className="field">{t('Giảm giá (VND)')}<input type="number" min="0" max={subtotal} step="1000" value={discount} placeholder="0" onChange={(event) => setDiscount(event.target.value)} /></label>
        <div className="pos-live-totals">
          <div className="pos-live-total"><span>{t('Tạm tính')}</span><strong>{formatCurrency(subtotal)}</strong></div>
          {discountValue > 0 && <div className="pos-live-total"><span>{t('Giảm giá')}</span><strong>− {formatCurrency(discountValue)}</strong></div>}
          <div className="pos-live-total grand-total"><span>{t('Khách cần thanh toán')}</span><strong>{formatCurrency(total)}</strong></div>
        </div>
        <button className="btn primary pos-live-submit" disabled={busy || !cart.length} onClick={createOrder}>{busy ? t('Đang tạo đơn…') : t('Thanh toán')} →</button>
      </section>
    </div>
    {pendingOrder && <PaymentDialog order={pendingOrder} method={paymentMethod} setMethod={setPaymentMethod} tendered={tendered} setTendered={setTendered} busy={busy}
      t={t} formatCurrency={formatCurrency} onConfirm={confirmPayment} onCancelOrder={cancelOrder}
      onLater={() => { notify.info(`${t('Đơn')} ${pendingOrder.orderCode} ${t('đang chờ thanh toán; xử lý tiếp tại màn hình Đơn bán.')}`); setPendingOrder(null); clearCart(); }} />}
    {preorderFor && <PreorderDialog branch={branch} initialVariantId={preorderFor} t={t} formatCurrency={formatCurrency}
      options={catalog.map((item) => ({ variantId: item.variantId, productName: item.productName, variantName: item.variantName, sku: item.sku, price: item.price, available: item.available }))}
      onClose={() => setPreorderFor(null)} onCreated={() => {}} />}
  </>;
}
