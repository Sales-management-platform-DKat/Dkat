import React, { useEffect, useRef, useState } from 'react';
import { ConfirmDialog } from './ConfirmDialog.jsx';
import { dismissToast, subscribeToasts } from './toast.js';
import { errorMessage, useLanguage } from '../../i18n/index.js';

export function Toaster() {
  const [items, setItems] = useState([]);

  useEffect(() => subscribeToasts(setItems), []);

  return (
    <div className="dk-toaster" aria-live="polite">
      {items.map((item) => <ToastCard key={item.id} item={item} />)}
    </div>
  );
}

function ToastCard({ item }) {
  // Titles and messages stay in their source form (Vietnamese or a key) until here,
  // so a toast that is already on screen follows a language switch.
  const { t } = useLanguage();
  const [leaving, setLeaving] = useState(false);
  const paused = useRef(false);
  const remaining = useRef(item.duration);
  const started = useRef(0);
  const timer = useRef(null);

  function schedule(delay) {
    clearTimeout(timer.current);
    started.current = Date.now();
    // duration 0: important errors stay until the user closes them.
    if (item.duration > 0) timer.current = setTimeout(close, delay);
  }

  useEffect(() => {
    // A repeated message restarts the countdown (see pushToast de-duplication).
    remaining.current = item.duration;
    schedule(remaining.current);
    return () => clearTimeout(timer.current);
  }, [item.id, item.createdAt]);

  function close() {
    if (leaving) return;
    clearTimeout(timer.current);
    setLeaving(true);
    setTimeout(() => dismissToast(item.id), 160);
  }

  return (
    <article
      className={`dk-toast dk-toast-${item.kind}${leaving ? ' is-leaving' : ''}`}
      role={item.kind === 'error' ? 'alert' : 'status'}
      onMouseEnter={() => { if (paused.current || leaving) return; paused.current = true; clearTimeout(timer.current); remaining.current = Math.max(0, remaining.current - (Date.now() - started.current)); }}
      onMouseLeave={() => { if (!paused.current || leaving) return; paused.current = false; schedule(Math.max(remaining.current, 800)); }}
    >
      <span className="dk-toast-mark" aria-hidden="true">{item.kind === 'error' ? '!' : item.kind === 'warning' ? '!' : item.kind === 'info' ? 'i' : '✓'}</span>
      <div>
        <strong>{t(item.title)}{item.repeat > 1 && <span className="dk-toast-repeat"> ×{item.repeat}</span>}</strong>
        <p>{t(item.message)}</p>
      </div>
      <button type="button" aria-label={t('Đóng thông báo')} onClick={close}>×</button>
    </article>
  );
}

let requestSequence = 0;

export function ConfirmHost() {
  const [request, setRequest] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const queue = useRef([]);
  // Keyed by the last request: a new confirmation starts with an empty reason,
  // while closing keeps the same instance so the exit animation still plays.
  const shownId = useRef(0);
  if (request) shownId.current = request.id;

  useEffect(() => {
    function onConfirm(event) {
      // Each request gets its own id so the dialog (and a typed reason) starts fresh.
      const next = { ...event.detail, id: ++requestSequence };
      setRequest((current) => {
        if (current) {
          queue.current.push(next);
          return current;
        }
        return next;
      });
    }
    window.addEventListener('dkat-confirm', onConfirm);
    return () => window.removeEventListener('dkat-confirm', onConfirm);
  }, []);

  function settle(value) {
    request?.resolve(value);
    setBusy(false);
    setError('');
    setRequest(queue.current.shift() || null);
  }

  return (
    <ConfirmDialog
      key={shownId.current}
      open={!!request}
      busy={busy}
      error={error}
      {...(request?.options || {})}
      onClose={() => { if (!busy) settle(null); }}
      onConfirm={async (result) => {
        if (busy) return;
        setBusy(true);
        setError('');
        try {
          await request?.options?.onConfirm?.(result);
          settle(result);
        } catch (cause) {
          setBusy(false);
          setError(errorMessage(cause, 'Không thực hiện được thao tác. Dữ liệu bạn nhập vẫn được giữ.'));
        }
      }}
    />
  );
}
