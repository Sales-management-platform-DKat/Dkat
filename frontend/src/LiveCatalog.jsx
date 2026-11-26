import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Select } from './components/ui.jsx';
import { money } from './domain.js';
import { errorMessage, useLanguage } from './i18n/index.js';
import './product-catalog.css';

// Public website backed by the real API (FR-07): GET /public/branches, GET /public/products, POST /preorders.
// Enabled when VITE_PUBLIC_STORE_ID is set; otherwise main.jsx keeps the browser-only demo catalog.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
export const PUBLIC_STORE_ID = Number(import.meta.env.VITE_PUBLIC_STORE_ID) || null;
const PAGE_SIZE = 6;

async function publicRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!response.ok) {
    const body = data?.detail && typeof data.detail === 'object' && !Array.isArray(data.detail) ? data.detail : data;
    const error = new Error(body?.message || (typeof data?.detail === 'string' ? data.detail : 'Không thể xử lý yêu cầu.'));
    error.status = response.status;
    error.code = body?.code;
    error.details = Array.isArray(body?.details) ? body.details : [];
    throw error;
  }
  return data;
}

const FIELD_LABELS = {
  'customer.fullName': 'Họ tên', 'customer.phone': 'Số điện thoại', 'customer.email': 'Email',
  'customer.address': 'Địa chỉ', items: 'Sản phẩm', note: 'Ghi chú',
};

function PreorderDialog({ item, branch, onClose, onCreated }) {
  const { t, formatNumber } = useLanguage();
  const [form, setForm] = useState({ name: '', phone: '', email: '', address: '', note: '', quantity: 1 });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState('');
  const [created, setCreated] = useState(null);
  useEffect(() => { const esc = (e) => { if (e.key === 'Escape' && !busy) onClose(); }; window.addEventListener('keydown', esc); return () => window.removeEventListener('keydown', esc); }, [onClose, busy]);
  const update = (e) => setForm((c) => ({ ...c, [e.target.name]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    const next = {};
    if (!form.name.trim()) next.name = 'Vui lòng nhập họ tên.';
    if (!/^0\d{9}$/.test(form.phone.trim())) next.phone = 'Nhập số điện thoại gồm 10 chữ số, bắt đầu bằng 0.';
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) next.email = 'Email chưa đúng định dạng.';
    if (!form.address.trim()) next.address = 'Vui lòng nhập địa chỉ.';
    const quantity = Number(form.quantity);
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 100) next.quantity = 'Số lượng từ 1 đến 100.';
    setErrors(next);
    setServerError('');
    if (Object.keys(next).length) return;
    setBusy(true);
    try {
      const customer = { fullName: form.name.trim(), phone: form.phone.trim(), address: form.address.trim() };
      if (form.email.trim()) customer.email = form.email.trim();
      const result = await publicRequest('/preorders', {
        method: 'POST',
        body: JSON.stringify({ branchId: branch.branchId, customer, items: [{ variantId: item.variant.variantId, quantity }], note: form.note.trim() || null }),
      });
      setCreated(result);
      onCreated();
    } catch (error) {
      const reasons = error.details.map((d) => `${t(FIELD_LABELS[d.field] || d.field)}: ${t(d.reason)}`).join('; ');
      setServerError(error.code === 'VARIANT_IN_STOCK' ? 'Sản phẩm vừa có hàng tại chi nhánh này, mời bạn mua trực tiếp tại cửa hàng.'
        : error.code === 'RATE_LIMIT_EXCEEDED' ? 'Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau ít phút.'
          : { key: 'catalog.preorder.failed', values: { reason: t(errorMessage(error, 'Không gửi được yêu cầu đặt trước.')) + (reasons ? ` (${reasons})` : '') } });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="catalog-overlay" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <section className="catalog-dialog" role="dialog" aria-modal="true" aria-labelledby="live-preorder-title">
        <button className="catalog-close" type="button" aria-label={t('Đóng')} disabled={busy} onClick={onClose}>×</button>
        {created ? (
          <div className="preview-confirmation">
            <span className="preview-check" aria-hidden="true">✓</span>
            <span className="preview-label">{t('ĐÃ GỬI ĐẾN CỬA HÀNG')}</span>
            <h2 id="live-preorder-title">{t('Đặt trước thành công')}</h2>
            <p>{t('Mã đơn')} <b>{created.preorderCode}</b></p>
            <dl>
              <div><dt>{t('Sản phẩm')}</dt><dd>{item.product.name} · {item.variant.variantName}</dd></div>
              <div><dt>{t('Số lượng')}</dt><dd>{formatNumber(created.items?.[0]?.quantity ?? form.quantity)}</dd></div>
              <div><dt>{t('Tạm tính')}</dt><dd>{money(Number(created.totalAmount))}</dd></div>
              <div><dt>{t('Chi nhánh')}</dt><dd>{branch.name}</dd></div>
              <div><dt>{t('Trạng thái')}</dt><dd>{t('Chờ hàng về')}</dd></div>
            </dl>
            <p>{t('Cửa hàng sẽ nhắn SMS hoặc email cho bạn ngay khi hàng về và được giữ cho bạn.')}</p>
            <Button onClick={onClose}>{t('Quay lại danh mục')}</Button>
          </div>
        ) : (
          <>
            <span className="preview-label">{t('ĐẶT TRƯỚC SẢN PHẨM HẾT HÀNG')}</span>
            <h2 id="live-preorder-title">{t('Thông tin đặt trước')}</h2>
            <div className="preorder-product-summary"><b>{item.product.name}</b><span>{item.variant.sku} · {item.variant.variantName}</span><strong>{money(Number(item.variant.price))}</strong></div>
            <form className="preorder-preview-form" onSubmit={submit} noValidate>
              <label>{t('Họ tên')} *<input name="name" autoComplete="name" value={form.name} onChange={update} aria-invalid={!!errors.name} />{errors.name && <small className="field-error">{t(errors.name)}</small>}</label>
              <label>{t('Số điện thoại')} *<input name="phone" type="tel" autoComplete="tel" inputMode="numeric" value={form.phone} onChange={update} aria-invalid={!!errors.phone} />{errors.phone && <small className="field-error">{t(errors.phone)}</small>}</label>
              <label>{t('Email')}<input name="email" type="email" autoComplete="email" value={form.email} onChange={update} aria-invalid={!!errors.email} />{errors.email && <small className="field-error">{t(errors.email)}</small>}</label>
              <label>{t('Địa chỉ')} *<input name="address" autoComplete="street-address" value={form.address} onChange={update} aria-invalid={!!errors.address} />{errors.address && <small className="field-error">{t(errors.address)}</small>}</label>
              <label>{t('Ghi chú')}<textarea name="note" rows="2" maxLength="255" value={form.note} onChange={update} /></label>
              <label>{t('Số lượng')}<input name="quantity" type="number" min="1" max="100" value={form.quantity} onChange={update} />{errors.quantity && <small className="field-error">{t(errors.quantity)}</small>}</label>
              <div className="preorder-preview-branch"><span>{t('Chi nhánh nhận hàng')}</span><b>{branch.name}</b></div>
              {serverError && <p className="field-error" role="alert">{t(serverError)}</p>}
              <div className="catalog-form-actions"><Button variant="outline" type="button" disabled={busy} onClick={onClose}>{t('Hủy')}</Button><Button type="submit" disabled={busy} loading={busy}>{busy ? t('Đang gửi…') : t('Gửi đặt trước')}</Button></div>
            </form>
          </>
        )}
      </section>
    </div>
  );
}

export function LiveCatalog() {
  const { t, formatNumber } = useLanguage();
  const [branches, setBranches] = useState([]);
  const [branchId, setBranchId] = useState(null);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [stock, setStock] = useState('all');
  const [page, setPage] = useState(1);
  const [preorder, setPreorder] = useState(null);

  const load = useCallback(async () => {
    setError('');
    try {
      const [b, p] = await Promise.all([
        publicRequest(`/public/branches?storeId=${PUBLIC_STORE_ID}`),
        publicRequest(`/public/products?storeId=${PUBLIC_STORE_ID}`),
      ]);
      setBranches(b);
      setProducts(p);
      setBranchId((current) => (b.some((x) => x.branchId === current) ? current : b[0]?.branchId ?? null));
    } catch (e) {
      setError(errorMessage(e, 'Không tải được danh mục.'));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const branch = branches.find((b) => b.branchId === branchId);
  const items = useMemo(() => products.flatMap((product) => product.variants.map((variant) => ({
    product, variant, inStock: variant.stock.find((s) => s.branchId === branchId)?.status === 'IN_STOCK',
  }))), [products, branchId]);
  const q = query.trim().toLocaleLowerCase('vi');
  const filtered = items.filter((i) => (!q || `${i.product.name} ${i.variant.variantName} ${i.variant.sku}`.toLocaleLowerCase('vi').includes(q))
    && (stock === 'all' || (stock === 'available' ? i.inStock : !i.inStock)));
  useEffect(() => setPage(1), [query, stock, branchId]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <main className="catalog-page">
      <div className="catalog-heading"><div><span className="eyebrow">{t('DKAT / CỬA HÀNG')}</span><h1>{t('Danh mục sản phẩm')}</h1><p>{t('Xem tình trạng hàng tại chi nhánh. Sản phẩm hết hàng có thể đặt trước, cửa hàng sẽ báo khi hàng về.')}</p></div>
        <label className="catalog-branch">{t('Chi nhánh')}<Select value={branchId ?? ''} onChange={(e) => setBranchId(Number(e.target.value))}>{branches.map((b) => <option key={b.branchId} value={b.branchId}>{b.name}</option>)}</Select></label></div>
      {branch && <p className="catalog-results-count">{branch.address}{branch.phone ? ` · ${branch.phone}` : ''}</p>}
      <section className="catalog-filters" aria-label={t('Tìm và lọc sản phẩm')}>
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('Tìm theo tên hoặc SKU')} aria-label={t('Tìm sản phẩm')} />
        <Select aria-label={t('Tình trạng')} value={stock} onChange={(e) => setStock(e.target.value)}><option value="all">{t('Mọi tình trạng')}</option><option value="available">{t('Còn hàng')}</option><option value="out">{t('Hết hàng')}</option></Select>
        <Button variant="outline" type="button" onClick={load}>{t('Làm mới')}</Button>
      </section>
      {loading ? <div className="catalog-empty" role="status"><p>{t('Đang tải danh mục…')}</p></div>
        : error ? <div className="catalog-empty" role="alert"><h2>{t('Không tải được danh mục')}</h2><p>{t(error)}</p><p className="muted">{t('Kiểm tra kết nối mạng rồi bấm Thử lại. Nếu vẫn lỗi, hãy liên hệ cửa hàng.')}</p><Button variant="outline" onClick={load}>{t('Thử lại')}</Button></div>
          : visible.length ? <>
            <div className="catalog-results-count">{t('catalog.results', { count: formatNumber(filtered.length) })}</div>
            <section className="catalog-grid" aria-label={t('Danh sách sản phẩm')}>
              {visible.map((i) => <article className="catalog-product-card" key={i.variant.variantId}>
                <div className="catalog-product-art">{i.product.imageUrl ? <img src={i.product.imageUrl} alt={i.product.name} /> : <span aria-hidden="true">◇</span>}</div>
                <div className="catalog-product-info"><span className="catalog-category">{i.product.categoryName}</span><h2>{i.product.name}</h2>
                  <span className="catalog-sku">{i.variant.variantName} · SKU {i.variant.sku}</span><strong>{money(Number(i.variant.price))}</strong>
                  <span className={`catalog-stock ${i.inStock ? 'is-available' : 'is-out'}`}>{i.inStock ? t('Còn hàng') : t('Hết hàng')}</span>
                  <div className="catalog-card-actions">{!i.inStock && branch && <Button onClick={() => setPreorder(i)}>{t('Đặt trước')}</Button>}</div></div>
              </article>)}
            </section>
            {pageCount > 1 && <nav className="catalog-pagination" aria-label={t('Phân trang')}><Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t('Trước')}</Button><span>{t('catalog.page', { page: formatNumber(page), total: formatNumber(pageCount) })}</span><Button variant="outline" disabled={page >= pageCount} onClick={() => setPage(page + 1)}>{t('Tiếp')}</Button></nav>}
          </> : <div className="catalog-empty"><h2>{t('Không tìm thấy sản phẩm')}</h2><p>{t('Thử đổi từ khóa hoặc bộ lọc.')}</p></div>}
      {preorder && branch && <PreorderDialog item={preorder} branch={branch} onClose={() => setPreorder(null)} onCreated={load} />}
    </main>
  );
}
