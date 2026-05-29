import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { buildCfgFromFormData, deriveFormDataFromCfg } from '../../src/menu_planner/ui_static/cfg_transform.js';

test('index page exposes dish allowed weekdays planning controls', () => {
  const html = readFileSync(new URL('../../src/menu_planner/ui_static/index.html', import.meta.url), 'utf8');

  assert.match(html, /菜色允許供應週幾（排菜設定）/);
  assert.match(html, /id="allowed_dish_search"/);
  assert.match(html, /id="allowed_dish_weekday_picker"/);
  assert.match(html, /id="allowed_dish_rules"/);
  assert.match(html, /週一/);
  assert.match(html, /週日/);
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
  assert.match(html, /建議清單最多顯示前 12 筆/);
  assert.match(html, /菜色允許供應週幾（排菜設定）/);
  assert.match(appJs, /SUGGEST_RESULT_LIMIT = 12/);
  assert.match(appJs, /僅顯示前 \${items\.length} 筆，共 \${totalCount} 筆符合/);
});
