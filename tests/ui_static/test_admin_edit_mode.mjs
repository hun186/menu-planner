import test from "node:test";
import assert from "node:assert/strict";

import { filterBackups, shouldRenameEntity } from "../../src/menu_planner/ui_static/admin.js";

test("shouldRenameEntity only renames in edit mode with changed id", () => {
  assert.equal(shouldRenameEntity("", "ing-new"), false);
  assert.equal(shouldRenameEntity("ing-old", "ing-old"), false);
  assert.equal(shouldRenameEntity(" ing-old ", "ing-new"), true);
});

test("filterBackups supports date and keyword filters", () => {
  const files = [
    { filename: "menu_1.db", modified_at: "2026-03-26T10:10:10", comment: "release snapshot", action_reason: "admin_manual_snapshot" },
    { filename: "menu_2.db", modified_at: "2026-03-25T08:00:00", comment: "before import", action_reason: "ingredient_upsert" },
  ];
  assert.equal(filterBackups(files, { date: "2026-03-26" }).length, 1);
  assert.equal(filterBackups(files, { keyword: "import" }).length, 1);
  assert.equal(filterBackups(files, { date: "2026-03-26", keyword: "release" }).length, 1);
  assert.equal(filterBackups(files, { date: "2026-03-26", keyword: "import" }).length, 0);
});
