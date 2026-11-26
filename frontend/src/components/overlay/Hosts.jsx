import React, { useEffect, useRef, useState } from 'react';
import { ConfirmDialog } from './ConfirmDialog.jsx';
import { dismissToast, subscribeToasts } from './toast.js';
import { translate } from '../../i18n/index.js';

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
        <strong>{item.title}{item.repeat > 1 && <span className="dk-toast-repeat"> ×{item.repeat}</span>}</strong>
        <p>{item.message}</p>
      </div>
      <button type="button" aria-label={translate('Đóng thông báo')} onClick={close}>×</button>
    </article>
  );
}

export function ConfirmHost() {
  const [request, setRequest] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const queue = useRef([]);

  useEffect(() => {
    function onConfirm(event) {
      setRequest((current) => {
        if (current) {
          queue.current.push(event.detail);
          return current;
        }
        return event.detail;
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
          setError(cause?.message || 'Không thực hiện được thao tác. Dữ liệu bạn nhập vẫn được giữ.');
        }
      }}
    />
  );
}
