import { apiRequest } from '../../auth-client.js';

export function listInventory({ branchId, keyword = '', page = 1, size = 100, lowStock = false } = {}) {
  const params = new URLSearchParams({ page: String(page), size: String(size), lowStock: String(lowStock) });
  if (branchId) params.set('branchId', String(branchId));
  if (keyword) params.set('keyword', keyword);
  return apiRequest(`/inventory?${params}`);
}

export function listInventoryMovements(filters = {}) {
  const params = new URLSearchParams();
  for (const key of ['branchId', 'variantId', 'type', 'from', 'to', 'page', 'size']) {
    if (filters[key] !== undefined && filters[key] !== null && filters[key] !== '') params.set(key, String(filters[key]));
  }
  return apiRequest(`/inventory/movements?${params}`);
}

export function changeInventory(action, payload) {
  const endpoint = { import: '/inventory/import', export: '/inventory/export', stocktake: '/inventory/stocktake' }[action];
  if (!endpoint) throw new Error('Unsupported inventory action');
  return apiRequest(endpoint, { method: 'POST', body: JSON.stringify(payload) });
}

export function importInventoryCsv({ branchId, file, dryRun = false, signal }) {
  if (!Number.isSafeInteger(branchId) || branchId <= 0) {
    throw new Error('inventory.branchRequired');
  }
  const form = new FormData();
  form.append('file', file);
  const params = new URLSearchParams({ branchId: String(branchId), dryRun: String(dryRun) });
  return apiRequest(`/inventory/import-csv?${params}`, { method: 'POST', body: form, signal });
}
