import React, { useEffect, useRef, useState } from 'react';
import { errorMessage, useLanguage } from '../i18n/index.js';
import { Button } from './ui.jsx';

// In-app replacement for window.confirm/window.prompt: translated, styled, keyboard friendly.
// API matches the overlay module in progress (confirmAction + ConfirmHost, event "dkat-confirm"),
// so either implementation can back the same call sites.
//
//   const result = await confirmAction({ title, description, tone, confirmLabel, requireReason, onConfirm });
//   result === null      -> cancelled
//   result.reason        -> confirmed ('' unless requireReason; prefilled from initialValue)
//
// onConfirm (optional) runs while the dialog shows a busy state; if it throws, the dialog stays open,
// keeps what the user typed and shows the error, so a failed request never loses input.
export function confirmAction(options) {
  return new Promise((resolve) => {
    window.dispatchEvent(new CustomEvent('dkat-confirm', { detail: { options, resolve } }));
  });
}

export function ConfirmHost() {
  const { t } = useLanguage();
  const [request, setRequest] = useState(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const queue = useRef([]);
  const cancelRef = useRef(null);
  const reasonRef = useRef(null);

  useEffect(() => {
    function onConfirm(event) {
      setRequest((current) => {
        if (current) { queue.current.push(event.detail); return current; }
        return event.detail;
      });
    }
    window.addEventListener('dkat-confirm', onConfirm);
    return () => window.removeEventListener('dkat-confirm', onConfirm);
  }, []);

  useEffect(() => {
    if (!request) return undefined;
    setReason(request.options?.initialValue || '');
    setError('');
    const target = request.options?.requireReason ? reasonRef.current : cancelRef.current;
    target?.focus();
    return undefined;
  }, [request]);

  function settle(value) {
    request?.resolve(value);
    setBusy(false);
    setRequest(queue.current.shift() || null);
  }

  if (!request) return null;
  const {
    tone = 'danger', title, description, confirmLabel = 'Xác nhận', cancelLabel = 'Hủy',
    requireReason = false, reasonLabel = 'Lý do', reasonPlaceholder = 'Nhập lý do để tiếp tục',
  } = request.options || {};

  async function confirm(event) {
    event?.preventDefault();
    if (busy) return;
    if (requireReason && !reason.trim()) { setError('Hãy nhập lý do trước khi xác nhận.'); reasonRef.current?.focus(); return; }
    const result = { reason: requireReason ? reason.trim() : '' };
    if (!request.options?.onConfirm) { settle(result); return; }
    setBusy(true);
    setError('');
    try {
      await request.options.onConfirm(result);
      settle(result);
    } catch (cause) {
      setBusy(false);
      setError(errorMessage(cause, 'Không thực hiện được thao tác. Dữ liệu bạn nhập vẫn được giữ.'));
    }
  }

  const close = () => { if (!busy) settle(null); };
  return (
    <div className="overlay confirm-overlay" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && close()}
      onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } }}>
      <form className={`dialog confirm-dialog tone-${tone}`} role="alertdialog" aria-modal="true"
        aria-labelledby="confirm-title" aria-describedby={description ? 'confirm-description' : undefined} aria-busy={busy} onSubmit={confirm}>
        <span className="confirm-icon" aria-hidden="true">{tone === 'danger' || tone === 'warning' ? '!' : 'i'}</span>
        <h2 id="confirm-title">{t(title)}</h2>
        {description && <p id="confirm-description" className="muted">{t(description)}</p>}
        {requireReason && (
          <label className="field">{t(reasonLabel)}
            <textarea ref={reasonRef} rows="3" maxLength="255" value={reason} disabled={busy} placeholder={t(reasonPlaceholder)}
              aria-invalid={!!error && !reason.trim()} onChange={(e) => { setReason(e.target.value); setError(''); }} />
          </label>
        )}
        {error && <p className="field-error" role="alert">{t(error)}</p>}
        <div className="confirm-actions">
          <Button ref={cancelRef} variant="outline" type="button" disabled={busy} onClick={close}>{t(cancelLabel)}</Button>
          <Button variant={tone === 'danger' ? 'destructive' : 'primary'} type="submit" loading={busy}>
            {busy ? t('Đang xử lý…') : t(confirmLabel)}
          </Button>
        </div>
      </form>
    </div>
  );
}
