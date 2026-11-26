import React, { useEffect, useMemo, useState } from 'react';
import { demoVariantLabel, useLanguage } from './i18n';
import { Button, Select } from './components/ui.jsx';
import { available } from './domain.js';
import './product-catalog.css';

const PAGE_SIZE = 6;

function stockLabel(variant, inventory, preorders, branch) {
  if (!variant.active) return 'Ngừng kinh doanh';
  return available({ inventory, preorders }, branch, variant.id) > 0 ? 'Còn hàng' : 'Hết hàng';
}

function PreviewOrder({ variant, branchName, quantity, onClose }) {
  const { t, locale, formatCurrency } = useLanguage();
  const [form, setForm] = useState({ name: '', phone: '', email: '', address: '', note: '' });
  const [errors, setErrors] = useState({});
  const [preorderQuantity, setPreorderQuantity] = useState(quantity);
  const [confirmation, setConfirmation] = useState(null);
  useEffect(() => { const closeOnEscape = (event) => { if (event.key === 'Escape') onClose(); }; window.addEventListener('keydown', closeOnEscape); return () => window.removeEventListener('keydown', closeOnEscape); }, [onClose]);
  const update = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  const submit = (event) => {
    event.preventDefault();
    const next = {};
    if (!form.name.trim()) next.name = 'Vui lòng nhập họ tên.';
    if (!/^0\d{9}$/.test(form.phone.trim())) next.phone = 'Nhập số điện thoại gồm 10 chữ số, bắt đầu bằng 0.';
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) next.email = 'Email chưa đúng định dạng.';
    if (!Number.isInteger(Number(preorderQuantity)) || Number(preorderQuantity) < 1 || Number(preorderQuantity) > 10) next.quantity = 'Số lượng demo từ 1 đến 10.';
    setErrors(next);
    if (Object.keys(next).length) return;
    setConfirmation({ code: `DEMO-${Date.now().toString(36).toUpperCase()}`, createdAt: new Date() });
  };

  return (
    <div className="catalog-overlay" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="catalog-dialog" role="dialog" aria-modal="true" aria-labelledby="preorder-title">
        <button className="catalog-close" type="button" aria-label={t('Đóng')} onClick={onClose}>×</button>
        {confirmation ? (
          <div className="preview-confirmation">
            <span className="preview-check" aria-hidden="true">✓</span>
            <span className="preview-label">{t('BẢN XEM TRƯỚC · CHƯA GỬI ĐẾN CỬA HÀNG')}</span>
            <h2 id="preorder-title">{t('Yêu cầu demo đã xem trước')}</h2>
            <p>{t('Mã minh họa') + ' '}<b>{confirmation.code}</b></p>
            <dl><div><dt>{t('Sản phẩm')}</dt><dd>{variant.name} · {demoVariantLabel(variant.color,t)} / {demoVariantLabel(variant.size,t)}</dd></div><div><dt>{t('Số lượng')}</dt><dd>{preorderQuantity}</dd></div><div><dt>{t('Giá trị dự kiến')}</dt><dd>{formatCurrency(variant.price * Number(preorderQuantity))}</dd></div><div><dt>{t('Chi nhánh')}</dt><dd>{branchName}</dd></div><div><dt>{t('Khách hàng')}</dt><dd>{form.name} · {form.phone}</dd></div><div><dt>{t('Thời gian')}</dt><dd>{new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(confirmation.createdAt)}</dd></div></dl>
            <p className="catalog-demo-warning">{t('Đây chỉ là màn hình minh họa. Không có đơn nào được lưu hoặc gửi tới nhân viên.')}</p>
            <Button onClick={onClose}>{t('Quay lại danh mục')}</Button>
          </div>
        ) : (
          <>
            <span className="preview-label">{t('ĐẶT TRƯỚC · CHẾ ĐỘ DEMO')}</span>
            <h2 id="preorder-title">{t('Thông tin yêu cầu')}</h2>
            <div className="preorder-product-summary"><b>{variant.name}</b><span>{variant.sku} · {demoVariantLabel(variant.color,t)} / {demoVariantLabel(variant.size,t)}</span><strong>{formatCurrency(variant.price)}</strong></div>
            <form className="preorder-preview-form" onSubmit={submit} noValidate>
              <label>{t('Họ tên *')}<input name="name" autoComplete="name" value={form.name} onChange={update} aria-invalid={!!errors.name} />{errors.name && <small className="field-error">{t(errors.name)}</small>}</label>
              <label>{t('Số điện thoại *')}<input name="phone" type="tel" autoComplete="tel" inputMode="numeric" value={form.phone} onChange={update} aria-invalid={!!errors.phone} />{errors.phone && <small className="field-error">{t(errors.phone)}</small>}</label>
              <label>Email<input name="email" type="email" autoComplete="email" value={form.email} onChange={update} aria-invalid={!!errors.email} />{errors.email && <small className="field-error">{t(errors.email)}</small>}</label>
              <label>{t('Địa chỉ')}<input name="address" autoComplete="street-address" value={form.address} onChange={update} /></label>
              <label>{t('Ghi chú')}<textarea name="note" rows="2" value={form.note} onChange={update} /></label>
              <label>{t('Số lượng')}<input type="number" min="1" max="10" value={preorderQuantity} onChange={(event) => setPreorderQuantity(Number(event.target.value))} aria-label={t('Số lượng xem trước')} />{errors.quantity && <small className="field-error">{t(errors.quantity)}</small>}</label>
              <div className="preorder-preview-branch"><span>{t('Chi nhánh tiếp nhận')}</span><b>{branchName}</b></div>
              <p className="catalog-demo-warning">{t('Bản demo không gửi yêu cầu và không xác nhận tồn kho, giá hoặc thời gian giao hàng.')}</p>
              <div className="catalog-form-actions"><Button variant="outline" type="button" onClick={onClose}>{t('Hủy')}</Button><Button type="submit">{t('Tạo bản xem trước')}</Button></div>
            </form>
          </>
        )}
      </section>
    </div>
  );
}

export function ProductCatalog({ variants, inventory, preorders, branches, branch, setBranch }) {
  const { t, formatCurrency, formatNumber } = useLanguage();
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [stock, setStock] = useState('all');
  const [priceRange, setPriceRange] = useState('all');
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [preorder, setPreorder] = useState(null);
  const currentBranch = branches.find((item) => item.id === branch);
  useEffect(() => { if (!selected) return; const closeOnEscape = (event) => { if (event.key === 'Escape') setSelected(null); }; window.addEventListener('keydown', closeOnEscape); return () => window.removeEventListener('keydown', closeOnEscape); }, [selected]);
  const categories = [...new Set(variants.map((item) => item.category).filter(Boolean))];

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim().toLocaleLowerCase('vi')), 250);
    return () => clearTimeout(timer);
  }, [query]);

  const filtered = useMemo(() => variants.filter((item) => {
    const queryMatch = !debouncedQuery || `${item.name} ${item.sku}`.toLocaleLowerCase('vi').includes(debouncedQuery);
    const quantity = available({ inventory, preorders }, branch, item.id);
    const categoryMatch = category === 'all' || item.category === category;
    const stockMatch = stock === 'all' || (stock === 'available' ? quantity > 0 && item.active : stock === 'out' ? quantity <= 0 && item.active : !item.active);
    const priceMatch = priceRange === 'all' || (priceRange === 'low' ? item.price < 200000 : priceRange === 'mid' ? item.price >= 200000 && item.price <= 500000 : item.price > 500000);
    return queryMatch && categoryMatch && stockMatch && priceMatch;
  }).sort((a, b) => sort === 'price-asc' ? a.price - b.price : sort === 'price-desc' ? b.price - a.price : sort === 'name' ? a.name.localeCompare(b.name, 'vi') : 0), [variants, inventory, branch, debouncedQuery, category, stock, priceRange, sort]);

  useEffect(() => setPage(1), [debouncedQuery, category, stock, priceRange, sort, branch]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <main className="catalog-page">
      <div className="catalog-demo-banner"><span aria-hidden="true">i</span><div><b>{t('Danh mục xem trước · Dữ liệu demo trên trình duyệt')}</b><small>{t('DKat hiện chưa có API danh mục công khai. Giá và tồn kho trên trang này không được xác nhận từ máy chủ.')}</small></div></div>
      <div className="catalog-heading"><div><span className="eyebrow">{t('DKAT / CỬA HÀNG')}</span><h1>{t('Danh mục sản phẩm')}</h1><p>{t('Tìm sản phẩm và xem tình trạng tại chi nhánh đang chọn.')}</p></div><label className="catalog-branch">{t('Chi nhánh')}<Select value={branch} onChange={(event) => setBranch(event.target.value)}>{branches.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></label></div>
      <section className="catalog-filters" aria-label={t('Tìm và lọc sản phẩm')}>
        <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('Tìm theo tên hoặc SKU')} aria-label={t('Tìm sản phẩm')} />
        <Select aria-label={t('Danh mục')} value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">{t('Tất cả danh mục')}</option>{categories.map((item) => <option key={item} value={item}>{demoVariantLabel(item,t)}</option>)}</Select>
        <Select aria-label={t('Tình trạng tồn kho')} value={stock} onChange={(event) => setStock(event.target.value)}><option value="all">{t('Mọi tình trạng')}</option><option value="available">{t('Còn hàng')}</option><option value="out">{t('Hết hàng')}</option><option value="inactive">{t('Ngừng kinh doanh')}</option></Select>
        <Select aria-label={t('Khoảng giá')} value={priceRange} onChange={(event) => setPriceRange(event.target.value)}><option value="all">{t('Mọi mức giá')}</option><option value="low">{t('catalog.price.below',{amount:formatCurrency(200000)})}</option><option value="mid">{t('catalog.price.range',{low:formatCurrency(200000),high:formatCurrency(500000)})}</option><option value="high">{t('catalog.price.above',{amount:formatCurrency(500000)})}</option></Select>
        <Select aria-label={t('Sắp xếp')} value={sort} onChange={(event) => setSort(event.target.value)}><option value="name">{t('Tên A–Z')}</option><option value="price-asc">{t('Giá tăng dần')}</option><option value="price-desc">{t('Giá giảm dần')}</option></Select>
      </section>
      {visible.length ? <>
        <div className="catalog-results-count">{t('catalog.resultCount',{count:formatNumber(filtered.length)})}</div>
        <section className="catalog-grid" aria-label={t('Danh sách sản phẩm')}>
          {visible.map((item) => {
            const quantity = available({ inventory, preorders }, branch, item.id);
            const isOut = quantity <= 0 && item.active;
            return <article className="catalog-product-card" key={item.id}>
              <div className="catalog-product-art"><span aria-hidden="true">{item.category === 'Áo' ? '◈' : item.category === 'Quần' ? '▤' : '◇'}</span><small>{t('Ảnh minh họa')}</small></div>
              <div className="catalog-product-info"><span className="catalog-category">{demoVariantLabel(item.category,t)}</span><h2>{item.name}</h2><span className="catalog-sku">SKU {item.sku} · {demoVariantLabel(item.color,t)} / {demoVariantLabel(item.size,t)}</span><strong>{formatCurrency(item.price)}</strong><span className={`catalog-stock ${!item.active ? 'is-inactive' : isOut ? 'is-out' : 'is-available'}`}>{t(stockLabel(item, inventory, preorders, branch))}</span><div className="catalog-card-actions"><Button variant="outline" onClick={() => setSelected(item)}>{t('Xem chi tiết')}</Button>{isOut && <Button onClick={() => setPreorder(item)}>{t('Đặt trước demo')}</Button>}</div></div>
            </article>;
          })}
        </section>
        {pageCount > 1 && <nav className="catalog-pagination" aria-label={t('Phân trang')}><Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t('Trước')}</Button><span>{t('catalog.page',{page:formatNumber(page),total:formatNumber(pageCount)})}</span><Button variant="outline" disabled={page >= pageCount} onClick={() => setPage(page + 1)}>{t('Tiếp')}</Button></nav>}
      </> : <div className="catalog-empty"><span aria-hidden="true">⌕</span><h2>{t('Không tìm thấy sản phẩm')}</h2><p>{t('Thử đổi từ khóa hoặc bộ lọc. Danh mục hiện dùng dữ liệu demo trên trình duyệt.')}</p><Button variant="outline" onClick={() => { setQuery(''); setCategory('all'); setStock('all'); setPriceRange('all'); setSort('name'); }}>{t('Xóa bộ lọc')}</Button></div>}
      {selected && <div className="catalog-overlay" onMouseDown={(event) => event.target === event.currentTarget && setSelected(null)}><section className="catalog-dialog product-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="product-detail-title"><button className="catalog-close" type="button" aria-label={t('Đóng')} onClick={() => setSelected(null)}>×</button><div className="catalog-detail-art"><span aria-hidden="true">◇</span><small>{t('Ảnh minh họa')}</small></div><div className="catalog-detail-copy"><span className="catalog-category">{demoVariantLabel(selected.category,t)}</span><h2 id="product-detail-title">{selected.name}</h2><span className="catalog-sku">SKU {selected.sku}</span><p>{demoVariantLabel(selected.color,t)} · {demoVariantLabel(selected.size,t)}</p><strong className="catalog-detail-price">{formatCurrency(selected.price)}</strong><p className="catalog-detail-description">{t('Mô tả chi tiết và gallery ảnh chưa có trong dữ liệu hiện tại.')}</p><div className="catalog-detail-stock">{t('Tình trạng:') + ' '}<b>{t(stockLabel(selected, inventory, preorders, branch))}</b>{selected.active && available({ inventory, preorders }, branch, selected.id) > 0 && <span>{' ' + t('· Còn hàng theo dữ liệu demo')}</span>}</div>{selected.active && available({ inventory, preorders }, branch, selected.id) <= 0 && <Button onClick={() => { setSelected(null); setPreorder(selected); }}>{t('Tạo bản xem trước đặt trước')}</Button>}</div></section></div>}
      {preorder && <PreviewOrder variant={preorder} branchName={currentBranch?.name || t('Chưa chọn')} quantity={1} onClose={() => setPreorder(null)} />}
    </main>
  );
}
