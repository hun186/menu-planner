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


test('daily role counts use the same compact role-column layout as weekday overrides', () => {
  const html = readFileSync(new URL('../../src/menu_planner/ui_static/index.html', import.meta.url), 'utf8');

  assert.match(html, /<table class="mini-table role-counts-table" id="daily_role_counts_table">/);
  assert.match(html, /<table class="mini-table role-counts-table" id="weekday_role_counts_table">/);
  assert.match(html, /<th>設定<\/th><th>主菜<\/th><th>麵食<\/th><th>配菜<\/th><th>純蔬<\/th><th>湯<\/th><th>水果<\/th>/);
  assert.match(html, /<tr><td>全域每日預設<\/td>/);
  assert.match(html, /aria-label="全域每日預設主菜數量"/);
  assert.match(html, /aria-label="全域每日預設水果數量"/);
  assert.doesNotMatch(html, /<thead><tr><th>角色<\/th><th>全域每日預設<\/th><\/tr><\/thead>/);
});


test('repeat limit controls include all split menu roles', () => {
  const html = readFileSync(new URL('../../src/menu_planner/ui_static/index.html', import.meta.url), 'utf8');

  assert.match(html, /麵食 7 天重複上限/);
  assert.match(html, /data-key="max_same_noodle_in_7_days"/);
  assert.match(html, /麵食 30 天重複上限/);
  assert.match(html, /data-key="max_same_noodle_in_30_days"/);
  assert.match(html, /純蔬 7 天重複上限/);
  assert.match(html, /data-key="max_same_veg_in_7_days"/);
});


test('weekly meat quotas use meat-type columns and repeat limits use paired rows', () => {
  const html = readFileSync(new URL('../../src/menu_planner/ui_static/index.html', import.meta.url), 'utf8');

  assert.match(html, /<table class="mini-table quota-matrix-table" id="weekly_quota_table">/);
  assert.match(html, /<tr><th>每週上限<\/th><th>雞<\/th><th>豬<\/th><th>牛<\/th><th>海鮮<\/th><th>素<\/th><\/tr>/);
  assert.match(html, /<td>主菜數<\/td>/);
  assert.match(html, /aria-label="雞每週上限"/);
  assert.doesNotMatch(html, /<tr><td>雞<\/td><td><input class="quota"/);

  assert.match(html, /<table class="mini-table repeat-limits-table" id="repeat_limits_table">/);
  assert.match(html, /<tr><th>限制項目<\/th><th>數值<\/th><th>限制項目<\/th><th>數值<\/th><\/tr>/);
  assert.match(html, /以兩欄並排呈現，保留完整限制名稱，同時減少垂直捲動/);
  assert.match(html, /主菜 30 天重複上限<\/td><td><input class="repeat-limit"[\s\S]+麵食 7 天重複上限/);
  assert.match(html, /食材窗口天數<\/td><td><input class="repeat-limit"[\s\S]+食材連續天數上限/);
});


test('settings board reserves enough width for dense constraint tables', () => {
  const html = readFileSync(new URL('../../src/menu_planner/ui_static/index.html', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('../../src/menu_planner/ui_static/styles.css', import.meta.url), 'utf8');

  assert.match(html, /<div class="grid planner-grid">/);
  assert.match(styles, /--planner-settings-board-min-width\s*:\s*672px\s*;/);
  assert.match(styles, /--planner-settings-table-min-width\s*:\s*640px\s*;/);
  assert.match(styles, /\.planner-grid\s*\{[\s\S]*grid-template-columns\s*:\s*minmax\(var\(--planner-settings-board-min-width\), 1fr\) minmax\(0, 1fr\)\s*;/);
  assert.match(styles, /\.planner-settings-card\s*\{[\s\S]*min-width\s*:\s*max\(100%, var\(--planner-settings-board-min-width\)\)\s*;/);
  assert.match(
    styles,
    new RegExp('\\.quota-matrix-table,\\n\\.repeat-limits-table,\\n#daily_role_counts_table,\\n#weekday_role_counts_table\\s*\\{[\\s\\S]*min-width\\s*:\\s*var\\(--planner-settings-table-min-width\\)\\s*;'),
  );
});
