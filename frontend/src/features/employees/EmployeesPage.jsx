import React, { useEffect, useState } from 'react';
import { useLanguage } from '../../i18n/index.js';
import { listBranches } from '../branches/api.js';
import { assignEmployeeBranches, createEmployee, listEmployees, resetEmployeePassword, setEmployeeStatus, updateEmployee } from './api.js';
import { Dialog } from '../../components/overlay/index.js';

const blankEmployee = { username: '', full_name: '', email: '', phone: '', role: 'staff', password: '', branch_ids: [] };

function EmployeeDialog({ initial, branches, busy, onCancel, onSubmit, onBranchToggle, t }) {
  const create = !initial?.id;
  return <Dialog open title={create ? t('Thêm nhân viên') : t('Cập nhật nhân viên')} busy={busy} onClose={onCancel} className="employee-dialog">
    <form className="dk-form" onSubmit={onSubmit}>
      <div className="section-title"><h2 id="employee-form-title">{create ? t('Thêm nhân viên') : t('Cập nhật nhân viên')}</h2><button className="link" type="button" onClick={onCancel} aria-label={t('Đóng')}>×</button></div>
      {create && <label className="field">{t('Tên đăng nhập')}<input name="username" required minLength={3} maxLength={32} pattern="[A-Za-z0-9._-]+" value={initial.username} onChange={(event) => onBranchToggle('username', event.target.value)} autoComplete="off" /></label>}
      <label className="field">{t('Họ tên')}<input name="full_name" required maxLength={150} value={initial.full_name} onChange={(event) => onBranchToggle('full_name', event.target.value)} autoFocus /></label>
      <label className="field">{t('Email')}<input name="email" type="email" maxLength={255} value={initial.email} onChange={(event) => onBranchToggle('email', event.target.value)} /></label>
      <label className="field">{t('Số điện thoại')}<input name="phone" maxLength={20} value={initial.phone} onChange={(event) => onBranchToggle('phone', event.target.value)} /></label>
      {create && <label className="field">{t('Vai trò')}<select name="role" value={initial.role} onChange={(event) => onBranchToggle('role', event.target.value)}><option value="staff">{t('Nhân viên')}</option><option value="manager">{t('Quản lý')}</option></select></label>}
      {create && <label className="field">{t('Mật khẩu khởi tạo')}<input name="password" type="password" minLength={12} maxLength={128} required autoComplete="new-password" value={initial.password} onChange={(event) => onBranchToggle('password', event.target.value)} /><small className="muted">{t('Ít nhất 12 ký tự; mật khẩu được băm ở backend.')}</small></label>}
      <fieldset className="employee-branches"><legend>{t('Chi nhánh được phân công')}</legend>{branches.length ? branches.map((branch) => { const checked=initial.branch_ids.includes(branch.id); const inactive=branch.status!=='ACTIVE'; return <label key={branch.id} className="employee-branch-option"><input type="checkbox" checked={checked} disabled={inactive&&!checked} onChange={() => onBranchToggle('branch_ids', branch.id)} /><span>{branch.name}</span><small>{branch.branchCode || branch.branch_code}</small></label>; }) : <p className="muted">{t('Chưa có chi nhánh đang hoạt động.')}</p>}</fieldset>
      <div className="actions"><button className="btn primary" disabled={busy || initial.branch_ids.length === 0}>{busy ? t('Đang lưu…') : t('Lưu thay đổi')}</button><button className="btn outline" type="button" onClick={onCancel}>{t('Hủy')}</button></div>
    </form>
  </Dialog>;
}

function PasswordDialog({ busy, onCancel, onSubmit, t }) {
  return <Dialog open title={t('Đặt lại mật khẩu')} size="sm" busy={busy} onClose={onCancel} className="employee-dialog">
    <form className="dk-form" onSubmit={onSubmit}>
      <div className="section-title"><h2 id="employee-password-title">{t('Đặt lại mật khẩu')}</h2><button className="link" type="button" onClick={onCancel} aria-label={t('Đóng')}>×</button></div>
      <label className="field">{t('Mật khẩu mới')}<input name="new_password" type="password" minLength={12} maxLength={128} required autoComplete="new-password" autoFocus /></label>
      <p className="muted small">{t('Các phiên đăng nhập hiện tại của nhân viên sẽ bị thu hồi.')}</p>
      <div className="actions"><button className="btn primary" disabled={busy}>{busy ? t('Đang lưu…') : t('Đặt lại')}</button><button className="btn outline" type="button" onClick={onCancel}>{t('Hủy')}</button></div>
    </form>
  </Dialog>;
}

export default function EmployeesPage() {
  const { t } = useLanguage();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [employees, setEmployees] = useState([]);
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editing, setEditing] = useState(null);
  const [passwordTarget, setPasswordTarget] = useState(null);

  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);

  async function reload(term = search) {
    setLoading(true);
    setError('');
    try {
      const [usersResult, branchesResult] = await Promise.all([
        listEmployees({ query: term, page: 1, pageSize: 100 }),
        listBranches(),
      ]);
      setEmployees(Array.isArray(usersResult?.items) ? usersResult.items : []);
      setBranches(Array.isArray(branchesResult) ? branchesResult : []);
    } catch (cause) {
      setEmployees([]);
      setError(cause.message || t('Không tải được danh sách nhân viên.'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { reload(); }, [search]);

  function updateFormField(field, value) {
    setEditing((current) => {
      if (!current) return current;
      if (field === 'branch_ids') {
        const selected = current.branch_ids.includes(value)
          ? current.branch_ids.filter((id) => id !== value)
          : [...current.branch_ids, value];
        return { ...current, branch_ids: selected };
      }
      return { ...current, [field]: value };
    });
  }

  async function saveEmployee(event) {
    event.preventDefault();
    if (!editing?.branch_ids.length) {
      setError(t('Hãy phân công ít nhất một chi nhánh.'));
      return;
    }
    setBusy(true);
    setError('');
    try {
      if (editing.id) {
        await updateEmployee(editing.id, {
          full_name: editing.full_name.trim(), email: editing.email.trim() || null, phone: editing.phone.trim() || null,
        });
        await assignEmployeeBranches(editing.id, editing.branch_ids);
      } else {
        await createEmployee({
          username: editing.username.trim(), full_name: editing.full_name.trim(),
          email: editing.email.trim() || null, phone: editing.phone.trim() || null,
          password: editing.password, role: editing.role, branch_ids: editing.branch_ids,
        });
      }
      setEditing(null);
      setNotice(t('Đã lưu thông tin nhân viên.'));
      await reload();
    } catch (cause) {
      setError(cause.message || t('Không lưu được nhân viên.'));
    } finally {
      setBusy(false);
    }
  }

  async function toggleStatus(employee) {
    const next = employee.status === 'ACTIVE' ? 'LOCKED' : 'ACTIVE';
    setError('');
    try {
      await setEmployeeStatus(employee.id, next);
      setNotice(next === 'LOCKED' ? t('Đã khóa tài khoản và thu hồi phiên đăng nhập.') : t('Đã mở khóa tài khoản.'));
      await reload();
    } catch (cause) {
      setError(cause.message || t('Không cập nhật được trạng thái.'));
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    const newPassword = new FormData(event.currentTarget).get('new_password');
    setBusy(true);
    setError('');
    try {
      await resetEmployeePassword(passwordTarget.id, newPassword);
      setPasswordTarget(null);
      setNotice(t('Đã đặt lại mật khẩu và thu hồi phiên đăng nhập.'));
    } catch (cause) {
      setError(cause.message || t('Không đặt lại được mật khẩu.'));
    } finally {
      setBusy(false);
    }
  }

  return <>
    <div className="toolbar employee-toolbar">
      <input aria-label={t('Tìm nhân viên')} placeholder={t('Tìm theo tên, username, email hoặc điện thoại')} value={query} onChange={(event) => setQuery(event.target.value)} />
      <button className="btn primary" onClick={() => { setNotice(''); setEditing({ ...blankEmployee, branch_ids: [] }); }}>{t('+ Thêm nhân viên')}</button>
      <span className="muted small" aria-live="polite">{t('Nhân viên')}: {employees.length}</span>
    </div>
    {error && <div className="notice error-state" role="alert">{error}</div>}
    {notice && <div className="notice success-state" role="status">{notice}</div>}
    <section className="panel">
      {loading ? <p className="muted" role="status">{t('Đang tải nhân viên…')}</p> : employees.length === 0 ? <div className="empty"><h3>{t('Chưa có nhân viên')}</h3><p>{query ? t('Thử từ khóa tìm kiếm khác.') : t('Tài khoản nhân viên được tạo sẽ hiển thị tại đây.')}</p></div> :
        <div className="table-wrap"><table><thead><tr><th>{t('Nhân viên')}</th><th>{t('Tài khoản')}</th><th>{t('Vai trò')}</th><th>{t('Chi nhánh')}</th><th>{t('Trạng thái')}</th><th>{t('Thao tác')}</th></tr></thead><tbody>
          {employees.map((employee) => <tr key={employee.id}>
            <td><strong>{employee.full_name}</strong><small className="block muted">{employee.phone || '—'}</small></td>
            <td>{employee.username}<small className="block muted">{employee.email || '—'}</small></td>
            <td>{employee.role === 'manager' ? t('Quản lý') : t('Nhân viên')}</td>
            <td>{employee.branches?.map((branch) => branch.name).join(', ') || '—'}</td>
            <td><span className={`badge ${employee.status === 'ACTIVE' ? 'green' : 'amber'}`}>{employee.status === 'ACTIVE' ? t('Đang hoạt động') : t('Đã khóa')}</span></td>
            <td><div className="actions wrap"><button className="link" onClick={() => { setNotice(''); setEditing({ id: employee.id, full_name: employee.full_name, email: employee.email || '', phone: employee.phone || '', role: employee.role, branch_ids: employee.branches?.map((branch) => branch.id) || [] }); }}>{t('Sửa')}</button><button className="link" onClick={() => toggleStatus(employee)}>{employee.status === 'ACTIVE' ? t('Khóa') : t('Mở khóa')}</button><button className="link" onClick={() => setPasswordTarget(employee)}>{t('Đặt lại mật khẩu')}</button></div></td>
          </tr>)}
        </tbody></table></div>}
    </section>
    {editing && <EmployeeDialog initial={editing} branches={branches} busy={busy} onCancel={() => setEditing(null)} onSubmit={saveEmployee} onBranchToggle={updateFormField} t={t} />}
    {passwordTarget && <PasswordDialog busy={busy} onCancel={() => setPasswordTarget(null)} onSubmit={savePassword} t={t} />}
  </>;
}
