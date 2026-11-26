import { apiRequest } from '../../auth-client.js';

export function listPreorders({ branchId, status, paymentStatus, keyword = '', page = 1, size = 50 } = {}) {
  const params = new URLSearchParams({ page: String(page), size: String(size) });
  if (branchId) params.set('branchId', String(branchId));
  if (status) params.set('status', status);
  if (paymentStatus) params.set('paymentStatus', paymentStatus);
  if (keyword) params.set('keyword', keyword);
  return apiRequest(`/preorders?${params}`);
}

export function getPreorder(id) { return apiRequest(`/preorders/${encodeURIComponent(id)}`); }
export function createPreorder(payload) { return apiRequest('/preorders', { method: 'POST', body: JSON.stringify(payload) }); }
export function confirmPreorderPayment(id, payload) { return apiRequest(`/preorders/${encodeURIComponent(id)}/confirm-payment`, { method: 'POST', body: JSON.stringify(payload) }); }
export function setPreorderFulfillment(id, payload) { return apiRequest(`/preorders/${encodeURIComponent(id)}/fulfillment`, { method: 'PUT', body: JSON.stringify(payload) }); }
export function fulfillPreorder(id, payload = {}) { return apiRequest(`/preorders/${encodeURIComponent(id)}/fulfill`, { method: 'POST', body: JSON.stringify(payload) }); }
export function cancelPreorder(id, reason) { return apiRequest(`/preorders/${encodeURIComponent(id)}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) }); }
export function listPreorderNotifications(id) { return apiRequest(`/preorders/${encodeURIComponent(id)}/notifications`); }
export function resendNotification(id) { return apiRequest(`/notifications/${encodeURIComponent(id)}/resend`, { method: 'POST' }); }
