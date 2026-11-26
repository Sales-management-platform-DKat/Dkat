const listeners = new Set();
let items = [];
let sequence = 0;

const titles = {
  success: 'Đã hoàn tất',
  error: 'Không thể hoàn tất',
  warning: 'Cần lưu ý',
  info: 'Thông báo',
};

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

export function pushToast({ message, kind = 'success', title, duration } = {}) {
  const id = ++sequence;
  const item = {
    id,
    kind,
    title: title || titles[kind] || titles.info,
    message: typeof message === 'string' ? message : message?.message || 'Đã xảy ra sự cố khi xử lý yêu cầu.',
    duration: duration ?? (kind === 'error' ? 7000 : 4500),
  };
  items = [...items, item].slice(-4);
  emit();
  return id;
}

export function dismissToast(id) {
  items = items.filter((item) => item.id !== id);
  emit();
}
