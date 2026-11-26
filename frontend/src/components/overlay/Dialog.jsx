import React, { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { acquireLayer, focusableElements, isTopLayer, lockScroll } from './layer.js';

function Presence({ present, children }) {
  const [shown, setShown] = useState(present);
  const [phase, setPhase] = useState(present ? 'closed' : 'closed');

  useEffect(() => {
    if (present) {
      setShown(true);
      const frame = requestAnimationFrame(() => setPhase('open'));
      return () => cancelAnimationFrame(frame);
    }
    setPhase('closed');
    const timer = setTimeout(() => setShown(false), 180);
    return () => clearTimeout(timer);
  }, [present]);

  if (!shown) return null;
  return children(phase);
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M5.2 5.2 14.8 14.8M14.8 5.2 5.2 14.8" />
    </svg>
  );
}

export function Dialog({
  open = true,
  title,
  description,
  eyebrow,
  size = 'md',
  busy = false,
  dismissible = true,
  onClose,
  footer,
  children,
  role = 'dialog',
  className = '',
  initialFocus = '',
}) {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const canDismiss = dismissible && !busy;

  useEffect(() => {
    if (!open) return undefined;
    const unlock = lockScroll();
    const layer = acquireLayer();
    const panel = panelRef.current;
    if (panel) panel.style.zIndex = String(layer.zIndex);
    const overlay = panel?.parentElement;
    if (overlay) overlay.style.zIndex = String(layer.zIndex);
    const previouslyFocused = document.activeElement;
    const preferred = initialFocus ? panel?.querySelector(initialFocus) : null;
    const firstField = panel?.querySelector('input,select,textarea,button');
    (preferred || firstField || panel)?.focus();

    function onKeyDown(event) {
      if (!isTopLayer(layer.id)) return;
      if (event.key === 'Escape' && canDismiss) {
        event.preventDefault();
        onCloseRef.current?.();
        return;
      }
      if (event.key !== 'Tab' || !panel) return;
      const items = focusableElements(panel);
      if (!items.length) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      unlock();
      layer.release();
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    };
  }, [open, canDismiss, initialFocus]);

  return (
    <Presence present={open}>
      {(phase) => createPortal(
        <div
          className="dk-overlay"
          data-phase={phase}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && canDismiss) onClose?.();
          }}
        >
          <section
            ref={panelRef}
            className={`dk-dialog dk-dialog-${size}${className ? ` ${className}` : ''}`}
            role={role}
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={description ? descriptionId : undefined}
            aria-busy={busy || undefined}
            tabIndex={-1}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="dk-dialog-header">
              <div>
                {eyebrow && <span className="dk-eyebrow">{eyebrow}</span>}
                <h2 id={titleId}>{title}</h2>
                {description && <p id={descriptionId}>{description}</p>}
              </div>
              <button type="button" className="dk-close" aria-label="Đóng" disabled={!canDismiss} onClick={onClose}>
                <CloseIcon />
              </button>
            </header>
            <div className="dk-dialog-body">{children}</div>
            {footer && <footer className="dk-dialog-footer">{footer}</footer>}
          </section>
        </div>,
        document.body,
      )}
    </Presence>
  );
}

export function Drawer({
  open = true,
  title,
  description,
  eyebrow,
  size = 'md',
  busy = false,
  dismissible = true,
  onClose,
  footer,
  children,
}) {
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
      footer={footer}
      className={`dk-drawer dk-drawer-${size}`}
    >
      {children}
    </Dialog>
  );
}
