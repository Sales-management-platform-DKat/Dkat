import React, { useState } from 'react';
import { apiRequest } from './auth-client';
import { useLanguage, errorMessage, LanguageSwitcher } from './i18n';
import { Button, Select } from './components/ui';

const BRAND_URL = `${import.meta.env.BASE_URL}brand/`;

const plans = [
  ['basic', 'Cơ bản', false],
  ['pro', 'Nâng cao', true],
  ['enterprise', 'Doanh nghiệp', true],
];

function planName(value) {
  return plans.find(([key]) => key === value)?.[1] || value || '—';
}

// The platform admin signs in with DKAT_ADMIN_TOKEN (X-Admin-Token), not a username/password.
function adminConnectError(error) {
  if (error?.status === 401) return 'admin.token.invalid';
  if (error?.status === 503) return 'admin.token.notConfigured';
  if (error instanceof TypeError) return 'admin.token.unreachable';
  return errorMessage(error, 'Đã xảy ra sự cố khi kết nối hoặc xử lý yêu cầu. Vui lòng thử lại.');
}

export default function PlatformAdmin() {
  const { t, formatDate, formatNumber } = useLanguage();
  const dateLabel = (value) => value ? formatDate(new Date(value)) : '—';
  const [adminToken, setAdminToken] = useState('');
  const [accounts, setAccounts] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [messageKind, setMessageKind] = useState('success');
  const [created, setCreated] = useState(null);
  const [editing, setEditing] = useState(null);

  async function loadAccounts(token) {
    const result = await apiRequest('/admin/accounts', { adminToken: token });
    setAccounts(result);
  }

  async function connect(event) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    setMessageKind('success');
    // Pasted tokens often carry spaces or a trailing newline.
    const token = adminToken.trim();
    setAdminToken(token);
    try {
      await loadAccounts(token);
    } catch (error) {
      setMessage(adminConnectError(error));
      setMessageKind('error');
    } finally {
      setBusy(false);
    }
  }

  async function createAccount(event) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    setMessageKind('success');
    setCreated(null);
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    if (!/^[a-zA-Z0-9._-]{3,32}$/.test(values.owner_username)) {
      setMessage('T\u00ean \u0111\u0103ng nh\u1eadp d\u00f9ng 3\u201332 k\u00fd t\u1ef1: ch\u1eef, s\u1ed1, d\u1ea5u ch\u1ea5m, g\u1ea1ch d\u01b0\u1edbi ho\u1eb7c g\u1ea1ch ngang.');
      setMessageKind('error');
      setBusy(false);
      form.elements.owner_username.focus();
      return;
    }
    values.subscription_months = Number(values.subscription_months);
    try {
      const result = await apiRequest('/admin/accounts', {
        adminToken,
        method: 'POST',
        body: JSON.stringify(values),
      });
      setCreated(result);
      setMessage('Đã cấp tài khoản chủ cửa hàng và kích hoạt gói đăng ký.');
      form.reset();
      await loadAccounts(adminToken);
    } catch (error) {
      setMessage(errorMessage(error, 'Đã xảy ra sự cố khi kết nối hoặc xử lý yêu cầu. Vui lòng thử lại.'));
      setMessageKind('error');
    } finally {
      setBusy(false);
    }
  }

  async function updateAccount(event) {
    event.preventDefault();
    if (!editing || busy) return;
    setBusy(true);
    setMessage('');
    setMessageKind('success');
    const values = Object.fromEntries(new FormData(event.currentTarget));
    if (!values.owner_password) delete values.owner_password;
    try {
      await apiRequest(`/admin/accounts/${editing.shop_id}`, {
        adminToken,
        method: 'PATCH',
        body: JSON.stringify(values),
      });
      setEditing(null);
      setMessage('\u0110\u00e3 c\u1eadp nh\u1eadt t\u00e0i kho\u1ea3n c\u1eeda h\u00e0ng.');
      await loadAccounts(adminToken);
    } catch (error) {
      setMessage(errorMessage(error, 'Đã xảy ra sự cố khi kết nối hoặc xử lý yêu cầu. Vui lòng thử lại.'));
      setMessageKind('error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="platform-admin">
      <header className="platform-admin-header">
        <div className="platform-admin-brand-group">
          <a className="platform-admin-brand" href="#/" aria-label={t('DKat — Digital Key To All')}>
            <img className="brand-logo brand-logo-full brand-logo-light" src={`${BRAND_URL}dkat-logo-light.svg`} alt="DKat" />
            <img className="brand-logo brand-logo-full brand-logo-dark" src={`${BRAND_URL}dkat-logo-dark.svg`} alt="" />
          </a>
          <span className="platform-admin-brand-divider" />
          <span className="platform-admin-brand-label">{t('QUẢN TRỊ HỆ THỐNG')}</span>
        </div>
        <div className="platform-admin-header-actions">
          <LanguageSwitcher />
          <span className="platform-admin-access"><i />{' ' + t('CỔNG QUẢN TRỊ')}</span>
          <Button as="a" variant="outline" href="#/login">{t('Đăng nhập cửa hàng') + ' '}<span aria-hidden="true">↗</span></Button>
        </div>
      </header>
      <section className="platform-admin-content">
        <span className="eyebrow">{t('DKAT / QUẢN TRỊ HỆ THỐNG')}</span>
        <h1>{t('Cấp tài khoản doanh nghiệp')}</h1>
        <p className="muted">
          {t('Tạo không gian cửa hàng, kích hoạt gói đăng ký và cấp thông tin đăng nhập ban đầu cho chủ doanh nghiệp.')}
        </p>

        <form className="panel platform-admin-token" onSubmit={connect}>
          <label className="field">
            {t('Mã quản trị hệ thống')}
            <input
              type="password"
              autoComplete="current-password"
              value={adminToken}
              onChange={(event) => {
                setAdminToken(event.target.value);
                setAccounts(null);
              }}
              required
            />
          </label>
          <Button variant="primary" type="submit" loading={busy}>
            {busy ? t('Đang kết nối…') : t('Xác thực quản trị')}
          </Button>
        </form>

        {message && <div className={`platform-admin-message ${messageKind}`} role={messageKind === 'error' ? 'alert' : 'status'}><span aria-hidden="true">{messageKind === 'error' ? '!' : '\u2713'}</span>{t(message)}</div>}
        {created && (
          <section className="notice platform-admin-created">
            <strong>{created.shop_name}</strong>
            <span>
              {t('Tài khoản chủ cửa hàng:') + ' '}<b>{created.owner_username}</b>{' ' + t('| Email đăng nhập:') + ' '}<b>{created.owner_email}</b>{' ' + t('· Gói')}{' '}
              {t(planName(created.plan))}{' ' + t('đến ngày') + ' '}{dateLabel(created.subscription_expires_at)}
            </span>
            <small>{t('Mật khẩu không được lưu hoặc hiển thị lại sau khi tạo.')}</small>
          </section>
        )}

        {accounts !== null && (
          <>
            <form className="panel platform-admin-form" onSubmit={createAccount}>
              <div className="platform-admin-form-heading">
                <div>
                  <span className="eyebrow">{t('TẠO KHÔNG GIAN MỚI')}</span>
                  <h2>{t('Thông tin đăng ký')}</h2>
                </div>
                <span className="badge green">{t('Chỉ mở gói Cơ bản')}</span>
              </div>
              <label className="field">
                {t('Tên doanh nghiệp / cửa hàng')}
                <input name="shop_name" minLength="2" maxLength="150" required />
              </label>
              <div className="platform-admin-fields">
                <label className="field">
                  {t('Gói đăng ký')}
                  <Select name="plan" defaultValue="basic">
                    {plans.map(([value, label, locked]) => (
                      <option key={value} value={value} disabled={locked}>
                        {t(label)}{locked ? ' ' + t('— Tạm khóa') : ''}
                      </option>
                    ))}
                  </Select>
                </label>
                <label className="field">
                  {t('Thời hạn (tháng)')}
                  <input name="subscription_months" type="number" min="1" max="36" defaultValue="12" required />
                </label>
              </div>
              <p className="platform-admin-plan-note">
                {t('Gói Nâng cao và Doanh nghiệp đang tạm khóa. Tài khoản mới hiện chỉ có thể đăng ký gói Cơ bản.')}
              </p>
              <div className="platform-admin-fields">
                <label className="field">
                  {t('Tên đăng nhập chủ cửa hàng')}
                  <input name="owner_username" minLength="3" maxLength="32" pattern="[A-Za-z0-9._\-]+" title={t('3–32 characters: letters, numbers, periods, underscores, or hyphens.')} autoComplete="off" required />
                </label>
                <label className="field">
                  {t('Họ tên chủ doanh nghiệp')}
                  <input name="owner_full_name" minLength="1" maxLength="120" required />
                </label>
              </div>
              <label className="field">{t('Email của chủ cửa hàng (dùng để đăng nhập)')}
                <input name="owner_email" type="email" pattern="[^@\s]+@[^@\s]+\.[^@\s]+" maxLength="255" autoComplete="email" required />
              </label>
              <label className="field">
                {t('Mật khẩu khởi tạo (tối thiểu 12 ký tự)')}
                <input name="owner_password" type="password" minLength="12" maxLength="128" autoComplete="new-password" required />
              </label>
              <p className="muted small">
                {t('Hãy tạo mật khẩu riêng và gửi cho chủ doanh nghiệp qua kênh an toàn.')}
                {t('Chủ cửa hàng có thể đăng nhập bằng email hoặc tên đăng nhập không kèm hậu tố.')}
              </p>
              <Button variant="primary" type="submit" loading={busy}>
                {busy ? t('Đang cấp tài khoản…') : t('Cấp tài khoản và kích hoạt gói')}
              </Button>
            </form>

            <section className="panel platform-admin-list">
              <div className="section-title">
                <h2>{t('Doanh nghiệp đã cấp tài khoản')}</h2>
                <span className="badge">{t('platform.storeCount',{count:formatNumber(accounts.length)})}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>{t('Cửa hàng')}</th><th>{t('Tài khoản chủ')}</th><th>Email</th><th>{t('Gói')}</th><th>{t('Hết hạn')}</th><th>{t('Trạng thái')}</th><th>{t('Thao tác')}</th></tr>
                  </thead>
                  <tbody>
                    {accounts.length ? accounts.map((account) => (
                      <tr key={account.shop_id}>
                        <td>{account.shop_name}</td>
                        <td>{account.owner_username}</td>
                        <td>{account.owner_email || '-'}</td>
                        <td>{t(planName(account.plan))}</td>
                        <td>{dateLabel(account.subscription_expires_at)}</td>
                        <td><span className={`badge ${account.status === 'active' ? 'green' : 'amber'}`}>
                          {account.status === 'active' ? t('Đang hoạt động') : t('Đã khóa')}
                        </span></td>
                        <td><Button variant="ghost" size="small" className="link" type="button" onClick={() => setEditing(account)}>{t('Sửa')}</Button></td>
                      </tr>
                    )) : (
                      <tr><td colSpan="7">{t('Chưa có doanh nghiệp nào.')}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
            {editing && (
              <div className="overlay" onClick={() => !busy && setEditing(null)}>
                <form className="dialog platform-admin-edit" role="dialog" aria-modal="true" aria-labelledby="edit-account-title" onClick={(event) => event.stopPropagation()} onSubmit={updateAccount}>
                  <button className="close" type="button" aria-label={t('Close')} onClick={() => setEditing(null)}>&#215;</button>
                  <span className="eyebrow">{t('DKAT / CHỈNH SỬA TÀI KHOẢN')}</span>
                  <h2 id="edit-account-title">{t('platform.editStore',{name:editing.shop_name})}</h2>
                  <label className="field">{t('Tên cửa hàng')}<input name="shop_name" minLength="2" maxLength="150" defaultValue={editing.shop_name} required /></label>
                  <div className="platform-admin-fields">
                    <label className="field">{t('Tên đăng nhập chủ cửa hàng')}<input name="owner_username" minLength="3" maxLength="32" pattern="[A-Za-z0-9._\-]+" defaultValue={editing.owner_username || ''} autoComplete="off" required /></label>
                    <label className="field">{t('Họ tên chủ cửa hàng')}<input name="owner_full_name" minLength="1" maxLength="150" defaultValue={editing.owner_full_name || ''} required /></label>
                  </div>
                  <label className="field">{t('Email chủ cửa hàng')}<input name="owner_email" type="email" pattern="[^@\s]+@[^@\s]+\.[^@\s]+" maxLength="255" defaultValue={editing.owner_email || ''} autoComplete="email" required /></label>
                  <div className="platform-admin-fields">
                    <label className="field">{t('Gói đăng ký')}<Select name="plan" defaultValue={editing.plan || 'basic'}>{plans.map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}</Select></label>
                    <label className="field">{t('Ngày hết hạn')}<input name="subscription_expires_at" type="date" defaultValue={editing.subscription_expires_at?.slice(0, 10) || ''} required /></label>
                  </div>
                  <label className="field">{t('Trạng thái gói')}<Select name="subscription_status" defaultValue={editing.subscription_status || 'ACTIVE'}><option value="ACTIVE">{t('Đang hoạt động')}</option><option value="CANCELLED">{t('Đã hủy')}</option></Select></label>
                  <label className="field">{t('Mật khẩu mới (để trống nếu giữ nguyên)')}<input name="owner_password" type="password" minLength="12" maxLength="128" autoComplete="new-password" /></label>
                  <p className="muted small">{t('Đổi tên đăng nhập, email hoặc mật khẩu sẽ kết thúc các phiên hiện tại của chủ cửa hàng.')}</p>
                  <Button variant="primary" type="submit" loading={busy}>{busy ? t('Đang lưu…') : t('Lưu thay đổi')}</Button>
                </form>
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}
