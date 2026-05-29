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

  assert.deepEqual(headers, ['ID', '名稱', '角色', '肉類', '菜系', '允許週幾', '成本', '操作']);
  assert.match(styles, /\.dish-tbl th:nth-child\(8\), \.dish-tbl td:nth-child\(8\)\{ width:18%; \}/);
});

test('dish table widths include action buttons without over-allocating columns', () => {
  const widths = [...styles.matchAll(/\.dish-tbl th:nth-child\(\d+\), \.dish-tbl td:nth-child\(\d+\)\{ width:(\d+)%; \}/g)]
    .map((match) => Number(match[1]));

  assert.equal(widths.length, 8, 'expected explicit widths for all dish table columns');
  assert.equal(widths.reduce((sum, width) => sum + width, 0), 100);
  assert.ok(widths[7] >= 18, 'operation column should reserve enough width for row action buttons');
  assert.match(styles, /\.tbl-scroll\{ width:100%; overflow-x:auto; \}/);
});
