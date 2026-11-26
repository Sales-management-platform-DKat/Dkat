import React, { createContext, useContext, useId, useRef, useState } from 'react';
import { Button } from '../ui.jsx';
import { Dialog } from './Dialog.jsx';

const FormContext = createContext({ errors: {} });

export function FormField({ name, label, hint, required = false, children }) {
  const { errors } = useContext(FormContext);
  const error = name ? errors[name] : '';
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

export function FormDialog({
  open = true,
  title,
  description,
  eyebrow,
  size = 'md',
  busy = false,
  error = '',
  submitLabel = 'Lưu',
  cancelLabel = 'Hủy',
  onClose,
  onSubmit,
  validate,
  children,
  dismissible = true,
}) {
  const formId = useId();
  const lock = useRef(false);
  const [errors, setErrors] = useState({});

  async function handleSubmit(event) {
    event.preventDefault();
    if (busy || lock.current) return;
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const nextErrors = validate?.(data) || {};
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      const first = event.currentTarget.querySelector('[aria-invalid="true"], .is-invalid input, .is-invalid select, .is-invalid textarea');
      first?.focus();
      return;
    }
    setErrors({});
    lock.current = true;
    try {
      await onSubmit?.(data, event);
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
      onClose={onClose}
      footer={(
        <>
          <Button variant="outline" type="button" disabled={busy} onClick={onClose}>{cancelLabel}</Button>
          <Button variant="primary" type="submit" form={formId} loading={busy}>{busy ? 'Đang lưu…' : submitLabel}</Button>
        </>
      )}
    >
      <FormContext.Provider value={{ errors }}>
        <form
          id={formId}
          className="dk-form"
          onSubmit={handleSubmit}
          onInput={(event) => {
            const field = event.target?.name;
            if (!field || !errors[field]) return;
            setErrors((current) => {
              const next = { ...current };
              delete next[field];
              return next;
            });
          }}
        >
          {error && <div className="dk-form-error" role="alert">{error}</div>}
          {children}
        </form>
      </FormContext.Provider>
    </Dialog>
  );
}
