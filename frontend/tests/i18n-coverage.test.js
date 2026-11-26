import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { auditProject, auditSource } from '../scripts/check-i18n.mjs';
import { translate } from '../src/i18n/index.js';

const en = JSON.parse(readFileSync(new URL('../src/locales/en.json', import.meta.url), 'utf8'));
const vi = JSON.parse(readFileSync(new URL('../src/locales/vi.json', import.meta.url), 'utf8'));

test('every rendered screen has an English translation and no hardcoded Vietnamese', () => {
  const { missing, hardcoded } = auditProject();
  const show = (items) => items.map((item) => `${item.file}:${item.line} ${item.text}`).join('\n');
  assert.deepEqual(missing, [], `Missing translations:\n${show(missing)}`);
  assert.deepEqual(hardcoded, [], `Hardcoded Vietnamese text:\n${show(hardcoded)}`);
});

test('the audit catches untranslated JSX text, attributes and unknown keys', () => {
  const { missing, hardcoded } = auditSource(`
    export function X({ t }) {
      return <div title="Tiêu đề chưa dịch">Nút chưa dịch {t('Khóa không tồn tại xyz')}{t('branch.not.there')}</div>;
    }`);
  assert.deepEqual(missing.map((item) => item.text), ['Khóa không tồn tại xyz', 'branch.not.there']);
  assert.deepEqual(hardcoded.map((item) => item.kind), ['attr:title', 'jsx-text']);
});

test('catalog values are never empty, so the UI never shows a blank label', () => {
  for (const [name, catalog] of [['en', en], ['vi', vi]]) {
    for (const [key, value] of Object.entries(catalog)) {
      assert.ok(typeof value === 'string' && value.trim(), `${name}.json has an empty value for ${key}`);
    }
  }
});

test('dotted keys resolve in both languages and placeholders are filled', () => {
  for (const key of Object.keys(en).filter((k) => /^[a-z][\w-]*(\.[\w-]+)+$/.test(k))) {
    assert.ok(Object.hasOwn(vi, key), `vi.json lacks ${key}`);
    assert.notEqual(translate(key, 'vi'), key);
    assert.notEqual(translate(key, 'en'), key);
  }
  assert.equal(translate({ key: 'order.cancel.title', values: { code: 'SO-1' } }, 'en'), 'Cancel order SO-1?');
  assert.equal(translate({ key: 'order.cancel.title', values: { code: 'SO-1' } }, 'vi'), 'Hủy đơn SO-1?');
});

test('no-branch empty state matches the agreed copy in both languages', () => {
  assert.equal(translate('branch.empty.title', 'vi'), 'Bạn chưa có chi nhánh hoạt động');
  assert.equal(translate('branch.empty.title', 'en'), 'No active branch found');
  assert.match(translate('branch.empty.description', 'en'), /at least one active branch/);
});

test('switching language back and forth returns the same strings', () => {
  const keys = ['Đăng nhập DKat', 'branch.empty.title', 'Hủy', 'Close', 'catalog.results'];
  const first = keys.map((key) => [translate(key, 'en'), translate(key, 'vi')]);
  for (let round = 0; round < 5; round += 1) {
    assert.deepEqual(keys.map((key) => [translate(key, 'en'), translate(key, 'vi')]), first);
  }
  assert.equal(translate('Close', 'vi'), 'Đóng');
});

test('system-generated stock movement notes are shown in the active language', async () => {
  const { systemNote } = await import('../src/i18n/index.js');
  assert.equal(translate(systemNote('Bán đơn DK-1'), 'en'), 'Sale DK-1');
  assert.equal(translate(systemNote('Bán đơn DK-1'), 'vi'), 'Bán đơn DK-1');
  assert.equal(translate(systemNote('Giao đơn PO-9'), 'en'), 'Pre-order handover PO-9');
  assert.equal(systemNote('Kiểm kê cuối ngày'), 'Kiểm kê cuối ngày', 'notes typed by users stay as written');
});
