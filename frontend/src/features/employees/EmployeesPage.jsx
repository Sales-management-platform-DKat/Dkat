import React, { useEffect, useMemo, useState } from 'react';
import { useLanguage } from '../../i18n/index.js';
import { listBranches } from '../branches/api.js';
import { listSalesOrders } from '../orders/api.js';
import { assignEmployeeBranches, createEmployee, listEmployees, resetEmployeePassword, setEmployeeStatus, updateEmployee } from './api.js';
import { confirmAction, FormDialog, FormField, FormSection, notify } from '../../components/overlay/index.js';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../../components/states.jsx';

const USERNAME = /^[A-Za-z0-9._-]{3,32}$/;

function EmployeeForm({ employee, branches, onClose, onSaved, t }) {
  const creating = !employee?.id;
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState(null);
  const [branchIds, setBranchIds] = useState(employee?.branches?.map((branch) => branch.id) || []);

  function validate(data) {
    const errors = {};
    if (creating && !USERNAME.test(String(data.username || '').trim())) errors.username = t('3–32 ký tự: chữ không dấu, số, ".", "_" hoặc "-".');
    if (!String(data.full_name || '').trim()) errors.full_name = t('Vui lòng nhập họ tên.');
    if (data.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(data.email).trim())) errors.email = t('Email chưa đúng định dạng.');
    if (creating && String(data.password || '').length < 12) errors.password = t('Mật khẩu cần ít nhất 12 ký tự.');
    if (!branchIds.length) errors.branch_ids = t('Hãy phân công ít nhất một chi nhánh.');
    return errors;
  }

  async function submit(data) {
    setBusy(true);
    setFieldErrors(null);
    try {
      if (creating) {
        await createEmployee({
          username: data.username.trim(), full_name: data.full_name.trim(), email: data.email.trim() || null,
          phone: data.phone.trim() || null, password: data.password, role: data.role, branch_ids: branchIds,
        });
        notify.success(`${t('Đã tạo tài khoản')} ${data.username.trim().toLowerCase()}.`);
      } else {
        await updateEmployee(employee.id, { full_name: data.full_name.trim(), email: data.email.trim() || null, phone: data.phone.trim() || null });
        await assignEmployeeBranches(employee.id, branchIds);
        notify.success(t('Đã cập nhật nhân viên.'));
      }
      onSaved();
      return true;
    } catch (error) {
      setFieldErrors(Object.keys(error.fieldErrors || {}).length ? error.fieldErrors : null);
      notify.error(error, { title: creating ? t('Không thể tạo tài khoản') : t('Không thể cập nhật nhân viên') });
      return false;
    } finally {
      setBusy(false);
    }
  }

  return <FormDialog title={creating ? t('Thêm nhân viên') : t('Cập nhật nhân viên')} size="lg" busy={busy}
    fieldErrors={fieldErrors} validate={validate} onClose={onClose} onSubmit={submit}
    submitLabel={creating ? t('Tạo tài khoản') : t('Lưu thay đổi')}>
    <FormSection title={t('Tài khoản')}>
      {creating ? <FormField name="username" label={t('Tên đăng nhập')} required hint={t('Dùng để đăng nhập; không phân biệt hoa thường.')}><input name="username" maxLength={32} autoComplete="off" autoFocus /></FormField>
        : <FormField label={t('Tên đăng nhập')}><input value={employee.username} disabled /></FormField>}
      <FormField name="role" label={t('Vai trò')} required>
        <select name="role" defaultValue={employee?.role === 'manager' ? 'manager' : 'staff'} disabled={!creating}>
          <option value="staff">{t('Nhân viên bán hàng')}</option><option value="manager">{t('Quản lý chi nhánh')}</option>
        </select>
      </FormField>
      {creating && <FormField name="password" label={t('Mật khẩu khởi tạo')} required hint={t('Ít nhất 12 ký tự.')}><input name="password" type="password" maxLength={128} autoComplete="new-password" /></FormField>}
    </FormSection>
    <FormSection title={t('Thông tin cá nhân')}>
      <FormField name="full_name" label={t('Họ tên')} required><input name="full_name" maxLength={150} defaultValue={employee?.full_name || ''} autoFocus={!creating} /></FormField>
      <FormField name="phone" label={t('Số điện thoại')}><input name="phone" type="tel" maxLength={20} defaultValue={employee?.phone || ''} /></FormField>
      <FormField name="email" label={t('Email')}><input name="email" type="email" maxLength={255} defaultValue={employee?.email || ''} /></FormField>
    </FormSection>
    <FormSection title={t('Chi nhánh được phân công')}>
      <FormField name="branch_ids" label={t('Chọn chi nhánh')} required>
        <div className="employee-branches" role="group">
          {branches.length ? branches.map((branch) => {
            const checked = branchIds.includes(branch.id);
            return <label key={branch.id} className="employee-branch-option">
              <input type="checkbox" checked={checked} disabled={branch.status !== 'ACTIVE' && !checked}
                onChange={() => setBranchIds((ids) => checked ? ids.filter((id) => id !== branch.id) : [...ids, branch.id])} />
              <span>{branch.name}</span><small>{branch.branchCode}</small>
            </label>;
          }) : <p className="muted">{t('Chưa có chi nhánh đang hoạt động.')}</p>}
        </div>
      </FormField>
    </FormSection>
  </FormDialog>;
}

function PasswordForm({ employee, onClose, t }) {
  const [busy, setBusy] = useState(false);
  return <FormDialog title={t('Đặt lại mật khẩu')} description={`${employee.full_name} · ${employee.username}`} size="sm" busy={busy}
    submitLabel={t('Đặt lại')} onClose={onClose}
    validate={(data) => String(data.new_password || '').length < 12 ? { new_password: t('Mật khẩu cần ít nhất 12 ký tự.') } : {}}
    onSubmit={async (data) => {
      setBusy(true);
      try {
        await resetEmployeePassword(employee.id, data.new_password);
        notify.success(t('Đã đặt lại mật khẩu và thu hồi phiên đăng nhập.'));
        onClose();
        return true;
      } catch (error) {
        notify.error(error, { title: t('Không đặt lại được mật khẩu') });
        return false;
      } finally { setBusy(false); }
    }}>
    <FormField name="new_password" label={t('Mật khẩu mới')} required hint={t('Các phiên đăng nhập hiện tại của nhân viên sẽ bị thu hồi.')}><input name="new_password" type="password" maxLength={128} autoComplete="new-password" autoFocus /></FormField>
  </FormDialog>;
}

// Paid orders of the last 30 days per employee (managers monitor their branch).
function usePerformance(branchId) {
  const [stats, setStats] = useState(new Map());
  useEffect(() => {
    let active = true;
    if (!branchId) { setStats(new Map()); return undefined; }
    listSalesOrders({ branchId, status: 'PAID', size: 100 }).then((orders) => {
      if (!active) return;
      const since = Date.now() - 30 * 86400000;
      const map = new Map();
      for (const order of orders || []) {
        if (new Date(order.paidAt || order.createdAt).getTime() < since) continue;
        const entry = map.get(order.createdBy) || { count: 0, revenue: 0 };
        entry.count += 1;
        entry.revenue += Number(order.totalAmount || 0);
        map.set(order.createdBy, entry);
      }
      setStats(map);
    }).catch(() => active && setStats(new Map()));
    return () => { active = false; };
  }, [branchId]);
  return stats;
}

export default function EmployeesPage({ canManage = false, branchId }) {
  const { t, formatCurrency } = useLanguage();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [employees, setEmployees] = useState([]);
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [editing, setEditing] = useState(null);
  const [passwordTarget, setPasswordTarget] = useState(null);
  const performance = usePerformance(branchId);

  useEffect(() => { const timer = setTimeout(() => setSearch(query.trim()), 250); return () => clearTimeout(timer); }, [query]);

  async function reload(term = search) {
    setLoading(true);
    setLoadError(null);
    try {
      const [usersResult, branchesResult] = await Promise.all([
        listEmployees({ query: term, page: 1, pageSize: 100, branchId: canManage ? undefined : branchId }),
        listBranches(),
      ]);
      setEmployees(Array.isArray(usersResult?.items) ? usersResult.items : []);
      setBranches(Array.isArray(branchesResult) ? branchesResult : []);
    } catch (error) {
      setEmployees([]);
      setLoadError(error);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { reload(); }, [search, branchId, canManage]);

  async function toggleStatus(employee) {
    const locking = employee.status === 'ACTIVE';
    const ok = await confirmAction({
      title: locking ? t('Khóa tài khoản?') : t('Mở khóa tài khoản?'),
      description: locking ? `${employee.full_name} ${t('sẽ bị đăng xuất và không thể đăng nhập cho đến khi được mở khóa.')}` : employee.full_name,
      confirmLabel: locking ? t('Khóa tài khoản') : t('Mở khóa'),
      tone: locking ? 'danger' : 'primary',
    });
    if (!ok) return;
    setBusyId(employee.id);
    try {
      await setEmployeeStatus(employee.id, locking ? 'LOCKED' : 'ACTIVE');
      notify.success(locking ? t('Đã khóa tài khoản và thu hồi phiên đăng nhập.') : t('Đã mở khóa tài khoản.'));
      await reload();
    } catch (error) {
      notify.error(error, { title: t('Không cập nhật được trạng thái') });
    } finally {
      setBusyId(null);
    }
  }

  const summary = useMemo(() => ({
    total: employees.length,
    active: employees.filter((employee) => employee.status === 'ACTIVE').length,
    managers: employees.filter((employee) => employee.role === 'manager').length,
  }), [employees]);

  return <>
    <div className="toolbar employee-toolbar">
      <input aria-label={t('Tìm nhân viên')} placeholder={t('Tìm theo tên, username, email hoặc điện thoại')} value={query} onChange={(event) => setQuery(event.target.value)} />
      {canManage && <button className="btn primary" onClick={() => setEditing({})}>{t('+ Thêm nhân viên')}</button>}
      <span className="muted small" aria-live="polite">{summary.active}/{summary.total} {t('đang hoạt động')}{canManage ? ` · ${summary.managers} ${t('quản lý')}` : ''}</span>
    </div>
    {!canManage && <div className="notice">{t('Bạn đang xem nhân viên thuộc chi nhánh được phân công. Việc tạo, khóa tài khoản và phân quyền do chủ cửa hàng thực hiện.')}</div>}
    <section className="panel">
      {loading ? <LoadingState label={t('Đang tải nhân viên…')} />
        : loadError ? <ErrorState error={loadError} onRetry={() => reload()} />
          : !employees.length ? <EmptyState title={t('Chưa có nhân viên')} description={query ? t('Thử từ khóa tìm kiếm khác.') : canManage ? t('Tạo tài khoản quản lý hoặc nhân viên và phân công chi nhánh.') : t('Chưa có nhân viên nào được phân công vào chi nhánh này.')}
            action={canManage && !query && <button className="btn primary" onClick={() => setEditing({})}>{t('+ Thêm nhân viên')}</button>} />
            : <div className="table-wrap"><table><thead><tr><th>{t('Nhân viên')}</th><th>{t('Tài khoản')}</th><th>{t('Vai trò')}</th><th>{t('Chi nhánh')}</th>{branchId && <th>{t('Đơn đã thu (30 ngày)')}</th>}<th>{t('Trạng thái')}</th>{canManage && <th>{t('Thao tác')}</th>}</tr></thead><tbody>
              {employees.map((employee) => {
                const stat = performance.get(employee.id);
                return <tr key={employee.id}>
                  <td><strong>{employee.full_name}</strong><small className="block muted">{employee.phone || '—'}</small></td>
                  <td>{employee.username}<small className="block muted">{employee.email || '—'}</small></td>
                  <td>{employee.role === 'manager' ? t('Quản lý') : t('Nhân viên')}</td>
                  <td>{employee.branches?.map((branch) => branch.name).join(', ') || '—'}</td>
                  {branchId && <td>{stat ? <><b>{stat.count}</b><small className="block muted">{formatCurrency(stat.revenue)}</small></> : <span className="muted">0</span>}</td>}
                  <td><StatusBadge status={employee.status} /></td>
                  {canManage && <td><div className="actions wrap">
                    <button className="link" onClick={() => setEditing(employee)}>{t('Sửa')}</button>
                    <button className={`link${employee.status === 'ACTIVE' ? ' danger' : ''}`} disabled={busyId === employee.id} onClick={() => toggleStatus(employee)}>{employee.status === 'ACTIVE' ? t('Khóa') : t('Mở khóa')}</button>
                    <button className="link" onClick={() => setPasswordTarget(employee)}>{t('Đặt lại mật khẩu')}</button>
                  </div></td>}
                </tr>;
              })}
            </tbody></table></div>}
    </section>
    {editing && <EmployeeForm employee={editing.id ? editing : null} branches={branches} t={t} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />}
    {passwordTarget && <PasswordForm employee={passwordTarget} t={t} onClose={() => setPasswordTarget(null)} />}
  </>;
}
