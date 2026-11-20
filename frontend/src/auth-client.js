import { mockApiRequest } from './mocks/api';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

function dispatchToast(message) {
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('dkat:toast', { detail: { message, kind: 'error' } }));
}

export async function apiRequest(path, { adminToken, token, ...options } = {}) {
  token = token || (typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('dkat-access-token') : null);
  if (USE_MOCK) return mockApiRequest(path, { ...options, token });
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', 'Bearer ' + token);
  if (adminToken) headers.set('X-Admin-Token', adminToken);
  let response;
  try { response = await fetch(API_BASE_URL + path, { ...options, headers }); }
  catch { const error = new Error('\u004b\u00f4ng th\u1ec3 k\u1ebft n\u1ed1i m\u00e1y ch\u1ee7.');; error.code = 'NETWORK_ERROR'; dispatchToast(error.message); throw error; }
  const text = await response.text();
  let data = null;
  if (text) { try { data = JSON.parse(text); } catch { const error = new Error('Invalid server response.'); error.code = 'INVALID_RESPONSE'; throw error; } }
  if (!response.ok) {
    const apiError = data?.error;
    const detail = Array.isArray(data?.detail) ? data.detail.map(issue => issue.msg).join(' ') : data?.detail;
    const error = new Error(apiError?.message || (typeof detail === 'string' ? detail : 'Request failed.'));
    error.code = apiError?.code || (response.status === 422 ? 'VALIDATION_ERROR' : response.status === 403 ? 'FORBIDDEN' : response.status === 401 ? 'UNAUTHORIZED' : 'HTTP_ERROR');
    error.details = apiError?.details || (Array.isArray(data?.detail) ? data.detail.map(issue => ({ field: (issue.loc || []).filter(x => x !== 'body').join('.'), message: issue.msg })) : null);
    error.status = response.status;
    if (response.status === 401 && token) {
      sessionStorage.removeItem('dkat-access-token'); sessionStorage.removeItem('dkat-session'); sessionStorage.removeItem('dkat-demo-role');
      window.dispatchEvent(new CustomEvent('dkat:auth-expired'));
      if (location.hash.startsWith('#/admin')) location.hash = '#/login';
    }
    if (response.status === 403) dispatchToast('\u0042\u1ea1n kh\u00f4ng c\u00f3 quy\u1ec1n th\u1ef1c hi\u1ec7n thao t\u00e1c n\u00e0y.');
    throw error;
  }
  return data;
}
