import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("result menu board expands with the menu table on narrow screens", () => {
  const html = readFileSync("src/menu_planner/ui_static/index.html", "utf8");
  const styles = readFileSync("src/menu_planner/ui_static/styles.css", "utf8");

  assert.match(html, /<section class="card full result-card">[\s\S]*<div id="result" class="result"><\/div>/);
  assert.match(styles, /@media \(max-width: 1100px\)\s*\{[\s\S]*\.result-card\s*\{[\s\S]*min-width\s*:\s*max\(100%, 860px\)\s*;/);
  assert.match(styles, /\.result\s*\{[\s\S]*overflow-x\s*:\s*auto\s*;[\s\S]*\}/);
  assert.match(styles, /\.result\s*>\s*\.tbl\s*\{[\s\S]*min-width\s*:\s*860px\s*;/);
});

test("result menu table reserves compact date and people columns", () => {
  const render = readFileSync("src/menu_planner/ui_static/render.js", "utf8");
  const styles = readFileSync("src/menu_planner/ui_static/styles.css", "utf8");

  assert.match(render, /<table class="tbl result-menu-table">[\s\S]*<col class="result-date-col" \/>[\s\S]*<col class="result-weekday-col" \/>[\s\S]*<col class="result-people-col" \/>/);
  assert.match(render, /class="day-people-input" type="number" min="1" max="9999"/);
  assert.match(styles, /--result-date-col-width\s*:\s*calc\(13ch \+ 16px\)\s*;/);
  assert.match(styles, /--result-weekday-col-width\s*:\s*calc\(4ch \+ 12px\)\s*;/);
  assert.match(styles, /--result-people-col-width\s*:\s*calc\(4ch \+ 12px\)\s*;/);
  assert.match(styles, /\.result-menu-table th:nth-child\(1\),[\s\S]*\.result-menu-table td:nth-child\(3\)\{[\s\S]*white-space\s*:\s*nowrap\s*;/);
});
