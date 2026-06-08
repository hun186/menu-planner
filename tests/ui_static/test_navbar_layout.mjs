import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

for (const page of ['index.html', 'admin.html', 'inventory.html', 'account.html']) {
  test(`${page} includes fixed top navigation structure`, () => {
    const html = readFileSync(`src/menu_planner/ui_static/${page}`, 'utf8');
    assert.match(html, /class="top-nav"/);
    assert.match(html, /class="nav-toggle"/);
    assert.match(html, /id="primary-nav-links"/);
    assert.match(html, /<a href="\/account\.html">帳號管理<\/a>/);
    assert.match(html, /<script src="nav\.js"><\/script>/);
  });
}
