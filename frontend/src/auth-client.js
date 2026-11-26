import { ApiError, errorFromResponse, networkError } from './lib/api-errors.js';

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || '/api/v1'
).replace(/\/$/, '');

export function apiAssetUrl(path) {
  if (!path) return '';
  if (/^(?:https?:|data:|blob:)/i.test(path)) return path;
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

let accessToken = null;
let refreshPromise = null;
// When set (demo mode), every request goes to this in-browser handler instead of the server.
let demoHandler = null;

export function setAccessToken(token) {
  accessToken = token || null;
}

export function setDemoApiHandler(handler) {
  demoHandler = handler || null;
}

export function isDemoApi() {
  return !!demoHandler;
}

async function readResponse(response) {
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      // Proxies return HTML error pages; never show them to the user.
      data = null;
    }
  }
  return { data, response };
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
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      credentials: 'include',
      headers,
    });
  } catch (cause) {
    if (cause?.name === 'AbortError') throw cause;
    throw networkError(cause);
  }
  return readResponse(response);
}

async function demoRequest(path, options) {
  try {
    return await demoHandler(path, options);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw errorFromResponse(error?.status || 400, error?.details
      ? { detail: { code: error.code, message: error.message }, details: error.details }
      : { detail: error?.code ? { code: error.code, message: error.message } : error?.message });
  }
}

export async function apiRequest(path, { adminToken, token, ...options } = {}) {
  if (demoHandler && !adminToken) return demoRequest(path, options);
  const requestToken = token || accessToken;
  let result = await send(path, { ...options, adminToken }, requestToken);
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
      throw error instanceof ApiError ? error : networkError(error);
    }
    if (session?.access_token) {
      result = await send(path, { ...options, adminToken }, session.access_token);
      if (result.response.status === 401) {
        setAccessToken(null);
        window.dispatchEvent(new Event('dkat-auth-expired'));
      }
    } else {
      window.dispatchEvent(new Event('dkat-auth-expired'));
      throw errorFromResponse(401, result.data);
    }
  }

  if (!result.response.ok) {
    const error = errorFromResponse(result.response.status, result.data);
    if (result.response.status >= 500) console.error('API error', result.response.status, path, result.data);
    throw error;
  }
  return result.data;
}

