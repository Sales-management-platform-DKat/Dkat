const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'
).replace(/\/$/, '');

export async function apiRequest(path, { adminToken, token, ...options } = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (adminToken) headers.set('X-Admin-Token', adminToken);

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error('Máy chủ trả về dữ liệu không hợp lệ.');
    }
  }
  if (!response.ok) {
    const detail = Array.isArray(data?.detail)
      ? data.detail.map((issue) => issue.msg).join(' ')
      : data?.detail;
    throw new Error(typeof detail === 'string' ? detail : 'Không thể xử lý yêu cầu.');
  }
  return data;
}
