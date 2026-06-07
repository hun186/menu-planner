import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("result menu board expands with the menu table on narrow screens", () => {
  const html = readFileSync("src/menu_planner/ui_static/index.html", "utf8");
  const styles = readFileSync("src/menu_planner/ui_static/styles.css", "utf8");

  assert.match(html, /<section class="card full result-card">[\s\S]*<div id="result" class="result"><\/div>/);
  assert.match(styles, /@media \(max-width: 1100px\)\s*\{[\s\S]*\.result-card\s*\{[\s\S]*min-width\s*:\s*max\(100%, 860px\)\s*;/);
  assert.doesNotMatch(styles, /\.result\s*\{[\s\S]*overflow-x\s*:\s*auto\s*;[\s\S]*\}/);
  assert.doesNotMatch(styles, /\.result\s*>\s*\.tbl\s*\{[\s\S]*min-width/);
});
