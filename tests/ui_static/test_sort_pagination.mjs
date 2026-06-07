import test from 'node:test';
import assert from 'node:assert/strict';

import { sortThenPaginate } from '../../src/menu_planner/ui_static/shared/sort_pagination.js';

test('sortThenPaginate sorts the full data set before slicing the requested page', () => {
  const rows = [
    { id: 'b', name: 'B' },
    { id: 'd', name: 'D' },
    { id: 'a', name: 'A' },
    { id: 'c', name: 'C' },
  ];

  const { sortedRows, pageRows } = sortThenPaginate(rows, {
    sort: { key: 'id', direction: 'asc' },
    pagination: { page: 2, pageSize: 2 },
  });

  assert.deepEqual(sortedRows.map((row) => row.id), ['a', 'b', 'c', 'd']);
  assert.deepEqual(pageRows.map((row) => row.id), ['c', 'd']);
});
