export function compareNullable(a, b) {
  const aNull = a === null || a === undefined || a === "";
  const bNull = b === null || b === undefined || b === "";
  if (aNull && bNull) return 0;
  if (aNull) return 1;
  if (bNull) return -1;
  if (typeof a === "number" && typeof b === "number") {
    return a - b;
  }
  return String(a).localeCompare(String(b), "zh-Hant", { numeric: true, sensitivity: "base" });
}

export function normalizeSortDirection(direction) {
  return direction === "desc" ? "desc" : "asc";
}

export function sortRows(rows, { key, direction = "asc", valueGetter, compare = compareNullable } = {}) {
  if (!Array.isArray(rows)) return [];
  if (!key && typeof valueGetter !== "function") return [...rows];

  const normalizedDirection = normalizeSortDirection(direction);
  const getValue = typeof valueGetter === "function"
    ? valueGetter
    : (row) => row?.[key];

  return [...rows].sort((a, b) => {
    const result = compare(getValue(a, key), getValue(b, key), key, a, b);
    return normalizedDirection === "asc" ? result : -result;
  });
}

export function paginateRows(rows, { page = 1, pageSize = 50 } = {}) {
  if (!Array.isArray(rows)) return [];
  const limit = Math.max(1, Number.parseInt(pageSize, 10) || 50);
  const currentPage = Math.max(1, Number.parseInt(page, 10) || 1);
  const start = (currentPage - 1) * limit;
  return rows.slice(start, start + limit);
}

export function sortThenPaginate(rows, { sort = {}, pagination = {} } = {}) {
  const sortedRows = sortRows(rows, sort);
  return {
    sortedRows,
    pageRows: paginateRows(sortedRows, pagination),
  };
}
