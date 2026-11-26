import React, { useMemo, useState } from 'react';
import { confirmAction, Drawer, FormDialog, FormField, notify } from '../../components/overlay/index.js';
import { StatusBadge } from '../../components/states.jsx';
import { flattenCategories } from '../products/ProductForm.jsx';
import { createCategory, setCategoryStatus, updateCategory } from './api.js';

function descendantIds(category) {
  return [category.categoryId, ...(category.children || []).flatMap(descendantIds)];
}

export function CategoryForm({ category, categories, onClose, onSaved, t }) {
  const editing = !!category?.categoryId;
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState(null);
  const flat = useMemo(() => flattenCategories(categories), [categories]);
  // A category cannot be moved under itself or one of its children.
  const blocked = useMemo(() => {
    const node = flat.find((item) => item.categoryId === category?.categoryId);
    return new Set(node ? descendantIds(node) : []);
  }, [flat, category]);

  return <FormDialog title={editing ? t('Sửa danh mục') : t('Thêm danh mục')} size="md" busy={busy} fieldErrors={fieldErrors}
    submitLabel={editing ? t('Lưu thay đổi') : t('Tạo danh mục')} onClose={onClose}
    validate={(data) => (String(data.name || '').trim() ? {} : { name: t('Vui lòng nhập tên danh mục.') })}
    onSubmit={async (data) => {
      const payload = {
        name: data.name.trim(),
        parentCategoryId: data.parentCategoryId ? Number(data.parentCategoryId) : null,
        description: String(data.description || '').trim() || null,
      };
      setBusy(true);
      setFieldErrors(null);
      try {
        const saved = editing ? await updateCategory(category.categoryId, payload) : await createCategory(payload);
        notify.success(editing ? t('Đã cập nhật danh mục.') : `${t('Đã tạo danh mục')} "${saved.name}".`);
        onSaved(saved);
        return true;
      } catch (error) {
        setFieldErrors(Object.keys(error.fieldErrors || {}).length ? error.fieldErrors : null);
        notify.error(error, { title: editing ? t('Không thể cập nhật danh mục') : t('Không thể tạo danh mục') });
        return false;
      } finally {
        setBusy(false);
      }
    }}>
    <FormField name="name" label={t('Tên danh mục')} required><input name="name" maxLength={100} defaultValue={category?.name || ''} autoFocus /></FormField>
    <FormField name="parentCategoryId" label={t('Danh mục cha')} hint={t('Để trống nếu là danh mục gốc.')}>
      <select name="parentCategoryId" defaultValue={category?.parentCategoryId || ''}>
        <option value="">{t('— Không có (danh mục gốc) —')}</option>
        {flat.filter((item) => !blocked.has(item.categoryId)).map((item) => <option key={item.categoryId} value={item.categoryId}>{'— '.repeat(item.depth)}{item.name}</option>)}
      </select>
    </FormField>
    <div className="dk-field-wide"><FormField name="description" label={t('Mô tả')}><textarea name="description" rows={3} maxLength={16000} defaultValue={category?.description || ''} /></FormField></div>
  </FormDialog>;
}

export default function CategoryManager({ categories, canToggle, onClose, onChanged, t }) {
  const [editing, setEditing] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const flat = useMemo(() => flattenCategories(categories), [categories]);

  async function toggle(category) {
    const deactivate = category.status === 'ACTIVE';
    if (deactivate && !(await confirmAction({
      title: t('Ngừng hoạt động danh mục?'),
      description: `"${category.name}" ${t('sẽ không còn được chọn khi tạo sản phẩm mới.')}`,
      confirmLabel: t('Ngừng hoạt động'),
    }))) return;
    setBusyId(category.categoryId);
    try {
      await setCategoryStatus(category.categoryId, deactivate ? 'INACTIVE' : 'ACTIVE');
      notify.success(deactivate ? t('Đã ngừng hoạt động danh mục.') : t('Đã kích hoạt danh mục.'));
      await onChanged();
    } catch (error) {
      notify.error(error, { title: t('Không cập nhật được danh mục') });
    } finally {
      setBusyId(null);
    }
  }

  return <>
    <Drawer open title={t('Danh mục sản phẩm')} description={t('Tổ chức sản phẩm theo nhóm để tìm kiếm và báo cáo dễ hơn.')} onClose={onClose}
      footer={<button className="btn primary" type="button" onClick={() => setEditing({})}>{t('+ Thêm danh mục')}</button>}>
      {!flat.length ? <div className="empty"><h3>{t('Chưa có danh mục')}</h3><p>{t('Tạo danh mục đầu tiên, ví dụ: Áo, Quần, Phụ kiện.')}</p></div>
        : <ul className="category-tree">{flat.map((category) => <li key={category.categoryId} style={{ paddingLeft: `${category.depth * 18}px` }}>
          <div><b>{category.name}</b>{category.description && <small className="block muted">{category.description}</small>}</div>
          <StatusBadge status={category.status} />
          <div className="actions">
            <button className="link" onClick={() => setEditing(category)}>{t('Sửa')}</button>
            {canToggle && <button className={`link${category.status === 'ACTIVE' ? ' danger' : ''}`} disabled={busyId === category.categoryId} onClick={() => toggle(category)}>{category.status === 'ACTIVE' ? t('Ngừng') : t('Kích hoạt')}</button>}
          </div>
        </li>)}</ul>}
    </Drawer>
    {editing && <CategoryForm category={editing.categoryId ? editing : null} categories={categories} t={t}
      onClose={() => setEditing(null)} onSaved={async () => { setEditing(null); await onChanged(); }} />}
  </>;
}
