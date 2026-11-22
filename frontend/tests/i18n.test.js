import test from 'node:test';
import assert from 'node:assert/strict';
import { translate } from '../src/i18n/index.js';

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
