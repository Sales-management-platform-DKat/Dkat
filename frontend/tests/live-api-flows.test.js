import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { mockApiRequest as api } from '../src/mocks/api.js';

globalThis.localStorage = {
  data: new Map(),
  getItem(key) { return this.data.get(key) ?? null; },
  setItem(key, value) { this.data.set(key, value); },
  removeItem(key) { this.data.delete(key); },
};

beforeEach(() => localStorage.data.clear());
const call = (path, options = {}) => api(path, options);
const login = async (username = 'owner') => call('/auth/login', { method: 'POST', body: JSON.stringify({ username, password: 'demo' }) });
const createOrder = async (token, overrides = {}) => call('/sales-orders', { method: 'POST', token, body: JSON.stringify({ branchId: 1, items: [{ variantId: 1, quantity: 1 }], discountAmount: 0, ...overrides }) });

test('Inventory import of five increases on-hand quantity by five', async () => {
  const { access_token: token } = await login();
  await call('/inventory/import', { method:'POST', token, body:JSON.stringify({branchId:1,items:[{variantId:1,quantity:5}]}) });
  assert.equal((await call('/inventory?branchId=1'))[0].quantity,25);
});

test('Inventory export rejects a quantity above available stock', async () => {
  const { access_token: token } = await login();
  await assert.rejects(call('/inventory/export',{method:'POST',token,body:JSON.stringify({branchId:1,reason:'KHAC',items:[{variantId:1,quantity:21}]})}),e=>e.code==='INSUFFICIENT_STOCK');
});

test('Stocktake adjusts quantity and records an adjustment movement', async () => {
  const { access_token: token } = await login();
  await call('/inventory/stocktake',{method:'POST',token,body:JSON.stringify({branchId:1,items:[{variantId:1,countedQuantity:17}],note:'cycle count'})});
  assert.equal((await call('/inventory?branchId=1'))[0].quantity,17);
  assert.equal((await call('/inventory/movements?branchId=1'))[0].movementType,'ADJUSTMENT');
});

test('POS searches products by exact SKU', async () => {
  await login();
  const rows = await call('/products?keyword=TEE-BLK-M');
  assert.equal(rows[0].variants[0].sku, 'TEE-BLK-M');
});

test('POS rejects quantities above available stock', async () => {
  const { access_token: token } = await login();
  await assert.rejects(createOrder(token, { items: [{ variantId: 1, quantity: 21 }] }), e => e.code === 'OUT_OF_STOCK');
});

test('POS calculates subtotal, discount, and total', async () => {
  const { access_token: token } = await login();
  const order = await createOrder(token, { items: [{ variantId: 1, quantity: 2 }], discountAmount: 10000 });
  assert.deepEqual([order.subtotal, order.discountAmount, order.totalAmount], [300000, 10000, 290000]);
});

test('POS rejects discount greater than subtotal', async () => {
  const { access_token: token } = await login();
  await assert.rejects(createOrder(token, { discountAmount: 150001 }), e => e.code === 'VALIDATION_ERROR');
});

test('Cash payment confirmation changes pending order to paid', async () => {
  const { access_token: token } = await login();
  const order = await createOrder(token);
  const paid = await call(`/sales-orders/${order.salesOrderId}/confirm-payment`, { method: 'POST', token, body: JSON.stringify({ paymentMethod: 'CASH', amountTendered: order.totalAmount + 50000 }) });
  assert.equal(paid.status, 'PAID');
  assert.equal((await call('/inventory?branchId=1'))[0].quantity, 19);
});

test('POS rejects a second payment confirmation', async () => {
  const { access_token: token } = await login();
  const order = await createOrder(token);
  await call(`/sales-orders/${order.salesOrderId}/confirm-payment`, { method: 'POST', token, body: JSON.stringify({ paymentMethod: 'CARD' }) });
  await assert.rejects(call(`/sales-orders/${order.salesOrderId}/confirm-payment`, { method: 'POST', token, body: JSON.stringify({ paymentMethod: 'CARD' }) }), e => e.code === 'CONFLICT');
});

test('Cancelling a pending order releases held stock', async () => {
  const { access_token: token } = await login();
  const order = await createOrder(token);
  await call(`/sales-orders/${order.salesOrderId}/cancel`, { method: 'POST', token });
  assert.equal((await call('/inventory?branchId=1'))[0].available, 20);
});

test('Manager cannot create an order in an unassigned branch', async () => {
  const { access_token: token } = await login('manager');
  await assert.rejects(createOrder(token, { branchId: 2 }), e => e.code === 'FORBIDDEN');
});

test('Employee cannot refund an order', async () => {
  const { access_token: ownerToken } = await login();
  const order = await createOrder(ownerToken);
  await call(`/sales-orders/${order.salesOrderId}/confirm-payment`, { method: 'POST', token: ownerToken, body: JSON.stringify({ paymentMethod: 'CARD' }) });
  const { access_token: employeeToken } = await login('staff');
  await assert.rejects(call(`/sales-orders/${order.salesOrderId}/refund`, { method: 'POST', token: employeeToken, body: JSON.stringify({ reason: 'Return' }) }), e => e.code === 'FORBIDDEN');
});

test('Guest order has no customer requirement', async () => {
  const { access_token: token } = await login();
  const order = await createOrder(token);
  assert.equal(order.customerId, null);
  assert.equal(order.status, 'PENDING');
});

test('Quick customer creation reuses a duplicate phone number', async () => {
  const { access_token: token } = await login();
  const first = await call('/customers',{method:'POST',token,body:JSON.stringify({fullName:'Lan Nguyen',phone:'0900000000'})});
  const second = await call('/customers',{method:'POST',token,body:JSON.stringify({fullName:'Another name',phone:'0900000000'})});
  assert.equal(second.customerId,first.customerId);
});

test('POS order links a selected customer', async () => {
  const { access_token: token } = await login();
  const customer = await call('/customers',{method:'POST',token,body:JSON.stringify({fullName:'Lan Nguyen'})});
  const order = await createOrder(token,{customerId:customer.customerId});
  assert.equal(order.customerName,'Lan Nguyen');
});

test('Order list filters by status and keyword', async () => {
  const { access_token: token } = await login();
  const order = await createOrder(token);
  const pending = await call('/sales-orders?status=PENDING&keyword=' + order.orderCode, { token });
  const paid = await call('/sales-orders?status=PAID', { token });
  assert.equal(pending.length, 1);
  assert.equal(paid.length, 0);
});

test('Order detail keeps item snapshots and guest label data', async () => {
  const { access_token: token } = await login();
  const order = await createOrder(token);
  const detail = await call(`/sales-orders/${order.salesOrderId}`, { token });
  assert.equal(detail.items[0].sku, 'TEE-BLK-M');
  assert.equal(detail.items[0].productName, 'Essential Tee');
});

test('Refund requires reason, restores stock, and marks payment refunded', async () => {
  const { access_token: token } = await login();
  const order = await createOrder(token);
  await call(`/sales-orders/${order.salesOrderId}/confirm-payment`, { method: 'POST', token, body: JSON.stringify({ paymentMethod: 'CARD' }) });
  const refunded = await call(`/sales-orders/${order.salesOrderId}/refund`, { method: 'POST', token, body: JSON.stringify({ reason: 'Customer return' }) });
  assert.equal(refunded.status, 'CANCELLED');
  assert.equal(refunded.payments[0].status, 'REFUNDED');
  assert.equal((await call('/inventory?branchId=1'))[0].quantity, 20);
});

test('Employee order list is restricted to assigned branch', async () => {
  const { access_token: ownerToken } = await login();
  await createOrder(ownerToken, { branchId: 1 });
  await createOrder(ownerToken, { branchId: 2 });
  const { access_token: employeeToken } = await login('staff');
  const rows = await call('/sales-orders', { token: employeeToken });
  assert.ok(rows.every(order => order.branchId === 1));
});
