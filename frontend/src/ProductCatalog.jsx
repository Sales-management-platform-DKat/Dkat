import React, { useEffect, useMemo, useState } from 'react';
import { Button, Select } from './components/ui.jsx';
import { apiAssetUrl } from './auth-client.js';
import { createDemoApi } from './demo/demo-api.js';
import { friendlyMessage } from './lib/api-errors.js';
import { useLanguage } from './i18n';
import './product-catalog.css';

const PAGE_SIZE = 6;
const PHONE = /^(?:\+?84|0)\d{9,10}$/;
// The public catalog is a showcase on the demo store: it reads and writes the
// same browser-only demo data as the demo admin (never the production database).
const demoApi = createDemoApi('OWNER');
const call = (path, method = 'GET', body) => demoApi(path, { method, body: body ? JSON.stringify(body) : undefined });
const money = (value) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(value) || 0);

function stockLabel(item) {
  return item.available > 0 ? `Còn hàng (${item.available})` : 'Hết hàng';
}

function PreorderForm({ item, branch, onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', phone: '', email: '', address: '', note: '' });
  const [quantity, setQuantity] = useState(1);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState('');
  const [created, setCreated] = useState(null);
  useEffect(() => { const onKey = (event) => { if (event.key === 'Escape' && !busy) onClose(); }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey); }, [onClose, busy]);
  const update = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }));

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const next = {};
    if (!form.name.trim()) next.name = 'Vui lòng nhập họ tên.';
    if (!PHONE.test(form.phone.replace(/[\s.-]/g, ''))) next.phone = 'Số điện thoại gồm 10–11 chữ số, bắt đầu bằng 0 hoặc +84.';
    if (!form.address.trim()) next.address = 'Vui lòng nhập địa chỉ.';
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) next.email = 'Email chưa đúng định dạng.';
    if (!Number.isInteger(Number(quantity)) || quantity < 1 || quantity > 99) next.quantity = 'Số lượng từ 1 đến 99.';
    setErrors(next);
    if (Object.keys(next).length) return;
    setBusy(true); setServerError('');
    try {
      const order = await call('/preorders', 'POST', {
        branchId: branch.id,
        customer: { fullName: form.name.trim(), phone: form.phone.trim(), email: form.email.trim() || null, address: form.address.trim() },
        items: [{ variantId: item.variantId, quantity: Number(quantity) }],
        note: form.note.trim() || null,
      });
      setCreated(order);
      onCreated();
    } catch (error) {
      setServerError(friendlyMessage(error, 'Không thể tạo đơn đặt trước. Vui lòng thử lại.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="catalog-overlay" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <section className="catalog-dialog" role="dialog" aria-modal="true" aria-labelledby="preorder-title">
        <button className="catalog-close" type="button" aria-label="Đóng" onClick={onClose} disabled={busy}>×</button>
        {created ? (
          <div className="preview-confirmation">
            <span className="preview-check" aria-hidden="true">✓</span>
            <span className="preview-label">ĐÃ GHI NHẬN ĐƠN ĐẶT TRƯỚC (BẢN DEMO)</span>
            <h2 id="preorder-title">Đặt trước thành công</h2>
            <p>Mã đơn của bạn: <b>{created.preorderCode}</b></p>
            <dl><div><dt>Sản phẩm</dt><dd>{item.name} · {item.variantName}</dd></div><div><dt>Số lượng</dt><dd>{created.items[0].quantity}</dd></div><div><dt>Tạm tính</dt><dd>{money(created.totalAmount)}</dd></div><div><dt>Chi nhánh</dt><dd>{branch.name}</dd></div><div><dt>Khách hàng</dt><dd>{created.customer.fullName} · {created.customer.phone}</dd></div><div><dt>Trạng thái</dt><dd>Chờ hàng – cửa hàng sẽ liên hệ khi có hàng</dd></div></dl>
            <p className="catalog-demo-warning">Bản demo: đơn được lưu trong dữ liệu demo của trình duyệt này và hiển thị ở màn hình "Đặt trước" khi bạn vào bản demo.</p>
            <Button onClick={onClose}>Quay lại danh mục</Button>
          </div>
        ) : (
          <>
            <span className="preview-label">ĐẶT TRƯỚC SẢN PHẨM HẾT HÀNG</span>
            <h2 id="preorder-title">Thông tin đặt trước</h2>
            <div className="preorder-product-summary"><b>{item.name}</b><span>{item.variantName} · SKU {item.sku}</span><strong>{money(item.price)}</strong></div>
            <form className="preorder-preview-form" onSubmit={submit} noValidate>
              <label>Họ tên *<input name="name" autoComplete="name" value={form.name} onChange={update} aria-invalid={!!errors.name} />{errors.name && <small className="field-error">{errors.name}</small>}</label>
              <label>Số điện thoại *<input name="phone" type="tel" autoComplete="tel" inputMode="numeric" value={form.phone} onChange={update} aria-invalid={!!errors.phone} />{errors.phone && <small className="field-error">{errors.phone}</small>}</label>
              <label>Địa chỉ *<input name="address" autoComplete="street-address" value={form.address} onChange={update} aria-invalid={!!errors.address} />{errors.address && <small className="field-error">{errors.address}</small>}</label>
              <label>Email<input name="email" type="email" autoComplete="email" value={form.email} onChange={update} aria-invalid={!!errors.email} />{errors.email && <small className="field-error">{errors.email}</small>}</label>
              <label>Số lượng *<input type="number" min="1" max="99" value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} aria-invalid={!!errors.quantity} />{errors.quantity && <small className="field-error">{errors.quantity}</small>}</label>
              <label>Ghi chú<textarea name="note" rows="2" value={form.note} onChange={update} /></label>
              <div className="preorder-preview-branch"><span>Chi nhánh tiếp nhận</span><b>{branch.name}</b><span>Tạm tính: <b>{money(item.price * (Number(quantity) || 0))}</b></span></div>
              {serverError && <p className="field-error" role="alert">{serverError}</p>}
              <div className="catalog-form-actions"><Button variant="outline" type="button" onClick={onClose} disabled={busy}>Hủy</Button><Button type="submit" disabled={busy}>{busy ? 'Đang gửi…' : 'Gửi đặt trước'}</Button></div>
            </form>
          </>
        )}
      </section>
    </div>
  );
}

export function ProductCatalog() {
  useLanguage();
  const [branches, setBranches] = useState([]);
  const [branchId, setBranchId] = useState('');
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loadError, setLoadError] = useState('');
  const [version, setVersion] = useState(0);
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [stock, setStock] = useState('all');
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [preorder, setPreorder] = useState(null);

  useEffect(() => {
    call('/branches').then((rows) => {
      const active = rows.filter((branch) => branch.status === 'ACTIVE');
      setBranches(active);
      setBranchId((current) => current || String(active[0]?.id || ''));
    }).catch((error) => setLoadError(friendlyMessage(error)));
  }, []);

  useEffect(() => {
    if (!branchId) return;
    Promise.all([call('/products?size=100'), call(`/inventory?branchId=${branchId}`), call('/categories')]).then(([products, inventory, tree]) => {
      const stockById = new Map(inventory.map((row) => [row.variantId, row]));
      const names = new Map();
      const walk = (nodes) => nodes.forEach((node) => { names.set(node.categoryId, node.name); walk(node.children || []); });
      walk(tree);
      setCategories([...new Set(products.map((product) => names.get(product.category_id)).filter(Boolean))]);
      setItems(products.flatMap((product) => product.variants.map((variant) => ({
        variantId: variant.variant_id, name: product.name, variantName: variant.variant_name, sku: variant.sku,
        price: Number(variant.price), category: names.get(product.category_id) || '', imageUrl: product.image_url,
        available: stockById.get(variant.variant_id)?.available ?? 0,
      }))));
      setLoadError('');
    }).catch((error) => setLoadError(friendlyMessage(error)));
  }, [branchId, version]);

  useEffect(() => { const timer = setTimeout(() => setDebouncedQuery(query.trim().toLocaleLowerCase('vi')), 250); return () => clearTimeout(timer); }, [query]);
  useEffect(() => { if (!selected) return undefined; const onKey = (event) => { if (event.key === 'Escape') setSelected(null); }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey); }, [selected]);

  const filtered = useMemo(() => items.filter((item) => {
    const queryMatch = !debouncedQuery || `${item.name} ${item.variantName} ${item.sku}`.toLocaleLowerCase('vi').includes(debouncedQuery);
    const stockMatch = stock === 'all' || (stock === 'available' ? item.available > 0 : item.available <= 0);
    return queryMatch && (category === 'all' || item.category === category) && stockMatch;
  }).sort((a, b) => sort === 'price-asc' ? a.price - b.price : sort === 'price-desc' ? b.price - a.price : a.name.localeCompare(b.name, 'vi')), [items, debouncedQuery, category, stock, sort]);

  useEffect(() => setPage(1), [debouncedQuery, category, stock, sort, branchId]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const branch = branches.find((item) => String(item.id) === String(branchId));

  const art = (item) => item.imageUrl ? <img src={apiAssetUrl(item.imageUrl)} alt="" /> : <><span aria-hidden="true">{item.category === 'Áo' ? '◈' : item.category === 'Quần' ? '▤' : '◇'}</span><small>Ảnh minh họa</small></>;

  return (
    <main className="catalog-page">
      <div className="catalog-demo-banner"><span aria-hidden="true">i</span><div><b>Cửa hàng mẫu · Dữ liệu demo trên trình duyệt</b><small>Tồn kho và đơn đặt trước trên trang này dùng chung dữ liệu với bản demo quản trị, không ghi vào cơ sở dữ liệu của cửa hàng thật.</small></div></div>
      <div className="catalog-heading"><div><span className="eyebrow">DKAT / CỬA HÀNG</span><h1>Danh mục sản phẩm</h1><p>Xem tình trạng hàng tại chi nhánh và đặt trước sản phẩm đang hết hàng.</p></div><label className="catalog-branch">Chi nhánh<Select value={branchId} onChange={(event) => setBranchId(event.target.value)}>{branches.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></label></div>
      <section className="catalog-filters" aria-label="Tìm và lọc sản phẩm">
        <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo tên hoặc SKU" aria-label="Tìm sản phẩm" />
        <Select aria-label="Danh mục" value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">Tất cả danh mục</option>{categories.map((item) => <option key={item}>{item}</option>)}</Select>
        <Select aria-label="Tình trạng tồn kho" value={stock} onChange={(event) => setStock(event.target.value)}><option value="all">Mọi tình trạng</option><option value="available">Còn hàng</option><option value="out">Hết hàng – có thể đặt trước</option></Select>
        <Select aria-label="Sắp xếp" value={sort} onChange={(event) => setSort(event.target.value)}><option value="name">Tên A–Z</option><option value="price-asc">Giá tăng dần</option><option value="price-desc">Giá giảm dần</option></Select>
      </section>
      {loadError ? <div className="catalog-empty"><h2>Không tải được danh mục</h2><p>{loadError}</p><Button variant="outline" onClick={() => setVersion((value) => value + 1)}>Thử lại</Button></div>
        : visible.length ? <>
          <div className="catalog-results-count">{filtered.length} sản phẩm</div>
          <section className="catalog-grid" aria-label="Danh sách sản phẩm">
            {visible.map((item) => {
              const isOut = item.available <= 0;
              return <article className="catalog-product-card" key={item.variantId}>
                <div className="catalog-product-art">{art(item)}</div>
                <div className="catalog-product-info"><span className="catalog-category">{item.category}</span><h2>{item.name}</h2><span className="catalog-sku">SKU {item.sku} · {item.variantName}</span><strong>{money(item.price)}</strong><span className={`catalog-stock ${isOut ? 'is-out' : 'is-available'}`}>{stockLabel(item)}</span>
                  <div className="catalog-card-actions"><Button variant="outline" onClick={() => setSelected(item)}>Xem chi tiết</Button>{isOut ? <Button onClick={() => setPreorder(item)}>Đặt trước</Button> : <Button variant="outline" disabled title="Mua trực tiếp tại cửa hàng">Mua tại cửa hàng</Button>}</div></div>
              </article>;
            })}
          </section>
          {pageCount > 1 && <nav className="catalog-pagination" aria-label="Phân trang"><Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Trước</Button><span>Trang {page} / {pageCount}</span><Button variant="outline" disabled={page >= pageCount} onClick={() => setPage(page + 1)}>Tiếp</Button></nav>}
        </> : <div className="catalog-empty"><span aria-hidden="true">⌕</span><h2>Không tìm thấy sản phẩm</h2><p>Thử đổi từ khóa hoặc bộ lọc.</p><Button variant="outline" onClick={() => { setQuery(''); setCategory('all'); setStock('all'); setSort('name'); }}>Xóa bộ lọc</Button></div>}
      {selected && <div className="catalog-overlay" onMouseDown={(event) => event.target === event.currentTarget && setSelected(null)}><section className="catalog-dialog product-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="product-detail-title"><button className="catalog-close" type="button" aria-label="Đóng" onClick={() => setSelected(null)}>×</button><div className="catalog-detail-art">{art(selected)}</div><div className="catalog-detail-copy"><span className="catalog-category">{selected.category}</span><h2 id="product-detail-title">{selected.name}</h2><span className="catalog-sku">SKU {selected.sku}</span><p>{selected.variantName}</p><strong className="catalog-detail-price">{money(selected.price)}</strong><div className="catalog-detail-stock">Tình trạng tại {branch?.name}: <b>{stockLabel(selected)}</b></div>{selected.available <= 0 && <Button onClick={() => { setSelected(null); setPreorder(selected); }}>Đặt trước sản phẩm này</Button>}</div></section></div>}
      {preorder && branch && <PreorderForm item={preorder} branch={branch} onClose={() => setPreorder(null)} onCreated={() => setVersion((value) => value + 1)} />}
    </main>
  );
}
