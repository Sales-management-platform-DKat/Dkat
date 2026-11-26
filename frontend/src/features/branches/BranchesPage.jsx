import React, { useEffect, useMemo, useState } from 'react';
import { useLanguage } from '../../i18n/index.js';
import { createBranch, listBranches, setBranchStatus, updateBranch } from './api.js';
import { listEmployees } from '../employees/api.js';
import { confirmAction, Drawer, FormDialog, FormField, notify } from '../../components/overlay/index.js';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../../components/states.jsx';

const PHONE = /^\+?[0-9][0-9 .-]{5,18}$/;
const CODE = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;

export function notifyBranchesChanged() {
  window.dispatchEvent(new Event('dkat-branches-changed'));
}

function BranchForm({ branch, onClose, onSaved, t }) {
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState(null);
  const editing = !!branch?.id;

  function validate(data) {
    const errors = {};
    if (!String(data.name || '').trim()) errors.name = t('Vui lòng nhập tên chi nhánh.');
    if (!String(data.address || '').trim()) errors.address = t('Vui lòng nhập địa chỉ.');
    const phone = String(data.phone || '').trim();
    if (phone && !PHONE.test(phone)) errors.phone = t('Số điện thoại chỉ gồm chữ số (6–19 ký tự).');
    const code = String(data.branchCode || '').trim();
    if (code && !CODE.test(code)) errors.branchCode = t('Mã chỉ gồm chữ không dấu, số, "-" hoặc "_", không có khoảng trắng.');
    return errors;
  }

  async function submit(data) {
    const payload = {
      name: data.name.trim(),
      address: data.address.trim(),
      phone: String(data.phone || '').trim() || null,
      branchCode: String(data.branchCode || '').trim() || null,
    };
    setBusy(true);
    setFieldErrors(null);
    try {
      const saved = editing ? await updateBranch(branch.id, payload) : await createBranch(payload);
      notify.success(editing ? t('Đã cập nhật chi nhánh.') : `${t('Đã tạo chi nhánh thành công')}: ${saved.name} (${saved.branchCode})`);
      onSaved(saved);
      return true;
    } catch (error) {
      setFieldErrors(error.fieldErrors && Object.keys(error.fieldErrors).length ? error.fieldErrors : null);
      notify.error(error, { title: editing ? t('Không thể cập nhật chi nhánh') : t('Không thể tạo chi nhánh') });
      return false;
    } finally {
      setBusy(false);
    }
  }

  return <FormDialog
    title={editing ? t('Sửa chi nhánh') : t('Thêm chi nhánh')}
    description={editing ? `${branch.branchCode}` : t('Chi nhánh mới sẽ được tạo tồn kho 0 cho mọi sản phẩm đang bán.')}
    busy={busy}
    fieldErrors={fieldErrors}
    validate={validate}
    submitLabel={editing ? t('Lưu thay đổi') : t('Tạo chi nhánh')}
    onClose={onClose}
    onSubmit={submit}
  >
    <FormField name="name" label={t('Tên chi nhánh')} required><input name="name" maxLength={150} defaultValue={branch?.name || ''} autoFocus /></FormField>
    <FormField name="address" label={t('Địa chỉ')} required><input name="address" maxLength={255} defaultValue={branch?.address || ''} /></FormField>
    <FormField name="phone" label={t('Điện thoại')}><input name="phone" type="tel" maxLength={20} defaultValue={branch?.phone || ''} /></FormField>
    <FormField name="branchCode" label={t('Mã chi nhánh')} hint={editing ? t('Để trống để giữ mã hiện tại.') : t('Để trống để hệ thống tự tạo (CN01, CN02…).')}>
      <input name="branchCode" maxLength={30} defaultValue={branch?.branchCode || ''} placeholder="CN01" autoComplete="off" />
    </FormField>
  </FormDialog>;
}

function BranchDetail({ branch, canManage, onClose, onEdit, t, formatDateTime }) {
  const [staff, setStaff] = useState(null);
  useEffect(() => {
    let active = true;
    listEmployees({ branchId: branch.id, pageSize: 100 })
      .then((result) => active && setStaff(result?.items || []))
      .catch(() => active && setStaff(null));
    return () => { active = false; };
  }, [branch.id]);

  return <Drawer open title={branch.name} eyebrow={branch.branchCode} onClose={onClose}
    footer={canManage && <button className="btn primary" type="button" onClick={onEdit}>{t('Sửa thông tin')}</button>}>
    <dl className="dk-meta-list">
      <div><span>{t('Mã chi nhánh')}</span><b>{branch.branchCode}</b></div>
      <div><span>{t('Địa chỉ')}</span><b>{branch.address || '—'}</b></div>
      <div><span>{t('Điện thoại')}</span><b>{branch.phone || '—'}</b></div>
      <div><span>{t('Trạng thái')}</span><StatusBadge status={branch.status} /></div>
      <div><span>{t('Ngày tạo')}</span><b>{branch.createdAt ? formatDateTime(new Date(branch.createdAt)) : '—'}</b></div>
    </dl>
    <h3 className="detail-subtitle">{t('Nhân sự được phân công')}</h3>
    {staff === null ? <p className="muted small">{t('Không có quyền xem hoặc chưa tải được danh sách nhân sự.')}</p>
      : !staff.length ? <p className="muted small">{t('Chưa có nhân sự được phân công.')}</p>
        : <ul className="detail-list">{staff.map((person) => <li key={person.id}><b>{person.full_name}</b><small>{person.role === 'manager' ? t('Quản lý') : t('Nhân viên')} · {person.username}</small></li>)}</ul>}
  </Drawer>;
}

export default function BranchesPage({ canManage, onBranchesChanged }) {
  const changed = () => { notifyBranchesChanged(); onBranchesChanged?.(); };
  const { t, formatDateTime } = useLanguage();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [editing, setEditing] = useState(null);
  const [viewing, setViewing] = useState(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');

  async function reload() {
    setLoading(true);
    setLoadError(null);
    try { setRows(await listBranches()); }
    catch (error) { setRows([]); setLoadError(error); }
    finally { setLoading(false); }
  }
  useEffect(() => { reload(); }, []);

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase();
    return rows.filter((row) => (!status || row.status === status)
      && (!term || [row.name, row.branchCode, row.address, row.phone].some((value) => String(value || '').toLowerCase().includes(term))));
  }, [rows, query, status]);

  async function toggle(row) {
    const deactivate = row.status === 'ACTIVE';
    const ok = await confirmAction({
      title: deactivate ? t('Ngừng hoạt động chi nhánh?') : t('Kích hoạt lại chi nhánh?'),
      description: deactivate ? `${row.name}: ${t('nhân viên sẽ không thể bán hàng tại chi nhánh này.')}` : row.name,
      confirmLabel: deactivate ? t('Ngừng hoạt động') : t('Kích hoạt'),
      tone: deactivate ? 'danger' : 'primary',
    });
    if (!ok) return;
    setBusyId(row.id);
    try {
      await setBranchStatus(row.id, deactivate ? 'INACTIVE' : 'ACTIVE');
      notify.success(deactivate ? t('Đã ngừng hoạt động chi nhánh.') : t('Đã kích hoạt chi nhánh.'));
      await reload();
      changed();
    } catch (error) {
      notify.error(error, { title: t('Không đổi được trạng thái chi nhánh') });
    } finally {
      setBusyId(null);
    }
  }

  async function saved(branch) {
    setEditing(null);
    await reload();
    changed();
    if (viewing?.id === branch.id) setViewing(branch);
  }

  return <>
    <div className="toolbar">
      <input aria-label={t('Tìm chi nhánh')} placeholder={t('Tìm theo tên, mã hoặc địa chỉ')} value={query} onChange={(event) => setQuery(event.target.value)} />
      <select aria-label={t('Trạng thái')} value={status} onChange={(event) => setStatus(event.target.value)}>
        <option value="">{t('Mọi trạng thái')}</option><option value="ACTIVE">{t('Hoạt động')}</option><option value="INACTIVE">{t('Ngừng hoạt động')}</option>
      </select>
      {canManage && <button className="btn primary" onClick={() => setEditing({})}>{t('+ Thêm chi nhánh')}</button>}
    </div>
    <section className="panel">
      {loading ? <LoadingState label={t('Đang tải chi nhánh…')} />
        : loadError ? <ErrorState error={loadError} onRetry={reload} />
          : !visible.length ? <EmptyState title={rows.length ? t('Không có chi nhánh phù hợp') : t('Chưa có chi nhánh')}
            description={!rows.length && canManage ? t('Tạo chi nhánh đầu tiên để bắt đầu bán hàng và quản lý kho.') : ''}
            action={!rows.length && canManage && <button className="btn primary" onClick={() => setEditing({})}>{t('+ Thêm chi nhánh')}</button>} />
            : <div className="table-wrap"><table><thead><tr>{[t('Mã'), t('Tên chi nhánh'), t('Địa chỉ'), t('Điện thoại'), t('Trạng thái'), t('Thao tác')].map((x) => <th key={x}>{x}</th>)}</tr></thead>
              <tbody>{visible.map((row) => <tr key={row.id} className="clickable" onClick={() => setViewing(row)}>
                <td><b>{row.branchCode}</b></td><td>{row.name}</td><td>{row.address || '—'}</td><td>{row.phone || '—'}</td>
                <td><StatusBadge status={row.status} /></td>
                <td onClick={(event) => event.stopPropagation()}><div className="actions">
                  <button className="link" onClick={() => setViewing(row)}>{t('Chi tiết')}</button>
                  {canManage && <button className="link" onClick={() => setEditing(row)}>{t('Sửa')}</button>}
                  {canManage && <button className={`link${row.status === 'ACTIVE' ? ' danger' : ''}`} disabled={busyId === row.id} onClick={() => toggle(row)}>{row.status === 'ACTIVE' ? t('Ngừng hoạt động') : t('Kích hoạt')}</button>}
                </div></td>
              </tr>)}</tbody></table></div>}
    </section>
    {editing && <BranchForm branch={editing} t={t} onClose={() => setEditing(null)} onSaved={saved} />}
    {viewing && !editing && <BranchDetail branch={viewing} canManage={canManage} t={t} formatDateTime={formatDateTime}
      onClose={() => setViewing(null)} onEdit={() => setEditing(viewing)} />}
  </>;
}
