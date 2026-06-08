import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('index subtitle describes flexible roles and newer constraints', () => {
  const html = readFileSync('src/menu_planner/ui_static/index.html', 'utf8');
  assert.match(html, /每日數量設定與週幾覆寫/);
  assert.match(html, /備菜時間上限/);
  assert.match(html, /可解釋打分/);
  assert.match(html, /匯出 Excel/);
});
