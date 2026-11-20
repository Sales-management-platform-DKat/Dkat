// Mock records follow the response field names used by the store API.
export const mockProducts = [
  { product_id: 1, category_id: 2, product_code: 'TOP-001', name: 'Essential Tee', variants: [{ variant_id: 1, sku: 'TEE-BLK-M', variant_name: 'Size M - Color Black', price: 150000, status: 'ACTIVE', attributes: [] }] },
];

export const mockInventory = [
  { branchId: 1, branchName: 'Branch 1', productId: 1, productName: 'Essential Tee', variantId: 1, variantName: 'Size M - Color Black', sku: 'TEE-BLK-M', quantity: 20, reserved: 0, available: 20 },
  { branchId: 2, branchName: 'Branch 2', productId: 1, productName: 'Essential Tee', variantId: 1, variantName: 'Size M - Color Black', sku: 'TEE-BLK-M', quantity: 9, reserved: 0, available: 9 },
];

export const mockSalesOrders = [];
