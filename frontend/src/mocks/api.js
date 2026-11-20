import { mockProducts, mockInventory, mockSalesOrders } from './data.js';
const STORE_KEY = 'dkat-api-mock-v1';
const seed = () => ({
  categories: [
    { categoryId: 1, parentCategoryId: null, name: 'Clothing', description: '', status: 'ACTIVE' },
    { categoryId: 2, parentCategoryId: 1, name: 'Tops', description: '', status: 'ACTIVE' },
    { categoryId: 3, parentCategoryId: null, name: 'Accessories', description: '', status: 'ACTIVE' },
  ],
  products: structuredClone(mockProducts),
  attributes: [],
  inventory: structuredClone(mockInventory),
  movements: [],
  customers: [],
  branches: [{ id: 1, storeId: 1, branchCode: 'BR-01', name: 'Branch 1', address: '', phone: '', status: 'ACTIVE' }, { id: 2, storeId: 1, branchCode: 'BR-02', name: 'Branch 2', address: '', phone: '', status: 'ACTIVE' }],
  salesOrders: structuredClone(mockSalesOrders), next: { category: 4, product: 2, variant: 2, attribute: 1, order: 1, movement: 1, customer: 1 }, user: null,
});

function read() { try { return JSON.parse(localStorage.getItem(STORE_KEY)) || seed(); } catch { return seed(); } }
function write(state) { localStorage.setItem(STORE_KEY, JSON.stringify(state)); }
function ownerOnly(state) { if (state.user?.role !== 'owner') fail(403, 'FORBIDDEN', 'Owner role required.'); }
function fail(status, code, message, details = null) { const error = new Error(message); error.status = status; error.code = code; error.details = details; throw error; }
function tree(nodes, parentId = null) { return nodes.filter(c => c.parentCategoryId === parentId).map(c => ({ ...c, children: tree(nodes, c.categoryId) })); }
function flatten(nodes) { return nodes.flatMap(c => [c, ...flatten(c.children || [])]); }

export async function mockApiRequest(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const url = new URL(path, 'http://mock.local');
  const route = url.pathname;
  const body = options.body ? JSON.parse(options.body) : {};
  const s = read();
  const match = (regex) => route.match(regex);

  if (route === '/auth/login' && method === 'POST') {
    const raw = String(body.username || '').toLowerCase();
    if (raw.includes('locked')) fail(401, 'UNAUTHORIZED', 'Account is locked.');
    if (raw.includes('wrong')) fail(401, 'UNAUTHORIZED', 'Invalid username or password.');
    const role = raw.includes('manager') ? 'manager' : raw.includes('staff') || raw.includes('employee') ? 'staff' : 'owner';
    const user = { id: 1, username: raw || 'demo', full_name: role === 'owner' ? 'Demo Owner' : role === 'manager' ? 'Demo Manager' : 'Demo Employee', role, shop_id: 1, accessible_branches: role === 'owner' ? [1,2] : [1] };
    s.user = user; write(s); return { access_token: `mock-${role}-token`, token_type: 'bearer', user };
  }
  if (route === '/auth/me' && method === 'GET') return s.user || fail(401, 'UNAUTHORIZED', 'Please sign in.');
  if (route === '/auth/logout' && method === 'POST') { s.user = null; write(s); return null; }

  if (route === '/categories' && method === 'GET') {
    const all = flatten(tree(s.categories));
    const status = url.searchParams.get('status');
    return status ? all.filter(c => c.status === status) : tree(s.categories);
  }
  if (route === '/categories' && method === 'POST') {
    ownerOnly(s);
    const name = String(body.name || '').trim();
    if (!name) fail(422, 'VALIDATION_ERROR', 'Invalid request data', [{ field: 'name', message: 'Field required' }]);
    if (flatten(tree(s.categories)).some(c => c.name.toLowerCase() === name.toLowerCase() && c.parentCategoryId === (body.parentCategoryId || null))) fail(409, 'CONFLICT', 'Category already exists under this parent.');
    const category = { categoryId: s.next.category++, parentCategoryId: body.parentCategoryId || null, name, description: body.description || null, status: 'ACTIVE', children: [] };
    s.categories.push(category); write(s); return category;
  }
  let m = match(/^\/categories\/(\d+)(?:\/(status))?$/);
  if (m && method === 'PUT') {
    ownerOnly(s);
    const category = s.categories.find(c => c.categoryId === Number(m[1])); if (!category) fail(404, 'NOT_FOUND', 'Category not found.');
    Object.assign(category, body); write(s); return category;
  }
  if (m && method === 'PATCH' && m[2] === 'status') {
    ownerOnly(s);
    const category = s.categories.find(c => c.categoryId === Number(m[1])); if (!category) fail(404, 'NOT_FOUND', 'Category not found.');
    category.status = body.status; write(s); return category;
  }

  if (route === '/branches' && method === 'GET') return s.branches.filter(b => (s.user?.role === 'owner' || b.id === 1) && (!url.searchParams.get('status') || b.status === url.searchParams.get('status')));
  if (route === '/customers/quick-search' && method === 'GET') { const q=(url.searchParams.get('q')||'').toLowerCase(); return s.customers.filter(c=>!q||c.phone?.includes(q)||c.fullName.toLowerCase().includes(q)).slice(0,10); }
  if (route === '/customers' && method === 'POST') { if(!body.fullName?.trim())fail(422,'VALIDATION_ERROR','Name is required.',[{field:'fullName',message:'Field required'}]); const existing=body.phone&&s.customers.find(c=>c.phone===body.phone); if(existing)return existing; const customer={customerId:s.next.customer++,fullName:body.fullName.trim(),phone:body.phone||null,email:body.email||null,address:body.address||null};s.customers.push(customer);write(s);return customer; }
  if (route === '/attributes' && method === 'GET') return s.attributes;
  if (route === '/attributes' && method === 'POST') {
    ownerOnly(s);
    const found = s.attributes.find(a => a.name.toLowerCase() === body.name.toLowerCase());
    if (found) fail(409, 'CONFLICT', 'Attribute already exists.');
    const attribute = { ...body, attributeId: s.next.attribute++, status: 'ACTIVE' }; s.attributes.push(attribute); write(s); return attribute;
  }

  if (route === '/products' && method === 'GET') {
    const categoryId = Number(url.searchParams.get('categoryId')) || null;
    const keyword = (url.searchParams.get('keyword') || '').toLowerCase();
    const status = url.searchParams.get('status') || 'ACTIVE';
    const page = Number(url.searchParams.get('page') || 1), size = Number(url.searchParams.get('size') || 50);
    return s.products.filter(p => (p.status || 'ACTIVE') === status && (!categoryId || p.category_id === categoryId) && (!keyword || [p.name,p.product_code,...p.variants.map(v=>v.sku)].some(v=>v.toLowerCase().includes(keyword)))).slice((page-1)*size,page*size);
  }
  if (route === '/products' && method === 'POST') {
    ownerOnly(s);
    if (!body.name?.trim()) fail(422, 'VALIDATION_ERROR', 'Invalid request data', [{ field: 'name', message: 'Field required' }]);
    const category = flatten(tree(s.categories)).find(c => c.categoryId === Number(body.categoryId));
    if (!category) fail(422, 'VALIDATION_ERROR', 'Invalid request data', [{ field: 'categoryId', message: 'Select a valid category' }]);
    const product = { productId: s.next.product++, productCode: body.productCode || `PRD-${String(s.next.product).padStart(4,'0')}`, categoryId: category.categoryId, name: body.name.trim(), description: body.description || null, imageUrl: body.imageUrl || null, status: 'ACTIVE', createdBy: 1, variants: [] };
    s.products.push({ product_id: product.productId, category_id: product.categoryId, product_code: product.productCode, name: product.name, description: product.description, imageUrl: product.imageUrl, status: product.status, variants: [] }); write(s); return product;
  }
  m = match(/^\/products\/(\d+)(?:\/(status|variants))?$/);
  if (m && method === 'GET') {
    const product = s.products.find(p => p.product_id === Number(m[1])); if (!product) fail(404, 'NOT_FOUND', 'Product not found.');
    return { productId: product.product_id, productCode: product.product_code, categoryId: product.category_id, name: product.name, description: product.description || null, imageUrl: product.imageUrl || null, status: product.status || 'ACTIVE', createdBy: 1, variants: product.variants };
  }
  if (m && method === 'PUT' && !m[2]) {
    ownerOnly(s);
    const product = s.products.find(p => p.product_id === Number(m[1])); if (!product) fail(404, 'NOT_FOUND', 'Product not found.');
    Object.assign(product, { name: body.name, category_id: Number(body.categoryId), description: body.description || null, imageUrl: body.imageUrl || null }); write(s);
    return { productId: product.product_id, productCode: product.product_code, categoryId: product.category_id, name: product.name, description: product.description, imageUrl: product.imageUrl || null, status: product.status || 'ACTIVE', createdBy: 1 };
  }
  if (m && method === 'PATCH' && m[2] === 'status') {
    ownerOnly(s);
    const product = s.products.find(p => p.product_id === Number(m[1])); if (!product) fail(404, 'NOT_FOUND', 'Product not found.'); product.status = body.status; write(s);
    return { productId: product.product_id, productCode: product.product_code, categoryId: product.category_id, name: product.name, description: product.description || null, imageUrl: product.imageUrl || null, status: product.status, createdBy: 1 };
  }
  if (m && method === 'POST' && m[2] === 'variants') {
    ownerOnly(s);
    const product = s.products.find(p => p.product_id === Number(m[1])); if (!product) fail(404, 'NOT_FOUND', 'Product not found.');
    const variant = { variant_id: s.next.variant++, sku: body.sku || `${product.product_code}-${s.next.variant}`, variant_name: body.variantName, price: String(body.price), status: 'ACTIVE', attributes: body.attributes.map(a => ({ attribute_id: a.attributeId, name: s.attributes.find(x=>x.attributeId===a.attributeId)?.name, data_type: s.attributes.find(x=>x.attributeId===a.attributeId)?.dataType, value: String(a.value) })) };
    product.variants.push(variant); for (const branch of s.branches) s.inventory.push({ branchId: branch.id, branchName: branch.name, productId: product.product_id, productName: product.name, variantId: variant.variant_id, variantName: variant.variant_name, sku: variant.sku, quantity: 0, reserved: 0, available: 0 }); write(s); return variant;
  }

  if (route === '/inventory' && method === 'GET') {
    const rawBranch = url.searchParams.get('branchId'), branchId = Number(rawBranch) || null, keyword = (url.searchParams.get('keyword') || '').toLowerCase();
    return s.inventory.filter(i => (!branchId || i.branchId === branchId) && (!keyword || [i.sku,i.productName,i.variantName].some(x=>x.toLowerCase().includes(keyword))));
  }
  if (route === '/inventory/movements' && method === 'GET') {
    const branchId = Number(url.searchParams.get('branchId')) || null;
    const type = url.searchParams.get('type');
    const keyword = (url.searchParams.get('keyword') || '').toLowerCase();
    return s.movements.filter(m => (!branchId || m.branchId === branchId) && (!type || m.movementType === type) && (!keyword || [m.sku,m.variantName,m.productName].some(v => String(v||'').toLowerCase().includes(keyword))));
  }
  if (['/inventory/import','/inventory/export','/inventory/stocktake'].includes(route) && method === 'POST') {
    const branchId = Number(body.branchId);
    if (!s.branches.some(b => b.id === branchId && b.status === 'ACTIVE' && (s.user?.role === 'owner' || branchId === 1))) fail(403,'FORBIDDEN','Branch access denied.');
    if (!Array.isArray(body.items) || !body.items.length) fail(422,'VALIDATION_ERROR','Add at least one SKU.');
    const kind = route.endsWith('/import') ? 'IMPORT' : route.endsWith('/export') ? 'EXPORT' : 'ADJUSTMENT';
    const staged = [];
    for (const line of body.items) {
      const stock = s.inventory.find(i => i.branchId === branchId && i.variantId === Number(line.variantId));
      if (!stock) fail(404,'NOT_FOUND','Inventory item not found.');
      const submitted = Number(kind === 'ADJUSTMENT' ? line.countedQuantity : line.quantity);
      if (!Number.isInteger(submitted) || submitted < (kind === 'ADJUSTMENT' ? 0 : 1)) fail(422,'VALIDATION_ERROR','Quantity must be a valid whole number.');
      if (kind === 'EXPORT' && submitted > stock.available) fail(409,'INSUFFICIENT_STOCK',`Insufficient stock for ${stock.sku}.`,{variantId:stock.variantId,available:stock.available});
      const target = kind === 'ADJUSTMENT' ? submitted : stock.quantity + (kind === 'IMPORT' ? submitted : -submitted);
      if (kind === 'ADJUSTMENT' && target < stock.reserved) fail(409,'STOCK_BELOW_RESERVED',`Counted stock is below reserved stock for ${stock.sku}.`,{variantId:stock.variantId,reserved:stock.reserved});
      staged.push({stock,target,delta:target-stock.quantity});
    }
    const results=[];
    for (const row of staged) { const before=row.stock.quantity; row.stock.quantity=row.target; row.stock.available=row.target-row.stock.reserved; const movement={movementId:s.next.movement++,branchId,branchName:s.branches.find(b=>b.id===branchId).name,variantId:row.stock.variantId,sku:row.stock.sku,variantName:row.stock.variantName,productName:row.stock.productName,movementType:kind,quantityChange:row.delta,reason:body.reason||null,note:body.note||null,createdBy:s.user?.full_name||'Mock user',actorName:s.user?.full_name||'Mock user',createdAt:new Date().toISOString(),referenceId:null}; s.movements.unshift(movement); results.push({variantId:row.stock.variantId,quantityBefore:before,quantityChange:row.delta,quantityAfter:row.target}); }
    write(s); return {branchId,movementType:kind,reason:body.reason||null,items:results};
  }
  if (route === '/sales-orders' && method === 'POST') {
    const branch = s.branches.find(b => b.id === Number(body.branchId) && b.status === 'ACTIVE');
    if (!branch) fail(403, 'FORBIDDEN', 'Branch is unavailable.');
    if (s.user?.role !== 'owner' && branch.id !== 1) fail(403, 'FORBIDDEN', 'Branch is not assigned to this account.');
    const items = []; let subtotal = 0;
    for (const line of body.items || []) {
      const stock = s.inventory.find(i => i.branchId === branch.id && i.variantId === Number(line.variantId));
      const product = s.products.find(p => p.product_id === stock?.productId);
      const variant = product?.variants.find(v => v.variant_id === Number(line.variantId));
      if (!stock || !variant || Number(line.quantity) > stock.available) fail(409, 'OUT_OF_STOCK', 'Insufficient stock.', { variantId: line.variantId, available: stock?.available || 0 });
      const price = Number(variant.price), quantity = Number(line.quantity), lineTotal = price * quantity;
      subtotal += lineTotal; items.push({ variantId: variant.variant_id, productName: product.name, sku: variant.sku, unitPrice: price, quantity, lineTotal });
    }
    const discountAmount = Number(body.discountAmount || 0);
    if (discountAmount > subtotal) fail(422, 'VALIDATION_ERROR', 'Discount cannot exceed subtotal.', [{ field: 'discountAmount', message: 'Must not exceed subtotal.' }]);
    const customer=s.customers.find(c=>c.customerId===Number(body.customerId));
    if(body.customerId&&!customer)fail(422,'VALIDATION_ERROR','Choose a valid customer.',[{field:'customerId',message:'Unknown customer'}]);
    const order = { salesOrderId: s.next.order, orderCode: 'SO-' + String(s.next.order++).padStart(6,'0'), branchId: branch.id, customerId:customer?.customerId||null, customerName:customer?.fullName||'Guest', subtotal, discountAmount, totalAmount: subtotal - discountAmount, status: 'PENDING', items, createdAt: new Date().toISOString() };
    for (const line of items) { const stock = s.inventory.find(i=>i.branchId===branch.id&&i.variantId===line.variantId); if (stock) { stock.available -= line.quantity; stock.reserved += line.quantity; } } s.salesOrders.push(order); write(s); return order;
  }
  if (route === '/sales-orders' && method === 'GET') {
    const status=url.searchParams.get('status'), branchId=Number(url.searchParams.get('branchId'))||null, keyword=(url.searchParams.get('keyword')||'').toLowerCase();
    const from=url.searchParams.get('date_from'),to=url.searchParams.get('date_to'),page=Number(url.searchParams.get('page')||1),size=Number(url.searchParams.get('size')||50);
    return s.salesOrders.filter(o=>(s.user?.role==='owner'||o.branchId===1)&&(!status||o.status===status)&&(!branchId||o.branchId===branchId)&&(!keyword||o.orderCode.toLowerCase().includes(keyword))&&(!from||o.createdAt.slice(0,10)>=from)&&(!to||o.createdAt.slice(0,10)<=to)).slice((page-1)*size,page*size);
  }
  m=match(/^\/sales-orders\/(\d+)(?:\/(confirm-payment|cancel|refund))?$/);
  if(m){
    const order=s.salesOrders.find(o=>o.salesOrderId===Number(m[1])); if(!order)fail(404,'NOT_FOUND','Sales order not found.');
    if(s.user?.role!=='owner'&&order.branchId!==1)fail(403,'FORBIDDEN','Branch access denied.');
    if(method==='GET'&&!m[2])return order;
    if(method==='POST'&&m[2]==='confirm-payment'){
      if(order.status!=='PENDING')fail(409,'CONFLICT','Only pending orders can be paid.');
      if(body.paymentMethod==='CASH'&&Number(body.amountTendered)<order.totalAmount)fail(422,'VALIDATION_ERROR','Cash received must cover the order total.',[{field:'amountTendered',message:'Must cover total.'}]);
      order.status='PAID';order.paidAt=new Date().toISOString();order.payments=[{paymentMethod:body.paymentMethod,amount:order.totalAmount,status:'SUCCESS',confirmedAt:order.paidAt}];
      for(const line of order.items){const stock=s.inventory.find(i=>i.branchId===order.branchId&&i.variantId===line.variantId);if(stock){stock.quantity-=line.quantity;stock.reserved-=line.quantity;s.movements.unshift({movementId:s.next.movement++,branchId:order.branchId,branchName:stock.branchName,variantId:line.variantId,sku:line.sku,variantName:stock.variantName,productName:stock.productName,movementType:'SALE',quantityChange:-line.quantity,reason:null,note:'POS sale',actorName:s.user?.full_name,createdBy:s.user?.full_name,createdAt:order.paidAt,referenceId:order.salesOrderId});}}
      write(s);return order;
    }
    if(method==='POST'&&m[2]==='cancel'){
      if(order.status!=='PENDING')fail(409,'CONFLICT','Only pending orders can be cancelled.');order.status='CANCELLED';
      for(const line of order.items){const stock=s.inventory.find(i=>i.branchId===order.branchId&&i.variantId===line.variantId);if(stock){stock.reserved-=line.quantity;stock.available+=line.quantity;}}
      write(s);return order;
    }
    if(method==='POST'&&m[2]==='refund'){
      if(s.user?.role==='staff')fail(403,'FORBIDDEN','Only OWNER or MANAGER can refund.');if(order.status!=='PAID')fail(409,'CONFLICT','Only paid orders can be refunded.');if(!String(body.reason||'').trim())fail(422,'VALIDATION_ERROR','Refund reason is required.');order.status='CANCELLED';order.refundReason=body.reason;order.payments=(order.payments||[]).map(p=>({...p,status:'REFUNDED'}));
      for(const line of order.items){const stock=s.inventory.find(i=>i.branchId===order.branchId&&i.variantId===line.variantId);if(stock){stock.quantity+=line.quantity;stock.available+=line.quantity;s.movements.unshift({movementId:s.next.movement++,branchId:order.branchId,branchName:stock.branchName,variantId:line.variantId,sku:line.sku,variantName:stock.variantName,productName:stock.productName,movementType:'ADJUSTMENT',quantityChange:line.quantity,note:'Refund: '+body.reason,actorName:s.user?.full_name,createdBy:s.user?.full_name,createdAt:new Date().toISOString(),referenceId:order.salesOrderId});}}
      write(s);return order;
    }
  }
  fail(404, 'NOT_FOUND', `Mock endpoint not found: ${method} ${route}`);
}
