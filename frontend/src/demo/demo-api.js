// In-browser demo backend. Demo mode sends every apiRequest() here (see
// setDemoApiHandler in auth-client.js), so the demo uses exactly the same screens,
// forms, dialogs and toasts as the real app. Data lives only in this browser
// (localStorage) and never reaches the server or the store database.
// Response shapes and permission rules mirror the FastAPI backend.

import { DEMO_ATTRIBUTES, DEMO_BRANCHES, DEMO_CATALOG, DEMO_CATEGORIES, DEMO_CUSTOMERS, DEMO_STORE_NAME, DEMO_USERS, demoDescription } from './demo-seed.js';

export const DEMO_STORE_KEY = 'dkat-demo-api-v2';
const ROLE_USERS = { OWNER: 1, MANAGER: 2, EMPLOYEE: 3 };
const OPEN_PREORDER = ['WAITING_STOCK', 'READY', 'NOTIFIED'];
// Bump when seed() changes shape, so browsers holding older demo data start again.
const DEMO_DATA_VERSION = 3;
const PREORDER_READY_DAYS = 7;

class DemoError extends Error {
  constructor(status, message, details = null, code = '') {
    super(message);
    this.status = status;
    this.details = details;
    this.code = code;
  }
}
const fail = (status, message, details, code) => { throw new DemoError(status, message, details, code); };
const now = () => new Date().toISOString();
const daysAgo = (days, hour = 10) => { const date = new Date(); date.setDate(date.getDate() - days); date.setHours(hour, 15, 0, 0); return date.toISOString(); };
const clone = (value) => (value === undefined ? null : structuredClone(value));
const fold = (value) => String(value ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/gi, 'd').toLowerCase();

function seed() {
  const s = {
    version: DEMO_DATA_VERSION,
    next: { branch: 3, user: 4, category: 4, product: 5, variant: 9, attribute: 3, movement: 1, order: 1, preorder: 1, customer: 3, payment: 1, notification: 1 },
    store: { id: 1, name: DEMO_STORE_NAME },
    branches: DEMO_BRANCHES.map(({ ageDays, ...branch }) => ({ ...branch, storeId: 1, status: 'ACTIVE', createdAt: daysAgo(ageDays) })),
    users: DEMO_USERS.map(({ ageDays, ...user }) => ({ ...user, status: 'ACTIVE', created_at: daysAgo(ageDays) })),
    categories: structuredClone(DEMO_CATEGORIES),
    attributes: [{ attributeId: 1, name: DEMO_ATTRIBUTES.color, dataType: 'TEXT', status: 'ACTIVE' }, { attributeId: 2, name: DEMO_ATTRIBUTES.size, dataType: 'TEXT', status: 'ACTIVE' }],
    products: [],
    inventory: [],
    movements: [],
    orders: [],
    preorders: [],
    notifications: [],
    customers: structuredClone(DEMO_CUSTOMERS),
  };
  const catalog = DEMO_CATALOG;
  let variantId = 1;
  for (const [productId, name, code, categoryId, variants] of catalog) {
    const product = { productId, productCode: `${code}-${String(productId).padStart(4, '0')}`, categoryId, name, description: demoDescription(name), imageUrl: null, status: 'ACTIVE', createdBy: 1, variants: [] };
    for (const [color, size, price, stock] of variants) {
      const id = variantId++;
      product.variants.push({ variant_id: id, sku: `${code}-${fold(color).replace(/\s+/g, '').toUpperCase()}-${size.toUpperCase()}`, variant_name: `${color} / ${size}`, price: String(price), cost_price: String(Math.round(price * 0.55)), barcode: null, status: 'ACTIVE', attributes: [{ attribute_id: 1, name: DEMO_ATTRIBUTES.color, data_type: 'TEXT', value: color }, { attribute_id: 2, name: DEMO_ATTRIBUTES.size, data_type: 'TEXT', value: size }] });
      s.inventory.push({ branchId: 1, variantId: id, quantity: stock, updatedAt: daysAgo(2) });
      s.inventory.push({ branchId: 2, variantId: id, quantity: Math.max(0, stock - 3), updatedAt: daysAgo(2) });
    }
    s.products.push(product);
  }
  // A little history so the dashboard and reports are not empty.
  [[6, 1, [[1, 2]], 1], [4, 1, [[4, 1], [6, 1]], 2], [2, 1, [[3, 1]], null], [1, 2, [[1, 1]], null], [0, 1, [[4, 2]], 1]].forEach(([days, branchId, lines, customerId]) => {
    const order = buildOrder(s, branchId, lines.map(([variant, quantity]) => ({ variantId: variant, quantity })), 0, customerId, 1, daysAgo(days, 9 + days));
    order.status = 'PAID';
    order.paidAt = order.createdAt;
    order.paymentMethods = ['CASH'];
    order.payments = [{ paymentId: s.next.payment++, paymentMethod: 'CASH', amount: order.totalAmount, status: 'SUCCESS', confirmedAt: order.paidAt }];
    s.orders.push(order);
  });
  seedPreorders(s);
  return s;
}

// A few pre-orders at branch 1 covering the main states, so the screen and the
// notification history are not empty: [days ago, customer, variant, qty, state].
function seedPreorders(s) {
  [[3, 1, 2, 1, 'WAITING_STOCK'], [2, 2, 3, 2, 'NOTIFIED'], [1, 1, 8, 1, 'READY'], [8, 1, 6, 1, 'FULFILLED']].forEach(([days, customerId, variantId, quantity, state]) => {
    const order = buildPreorder(s, s.branches[0], s.customers.find((item) => item.customerId === customerId), [{ variantId, quantity }], null, daysAgo(days, 9));
    if (state !== 'WAITING_STOCK') {
      order.items.forEach((line) => { line.allocatedQuantity = line.quantity; });
      order.readyAt = daysAgo(Math.max(days - 1, 0), 14);
      order.expiresAt = new Date(new Date(order.readyAt).getTime() + PREORDER_READY_DAYS * 86400000).toISOString();
      order.status = 'READY';
    }
    if (state === 'NOTIFIED') { recordReadyNotifications(s, order, { at: order.readyAt }); order.paymentStatus = 'PAID'; }
    // Seeded as "the provider was not reachable", so the resend flow can be tried.
    if (state === 'READY') recordReadyNotifications(s, order, { at: order.readyAt, failed: true });
    if (state === 'FULFILLED') {
      recordReadyNotifications(s, order, { at: order.readyAt });
      Object.assign(order, { status: 'FULFILLED', paymentStatus: 'PAID', fulfilledAt: daysAgo(days - 2, 16) });
    }
    s.preorders.push(order);
  });
}

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(DEMO_STORE_KEY));
    if (saved?.version === DEMO_DATA_VERSION && saved.next && saved.products) return saved;
  } catch { /* corrupt demo data: start again */ }
  return seed();
}
function save(s) {
  try { localStorage.setItem(DEMO_STORE_KEY, JSON.stringify(s)); }
  catch { fail(507, 'Bộ nhớ trình duyệt cho bản demo đã đầy. Hãy đặt lại dữ liệu demo.'); }
}
export function resetDemoData() { localStorage.removeItem(DEMO_STORE_KEY); }

// --- helpers ---------------------------------------------------------------
const variantsOf = (s) => s.products.flatMap((product) => product.variants.map((variant) => ({ product, variant })));
const findVariant = (s, id) => variantsOf(s).find((entry) => entry.variant.variant_id === Number(id));
const branchName = (s, id) => s.branches.find((branch) => branch.id === Number(id))?.name || '';
const userName = (s, id) => s.users.find((user) => user.id === id)?.full_name || null;

function stockRow(s, branchId, variantId, create = false) {
  let row = s.inventory.find((item) => item.branchId === Number(branchId) && item.variantId === Number(variantId));
  if (!row && create) { row = { branchId: Number(branchId), variantId: Number(variantId), quantity: 0, updatedAt: now() }; s.inventory.push(row); }
  return row;
}
function reserved(s, branchId, variantId) {
  const pre = s.preorders.filter((order) => order.branchId === branchId && OPEN_PREORDER.includes(order.status))
    .flatMap((order) => order.items).filter((item) => item.variantId === variantId).reduce((sum, item) => sum + item.allocatedQuantity, 0);
  const sales = s.orders.filter((order) => order.branchId === branchId && order.status === 'PENDING')
    .flatMap((order) => order.items).filter((item) => item.variantId === variantId).reduce((sum, item) => sum + item.quantity, 0);
  return pre + sales;
}
const available = (s, branchId, variantId) => (stockRow(s, branchId, variantId)?.quantity || 0) - reserved(s, branchId, variantId);

function accessibleBranches(s, actor) {
  return s.branches.filter((branch) => actor.role === 'OWNER' || actor.branchIds.includes(branch.id)).map((branch) => branch.id);
}
function requireBranch(s, actor, branchId) {
  if (!accessibleBranches(s, actor).includes(Number(branchId))) fail(403, 'Bạn không có quyền truy cập chi nhánh này.');
}
function requireRole(actor, ...roles) {
  if (!roles.includes(actor.role)) fail(403, 'Bạn không có quyền thực hiện thao tác này.');
}
function required(body, fields) {
  const details = fields.filter((field) => body[field] === undefined || body[field] === null || String(body[field]).trim() === '').map((field) => ({ field, reason: 'Vui lòng nhập thông tin này.' }));
  if (details.length) fail(422, 'Dữ liệu nhập không hợp lệ.', details);
}

function move(s, actor, branchId, variantId, delta, type, note, extra = {}) {
  const row = stockRow(s, branchId, variantId, true);
  const before = row.quantity;
  row.quantity += delta;
  row.updatedAt = now();
  const movementId = s.next.movement++;
  const { product, variant } = findVariant(s, variantId);
  s.movements.unshift({
    movementId, inventoryId: s.inventory.indexOf(row) + 1, branchId: Number(branchId), branchName: branchName(s, branchId),
    productId: product.productId, productName: product.name, variantId: Number(variantId), variantName: variant.variant_name, sku: variant.sku,
    movementType: type, quantityChange: delta, createdBy: actor.id, createdByName: userName(s, actor.id), note: note || null,
    referenceType: extra.referenceType || null, referenceId: extra.referenceId || null, exportReason: extra.reason || null, createdAt: now(),
  });
  return { variantId: Number(variantId), inventoryId: s.inventory.indexOf(row) + 1, movementId, quantityBefore: before, quantityChange: delta, quantityAfter: row.quantity };
}

// FIFO: stock received at a branch is allocated to the oldest waiting pre-orders.
function allocate(s, branchId, variantIds) {
  for (const order of s.preorders.filter((item) => item.branchId === branchId && item.status === 'WAITING_STOCK').sort((a, b) => a.createdAt.localeCompare(b.createdAt))) {
    for (const line of order.items) {
      if (!variantIds.includes(line.variantId) || line.allocatedQuantity >= line.quantity) continue;
      const free = available(s, branchId, line.variantId);
      if (free > 0) line.allocatedQuantity += Math.min(free, line.quantity - line.allocatedQuantity);
    }
    if (order.items.every((line) => line.allocatedQuantity >= line.quantity)) {
      order.status = 'READY'; order.readyAt = now();
      order.expiresAt = new Date(Date.now() + PREORDER_READY_DAYS * 86400000).toISOString();
      recordReadyNotifications(s, order);
    }
  }
}

function buildPreorder(s, branch, customer, lines, note, createdAt = now()) {
  const items = lines.map((line) => {
    const { product, variant } = findVariant(s, line.variantId);
    return { variantId: variant.variant_id, productName: product.name, sku: variant.sku, unitPrice: variant.price, quantity: line.quantity, allocatedQuantity: 0, lineTotal: String(Number(variant.price) * line.quantity) };
  });
  const id = s.next.preorder++;
  return {
    preorderId: id, preorderCode: `PD-DEMO-${String(id).padStart(5, '0')}`, branchId: branch.id, branchName: branch.name, customerId: customer.customerId,
    customer: { fullName: customer.fullName, phone: customer.phone, email: customer.email || null, address: customer.address },
    totalAmount: String(items.reduce((sum, item) => sum + Number(item.lineTotal), 0)), status: 'WAITING_STOCK', paymentStatus: 'UNPAID',
    note: note || null, createdAt, readyAt: null, expiresAt: null, fulfilledAt: null, cancelReason: null, cancelledAt: null, items,
  };
}

// "Goods have arrived" messages (FR-09). The demo never contacts an SMS/email
// provider: a delivery is recorded as simulated, which the message says.
const maskPhone = (phone) => (phone && phone.length > 6 ? `${phone.slice(0, 4)}***${phone.slice(-3)}` : phone);
const maskEmail = (email) => { const [name, domain] = String(email).split('@'); return domain ? `${name[0]}***@${domain}` : email; };
function recordReadyNotifications(s, order, { at = now(), failed = false } = {}) {
  s.notifications ||= [];
  s.next.notification ||= 1;
  const products = order.items.map((line) => `${line.productName} x${line.quantity}`).join(', ');
  const until = order.expiresAt ? new Date(order.expiresAt).toLocaleDateString('vi-VN') : '';
  const message = `DKat: Chào ${order.customer.fullName}, ${products} (đơn ${order.preorderCode}) đã có hàng tại ${order.branchName}. Mời bạn đến nhận trước ${until}.`;
  const channels = [['SMS', order.customer.phone], ['EMAIL', order.customer.email]].filter(([, recipient]) => recipient);
  for (const [channel, recipient] of channels) {
    s.notifications.push({
      id: s.next.notification++, preorderId: order.preorderId, branchId: order.branchId, eventType: 'PREORDER_READY', channel, recipient, message,
      status: failed ? 'FAILED' : 'SENT', retryCount: 0, providerMessageId: failed ? null : 'DEMO-SIMULATED',
      errorMessage: failed ? 'DEMO_PROVIDER_OFFLINE: simulated provider did not respond' : null,
      sentAt: failed ? null : at, lastAttemptAt: at, createdAt: at,
    });
  }
  if (!failed && channels.length && order.status === 'READY') order.status = 'NOTIFIED';
}
function notificationOut(item) {
  return { ...item, recipient: item.channel === 'SMS' ? maskPhone(item.recipient) : maskEmail(item.recipient), canResend: item.status === 'FAILED', branchId: undefined };
}

function buildOrder(s, branchId, lines, discount, customerId, actorId, createdAt = now()) {
  const items = lines.map((line) => {
    const { product, variant } = findVariant(s, line.variantId);
    return { variantId: variant.variant_id, productName: product.name, sku: variant.sku, unitPrice: String(variant.price), quantity: line.quantity, lineTotal: String(Number(variant.price) * line.quantity) };
  });
  const subtotal = items.reduce((sum, item) => sum + Number(item.lineTotal), 0);
  const customer = s.customers.find((item) => item.customerId === Number(customerId));
  const id = s.next.order++;
  return {
    salesOrderId: id, orderCode: `SO-${String(id).padStart(6, '0')}`, branchId: Number(branchId), branchName: branchName(s, branchId),
    customerId: customer?.customerId || null, customerName: customer?.fullName || null, createdBy: actorId, createdByName: userName(s, actorId),
    subtotal: String(subtotal), discountAmount: String(discount), totalAmount: String(subtotal - discount), status: 'PENDING', createdAt,
    paidAt: null, cancelledAt: null, cancelReason: null, paymentMethods: [], items, payments: [],
  };
}

function tree(categories, parent = null) {
  return categories.filter((category) => category.parentCategoryId === parent).sort((a, b) => a.name.localeCompare(b.name, 'vi'))
    .map((category) => ({ ...category, children: tree(categories, category.categoryId) }));
}

function employeeOut(s, user, visibleBranchIds = null) {
  return {
    id: user.id, store_id: 1, username: user.username, full_name: user.full_name, email: user.email, phone: user.phone,
    role: user.role.toLowerCase(), status: user.status, created_at: user.created_at,
    branches: s.branches.filter((branch) => user.branchIds.includes(branch.id) && (!visibleBranchIds || visibleBranchIds.includes(branch.id)))
      .map((branch) => ({ id: branch.id, branch_code: branch.branchCode, name: branch.name, status: branch.status })),
  };
}

function userInfo(s, user) {
  return { id: user.id, shop_id: 1, username: user.username, email: user.email, full_name: user.full_name, role: { OWNER: 'owner', MANAGER: 'manager', EMPLOYEE: 'staff' }[user.role], shop_name: s.store.name, plan: 'demo', subscription_expires_at: '2099-12-31T00:00:00Z' };
}

function inventoryItem(s, row) {
  const entry = findVariant(s, row.variantId);
  if (!entry || entry.variant.status !== 'ACTIVE' || entry.product.status !== 'ACTIVE') return null;
  const reservedQuantity = reserved(s, row.branchId, row.variantId);
  return { branchId: row.branchId, branchName: branchName(s, row.branchId), productId: entry.product.productId, productName: entry.product.name, variantId: row.variantId, variantName: entry.variant.variant_name, sku: entry.variant.sku, quantity: row.quantity, reserved: reservedQuantity, available: row.quantity - reservedQuantity, updatedAt: row.updatedAt };
}

function parseCsv(text) {
  const source = text.replace(/^﻿/, '');
  const firstLine = source.split(/\r?\n/, 1)[0] || '';
  const delimiter = [',', ';', '\t'].reduce((best, candidate) => (firstLine.split(candidate).length > firstLine.split(best).length ? candidate : best), ',');
  const rows = [];
  let row = [''];
  let quoted = false;
  for (let index = 0; index < source.length; index++) {
    const char = source[index];
    if (quoted) {
      if (char === '"' && source[index + 1] === '"') { row[row.length - 1] += '"'; index++; }
      else if (char === '"') quoted = false;
      else row[row.length - 1] += char;
    } else if (char === '"') quoted = true;
    else if (char === delimiter) row.push('');
    else if (char === '\n') { rows.push(row); row = ['']; }
    else if (char !== '\r') row[row.length - 1] += char;
  }
  if (row.length > 1 || row[0]) rows.push(row);
  return rows;
}

const HEADER_ALIASES = {
  sku: 'sku', 'ma sku': 'sku', 'ma hang': 'sku', quantity: 'quantity', 'so luong': 'quantity', qty: 'quantity', note: 'note', 'ghi chu': 'note',
  'product name': 'product_name', 'ten san pham': 'product_name', 'san pham': 'product_name', 'variant name': 'variant_name', 'ten bien the': 'variant_name',
  'bien the': 'variant_name', category: 'category', 'danh muc': 'category', price: 'price', 'gia ban': 'price', gia: 'price', 'don gia': 'price',
};
const DEFAULT_CATEGORY = 'Chưa phân loại';

async function readFileText(file) {
  if (typeof file?.text === 'function') return file.text();
  return String(file || '');
}

function parsePrice(raw) {
  let value = String(raw || '').replace(/[\s₫đ]/g, '');
  if (!value) return null;
  if (/^\d{1,3}(\.\d{3})+$/.test(value)) value = value.replaceAll('.', '');
  const price = Number(value);
  return Number.isFinite(price) && price >= 0 ? price : NaN;
}

// Creates the product/variant for a NEW SKU row (same rules as the backend).
function createVariantForImport(s, actor, row) {
  let category = s.categories.find((item) => fold(item.name).trim() === fold(row.category).trim());
  if (!category) {
    category = { categoryId: s.next.category++, parentCategoryId: null, name: row.category, description: null, status: 'ACTIVE' };
    s.categories.push(category);
  }
  let product = s.products.find((item) => item.status === 'ACTIVE' && fold(item.name) === fold(row.productName) && item.categoryId === category.categoryId);
  if (!product) {
    const productId = s.next.product++;
    const prefix = fold(category.name).replace(/[^a-z]/g, '').slice(0, 3).toUpperCase() || 'SP';
    product = { productId, productCode: `${prefix}-${String(productId).padStart(4, '0')}`, categoryId: category.categoryId, name: row.productName, description: null, imageUrl: null, status: 'ACTIVE', createdBy: actor.id, variants: [] };
    s.products.push(product);
  }
  const variant = { variant_id: s.next.variant++, sku: row.sku, variant_name: row.variantName, price: String(row.price), cost_price: null, barcode: null, status: 'ACTIVE', attributes: [] };
  product.variants.push(variant);
  for (const branch of s.branches.filter((item) => item.status === 'ACTIVE')) stockRow(s, branch.id, variant.variant_id, true);
  return { sku: variant.sku, productId: product.productId, variantId: variant.variant_id, productName: product.name, variantName: variant.variant_name, category: category.name, price: variant.price };
}

function quantityError(raw) {
  if (raw.startsWith('-')) return 'Số lượng không được âm';
  if (!raw) return 'Thiếu số lượng';
  if (Number(raw) === 0) return 'Số lượng phải lớn hơn 0';
  return 'Số lượng phải là số nguyên dương';
}

function demoStockImport(s, actor, branchId, text, dryRun, allowDuplicate) {
  const rows = parseCsv(text);
  const errors = [];
  const warnings = [];
  const header = (rows[0] || []).map((cell) => HEADER_ALIASES[fold(cell).replace(/[_-]/g, ' ').trim()] || null);
  const base = { dryRun, newSkus: 0, existingSkus: 0, warnings, fileType: 'csv', duplicateOfImportAt: null, created: [], items: [] };
  if (!header.includes('sku') || !header.includes('quantity')) {
    return { ...base, valid: false, totalRows: 0, validRows: 0, rows: [], errors: [{ line: 1, field: 'header', code: 'INVALID_HEADER', message: 'Dòng tiêu đề cần các cột: sku, quantity (tùy chọn: note, product_name, variant_name, category, price)' }] };
  }
  const canCreate = actor.role === 'OWNER' || actor.role === 'MANAGER';
  const valid = [];
  const seen = new Map();
  let total = 0;
  rows.slice(1).forEach((cells, index) => {
    if (!cells.some((cell) => cell.trim())) return;
    total++;
    const line = index + 2;
    const value = (name) => (header.includes(name) ? cells[header.indexOf(name)] || '' : '').trim();
    const sku = value('sku');
    const rawQuantity = value('quantity').replace(/\s/g, '');
    if (!sku) { errors.push({ line, field: 'sku', code: 'INVALID_VALUE', message: 'Thiếu SKU' }); return; }
    if (!/^\d+$/.test(rawQuantity) || Number(rawQuantity) < 1) { errors.push({ line, field: 'quantity', code: 'INVALID_VALUE', message: quantityError(rawQuantity) }); return; }
    const quantity = Number(rawQuantity);
    const note = value('note') || null;
    const key = sku.toLowerCase();
    const entry = variantsOf(s).find((item) => item.variant.sku.toLowerCase() === key);
    if (entry) {
      if (entry.variant.status !== 'ACTIVE' || entry.product.status !== 'ACTIVE') { errors.push({ line, field: 'sku', code: 'SKU_INACTIVE', message: `SKU "${entry.variant.sku}" đang ngừng kinh doanh` }); return; }
      if (seen.has(key)) warnings.push({ line, field: 'sku', code: 'DUPLICATE_SKU_ROW', message: `SKU "${entry.variant.sku}" đã có ở dòng ${seen.get(key).line}; số lượng sẽ được cộng dồn` });
      else seen.set(key, { line });
      valid.push({ line, status: 'EXISTING', variantId: entry.variant.variant_id, sku: entry.variant.sku, quantity, note, productName: entry.product.name, variantName: entry.variant.variant_name, quantityBefore: stockRow(s, branchId, entry.variant.variant_id)?.quantity || 0 });
      return;
    }
    if (!canCreate) { errors.push({ line, field: 'sku', code: 'SKU_NOT_FOUND', message: `SKU "${sku}" chưa có trong cửa hàng; chỉ chủ cửa hàng hoặc quản lý được tạo sản phẩm mới` }); return; }
    const productName = value('product_name');
    const price = parsePrice(value('price'));
    if (Number.isNaN(price)) { errors.push({ line, field: 'price', code: 'INVALID_VALUE', message: 'Giá bán phải là số' }); return; }
    const missing = [!productName && 'product_name', price === null && 'price'].filter(Boolean);
    if (missing.length) { errors.push({ line, field: 'sku', code: 'SKU_NOT_FOUND', message: `SKU "${sku}" chưa có trong cửa hàng. Điền cột ${missing.join(' và ')} để tạo sản phẩm mới` }); return; }
    const category = value('category') || DEFAULT_CATEGORY;
    const existingCategory = s.categories.find((item) => fold(item.name).trim() === fold(category).trim());
    if (existingCategory && existingCategory.status !== 'ACTIVE') { errors.push({ line, field: 'category', code: 'CATEGORY_INACTIVE', message: `Danh mục "${existingCategory.name}" đang ngừng hoạt động` }); return; }
    const candidate = { line, status: 'NEW', variantId: null, sku, quantity, note, productName, variantName: value('variant_name') || 'Mặc định', category: existingCategory?.name || category, price, quantityBefore: 0 };
    const first = seen.get(key);
    if (first) {
      if (fold(first.productName) !== fold(productName) || first.price !== price || fold(first.category) !== fold(candidate.category)) {
        errors.push({ line, field: 'sku', code: 'SKU_CONFLICT', message: `SKU "${sku}" ở dòng ${first.line} có tên, giá hoặc danh mục khác` });
        return;
      }
      warnings.push({ line, field: 'sku', code: 'DUPLICATE_SKU_ROW', message: `SKU "${sku}" đã có ở dòng ${first.line}; số lượng sẽ được cộng dồn` });
    } else seen.set(key, candidate);
    valid.push(candidate);
  });
  if (!total && !errors.length) errors.push({ line: 1, field: 'file', code: 'EMPTY_FILE', message: 'File không có dòng dữ liệu' });
  const totals = new Map();
  for (const row of valid) totals.set(row.sku.toLowerCase(), (totals.get(row.sku.toLowerCase()) || 0) + row.quantity);
  const fingerprint = `${branchId}|${[...totals].sort((a, b) => a[0].localeCompare(b[0])).map(([sku, qty]) => `${sku}:${qty}`).join(';')}`;
  const recent = s.movements.find((item) => item.referenceType === 'STOCK_FILE' && item.referenceId === fingerprint && Date.now() - new Date(item.createdAt).getTime() < 86400000);
  const newSkus = new Set(valid.filter((row) => row.status === 'NEW').map((row) => row.sku.toLowerCase())).size;
  const result = { ...base, valid: !errors.length, totalRows: total, validRows: valid.length, newSkus, existingSkus: totals.size - newSkus, rows: valid, errors, duplicateOfImportAt: recent?.createdAt || null };
  if (dryRun) return result;
  if (errors.length) fail(422, 'File nhập kho còn dòng lỗi.', null, 'INVALID_STOCK_CSV');
  if (recent && !allowDuplicate) fail(409, 'Dữ liệu này đã được nhập vào chi nhánh trong 24 giờ qua. Xác nhận lại nếu đây là lô hàng mới.', null, 'DUPLICATE_STOCK_IMPORT');
  const variantBySku = new Map(valid.filter((row) => row.status === 'EXISTING').map((row) => [row.sku.toLowerCase(), row.variantId]));
  for (const row of valid) {
    const key = row.sku.toLowerCase();
    if (row.status === 'NEW' && !variantBySku.has(key)) {
      const created = createVariantForImport(s, actor, row);
      result.created.push(created);
      variantBySku.set(key, created.variantId);
    }
    row.variantId = variantBySku.get(key);
  }
  result.items = [...totals].map(([key, quantity]) => {
    const lines = valid.filter((row) => row.sku.toLowerCase() === key);
    const note = lines.map((row) => row.note).filter(Boolean).join(' | ') || null;
    const label = lines[0].status === 'NEW' ? (note ? `SKU mới: ${note}` : 'SKU mới tạo khi nhập kho') : note;
    return move(s, actor, branchId, variantBySku.get(key), quantity, 'IMPORT', label, { referenceType: 'STOCK_FILE', referenceId: fingerprint });
  });
  allocate(s, Number(branchId), result.items.map((item) => item.variantId));
  return result;
}

function reportWindow(params) {
  const end = params.get('to') ? new Date(`${params.get('to')}T23:59:59`) : new Date();
  const start = params.get('from') ? new Date(`${params.get('from')}T00:00:00`) : new Date(end.getTime() - 29 * 86400000);
  start.setHours(0, 0, 0, 0);
  return [start, end];
}
function revenueEvents(s, actor, branchId) {
  const branches = branchId ? [Number(branchId)] : accessibleBranches(s, actor);
  return [
    ...s.orders.filter((order) => order.status === 'PAID' && branches.includes(order.branchId)).map((order) => ({ at: new Date(order.paidAt), amount: Number(order.totalAmount), items: order.items })),
    ...s.preorders.filter((order) => order.status === 'FULFILLED' && order.paymentStatus !== 'REFUNDED' && branches.includes(order.branchId)).map((order) => ({ at: new Date(order.fulfilledAt), amount: Number(order.totalAmount), items: order.items })),
  ];
}
const metric = (value, previous) => ({ value: Math.round(value * 100) / 100, previous: Math.round(previous * 100) / 100, change_percent: previous ? Math.round(((value - previous) / previous) * 1000) / 10 : null });

// --- router ----------------------------------------------------------------
export function createDemoApi(role = 'OWNER') {
  return async function demoApiRequest(path, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const url = new URL(path, 'http://demo.local');
    const route = url.pathname;
    const params = url.searchParams;
    const isForm = typeof FormData !== 'undefined' && options.body instanceof FormData;
    const body = !options.body || isForm ? {} : JSON.parse(options.body);
    const s = load();
    const actorUser = s.users.find((user) => user.id === ROLE_USERS[role]) || s.users[0];
    const actor = { id: actorUser.id, role: actorUser.role, branchIds: actorUser.branchIds };
    const commit = (value) => { save(s); return clone(value); };
    const m = (pattern) => route.match(pattern);
    let match;

    // Auth
    if (route === '/auth/me') return userInfo(s, actorUser);
    if (route === '/auth/logout') return null;

    // Branches
    if (route === '/branches' && method === 'GET') {
      const ids = accessibleBranches(s, actor);
      return clone(s.branches.filter((branch) => ids.includes(branch.id) && (!params.get('status') || branch.status === params.get('status'))).sort((a, b) => a.branchCode.localeCompare(b.branchCode)));
    }
    if ((match = m(/^\/branches\/(\d+)$/)) && method === 'GET') { requireBranch(s, actor, match[1]); return clone(s.branches.find((branch) => branch.id === Number(match[1]))); }
    if ((route === '/branches' && method === 'POST') || ((match = m(/^\/branches\/(\d+)$/)) && method === 'PUT')) {
      requireRole(actor, 'OWNER');
      required(body, ['name', 'address']);
      const id = match ? Number(match[1]) : null;
      const current = id && s.branches.find((branch) => branch.id === id);
      if (id && !current) fail(404, 'Không tìm thấy chi nhánh');
      const code = String(body.branchCode || body.branch_code || '').trim().toUpperCase() || current?.branchCode || (() => { let n = s.branches.length + 1; while (s.branches.some((branch) => branch.branchCode === `CN${String(n).padStart(2, '0')}`)) n++; return `CN${String(n).padStart(2, '0')}`; })();
      if (!/^[A-Z0-9][A-Z0-9_-]*$/.test(code)) fail(422, 'Dữ liệu nhập không hợp lệ.', [{ field: 'branchCode', reason: "Mã chi nhánh chỉ gồm chữ không dấu, số, '-' hoặc '_' và không có khoảng trắng" }]);
      if (s.branches.some((branch) => branch.id !== id && branch.branchCode === code)) fail(409, 'Mã chi nhánh đã tồn tại trong cửa hàng');
      if (s.branches.some((branch) => branch.id !== id && fold(branch.name).trim() === fold(body.name).trim())) fail(409, 'Tên chi nhánh đã tồn tại trong cửa hàng');
      const values = { branchCode: code, name: body.name.trim(), address: body.address.trim(), phone: body.phone?.trim() || null };
      if (current) { Object.assign(current, values); return commit(current); }
      const branch = { id: s.next.branch++, storeId: 1, ...values, status: 'ACTIVE', createdAt: now() };
      s.branches.push(branch);
      let created = 0;
      for (const { variant } of variantsOf(s)) if (variant.status === 'ACTIVE') { stockRow(s, branch.id, variant.variant_id, true); created++; }
      return commit({ ...branch, inventoryRowsCreated: created });
    }
    if ((match = m(/^\/branches\/(\d+)\/status$/)) && method === 'PATCH') {
      requireRole(actor, 'OWNER');
      const branch = s.branches.find((item) => item.id === Number(match[1])) || fail(404, 'Không tìm thấy chi nhánh');
      if (body.status === 'INACTIVE' && s.preorders.some((order) => order.branchId === branch.id && OPEN_PREORDER.includes(order.status))) fail(409, 'Không thể ngừng hoạt động khi chi nhánh còn đơn đặt trước đang xử lý');
      branch.status = body.status;
      return commit(branch);
    }

    // Users / employees
    if (route === '/users' && method === 'GET') {
      requireRole(actor, 'OWNER', 'MANAGER');
      const branchFilter = Number(params.get('branchId')) || null;
      if (branchFilter && actor.role === 'MANAGER' && !actor.branchIds.includes(branchFilter)) fail(403, 'Bạn không có quyền truy cập chi nhánh này.');
      const q = fold(params.get('q') || '');
      const items = s.users.filter((user) => user.role !== 'OWNER'
        && (actor.role === 'OWNER' || (user.role === 'EMPLOYEE' && user.branchIds.some((id) => actor.branchIds.includes(id))))
        && (!branchFilter || user.branchIds.includes(branchFilter))
        && (!q || [user.full_name, user.username, user.email, user.phone].some((value) => fold(value).includes(q))))
        .map((user) => employeeOut(s, user, actor.role === 'OWNER' ? null : actor.branchIds));
      return clone({ items, page: 1, page_size: items.length, total: items.length, total_pages: 1 });
    }
    if (route === '/users' && method === 'POST') {
      requireRole(actor, 'OWNER');
      required(body, ['username', 'full_name', 'password']);
      const username = String(body.username).trim().toLowerCase();
      if (!/^[a-z0-9._-]{3,32}$/.test(username)) fail(422, 'Dữ liệu nhập không hợp lệ.', [{ field: 'username', reason: '3–32 ký tự: chữ không dấu, số, ".", "_" hoặc "-".' }]);
      if (String(body.password).length < 12) fail(422, 'Dữ liệu nhập không hợp lệ.', [{ field: 'password', reason: 'Mật khẩu cần ít nhất 12 ký tự.' }]);
      if (s.users.some((user) => user.username === username)) fail(409, 'Tên đăng nhập này đã được sử dụng.');
      const user = { id: s.next.user++, username, full_name: body.full_name.trim(), email: body.email || null, phone: body.phone || null, role: body.role === 'manager' ? 'MANAGER' : 'EMPLOYEE', status: 'ACTIVE', created_at: now(), branchIds: (body.branch_ids || []).map(Number) };
      s.users.push(user);
      return commit(userInfo(s, user));
    }
    if ((match = m(/^\/users\/(\d+)(?:\/(status|branches|reset-password))?$/))) {
      requireRole(actor, 'OWNER');
      const user = s.users.find((item) => item.id === Number(match[1]) && item.role !== 'OWNER') || fail(404, 'Không tìm thấy tài khoản nhân viên.');
      if (!match[2] && method === 'PUT') { required(body, ['full_name']); Object.assign(user, { full_name: body.full_name.trim(), email: body.email || null, phone: body.phone || null }); }
      else if (match[2] === 'status') user.status = body.status;
      else if (match[2] === 'branches') user.branchIds = (body.branch_ids || []).map(Number);
      else if (match[2] === 'reset-password') { save(s); return null; }
      return commit(employeeOut(s, user));
    }

    // Categories & attributes
    if (route === '/categories' && method === 'GET') {
      const status = params.get('status');
      return clone(tree(s.categories.filter((category) => !status || category.status === status)));
    }
    if ((route === '/categories' && method === 'POST') || ((match = m(/^\/categories\/(\d+)$/)) && method === 'PUT')) {
      requireRole(actor, 'OWNER', 'MANAGER');
      required(body, ['name']);
      const id = match ? Number(match[1]) : null;
      const parent = body.parentCategoryId ? Number(body.parentCategoryId) : null;
      if (parent && !s.categories.some((category) => category.categoryId === parent)) fail(404, 'Không tìm thấy danh mục.');
      let cursor = parent;
      while (cursor) { if (cursor === id) fail(409, 'Không thể chọn danh mục con làm danh mục cha.'); cursor = s.categories.find((category) => category.categoryId === cursor)?.parentCategoryId; }
      if (s.categories.some((category) => category.categoryId !== id && category.parentCategoryId === parent && fold(category.name) === fold(body.name.trim()))) fail(409, 'Danh mục đã tồn tại.');
      const values = { name: body.name.trim(), parentCategoryId: parent, description: body.description || null };
      if (id) { const category = s.categories.find((item) => item.categoryId === id) || fail(404, 'Không tìm thấy danh mục.'); Object.assign(category, values); return commit(category); }
      const category = { categoryId: s.next.category++, ...values, status: 'ACTIVE' };
      s.categories.push(category);
      return commit(category);
    }
    if ((match = m(/^\/categories\/(\d+)\/status$/)) && method === 'PATCH') {
      requireRole(actor, 'OWNER');
      const category = s.categories.find((item) => item.categoryId === Number(match[1])) || fail(404, 'Không tìm thấy danh mục.');
      category.status = body.status;
      return commit(category);
    }
    if (route === '/attributes' && method === 'GET') return clone(s.attributes);
    if (route === '/attributes' && method === 'POST') {
      requireRole(actor, 'OWNER', 'MANAGER');
      if (s.attributes.some((item) => fold(item.name) === fold(body.name))) fail(409, 'Thuộc tính đã tồn tại.');
      const attribute = { attributeId: s.next.attribute++, name: body.name.trim(), dataType: body.dataType, status: 'ACTIVE' };
      s.attributes.push(attribute);
      return commit(attribute);
    }

    // Products & variants
    if (route === '/products' && method === 'GET') {
      const keyword = fold(params.get('keyword') || '');
      const status = params.get('status') || 'ACTIVE';
      const categoryId = Number(params.get('categoryId')) || null;
      return clone(s.products.filter((product) => product.status === status && (!categoryId || product.categoryId === categoryId)
        && (!keyword || [product.name, product.productCode, ...product.variants.map((variant) => variant.sku)].some((value) => fold(value).includes(keyword))))
        .sort((a, b) => a.name.localeCompare(b.name, 'vi'))
        .map((product) => ({ product_id: product.productId, category_id: product.categoryId, product_code: product.productCode, name: product.name, image_url: product.imageUrl, variants: product.variants.filter((variant) => variant.status === 'ACTIVE').map(({ variant_id, sku, variant_name, price }) => ({ variant_id, sku, variant_name, price })) })));
    }
    if (route === '/products/images' && method === 'POST') {
      requireRole(actor, 'OWNER', 'MANAGER');
      const file = options.body.get('file');
      if (!file || file.size > 700 * 1024) fail(413, 'Ảnh trong bản demo tối đa 700 KB (bản chính thức hỗ trợ 5 MB).');
      const dataUrl = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
      return { imageUrl: dataUrl, contentType: file.type, size: file.size };
    }
    if (m(/^\/products\/images\//) && method === 'DELETE') return null;
    if (route === '/products/full' && method === 'POST') {
      requireRole(actor, 'OWNER', 'MANAGER');
      required(body, ['name', 'categoryId']);
      const category = s.categories.find((item) => item.categoryId === Number(body.categoryId)) || fail(404, 'Không tìm thấy danh mục.');
      if (category.status !== 'ACTIVE') fail(409, 'Danh mục đang ngừng hoạt động.');
      const productId = s.next.product++;
      const code = body.productCode?.trim() || `${fold(category.name).slice(0, 3).toUpperCase()}-${String(productId).padStart(4, '0')}`;
      if (s.products.some((product) => product.productCode.toLowerCase() === code.toLowerCase())) fail(409, 'Mã sản phẩm đã tồn tại trong cửa hàng.');
      const variants = (body.variants || []).map((input, index) => {
        const sku = (input.sku?.trim() || `${code}-${index + 1}`).toUpperCase();
        if (variantsOf(s).some((entry) => entry.variant.sku.toLowerCase() === sku.toLowerCase())) fail(409, 'SKU đã tồn tại trong cửa hàng.', null, 'DUPLICATE_SKU');
        return { variant_id: s.next.variant++, sku, variant_name: input.variantName, price: String(input.price), cost_price: actor.role === 'OWNER' && input.costPrice != null ? String(input.costPrice) : null, barcode: input.barcode || null, status: 'ACTIVE', attributes: (input.attributes || []).map((attribute) => ({ attribute_id: attribute.attributeId, name: s.attributes.find((item) => item.attributeId === attribute.attributeId)?.name, data_type: 'TEXT', value: String(attribute.value) })), initialQuantity: input.initialQuantity || 0 };
      });
      if (!variants.length) fail(422, 'Cần ít nhất một biến thể.');
      if (variants.some((variant) => variant.initialQuantity) ) requireBranch(s, actor, body.stockBranchId);
      const product = { productId, productCode: code, categoryId: category.categoryId, name: body.name.trim(), description: body.description || null, imageUrl: body.imageUrl || null, status: 'ACTIVE', createdBy: actor.id, variants: variants.map(({ initialQuantity, ...variant }) => variant) };
      s.products.push(product);
      for (const branch of s.branches.filter((item) => item.status === 'ACTIVE')) for (const variant of product.variants) stockRow(s, branch.id, variant.variant_id, true);
      for (const variant of variants) if (variant.initialQuantity) move(s, actor, body.stockBranchId, variant.variant_id, variant.initialQuantity, 'IMPORT', 'Tồn đầu kỳ khi tạo sản phẩm');
      const out = clone(product);
      if (actor.role !== 'OWNER') out.variants.forEach((variant) => { variant.cost_price = null; });
      save(s);
      return out;
    }
    if ((match = m(/^\/products\/(\d+)(?:\/(status|variants))?$/))) {
      const product = s.products.find((item) => item.productId === Number(match[1])) || fail(404, 'Không tìm thấy sản phẩm.');
      if (method === 'GET') { const out = clone(product); if (actor.role !== 'OWNER') out.variants.forEach((variant) => { variant.cost_price = null; }); return out; }
      if (!match[2] && method === 'PUT') { requireRole(actor, 'OWNER', 'MANAGER'); required(body, ['name', 'categoryId']); Object.assign(product, { name: body.name.trim(), categoryId: Number(body.categoryId), description: body.description || null, imageUrl: body.imageUrl || null }); return commit(product); }
      if (match[2] === 'status') { requireRole(actor, 'OWNER'); product.status = body.status; return commit(product); }
      if (match[2] === 'variants' && method === 'POST') {
        requireRole(actor, 'OWNER', 'MANAGER');
        const sku = (body.sku?.trim() || `${product.productCode}-${product.variants.length + 1}`).toUpperCase();
        if (variantsOf(s).some((entry) => entry.variant.sku.toLowerCase() === sku.toLowerCase())) fail(409, 'SKU đã tồn tại trong cửa hàng.', null, 'DUPLICATE_SKU');
        const variant = { variant_id: s.next.variant++, sku, variant_name: body.variantName, price: String(body.price), cost_price: actor.role === 'OWNER' && body.costPrice != null ? String(body.costPrice) : null, barcode: body.barcode || null, status: 'ACTIVE', attributes: [] };
        product.variants.push(variant);
        for (const branch of s.branches.filter((item) => item.status === 'ACTIVE')) stockRow(s, branch.id, variant.variant_id, true);
        return commit(variant);
      }
    }
    if ((match = m(/^\/variants\/(\d+)(?:\/(status))?$/))) {
      const entry = findVariant(s, match[1]) || fail(404, 'Không tìm thấy biến thể sản phẩm.');
      if (match[2]) { requireRole(actor, 'OWNER'); entry.variant.status = body.status; return commit(entry.variant); }
      requireRole(actor, 'OWNER', 'MANAGER');
      const sku = body.sku?.trim().toUpperCase() || entry.variant.sku;
      if (variantsOf(s).some((item) => item.variant.variant_id !== entry.variant.variant_id && item.variant.sku.toLowerCase() === sku.toLowerCase())) fail(409, 'SKU đã tồn tại trong cửa hàng.', null, 'DUPLICATE_SKU');
      Object.assign(entry.variant, { sku, variant_name: body.variantName, price: String(body.price), barcode: body.barcode || null, cost_price: actor.role === 'OWNER' ? (body.costPrice != null ? String(body.costPrice) : null) : entry.variant.cost_price });
      const out = commit(entry.variant);
      if (actor.role !== 'OWNER') out.cost_price = null;
      return out;
    }

    // Inventory
    if (route === '/inventory' && method === 'GET') {
      const branchId = Number(params.get('branchId')) || null;
      if (branchId) requireBranch(s, actor, branchId);
      const ids = branchId ? [branchId] : accessibleBranches(s, actor);
      const keyword = fold(params.get('keyword') || '');
      return clone(s.inventory.filter((row) => ids.includes(row.branchId)).map((row) => inventoryItem(s, row)).filter(Boolean)
        .filter((item) => !keyword || [item.sku, item.productName, item.variantName].some((value) => fold(value).includes(keyword)))
        .sort((a, b) => a.productName.localeCompare(b.productName, 'vi') || a.sku.localeCompare(b.sku)));
    }
    if (route === '/inventory/movements' && method === 'GET') {
      const branchId = Number(params.get('branchId')) || null;
      if (branchId) requireBranch(s, actor, branchId);
      const ids = branchId ? [branchId] : accessibleBranches(s, actor);
      const variantId = Number(params.get('variantId')) || null;
      return clone(s.movements.filter((item) => ids.includes(item.branchId) && (!variantId || item.variantId === variantId) && (!params.get('type') || item.movementType === params.get('type'))).slice(0, Number(params.get('size') || 50)));
    }
    if (['/inventory/import', '/inventory/export', '/inventory/stocktake'].includes(route) && method === 'POST') {
      requireRole(actor, 'OWNER', 'MANAGER');
      requireBranch(s, actor, body.branchId);
      const branchId = Number(body.branchId);
      const kind = route.split('/').pop();
      for (const item of body.items || []) {
        findVariant(s, item.variantId) || fail(404, 'Không tìm thấy biến thể sản phẩm.', null, 'VARIANT_NOT_FOUND');
        if (kind === 'export' && item.quantity > available(s, branchId, item.variantId)) fail(409, 'Không đủ tồn kho khả dụng cho thao tác này.', null, 'INSUFFICIENT_STOCK');
        if (kind === 'stocktake' && item.countedQuantity < reserved(s, branchId, item.variantId)) fail(409, 'Số lượng kiểm kê thấp hơn số lượng đang giữ cho đơn đặt trước.', null, 'STOCK_BELOW_RESERVED');
      }
      const items = (body.items || []).map((item) => {
        const before = stockRow(s, branchId, item.variantId, true).quantity;
        const delta = kind === 'import' ? item.quantity : kind === 'export' ? -item.quantity : item.countedQuantity - before;
        return delta ? move(s, actor, branchId, item.variantId, delta, kind === 'stocktake' ? 'ADJUSTMENT' : kind.toUpperCase(), body.note, { reason: body.reason }) : { variantId: item.variantId, inventoryId: 0, movementId: null, quantityBefore: before, quantityChange: 0, quantityAfter: before };
      });
      if (kind === 'import') allocate(s, branchId, items.map((item) => item.variantId));
      return commit({ branchId, movementType: kind === 'stocktake' ? 'ADJUSTMENT' : kind.toUpperCase(), reason: body.reason || null, items });
    }
    if (route === '/inventory/import-csv' && method === 'POST') {
      requireRole(actor, 'OWNER', 'MANAGER');
      const branchId = Number(params.get('branchId'));
      requireBranch(s, actor, branchId);
      const file = options.body.get('file');
      if (/\.xlsx?$/i.test(file?.name || '')) fail(422, 'Bản demo chỉ đọc file CSV trong trình duyệt. File Excel (.xlsx) được hỗ trợ ở bản chính thức.');
      const result = demoStockImport(s, actor, branchId, await readFileText(file), params.get('dryRun') !== 'false', params.get('allowDuplicate') === 'true');
      if (!result.dryRun) save(s);
      return clone(result);
    }

    // Sales orders
    if (route === '/sales-orders' && method === 'GET') {
      const branchId = Number(params.get('branchId')) || null;
      if (branchId) requireBranch(s, actor, branchId);
      const ids = branchId ? [branchId] : accessibleBranches(s, actor);
      const keyword = fold(params.get('keyword') || '');
      return clone(s.orders.filter((order) => ids.includes(order.branchId) && (actor.role !== 'EMPLOYEE' || order.createdBy === actor.id)
        && (!params.get('status') || order.status === params.get('status')) && (!keyword || fold(order.orderCode + order.customerName).includes(keyword)))
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, Number(params.get('size') || 50)));
    }
    if (route === '/sales-orders' && method === 'POST') {
      requireBranch(s, actor, body.branchId);
      const branch = s.branches.find((item) => item.id === Number(body.branchId));
      if (branch?.status !== 'ACTIVE') fail(409, 'Chi nhánh đang ngừng hoạt động.');
      if (!body.items?.length) fail(422, 'Giỏ hàng trống.');
      for (const line of body.items) if (line.quantity > available(s, branch.id, line.variantId)) fail(409, 'Sản phẩm không đủ hàng tại chi nhánh.', null, 'OUT_OF_STOCK');
      const subtotal = body.items.reduce((sum, line) => sum + Number(findVariant(s, line.variantId).variant.price) * line.quantity, 0);
      if (Number(body.discountAmount || 0) > subtotal) fail(422, 'Chiết khấu không được lớn hơn tạm tính.');
      const order = buildOrder(s, branch.id, body.items, Number(body.discountAmount || 0), body.customerId, actor.id);
      s.orders.push(order);
      return commit(order);
    }
    if ((match = m(/^\/sales-orders\/(\d+)(?:\/(confirm-payment|cancel|refund))?$/))) {
      const order = s.orders.find((item) => item.salesOrderId === Number(match[1])) || fail(404, 'Không tìm thấy đơn hàng.');
      requireBranch(s, actor, order.branchId);
      if (method === 'GET') return clone(order);
      if (match[2] === 'confirm-payment') {
        if (order.status !== 'PENDING') fail(409, 'Đơn hàng không còn ở trạng thái chờ thanh toán.', null, 'ORDER_NOT_PENDING');
        order.status = 'PAID'; order.paidAt = now(); order.paymentMethods = [body.paymentMethod];
        order.payments = [{ paymentId: s.next.payment++, paymentMethod: body.paymentMethod, amount: order.totalAmount, status: 'SUCCESS', confirmedAt: order.paidAt }];
        for (const line of order.items) move(s, actor, order.branchId, line.variantId, -line.quantity, 'SALE', `Bán hàng ${order.orderCode}`, { referenceType: 'SALES_ORDER', referenceId: order.salesOrderId });
        return commit(order);
      }
      if (match[2] === 'cancel') {
        if (order.status !== 'PENDING') fail(409, 'Đơn hàng không còn ở trạng thái chờ thanh toán.', null, 'ORDER_NOT_PENDING');
        Object.assign(order, { status: 'CANCELLED', cancelledAt: now(), cancelReason: body.reason });
        return commit(order);
      }
      if (match[2] === 'refund') {
        requireRole(actor, 'OWNER', 'MANAGER');
        if (order.status !== 'PAID') fail(409, 'Chỉ hoàn tiền đơn đã thanh toán.');
        Object.assign(order, { status: 'REFUNDED', cancelReason: body.reason });
        order.payments.forEach((payment) => { payment.status = 'REFUNDED'; });
        for (const line of order.items) move(s, actor, order.branchId, line.variantId, line.quantity, 'ADJUSTMENT', `Hoàn tiền ${order.orderCode}: ${body.reason}`);
        return commit(order);
      }
    }

    // Pre-orders
    if (route === '/preorders' && method === 'POST') {
      const details = [];
      for (const field of ['fullName', 'phone', 'address']) if (!String(body.customer?.[field] || '').trim()) details.push({ field: `customer.${field}`, reason: 'Vui lòng nhập thông tin này.' });
      if (details.length) fail(422, 'Đơn đặt trước không hợp lệ', details, 'INVALID_PREORDER');
      const branch = s.branches.find((item) => item.id === Number(body.branchId) && item.status === 'ACTIVE') || fail(404, 'Không tìm thấy chi nhánh đang hoạt động', null, 'BRANCH_NOT_FOUND');
      const items = (body.items || []).map((line) => {
        if (!findVariant(s, line.variantId)) fail(404, 'Không tìm thấy biến thể trong cửa hàng', null, 'VARIANT_NOT_FOUND');
        if (available(s, branch.id, line.variantId) >= line.quantity) fail(409, 'Hàng còn đủ; vui lòng mua trực tiếp tại cửa hàng', null, 'VARIANT_IN_STOCK');
        return { variantId: Number(line.variantId), quantity: line.quantity };
      });
      let customer = s.customers.find((item) => item.phone === body.customer.phone.trim());
      if (!customer) { customer = { customerId: s.next.customer++, fullName: body.customer.fullName.trim(), phone: body.customer.phone.trim(), email: body.customer.email || null, address: body.customer.address.trim(), note: null }; s.customers.push(customer); }
      // The order keeps what the customer typed (a snapshot), like the backend.
      const snapshot = { ...customer, fullName: body.customer.fullName.trim(), phone: body.customer.phone.trim(), email: body.customer.email || null, address: body.customer.address.trim() };
      const order = buildPreorder(s, branch, snapshot, items, body.note);
      s.preorders.push(order);
      return commit(order);
    }
    if (route === '/preorders' && method === 'GET') {
      const branchId = Number(params.get('branchId')) || null;
      if (branchId) requireBranch(s, actor, branchId);
      const ids = branchId ? [branchId] : accessibleBranches(s, actor);
      const keyword = fold(params.get('keyword') || '');
      return clone(s.preorders.filter((order) => ids.includes(order.branchId) && (!params.get('status') || order.status === params.get('status'))
        && (!keyword || fold(`${order.preorderCode} ${order.customer.fullName} ${order.customer.phone}`).includes(keyword))).sort((a, b) => b.createdAt.localeCompare(a.createdAt)));
    }
    if ((match = m(/^\/preorders\/(\d+)$/)) && method === 'GET') {
      const order = s.preorders.find((item) => item.preorderId === Number(match[1])) || fail(404, 'Không tìm thấy đơn đặt trước.', null, 'PREORDER_NOT_FOUND');
      requireBranch(s, actor, order.branchId);
      const notifications = (s.notifications || []).filter((item) => item.preorderId === order.preorderId).reverse()
        .map((item) => ({ notificationId: item.id, channel: item.channel, recipient: notificationOut(item).recipient, message: item.message, status: item.status, providerMessageId: item.providerMessageId, errorMessage: item.errorMessage, sentAt: item.sentAt, createdAt: item.createdAt }));
      return clone({ ...order, payments: [], fulfillment: null, notifications });
    }
    if ((match = m(/^\/preorders\/(\d+)\/notifications$/)) && method === 'GET') {
      const order = s.preorders.find((item) => item.preorderId === Number(match[1])) || fail(404, 'Không tìm thấy đơn đặt trước.', null, 'PREORDER_NOT_FOUND');
      requireBranch(s, actor, order.branchId);
      return clone({ preorderId: order.preorderId, preorderCode: order.preorderCode, maxAutoRetries: 3,
        items: (s.notifications || []).filter((item) => item.preorderId === order.preorderId).map(notificationOut) });
    }
    if ((match = m(/^\/notifications\/(\d+)\/resend$/)) && method === 'POST') {
      const item = (s.notifications || []).find((entry) => entry.id === Number(match[1])) || fail(404, 'Không tìm thấy thông báo.', null, 'NOTIFICATION_NOT_FOUND');
      requireBranch(s, actor, item.branchId);
      if (item.status !== 'FAILED') fail(409, 'Thông báo đang được gửi lại hoặc đã gửi thành công.', null, 'NOTIFICATION_NOT_FAILED');
      const at = now();
      Object.assign(item, { status: 'SENT', retryCount: item.retryCount + 1, providerMessageId: 'DEMO-SIMULATED', errorMessage: null, sentAt: at, lastAttemptAt: at });
      const order = s.preorders.find((entry) => entry.preorderId === item.preorderId);
      if (order?.status === 'READY') order.status = 'NOTIFIED';
      return commit({ result: 'SENT', notification: notificationOut(item) });
    }
    if ((match = m(/^\/preorders\/(\d+)\/(confirm-payment|fulfill|cancel)$/)) && method === 'POST') {
      const order = s.preorders.find((item) => item.preorderId === Number(match[1])) || fail(404, 'Không tìm thấy đơn đặt trước.');
      requireBranch(s, actor, order.branchId);
      if (match[2] === 'confirm-payment') { if (order.paymentStatus !== 'UNPAID') fail(409, 'Đơn đã được thanh toán.'); order.paymentStatus = 'PAID'; }
      if (match[2] === 'fulfill') {
        if (!['READY', 'NOTIFIED'].includes(order.status) || order.paymentStatus !== 'PAID') fail(409, 'Đơn chưa sẵn sàng hoặc chưa thanh toán.');
        for (const line of order.items) move(s, actor, order.branchId, line.variantId, -line.quantity, 'PREORDER_FULFILLMENT', `Giao đặt trước ${order.preorderCode}`);
        order.status = 'FULFILLED'; order.fulfilledAt = now();
      }
      if (match[2] === 'cancel') {
        if (!OPEN_PREORDER.includes(order.status)) fail(409, 'Đơn đã kết thúc.');
        Object.assign(order, { status: 'CANCELLED', cancelledAt: now(), cancelReason: body.reason, paymentStatus: order.paymentStatus === 'PAID' ? 'REFUNDED' : order.paymentStatus });
        allocate(s, order.branchId, order.items.map((line) => line.variantId));
      }
      return commit(order);
    }

    // Customers
    if ((route === '/customers' || route === '/customers/quick-search') && method === 'GET') {
      const q = fold(params.get('q') || '');
      // Same rule as the backend: paid sales + fulfilled pre-orders, in branches the user can see.
      const visible = accessibleBranches(s, actor);
      const rows = s.customers.filter((customer) => !q || [customer.fullName, customer.phone, customer.email].some((value) => fold(value).includes(q)))
        .map((customer) => {
          const purchases = [
            ...s.orders.filter((order) => order.status === 'PAID'),
            ...s.preorders.filter((order) => order.status === 'FULFILLED'),
          ].filter((order) => order.customerId === customer.customerId && visible.includes(order.branchId));
          return { ...customer, orderCount: purchases.length, totalSpent: String(purchases.reduce((sum, order) => sum + Number(order.totalAmount), 0)) };
        });
      return clone(route.endsWith('quick-search') ? rows.slice(0, Number(params.get('limit') || 10)) : rows);
    }
    if (route === '/customers' && method === 'POST') {
      required(body, ['fullName']);
      const existing = body.phone && s.customers.find((customer) => customer.phone === body.phone);
      if (existing) fail(409, 'Số điện thoại đã thuộc về khách hàng khác.');
      const customer = { customerId: s.next.customer++, fullName: body.fullName.trim(), phone: body.phone || null, email: body.email || null, address: body.address || null, note: body.note || null };
      s.customers.push(customer);
      return commit(customer);
    }
    if ((match = m(/^\/customers\/(\d+)(?:\/(history))?$/))) {
      const customer = s.customers.find((item) => item.customerId === Number(match[1])) || fail(404, 'Không tìm thấy khách hàng.');
      if (match[2]) {
        const visible = accessibleBranches(s, actor);
        const mine = (order) => order.customerId === customer.customerId && visible.includes(order.branchId);
        return clone([
          ...s.orders.filter(mine).map((order) => ({ id: order.salesOrderId, type: 'SALE', orderCode: order.orderCode, branchName: order.branchName, createdAt: order.createdAt, status: order.status, totalAmount: order.totalAmount })),
          ...s.preorders.filter(mine).map((order) => ({ id: order.preorderId, type: 'PREORDER', orderCode: order.preorderCode, branchName: order.branchName, createdAt: order.createdAt, status: order.status, totalAmount: order.totalAmount })),
        ].sort((a, b) => b.createdAt.localeCompare(a.createdAt)));
      }
      if (method === 'GET') return clone(customer);
      if (method === 'PUT') { requireRole(actor, 'OWNER', 'MANAGER'); required(body, ['fullName']); Object.assign(customer, { fullName: body.fullName.trim(), phone: body.phone || null, email: body.email || null, address: body.address || null, note: body.note || null }); return commit(customer); }
    }

    // Reports
    if (route.startsWith('/reports/')) {
      requireRole(actor, 'OWNER', 'MANAGER');
      const branchId = Number(params.get('branchId')) || null;
      if (branchId) requireBranch(s, actor, branchId);
      else if (actor.role !== 'OWNER') fail(400, 'Quản lý chi nhánh cần chọn chi nhánh được phân công.');
      const [start, end] = reportWindow(params);
      const events = revenueEvents(s, actor, branchId);
      const inRange = (from, to) => events.filter((event) => event.at >= from && event.at <= to);
      if (route === '/reports/summary') {
        const length = end - start;
        const current = inRange(start, end);
        const previous = inRange(new Date(start - length), new Date(start - 1));
        const sum = (list) => list.reduce((total, event) => total + event.amount, 0);
        return { date_from: start.toISOString().slice(0, 10), date_to: end.toISOString().slice(0, 10), branch_id: branchId, revenue: metric(sum(current), sum(previous)), order_count: metric(current.length, previous.length), average_order_value: metric(current.length ? sum(current) / current.length : 0, previous.length ? sum(previous) / previous.length : 0), sales_revenue: sum(current), preorder_revenue: 0 };
      }
      if (route === '/reports/revenue') {
        const points = [];
        for (const day = new Date(start); day <= end; day.setDate(day.getDate() + 1)) {
          const next = new Date(day); next.setDate(next.getDate() + 1);
          const list = inRange(day, new Date(next - 1));
          const revenue = list.reduce((total, event) => total + event.amount, 0);
          points.push({ period: day.toLocaleDateString('en-CA'), period_start: day.toLocaleDateString('en-CA'), period_end: day.toLocaleDateString('en-CA'), revenue, sales_revenue: revenue, preorder_revenue: 0, order_count: list.length, sales_count: list.length, preorder_count: 0 });
        }
        return { granularity: 'day', points, totals: { revenue: points.reduce((total, point) => total + point.revenue, 0), order_count: points.reduce((total, point) => total + point.order_count, 0) } };
      }
      if (route === '/reports/top-products') {
        const totals = new Map();
        for (const event of inRange(start, end)) for (const item of event.items) {
          const entry = totals.get(item.sku) || { sku: item.sku, product_name: item.productName, quantity: 0, revenue: 0 };
          entry.quantity += item.quantity; entry.revenue += Number(item.lineTotal);
          totals.set(item.sku, entry);
        }
        const key = params.get('sortBy') === 'quantity' ? 'quantity' : 'revenue';
        return { items: [...totals.values()].sort((a, b) => b[key] - a[key]).slice(0, Number(params.get('limit') || 10)).map((item, index) => ({ rank: index + 1, ...item })) };
      }
      if (route === '/reports/revenue/export') fail(501, 'Xuất file báo cáo chỉ có ở bản chính thức.');
    }

    fail(404, 'Chức năng này chưa có trong bản demo.');
  };
}
