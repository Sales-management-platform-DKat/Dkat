import { apiRequest } from '../../auth-client.js';

export function listCustomers({ query = '', limit = 100 } = {}) {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return apiRequest(`/customers?${params}`);
}

export function quickSearchCustomers(query, { limit = 10 } = {}) {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return apiRequest(`/customers/quick-search?${params}`);
}

export function getCustomer(customerId) {
  return apiRequest(`/customers/${encodeURIComponent(customerId)}`);
}

export function getCustomerPurchaseHistory(customerId, { limit = 100 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiRequest(`/customers/${encodeURIComponent(customerId)}/history?${params}`);
}

export function createCustomer(payload) {
  return apiRequest('/customers', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateCustomer(customerId, payload) {
  return apiRequest(`/customers/${encodeURIComponent(customerId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}
