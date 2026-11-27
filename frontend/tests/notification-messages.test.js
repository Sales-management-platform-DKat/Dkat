// Notification copy: messages follow the active language, API reasons are kept,
// provider errors become readable, and toasts are not duplicated.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { errorMessage, translate } from '../src/i18n/index.js';
import { ApiError, errorFromResponse } from '../src/lib/api-errors.js';
import { deliveryErrorKey } from '../src/features/preorders/notification-errors.js';
import { getToasts, notify, dismissToast } from '../src/components/overlay/toast.js';

const en = JSON.parse(readFileSync(new URL('../src/locales/en.json', import.meta.url), 'utf8'));
const vi = JSON.parse(readFileSync(new URL('../src/locales/vi.json', import.meta.url), 'utf8'));
const VIETNAMESE = /[À-ỹđĐ]/;

test('backend messages with values are shown in the active language', () => {
  const branch = "Mã chi nhánh 'CN01' đã tồn tại trong cửa hàng";
  assert.equal(translate(branch, 'en'), "Branch code 'CN01' already exists in this store. Use a different code.");
  assert.match(translate(branch, 'vi'), /^Mã chi nhánh 'CN01' đã tồn tại/);
  assert.equal(translate('SKU "ATB-DEN-M" đã có ở dòng 3; số lượng sẽ được cộng dồn', 'en'),
    'SKU "ATB-DEN-M" already appears on row 3; the quantities will be added together.');
  assert.match(translate('Không thể ngừng hoạt động: chi nhánh còn 2 đơn đặt trước chưa hoàn tất', 'en'), /2 pre-orders are still open/);
  // User data that merely contains Vietnamese is left alone.
  assert.equal(translate('Nguyễn Minh Anh', 'en'), 'Nguyễn Minh Anh');
});

test('every message lib/api-errors.js can produce has an English translation', () => {
  const source = readFileSync(new URL('../src/lib/api-errors.js', import.meta.url), 'utf8');
  const messages = [...source.matchAll(/'([^'\n]*[À-ỹđĐ][^'\n]*)'/g)].map((match) => match[1]);
  assert.ok(messages.length > 30);
  for (const message of messages) assert.ok(Object.hasOwn(en, message), `en.json lacks "${message}"`);
});

test('static backend messages reaching the UI have English copy', () => {
  for (const message of ['Mật khẩu hiện tại không đúng.', 'Phiên đăng nhập đã hết hạn.', 'Không thể tự khóa tài khoản của chính mình',
    'Bạn không có quyền thay đổi tồn kho.', 'Chỉ được gửi 5 yêu cầu trong 10 phút mỗi IP']) {
    assert.ok(!VIETNAMESE.test(translate(message, 'en')), message);
  }
});

test('a specific API reason is kept instead of the generic fallback', () => {
  const error = errorFromResponse(409, { detail: 'Không thể khóa chủ cửa hàng duy nhất đang hoạt động' });
  assert.equal(errorMessage(error, 'Không cập nhật được.'), 'Không thể khóa chủ cửa hàng duy nhất đang hoạt động');
  assert.equal(translate(errorMessage(error), 'en'), "You can't lock the only active store owner.");
  // Something that is not a user-facing message still falls back.
  assert.equal(errorMessage(new Error('TypeError: x is undefined'), 'Không tải được.'), 'Không tải được.');
  assert.ok(error instanceof ApiError);
});

test('provider error codes become a reason staff can act on, in both languages', () => {
  const cases = {
    'NOT_CONFIGURED: thiếu ESMS_API_KEY': 'preorder.notification.error.notConfigured',
    'SMTP_AUTH_FAILED: 535': 'preorder.notification.error.account',
    'TIMEOUT: 10s': 'preorder.notification.error.connection',
    'INVALID_PHONE: 0123': 'preorder.notification.error.phone',
    'RETRY_EXHAUSTED: đã gửi lại 3 lần': 'preorder.notification.error.exhausted',
    'SOMETHING_NEW': 'preorder.notification.error.unknown',
  };
  for (const [raw, key] of Object.entries(cases)) {
    assert.equal(deliveryErrorKey(raw), key, raw);
    assert.ok(Object.hasOwn(en, key) && Object.hasOwn(vi, key), key);
    assert.ok(!VIETNAMESE.test(translate(key, 'en')), key);
  }
  assert.equal(deliveryErrorKey(null), '');
});

test('toasts keep keys until rendered and the same message is not stacked', () => {
  getToasts().forEach((item) => dismissToast(item.id));
  notify.success({ key: 'preorder.toast.paid', values: { code: 'PD-1' } });
  notify.success({ key: 'preorder.toast.paid', values: { code: 'PD-1' } });
  notify.error({ key: 'preorder.notification.error.unknown' }, { title: 'Gửi lại không thành công' });
  const [paid, failed] = getToasts();
  assert.equal(getToasts().length, 2);
  assert.equal(paid.repeat, 2);
  assert.equal(translate(paid.message, 'en'), 'Payment recorded for pre-order PD-1.');
  assert.equal(translate(paid.message, 'vi'), 'Đã ghi nhận thanh toán cho đơn đặt trước PD-1.');
  assert.equal(translate(failed.title, 'en'), 'Resend failed');
  assert.equal(translate(failed.message, 'en'), 'Delivery failed. Please try resending.');
  // Default titles are translated too.
  assert.ok(!VIETNAMESE.test(translate(paid.title, 'en')));
  getToasts().forEach((item) => dismissToast(item.id));
});

test('only one confirmation host is mounted, so a confirmation opens one dialog', () => {
  const main = readFileSync(new URL('../src/main.jsx', import.meta.url), 'utf8');
  assert.equal(main.match(/<ConfirmHost\s*\/>/g)?.length, 1);
  assert.doesNotMatch(main, /components\/confirm\.jsx/);
  const legacy = readFileSync(new URL('../src/components/confirm.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(legacy, /addEventListener/);
});
