import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const adminHtml = readFileSync('src/menu_planner/ui_static/admin.html', 'utf8');
const adminJs = readFileSync('src/menu_planner/ui_static/admin.js', 'utf8');

test('unit conversion factor input and table use two decimal precision in the UI', () => {
  assert.match(adminHtml, /id="conv_factor" type="number" step="0\.01"/);
  assert.match(adminJs, /Number\(row\.factor \|\| 0\)\.toFixed\(2\)/);
  assert.doesNotMatch(adminJs, /toFixed\(6\)/);
});
