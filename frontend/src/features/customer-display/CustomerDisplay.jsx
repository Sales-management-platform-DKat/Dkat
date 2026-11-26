import React, { useEffect, useRef, useState } from 'react';
import { apiAssetUrl } from '../../auth-client.js';
import { createDisplaySubscriber } from './channel.js';
import './customer-display.css';

const BRAND_URL = `${import.meta.env.BASE_URL}brand/`;
const PAID_HOLD_MS = 9000;
const money = (value) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(value) || 0);
const METHODS = { CASH: 'Tiền mặt', BANK_TRANSFER: 'Chuyển khoản', CARD: 'Thẻ', OTHER: 'Khác' };

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const timer = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(timer); }, []);
  return <time className="cd-clock" dateTime={now.toISOString()}>
    <b>{now.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</b>
    <span>{now.toLocaleDateString('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' })}</span>
  </time>;
}

function Logo() {
  return <span className="cd-logo"><img className="cd-logo-light" src={`${BRAND_URL}dkat-logo-light.svg`} alt="DKat" /><img className="cd-logo-dark" src={`${BRAND_URL}dkat-logo-dark.svg`} alt="" /></span>;
}

function Welcome({ connected }) {
  return <section className="cd-welcome">
    <img className="cd-welcome-mark" src={`${BRAND_URL}dkat-icon-light.svg`} alt="" />
    <h1>Chào mừng quý khách</h1>
    <p>Vui lòng chờ nhân viên quét sản phẩm. Thông tin đơn hàng sẽ hiển thị tại đây.</p>
    {!connected && <small className="cd-waiting">Đang chờ kết nối với quầy thanh toán…</small>}
  </section>;
}

function ItemImage({ src, name }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return <span className="cd-item-thumb is-empty" aria-hidden="true">{(name || '?').slice(0, 1).toUpperCase()}</span>;
  return <img className="cd-item-thumb" src={apiAssetUrl(src)} alt="" onError={() => setFailed(true)} />;
}

/**
 * Read-only screen for customers. It renders whatever the POS window sends and
 * has no controls that could change an order.
 */
export default function CustomerDisplay() {
  const [state, setState] = useState(null);
  const [connected, setConnected] = useState(false);
  const [paidHold, setPaidHold] = useState(null);
  const listRef = useRef(null);

  useEffect(() => {
    document.title = 'DKat · Màn hình khách hàng';
    document.documentElement.classList.add('cd-root');
    const subscriber = createDisplaySubscriber({ onState: setState, onConnectionChange: setConnected });
    return () => { subscriber.destroy(); document.documentElement.classList.remove('cd-root'); };
  }, []);

  // Keep the "paid" screen up for a moment even if the POS starts the next sale.
  useEffect(() => {
    if (state?.status !== 'paid') return undefined;
    setPaidHold(state);
    const timer = setTimeout(() => setPaidHold(null), PAID_HOLD_MS);
    return () => clearTimeout(timer);
  }, [state?.status, state?.orderCode]);

  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [state?.items?.length, state?.updatedAt]);

  const view = paidHold && (!state || state.status === 'idle' || state.status === 'paid') ? paidHold : state;
  const status = view?.status || 'idle';

  return <div className={`cd-screen cd-status-${status}`}>
    <header className="cd-header">
      <div className="cd-brand"><Logo /><div><b>{view?.storeName || 'DKat'}</b>{view?.branchName && <span>{view.branchName}</span>}</div></div>
      <div className="cd-header-right">
        <span className={`cd-connection${connected ? ' is-on' : ''}`} title={connected ? 'Đã kết nối quầy' : 'Mất kết nối quầy'}><i />{connected ? 'Đang phục vụ' : 'Chờ kết nối'}</span>
        <Clock />
        <button type="button" className="cd-fullscreen" onClick={() => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.())} aria-label="Toàn màn hình">⛶</button>
      </div>
    </header>

    {status === 'idle' || (status !== 'paid' && !view?.items?.length) ? <Welcome connected={connected} />
      : status === 'paid' ? <section className="cd-paid" role="status">
        <span className="cd-paid-icon" aria-hidden="true">✓</span>
        <h1>Thanh toán thành công</h1>
        <p className="cd-paid-total">{money(view.total)}</p>
        {view.change > 0 && <p className="cd-paid-change">Tiền thừa trả khách: <b>{money(view.change)}</b></p>}
        {view.orderCode && <p className="cd-paid-code">Mã đơn hàng: <b>{view.orderCode}</b></p>}
        <p className="cd-thanks">Cảm ơn quý khách và hẹn gặp lại!</p>
      </section>
        : <main className="cd-main">
          <section className="cd-items" aria-label="Sản phẩm đang mua">
            <div className="cd-items-head"><span>Sản phẩm</span><span>SL</span><span>Đơn giá</span><span>Thành tiền</span></div>
            <ol ref={listRef}>{view.items.map((item) => <li key={item.key} className="cd-item">
              <ItemImage src={item.imageUrl} name={item.name} />
              <div className="cd-item-name"><b>{item.name}</b>{item.variantName && <small>{item.variantName}</small>}</div>
              <span className="cd-item-qty">{item.quantity}</span>
              <span className="cd-item-price">{money(item.unitPrice)}</span>
              <b className="cd-item-total">{money(item.lineTotal)}</b>
            </li>)}</ol>
          </section>
          <aside className="cd-summary" aria-live="polite">
            {status === 'paying' && <div className="cd-paying"><i aria-hidden="true" />Đang thanh toán{view.paymentMethod ? ` · ${METHODS[view.paymentMethod] || view.paymentMethod}` : ''}</div>}
            <dl>
              <div><dt>Số lượng</dt><dd>{view.itemCount} sản phẩm</dd></div>
              <div><dt>Tổng tiền hàng</dt><dd>{money(view.subtotal)}</dd></div>
              <div className="cd-discount"><dt>Giảm giá</dt><dd>{view.discount ? `− ${money(view.discount)}` : money(0)}</dd></div>
            </dl>
            <div className="cd-grand"><span>{status === 'paying' ? 'Quý khách cần thanh toán' : 'Tổng thanh toán'}</span><strong>{money(view.total)}</strong></div>
            {view.tendered != null && <dl className="cd-cash">
              <div><dt>Khách đưa</dt><dd>{money(view.tendered)}</dd></div>
              <div><dt>Tiền thừa</dt><dd>{view.change != null ? money(view.change) : '—'}</dd></div>
            </dl>}
            {view.orderCode && <p className="cd-order-code">Mã đơn: {view.orderCode}</p>}
          </aside>
        </main>}
    <footer className="cd-footer">Cảm ơn quý khách đã mua sắm · Powered by DKat</footer>
  </div>;
}
