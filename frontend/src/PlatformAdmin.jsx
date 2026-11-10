import React, { useState } from 'react';
import { apiRequest } from './auth-client';

const plans = [
  ['basic', 'Cơ bản'],
  ['pro', 'Nâng cao'],
  ['enterprise', 'Doanh nghiệp'],
];

function formatDate(value) {
  return new Date(value).toLocaleDateString('vi-VN');
}

export default function PlatformAdmin() {
  const [adminToken, setAdminToken] = useState('');
  const [accounts, setAccounts] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [created, setCreated] = useState(null);

  async function loadAccounts(token) {
    const result = await apiRequest('/admin/accounts', { adminToken: token });
    setAccounts(result);
  }

  async function connect(event) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      await loadAccounts(adminToken);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function createAccount(event) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    setCreated(null);
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
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
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="platform-admin">
      <header className="platform-admin-header">
        <a className="logo" href="#/">DKat</a>
        <a className="btn outline" href="#/login">Đăng nhập cửa hàng</a>
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
          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? 'Đang kết nối…' : 'Xác thực quản trị'}
          </button>
        </form>

        {message && <p className="platform-admin-message" role="status">{message}</p>}
        {created && (
          <section className="notice platform-admin-created">
            <strong>{created.shop_name}</strong>
            <span>
              Tài khoản chủ cửa hàng: <b>{created.owner_username}</b> · Gói{' '}
              {created.plan} đến ngày {formatDate(created.subscription_expires_at)}
            </span>
            <small>Mật khẩu không được lưu hoặc hiển thị lại sau khi tạo.</small>
          </section>
        )}

        {accounts !== null && (
          <>
            <form className="panel platform-admin-form" onSubmit={createAccount}>
              <h2>Thông tin đăng ký mới</h2>
              <label className="field">
                Tên doanh nghiệp / cửa hàng
                <input name="shop_name" minLength="2" maxLength="160" required />
              </label>
              <div className="platform-admin-fields">
                <label className="field">
                  Gói đăng ký
                  <select name="plan" defaultValue="basic">
                    {plans.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Thời hạn (tháng)
                  <input name="subscription_months" type="number" min="1" max="36" defaultValue="12" required />
                </label>
              </div>
              <div className="platform-admin-fields">
                <label className="field">
                  Tên đăng nhập chủ cửa hàng
                  <input name="owner_username" minLength="3" maxLength="32" pattern="[A-Za-z0-9._-]+" autoComplete="off" required />
                </label>
                <label className="field">
                  Họ tên chủ doanh nghiệp
                  <input name="owner_full_name" minLength="1" maxLength="120" required />
                </label>
              </div>
              <label className="field">
                Mật khẩu khởi tạo (tối thiểu 12 ký tự)
                <input name="owner_password" type="password" minLength="12" maxLength="128" autoComplete="new-password" required />
              </label>
              <p className="muted small">
                Hãy tạo mật khẩu riêng và gửi cho chủ doanh nghiệp qua kênh an toàn.
                Chủ cửa hàng đăng nhập bằng tên đăng nhập không kèm hậu tố.
              </p>
              <button className="btn primary" type="submit" disabled={busy}>
                {busy ? 'Đang cấp tài khoản…' : 'Cấp tài khoản và kích hoạt gói'}
              </button>
            </form>

            <section className="panel platform-admin-list">
              <div className="section-title">
                <h2>Doanh nghiệp đã cấp tài khoản</h2>
                <span className="badge">{accounts.length} cửa hàng</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Cửa hàng</th><th>Tài khoản chủ</th><th>Gói</th><th>Hết hạn</th><th>Trạng thái</th></tr>
                  </thead>
                  <tbody>
                    {accounts.length ? accounts.map((account) => (
                      <tr key={account.shop_id}>
                        <td>{account.shop_name}</td>
                        <td>{account.owner_username}</td>
                        <td>{account.plan}</td>
                        <td>{formatDate(account.subscription_expires_at)}</td>
                        <td>{account.status === 'active' ? 'Đang hoạt động' : 'Đã khóa'}</td>
                      </tr>
                    )) : (
                      <tr><td colSpan="5">Chưa có doanh nghiệp nào.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </section>
    </main>
  );
}
