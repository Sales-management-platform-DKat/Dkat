import { friendlyMessage } from '../../lib/api-errors.js';

const listeners = new Set();
let items = [];
let sequence = 0;

const titles = {
  success: 'Thành công',
  error: 'Không thể hoàn tất',
  warning: 'Cần lưu ý',
  info: 'Thông báo',
};

const DURATIONS = { success: 4000, info: 4500, warning: 6500, error: 7000 };
const DEDUPE_WINDOW_MS = 4000;

function emit() {
  const snapshot = items;
  listeners.forEach((listener) => listener(snapshot));
}

export function getToasts() {
  return items;
}

export function subscribeToasts(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// duration: milliseconds; 0 keeps the toast until the user closes it.
// message/title: text, a catalog key, or { key, values }; the Toaster translates them on render.
export function pushToast({ message, kind = 'success', title, duration } = {}) {
  const text = typeof message === 'string' || typeof message?.key === 'string' ? message : friendlyMessage(message);
  const now = Date.now();
  const signature = JSON.stringify(text);
  const same = items.find((item) => item.kind === kind && JSON.stringify(item.message) === signature && now - item.createdAt < DEDUPE_WINDOW_MS);
  if (same) {
    // The same message again: restart its timer instead of stacking a copy.
    items = items.map((item) => item.id === same.id ? { ...item, createdAt: now, repeat: (item.repeat || 1) + 1 } : item);
    emit();
    return same.id;
  }
  const id = ++sequence;
  const item = {
    id,
    kind,
    title: title || titles[kind] || titles.info,
    message: text,
    duration: duration ?? DURATIONS[kind] ?? DURATIONS.info,
    createdAt: now,
    repeat: 1,
  };
  items = [...items, item].slice(-4);
  emit();
  return id;
}

export function dismissToast(id) {
  items = items.filter((item) => item.id !== id);
  emit();
}

export const notify = {
  success: (message, options = {}) => pushToast({ ...options, message, kind: 'success' }),
  info: (message, options = {}) => pushToast({ ...options, message, kind: 'info' }),
  warning: (message, options = {}) => pushToast({ ...options, message, kind: 'warning' }),
  // Server-side failures stay until dismissed so they are not missed.
  error: (error, options = {}) => pushToast({
    title: error?.status === 403 ? 'Không có quyền' : error?.code === 'DATABASE_SCHEMA_OUTDATED' ? 'Hệ thống cần cập nhật'
      : error?.status === 0 || error?.status >= 500 ? 'Lỗi kết nối' : undefined,
    duration: error?.status === 0 || error?.status >= 500 ? 0 : undefined,
    ...options,
    message: typeof error?.key === 'string' ? error : friendlyMessage(error, options.fallback),
    kind: 'error',
  }),
};
