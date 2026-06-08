import test from "node:test";
import assert from "node:assert/strict";

import { renderResult } from "../../src/menu_planner/ui_static/render.js";

test("renderResult: displays all dishes from multi-count role arrays", () => {
  let renderedHtml = "";
  global.$ = (selector) => {
    assert.equal(selector, "#result");
    return {
      html(value) {
        renderedHtml = String(value || "");
      },
    };
  };

  const result = {
    summary: { days: 1, total_cost: 0, avg_cost_per_day: 0, total_score: 0 },
    days: [
      {
        day_index: 0,
        date: "2026-03-21",
        is_scheduled: true,
        items: {
          main: { id: "m1", name: "主菜A" },
          mains: [{ id: "m1", name: "主菜A" }, { id: "m2", name: "主菜B" }],
          noodle: { id: "n1", name: "麵食A" },
          noodles: [{ id: "n1", name: "麵食A" }, { id: "n2", name: "麵食B" }],
          sides: [{ id: "s1", name: "配菜A" }, { id: "s2", name: "配菜B" }, { id: "s3", name: "配菜C" }],
          veg: { id: "v1", name: "純蔬A" },
          vegs: [{ id: "v1", name: "純蔬A" }, { id: "v2", name: "純蔬B" }],
          soup: { id: "so1", name: "湯品A" },
          soups: [{ id: "so1", name: "湯品A" }, { id: "so2", name: "湯品B" }],
          fruit: { id: "f1", name: "水果A" },
          fruits: [{ id: "f1", name: "水果A" }, { id: "f2", name: "水果B" }],
        },
        day_cost: 0,
        score: 0,
        score_breakdown: {},
      },
    ],
    errors: [],
  };

  renderResult(result, { people: 250 }, { editable: false });

  for (const name of ["主菜A、主菜B", "麵食A、麵食B", "配菜A、配菜B、配菜C", "純蔬A、純蔬B", "湯品A、湯品B", "水果A、水果B"]) {
    assert.match(renderedHtml, new RegExp(name));
  }
});


test("renderResult: adds weekday column and highlights weekend offdays", () => {
  let renderedHtml = "";
  global.$ = (selector) => {
    assert.equal(selector, "#result");
    return {
      html(value) {
        renderedHtml = String(value || "");
      },
    };
  };

  const result = {
    summary: { days: 2, total_cost: 0, avg_cost_per_day: 0, total_score: 0 },
    days: [
      { day_index: 0, date: "2026-03-21", is_scheduled: false, items: {} },
      { day_index: 1, date: "2026-03-23", is_scheduled: true, items: {}, day_cost: 0, score: 0, score_breakdown: {} },
    ],
    errors: [],
  };

  renderResult(result, { people: 250 }, { editable: false });

  assert.match(renderedHtml, /<th>日期<\/th><th>週幾<\/th><th>人數<\/th>/);
  assert.match(renderedHtml, /<tr class="row-offday row-weekend-offday">[\s\S]*<td class="weekday-cell">六<\/td>/);
  assert.match(renderedHtml, /<td class="weekday-cell">一<\/td>/);
  assert.match(renderedHtml, /<td colspan="11">[\s\S]*可解釋明細/);
});
