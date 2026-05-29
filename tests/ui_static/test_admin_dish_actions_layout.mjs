import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('admin dish table keeps operation column after allowed weekdays column', () => {
  const html = readFileSync(new URL('../../src/menu_planner/ui_static/admin.html', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('../../src/menu_planner/ui_static/styles.css', import.meta.url), 'utf8');
  const adminJs = readFileSync(new URL('../../src/menu_planner/ui_static/admin.js', import.meta.url), 'utf8');

  assert.match(html, /<th>允許週幾<\/th>\s*<th[^>]*>成本<\/th>\s*<th>操作<\/th>/);
  assert.match(styles, /\.dish-tbl th:nth-child\(8\), \.dish-tbl td:nth-child\(8\)\{ width:18%; \}/);
  assert.match(styles, /\.tbl-scroll\{ width:100%; overflow-x:auto; \}/);
  assert.match(adminJs, /<button class="btn_edit" title="編輯">修<\/button>/);
  assert.match(adminJs, /<button class="btn_ing" title="編輯食材">材<\/button>/);
  assert.match(adminJs, /<button class="btn_del" title="刪除">刪<\/button>/);
});
