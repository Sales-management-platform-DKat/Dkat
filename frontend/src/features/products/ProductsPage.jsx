import React, { useEffect, useMemo, useState } from 'react';
import { apiAssetUrl } from '../../auth-client.js';
import { useLanguage } from '../../i18n/index.js';
import { confirmAction, FormDialog, FormField, notify } from '../../components/overlay/index.js';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../../components/states.jsx';
import { listCategories } from '../categories/api.js';
import CategoryManager from '../categories/CategoryManager.jsx';
import { listInventory } from '../inventory/api.js';
import ProductForm, { flattenCategories } from './ProductForm.jsx';
import { createProductVariant, getProduct, listProducts, setProductStatus, setVariantStatus, updateProductVariant } from './api.js';

function VariantForm({ productId, variant, isOwner, onClose, onSaved, t }) {
  const editing = !!variant?.variant_id;
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState(null);
  return <FormDialog title={editing ? t('Sửa biến thể') : t('Thêm biến thể')} description={editing ? variant.sku : ''} busy={busy} fieldErrors={fieldErrors}
    onClose={onClose} submitLabel={editing ? t('Lưu thay đổi') : t('Thêm biến thể')}
    validate={(data) => {
      const errors = {};
      if (!String(data.variantName || '').trim()) errors.variantName = t('Vui lòng nhập tên biến thể (VD: Trắng / M).');
      if (data.price === '' || Number(data.price) < 0) errors.price = t('Nhập giá bán hợp lệ.');
      if (data.costPrice && Number(data.costPrice) < 0) errors.costPrice = t('Giá nhập không được âm.');
      return errors;
    }}
    onSubmit={async (data) => {
      const payload = {
        variantName: data.variantName.trim(), sku: String(data.sku || '').trim() || null, price: Number(data.price),
        costPrice: isOwner && data.costPrice !== '' ? Number(data.costPrice) : null,
        barcode: String(data.barcode || '').trim() || null,
        // Editing keeps the variant's attributes (colour/size).
        attributes: (variant?.attributes || []).map((attribute) => ({ attributeId: attribute.attribute_id, value: attribute.value })),
      };
      setBusy(true);
      setFieldErrors(null);
      try {
        if (editing) await updateProductVariant(variant.variant_id, payload);
        else await createProductVariant(productId, payload);
        notify.success(editing ? t('Đã cập nhật biến thể.') : t('Đã thêm biến thể.'));
        onSaved();
        return true;
      } catch (error) {
        setFieldErrors(Object.keys(error.fieldErrors || {}).length ? error.fieldErrors : null);
        notify.error(error, { title: t('Không lưu được biến thể') });
        return false;
      } finally { setBusy(false); }
    }}>
    <FormField name="variantName" label={t('Tên biến thể')} required><input name="variantName" maxLength={200} defaultValue={variant?.variant_name || ''} autoFocus placeholder={t('VD: Trắng / M')} /></FormField>
    <FormField name="sku" label="SKU" hint={editing ? '' : t('Để trống để hệ thống tạo SKU.')}><input name="sku" maxLength={80} defaultValue={variant?.sku || ''} /></FormField>
    <FormField name="price" label={t('Giá bán')} required><input name="price" type="number" min="0" step="1000" defaultValue={variant?.price ?? ''} /></FormField>
    {isOwner && <FormField name="costPrice" label={t('Giá nhập')}><input name="costPrice" type="number" min="0" step="1000" defaultValue={variant?.cost_price ?? ''} /></FormField>}
    <FormField name="barcode" label="Barcode"><input name="barcode" maxLength={100} defaultValue={variant?.barcode || ''} /></FormField>
  </FormDialog>;
}

export default function ProductsPage({ branchId, branch, role = 'OWNER' }) {
  const { t, formatCurrency } = useLanguage();
  const isOwner = role === 'OWNER';
  const canEdit = role === 'OWNER' || role === 'MANAGER';
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [stock, setStock] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [imageFailed, setImageFailed] = useState(false);
  const [productDialog, setProductDialog] = useState(null);
  const [variantDialog, setVariantDialog] = useState(null);
  const [showCategories, setShowCategories] = useState(false);

  const flatCategories = useMemo(() => flattenCategories(categories), [categories]);
  useEffect(() => { const timer = setTimeout(() => setSearch(query.trim()), 250); return () => clearTimeout(timer); }, [query]);

  async function loadCategories() {
    const rows = await listCategories();
    setCategories(Array.isArray(rows) ? rows : []);
  }

  async function reload(term = search) {
    setLoading(true);
    setLoadError(null);
    const results = await Promise.allSettled([
      listProducts({ keyword: term, categoryId: categoryFilter || undefined, page: 1, size: 100, sort: 'name' }),
      listCategories(),
      branchId ? listInventory({ branchId, size: 100 }) : Promise.resolve([]),
    ]);
    const failed = results.find((result) => result.status === 'rejected');
    if (failed) {
      setProducts([]);
      setLoadError(failed.reason);
    } else {
      setProducts(Array.isArray(results[0].value) ? results[0].value : []);
      setCategories(Array.isArray(results[1].value) ? results[1].value : []);
      setStock(Array.isArray(results[2].value) ? results[2].value : []);
    }
    setLoading(false);
  }
  useEffect(() => { reload(); }, [search, branchId, categoryFilter]);

  async function openDetail(productId) {
    setSelectedId(productId); setDetail(null); setImageFailed(false);
    try { setDetail(await getProduct(productId)); }
    catch (error) { setSelectedId(null); notify.error(error, { title: t('Không tải được chi tiết sản phẩm') }); }
  }

  async function toggleProductStatus(product) {
    const deactivate = product.status === 'ACTIVE';
    if (deactivate && !(await confirmAction({ title: t('Ngừng bán sản phẩm?'), description: `"${product.name}" ${t('sẽ không còn xuất hiện ở POS và danh mục bán hàng.')}`, confirmLabel: t('Ngừng bán') }))) return;
    setBusy(true);
    try {
      await setProductStatus(product.productId, deactivate ? 'INACTIVE' : 'ACTIVE');
      notify.success(deactivate ? t('Đã ngừng bán sản phẩm.') : t('Đã mở bán lại sản phẩm.'));
      setSelectedId(null); setDetail(null); await reload();
    } catch (error) { notify.error(error, { title: t('Không cập nhật được trạng thái') }); }
    finally { setBusy(false); }
  }

  async function toggleVariantStatus(variant) {
    const deactivate = variant.status === 'ACTIVE';
    if (deactivate && !(await confirmAction({ title: t('Ngừng bán biến thể?'), description: `${variant.variant_name} · ${variant.sku}`, confirmLabel: t('Ngừng bán') }))) return;
    setBusy(true);
    try {
      await setVariantStatus(variant.variant_id, deactivate ? 'INACTIVE' : 'ACTIVE');
      notify.success(t('Đã cập nhật trạng thái biến thể.'));
      await openDetail(selectedId); await reload();
    } catch (error) { notify.error(error, { title: t('Không cập nhật được trạng thái') }); }
    finally { setBusy(false); }
  }

  const categoryName = (id) => flatCategories.find((category) => category.categoryId === id)?.name || '—';
  const stockByVariant = useMemo(() => new Map(stock.map((item) => [item.variantId, item])), [stock]);
  const stockCell = (variantId) => {
    const item = stockByVariant.get(variantId);
    if (!item) return <span className="muted">—</span>;
    return <span className={`badge ${item.available > 0 ? 'green' : 'amber'}`}>{item.available > 0 ? item.available : t('Hết hàng')}</span>;
  };

  return <>
    <div className="toolbar product-toolbar">
      <input aria-label={t('Tìm sản phẩm')} placeholder={t('Tìm theo tên hoặc SKU')} value={query} onChange={(event) => setQuery(event.target.value)} />
      <select aria-label={t('Danh mục')} value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
        <option value="">{t('Tất cả danh mục')}</option>
        {flatCategories.map((category) => <option key={category.categoryId} value={category.categoryId}>{'— '.repeat(category.depth)}{category.name}</option>)}
      </select>
      {canEdit && <button className="btn primary" onClick={() => setProductDialog({})}>{t('+ Thêm sản phẩm')}</button>}
      {canEdit && <button className="btn outline" onClick={() => setShowCategories(true)}>{t('Danh mục')}</button>}
      <span className="muted small">{products.length} {t('sản phẩm')}</span>
    </div>

    {selectedId ? <section className="panel product-detail-panel">
      {!detail ? <LoadingState label={t('Đang tải chi tiết…')} /> : <>
        <div className="section-title"><div><button className="link" onClick={() => { setSelectedId(null); setDetail(null); }}>{`← ${t('Quay lại danh sách')}`}</button><h2>{detail.name}</h2><p className="muted">{detail.productCode} · {categoryName(detail.categoryId)} · <StatusBadge status={detail.status} /></p></div>
          {canEdit && <div className="actions wrap">
            <button className="btn outline" onClick={() => setProductDialog(detail)}>{t('Sửa thông tin')}</button>
            <button className="btn outline" onClick={() => setVariantDialog({})}>{t('+ Thêm biến thể')}</button>
            {isOwner && <button className={`btn outline${detail.status === 'ACTIVE' ? ' danger' : ''}`} disabled={busy} onClick={() => toggleProductStatus(detail)}>{detail.status === 'ACTIVE' ? t('Ngừng bán') : t('Mở bán lại')}</button>}
          </div>}
        </div>
        <div className="product-detail-content"><div className="product-live-image">{detail.imageUrl && !imageFailed ? <img src={apiAssetUrl(detail.imageUrl)} alt={detail.name} onError={() => setImageFailed(true)} /> : <span aria-label={t('Chưa có ảnh')}>◇</span>}</div><div><p>{detail.description || t('Chưa có mô tả.')}</p></div></div>
        <h3>{t('Biến thể và tồn kho')}{branch ? ` · ${branch.name}` : ''}</h3>
        <div className="table-wrap"><table><thead><tr><th>{t('Biến thể')}</th><th>SKU</th><th>{t('Giá bán')}</th>{isOwner && <th>{t('Giá nhập')}</th>}<th>{t('Tồn khả dụng')}</th><th>{t('Trạng thái')}</th>{canEdit && <th>{t('Thao tác')}</th>}</tr></thead><tbody>
          {detail.variants.map((variant) => <tr key={variant.variant_id}>
            <td><strong>{variant.variant_name}</strong><small className="block muted">{variant.attributes?.map((attribute) => `${attribute.name}: ${attribute.value}`).join(' · ')}</small></td>
            <td>{variant.sku}</td><td>{formatCurrency(Number(variant.price))}</td>
            {isOwner && <td>{variant.cost_price == null ? '—' : formatCurrency(Number(variant.cost_price))}</td>}
            <td>{stockCell(variant.variant_id)}</td><td><StatusBadge status={variant.status} /></td>
            {canEdit && <td><div className="actions"><button className="link" onClick={() => setVariantDialog(variant)}>{t('Sửa')}</button>{isOwner && <button className="link" disabled={busy} onClick={() => toggleVariantStatus(variant)}>{variant.status === 'ACTIVE' ? t('Ngừng bán') : t('Mở bán')}</button>}</div></td>}
          </tr>)}
        </tbody></table></div>
      </>}
    </section>
      : loading ? <section className="panel"><LoadingState label={t('Đang tải sản phẩm…')} /></section>
        : loadError ? <section className="panel"><ErrorState error={loadError} onRetry={() => reload()} /></section>
          : !products.length ? <section className="panel"><EmptyState title={t('Chưa có sản phẩm')} description={query ? t('Thử từ khóa tìm kiếm khác.') : canEdit ? t('Bắt đầu bằng việc tạo danh mục, sau đó thêm sản phẩm và biến thể.') : t('Sản phẩm của cửa hàng sẽ xuất hiện tại đây.')}
            action={canEdit && !query && <button className="btn primary" onClick={() => setProductDialog({})}>{t('+ Thêm sản phẩm')}</button>} /></section>
            : <section className="panel"><div className="table-wrap"><table><thead><tr><th>{t('Ảnh')}</th><th>{t('Sản phẩm')}</th><th>SKU</th><th>{t('Danh mục')}</th><th>{t('Giá bán')}</th><th>{t('Tồn khả dụng')}</th><th>{t('Thao tác')}</th></tr></thead><tbody>
              {products.flatMap((product) => (product.variants.length ? product.variants : [null]).map((variant, index) => <tr key={`${product.product_id}-${variant?.variant_id || 'empty'}`} className="clickable" onClick={() => openDetail(product.product_id)}>
                <td>{index === 0 && (product.image_url ? <img className="product-table-image" src={apiAssetUrl(product.image_url)} alt="" loading="lazy" onError={(event) => { event.currentTarget.hidden = true; }} /> : <span className="product-table-image-placeholder" aria-label={t('Chưa có ảnh')}>◇</span>)}</td>
                <td><b>{product.name}</b><small className="block muted">{variant ? variant.variant_name : product.product_code}</small></td>
                <td>{variant?.sku || <span className="muted">{t('Chưa có biến thể')}</span>}</td>
                <td>{categoryName(product.category_id)}</td>
                <td>{variant ? formatCurrency(Number(variant.price)) : '—'}</td>
                <td>{variant ? stockCell(variant.variant_id) : '—'}</td>
                <td><button className="link" onClick={(event) => { event.stopPropagation(); openDetail(product.product_id); }}>{t('Chi tiết')}</button></td>
              </tr>))}
            </tbody></table></div></section>}

    {productDialog !== null && <ProductForm product={productDialog?.productId ? productDialog : null} categories={categories} isOwner={isOwner}
      canWriteStock={canEdit} branch={branch} t={t} onClose={() => setProductDialog(null)}
      onManageCategories={canEdit ? () => setShowCategories(true) : null}
      onSaved={async (saved) => { setProductDialog(null); await reload(); if (saved?.productId) await openDetail(saved.productId); }} />}
    {variantDialog !== null && <VariantForm productId={selectedId} variant={variantDialog?.variant_id ? variantDialog : null} isOwner={isOwner} t={t}
      onClose={() => setVariantDialog(null)} onSaved={async () => { setVariantDialog(null); await openDetail(selectedId); await reload(); }} />}
    {showCategories && <CategoryManager categories={categories} canToggle={isOwner} t={t} onClose={() => setShowCategories(false)} onChanged={loadCategories} />}
  </>;
}
