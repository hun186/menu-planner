import test from "node:test";
import assert from "node:assert/strict";

import { renderResult } from "../../src/menu_planner/ui_static/render.js";

function renderToHtml(result, cfg = { people: 250 }) {
  let renderedHtml = "";
  global.$ = (selector) => {
    assert.equal(selector, "#result");
    return {
      html(value) {
        renderedHtml = String(value || "");
      },
    };
  };

  renderResult(result, cfg, { editable: true });
  return renderedHtml;
}

function oneDayResult({ date = "2026-03-21", sides = [] } = {}) {
  return {
    summary: { days: 1, total_cost: 0, avg_cost_per_day: 0, total_score: 0 },
    days: [
      {
        day_index: 0,
        date,
        is_scheduled: true,
        items: {
          main: { id: "m1", name: "主菜A" },
          sides,
          veg: { id: "", name: "" },
          soup: { id: "", name: "" },
          fruit: { id: "", name: "" },
        },
        day_cost: 0,
        score: 0,
        score_breakdown: {},
      },
    ],
    errors: [],
  };
}

test("renderResult: editable mode keeps default side selectors when sides are empty", () => {
  const renderedHtml = renderToHtml(oneDayResult());

  assert.match(renderedHtml, /data-role="side"/);
  assert.match(renderedHtml, /data-slot="side_0"/);
  assert.match(renderedHtml, /data-slot="side_1"/);
});

test("renderResult: editable side selectors follow per-weekday side count", () => {
  const renderedHtml = renderToHtml(
    oneDayResult({
      date: "2026-03-18",
      sides: [{ id: "s1", name: "配菜一" }],
    }),
    {
      people: 250,
      per_day_roles: { side: 3 },
      per_weekday_roles: {
        3: { side: 1 },
      },
    },
  );

  assert.match(renderedHtml, /data-slot="side_0"/);
  assert.doesNotMatch(renderedHtml, /data-slot="side_1"/);
  assert.doesNotMatch(renderedHtml, /（選擇配菜2）/);
});


test("renderResult: editable mode renders empty selectors for every configured role slot", () => {
  const renderedHtml = renderToHtml(
    oneDayResult({ date: "2026-03-18" }),
    {
      people: 250,
      per_day_roles: { main: 1, noodle: 1, side: 2, veg: 1, soup: 1, fruit: 1 },
      per_weekday_roles: {
        3: { main: 1, noodle: 1, side: 2, veg: 1, soup: 1, fruit: 1 },
      },
    },
  );

  for (const role of ["main", "noodle", "veg", "soup", "fruit"]) {
    assert.match(renderedHtml, new RegExp(`data-role="${role}"`));
  }
  assert.match(renderedHtml, /（選擇純蔬1）/);
  assert.match(renderedHtml, /（選擇湯品1）/);
  assert.match(renderedHtml, /（選擇水果1）/);
});


test("renderResult: editable mode renders remaining selectors when configured count exceeds scheduled items", () => {
  const renderedHtml = renderToHtml(
    oneDayResult({
      date: "2026-03-18",
      sides: [{ id: "s1", name: "配菜一" }],
    }),
    {
      people: 250,
      per_day_roles: { main: 5, noodle: 5, side: 5, veg: 5, soup: 5, fruit: 5 },
      per_weekday_roles: {
        3: { main: 5, noodle: 5, side: 5, veg: 5, soup: 5, fruit: 5 },
      },
    },
  );

  for (const slot of ["main_1", "main_2", "main_3", "main_4"]) {
    assert.match(renderedHtml, new RegExp(`data-slot="${slot}"`));
  }
  for (const role of ["noodle", "veg", "soup", "fruit"]) {
    assert.match(renderedHtml, new RegExp(`data-role="${role}"[^>]+data-slot="${role}"`));
    for (const suffix of [1, 2, 3, 4]) {
      assert.match(renderedHtml, new RegExp(`data-slot="${role}_${suffix}"`));
    }
  }
  for (const suffix of [1, 2, 3, 4]) {
    assert.match(renderedHtml, new RegExp(`data-slot="side_${suffix}"`));
  }
  assert.match(renderedHtml, /配菜一/);
  assert.match(renderedHtml, /（選擇配菜5）/);
  assert.match(renderedHtml, /（選擇純蔬5）/);
});
