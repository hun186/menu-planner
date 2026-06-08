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

  assert.match(render, /RESULT_COLUMNS\.map\(\(col\) => \{[\s\S]*class="\$\{col\.colClass\}"[\s\S]*resultColumnDataAttrs\(col\.key\)/);
  assert.match(render, /class="day-people-input" type="number" min="1" max="9999"/);
  assert.match(styles, /--result-date-col-width\s*:\s*calc\(10ch \+ 12px\)\s*;/);
  assert.match(styles, /--result-weekday-col-width\s*:\s*36px\s*;/);
  assert.match(styles, /--result-people-col-width\s*:\s*38px\s*;/);
  assert.match(styles, /\.result-menu-table th:nth-child\(1\),[\s\S]*\.result-menu-table td:nth-child\(3\)\{[\s\S]*white-space\s*:\s*nowrap\s*;/);
  assert.match(styles, /\.result-menu-table th:nth-child\(1\),[\s\S]*\.result-menu-table td:nth-child\(1\)\{[\s\S]*padding-left\s*:\s*6px;[\s\S]*padding-right\s*:\s*6px\s*;/);
  assert.match(styles, /\.result-menu-table th:nth-child\(2\),[\s\S]*\.result-menu-table td:nth-child\(3\)\{[\s\S]*padding-left\s*:\s*4px;[\s\S]*text-align\s*:\s*center\s*;/);
  assert.match(styles, /\.result-menu-table th:nth-child\(3\),[\s\S]*\.result-menu-table td:nth-child\(3\)\{[\s\S]*padding-left\s*:\s*2px;[\s\S]*padding-right\s*:\s*2px\s*;/);
  assert.match(styles, /\.day-people-input\s*\{[\s\S]*width\s*:\s*36px\s*;[\s\S]*text-align\s*:\s*center\s*;/);
});


test("result menu table has column visibility control styles", () => {
  const render = readFileSync("src/menu_planner/ui_static/render.js", "utf8");
  const styles = readFileSync("src/menu_planner/ui_static/styles.css", "utf8");

  assert.match(render, /RESULT_COLUMN_STORAGE_KEY\s*=\s*"menuPlanner\.resultTable\.hiddenColumns"/);
  assert.match(render, /class="result-column-toggle-input" data-result-column-toggle="\$\{col\.key\}"/);
  assert.match(render, /root\.querySelectorAll\(`\[data-result-column="\$\{col\.key\}"\]`\)/);
  assert.match(styles, /\.result-column-panel\s*\{[\s\S]*display\s*:\s*flex\s*;/);
  assert.match(styles, /\.result-column-toggle\s*\{[\s\S]*border-radius\s*:\s*999px\s*;/);
  assert.match(styles, /\.result-column-hidden\s*\{[\s\S]*display\s*:\s*none\s*;/);
});
