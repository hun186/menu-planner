import test from "node:test";
import assert from "node:assert/strict";

import { renderResult } from "../../src/menu_planner/ui_static/render.js";

test("renderResult: editable mode keeps side selectors when sides are empty", () => {
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
          sides: [],
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

  renderResult(result, { people: 250 }, { editable: true });

  assert.match(renderedHtml, /data-role="side"/);
  assert.match(renderedHtml, /data-slot="side_0"/);
  assert.match(renderedHtml, /data-slot="side_1"/);
});
