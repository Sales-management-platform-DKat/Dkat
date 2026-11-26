import { apiRequest } from '../../auth-client.js';

export function listProducts({ keyword = '', categoryId, status = 'ACTIVE', page = 1, size = 50, sort = 'name' } = {}) {
  const params = new URLSearchParams({ keyword, status, page: String(page), size: String(size), sort });
  if (categoryId) params.set('categoryId', String(categoryId));
  return apiRequest(`/products?${params}`);
}

export function getProduct(productId) {
  return apiRequest(`/products/${encodeURIComponent(productId)}`);
}

export function createProduct(payload) {
  return apiRequest('/products', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateProduct(productId, payload) {
  return apiRequest(`/products/${encodeURIComponent(productId)}`, { method: 'PUT', body: JSON.stringify(payload) });
}

export function uploadProductImage(file) {
  const form = new FormData();
  form.append('file', file);
  return apiRequest('/products/images', { method: 'POST', body: form });
}

export function deleteUnusedProductImage(imageUrl) {
  const filename = String(imageUrl || '').split('/').pop();
  if (!filename) return Promise.resolve();
  return apiRequest(`/products/images/${encodeURIComponent(filename)}`, { method: 'DELETE' });
}

export function setProductStatus(productId, status) {
  return apiRequest(`/products/${encodeURIComponent(productId)}/status`, { method: 'PATCH', body: JSON.stringify({ status }) });
}

export function createProductVariant(productId, payload) {
  return apiRequest(`/products/${encodeURIComponent(productId)}/variants`, { method: 'POST', body: JSON.stringify(payload) });
}

export function updateProductVariant(variantId, payload) {
  return apiRequest(`/variants/${encodeURIComponent(variantId)}`, { method: 'PUT', body: JSON.stringify(payload) });
}

export function setVariantStatus(variantId, status) {
  return apiRequest(`/variants/${encodeURIComponent(variantId)}/status`, { method: 'PATCH', body: JSON.stringify({ status }) });
}

export function createProductFull(payload) {
  return apiRequest('/products/full', { method: 'POST', body: JSON.stringify(payload) });
}

export function listAttributes() {
  return apiRequest('/attributes');
}

export function createAttribute(payload) {
  return apiRequest('/attributes', { method: 'POST', body: JSON.stringify(payload) });
}

// Returns {color, size} attribute ids, creating the TEXT attributes on first use.
export async function ensureVariantAttributes() {
  const wanted = { color: 'Màu sắc', size: 'Kích thước' };
  const existing = await listAttributes();
  const result = {};
  for (const [key, name] of Object.entries(wanted)) {
    let attribute = (existing || []).find((item) => item.name.trim().toLowerCase() === name.toLowerCase());
    if (!attribute) {
      try {
        attribute = await createAttribute({ name, dataType: 'TEXT' });
      } catch (error) {
        if (error.status !== 409) throw error;
        attribute = (await listAttributes()).find((item) => item.name.trim().toLowerCase() === name.toLowerCase());
      }
    }
    result[key] = attribute?.attributeId;
  }
  return result;
}
