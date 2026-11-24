import { apiRequest } from '../../auth-client.js';

export function listCategories({ status } = {}) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  return apiRequest(`/categories?${params}`);
}

export function createCategory(payload) {
  return apiRequest('/categories', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateCategory(categoryId, payload) {
  return apiRequest(`/categories/${encodeURIComponent(categoryId)}`, { method: 'PUT', body: JSON.stringify(payload) });
}

export function setCategoryStatus(categoryId, status) {
  return apiRequest(`/categories/${encodeURIComponent(categoryId)}/status`, { method: 'PATCH', body: JSON.stringify({ status }) });
}
