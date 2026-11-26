import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { createDemoApi, DEMO_STORE_KEY } from '../src/demo/demo-api.js';
import { errorFromResponse, friendlyMessage } from '../src/lib/api-errors.js';
import { displayState } from '../src/features/customer-display/channel.js';
import { dismissToast, getToasts, pushToast } from '../src/components/overlay/toast.js';

globalThis.localStorage = {
  data: new Map(),
  getItem(key) { return this.data.get(key) ?? null; },
  setItem(key, value) { this.data.set(key, value); },
  removeItem(key) { this.data.delete(key); },
};
beforeEach(() => localStorage.data.clear());

const as = (role) => {
  const api = createDemoApi(role);
  return (path, method = 'GET', body) => api(path, { method, body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined });
};
const rejects = async (promise, status) => {
  await assert.rejects(promise, (error) => { assert.equal(error.status, status, error.message); return true; });
};
const csvFile = (text, name = 'nhap.csv') => { const form = new FormData(); form.append('file', new File([text], name, { type: 'text/csv' })); return form; };

// --- error handling -------------------------------------------------------
test('API errors never show raw server text, SQL or stack traces', () => {
  const server = errorFromResponse(500, { detail: 'Traceback ... pymysql.err.OperationalError SELECT * FROM users' });
  assert.equal(server.message, 'Máy chủ gặp sự cố. Vui lòng thử lại sau.');
  assert.equal(errorFromResponse(403, { detail: 'Bạn không có quyền thực hiện thao tác này.' }).message, 'Bạn không có quyền thực hiện thao tác này.');
  assert.equal(errorFromResponse(409, { detail: 'Product code already exists in this store' }).message, 'Mã sản phẩm đã tồn tại trong cửa hàng.');
  assert.equal(errorFromResponse(409, { detail: { code: 'INSUFFICIENT_STOCK', items: [] } }).message, 'Không đủ tồn kho khả dụng cho thao tác này.');
  assert.equal(friendlyMessage(new TypeError('Failed to fetch')), 'Không thể kết nối đến máy chủ. Kiểm tra mạng và thử lại.');
});

test('422 validation errors are mapped to fields', () => {
  const error = errorFromResponse(422, { detail: [
    { type: 'value_error', loc: ['body', 'branchCode'], msg: "Value error, Mã chi nhánh chỉ gồm chữ không dấu" },
    { type: 'missing', loc: ['body', 'name'], msg: 'Field required' },
  ] });
  assert.equal(error.fieldErrors.branchCode, 'Mã chi nhánh chỉ gồm chữ không dấu');
  assert.equal(error.fieldErrors.name, 'Vui lòng nhập thông tin này.');
  const preorder = errorFromResponse(422, { code: 'INVALID_PREORDER', message: 'Đơn đặt trước không hợp lệ', details: [{ field: 'customer.phone', reason: 'Số điện thoại không hợp lệ' }] });
  assert.equal(preorder.message, 'Đơn đặt trước không hợp lệ');
  assert.equal(preorder.fieldErrors.phone, 'Số điện thoại không hợp lệ');
});

test('the same toast is not stacked twice', () => {
  for (const item of getToasts()) dismissToast(item.id);
  const first = pushToast({ message: 'Không thể tạo chi nhánh.', kind: 'error' });
  const second = pushToast({ message: 'Không thể tạo chi nhánh.', kind: 'error' });
  assert.equal(first, second);
  assert.equal(getToasts().length, 1);
  assert.equal(getToasts()[0].repeat, 2);
  dismissToast(first);
});

// --- customer display ------------------------------------------------------
test('customer display payload computes totals, discount and change without sensitive data', () => {
  const state = displayState({
    status: 'paying', storeName: 'DKat', branchName: 'CN01', discount: 50000, tendered: '700000',
    items: [{ variantId: 1, name: 'Áo sơ mi', variantName: 'Trắng / M', price: 350000, quantity: 2, available: 9, sku: 'ASM' }],
  });
  assert.equal(state.subtotal, 700000);
  assert.equal(state.total, 650000);
  assert.equal(state.change, 50000);
  assert.equal(state.itemCount, 2);
  assert.deepEqual(Object.keys(state.items[0]).sort(), ['imageUrl', 'key', 'lineTotal', 'name', 'quantity', 'unitPrice', 'variantName']);
  assert.equal(displayState({ items: [{ variantId: 1, name: 'x', price: 10, quantity: 1 }], discount: 99 }).discount, 10);
  assert.equal(displayState({ items: [] }).status, 'idle');
});

// --- demo uses the real API contract and RBAC --------------------------------
test('demo: owner creates and edits a branch; duplicates and bad codes are rejected', async () => {
  const owner = as('OWNER');
  const created = await owner('/branches', 'POST', { name: 'DKat Đà Nẵng', address: '1 Bạch Đằng' });
  assert.match(created.branchCode, /^CN\d+$/);
  assert.ok(created.inventoryRowsCreated > 0);
  await rejects(owner('/branches', 'POST', { name: 'dkat đà nẵng', address: 'x' }), 409);
  await rejects(owner('/branches', 'POST', { name: 'Khác', address: 'x', branchCode: 'cn 9' }), 422);
  const updated = await owner(`/branches/${created.id}`, 'PUT', { name: 'DKat Đà Nẵng 2', address: '2 Bạch Đằng' });
  assert.equal(updated.branchCode, created.branchCode);
  assert.ok((await owner('/branches')).some((branch) => branch.name === 'DKat Đà Nẵng 2'));
});

test('demo: manager supervises but cannot manage accounts or branches', async () => {
  const manager = as('MANAGER');
  await rejects(manager('/branches', 'POST', { name: 'X', address: 'x' }), 403);
  await rejects(manager('/users', 'POST', { username: 'newstaff', full_name: 'A', password: 'password-12345', role: 'staff' }), 403);
  await rejects(manager('/users/3/status', 'PATCH', { status: 'LOCKED' }), 403);
  const staff = await manager('/users');
  assert.ok(staff.items.length > 0);
  assert.ok(staff.items.every((item) => item.role === 'employee'));
  assert.deepEqual((await manager('/branches')).map((branch) => branch.id), [1]);
  await rejects(manager('/inventory?branchId=2'), 403);
  const category = await manager('/categories', 'POST', { name: 'Giày' });
  const product = await manager('/products/full', 'POST', { name: 'Giày lười', categoryId: category.categoryId, variants: [{ variantName: 'Đen / 40', price: 500000, costPrice: 200000, initialQuantity: 3 }], stockBranchId: 1 });
  assert.equal(product.variants[0].cost_price, null);
  const stock = await manager(`/inventory?branchId=1&keyword=${encodeURIComponent('Giày lười')}`);
  assert.equal(stock[0].quantity, 3);
});

test('demo: employee sells but cannot change stock, products or accounts', async () => {
  const employee = as('EMPLOYEE');
  await rejects(employee('/inventory/import', 'POST', { branchId: 1, items: [{ variantId: 1, quantity: 1 }] }), 403);
  await rejects(employee('/products/full', 'POST', { name: 'X', categoryId: 1, variants: [{ variantName: 'x', price: 1 }] }), 403);
  await rejects(employee('/users'), 403);
  await rejects(employee('/reports/summary?branchId=1'), 403);
  const order = await employee('/sales-orders', 'POST', { branchId: 1, items: [{ variantId: 1, quantity: 1 }], discountAmount: 0 });
  const paid = await employee(`/sales-orders/${order.salesOrderId}/confirm-payment`, 'POST', { paymentMethod: 'CASH', amount: Number(order.totalAmount) });
  assert.equal(paid.status, 'PAID');
  const mine = await employee('/sales-orders?branchId=1');
  assert.ok(mine.length && mine.every((row) => row.createdBy === 3));
});

test('demo: pre-order only for out-of-stock items, FIFO allocation on import', async () => {
  const owner = as('OWNER');
  const out = (await owner('/inventory?branchId=1')).find((item) => item.available === 0);
  const inStock = (await owner('/inventory?branchId=1')).find((item) => item.available > 0);
  const customer = { fullName: 'Lê Văn B', phone: '0911222333', address: '3 Hai Bà Trưng' };
  await rejects(owner('/preorders', 'POST', { branchId: 1, customer, items: [{ variantId: inStock.variantId, quantity: 1 }] }), 409);
  await rejects(owner('/preorders', 'POST', { branchId: 1, customer: { ...customer, address: '' }, items: [{ variantId: out.variantId, quantity: 1 }] }), 422);
  const created = await owner('/preorders', 'POST', { branchId: 1, customer, items: [{ variantId: out.variantId, quantity: 2 }] });
  assert.match(created.preorderCode, /^PD-/);
  assert.equal(created.status, 'WAITING_STOCK');
  await owner('/inventory/import', 'POST', { branchId: 1, items: [{ variantId: out.variantId, quantity: 2 }] });
  const [ready] = await owner('/preorders?branchId=1');
  assert.equal(ready.status, 'READY');
  assert.equal(ready.items[0].allocatedQuantity, 2);
  assert.equal((await owner('/inventory?branchId=1')).find((item) => item.variantId === out.variantId).available, 0);
});

test('demo: CSV stock import validates rows, blocks invalid files and duplicate imports', async () => {
  const owner = as('OWNER');
  const [first] = await owner('/inventory?branchId=1');
  const bad = await owner('/inventory/import-csv?branchId=1&dryRun=true', 'POST', csvFile(`sku;so luong\n${first.sku};2\nNOPE;1\n${first.sku};-1\n`));
  assert.equal(bad.valid, false);
  assert.deepEqual(bad.errors.map((error) => error.code).sort(), ['INVALID_VALUE', 'SKU_NOT_FOUND']);
  await rejects(owner('/inventory/import-csv?branchId=1&dryRun=false', 'POST', csvFile(`sku,quantity\n${first.sku},2\nNOPE,1\n`)), 422);
  assert.equal((await owner('/inventory?branchId=1'))[0].quantity, first.quantity);
  const good = `sku,quantity,note\n${first.sku},4,Lô A\n`;
  const imported = await owner('/inventory/import-csv?branchId=1&dryRun=false', 'POST', csvFile(good));
  assert.equal(imported.items[0].quantityAfter, first.quantity + 4);
  const again = await owner('/inventory/import-csv?branchId=1&dryRun=true', 'POST', csvFile(good));
  assert.ok(again.duplicateOfImportAt);
  await rejects(owner('/inventory/import-csv?branchId=1&dryRun=false', 'POST', csvFile(good)), 409);
  await owner('/inventory/import-csv?branchId=1&dryRun=false&allowDuplicate=true', 'POST', csvFile(good));
  const movements = await owner('/inventory/movements?branchId=1');
  assert.equal(movements.filter((item) => item.referenceType === 'STOCK_FILE').length, 2);
});

test('demo data stays in the browser store', async () => {
  await as('OWNER')('/branches', 'POST', { name: 'Chỉ trên trình duyệt', address: 'x' });
  assert.ok(localStorage.getItem(DEMO_STORE_KEY).includes('Chỉ trên trình duyệt'));
});
