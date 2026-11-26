import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = 'http://127.0.0.1:5173/';
const OUT = path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1')), 'shots');
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const check = (name, ok, extra = '') => { results.push([ok ? 'PASS' : 'FAIL', name, extra]); console.log(ok ? 'PASS' : 'FAIL', name, extra); };
const step = async (name, fn) => { try { await fn(); } catch (error) { check(name, false, String(error.message).split('\n')[0]); } };

const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true });
const consoleErrors = [];

async function newPage(context) {
  const page = await context.newPage();
  page.on('pageerror', (error) => consoleErrors.push(String(error)));
  return page;
}
async function login(page, username, password) {
  await page.goto(BASE + '#/login');
  await page.fill('input[name=username]', username);
  await page.fill('input[name=password]', password);
  await page.click('button[type=submit]');
}
const toast = (page) => page.locator('.dk-toast').last();

// 1. Authentication ---------------------------------------------------------
const ctxAuth = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const auth = await newPage(ctxAuth);
await step('login wrong password shows toast', async () => {
  await login(auth, 'e2eowner', 'wrong-password-xx');
  await toast(auth).waitFor({ timeout: 8000 });
  check('login wrong password shows toast', (await toast(auth).innerText()).includes('không chính xác'), await toast(auth).innerText());
  check('stays on login', auth.url().includes('#/login'));
});
await step('login unknown user rejected', async () => {
  await login(auth, 'khongtontai', 'owner-password-123');
  await auth.waitForTimeout(1200);
  check('login unknown user rejected', auth.url().includes('#/login'));
});
await step('manager login with plain username', async () => {
  await login(auth, 'E2EManager', 'staff-password-123');
  await auth.waitForURL(/#\/admin\/dashboard/, { timeout: 10000 });
  check('manager login with plain username', true);
  const nav = await auth.locator('#primary-navigation').innerText();
  check('manager nav hides Chi nhánh', !nav.includes('Chi nhánh'), nav.replace(/\s+/g, ' '));
  await auth.goto(BASE + '#/admin/employees');
  await auth.locator('.notice', { hasText: 'Bạn đang xem nhân viên' }).waitFor({ timeout: 8000 });
  check('manager employees read-only', (await auth.locator('text=+ Thêm nhân viên').count()) === 0);
  await auth.screenshot({ path: path.join(OUT, '01-manager-employees.png') });
});
await ctxAuth.close();

// 2. Owner: branches, products, inventory import -----------------------------
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const owner = await newPage(ctx);
await step('owner flows', async () => {
  await login(owner, 'e2eowner', 'owner-password-123');
  await owner.waitForURL(/#\/admin\/dashboard/, { timeout: 10000 });
  await owner.goto(BASE + '#/admin/branches');
  await owner.click('text=+ Thêm chi nhánh');
  await owner.locator('.dk-dialog').waitFor();
  await owner.click('.dk-dialog-footer >> text=Tạo chi nhánh');
  check('branch form inline validation', (await owner.locator('.dk-field-error').count()) >= 2);
  await owner.fill('.dk-dialog input[name=name]', 'E2E Đà Nẵng');
  await owner.fill('.dk-dialog input[name=address]', '5 Bạch Đằng');
  await owner.fill('.dk-dialog input[name=branchCode]', 'dn 01');
  await owner.click('.dk-dialog-footer >> text=Tạo chi nhánh');
  check('bad branch code caught inline', (await owner.locator('.dk-field-error').innerText()).includes('Mã'));
  await owner.fill('.dk-dialog input[name=branchCode]', '');
  await owner.click('.dk-dialog-footer >> text=Tạo chi nhánh');
  await owner.locator('.dk-toast-success').waitFor({ timeout: 8000 });
  const created = (await owner.locator('.dk-toast-success').allInnerTexts()).join(' | ').replace(/\s+/g, ' ');
  check('branch created toast', created.includes('E2E Đà Nẵng'), created);
  await owner.locator('td', { hasText: 'E2E Đà Nẵng' }).waitFor();
  await owner.waitForFunction(() => [...document.querySelectorAll('.app-header select option')].some((o) => o.textContent === 'E2E Đà Nẵng'), null, { timeout: 5000 }).catch(() => {});
  const options = await owner.locator('.app-header select option').allInnerTexts();
  check('header branch list refreshed', options.includes('E2E Đà Nẵng'), options.join(','));
  await owner.click('text=+ Thêm chi nhánh');
  await owner.fill('.dk-dialog input[name=name]', 'e2e đà nẵng');
  await owner.fill('.dk-dialog input[name=address]', 'x');
  await owner.click('.dk-dialog-footer >> text=Tạo chi nhánh');
  await owner.locator('.dk-toast-error').waitFor({ timeout: 8000 });
  const errorText = await owner.locator('.dk-toast-error').last().innerText();
  check('duplicate branch error toast visible above dialog', errorText.includes('Tên chi nhánh đã tồn tại') && await owner.locator('.dk-dialog').isVisible(), errorText.replace(/\s+/g, ' '));
  await owner.screenshot({ path: path.join(OUT, '02-branch-duplicate-toast.png') });
  await owner.click('.dk-dialog-footer >> text=Hủy');
  const discard = owner.locator('text=Đóng, không lưu');
  if (await discard.count()) await discard.click();
  // edit
  await owner.locator('tr', { hasText: 'E2E Đà Nẵng' }).locator('text=Sửa').click();
  await owner.fill('.dk-dialog input[name=address]', '9 Bạch Đằng');
  await owner.click('.dk-dialog-footer >> text=Lưu thay đổi');
  await owner.locator('td', { hasText: '9 Bạch Đằng' }).waitFor({ timeout: 8000 });
  check('branch edited', true);
});

await step('owner product create with variants + opening stock', async () => {
  await owner.goto(BASE + '#/admin/products');
  await owner.click('text=+ Thêm sản phẩm');
  await owner.locator('.dk-dialog').waitFor();
  await owner.fill('.dk-dialog input[name=name]', 'Quần kaki E2E');
  await owner.selectOption('.dk-dialog select[name=categoryId]', { label: 'Áo E2E' });
  const rows = owner.locator('.variant-table tbody tr:not(.variant-error-row)');
  await rows.nth(0).locator('input').nth(0).fill('Be');
  await rows.nth(0).locator('input').nth(1).fill('30');
  await rows.nth(0).locator('input').nth(3).fill('400000');
  await rows.nth(0).locator('input[aria-label="Tồn ban đầu"]').fill('7');
  await owner.click('text=+ Thêm biến thể');
  await rows.nth(1).locator('input').nth(0).fill('Be');
  await rows.nth(1).locator('input').nth(1).fill('30');
  await owner.click('.dk-dialog-footer >> text=Tạo sản phẩm');
  check('duplicate variant row flagged', (await owner.locator('.variant-error-row').count()) > 0);
  await rows.nth(1).locator('input').nth(1).fill('32');
  await owner.screenshot({ path: path.join(OUT, '03-product-form.png') });
  await owner.click('.dk-dialog-footer >> text=Tạo sản phẩm');
  await owner.locator('.dk-toast-success').last().waitFor({ timeout: 10000 });
  await owner.locator('.product-detail-panel h2', { hasText: 'Quần kaki E2E' }).waitFor({ timeout: 8000 });
  const detail = await owner.locator('.product-detail-panel').innerText();
  check('product detail shows 2 variants with stock 7', detail.includes('Be / 30') && detail.includes('Be / 32') && detail.includes('7'), detail.slice(0, 200).replace(/\s+/g, ' '));
});

await step('inventory CSV import with preview, errors and duplicate guard', async () => {
  await owner.goto(BASE + '#/admin/inventory');
  await owner.click('text=Nhập từ file CSV/Excel');
  await owner.locator('.dropzone').waitFor();
  const bad = path.join(OUT, 'bad.csv'); fs.writeFileSync(bad, '\ufeffsku;số lượng;ghi chú\nE2E-SM-L;3;lô 1\nKHONG-CO;2;\nE2E-SM-M;-1;\n');
  await owner.setInputFiles('.dropzone input[type=file]', bad);
  await owner.locator('.import-preview').waitFor({ timeout: 10000 });
  check('error rows highlighted', (await owner.locator('tr.row-error').count()) === 2);
  check('confirm disabled with errors', await owner.locator('.dk-dialog-footer >> text=Xác nhận nhập').isDisabled());
  await owner.screenshot({ path: path.join(OUT, '04-import-errors.png') });
  await owner.click('text=← Chọn file khác');
  const good = path.join(OUT, 'good.csv'); fs.writeFileSync(good, 'sku,quantity,note\nE2E-SM-L,3,Lô E2E\n');
  await owner.setInputFiles('.dropzone input[type=file]', good);
  await owner.locator('.import-preview').waitFor({ timeout: 10000 });
  await owner.click('.dk-dialog-footer >> text=Xác nhận nhập');
  await owner.locator('.import-result').waitFor({ timeout: 10000 });
  check('import result shown', (await owner.locator('.import-result').innerText()).includes('E2E-SM-L'));
  await owner.click('text=Nhập file khác');
  await owner.setInputFiles('.dropzone input[type=file]', good);
  await owner.locator('.duplicate-confirm').waitFor({ timeout: 10000 });
  check('duplicate import requires confirmation', await owner.locator('.dk-dialog-footer >> text=Xác nhận nhập').isDisabled());
  await owner.click('.dk-dialog-footer >> text=← Chọn file khác');
  await owner.click('.dk-dialog-footer >> text=Đóng');
  const movement = await owner.locator('section.panel', { hasText: 'Lịch sử biến động kho' }).innerText();
  check('movement recorded from file', movement.includes('từ file'));
});
await ctx.close();

// 3. Staff POS + Customer Display ---------------------------------------------
const posCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const pos = await newPage(posCtx);
await step('POS + customer display', async () => {
  await login(pos, 'e2estaff', 'staff-password-123');
  await pos.waitForURL(/#\/admin\/pos/, { timeout: 10000 });
  await pos.locator('.pos-live-item').first().waitFor({ timeout: 10000 });
  const [display] = await Promise.all([posCtx.waitForEvent('page'), pos.locator('button', { hasText: 'Màn hình khách hàng' }).click()]);
  display.on('pageerror', (error) => consoleErrors.push('display: ' + error));
  await display.waitForLoadState();
  await display.locator('.cd-welcome h1').waitFor({ timeout: 8000 });
  check('display welcome state', (await display.locator('.cd-welcome h1').innerText()) === 'Chào mừng quý khách');
  await pos.locator('.display-status.is-on').waitFor({ timeout: 8000 });
  check('POS shows display connected', true);
  check('display has no admin sidebar', (await display.locator('.sidebar').count()) === 0);
  await pos.locator('.pos-live-item', { hasText: 'Trắng / M' }).locator('.pos-live-item-main').click();
  await pos.locator('.pos-live-item', { hasText: 'Trắng / M' }).locator('.pos-live-item-main').click();
  await display.locator('.cd-item').first().waitFor({ timeout: 5000 });
  await display.waitForFunction(() => document.querySelector('.cd-item-qty')?.textContent === '2', null, { timeout: 5000 }).catch(() => {});
  const first = await display.locator('.cd-summary').innerText();
  check('display syncs items and total', (await display.locator('.cd-item-qty').innerText()) === '2' && first.includes('700.000'), first.replace(/\s+/g, ' '));
  await pos.fill('input[placeholder="0"]', '50000');
  await display.waitForFunction(() => document.querySelector('.cd-grand strong')?.textContent.includes('650.000'), null, { timeout: 5000 });
  check('display syncs discount', true);
  await display.screenshot({ path: path.join(OUT, '05-display-cart.png') });
  // close & reopen keeps state
  await display.close();
  const [again] = await Promise.all([posCtx.waitForEvent('page'), pos.locator('button', { hasText: 'Màn hình khách hàng' }).click()]);
  await again.locator('.cd-item').first().waitFor({ timeout: 8000 });
  check('reopened display restores cart', (await again.locator('.cd-grand strong').innerText()).includes('650.000'));
  await pos.click('text=Thanh toán →');
  await pos.locator('.payment-dialog').waitFor({ timeout: 8000 });
  await again.locator('.cd-paying').waitFor({ timeout: 5000 });
  check('display shows paying state', true);
  await pos.fill('.payment-dialog input[type=number]', '700000');
  await again.waitForFunction(() => document.querySelector('.cd-cash')?.textContent.includes('50.000'), null, { timeout: 5000 });
  check('display shows tendered and change', true);
  await pos.screenshot({ path: path.join(OUT, '06-pos-payment.png') });
  await pos.click('.payment-dialog >> text=Đã nhận thanh toán');
  await again.locator('.cd-paid h1').waitFor({ timeout: 8000 });
  check('display shows payment success with order code', (await again.locator('.cd-paid').innerText()).includes('DK-'));
  await again.screenshot({ path: path.join(OUT, '07-display-paid.png') });
});
await step('POS preorder for out-of-stock product', async () => {
  // E2E-SM-L received stock in the import test, so pre-order the other new variant (Be / 32, no stock).
  if (!(await pos.locator('.dk-dialog').count())) {
    await pos.fill('input[aria-label="Tìm sản phẩm bán hàng"]', 'kaki');
    await pos.locator('.pos-live-item.is-out', { hasText: 'Be / 32' }).waitFor({ timeout: 8000 });
    await pos.locator('.pos-live-item.is-out', { hasText: 'Be / 32' }).locator('text=Đặt trước').click();
  }
  await pos.locator('.dk-dialog').waitFor();
  await pos.click('.dk-dialog-footer >> text=Gửi đặt trước');
  check('preorder form validation inline', (await pos.locator('.dk-field-error').count()) >= 3);
  await pos.fill('.dk-dialog input[name=fullName]', 'Phạm Thị C');
  await pos.fill('.dk-dialog input[name=phone]', '0933444555');
  await pos.fill('.dk-dialog input[name=address]', '7 Nguyễn Trãi');
  await pos.click('.dk-dialog-footer >> text=Gửi đặt trước');
  await pos.locator('.preorder-code').waitFor({ timeout: 8000 });
  const code = await pos.locator('.preorder-code').innerText();
  check('preorder created with code', code.startsWith('PD-'), code);
  await pos.screenshot({ path: path.join(OUT, '08-preorder-success.png') });
});
await step('popup blocked handling', async () => {
  await pos.locator('.dk-dialog-footer >> text=Hoàn tất').click();
  await pos.locator('.dk-dialog').waitFor({ state: 'detached', timeout: 5000 });
  for (const other of posCtx.pages()) if (other !== pos) await other.close();
  await pos.evaluate(() => { window.open = () => null; });
  await pos.locator('button', { hasText: 'Màn hình khách hàng' }).click();
  await pos.locator('.dk-toast-warning').waitFor({ timeout: 5000 });
  check('popup blocked warning + fallback link', (await pos.locator('a.link', { hasText: 'Mở trong tab mới' }).count()) === 1);
});
await posCtx.close();

// 4. Demo uses the same UI -----------------------------------------------------
const demoCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const demo = await newPage(demoCtx);
let apiCalls = 0;
demo.on('request', (request) => { if (request.url().includes('/api/v1/') && !request.url().includes('/auth/refresh')) apiCalls++; });
await step('demo uses same screens without touching the API', async () => {
  await demo.goto(BASE + '#/demo');
  await demo.selectOption('.demo-role-form select', 'MANAGER');
  await demo.click('.demo-role-form button[type=submit]');
  await demo.waitForURL(/#\/admin\/dashboard/);
  await demo.goto(BASE + '#/admin/products');
  await demo.locator('text=+ Thêm sản phẩm').waitFor({ timeout: 8000 });
  await demo.click('text=+ Thêm sản phẩm');
  check('demo product form is the real ProductForm', (await demo.locator('.variant-table').count()) === 1);
  await demo.click('.dk-dialog-footer >> text=Hủy');
  await demo.goto(BASE + '#/admin/pos');
  await demo.locator('.pos-live-item').first().waitFor({ timeout: 8000 });
  check('demo POS is the real POS with customer display button', (await demo.locator('text=Màn hình khách hàng').count()) === 1);
  await demo.screenshot({ path: path.join(OUT, '09-demo-pos.png') });
  check('demo made no server API calls', apiCalls === 0, `calls=${apiCalls}`);
  await demo.goto(BASE + '#/catalog');
  await demo.locator('.catalog-product-card').first().waitFor({ timeout: 8000 });
  await demo.selectOption('select[aria-label="Tình trạng tồn kho"]', 'out');
  await demo.locator('.catalog-product-card >> text=Đặt trước').first().click();
  await demo.fill('input[name=name]', 'Khách Demo');
  await demo.fill('input[name=phone]', '0900111222');
  await demo.fill('input[name=address]', '1 Demo');
  await demo.click('text=Gửi đặt trước');
  await demo.locator('.preview-confirmation').waitFor({ timeout: 5000 });
  check('catalog pre-order creates demo order', (await demo.locator('.preview-confirmation').innerText()).includes('PD-DEMO-'));
  await demo.screenshot({ path: path.join(OUT, '10-catalog-preorder.png') });
});
await demoCtx.close();

await browser.close();
check('no uncaught page errors', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '));
const failed = results.filter(([status]) => status === 'FAIL');
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
