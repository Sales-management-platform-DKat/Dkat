import { apiRequest } from '../../auth-client.js';

export function listBranches({ status } = {}) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  return apiRequest(`/branches?${params}`);
}

export function createBranch(payload) { return apiRequest('/branches', { method: 'POST', body: JSON.stringify(payload) }); }
export function updateBranch(id, payload) { return apiRequest(`/branches/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(payload) }); }
export function setBranchStatus(id, status) { return apiRequest(`/branches/${encodeURIComponent(id)}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }); }
