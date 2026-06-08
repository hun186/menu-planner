import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const adminHtml = readFileSync('src/menu_planner/ui_static/admin.html', 'utf8');
const styles = readFileSync('src/menu_planner/ui_static/styles.css', 'utf8');

test('dish management table keeps an explicit operation column after cost column', () => {
  const dishTableMatch = adminHtml.match(/<table class="tbl dish-tbl"[\s\S]*?<thead>([\s\S]*?)<\/thead>/);
  assert.ok(dishTableMatch, 'expected dish table header to exist');

  const headers = [...dishTableMatch[1].matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/g)]
    .map((match) => match[1].replace(/<[^>]+>/g, '').trim());

  assert.deepEqual(headers, ['ID', '名稱', '角色', '肉類', '菜系', '允許供應日', '備菜時間', '成本', '操作']);
  assert.match(styles, /\.dish-tbl th:nth-child\(9\), \.dish-tbl td:nth-child\(9\)\{ width:14%; \}/);
});

test('dish table widths include action buttons without over-allocating columns', () => {
  const widths = [...styles.matchAll(/\.dish-tbl th:nth-child\(\d+\), \.dish-tbl td:nth-child\(\d+\)\{ width:(\d+)%; \}/g)]
    .map((match) => Number(match[1]));

  assert.equal(widths.length, 9, 'expected explicit widths for all dish table columns');
  assert.equal(widths.reduce((sum, width) => sum + width, 0), 100);
  assert.ok(widths[7] >= 10, 'cost column should be wide enough to keep numbers on one line');
  assert.ok(widths[8] >= 14, 'operation column should still reserve enough width for compact row action buttons');
  assert.match(styles, /\.tbl-scroll\{ width:100%; overflow-x:auto; \}/);
});


test('dish cost warning badge wraps inside cost column without overlapping actions', () => {
  const adminJs = readFileSync('src/menu_planner/ui_static/admin.js', 'utf8');

  assert.match(adminJs, /<td class="dish-cost-cell">\s*<span class="dish-cost-line"><span class="dish-cost-value">/);
  assert.match(styles, /\.dish-tbl td\.dish-cost-cell\{[\s\S]*white-space:normal;[\s\S]*overflow-wrap:anywhere;[\s\S]*\}/);
  assert.match(styles, /\.dish-cost-line\{[\s\S]*display:inline-flex;[\s\S]*flex-wrap:wrap;[\s\S]*\}/);
  assert.match(styles, /\.dish-cost-value\{[\s\S]*white-space:nowrap;[\s\S]*\}/);
});


test('dish editor exposes prep minutes input and save payload field', () => {
  const adminJs = readFileSync('src/menu_planner/ui_static/admin.js', 'utf8');

  assert.match(adminHtml, /<label>備菜時間（分鐘）<\/label><input id="dish_prep_minutes" type="number" min="0" step="1" value="0" \/>/);
  assert.match(adminJs, /prep_minutes: Number\(\$\("#dish_prep_minutes"\)\.val\(\) \|\| 0\)/);
  assert.match(adminJs, /菜色：備菜時間（分鐘）必須是不可小於 0 的整數。/);
});
