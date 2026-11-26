import { useEffect, useLayoutEffect } from 'react';

export function fieldValidationMessage(field) {
  const { validity } = field;
  if (validity.badInput && field.type === 'number') return 'validation.number';
  if (validity.valueMissing) {
    if (field.type === 'checkbox') return 'validation.checkbox';
    if (field.tagName === 'SELECT' || field.type === 'radio') return 'validation.select';
    return 'validation.required';
  }
  if (field.type === 'email' && (validity.typeMismatch || validity.patternMismatch)) {
    return 'validation.email';
  }
  if (validity.typeMismatch && field.type === 'url') return 'validation.url';
  if (validity.tooShort) return { key: 'validation.minLength', values: { length: field.minLength } };
  if (validity.tooLong) return { key: 'validation.maxLength', values: { length: field.maxLength } };
  if (validity.patternMismatch && (field.name === 'username' || field.name === 'owner_username')) {
    return '3–32 characters: letters, numbers, periods, underscores, or hyphens.';
  }
  if (validity.rangeUnderflow) return { key: 'validation.minimum', values: { min: field.min } };
  if (validity.rangeOverflow) return { key: 'validation.maximum', values: { max: field.max } };
  if (validity.stepMismatch && field.type === 'number') {
    if (!field.step || field.step === '1') return 'validation.wholeNumber';
    return { key: 'validation.step', values: { step: field.step } };
  }
  return 'validation.invalid';
}

export function useFormValidation(toast, setToast, messageId) {
  useEffect(() => {
    const root = document.getElementById('root');
    if (!root) return;
    let pending;

    const onInvalid = (event) => {
      const field = event.target;
      if (!field.form || !field.validity) return;
      event.preventDefault();
      // Wait for all invalid events in this submit before reporting the first one.
      if (pending !== undefined) return;
      pending = setTimeout(() => {
        pending = undefined;
        if (field.isConnected && !field.validity.valid) {
          setToast({ kind: 'error', message: fieldValidationMessage(field), field });
        }
      }, 0);
    };
    const onEdit = ({ target: field }) => {
      setToast((current) => current?.field === field ? null : current);
    };
    const onSubmit = ({ target: form }) => {
      setToast((current) => current?.field?.form === form ? null : current);
    };

    root.addEventListener('invalid', onInvalid, true);
    // React's controlled inputs need to process the edit before the toast is cleared.
    root.addEventListener('input', onEdit);
    root.addEventListener('change', onEdit);
    root.addEventListener('submit', onSubmit);
    return () => {
      clearTimeout(pending);
      root.removeEventListener('invalid', onInvalid, true);
      root.removeEventListener('input', onEdit);
      root.removeEventListener('change', onEdit);
      root.removeEventListener('submit', onSubmit);
    };
  }, [setToast]);

  useLayoutEffect(() => {
    const field = toast?.field;
    if (!field) return;
    const clear = () => setToast((current) => current === toast ? null : current);
    if (!field.isConnected) {
      clear();
      return;
    }

    const invalid = field.getAttribute('aria-invalid');
    const description = field.getAttribute('aria-describedby');
    field.setAttribute('aria-invalid', 'true');
    field.setAttribute('aria-describedby', [description, messageId].filter(Boolean).join(' '));
    field.focus();

    const observer = new MutationObserver(() => {
      if (!field.isConnected) clear();
    });
    observer.observe(document.getElementById('root'), { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      if (invalid === null) field.removeAttribute('aria-invalid');
      else field.setAttribute('aria-invalid', invalid);
      if (description === null) field.removeAttribute('aria-describedby');
      else field.setAttribute('aria-describedby', description);
    };
  }, [toast, setToast, messageId]);
}
