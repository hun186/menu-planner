import test from "node:test";
import assert from "node:assert/strict";

import { shouldRenderFailedRow } from "../../src/menu_planner/ui_static/render.js";

test("shouldRenderFailedRow: keep normal row when partial dishes exist", () => {
  const day = {
    failed: true,
    items: {
      sides: [{ id: "s1", name: "配菜一" }, { id: "s2", name: "配菜二" }],
      veg: { id: "", name: "" },
      soup: { id: "", name: "" },
      fruit: { id: "f1", name: "香蕉" },
    },
  };

  assert.equal(shouldRenderFailedRow(day, [{ code: "SOUP_NO_SOLUTION" }]), false);
});

test("shouldRenderFailedRow: render failed row when all non-main slots are empty", () => {
  const day = {
    failed: true,
    items: {
      sides: [],
      veg: { id: "", name: "" },
      soup: { id: "", name: "" },
      fruit: { id: "", name: "" },
    },
  };

  assert.equal(shouldRenderFailedRow(day, [{ code: "SOUP_NO_SOLUTION" }]), true);
});
