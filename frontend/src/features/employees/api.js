import { apiRequest } from '../../auth-client.js';

export function listEmployees({ query = '', branchId, page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams({ q: query, page: String(page), page_size: String(pageSize) });
  if (branchId) params.set('branchId', String(branchId));
  return apiRequest(`/users?${params}`);
}

export function createEmployee(payload) {
  return apiRequest('/users', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateEmployee(employeeId, payload) {
  return apiRequest(`/users/${encodeURIComponent(employeeId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function setEmployeeStatus(employeeId, status) {
  return apiRequest(`/users/${encodeURIComponent(employeeId)}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export function assignEmployeeBranches(employeeId, branchIds) {
  return apiRequest(`/users/${encodeURIComponent(employeeId)}/branches`, {
    method: 'PUT',
    body: JSON.stringify({ branch_ids: branchIds }),
  });
}

export function resetEmployeePassword(employeeId, newPassword) {
  return apiRequest(`/users/${encodeURIComponent(employeeId)}/reset-password`, {
    method: 'POST',
    body: JSON.stringify({ new_password: newPassword }),
  });
}
