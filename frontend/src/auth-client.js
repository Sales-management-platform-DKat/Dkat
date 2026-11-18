const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || '/api/v1'
).replace(/\/$/, '');

let accessToken = null;
let refreshPromise = null;

export function setAccessToken(token) {
  accessToken = token || null;
}

async function readResponse(response) {
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error('Máy chủ trả về dữ liệu không hợp lệ.');
    }
  }
  return { data, response };
}

function responseError(data) {
  const detail = Array.isArray(data?.detail)
    ? data.detail.map((issue) => issue.msg).join(' ')
    : data?.detail;
  return new Error(typeof detail === 'string' ? detail : 'Không thể xử lý yêu cầu.');
}

async function requestRefresh() {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
  });
  const { data } = await readResponse(response);
  if (!response.ok) {
    setAccessToken(null);
    return null;
  }
  setAccessToken(data?.access_token);
  return data;
}

export async function refreshSession() {
  if (!refreshPromise) {
    const refresh = () => requestRefresh();
    const locks = globalThis.navigator?.locks;
    refreshPromise = (locks?.request
      ? locks.request('dkat-auth-refresh', refresh)
      : refresh()).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

async function send(path, options, token) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.adminToken) headers.set('X-Admin-Token', options.adminToken);
  const { response, data } = await readResponse(await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers,
  }));
  return { response, data };
}

export async function apiRequest(path, { adminToken, token, ...options } = {}) {
  const requestToken = token || accessToken;
  let result = await send(path, options, requestToken);
  const canRefresh = requestToken
    && result.response.status === 401
    && !path.startsWith('/auth/');

  if (canRefresh) {
    let session;
    try {
      session = await refreshSession();
    } catch (error) {
      setAccessToken(null);
      window.dispatchEvent(new Event('dkat-auth-expired'));
      throw error;
    }
    if (session?.access_token) {
      result = await send(path, options, session.access_token);
      if (result.response.status === 401) {
        setAccessToken(null);
        window.dispatchEvent(new Event('dkat-auth-expired'));
      }
    } else {
      window.dispatchEvent(new Event('dkat-auth-expired'));
      throw responseError(result.data);
    }
  }

  if (!result.response.ok) throw responseError(result.data);
  return result.data;
}
