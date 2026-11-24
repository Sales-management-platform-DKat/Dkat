import { apiRequest } from '../../auth-client.js';

export function listSalesOrders({ branchId, status, keyword = '', page = 1, size = 50 } = {}) {
  const params = new URLSearchParams({ page: String(page), size: String(size) });
  if (branchId) params.set('branchId', String(branchId));
  if (status) params.set('status', status);
  if (keyword) params.set('keyword', keyword);
  return apiRequest(`/sales-orders?${params}`);
}

export function getSalesOrder(orderId) {
  return apiRequest(`/sales-orders/${encodeURIComponent(orderId)}`);
}

export function createSalesOrder(payload) {
  return apiRequest('/sales-orders', { method: 'POST', body: JSON.stringify(payload) });
}

export function confirmSalesOrderPayment(orderId, payload) {
  return apiRequest(`/sales-orders/${encodeURIComponent(orderId)}/confirm-payment`, { method: 'POST', body: JSON.stringify(payload) });
}

export function cancelSalesOrder(orderId, reason) {
  return apiRequest(`/sales-orders/${encodeURIComponent(orderId)}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) });
}

export function refundSalesOrder(orderId, reason) {
  return apiRequest(`/sales-orders/${encodeURIComponent(orderId)}/refund`, { method: 'POST', body: JSON.stringify({ reason }) });
}
