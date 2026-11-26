import React, { useEffect, useMemo, useState } from 'react';
import { Dialog, FormDialog, FormField, FormSection, notify } from '../../components/overlay/index.js';
import { quickSearchCustomers } from '../customers/api.js';
import { createPreorder } from './api.js';

const PHONE = /^(?:\+?84|0)\d{9,10}$/;

/**
 * Pre-order for a variant that is out of stock at the branch. The request goes to
 * POST /preorders, which re-checks stock and refuses items that are available.
 * options: [{ variantId, productName, variantName, sku, price, available }]
 */
export default function PreorderDialog({ branch, options, initialVariantId, onClose, onCreated, t, formatCurrency }) {
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState(null);
  const [variantId, setVariantId] = useState(initialVariantId ? String(initialVariantId) : '');
  const [quantity, setQuantity] = useState(1);
  const [created, setCreated] = useState(null);
  const [lookup, setLookup] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [customer, setCustomer] = useState(null);
  const selected = options.find((option) => String(option.variantId) === variantId);
  const estimate = selected ? Number(selected.price) * Math.max(0, Number(quantity) || 0) : 0;
  const choices = useMemo(() => options.filter((option) => option.available <= 0), [options]);

  useEffect(() => {
    if (lookup.trim().length < 2) { setSuggestions([]); return undefined; }
    let active = true;
    const timer = setTimeout(() => quickSearchCustomers(lookup.trim()).then((rows) => active && setSuggestions(rows || [])).catch(() => active && setSuggestions([])), 250);
    return () => { active = false; clearTimeout(timer); };
  }, [lookup]);

  function validate(data) {
    const errors = {};
    if (!variantId) errors.variantId = t('Vui lòng chọn sản phẩm cần đặt trước.');
    const qty = Number(data.quantity);
    if (!Number.isInteger(qty) || qty < 1 || qty > 999) errors.quantity = t('Số lượng từ 1 đến 999.');
    if (!String(data.fullName || '').trim()) errors.fullName = t('Vui lòng nhập họ tên.');
    if (!PHONE.test(String(data.phone || '').replace(/[\s.-]/g, ''))) errors.phone = t('Số điện thoại gồm 10–11 chữ số, bắt đầu bằng 0 hoặc +84.');
    if (!String(data.address || '').trim()) errors.address = t('Vui lòng nhập địa chỉ.');
    if (data.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(data.email).trim())) errors.email = t('Email chưa đúng định dạng.');
    return errors;
  }

  async function submit(data) {
    setBusy(true);
    setFieldErrors(null);
    try {
      const order = await createPreorder({
        branchId: Number(branch.id),
        customer: { fullName: data.fullName.trim(), phone: data.phone.trim(), email: String(data.email || '').trim() || null, address: data.address.trim() },
        items: [{ variantId: Number(variantId), quantity: Number(data.quantity) }],
        note: String(data.note || '').trim() || null,
      });
      setCreated(order);
      notify.success(`${t('Đã tạo đơn đặt trước')} ${order.preorderCode}.`);
      onCreated?.(order);
      return true;
    } catch (error) {
      const mapped = {};
      for (const [field, message] of Object.entries(error.fieldErrors || {})) mapped[field === 'quantity' ? 'quantity' : field] = message;
      setFieldErrors(Object.keys(mapped).length ? mapped : null);
      notify.error(error, { title: t('Không thể tạo đơn đặt trước') });
      return false;
    } finally {
      setBusy(false);
    }
  }

  if (created) {
    return <Dialog open size="md" title={t('Đặt trước thành công')} onClose={onClose} className="preorder-success-dialog"
      footer={<><button className="btn outline" type="button" onClick={() => navigator.clipboard?.writeText(created.preorderCode).then(() => notify.info(t('Đã sao chép mã đơn.')))}>{t('Sao chép mã')}</button><button className="btn primary" type="button" onClick={onClose}>{t('Hoàn tất')}</button></>}>
      <div className="preorder-success">
        <span className="import-result-icon" aria-hidden="true">✓</span>
        <p className="muted">{t('Mã đơn đặt trước')}</p>
        <p className="preorder-code">{created.preorderCode}</p>
        <dl className="dk-meta-list">
          <div><span>{t('Khách hàng')}</span><b>{created.customer.fullName} · {created.customer.phone}</b></div>
          <div><span>{t('Sản phẩm')}</span><b>{created.items.map((item) => `${item.productName} × ${item.quantity}`).join(', ')}</b></div>
          <div><span>{t('Tạm tính')}</span><b>{formatCurrency(Number(created.totalAmount))}</b></div>
          <div><span>{t('Trạng thái')}</span><b>{t('Chờ hàng')}</b></div>
        </dl>
        <p className="muted small">{t('Khi chi nhánh nhập kho, hệ thống phân bổ hàng cho đơn theo thứ tự đặt trước (FIFO).')}</p>
      </div>
    </Dialog>;
  }

  return <FormDialog title={t('Tạo đơn đặt trước')} eyebrow={branch.name} size="lg" busy={busy} fieldErrors={fieldErrors}
    validate={validate} onClose={onClose} onSubmit={submit} submitLabel={t('Gửi đặt trước')}>
    <FormSection title={t('Sản phẩm')}>
      <div className="dk-field-wide"><FormField name="variantId" label={t('Sản phẩm hết hàng')} required hint={!choices.length ? t('Hiện không có sản phẩm hết hàng tại chi nhánh này.') : undefined}>
        <select name="variantId" value={variantId} onChange={(event) => setVariantId(event.target.value)}>
          <option value="">{t('Chọn sản phẩm / biến thể')}</option>
          {choices.map((option) => <option key={option.variantId} value={option.variantId}>{option.productName} · {option.variantName} · {option.sku} · {formatCurrency(Number(option.price))}</option>)}
        </select>
      </FormField></div>
      {selected && <div className="dk-field-wide preorder-product"><b>{selected.productName}</b><span>{selected.variantName} · SKU {selected.sku}</span><span className="badge amber">{t('Hết hàng')}</span><span>{formatCurrency(Number(selected.price))}</span></div>}
      <FormField name="quantity" label={t('Số lượng')} required><input name="quantity" type="number" min="1" max="999" step="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></FormField>
      <div className="dk-field preorder-estimate"><span className="dk-field-label">{t('Tạm tính')}</span><b>{formatCurrency(estimate)}</b></div>
    </FormSection>
    <FormSection title={t('Thông tin khách hàng')}>
      <div className="dk-field-wide customer-lookup">
        <FormField label={t('Tìm khách hàng đã có (tùy chọn)')}><input value={lookup} onChange={(event) => setLookup(event.target.value)} placeholder={t('Tên hoặc số điện thoại')} /></FormField>
        {suggestions.length > 0 && <div className="customer-suggestions">{suggestions.map((item) => <button type="button" key={item.customerId} onClick={() => { setCustomer(item); setSuggestions([]); setLookup(item.fullName); }}>{item.fullName} · {item.phone || item.email}</button>)}</div>}
      </div>
      <FormField name="fullName" label={t('Họ tên')} required><input key={`n${customer?.customerId || ''}`} name="fullName" maxLength={150} defaultValue={customer?.fullName || ''} /></FormField>
      <FormField name="phone" label={t('Số điện thoại')} required><input key={`p${customer?.customerId || ''}`} name="phone" type="tel" maxLength={20} defaultValue={customer?.phone || ''} /></FormField>
      <div className="dk-field-wide"><FormField name="address" label={t('Địa chỉ')} required><input key={`a${customer?.customerId || ''}`} name="address" maxLength={255} defaultValue={customer?.address || ''} /></FormField></div>
      <FormField name="email" label={t('Email (tùy chọn)')}><input key={`e${customer?.customerId || ''}`} name="email" type="email" maxLength={255} defaultValue={customer?.email || ''} /></FormField>
      <FormField name="note" label={t('Ghi chú')}><input name="note" maxLength={255} /></FormField>
    </FormSection>
    <p className="muted small">{t('Đơn đặt trước không trừ tồn kho khi tạo. Hệ thống chỉ nhận đặt trước khi sản phẩm không đủ hàng khả dụng.')}</p>
  </FormDialog>;
}
