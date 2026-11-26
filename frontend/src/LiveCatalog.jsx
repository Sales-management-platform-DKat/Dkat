import React, { useCallback, useEffect, useState } from 'react';
import { Button, Select } from './components/ui.jsx';
import { money } from './domain.js';
import './product-catalog.css';

// Public website backed by the real API (FR-07): GET /public/branches, /public/categories, /public/products (search),
// /public/products/{id} (detail with per-branch availability), POST /preorders.
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
      const reasons = error.details.map((d) => `${FIELD_LABELS[d.field] || d.field}: ${d.reason}`).join('; ');
      setServerError(error.code === 'VARIANT_IN_STOCK' ? 'Sản phẩm vừa có hàng tại chi nhánh này, mời bạn mua trực tiếp tại cửa hàng.'
        : error.code === 'RATE_LIMIT_EXCEEDED' ? 'Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau ít phút.'
          : `${error.message}${reasons ? ` (${reasons})` : ''}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="catalog-overlay" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <section className="catalog-dialog" role="dialog" aria-modal="true" aria-labelledby="live-preorder-title">
        <button className="catalog-close" type="button" aria-label="Đóng" disabled={busy} onClick={onClose}>×</button>
        {created ? (
          <div className="preview-confirmation">
            <span className="preview-check" aria-hidden="true">✓</span>
            <span className="preview-label">ĐÃ GỬI ĐẾN CỬA HÀNG</span>
            <h2 id="live-preorder-title">Đặt trước thành công</h2>
            <p>Mã đơn <b>{created.preorderCode}</b></p>
            <dl>
              <div><dt>Sản phẩm</dt><dd>{item.product.name} · {item.variant.variantName}</dd></div>
              <div><dt>Số lượng</dt><dd>{created.items?.[0]?.quantity ?? form.quantity}</dd></div>
              <div><dt>Tạm tính</dt><dd>{money(Number(created.totalAmount))}</dd></div>
              <div><dt>Chi nhánh</dt><dd>{branch.name}</dd></div>
              <div><dt>Trạng thái</dt><dd>Chờ hàng về</dd></div>
            </dl>
            <p>Cửa hàng sẽ nhắn SMS hoặc email cho bạn ngay khi hàng về và được giữ cho bạn.</p>
            <Button onClick={onClose}>Quay lại danh mục</Button>
          </div>
        ) : (
          <>
            <span className="preview-label">ĐẶT TRƯỚC SẢN PHẨM HẾT HÀNG</span>
            <h2 id="live-preorder-title">Thông tin đặt trước</h2>
            <div className="preorder-product-summary"><b>{item.product.name}</b><span>{item.variant.sku} · {item.variant.variantName}</span><strong>{money(Number(item.variant.price))}</strong></div>
            <form className="preorder-preview-form" onSubmit={submit} noValidate>
              <label>Họ tên *<input name="name" autoComplete="name" value={form.name} onChange={update} aria-invalid={!!errors.name} />{errors.name && <small className="field-error">{errors.name}</small>}</label>
              <label>Số điện thoại *<input name="phone" type="tel" autoComplete="tel" inputMode="numeric" value={form.phone} onChange={update} aria-invalid={!!errors.phone} />{errors.phone && <small className="field-error">{errors.phone}</small>}</label>
              <label>Email<input name="email" type="email" autoComplete="email" value={form.email} onChange={update} aria-invalid={!!errors.email} />{errors.email && <small className="field-error">{errors.email}</small>}</label>
              <label>Địa chỉ *<input name="address" autoComplete="street-address" value={form.address} onChange={update} aria-invalid={!!errors.address} />{errors.address && <small className="field-error">{errors.address}</small>}</label>
              <label>Ghi chú<textarea name="note" rows="2" maxLength="255" value={form.note} onChange={update} /></label>
              <label>Số lượng<input name="quantity" type="number" min="1" max="100" value={form.quantity} onChange={update} />{errors.quantity && <small className="field-error">{errors.quantity}</small>}</label>
              <div className="preorder-preview-branch"><span>Chi nhánh nhận hàng</span><b>{branch.name}</b></div>
              {serverError && <p className="field-error" role="alert">{serverError}</p>}
              <div className="catalog-form-actions"><Button variant="outline" type="button" disabled={busy} onClick={onClose}>Hủy</Button><Button type="submit" disabled={busy}>{busy ? 'Đang gửi…' : 'Gửi đặt trước'}</Button></div>
            </form>
          </>
        )}
      </section>
    </div>
  );
}

function flattenCategories(nodes, depth = 0) {
  return nodes.flatMap((n) => [{ id: n.id, name: n.name, depth }, ...flattenCategories(n.children || [], depth + 1)]);
}

function priceRange(min, max) {
  return min === max ? money(min) : `${money(min)} – ${money(max)}`;
}

// Detail of one product: variants with availability at the chosen branch (never a quantity), pre-order buttons.
function ProductDetail({ productId, branch, onClose, onPreorder }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    publicRequest(`/public/products/${productId}`).then((d) => active && setDetail(d)).catch((e) => active && setError(e.message));
    return () => { active = false; };
  }, [productId]);
  useEffect(() => { const esc = (e) => { if (e.key === 'Escape') onClose(); }; window.addEventListener('keydown', esc); return () => window.removeEventListener('keydown', esc); }, [onClose]);
  return (
    <div className="catalog-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section className="catalog-dialog product-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="live-detail-title">
        <button className="catalog-close" type="button" aria-label="Đóng" onClick={onClose}>×</button>
        {error ? <p className="field-error" role="alert">{error}</p> : !detail ? <p>Đang tải…</p> : <>
          <div className="catalog-detail-art">{detail.imageUrl ? <img src={detail.imageUrl} alt={detail.name} /> : <span aria-hidden="true">◇</span>}</div>
          <div className="catalog-detail-copy">
            <span className="catalog-category">{detail.category.name}</span>
            <h2 id="live-detail-title">{detail.name}</h2>
            <strong className="catalog-detail-price">{priceRange(detail.priceMin, detail.priceMax)}</strong>
            {detail.description && <p className="catalog-detail-description">{detail.description}</p>}
            <p className="catalog-results-count">Tình trạng tại {branch?.name}:</p>
            <ul className="catalog-variant-list" aria-label="Biến thể">
              {detail.variants.map((v) => {
                const inStock = v.branches.find((b) => b.branchId === branch?.branchId)?.availability === 'IN_STOCK';
                return <li key={v.id} className="catalog-variant-row">
                  <div className="catalog-variant-name"><b>{v.name}</b><small className="catalog-sku">SKU {v.sku}{v.attributes.length ? ` · ${v.attributes.map((a) => `${a.name} ${a.value}`).join(', ')}` : ''}</small></div>
                  <span>{money(v.price)}</span>
                  <span className={`catalog-stock ${inStock ? 'is-available' : 'is-out'}`}>{inStock ? 'Còn hàng' : 'Hết hàng'}</span>
                  {!inStock && branch ? <Button onClick={() => onPreorder({ product: detail, variant: { variantId: v.id, sku: v.sku, variantName: v.name, price: v.price } })}>Đặt trước</Button> : <span />}
                </li>;
              })}
            </ul>
          </div>
        </>}
      </section>
    </div>
  );
}

export function LiveCatalog() {
  const [branches, setBranches] = useState([]);
  const [branchId, setBranchId] = useState(null);
  const [categories, setCategories] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [keyword, setKeyword] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [stock, setStock] = useState('all');
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(null);
  const [preorder, setPreorder] = useState(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    Promise.all([publicRequest(`/public/branches?storeId=${PUBLIC_STORE_ID}`), publicRequest(`/public/categories?storeId=${PUBLIC_STORE_ID}`)])
      .then(([b, c]) => { setBranches(b); setCategories(flattenCategories(c)); setBranchId((cur) => (b.some((x) => x.branchId === cur) ? cur : b[0]?.branchId ?? null)); })
      .catch((e) => setError(e.message || 'Không tải được danh mục.'));
  }, []);
  useEffect(() => { const t = setTimeout(() => setKeyword(query.trim()), 300); return () => clearTimeout(t); }, [query]);
  useEffect(() => setPage(1), [keyword, categoryId, stock]);
  useEffect(() => {
    const params = new URLSearchParams({ storeId: String(PUBLIC_STORE_ID), page: String(page), size: String(PAGE_SIZE) });
    if (keyword) params.set('keyword', keyword);
    if (categoryId) params.set('categoryId', categoryId);
    if (stock !== 'all') params.set('inStock', stock === 'available' ? 'true' : 'false');
    let active = true;
    setLoading(true);
    publicRequest(`/public/products?${params}`)
      .then((r) => { if (active) { setResult(r); setError(''); } })
      .catch((e) => active && setError(e.message || 'Không tải được danh mục.'))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [keyword, categoryId, stock, page, version]);

  const branch = branches.find((b) => b.branchId === branchId);
  const reload = useCallback(() => setVersion((v) => v + 1), []);

  return (
    <main className="catalog-page">
      <div className="catalog-heading"><div><span className="eyebrow">DKAT / CỬA HÀNG</span><h1>Danh mục sản phẩm</h1><p>Xem tình trạng hàng tại chi nhánh. Sản phẩm hết hàng có thể đặt trước, cửa hàng sẽ báo khi hàng về.</p></div>
        <label className="catalog-branch">Chi nhánh<Select value={branchId ?? ''} onChange={(e) => setBranchId(Number(e.target.value))}>{branches.map((b) => <option key={b.branchId} value={b.branchId}>{b.name}</option>)}</Select></label></div>
      {branch && <p className="catalog-results-count">{branch.address}{branch.phone ? ` · ${branch.phone}` : ''}</p>}
      <section className="catalog-filters" aria-label="Tìm và lọc sản phẩm">
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm theo tên sản phẩm" aria-label="Tìm sản phẩm" />
        <Select aria-label="Danh mục" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}><option value="">Tất cả danh mục</option>{categories.map((c) => <option key={c.id} value={c.id}>{`${'— '.repeat(c.depth)}${c.name}`}</option>)}</Select>
        <Select aria-label="Tình trạng" value={stock} onChange={(e) => setStock(e.target.value)}><option value="all">Mọi tình trạng</option><option value="available">Còn hàng</option><option value="out">Hết hàng</option></Select>
        <Button variant="outline" type="button" onClick={reload}>Làm mới</Button>
      </section>
      {error ? <div className="catalog-empty" role="alert"><h2>Không tải được danh mục</h2><p>{error}</p><Button variant="outline" onClick={reload}>Thử lại</Button></div>
        : !result ? <div className="catalog-empty"><p>Đang tải danh mục…</p></div>
          : result.items.length ? <>
            <div className="catalog-results-count">{result.total} sản phẩm{loading ? ' · đang tải…' : ''}</div>
            <section className="catalog-grid" aria-label="Danh sách sản phẩm">
              {result.items.map((p) => <article className="catalog-product-card" key={p.id}>
                <div className="catalog-product-art">{p.imageUrl ? <img src={p.imageUrl} alt={p.name} /> : <span aria-hidden="true">◇</span>}</div>
                <div className="catalog-product-info"><span className="catalog-category">{p.category.name}</span><h2>{p.name}</h2>
                  <strong>{priceRange(p.priceMin, p.priceMax)}</strong>
                  <span className={`catalog-stock ${p.inStock ? 'is-available' : 'is-out'}`}>{p.inStock ? 'Còn hàng' : 'Hết hàng'}</span>
                  <div className="catalog-card-actions"><Button variant="outline" onClick={() => setOpen(p.id)}>Xem chi tiết</Button></div></div>
              </article>)}
            </section>
            {result.totalPages > 1 && <nav className="catalog-pagination" aria-label="Phân trang"><Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Trước</Button><span>Trang {page} / {result.totalPages}</span><Button variant="outline" disabled={page >= result.totalPages} onClick={() => setPage(page + 1)}>Tiếp</Button></nav>}
          </> : <div className="catalog-empty"><h2>Không tìm thấy sản phẩm</h2><p>Thử đổi từ khóa hoặc bộ lọc.</p></div>}
      {open && !preorder && <ProductDetail productId={open} branch={branch} onClose={() => setOpen(null)} onPreorder={setPreorder} />}
      {preorder && branch && <PreorderDialog item={preorder} branch={branch} onClose={() => setPreorder(null)} onCreated={reload} />}
    </main>
  );
}
