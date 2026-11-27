import React, { useState } from 'react';
import { Button } from '../ui.jsx';
import { Dialog } from './Dialog.jsx';
import { useLanguage } from '../../i18n/index.js';

function ToneIcon({ tone }) {
  if (tone === 'danger') {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8v5M12 17h.01" /><path d="M10.3 4.8 2.8 18a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4.8a2 2 0 0 0-3.4 0Z" /></svg>;
  }
  if (tone === 'warning') {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8v5M12 17h.01" /><circle cx="12" cy="12" r="9" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 8h.01" /></svg>;
}

export function ConfirmDialog({
  open = false,
  tone = 'danger',
  title,
  description,
  confirmLabel = 'Xác nhận',
  cancelLabel = 'Hủy',
  busy = false,
  error = '',
  requireReason = false,
  reasonLabel = 'Lý do',
  reasonPlaceholder = 'Nhập lý do để tiếp tục',
  onClose,
  onConfirm,
}) {
  const { t } = useLanguage();
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState('');
  const working = busy;

  async function confirm(event) {
    event?.preventDefault?.();
    if (working) return;
    if (requireReason && !reason.trim()) {
      setReasonError('Hãy nhập lý do trước khi xác nhận.');
      return;
    }
    setReasonError('');
    await onConfirm?.(requireReason ? { reason: reason.trim() } : { reason: '' });
  }

  return (
    <Dialog
      open={open}
      title={t(title)}
      description={description ? t(description) : description}
      size="sm"
      role="alertdialog"
      busy={working}
      dismissible
      onClose={onClose}
      className="dk-confirm-dialog"
      initialFocus="[data-dialog-cancel]"
      footer={(
        <>
          <Button variant="outline" type="button" data-dialog-cancel disabled={working} onClick={onClose}>{t(cancelLabel)}</Button>
          <Button variant={tone === 'danger' ? 'destructive' : 'primary'} type="button" loading={working} onClick={confirm}>{working ? t('Đang xử lý…') : t(confirmLabel)}</Button>
        </>
      )}
    >
      <div className={`dk-confirm dk-confirm-${tone}`}>
        <span className="dk-confirm-icon"><ToneIcon tone={tone} /></span>
        <div>
          {error && <p className="dk-form-error" role="alert">{t(error)}</p>}
          {requireReason && (
            <label className={`dk-field${reasonError ? ' is-invalid' : ''}`}>
              <span className="dk-field-label">{t(reasonLabel)}<i aria-hidden="true">*</i></span>
              <textarea value={reason} rows={3} maxLength={255} disabled={working} placeholder={t(reasonPlaceholder)} aria-invalid={reasonError ? true : undefined} onChange={(event) => { setReason(event.target.value); setReasonError(''); }} />
              {reasonError && <small className="dk-field-error" role="alert">{t(reasonError)}</small>}
            </label>
          )}
        </div>
      </div>
    </Dialog>
  );
}
