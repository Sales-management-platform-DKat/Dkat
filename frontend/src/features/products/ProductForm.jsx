import React, { useEffect, useMemo, useRef, useState } from 'react';
import { apiAssetUrl } from '../../auth-client.js';
import { FormDialog, FormField, FormSection, notify } from '../../components/overlay/index.js';
import {
  createProductFull, deleteUnusedProductImage, ensureVariantAttributes, updateProduct, uploadProductImage,
} from './api.js';

const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
let rowKey = 0;
const blankRow = () => ({ key: ++rowKey, color: '', size: '', sku: '', price: '', costPrice: '', initialQuantity: '' });

export function flattenCategories(nodes, depth = 0, result = []) {
  for (const node of nodes || []) {
    result.push({ ...node, depth });
    flattenCategories(node.children, depth + 1, result);
  }
  return result;
}

function ImagePicker({ initialUrl, onChange, t }) {
  const [preview, setPreview] = useState(initialUrl ? apiAssetUrl(initialUrl) : '');
  const [error, setError] = useState('');
  const input = useRef(null);
  useEffect(() => () => { if (preview.startsWith('blob:')) URL.revokeObjectURL(preview); }, [preview]);

  function pick(event) {
    const file = event.target.files?.[0];
    setError('');
    if (!file) return;
    if (!IMAGE_TYPES.includes(file.type)) { event.target.value = ''; setError(t('Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP.')); return; }
    if (file.size > 5 * 1024 * 1024) { event.target.value = ''; setError(t('Ảnh tối đa 5 MB.')); return; }
    setPreview(URL.createObjectURL(file));
    onChange({ file, url: null, removed: false });
  }
  function remove() {
    if (input.current) input.current.value = '';
    setPreview('');
    onChange({ file: null, url: null, removed: true });
  }

  return <div className="product-image-picker">
    <div className="product-image-frame">{preview ? <img src={preview} alt={t('Ảnh đại diện sản phẩm')} onError={() => setError(t('Không hiển thị được ảnh xem trước.'))} /> : <span aria-hidden="true">◇</span>}</div>
    <div className="product-image-actions">
      <label className="btn outline">{preview ? t('Đổi ảnh') : t('Tải ảnh lên')}<input ref={input} type="file" accept={IMAGE_TYPES.join(',')} hidden onChange={pick} /></label>
      {preview && <button type="button" className="btn outline danger" onClick={remove}>{t('Xóa ảnh')}</button>}
      <small className="muted">{t('Ảnh đại diện · JPEG, PNG hoặc WebP · tối đa 5 MB')}</small>
      {error && <small className="dk-field-error" role="alert">{error}</small>}
    </div>
  </div>;
}

function VariantRows({ rows, setRows, errors, showCost, showStock, t }) {
  const update = (key, field, value) => setRows((current) => current.map((row) => row.key === key ? { ...row, [field]: value } : row));
  return <div className="variant-editor">
    <div className="table-wrap"><table className="variant-table"><thead><tr>
      <th>{t('Màu sắc')}</th><th>{t('Kích thước')}</th><th>SKU</th><th>{t('Giá bán')} *</th>{showCost && <th>{t('Giá nhập')}</th>}{showStock && <th>{t('Tồn ban đầu')}</th>}<th aria-label={t('Thao tác')} />
    </tr></thead><tbody>
      {rows.map((row, index) => <React.Fragment key={row.key}>
        <tr>
          <td><input aria-label={t('Màu sắc')} value={row.color} maxLength={60} placeholder={t('VD: Trắng')} onChange={(e) => update(row.key, 'color', e.target.value)} /></td>
          <td><input aria-label={t('Kích thước')} value={row.size} maxLength={60} placeholder="M" onChange={(e) => update(row.key, 'size', e.target.value)} /></td>
          <td><input aria-label="SKU" value={row.sku} maxLength={80} placeholder={t('Tự tạo')} onChange={(e) => update(row.key, 'sku', e.target.value)} /></td>
          <td><input aria-label={t('Giá bán')} aria-invalid={errors[index]?.price ? true : undefined} type="number" min="0" step="1000" value={row.price} onChange={(e) => update(row.key, 'price', e.target.value)} /></td>
          {showCost && <td><input aria-label={t('Giá nhập')} type="number" min="0" step="1000" value={row.costPrice} onChange={(e) => update(row.key, 'costPrice', e.target.value)} /></td>}
          {showStock && <td><input aria-label={t('Tồn ban đầu')} type="number" min="0" step="1" value={row.initialQuantity} placeholder="0" onChange={(e) => update(row.key, 'initialQuantity', e.target.value)} /></td>}
          <td><button type="button" className="icon-btn" aria-label={t('Xóa biến thể')} disabled={rows.length === 1} onClick={() => setRows((current) => current.filter((item) => item.key !== row.key))}>×</button></td>
        </tr>
        {errors[index] && <tr className="variant-error-row"><td colSpan={7}><small className="dk-field-error" role="alert">{Object.values(errors[index]).join(' · ')}</small></td></tr>}
      </React.Fragment>)}
    </tbody></table></div>
    <button type="button" className="btn outline" onClick={() => setRows((current) => [...current, { ...blankRow(), price: current.at(-1)?.price || '', costPrice: current.at(-1)?.costPrice || '' }])}>{t('+ Thêm biến thể')}</button>
  </div>;
}

/**
 * Create (product + variants + optional opening stock, in one request) or edit
 * a product's basic information. Variants of an existing product are edited
 * from the product detail screen.
 */
export default function ProductForm({ product, categories, isOwner, canWriteStock, branch, onClose, onSaved, onManageCategories, t }) {
  const editing = !!product?.productId;
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState(null);
  const [rows, setRows] = useState(() => [blankRow()]);
  const [rowErrors, setRowErrors] = useState({});
  const [image, setImage] = useState({ file: null, url: product?.imageUrl || null, removed: false });
  const activeCategories = useMemo(() => flattenCategories(categories).filter((category) => category.status === 'ACTIVE'), [categories]);
  const showStock = !editing && canWriteStock && !!branch;

  function validate(data) {
    const errors = {};
    if (!String(data.name || '').trim()) errors.name = t('Vui lòng nhập tên sản phẩm.');
    if (!data.categoryId) errors.categoryId = t('Vui lòng chọn danh mục.');
    if (editing) return errors;
    const nextRowErrors = {};
    const seenSku = new Map();
    const seenCombo = new Map();
    rows.forEach((row, index) => {
      const issues = {};
      if (row.price === '' || Number(row.price) < 0 || !Number.isFinite(Number(row.price))) issues.price = t('Nhập giá bán hợp lệ');
      if (row.costPrice !== '' && Number(row.costPrice) < 0) issues.costPrice = t('Giá nhập không được âm');
      if (row.initialQuantity !== '' && (!Number.isInteger(Number(row.initialQuantity)) || Number(row.initialQuantity) < 0)) issues.initialQuantity = t('Tồn ban đầu phải là số nguyên ≥ 0');
      const sku = row.sku.trim().toLowerCase();
      if (sku && seenSku.has(sku)) issues.sku = `${t('SKU trùng với dòng')} ${seenSku.get(sku) + 1}`;
      if (sku) seenSku.set(sku, index);
      const combo = `${row.color.trim().toLowerCase()}|${row.size.trim().toLowerCase()}`;
      if (rows.length > 1 && combo === '|') issues.color = t('Nhập màu hoặc kích thước để phân biệt biến thể');
      else if (seenCombo.has(combo)) issues.color = `${t('Trùng màu/kích thước với dòng')} ${seenCombo.get(combo) + 1}`;
      seenCombo.set(combo, index);
      if (Object.keys(issues).length) nextRowErrors[index] = issues;
    });
    setRowErrors(nextRowErrors);
    if (Object.keys(nextRowErrors).length) errors.variants = t('Kiểm tra lại các dòng biến thể.');
    return errors;
  }

  async function submit(data) {
    setBusy(true);
    setFieldErrors(null);
    let uploaded = null;
    try {
      let imageUrl = image.removed ? null : image.url;
      if (image.file) {
        uploaded = (await uploadProductImage(image.file)).imageUrl;
        imageUrl = uploaded;
      }
      const basics = {
        name: data.name.trim(), categoryId: Number(data.categoryId),
        description: String(data.description || '').trim() || null, imageUrl,
      };
      let saved;
      if (editing) {
        saved = await updateProduct(product.productId, basics);
        notify.success(t('Đã cập nhật sản phẩm.'));
      } else {
        const needsAttributes = rows.some((row) => row.color.trim() || row.size.trim());
        const attributeIds = needsAttributes ? await ensureVariantAttributes() : {};
        const variants = rows.map((row) => {
          const color = row.color.trim();
          const size = row.size.trim();
          const attributes = [];
          if (color && attributeIds.color) attributes.push({ attributeId: attributeIds.color, value: color });
          if (size && attributeIds.size) attributes.push({ attributeId: attributeIds.size, value: size });
          return {
            variantName: [color, size].filter(Boolean).join(' / ') || t('Mặc định'),
            sku: row.sku.trim() || null,
            price: Number(row.price),
            costPrice: isOwner && row.costPrice !== '' ? Number(row.costPrice) : null,
            attributes,
            initialQuantity: showStock && row.initialQuantity !== '' ? Number(row.initialQuantity) : 0,
          };
        });
        const stocked = variants.some((variant) => variant.initialQuantity > 0);
        saved = await createProductFull({
          ...basics, productCode: String(data.productCode || '').trim() || null, variants,
          stockBranchId: stocked ? Number(branch.id) : null,
        });
        notify.success(stocked
          ? `${t('Đã tạo sản phẩm và nhập tồn ban đầu tại')} ${branch.name}.`
          : `${t('Đã tạo sản phẩm')} ${saved.productCode}. ${canWriteStock ? t('Bạn có thể nhập kho tại màn hình Kho hàng.') : ''}`);
      }
      onSaved(saved);
      return true;
    } catch (error) {
      if (uploaded) await deleteUnusedProductImage(uploaded).catch(() => {});
      setFieldErrors(Object.keys(error.fieldErrors || {}).length ? error.fieldErrors : null);
      notify.error(error, { title: editing ? t('Không thể cập nhật sản phẩm') : t('Không thể tạo sản phẩm') });
      return false;
    } finally {
      setBusy(false);
    }
  }

  return <FormDialog
    title={editing ? t('Sửa sản phẩm') : t('Thêm sản phẩm')}
    description={editing ? product.productCode : t('Điền thông tin theo từng nhóm. Mọi dữ liệu được lưu cùng lúc khi bạn bấm Tạo sản phẩm.')}
    size="xl" busy={busy} fieldErrors={fieldErrors} validate={validate} onClose={onClose} onSubmit={submit}
    submitLabel={editing ? t('Lưu thay đổi') : t('Tạo sản phẩm')}>
    <FormSection title={`A. ${t('Thông tin cơ bản')}`}>
      <FormField name="name" label={t('Tên sản phẩm')} required><input name="name" maxLength={200} defaultValue={product?.name || ''} autoFocus /></FormField>
      {!editing && <FormField name="productCode" label={t('Mã sản phẩm')} hint={t('Để trống để hệ thống tự tạo.')}><input name="productCode" maxLength={50} autoComplete="off" /></FormField>}
      <FormField name="categoryId" label={t('Danh mục')} required hint={!activeCategories.length ? t('Chưa có danh mục đang hoạt động.') : undefined}>
        <select name="categoryId" defaultValue={product?.categoryId || ''}>
          <option value="">{t('Chọn danh mục')}</option>
          {activeCategories.map((category) => <option key={category.categoryId} value={category.categoryId}>{'— '.repeat(category.depth)}{category.name}</option>)}
        </select>
      </FormField>
      {onManageCategories && <div className="dk-field form-inline-action"><span className="dk-field-label">&nbsp;</span><button type="button" className="link" onClick={onManageCategories}>{t('+ Tạo / quản lý danh mục')}</button></div>}
      <div className="dk-field-wide"><FormField name="description" label={t('Mô tả')}><textarea name="description" maxLength={16000} rows={3} defaultValue={product?.description || ''} /></FormField></div>
    </FormSection>
    <FormSection title={`B. ${t('Hình ảnh')}`}>
      <div className="dk-field-wide"><ImagePicker initialUrl={product?.imageUrl} onChange={setImage} t={t} /></div>
    </FormSection>
    {!editing && <FormSection title={`C. ${t('Biến thể và giá bán')}`} description={t('Mỗi dòng là một biến thể bán được (màu, kích thước, SKU, giá). Để trống SKU để hệ thống tự tạo.')}>
      <div className="dk-field-wide"><VariantRows rows={rows} setRows={setRows} errors={rowErrors} showCost={isOwner} showStock={showStock} t={t} /></div>
    </FormSection>}
    {!editing && <FormSection title={`D. ${t('Tồn kho')}`}>
      <p className="muted small dk-field-wide">{showStock
        ? `${t('Số lượng "Tồn ban đầu" sẽ được nhập vào chi nhánh')} ${branch.name} ${t('và ghi vào lịch sử kho. Để trống nếu chưa có hàng.')}`
        : canWriteStock ? t('Chọn một chi nhánh ở thanh trên cùng để nhập tồn ban đầu, hoặc nhập kho sau tại màn hình Kho hàng.')
          : t('Sau khi tạo, người có quyền kho sẽ nhập hàng tại màn hình Kho hàng.')}</p>
    </FormSection>}
  </FormDialog>;
}
