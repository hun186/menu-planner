import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("result menu table stays inside a horizontally scrollable result board", () => {
  const html = readFileSync("src/menu_planner/ui_static/index.html", "utf8");
  const styles = readFileSync("src/menu_planner/ui_static/styles.css", "utf8");

  assert.match(html, /<section class="card full">[\s\S]*<div id="result" class="result"><\/div>/);
  assert.match(styles, /\.result\s*\{[\s\S]*overflow-x\s*:\s*auto\s*;/);
  assert.match(styles, /\.result\s*>\s*\.tbl\s*\{[\s\S]*min-width\s*:\s*860px\s*;/);
});
