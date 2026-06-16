import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const adminHtml = fs.readFileSync(new URL('../../src/menu_planner/ui_static/admin.html', import.meta.url), 'utf8');
const accountHtml = fs.readFileSync(new URL('../../src/menu_planner/ui_static/account.html', import.meta.url), 'utf8');
const accountJs = fs.readFileSync(new URL('../../src/menu_planner/ui_static/account.js', import.meta.url), 'utf8');
const navJs = fs.readFileSync(new URL('../../src/menu_planner/ui_static/nav.js', import.meta.url), 'utf8');
const apiJs = fs.readFileSync(new URL('../../src/menu_planner/ui_static/admin/api.js', import.meta.url), 'utf8');
const httpJs = fs.readFileSync(new URL('../../src/menu_planner/ui_static/shared/http.js', import.meta.url), 'utf8');

test('account page exposes login, registration, approval, and permission guidance UI', () => {
  assert.doesNotMatch(adminHtml, /<h2>帳號與管理權限<\/h2>/);
  assert.match(accountHtml, /<h2>帳號與管理權限<\/h2>/);
  assert.match(accountHtml, /id="auth_login"[^>]*>登入<\/button>/);
  assert.match(accountHtml, /id="auth_register"[^>]*>註冊帳號<\/button>/);
  assert.match(accountHtml, /<h3 class="h3">帳號審核<\/h3>/);
  assert.match(accountHtml, /未登入訪客/);
  assert.match(accountHtml, /資料修改者（data_editor）/);
  assert.match(accountHtml, /資料庫操作者（db_operator）/);
  assert.match(accountHtml, /最高級全能者（superuser）/);
  assert.match(accountHtml, /role="tooltip"/);
  assert.doesNotMatch(accountHtml, /Admin Key|X-Admin-Key|MENU_ADMIN_KEY/);
});

test('account and nav scripts surface role-aware auth status', () => {
  assert.match(accountJs, /permissionSummary/);
  assert.match(accountJs, /資料維護需要資料修改者以上權限/);
  assert.match(accountJs, /資料庫操作者/);
  assert.match(accountJs, /不能審核帳號、還原或刪除備份/);
  assert.match(accountJs, /db_operator/);
  assert.match(navJs, /nav-auth-status/);
  assert.match(navJs, /帳號等級/);
});

test('admin API helpers use auth endpoints and bearer-compatible http helper', () => {
  assert.match(apiJs, /\/v1\/auth\/login/);
  assert.match(apiJs, /\/v1\/auth\/register/);
  assert.match(apiJs, /\/v1\/auth\/users/);
  assert.match(httpJs, /headers\.Authorization = `Bearer \$\{token\}`/);
  assert.match(httpJs, /menu_auth_token/);
});
