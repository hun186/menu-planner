import test from "node:test";
import assert from "node:assert/strict";

import { shouldRenameEntity } from "../../src/menu_planner/ui_static/admin.js";

test("shouldRenameEntity only renames in edit mode with changed id", () => {
  assert.equal(shouldRenameEntity("", "ing-new"), false);
  assert.equal(shouldRenameEntity("ing-old", "ing-old"), false);
  assert.equal(shouldRenameEntity(" ing-old ", "ing-new"), true);
});
