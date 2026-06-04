import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { buildCfgFromFormData, deriveFormDataFromCfg } from '../../src/menu_planner/ui_static/cfg_transform.js';

test('index page exposes dish allowed weekdays planning controls', () => {
  const html = readFileSync(new URL('../../src/menu_planner/ui_static/index.html', import.meta.url), 'utf8');

  assert.match(html, /菜色供應日設定（排菜設定）/);
  assert.match(html, /<details class="compact-help">/);
  assert.match(html, /aria-label="查看供應日說明"/);
  assert.match(html, /id="allowed_dish_search"/);
  assert.match(html, /id="allowed_dish_weekday_picker"/);
  assert.match(html, /id="allowed_dish_rules"/);
  assert.match(html, /id="allowed_dish_db_rules_btn"/);
  assert.match(html, /管理者在資料庫管理設定的「允許供應日」會在載入預設設定時自動帶入/);
  assert.match(html, /覆寫資料庫預設，只影響本次排菜 JSON，不會回寫資料庫/);
  assert.match(html, /星期一/);
  assert.match(html, /星期日/);
});

test('cfg transform round-trips dish allowed weekdays as hard planning config', () => {
  const cfg = buildCfgFromFormData(
    { hard: {}, soft: {}, schedule: {} },
    {
      horizonDays: 7,
      defaultPeople: 250,
      scheduleWeekdays: [1, 2, 3, 4, 5],
      forceIncludeDates: [],
      forceExcludeDates: [],
      peopleOverrides: {},
      costMin: 0,
      costMax: 999,
      meatTypes: ['chicken'],
      noConsecutiveMeat: true,
      weeklyQuota: { chicken: 2 },
      repeatLimits: {},
      preferInventory: false,
      preferExpiry: false,
      inventoryPreferIngredientIds: [],
      excludeDishIds: [],
      dishAllowedWeekdays: { wing: [3] },
    },
  );

  assert.deepEqual(cfg.hard.dish_allowed_weekdays, { wing: [3] });
  assert.deepEqual(deriveFormDataFromCfg(cfg).dishAllowedWeekdays, { wing: [3] });
});


test('dish suggestion controls disclose that keyword results are limited', () => {
  const html = readFileSync(new URL('../../src/menu_planner/ui_static/index.html', import.meta.url), 'utf8');
  const appJs = readFileSync(new URL('../../src/menu_planner/ui_static/app.js', import.meta.url), 'utf8');

  assert.match(html, /禁用菜色（搜尋加入）/);
  assert.match(html, /aria-label="查看禁用菜色說明"/);
  assert.match(html, /建議清單最多顯示前 12 筆/);
  assert.match(html, /下方已選限制清單就是本次排菜實際送出的限制/);
  assert.match(html, /刪除清單項目代表移除此菜色在本次排菜的限制/);
  assert.doesNotMatch(html, /晶片|點 chip/);
  assert.match(html, /菜色供應日設定（排菜設定）/);
  assert.match(appJs, /SUGGEST_RESULT_LIMIT = 12/);
  assert.match(appJs, /僅顯示前 \${items\.length} 筆，共 \${totalCount} 筆符合/);
});


test('index page can show database configured dish weekday rules modal', () => {
  const html = readFileSync(new URL('../../src/menu_planner/ui_static/index.html', import.meta.url), 'utf8');
  const appJs = readFileSync(new URL('../../src/menu_planner/ui_static/app.js', import.meta.url), 'utf8');

  assert.match(html, /查看資料庫已設定的菜色/);
  assert.match(appJs, /getCatalogDishAllowedWeekdayItems/);
  assert.match(appJs, /資料庫已設定允許供應日的菜色/);
  assert.match(appJs, /載入預設設定時會先帶入這些資料庫預設/);
  assert.match(appJs, /所有菜色皆視為全週可用/);
});


test('index page supports adding and deleting weekday role overrides', () => {
  const html = readFileSync(new URL('../../src/menu_planner/ui_static/index.html', import.meta.url), 'utf8');
  const appJs = readFileSync(new URL('../../src/menu_planner/ui_static/app.js', import.meta.url), 'utf8');
  const domJs = readFileSync(new URL('../../src/menu_planner/ui_static/dom.js', import.meta.url), 'utf8');

  assert.match(html, /id="weekday_role_add_select"/);
  assert.match(html, /id="weekday_role_add">新增週幾覆寫/);
  assert.match(html, /直接修改數量會同步到右側 JSON/);
  assert.match(html, /按「刪除」則恢復使用全域每日預設/);
  assert.match(html, /<th>操作<\/th>/);
  assert.match(html, /class="weekday-role-delete"/);
  assert.match(appJs, /function addWeekdayRoleOverride/);
  assert.match(appJs, /function renderWeekdayRoleOverrides/);
  assert.match(appJs, /DOM\.weekdayRoleAdd/);
  assert.match(appJs, /weekday-role-delete/);
  assert.match(domJs, /weekdayRoleAddSelect/);
  assert.match(domJs, /weekdayRoleTableBody/);
});
