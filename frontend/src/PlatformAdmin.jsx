import React, { useState } from 'react';
import { apiRequest } from './auth-client';
import { getLocale, LanguageSwitcher } from './i18n';
import { Button, Select } from './components/ui';

function platformError(error) {
  const detail = error?.message || '';
  if (!detail || /failed to fetch|networkerror|internal server error|request failed/i.test(detail)) return '\u0110\u00e3 x\u1ea3y ra s\u1ef1 c\u1ed1 khi k\u1ebft n\u1ed1i ho\u1eb7c x\u1eed l\u00fd y\u00eau c\u1ea7u. Vui l\u00f2ng th\u1eed l\u1ea1i.';
  if (/invalid admin token|unauthorized/i.test(detail)) return 'M\u00e3 qu\u1ea3n tr\u1ecb ch\u01b0a \u0111\u00fang ho\u1eb7c \u0111\u00e3 h\u1ebft h\u1ea1n.';
  if (!/[\u00c0-\u024f]/i.test(detail)) return '\u0110\u00e3 x\u1ea3y ra s\u1ef1 c\u1ed1 khi x\u1eed l\u00fd y\u00eau c\u1ea7u. Vui l\u00f2ng th\u1eed l\u1ea1i.';
  return detail;
}

const BRAND_URL = `${import.meta.env.BASE_URL}brand/`;

const plans = [
  ['basic', 'Cơ bản', false],
  ['pro', 'Nâng cao', true],
  ['enterprise', 'Doanh nghiệp', true],
];

function formatDate(value) {
  return value ? new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(value)) : '—';
}

function planName(value) {
  return plans.find(([key]) => key === value)?.[1] || value || '—';
}

export default function PlatformAdmin() {
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
    try {
      await loadAccounts(adminToken);
    } catch (error) {
      setMessage(platformError(error));
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
      setMessage(platformError(error));
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
      setMessage(platformError(error));
      setMessageKind('error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="platform-admin">
      <header className="platform-admin-header">
        <div className="platform-admin-brand-group">
          <a className="platform-admin-brand" href="#/" aria-label="DKat — Digital Key To All">
            <img className="brand-logo brand-logo-full brand-logo-light" src={`${BRAND_URL}dkat-logo-light.svg`} alt="DKat" />
            <img className="brand-logo brand-logo-full brand-logo-dark" src={`${BRAND_URL}dkat-logo-dark.svg`} alt="" />
          </a>
          <span className="platform-admin-brand-divider" />
          <span className="platform-admin-brand-label">QUẢN TRỊ HỆ THỐNG</span>
        </div>
        <div className="platform-admin-header-actions">
          <LanguageSwitcher />
          <span className="platform-admin-access"><i /> CỔNG QUẢN TRỊ</span>
          <Button as="a" variant="outline" href="#/login">Đăng nhập cửa hàng <span aria-hidden="true">↗</span></Button>
        </div>
      </header>
      <section className="platform-admin-content">
        <span className="eyebrow">DKAT / QUẢN TRỊ HỆ THỐNG</span>
        <h1>Cấp tài khoản doanh nghiệp</h1>
        <p className="muted">
          Tạo không gian cửa hàng, kích hoạt gói đăng ký và cấp thông tin đăng nhập
          ban đầu cho chủ doanh nghiệp.
        </p>

        <form className="panel platform-admin-token" onSubmit={connect}>
          <label className="field">
            Mã quản trị hệ thống
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
            {busy ? 'Đang kết nối…' : 'Xác thực quản trị'}
          </Button>
        </form>

        {message && <div className={`platform-admin-message ${messageKind}`} role={messageKind === 'error' ? 'alert' : 'status'}><span aria-hidden="true">{messageKind === 'error' ? '!' : '\u2713'}</span>{message}</div>}
        {created && (
          <section className="notice platform-admin-created">
            <strong>{created.shop_name}</strong>
            <span>
              Tài khoản chủ cửa hàng: <b>{created.owner_username}</b>{' | Email \u0111\u0103ng nh\u1eadp: '}<b>{created.owner_email}</b> · Gói{' '}
              {planName(created.plan)} đến ngày {formatDate(created.subscription_expires_at)}
            </span>
            <small>Mật khẩu không được lưu hoặc hiển thị lại sau khi tạo.</small>
          </section>
        )}

        {accounts !== null && (
          <>
            <form className="panel platform-admin-form" onSubmit={createAccount}>
              <div className="platform-admin-form-heading">
                <div>
                  <span className="eyebrow">TẠO KHÔNG GIAN MỚI</span>
                  <h2>Thông tin đăng ký</h2>
                </div>
                <span className="badge green">Chỉ mở gói Cơ bản</span>
              </div>
              <label className="field">
                Tên doanh nghiệp / cửa hàng
                <input name="shop_name" minLength="2" maxLength="150" required />
              </label>
              <div className="platform-admin-fields">
                <label className="field">
                  Gói đăng ký
                  <Select name="plan" defaultValue="basic">
                    {plans.map(([value, label, locked]) => (
                      <option key={value} value={value} disabled={locked}>
                        {label}{locked ? ' — Tạm khóa' : ''}
                      </option>
                    ))}
                  </Select>
                </label>
                <label className="field">
                  Thời hạn (tháng)
                  <input name="subscription_months" type="number" min="1" max="36" defaultValue="12" required />
                </label>
              </div>
              <p className="platform-admin-plan-note">
                Gói Nâng cao và Doanh nghiệp đang tạm khóa. Tài khoản mới hiện chỉ có thể đăng ký gói Cơ bản.
              </p>
              <div className="platform-admin-fields">
                <label className="field">
                  Tên đăng nhập chủ cửa hàng
                  <input name="owner_username" minLength="3" maxLength="32" pattern="[A-Za-z0-9._-]+" title="3–32 characters: letters, numbers, periods, underscores, or hyphens." autoComplete="off" required />
                </label>
                <label className="field">
                  Họ tên chủ doanh nghiệp
                  <input name="owner_full_name" minLength="1" maxLength="120" required />
                </label>
              </div>
              <label className="field">{'Email c\u1ee7a ch\u1ee7 c\u1eeda h\u00e0ng (d\u00f9ng \u0111\u1ec3 \u0111\u0103ng nh\u1eadp)'}
                <input name="owner_email" type="email" pattern="[^@\s]+@[^@\s]+\.[^@\s]+" maxLength="255" autoComplete="email" required />
              </label>
              <label className="field">
                Mật khẩu khởi tạo (tối thiểu 12 ký tự)
                <input name="owner_password" type="password" minLength="12" maxLength="128" autoComplete="new-password" required />
              </label>
              <p className="muted small">
                Hãy tạo mật khẩu riêng và gửi cho chủ doanh nghiệp qua kênh an toàn.
                {'Ch\u1ee7 c\u1eeda h\u00e0ng c\u00f3 th\u1ec3 \u0111\u0103ng nh\u1eadp b\u1eb1ng email ho\u1eb7c t\u00ean \u0111\u0103ng nh\u1eadp kh\u00f4ng k\u00e8m h\u1eadu t\u1ed1.'}
              </p>
              <Button variant="primary" type="submit" loading={busy}>
                {busy ? 'Đang cấp tài khoản…' : 'Cấp tài khoản và kích hoạt gói'}
              </Button>
            </form>

            <section className="panel platform-admin-list">
              <div className="section-title">
                <h2>Doanh nghiệp đã cấp tài khoản</h2>
                <span className="badge">{accounts.length} cửa hàng</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>C&#7917;a h&#224;ng</th><th>T&#224;i kho&#7843;n ch&#7911;</th><th>Email</th><th>G&#243;i</th><th>H&#7871;t h&#7841;n</th><th>Tr&#7841;ng th&#225;i</th><th>Thao t&#225;c</th></tr>
                  </thead>
                  <tbody>
                    {accounts.length ? accounts.map((account) => (
                      <tr key={account.shop_id}>
                        <td>{account.shop_name}</td>
                        <td>{account.owner_username}</td>
                        <td>{account.owner_email || '-'}</td>
                        <td>{planName(account.plan)}</td>
                        <td>{formatDate(account.subscription_expires_at)}</td>
                        <td><span className={`badge ${account.status === 'active' ? 'green' : 'amber'}`}>
                          {account.status === 'active' ? 'Đang hoạt động' : 'Đã khóa'}
                        </span></td>
                        <td><Button variant="ghost" size="small" className="link" type="button" onClick={() => setEditing(account)}>S&#7917;a</Button></td>
                      </tr>
                    )) : (
                      <tr><td colSpan="7">Chưa có doanh nghiệp nào.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
            {editing && (
              <div className="overlay" onClick={() => !busy && setEditing(null)}>
                <form className="dialog platform-admin-edit" role="dialog" aria-modal="true" aria-labelledby="edit-account-title" onClick={(event) => event.stopPropagation()} onSubmit={updateAccount}>
                  <button className="close" type="button" aria-label="Close" onClick={() => setEditing(null)}>&#215;</button>
                  <span className="eyebrow">DKAT / CH&#7880;NH S&#7916;A T&#192;I KHO&#7842;N</span>
                  <h2 id="edit-account-title">C&#7853;p nh&#7853;t {editing.shop_name}</h2>
                  <label className="field">T&#234;n c&#7917;a h&#224;ng<input name="shop_name" minLength="2" maxLength="150" defaultValue={editing.shop_name} required /></label>
                  <div className="platform-admin-fields">
                    <label className="field">T&#234;n &#273;&#259;ng nh&#7853;p ch&#7911; c&#7917;a h&#224;ng<input name="owner_username" minLength="3" maxLength="32" pattern="[A-Za-z0-9._-]+" defaultValue={editing.owner_username || ''} autoComplete="off" required /></label>
                    <label className="field">H&#7885; t&#234;n ch&#7911; c&#7917;a h&#224;ng<input name="owner_full_name" minLength="1" maxLength="150" defaultValue={editing.owner_full_name || ''} required /></label>
                  </div>
                  <label className="field">Email ch&#7911; c&#7917;a h&#224;ng<input name="owner_email" type="email" pattern="[^@\s]+@[^@\s]+\.[^@\s]+" maxLength="255" defaultValue={editing.owner_email || ''} autoComplete="email" required /></label>
                  <div className="platform-admin-fields">
                    <label className="field">G&#243;i &#273;&#259;ng k&#253;<Select name="plan" defaultValue={editing.plan || 'basic'}>{plans.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></label>
                    <label className="field">Ng&#224;y h&#7871;t h&#7841;n<input name="subscription_expires_at" type="date" defaultValue={editing.subscription_expires_at?.slice(0, 10) || ''} required /></label>
                  </div>
                  <label className="field">Tr&#7841;ng th&#225;i g&#243;i<Select name="subscription_status" defaultValue={editing.subscription_status || 'ACTIVE'}><option value="ACTIVE">&#272;ang ho&#7841;t &#273;&#7897;ng</option><option value="CANCELLED">&#272;&#227; h&#7911;y</option></Select></label>
                  <label className="field">M&#7853;t kh&#7849;u m&#7899;i (&#273;&#7875; tr&#7889;ng n&#7871;u gi&#7919; nguy&#234;n)<input name="owner_password" type="password" minLength="12" maxLength="128" autoComplete="new-password" /></label>
                  <p className="muted small">&#272;&#7893;i t&#234;n &#273;&#259;ng nh&#7853;p, email ho&#7863;c m&#7853;t kh&#7849;u s&#7869; k&#7871;t th&#250;c c&#225;c phi&#234;n hi&#7879;n t&#7841;i c&#7911;a ch&#7911; c&#7917;a h&#224;ng.</p>
                  <Button variant="primary" type="submit" loading={busy}>{busy ? '\u0110ang l\u01b0u\u2026' : 'L\u01b0u thay \u0111\u1ed5i'}</Button>
                </form>
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}
