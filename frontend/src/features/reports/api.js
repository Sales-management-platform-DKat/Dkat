import { apiRequest } from '../../auth-client.js';

function dateParams({ from, to, branchId } = {}) {
  const params = new URLSearchParams();
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  if (branchId) params.set('branchId', String(branchId));
  return params;
}

export function getReportSummary(filters) {
  return apiRequest(`/reports/summary?${dateParams(filters)}`);
}

export function getRevenueReport(filters = {}) {
  const params = dateParams(filters);
  params.set('granularity', filters.granularity || 'day');
  return apiRequest(`/reports/revenue?${params}`);
}

export function getTopProducts(filters = {}) {
  const params = dateParams(filters);
  params.set('limit', String(filters.limit || 10));
  params.set('sortBy', filters.sortBy || 'revenue');
  return apiRequest(`/reports/top-products?${params}`);
}

export function exportRevenueReport(filters = {}) {
  const params = dateParams(filters);
  params.set('granularity', filters.granularity || 'day');
  return apiRequest(`/reports/revenue/export?${params}`);
}
