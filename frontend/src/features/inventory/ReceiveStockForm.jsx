import React, { useEffect, useMemo, useState } from 'react';
import { FormDialog, FormField, FormSection, notify } from '../../components/overlay/index.js';
import { createCategory, listCategories } from '../categories/api.js';
import { flattenCategories } from '../products/ProductForm.jsx';
import { createProductFull, createProductVariant, listProducts } from '../products/api.js';
import { changeInventory, listInventory } from './api.js';

const DEFAULT_CATEGORY = 'Chưa phân loại';

/**
 * Receive stock by SKU. An existing SKU adds to its stock; a new SKU creates the
 * product + variant with that SKU and its opening quantity in one request.
 */
export default function ReceiveStockForm({ items, branch, initialVariant, onClose, onSaved, t }) {
  const initial = items.find((item) => item.variantId === initialVariant);
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState(null);
  const [sku, setSku] = useState(initial?.sku || '');
  const [lookup, setLookup] = useState({ sku: initial?.sku || '', match: initial || null, checking: false });
  const [categories, setCategories] = useState([]);
  const typed = sku.trim();
  const isNew = typed && !lookup.checking && lookup.sku.toLowerCase() === typed.toLowerCase() && !lookup.match;
  const match = lookup.sku.toLowerCase() === typed.toLowerCase() ? lookup.match : null;
  const flatCategories = useMemo(() => flattenCategories(categories).filter((category) => category.status === 'ACTIVE'), [categories]);

  // Look the SKU up in the loaded list first, then ask the server (the list is paged).
  useEffect(() => {
    if (!typed) { setLookup({ sku: '', match: null, checking: false }); return undefined; }
    const local = items.find((item) => item.sku.toLowerCase() === typed.toLowerCase());
    if (local) { setLookup({ sku: typed, match: local, checking: false }); return undefined; }
    let active = true;
    setLookup({ sku: typed, match: null, checking: true });
    const timer = setTimeout(() => {
      listInventory({ branchId: branch.id, keyword: typed, size: 20 })
        .then((rows) => active && setLookup({ sku: typed, match: (rows || []).find((row) => row.sku.toLowerCase() === typed.toLowerCase()) || null, checking: false }))
        .catch(() => active && setLookup({ sku: typed, match: null, checking: false }));
    }, 300);
    return () => { active = false; clearTimeout(timer); };
  }, [typed, items, branch.id]);

  useEffect(() => {
    if (!isNew || categories.length) return;
    listCategories().then((rows) => setCategories(Array.isArray(rows) ? rows : [])).catch(() => {});
  }, [isNew]);

  function validate(data) {
    const errors = {};
    if (!typed) errors.sku = t('Vui lòng nhập SKU.');
    else if (lookup.checking) errors.sku = t('Đang kiểm tra SKU, vui lòng đợi.');
    else if (typed.length > 80) errors.sku = t('SKU tối đa 80 ký tự.');
    const quantity = Number(data.quantity);
    if (data.quantity === '' || !Number.isInteger(quantity) || quantity < 1) errors.quantity = t('Nhập số nguyên lớn hơn 0.');
    if (isNew) {
      if (!String(data.productName || '').trim()) errors.productName = t('Vui lòng nhập tên sản phẩm.');
      if (data.price === '' || !(Number(data.price) >= 0)) errors.price = t('Nhập giá bán hợp lệ.');
    }
    return errors;
  }

  async function categoryIdFor(name) {
    const wanted = (name || DEFAULT_CATEGORY).trim();
    const found = flattenCategories(categories).find((category) => category.name.trim().toLowerCase() === wanted.toLowerCase());
    if (found) {
      if (found.status !== 'ACTIVE') throw Object.assign(new Error(`${t('Danh mục đang ngừng hoạt động')}: ${found.name}`), { fieldErrors: { category: t('Danh mục đang ngừng hoạt động.') } });
      return found.categoryId;
    }
    return (await createCategory({ name: wanted, parentCategoryId: null, description: null })).categoryId;
  }

  async function submit(data) {
    const quantity = Number(data.quantity);
    setBusy(true);
    setFieldErrors(null);
    try {
      if (match) {
        const result = await changeInventory('import', { branchId: Number(branch.id), note: String(data.note || '').trim() || null, items: [{ variantId: match.variantId, quantity }] });
        const line = result.items?.[0];
        notify.success(`${t('SKU đã tồn tại')} · ${match.sku}: ${t('đã cộng thêm')} ${quantity} (${line?.quantityBefore} → ${line?.quantityAfter}).`);
      } else {
        const categoryId = await categoryIdFor(data.category);
        const name = data.productName.trim();
        const variantName = String(data.variantName || '').trim() || t('Mặc định');
        // Same rule as the file import: a new SKU joins the product with the same name and category.
        const sameProduct = ((await listProducts({ keyword: name, categoryId, size: 50 })) || [])
          .find((product) => product.name.trim().toLowerCase() === name.toLowerCase() && product.category_id === categoryId);
        if (sameProduct) {
          const variant = await createProductVariant(sameProduct.product_id, { sku: typed, variantName, price: Number(data.price), costPrice: null, barcode: null, attributes: [] });
          await changeInventory('import', { branchId: Number(branch.id), note: 'SKU mới tạo khi nhập kho', items: [{ variantId: variant.variant_id, quantity }] });
        } else {
          await createProductFull({ categoryId, name, variants: [{ sku: typed, variantName, price: Number(data.price), initialQuantity: quantity }], stockBranchId: Number(branch.id) });
        }
        notify.success(`${t('Đã tạo SKU mới')} ${typed} (${name}) ${t('và nhập')} ${quantity} ${t('vào')} ${branch.name}.`);
      }
      onSaved();
      return true;
    } catch (error) {
      setFieldErrors(Object.keys(error.fieldErrors || {}).length ? error.fieldErrors : null);
      notify.error(error, { title: t('Không thể nhập kho') });
      return false;
    } finally {
      setBusy(false);
    }
  }

  return <FormDialog title={t('Nhập kho')} eyebrow={branch.name} size={isNew ? 'lg' : 'md'} busy={busy} fieldErrors={fieldErrors}
    validate={validate} onClose={onClose} onSubmit={submit} submitLabel={isNew ? t('Tạo SKU và nhập kho') : t('Xác nhận nhập kho')}>
    <div className="dk-field-wide"><FormField name="sku" label="SKU" required hint={t('Gõ hoặc chọn SKU. SKU chưa có sẽ được tạo thành sản phẩm mới.')}>
      <input name="sku" list="receive-sku-options" maxLength={80} value={sku} onChange={(event) => setSku(event.target.value)} autoComplete="off" autoFocus placeholder="VD: ASM-TRANG-M" />
    </FormField>
    <datalist id="receive-sku-options">{items.map((item) => <option key={item.variantId} value={item.sku}>{item.productName} · {item.variantName}</option>)}</datalist></div>
    {typed && <div className="dk-field-wide stock-snapshot" role="status">
      {lookup.checking ? <span>{t('Đang kiểm tra SKU…')}</span>
        : match ? <><span className="badge green">{t('Đã tồn tại · sẽ cộng thêm')}</span><span><b>{match.productName}</b> · {match.variantName}</span><span>{t('Tồn thực')}: <b>{match.quantity}</b></span><span>{t('Khả dụng')}: <b>{match.available}</b></span></>
          : <><span className="badge amber">{t('SKU mới · sẽ tạo sản phẩm')}</span><span>{t('Nhập thông tin sản phẩm bên dưới.')}</span></>}
    </div>}
    <FormField name="quantity" label={t('Số lượng nhập')} required><input name="quantity" type="number" min="1" step="1" inputMode="numeric" /></FormField>
    {!isNew && <FormField name="note" label={t('Ghi chú')}><input name="note" maxLength={255} /></FormField>}
    {isNew && <FormSection title={t('Thông tin SKU mới')} description={t('Sản phẩm, biến thể và tồn ban đầu được lưu cùng lúc.')}>
      <FormField name="productName" label={t('Tên sản phẩm')} required><input name="productName" maxLength={200} /></FormField>
      <FormField name="variantName" label={t('Tên biến thể')} hint={t('VD: Trắng / M')}><input name="variantName" maxLength={200} placeholder={t('Mặc định')} /></FormField>
      <FormField name="category" label={t('Danh mục')} hint={t('Chọn hoặc gõ tên mới; để trống sẽ dùng "Chưa phân loại".')}>
        <input name="category" list="receive-category-options" maxLength={100} autoComplete="off" />
      </FormField>
      <datalist id="receive-category-options">{flatCategories.map((category) => <option key={category.categoryId} value={category.name} />)}</datalist>
      <FormField name="price" label={t('Giá bán')} required><input name="price" type="number" min="0" step="1000" /></FormField>
    </FormSection>}
  </FormDialog>;
}
