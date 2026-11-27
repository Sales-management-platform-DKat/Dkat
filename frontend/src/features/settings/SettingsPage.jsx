import React, { useEffect, useMemo, useState } from 'react';
import { errorMessage, useLanguage } from '../../i18n/index.js';
import { Button, Select } from '../../components/ui.jsx';
import { confirmAction } from '../../components/overlay/index.js';
import { changePassword, getMyStore, getSessionSummary, revokeOtherSessions, updateMyStore, updateProfile } from './api.js';

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PHONE = /^\+?[0-9][0-9 .-]{7,18}$/;
const PLAN_NAMES = { basic: 'Cơ bản', pro: 'Nâng cao', enterprise: 'Doanh nghiệp' };
const ROLE_NAMES = { owner: 'Chủ cửa hàng', manager: 'Quản lý', staff: 'Nhân viên' };
const DAY = 24 * 60 * 60 * 1000;
const LANGUAGE_NAMES = { vi: 'Tiếng Việt', en: 'English' };

const TABS = [
  ['store', 'Cửa hàng', 'settings.tab.store'],
  ['account', 'Tài khoản', 'settings.tab.account'],
  ['security', 'Bảo mật', 'settings.tab.security'],
  ['preferences', 'Giao diện', 'settings.tab.preferences'],
];

function Icon({ name }) {
  const paths = {
    store: <path d="M4 10h16M5 10l1.2-5h11.6L19 10M6 10v9h12v-9M10 19v-5h4v5" />,
    account: <><circle cx="12" cy="8" r="3.5" /><path d="M5 20a7 7 0 0 1 14 0" /></>,
    security: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
    preferences: <><circle cx="12" cy="12" r="8" /><path d="M12 4a8 8 0 0 0 0 16z" /></>,
  };
  return <svg className="settings-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

function Card({ title, description, children, footer, tone }) {
  return <section className={`settings-card ${tone ? `tone-${tone}` : ''}`}>
    <header><h2>{title}</h2>{description && <p>{description}</p>}</header>
    <div className="settings-card-body">{children}</div>
    {footer && <footer>{footer}</footer>}
  </section>;
}

function Field({ label, hint, error, children, required }) {
  return <label className="settings-field">
    <span className="settings-label">{label}{required && <i aria-hidden="true"> *</i>}</span>
    {children}
    {error ? <small className="field-error" role="alert">{error}</small> : hint && <small className="muted">{hint}</small>}
  </label>;
}

function useUnsavedWarning(dirty) {
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (event) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
}

function passwordStrength(value) {
  let score = 0;
  if (value.length >= 12) score += 1;
  if (value.length >= 16) score += 1;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
  if (/\d/.test(value)) score += 1;
  if (/[^A-Za-z0-9]/.test(value)) score += 1;
  return value.length < 12 ? 0 : Math.min(3, Math.ceil(score / 1.7));
}

// ---------------- Store ----------------
function StoreTab({ demo, demoStore, onDemoSave, notify, onRenamed, go }) {
  const { t, formatDate, formatNumber } = useLanguage();
  const [store, setStore] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoadError('');
    if (demo) {
      setStore({ name: demoStore?.name || 'DKat Demo', plan: 'basic', subscriptionStatus: 'ACTIVE', canEdit: true, demo: true });
      setName(demoStore?.name || 'DKat Demo');
      return;
    }
    try { const data = await getMyStore(); setStore(data); setName(data.name); }
    catch (cause) { setLoadError(errorMessage(cause, 'Không tải được thông tin cửa hàng.')); }
  }
  useEffect(() => { load(); }, [demo]);

  const dirty = !!store && name.trim() !== store.name;
  useUnsavedWarning(dirty);
  if (loadError) return <Card title={t('Thông tin cửa hàng')} tone="error"><p role="alert">{t(loadError)}</p><Button variant="outline" onClick={load}>{t('Thử lại')}</Button></Card>;
  if (!store) return <Card title={t('Thông tin cửa hàng')}><p className="muted" role="status">{t('Đang tải…')}</p></Card>;

  async function save(event) {
    event.preventDefault();
    const value = name.trim();
    if (value.length < 2 || value.length > 150) { setError('settings.store.nameLength'); return; }
    if (busy || !dirty) return;
    setBusy(true); setError('');
    try {
      if (demo) { onDemoSave({ ...demoStore, name: value }); setStore({ ...store, name: value }); }
      else { const updated = await updateMyStore(value); setStore(updated); setName(updated.name); onRenamed(updated.name); }
      notify('settings.store.saved');
    } catch (cause) { setError(errorMessage(cause, 'Không lưu được tên cửa hàng.')); }
    finally { setBusy(false); }
  }

  const expires = store.subscriptionExpiresAt ? new Date(store.subscriptionExpiresAt) : null;
  const daysLeft = expires ? Math.ceil((expires - Date.now()) / DAY) : null;
  const expiringTone = store.subscriptionStatus !== 'ACTIVE' || (daysLeft !== null && daysLeft <= 0) ? 'red' : daysLeft !== null && daysLeft <= 30 ? 'amber' : 'green';

  return <>
    <Card title={t('Thông tin cửa hàng')} description={t(store.canEdit ? 'settings.store.description' : 'settings.store.readOnly')}>
      <form className="settings-form" onSubmit={save} noValidate>
        <Field label={t('Tên cửa hàng')} required error={error && t(error)} hint={t('settings.store.nameHint')}>
          <input value={name} maxLength={150} disabled={!store.canEdit || busy} onChange={(event) => { setName(event.target.value); setError(''); }} placeholder={t('Ví dụ: DKat Fashion')} aria-invalid={!!error} />
        </Field>
        {store.canEdit && <div className="settings-actions">
          <Button variant="outline" type="button" disabled={!dirty || busy} onClick={() => { setName(store.name); setError(''); }}>{t('Hoàn tác')}</Button>
          <Button variant="primary" type="submit" disabled={!dirty} loading={busy}>{busy ? t('Đang lưu…') : t('Lưu thay đổi')}</Button>
        </div>}
      </form>
    </Card>

    <Card title={t('Gói dịch vụ')} description={t('settings.plan.description')}>
      <dl className="settings-facts">
        <div><dt>{t('Gói')}</dt><dd>{t(PLAN_NAMES[store.plan] || store.plan || '—')}</dd></div>
        <div><dt>{t('Trạng thái')}</dt><dd><span className={`badge ${expiringTone}`}>{t(store.subscriptionStatus === 'ACTIVE' && (daysLeft === null || daysLeft > 0) ? 'Đang hoạt động' : 'Hết hạn')}</span></dd></div>
        <div><dt>{t('Hết hạn ngày')}</dt><dd>{expires ? formatDate(expires) : '—'}</dd></div>
        <div><dt>{t('Còn lại')}</dt><dd>{daysLeft === null ? '—' : t('settings.plan.daysLeft', { days: formatNumber(Math.max(daysLeft, 0)) })}</dd></div>
      </dl>
      {expiringTone !== 'green' && !store.demo && <p className={`notice ${expiringTone === 'red' ? 'error-state' : 'amber'}`} role="status">{t('settings.plan.renew')}</p>}
    </Card>

    {!store.demo && <Card title={t('Quy mô cửa hàng')}>
      <div className="settings-stats">
        <button type="button" className="settings-stat" onClick={() => go('admin/branches')} disabled={!store.canEdit}>
          <strong>{formatNumber(store.activeBranchCount)}<small>/{formatNumber(store.branchCount)}</small></strong>
          <span>{t('Chi nhánh đang hoạt động')}</span>
        </button>
        <button type="button" className="settings-stat" onClick={() => go('admin/employees')}>
          <strong>{formatNumber(store.staffCount)}</strong><span>{t('Nhân sự đang hoạt động')}</span>
        </button>
        <div className="settings-stat"><strong>{store.createdAt ? formatDate(new Date(store.createdAt)) : '—'}</strong><span>{t('Ngày tạo cửa hàng')}</span></div>
      </div>
    </Card>}
  </>;
}

// ---------------- Account ----------------
function AccountTab({ demo, user, onUpdated, notify }) {
  const { t } = useLanguage();
  const initial = useMemo(() => ({ full_name: user?.full_name || '', email: user?.email || '', phone: user?.phone || '' }), [user]);
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => setForm(initial), [initial]);
  const dirty = Object.keys(initial).some((key) => form[key].trim() !== initial[key]);
  useUnsavedWarning(dirty);

  if (demo) return <Card title={t('Hồ sơ cá nhân')}><p className="notice">{t('settings.demoOnly')}</p></Card>;

  const update = (key) => (event) => { setForm({ ...form, [key]: event.target.value }); setErrors({ ...errors, [key]: '' }); setServerError(''); };
  async function save(event) {
    event.preventDefault();
    const next = {};
    if (!form.full_name.trim()) next.full_name = 'Vui lòng nhập họ tên.';
    if (form.email.trim() && !EMAIL.test(form.email.trim())) next.email = 'Email chưa đúng định dạng.';
    if (form.phone.trim() && !PHONE.test(form.phone.trim())) next.phone = 'settings.account.phoneInvalid';
    setErrors(next);
    if (Object.keys(next).length || busy || !dirty) return;
    setBusy(true);
    try {
      const updated = await updateProfile({ full_name: form.full_name.trim(), email: form.email.trim() || null, phone: form.phone.trim() || null });
      onUpdated(updated);
      notify('settings.account.saved');
    } catch (cause) {
      if (cause?.code === 'EMAIL_TAKEN') setErrors({ email: 'api.error.EMAIL_TAKEN' });
      else setServerError(errorMessage(cause, 'Không lưu được hồ sơ.'));
    } finally { setBusy(false); }
  }

  return <Card title={t('Hồ sơ cá nhân')} description={t('settings.account.description')}>
    <form className="settings-form" onSubmit={save} noValidate>
      <div className="settings-grid">
        <Field label={t('Họ tên')} required error={errors.full_name && t(errors.full_name)}>
          <input value={form.full_name} maxLength={150} autoComplete="name" disabled={busy} onChange={update('full_name')} aria-invalid={!!errors.full_name} />
        </Field>
        <Field label={t('Email')} error={errors.email && t(errors.email)} hint={t('settings.account.emailHint')}>
          <input type="email" value={form.email} maxLength={255} autoComplete="email" disabled={busy} placeholder="ten@cuahang.vn" onChange={update('email')} aria-invalid={!!errors.email} />
        </Field>
        <Field label={t('Số điện thoại')} error={errors.phone && t(errors.phone)}>
          <input type="tel" value={form.phone} maxLength={20} autoComplete="tel" disabled={busy} placeholder="0901 234 567" onChange={update('phone')} aria-invalid={!!errors.phone} />
        </Field>
        <Field label={t('Tên đăng nhập')} hint={t('settings.account.usernameHint')}>
          <input value={user?.username || ''} disabled readOnly />
        </Field>
        <Field label={t('Vai trò')}>
          <input value={t(ROLE_NAMES[user?.role] || user?.role || '')} disabled readOnly />
        </Field>
      </div>
      {serverError && <p className="notice error-state" role="alert">{t(serverError)}</p>}
      <div className="settings-actions">
        <Button variant="outline" type="button" disabled={!dirty || busy} onClick={() => { setForm(initial); setErrors({}); setServerError(''); }}>{t('Hoàn tác')}</Button>
        <Button variant="primary" type="submit" disabled={!dirty} loading={busy}>{busy ? t('Đang lưu…') : t('Lưu thay đổi')}</Button>
      </div>
    </form>
  </Card>;
}

// ---------------- Security ----------------
function SecurityTab({ demo, notify }) {
  const { t, formatNumber } = useLanguage();
  const empty = { current: '', next: '', confirm: '' };
  const [form, setForm] = useState(empty);
  const [show, setShow] = useState(false);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [sessions, setSessions] = useState(null);
  const [sessionError, setSessionError] = useState('');

  async function loadSessions() {
    setSessionError('');
    try { setSessions(await getSessionSummary()); }
    catch (cause) { setSessionError(errorMessage(cause, 'Không tải được danh sách phiên đăng nhập.')); }
  }
  useEffect(() => { if (!demo) loadSessions(); }, [demo]);
  useUnsavedWarning(Object.values(form).some(Boolean));

  if (demo) return <Card title={t('Đổi mật khẩu')}><p className="notice">{t('settings.demoOnly')}</p></Card>;

  const strength = passwordStrength(form.next);
  const update = (key) => (event) => { setForm({ ...form, [key]: event.target.value }); setErrors({}); };
  async function submit(event) {
    event.preventDefault();
    const next = {};
    if (!form.current) next.current = 'settings.security.currentRequired';
    if (form.next.length < 12) next.next = 'settings.security.tooShort';
    else if (form.next === form.current) next.next = 'api.error.PASSWORD_UNCHANGED';
    if (form.confirm !== form.next) next.confirm = 'settings.security.mismatch';
    setErrors(next);
    if (Object.keys(next).length || busy) return;
    setBusy(true);
    try {
      const result = await changePassword(form.current, form.next);
      setForm(empty);
      notify({ key: 'settings.security.changed', values: { count: formatNumber(result.revoked_sessions) } });
      loadSessions();
    } catch (cause) {
      if (cause?.code === 'CURRENT_PASSWORD_INVALID') setErrors({ current: 'api.error.CURRENT_PASSWORD_INVALID' });
      else if (cause?.code === 'PASSWORD_UNCHANGED') setErrors({ next: 'api.error.PASSWORD_UNCHANGED' });
      else setErrors({ form: errorMessage(cause, 'Không đổi được mật khẩu.') });
    } finally { setBusy(false); }
  }

  async function signOutOthers() {
    const answer = await confirmAction({
      tone: 'warning', title: 'settings.sessions.confirmTitle', description: 'settings.sessions.confirmDescription',
      confirmLabel: 'Đăng xuất thiết bị khác',
      onConfirm: async () => {
        const result = await revokeOtherSessions();
        notify({ key: 'settings.sessions.revoked', values: { count: formatNumber(result.revoked_sessions) } });
      },
    });
    if (answer) loadSessions();
  }

  const type = show ? 'text' : 'password';
  return <>
    <Card title={t('Đổi mật khẩu')} description={t('settings.security.description')}>
      <form className="settings-form" onSubmit={submit} noValidate>
        <div className="settings-grid">
          <Field label={t('Mật khẩu hiện tại')} required error={errors.current && t(errors.current)}>
            <input type={type} value={form.current} autoComplete="current-password" disabled={busy} onChange={update('current')} aria-invalid={!!errors.current} />
          </Field>
          <div className="settings-grid-break" />
          <Field label={t('Mật khẩu mới')} required error={errors.next && t(errors.next)} hint={t('settings.security.rule')}>
            <input type={type} value={form.next} autoComplete="new-password" disabled={busy} onChange={update('next')} aria-invalid={!!errors.next} />
          </Field>
          <Field label={t('Nhập lại mật khẩu mới')} required error={errors.confirm && t(errors.confirm)}>
            <input type={type} value={form.confirm} autoComplete="new-password" disabled={busy} onChange={update('confirm')} aria-invalid={!!errors.confirm} />
          </Field>
        </div>
        {form.next && <div className={`password-meter level-${strength}`} aria-live="polite">
          <span /><span /><span />
          <small>{t(['settings.security.weak', 'settings.security.fair', 'settings.security.good', 'settings.security.strong'][strength])}</small>
        </div>}
        <label className="settings-check"><input type="checkbox" checked={show} onChange={(event) => setShow(event.target.checked)} />{t('Hiện mật khẩu')}</label>
        {errors.form && <p className="notice error-state" role="alert">{t(errors.form)}</p>}
        <div className="settings-actions">
          <Button variant="primary" type="submit" loading={busy}>{busy ? t('Đang lưu…') : t('Đổi mật khẩu')}</Button>
        </div>
      </form>
    </Card>

    <Card title={t('Phiên đăng nhập')} description={t('settings.sessions.description')}>
      {sessionError ? <p className="notice error-state" role="alert">{t(sessionError)}</p>
        : !sessions ? <p className="muted" role="status">{t('Đang tải…')}</p>
          : <div className="settings-session">
            <div><strong>{t('settings.sessions.active', { count: formatNumber(sessions.active_sessions) })}</strong>
              <span className="muted">{t(sessions.other_sessions ? 'settings.sessions.others' : 'settings.sessions.onlyThis', { count: formatNumber(sessions.other_sessions) })}</span></div>
            <div className="settings-session-actions">
              <Button variant="outline" type="button" onClick={loadSessions}>{t('Làm mới')}</Button>
              <Button variant="outline" disabled={!sessions.other_sessions} onClick={signOutOthers}>{t('Đăng xuất thiết bị khác')}</Button>
            </div>
          </div>}
    </Card>
  </>;
}

// ---------------- Preferences ----------------
function PreferencesTab({ dark, setDark, branches, branch, setBranch, notify }) {
  const { t, language, setLanguage } = useLanguage();
  const option = (active, onClick, label, description) => <button type="button" className={`settings-choice ${active ? 'is-active' : ''}`} aria-pressed={active} onClick={onClick}>
    <b>{label}</b><small>{description}</small>
  </button>;
  return <>
    <Card title={t('Ngôn ngữ')} description={t('settings.pref.languageDescription')}>
      <div className="settings-choices">
        {/* Language names stay in their own language so anyone can find theirs. */}
        {option(language === 'vi', () => setLanguage('vi'), LANGUAGE_NAMES.vi, t('settings.pref.viHint'))}
        {option(language === 'en', () => setLanguage('en'), LANGUAGE_NAMES.en, t('settings.pref.enHint'))}
      </div>
    </Card>
    <Card title={t('Giao diện')} description={t('settings.pref.themeDescription')}>
      <div className="settings-choices">
        {option(!dark, () => setDark(false), t('Sáng'), t('settings.pref.light'))}
        {option(dark, () => setDark(true), t('Tối'), t('settings.pref.dark'))}
      </div>
    </Card>
    {branches.length > 0 && <Card title={t('Chi nhánh làm việc')} description={t('settings.pref.branchDescription')}>
      <Field label={t('Chi nhánh')}>
        <Select value={branch} onChange={(event) => { setBranch(event.target.value); notify('settings.pref.branchSaved'); }}>
          {branches.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </Select>
      </Field>
    </Card>}
  </>;
}

export default function SettingsPage({ demo, user, onUserUpdated, demoStore, onDemoSave, notify, go, dark, setDark, branches, branch, setBranch }) {
  const { t } = useLanguage();
  const [tab, setTab] = useState('store');
  // Every tab stays mounted (only hidden), so switching tabs never discards what was typed.
  return <div className="settings-layout">
    <nav className="settings-tabs" role="tablist" aria-label={t('Cài đặt')}>
      {TABS.map(([id, label, hint]) => <button key={id} type="button" role="tab" id={`settings-tab-${id}`} aria-selected={tab === id}
        aria-controls={`settings-panel-${id}`} className={tab === id ? 'is-active' : ''} onClick={() => setTab(id)}>
        <Icon name={id} /><span><b>{t(label)}</b><small>{t(hint)}</small></span>
      </button>)}
    </nav>
    <div className="settings-panels">
      <div role="tabpanel" id="settings-panel-store" aria-labelledby="settings-tab-store" hidden={tab !== 'store'}>
        <StoreTab demo={demo} demoStore={demoStore} onDemoSave={onDemoSave} notify={notify} go={go}
          onRenamed={(name) => onUserUpdated({ ...user, shop_name: name })} />
      </div>
      <div role="tabpanel" id="settings-panel-account" aria-labelledby="settings-tab-account" hidden={tab !== 'account'}>
        <AccountTab demo={demo} user={user} onUpdated={onUserUpdated} notify={notify} />
      </div>
      <div role="tabpanel" id="settings-panel-security" aria-labelledby="settings-tab-security" hidden={tab !== 'security'}>
        <SecurityTab demo={demo} notify={notify} />
      </div>
      <div role="tabpanel" id="settings-panel-preferences" aria-labelledby="settings-tab-preferences" hidden={tab !== 'preferences'}>
        <PreferencesTab dark={dark} setDark={setDark} branches={branches} branch={branch} setBranch={setBranch} notify={notify} />
      </div>
    </div>
  </div>;
}
