import React, { useEffect, useMemo, useState } from 'react';
import { apiAssetUrl } from '../../auth-client.js';
import { errorMessage, useLanguage } from '../../i18n/index.js';
import { createCategory, listCategories, setCategoryStatus, updateCategory } from '../categories/api.js';
import { listInventory } from '../inventory/api.js';
import { createProduct, createProductVariant, deleteUnusedProductImage, getProduct, listProducts, setProductStatus, setVariantStatus, updateProduct, updateProductVariant, uploadProductImage } from './api.js';

function flattenCategories(nodes, depth = 0, result = []) {
  for (const node of nodes || []) {
    result.push({ ...node, depth });
    flattenCategories(node.children, depth + 1, result);
  }
  return result;
}

function ProductDialog({ product, categories, busy, onCancel, onSubmit, t }) {
  const [imagePreview, setImagePreview] = useState(product?.imageUrl ? apiAssetUrl(product.imageUrl) : '');
  const [imageError, setImageError] = useState('');
  useEffect(() => () => { if (imagePreview.startsWith('blob:')) URL.revokeObjectURL(imagePreview); }, [imagePreview]);
  function selectImage(event) {
    const file = event.target.files?.[0];
    setImageError('');
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      event.target.value = '';
      setImageError('Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      event.target.value = '';
      setImageError('Ảnh tối đa 5 MB.');
      return;
    }
    setImagePreview(URL.createObjectURL(file));
  }
  return <div className="overlay" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
    <form className="dialog product-dialog" onSubmit={onSubmit} aria-labelledby="product-form-title">
      <div className="section-title"><h2 id="product-form-title">{product ? t('Sửa sản phẩm') : t('Thêm sản phẩm')}</h2><button className="link" type="button" onClick={onCancel} aria-label={t('Đóng')}>×</button></div>
      <label className="field">{t('Tên sản phẩm')}<input name="name" required maxLength={200} defaultValue={product?.name || ''} autoFocus /></label>
      <label className="field">{t('Mã sản phẩm')}<input name="productCode" maxLength={50} defaultValue={product?.productCode || ''} /></label>
      <label className="field">{t('Danh mục')}<select name="categoryId" required defaultValue={product?.categoryId || ''}><option value="">{t('Chọn danh mục')}</option>{categories.filter((category) => category.status === 'ACTIVE').map((category) => <option key={category.categoryId} value={category.categoryId}>{'— '.repeat(category.depth)}{category.name}</option>)}</select></label>
      <label className="field">{t('Mô tả')}<textarea name="description" maxLength={16000} rows={4} defaultValue={product?.description || ''} /></label>
      <label className="field">{t('Đường dẫn ảnh')}<input name="imageUrl" type="url" maxLength={500} defaultValue={product?.imageUrl || ''} placeholder="https://…" onChange={(event) => { if (!event.currentTarget.form.elements.imageFile.files?.length) setImagePreview(apiAssetUrl(event.target.value.trim())); }} /></label>
      <label className="field">{t('Hoặc tải ảnh từ máy')}<input name="imageFile" type="file" accept="image/jpeg,image/png,image/webp" onChange={selectImage} /><small className="muted">{t('JPEG, PNG hoặc WebP · tối đa 5 MB')}</small></label>
      {imageError && <p className="error-state" role="alert">{t(imageError)}</p>}
      {imagePreview && <div className="product-upload-preview"><img src={imagePreview} alt={t('Xem trước ảnh sản phẩm')} onError={() => setImageError('Không hiển thị được ảnh xem trước.')} /><span>{t('Xem trước ảnh')}</span></div>}
      <p className="muted small">{t('Sau khi tạo sản phẩm, thêm ít nhất một biến thể để bán và quản lý tồn kho.')}</p>
      <div className="actions"><button className="btn primary" disabled={busy}>{busy ? t('Đang lưu…') : t('Lưu thay đổi')}</button><button className="btn outline" type="button" onClick={onCancel}>{t('Hủy')}</button></div>
    </form>
  </div>;
}

function VariantDialog({ variant, busy, onCancel, onSubmit, t, isOwner }) {
  return <div className="overlay" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
    <form className="dialog product-dialog" onSubmit={onSubmit} aria-labelledby="variant-form-title">
      <div className="section-title"><h2 id="variant-form-title">{variant?.variant_id ? t('Sửa biến thể') : t('Thêm biến thể')}</h2><button className="link" type="button" onClick={onCancel} aria-label={t('Đóng')}>×</button></div>
      <label className="field">{t('Tên biến thể')}<input name="variantName" required maxLength={200} defaultValue={variant?.variant_name || ''} autoFocus /></label>
      <label className="field">SKU<input name="sku" maxLength={80} defaultValue={variant?.sku || ''} placeholder={t('Để trống để hệ thống tạo SKU')} /></label>
      <label className="field">{t('Giá bán')}<input name="price" type="number" min="0" step="0.01" required defaultValue={variant?.price || ''} /></label>
      {isOwner && <label className="field">{t('Giá vốn')}<input name="costPrice" type="number" min="0" step="0.01" defaultValue={variant?.cost_price ?? ''} /></label>}
      <label className="field">{t('Barcode')}<input name="barcode" maxLength={100} defaultValue={variant?.barcode || ''} /></label>
      <div className="actions"><button className="btn primary" disabled={busy}>{busy ? t('Đang lưu…') : t('Lưu thay đổi')}</button><button className="btn outline" type="button" onClick={onCancel}>{t('Hủy')}</button></div>
    </form>
  </div>;
}

function CategoryDialog({ categories, busy, onCancel, onCreate, onToggle, onEdit, t }) {
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault();
    setError('');
    try { await onCreate(name.trim()); setName(''); }
    catch (cause) { setError(errorMessage(cause, 'Không lưu được danh mục.')); }
  }
  return <div className="overlay" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
    <section className="dialog product-dialog" role="dialog" aria-modal="true" aria-labelledby="category-manager-title">
      <div className="section-title"><h2 id="category-manager-title">{t('Quản lý danh mục')}</h2><button className="link" onClick={onCancel} aria-label={t('Đóng')}>×</button></div>
      <form className="category-create-row" onSubmit={submit}><input aria-label={t('Tên danh mục')} required maxLength={100} value={name} onChange={(event) => setName(event.target.value)} placeholder={t('Tên danh mục mới')} /><button className="btn primary" disabled={busy}>{t('Thêm')}</button></form>
      {error && <p className="error-state" role="alert">{t(error)}</p>}
      <div className="category-admin-list">{flattenCategories(categories).map((category) => <div className="category-admin-row" key={category.categoryId}><span>{'— '.repeat(category.depth)}{category.name}</span><span className="muted small">{category.status === 'ACTIVE' ? t('Đang hoạt động') : t('Ngừng hoạt động')}</span><button className="link" disabled={busy} onClick={() => onEdit(category)}>{t('Sửa')}</button><button className="link" disabled={busy} onClick={() => onToggle(category)}>{category.status === 'ACTIVE' ? t('Ngừng bán') : t('Kích hoạt')}</button></div>)}</div>
      <button className="btn outline" onClick={onCancel}>{t('Đóng')}</button>
    </section>
  </div>;
}

export default function ProductsPage({ branchId, isOwner }) {
  const { t, formatCurrency } = useLanguage();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [stock, setStock] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [imageFailed, setImageFailed] = useState(false);
  const [productDialog, setProductDialog] = useState(null);
  const [variantDialog, setVariantDialog] = useState(null);
  const [showCategories, setShowCategories] = useState(false);

  const flatCategories = useMemo(() => flattenCategories(categories), [categories]);
  useEffect(() => { const timer = setTimeout(() => setSearch(query.trim()), 250); return () => clearTimeout(timer); }, [query]);

  async function reload(term = search) {
    setLoading(true);
    setError('');
    const results = await Promise.allSettled([
      listProducts({ keyword: term, limit: 100, page: 1, size: 100, sort: 'name' }),
      listCategories(),
      listInventory({ branchId, size: 100 }),
    ]);
    const failed = results.find((result) => result.status === 'rejected');
    if (failed) {
      setProducts([]); setCategories([]); setStock([]);
      setError(errorMessage(failed.reason, 'Không tải được danh sách sản phẩm.'));
    } else {
      setProducts(Array.isArray(results[0].value) ? results[0].value : []);
      setCategories(Array.isArray(results[1].value) ? results[1].value : []);
      setStock(Array.isArray(results[2].value) ? results[2].value : []);
    }
    setLoading(false);
  }

  useEffect(() => { reload(); }, [search, branchId]);

  async function openDetail(productId) {
    setSelectedId(productId); setDetail(null); setImageFailed(false); setError('');
    try { setDetail(await getProduct(productId)); }
    catch (cause) { setError(errorMessage(cause, 'Không tải được chi tiết sản phẩm.')); }
  }

  async function saveProduct(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const imageFile = values.imageFile instanceof File && values.imageFile.size ? values.imageFile : null;
    const payload = { name: String(values.name).trim(), categoryId: Number(values.categoryId), productCode: String(values.productCode || '').trim() || null, description: String(values.description || '').trim() || null, imageUrl: String(values.imageUrl || '').trim() || null };
    setBusy(true); setError('');
    let uploadedImageUrl = null;
    try {
      if (imageFile) {
        const uploaded = await uploadProductImage(imageFile);
        uploadedImageUrl = uploaded.imageUrl;
        payload.imageUrl = uploadedImageUrl;
      }
      const saved = productDialog?.productId ? await (async () => { const { productCode, ...updatePayload } = payload; return updateProduct(productDialog.productId, updatePayload); })() : await createProduct(payload);
      setProductDialog(null); setNotice('Đã lưu sản phẩm.'); await reload();
      if (saved?.productId) await openDetail(saved.productId);
    } catch (cause) {
      if (uploadedImageUrl) await deleteUnusedProductImage(uploadedImageUrl).catch(() => {});
      setError(errorMessage(cause, 'Không lưu được sản phẩm.'));
    }
    finally { setBusy(false); }
  }

  async function saveVariant(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const payload = { variantName: String(values.variantName).trim(), sku: String(values.sku || '').trim() || null, price: Number(values.price), costPrice: isOwner && values.costPrice !== '' ? Number(values.costPrice) : null, barcode: String(values.barcode || '').trim() || null, attributes: [] };
    setBusy(true); setError('');
    try {
      if (variantDialog?.variant_id) await updateProductVariant(variantDialog.variant_id, payload);
      else await createProductVariant(selectedId, payload);
      setVariantDialog(null); setNotice('Đã lưu biến thể.'); await openDetail(selectedId); await reload();
    } catch (cause) { setError(errorMessage(cause, 'Không lưu được biến thể.')); }
    finally { setBusy(false); }
  }

  async function toggleProductStatus(product) {
    const next = product.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    setBusy(true); setError('');
    try { await setProductStatus(product.productId, next); setNotice('Đã cập nhật trạng thái sản phẩm.'); setSelectedId(null); setDetail(null); await reload(); }
    catch (cause) { setError(errorMessage(cause, 'Không cập nhật được trạng thái.')); }
    finally { setBusy(false); }
  }

  async function toggleVariantStatus(variant) {
    const next = variant.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    setBusy(true); setError('');
    try { await setVariantStatus(variant.variant_id, next); setNotice('Đã cập nhật trạng thái biến thể.'); await openDetail(selectedId); await reload(); }
    catch (cause) { setError(errorMessage(cause, 'Không cập nhật được trạng thái.')); }
    finally { setBusy(false); }
  }

  async function saveCategory(name) {
    setBusy(true);
    try { await createCategory({ name, parentCategoryId: null, description: null }); setNotice('Đã lưu danh mục.'); await reload(); }
    finally { setBusy(false); }
  }

  async function toggleCategory(category) {
    setBusy(true); setError('');
    try { await setCategoryStatus(category.categoryId, category.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'); setNotice('Đã cập nhật danh mục.'); await reload(); }
    catch (cause) { setError(errorMessage(cause, 'Không cập nhật được danh mục.')); }
    finally { setBusy(false); }
  }

  async function editCategory(category) {
    const name = window.prompt(t('Tên danh mục'), category.name);
    if (!name?.trim() || name.trim() === category.name) return;
    setBusy(true); setError('');
    try { await updateCategory(category.categoryId, { name: name.trim(), parentCategoryId: category.parentCategoryId, description: category.description }); setNotice('Đã cập nhật danh mục.'); await reload(); }
    catch (cause) { setError(errorMessage(cause, 'Không cập nhật được danh mục.')); }
    finally { setBusy(false); }
  }

  const categoryName = (id) => flatCategories.find((category) => category.categoryId === id)?.name || '—';
  const stockByVariant = useMemo(() => new Map(stock.map((item) => [item.variantId, item])), [stock]);

  return <>
    <div className="toolbar product-toolbar"><input aria-label={t('Tìm sản phẩm')} placeholder={t('Tìm theo tên hoặc SKU')} value={query} onChange={(event) => setQuery(event.target.value)} />{isOwner && <><button className="btn primary" onClick={() => setProductDialog({})}>{t('+ Thêm sản phẩm')}</button><button className="btn outline" onClick={() => setShowCategories(true)}>{t('Danh mục')}</button></>}<span className="muted small">{products.length} {t('sản phẩm')}</span></div>
    {error && <div className="notice error-state" role="alert">{t(error)}</div>}{notice && <div className="notice success-state" role="status">{t(notice)}</div>}
    {selectedId && detail ? <section className="panel product-detail-panel">
      <div className="section-title"><div><button className="link" onClick={() => { setSelectedId(null); setDetail(null); }}>{`← ${t('Quay lại danh sách')}`}</button><h2>{detail.name}</h2><p className="muted">{detail.productCode} · {categoryName(detail.categoryId)}</p></div><div className="actions wrap">{isOwner && <><button className="btn outline" onClick={() => setProductDialog(detail)}>{t('Sửa sản phẩm')}</button><button className="btn outline" onClick={() => setVariantDialog({})}>{t('+ Thêm biến thể')}</button><button className="btn outline" disabled={busy} onClick={() => toggleProductStatus(detail)}>{detail.status === 'ACTIVE' ? t('Ngừng bán') : t('Kích hoạt')}</button></>}</div></div>
      <div className="product-detail-content"><div className="product-live-image">{detail.imageUrl && !imageFailed ? <img src={apiAssetUrl(detail.imageUrl)} alt={detail.name} onError={() => setImageFailed(true)} /> : <span aria-label={t('Chưa có ảnh')}>◇</span>}</div><div><p>{detail.description || t('Chưa có mô tả.')}</p><p className="muted small">{t('Mã sản phẩm')}: {detail.productCode} · {t('Trạng thái')}: {detail.status === 'ACTIVE' ? t('Đang hoạt động') : t('Ngừng hoạt động')}</p></div></div>
      <h3>{t('Biến thể và tồn kho')}</h3><div className="table-wrap"><table><thead><tr><th>{t('Biến thể')}</th><th>SKU</th><th>{t('Giá bán')}</th>{isOwner&&<th>{t('Giá vốn')}</th>}<th>{t('Tồn khả dụng')}</th><th>{t('Trạng thái')}</th>{isOwner&&<th>{t('Thao tác')}</th>}</tr></thead><tbody>{detail.variants.map((variant) => { const inventory=stockByVariant.get(variant.variant_id); return <tr key={variant.variant_id}><td><strong>{variant.variant_name}</strong><small className="block muted">{variant.attributes?.map((attribute) => `${attribute.name}: ${attribute.value}`).join(' · ')}</small></td><td>{variant.sku}</td><td>{formatCurrency(Number(variant.price))}</td>{isOwner&&<td>{variant.cost_price == null ? '—' : formatCurrency(Number(variant.cost_price))}</td>}<td>{inventory?.available ?? '—'}</td><td>{variant.status === 'ACTIVE' ? t('Đang hoạt động') : t('Ngừng hoạt động')}</td>{isOwner&&<td><div className="actions"><button className="link" onClick={() => setVariantDialog(variant)}>{t('Sửa')}</button><button className="link" disabled={busy} onClick={() => toggleVariantStatus(variant)}>{variant.status === 'ACTIVE' ? t('Ngừng bán') : t('Kích hoạt')}</button></div></td>}</tr>; })}</tbody></table></div>
    </section> : loading ? <section className="panel"><p className="muted" role="status">{t('Đang tải sản phẩm…')}</p></section> : products.length === 0 ? <section className="panel"><div className="empty"><h3>{t('Chưa có sản phẩm')}</h3><p>{query ? t('Thử từ khóa tìm kiếm khác.') : t('Sản phẩm lấy từ danh mục cửa hàng sẽ xuất hiện tại đây.')}</p></div></section> : <section className="panel"><div className="table-wrap"><table><thead><tr><th>{t('Ảnh')}</th><th>{t('Sản phẩm')}</th><th>{t('SKU')}</th><th>{t('Danh mục')}</th><th>{t('Giá bán')}</th><th>{t('Tồn khả dụng')}</th><th>{t('Thao tác')}</th></tr></thead><tbody>{products.flatMap((product) => (product.variants.length ? product.variants : [null]).map((variant) => <tr key={`${product.product_id}-${variant?.variant_id || 'empty'}`}><td>{product.image_url ? <img className="product-table-image" src={apiAssetUrl(product.image_url)} alt="" loading="lazy" onError={(event) => { event.currentTarget.hidden = true; }} /> : <span className="product-table-image-placeholder" aria-label={t('Chưa có ảnh')}>◇</span>}</td><td><button className="link product-name-link" onClick={() => openDetail(product.product_id)}>{product.name}</button><small className="block muted">{product.product_code}</small></td><td>{variant?.sku || '—'}</td><td>{categoryName(product.category_id)}</td><td>{variant ? formatCurrency(Number(variant.price)) : '—'}</td><td>{variant ? (stockByVariant.get(variant.variant_id)?.available ?? '—') : '—'}</td><td><button className="link" onClick={() => openDetail(product.product_id)}>{t('Chi tiết')}</button></td></tr>))}</tbody></table></div></section>}
    {productDialog !== null && <ProductDialog product={productDialog?.productId ? productDialog : null} categories={flatCategories} busy={busy} onCancel={() => setProductDialog(null)} onSubmit={saveProduct} t={t} />}
    {variantDialog !== null && <VariantDialog variant={variantDialog} busy={busy} isOwner={isOwner} onCancel={() => setVariantDialog(null)} onSubmit={saveVariant} t={t} />}
    {showCategories && <CategoryDialog categories={categories} busy={busy} onCancel={() => setShowCategories(false)} onCreate={saveCategory} onToggle={toggleCategory} onEdit={editCategory} t={t} />}
  </>;
}
