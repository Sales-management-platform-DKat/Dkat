import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getNavigationItems } from '../src/navigation.js';

const allowAll = () => true;

test('real accounts do not see the demo notification screen', () => {
  const items = getNavigationItems({ demoSession: false, allowed: allowAll });
  assert.equal(items.some(([id]) => id === 'notifications'), false);
});

test('the demo retains its local notification screen', () => {
  const items = getNavigationItems({ demoSession: true, allowed: allowAll });
  assert.equal(items.some(([id]) => id === 'notifications'), true);
});
