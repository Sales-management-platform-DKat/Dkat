import test from 'node:test';
import assert from 'node:assert/strict';
import { demoVariantLabel, errorMessage, translate } from '../src/i18n/index.js';
import { fieldValidationMessage } from '../src/components/form-validation.js';
import { importProducts } from '../src/csv.js';
import englishCatalog from '../src/locales/en.json' with { type: 'json' };
import vietnameseCatalog from '../src/locales/vi.json' with { type: 'json' };

test('brand slogan follows the selected locale', () => {
  assert.equal(translate('Digital Key To All.', 'en'), 'Digital Key To All');
  assert.equal(translate('Digital Key To All.', 'vi'), 'Nền Tảng Số Hóa Thương Mại Tự Động');
});

test('legacy Vietnamese mojibake is repaired and translated centrally', () => {
  assert.equal(translate('Quáº£n lý', 'vi'), 'Quản lý');
  assert.equal(translate('Ä‘ang hoáº¡t Ä‘á»™ng', 'vi'), 'đang hoạt động');
  assert.equal(translate('Quáº£n lý chi nhánh', 'en'), 'Branch management');
});

test('demo amounts use English VND number formatting', () => {
  assert.equal(translate('28.640.000 ₫', 'en'), new Intl.NumberFormat('en-US', { style: 'currency', currency: 'VND' }).format(28640000));
  assert.equal(translate('12,8 triệu', 'en'), '12.8 million');
});

test('literal English UI copy resolves back to Vietnamese through the shared catalogs', () => {
  assert.equal(translate('Explore the demo', 'vi'), 'Trải nghiệm bản demo');
  assert.equal(translate('Overview', 'vi'), 'Tổng quan');
  assert.equal(translate('Quản lý chi nhánh', 'en'), 'Branch management');
  assert.equal(translate('Preorder created: {code}', 'vi', { code: 'PRE-001' }), 'Đã tạo đơn: PRE-001');
});

test('dynamic messages preserve names even when a name matches a translation key', () => {
  const name = 'Sản phẩm';
  const values = { name };
  assert.equal(translate('demo.preorder.title', 'en', values), 'Preorder Sản phẩm');
  assert.equal(translate('demo.preorder.title', 'vi', values), 'Đặt trước Sản phẩm');
  assert.equal(demoVariantLabel(name, (key) => translate(key, 'en')), name);
  assert.equal(demoVariantLabel('Đen', (key) => translate(key, 'en')), 'Black');
});

test('a stored CSV error can be rendered in both languages', () => {
  assert.throws(
    () => importProducts({ variants: [] }, 'name,sku,category,color,size,price\nExample,SKU'),
    (error) => {
      const message = errorMessage(error);
      assert.equal(translate(message, 'en'), 'Row 2 must have 6 columns.');
      assert.equal(translate(message, 'vi'), 'Dòng 2 cần có 6 cột.');
      return true;
    },
  );
});

test('API errors translate known codes and use localized fallbacks for unknown messages', () => {
  const error = Object.assign(new Error('Inventory validation failed'), { code: 'INSUFFICIENT_STOCK' });
  const message = errorMessage(error);
  assert.equal(translate(message, 'en'), 'Not enough available stock.');
  assert.equal(translate(message, 'vi'), 'Không đủ tồn kho khả dụng.');
  const fallback = errorMessage(new Error('Unexpected server response'), 'Không tải được dữ liệu kho.');
  assert.equal(translate(fallback, 'en'), 'Could not load inventory.');
  assert.equal(translate(fallback, 'vi'), 'Không tải được dữ liệu kho.');
});

test('interpolated messages use matching placeholders in both catalogs', () => {
  const placeholders = (message) => Array.from(message.matchAll(/\{(\w+)\}/g), ([, name]) => name).sort();
  for (const [key, message] of Object.entries(englishCatalog)) {
    const names = placeholders(message);
    if (!names.length) continue;
    assert.ok(Object.hasOwn(vietnameseCatalog, key), key);
    assert.deepEqual(placeholders(vietnameseCatalog[key]), names, key);
  }
});

test('form constraints map to localized messages with actionable details', () => {
  const missingSelect = fieldValidationMessage({ tagName: 'SELECT', validity: { valueMissing: true } });
  assert.equal(translate(missingSelect, 'vi'), 'Chọn một mục.');
  assert.equal(translate(missingSelect, 'en'), 'Select an option.');

  const minimum = fieldValidationMessage({ type: 'number', min: '1', validity: { rangeUnderflow: true } });
  assert.equal(translate(minimum, 'vi'), 'Giá trị phải từ 1 trở lên.');
  assert.equal(translate(minimum, 'en'), 'The value must be at least 1.');

  const email = fieldValidationMessage({ type: 'email', validity: { patternMismatch: true } });
  assert.equal(translate(email, 'vi'), 'Vui lòng nhập địa chỉ email hợp lệ.');
  assert.equal(translate(email, 'en'), 'Enter a valid email address.');

  const username = fieldValidationMessage({ name: 'owner_username', validity: { patternMismatch: true } });
  assert.match(translate(username, 'vi'), /3 đến 32 ký tự/);
});
