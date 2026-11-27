import React, { createContext, useContext, useEffect, useId, useRef, useState } from 'react';
import { Button } from '../ui.jsx';
import { Dialog } from './Dialog.jsx';
import { confirmAction } from './confirm.js';
import { useLanguage } from '../../i18n/index.js';

const FormContext = createContext({ errors: {} });

export function FormField({ name, label, hint, required = false, children }) {
  const { errors } = useContext(FormContext);
  const { t } = useLanguage();
  // Messages are kept in their source form and translated here, so they follow a language switch.
  const error = name && errors[name] ? t(errors[name]) : '';
  const fieldId = name ? `dk-${name}` : undefined;
  const describedBy = error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined;
  const control = React.isValidElement(children)
    ? React.cloneElement(children, {
      id: children.props.id || fieldId,
      'aria-invalid': error ? true : undefined,
      'aria-describedby': [children.props['aria-describedby'], describedBy].filter(Boolean).join(' ') || undefined,
    })
    : children;

  return (
    <label className={`dk-field${error ? ' is-invalid' : ''}`}>
      <span className="dk-field-label">{label}{required && <i aria-hidden="true">*</i>}</span>
      {control}
      {error ? <small id={`${fieldId}-error`} className="dk-field-error" role="alert">{error}</small> : hint && <small id={`${fieldId}-hint`} className="dk-field-hint">{hint}</small>}
    </label>
  );
}

export function FormSection({ title, description, children }) {
  return (
    <section className="dk-section">
      {(title || description) && (
        <header>
          {title && <h3>{title}</h3>}
          {description && <p>{description}</p>}
        </header>
      )}
      <div className="dk-section-grid">{children}</div>
    </section>
  );
}

// Browser constraint checks (required, min, pattern...) shown inline instead of as browser bubbles.
function nativeErrors(form) {
  const result = {};
  for (const element of form.elements) {
    if (!element.name || element.disabled || element.validity?.valid !== false || result[element.name]) continue;
    const v = element.validity;
    result[element.name] = v.valueMissing ? 'Vui lòng nhập thông tin này.'
      : v.typeMismatch ? 'Định dạng chưa đúng.'
        : v.rangeUnderflow || v.rangeOverflow ? 'Giá trị nằm ngoài khoảng cho phép.'
          : v.tooLong ? 'Nội dung quá dài.'
            : v.patternMismatch ? (element.title || 'Định dạng chưa đúng.')
              : v.stepMismatch || v.badInput ? 'Vui lòng nhập số hợp lệ.' : 'Giá trị chưa hợp lệ.';
  }
  return result;
}

export function FormDialog({
  open = true,
  title,
  description,
  eyebrow,
  size = 'md',
  busy = false,
  error = '',
  fieldErrors = null,
  submitLabel = 'Lưu',
  cancelLabel = 'Hủy',
  onClose,
  onSubmit,
  validate,
  children,
  dismissible = true,
  confirmDiscard = true,
  footerExtra = null,
}) {
  const { t } = useLanguage();
  const formId = useId();
  const lock = useRef(false);
  const formRef = useRef(null);
  const dirty = useRef(false);
  const [errors, setErrors] = useState({});

  // Server-side field errors (422) are shown next to the matching inputs.
  useEffect(() => {
    if (!fieldErrors || !Object.keys(fieldErrors).length) return;
    setErrors(fieldErrors);
    requestAnimationFrame(() => formRef.current?.querySelector('[aria-invalid="true"]')?.focus());
  }, [fieldErrors]);

  async function requestClose() {
    if (busy) return;
    if (confirmDiscard && dirty.current) {
      const ok = await confirmAction({
        title: 'Đóng biểu mẫu?',
        description: 'Thông tin bạn vừa nhập chưa được lưu và sẽ bị mất.',
        confirmLabel: 'Đóng, không lưu',
        cancelLabel: 'Tiếp tục nhập',
        tone: 'danger',
      });
      if (!ok) return;
    }
    onClose?.();
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (busy || lock.current) return;
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const nextErrors = { ...nativeErrors(event.currentTarget), ...(validate?.(data) || {}) };
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      const first = event.currentTarget.querySelector('[aria-invalid="true"], .is-invalid input, .is-invalid select, .is-invalid textarea');
      first?.focus();
      return;
    }
    setErrors({});
    lock.current = true;
    try {
      const saved = await onSubmit?.(data, event);
      if (saved !== false) dirty.current = false;
    } finally {
      lock.current = false;
    }
  }

  return (
    <Dialog
      open={open}
      title={title}
      description={description}
      eyebrow={eyebrow}
      size={size}
      busy={busy}
      dismissible={dismissible}
      onClose={requestClose}
      footer={(
        <>
          {footerExtra}
          <Button variant="outline" type="button" disabled={busy} onClick={requestClose}>{t(cancelLabel)}</Button>
          <Button variant="primary" type="submit" form={formId} loading={busy}>{busy ? t('Đang lưu…') : t(submitLabel)}</Button>
        </>
      )}
    >
      <FormContext.Provider value={{ errors }}>
        <form
          id={formId}
          ref={formRef}
          className="dk-form"
          noValidate
          onSubmit={handleSubmit}
          onChange={() => { dirty.current = true; }}
          onInput={(event) => {
            dirty.current = true;
            const field = event.target?.name;
            if (!field || !errors[field]) return;
            setErrors((current) => {
              const next = { ...current };
              delete next[field];
              return next;
            });
          }}
        >
          {error && <div className="dk-form-error" role="alert">{t(error)}</div>}
          {children}
        </form>
      </FormContext.Provider>
    </Dialog>
  );
}
