import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const html = fs.readFileSync(new URL('../../src/menu_planner/ui_static/admin.html', import.meta.url), 'utf8');
const apiJs = fs.readFileSync(new URL('../../src/menu_planner/ui_static/admin/api.js', import.meta.url), 'utf8');
const httpJs = fs.readFileSync(new URL('../../src/menu_planner/ui_static/shared/http.js', import.meta.url), 'utf8');

test('admin page exposes account login, registration, and approval UI', () => {
  assert.match(html, /<h2>帳號與管理權限<\/h2>/);
  assert.match(html, /id="auth_login"[^>]*>登入<\/button>/);
  assert.match(html, /id="auth_register"[^>]*>註冊帳號<\/button>/);
  assert.match(html, /<h3 class="h3">帳號審核<\/h3>/);
  assert.doesNotMatch(html, /Admin Key|X-Admin-Key|MENU_ADMIN_KEY/);
});

test('admin API helpers use auth endpoints and bearer-compatible http helper', () => {
  assert.match(apiJs, /\/v1\/auth\/login/);
  assert.match(apiJs, /\/v1\/auth\/register/);
  assert.match(apiJs, /\/v1\/auth\/users/);
  assert.match(httpJs, /headers\.Authorization = `Bearer \$\{token\}`/);
  assert.match(httpJs, /menu_auth_token/);
});
