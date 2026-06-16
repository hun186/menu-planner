import { authToken, httpArray, httpJson } from "../shared/http.js";

const CATALOG_MANAGE_PAGE_SIZE = 10000;

export const ADMIN_API = {
  ingredients: "/admin/catalog/ingredients",
  dishes: "/admin/catalog/dishes",
  ingUpsert: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}`,
  ingDelete: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}`,
  ingRename: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}/rename`,
  dishUpsert: (id) => `/admin/catalog/dishes/${encodeURIComponent(id)}`,
  dishRename: (id) => `/admin/catalog/dishes/${encodeURIComponent(id)}/rename`,
  dishDelete: "/admin/catalog/dishes/delete",
  dishIngGet: (dishId) => `/admin/catalog/dishes/${encodeURIComponent(dishId)}/ingredients`,
  dishIngPut: (dishId) => `/admin/catalog/dishes/${encodeURIComponent(dishId)}/ingredients`,
  dishCostPreview: "/admin/catalog/dishes/cost-preview",
  ingPrices: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}/prices`,
  ingPriceUpsert: (id, date) => `/admin/catalog/ingredients/${encodeURIComponent(id)}/prices/${encodeURIComponent(date)}`,
  ingPriceDelete: (id, date) => `/admin/catalog/ingredients/${encodeURIComponent(id)}/prices/${encodeURIComponent(date)}`,
  ingInventory: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}/inventory`,
  inventorySummary: "/admin/catalog/inventory/summary",
  inventoryMergeIngredient: "/admin/catalog/inventory/summary/merge-ingredient",
  inventorySummaryExport: "/admin/catalog/inventory/summary/export",
  unitConversions: "/admin/catalog/unit-conversions",
  unitConversionUpsert: (fromUnit, toUnit) =>
    `/admin/catalog/unit-conversions/${encodeURIComponent(fromUnit)}/${encodeURIComponent(toUnit)}`,
  unitConversionDelete: (fromUnit, toUnit) =>
    `/admin/catalog/unit-conversions/${encodeURIComponent(fromUnit)}/${encodeURIComponent(toUnit)}`,
  backups: "/admin/catalog/backups",
  backupStats: "/admin/catalog/backups/stats",
  backupCreate: "/admin/catalog/backups/create",
  backupRestore: "/admin/catalog/backups/restore",
  backupBatchDelete: "/admin/catalog/backups/batch-delete",
  backupDelete: (filename) => `/admin/catalog/backups/${encodeURIComponent(filename)}`,
  backupComment: (filename) => `/admin/catalog/backups/${encodeURIComponent(filename)}/comment`,
  ingredientsExport: "/admin/catalog/ingredients/export",
  dishesExport: "/admin/catalog/dishes/export",
};

export function loginAuth(username, password) {
  return httpJson("/v1/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
}

export function registerAuth({ username, password, fullName = "", department = "", note = "" }) {
  return httpJson("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password, full_name: fullName, department, note }),
  });
}

export function logoutAuth() {
  return httpJson("/v1/auth/logout", { method: "POST" }, { includeAuth: true });
}

export function changePasswordAuth(currentPassword, newPassword) {
  return httpJson("/v1/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  }, { includeAuth: true });
}

export function forgotPasswordAuth(username) {
  return httpJson("/v1/auth/forgot-password", { method: "POST", body: JSON.stringify({ username }) });
}

export function recoverPasswordAuth(username, resetToken, newPassword) {
  return httpJson("/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ username, reset_token: resetToken, new_password: newPassword }),
  });
}

export function issuePasswordResetToken(username) {
  return httpJson(`/v1/auth/users/${encodeURIComponent(username)}/password-reset-token`, { method: "POST" }, { includeAuth: true });
}

export function resetUserPasswordAuth(username, newPassword) {
  return httpJson(`/v1/auth/users/${encodeURIComponent(username)}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  }, { includeAuth: true });
}

export function getAuthMe() {
  return httpJson("/v1/auth/me", { method: "GET", headers: {} }, { includeAuth: true });
}

export function listAuthUsers() {
  return httpJson("/v1/auth/users", { method: "GET", headers: {} }, { includeAuth: true });
}

export function approveAuthUser(username, role = "data_reader") {
  return httpJson(`/v1/auth/users/${encodeURIComponent(username)}/approve`, {
    method: "POST",
    body: JSON.stringify({ role }),
  }, { includeAuth: true });
}

export function rejectAuthUser(username) {
  return httpJson(`/v1/auth/users/${encodeURIComponent(username)}/reject`, { method: "POST" }, { includeAuth: true });
}

export function deleteAuthUser(username) {
  return httpJson(`/v1/auth/users/${encodeURIComponent(username)}`, { method: "DELETE" }, { includeAuth: true });
}

export async function loadCatalog() {
  const [ingredients, dishes] = await Promise.all([
    httpArray("/catalog/ingredients", { method: "GET", headers: {} }),
    httpArray("/catalog/dishes", { method: "GET", headers: {} }),
  ]);
  return { ingredients, dishes };
}

async function fetchAdminBlob(url) {
  const headers = {};
  const token = authToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(url, { method: "GET", headers });
  if (!res.ok) {
    let detail = "";
    try {
      const payload = await res.json();
      detail = payload?.detail?.message || payload?.detail || "";
    } catch (_e) {
      detail = "";
    }
    throw new Error(typeof detail === "string" && detail ? detail : `HTTP ${res.status}`);
  }
  return res;
}

async function loadAllCatalogItems(endpoint, params) {
  const buildUrl = (page) => {
    const pageParams = new URLSearchParams(params);
    pageParams.set("page", String(page));
    pageParams.set("page_size", String(CATALOG_MANAGE_PAGE_SIZE));
    return `${endpoint}?${pageParams.toString()}`;
  };

  const firstPage = await httpJson(buildUrl(1), { method: "GET", headers: {} }, { includeAuth: true });
  const total = Number(firstPage?.total || 0);
  const totalPages = Math.max(
    1,
    Number(firstPage?.total_pages || 0),
    Math.ceil(total / CATALOG_MANAGE_PAGE_SIZE),
  );
  const firstItems = Array.isArray(firstPage?.items) ? firstPage.items : [];

  if (totalPages <= 1) {
    return {
      ...firstPage,
      items: firstItems,
      total: total || firstItems.length,
      total_pages: 1,
    };
  }

  const remainingPages = Array.from({ length: totalPages - 1 }, (_item, index) => index + 2);
  const remainingPayloads = await Promise.all(
    remainingPages.map((page) => httpJson(buildUrl(page), { method: "GET", headers: {} }, { includeAuth: true })),
  );
  const items = remainingPayloads.reduce(
    (acc, payload) => acc.concat(Array.isArray(payload?.items) ? payload.items : []),
    [...firstItems],
  );

  return {
    ...firstPage,
    items,
    total: total || items.length,
    total_pages: Math.max(1, Math.ceil((total || items.length) / CATALOG_MANAGE_PAGE_SIZE)),
    is_partial: total > 0 && items.length < total,
  };
}

export async function loadCatalogPage({
  ingredientPage = 1,
  ingredientPageSize = 50,
  ingredientQ = "",
  dishPage = 1,
  dishPageSize = 50,
  dishQ = "",
  dishIngredientId = "",
} = {}) {
  const ingParams = new URLSearchParams();
  if (ingredientQ) ingParams.set("q", ingredientQ);

  const dishParams = new URLSearchParams();
  if (dishQ) dishParams.set("q", dishQ);
  if (dishIngredientId) dishParams.set("ingredient_id", dishIngredientId);

  const [ingredients, dishes] = await Promise.all([
    loadAllCatalogItems(ADMIN_API.ingredients, ingParams),
    loadAllCatalogItems(ADMIN_API.dishes, dishParams),
  ]);

  return { ingredients, dishes };
}

export async function searchIngredients(q = "", limit = 20) {
  const params = new URLSearchParams({
    page: "1",
    page_size: String(limit),
  });
  if (q) params.set("q", q);
  const payload = await httpJson(`${ADMIN_API.ingredients}?${params.toString()}`, { method: "GET", headers: {} }, { includeAuth: true });
  return Array.isArray(payload?.items) ? payload.items : [];
}

export function upsertIngredient(id, body) {
  return httpJson(ADMIN_API.ingUpsert(id), { method: "PUT", body: JSON.stringify(body) }, { includeAuth: true });
}

export function renameIngredient(sourceId, targetId, body) {
  return httpJson(
    ADMIN_API.ingRename(sourceId),
    { method: "POST", body: JSON.stringify({ ...body, target_id: targetId }) },
    { includeAuth: true }
  );
}

export function deleteIngredient(id) {
  return httpJson(ADMIN_API.ingDelete(id), { method: "DELETE" }, { includeAuth: true });
}

export function upsertDish(id, body) {
  return httpJson(ADMIN_API.dishUpsert(id), { method: "PUT", body: JSON.stringify(body) }, { includeAuth: true });
}

export function renameDish(sourceId, targetId, body) {
  return httpJson(
    ADMIN_API.dishRename(sourceId),
    { method: "POST", body: JSON.stringify({ ...body, target_id: targetId }) },
    { includeAuth: true }
  );
}

export function deleteDish(id) {
  return httpJson(
    ADMIN_API.dishDelete,
    { method: "POST", body: JSON.stringify({ id }) },
    { includeAuth: true }
  );
}

export function getDishIngredients(dishId) {
  return httpJson(ADMIN_API.dishIngGet(dishId), { method: "GET", headers: {} }, { includeAuth: true });
}

export function putDishIngredients(dishId, rows) {
  return httpJson(ADMIN_API.dishIngPut(dishId), { method: "PUT", body: JSON.stringify(rows) }, { includeAuth: true });
}

export function previewDishCost(rows, servings = 1) {
  return httpJson(
    ADMIN_API.dishCostPreview,
    { method: "POST", body: JSON.stringify({ items: rows, servings }) },
    { includeAuth: true }
  );
}

export function listDishCostPreview(dishIds = []) {
  const params = new URLSearchParams();
  (dishIds || []).forEach(id => params.append("dish_id", id));
  const query = params.toString();
  const url = query ? `${ADMIN_API.dishCostPreview}?${query}` : ADMIN_API.dishCostPreview;
  return httpArray(url, { method: "GET", headers: {} }, { includeAuth: true });
}

export function getIngredientInventory(ingId) {
  return httpJson(ADMIN_API.ingInventory(ingId), { method: "GET", headers: {} }, { includeAuth: true });
}

export function putIngredientInventory(ingId, body) {
  return httpJson(ADMIN_API.ingInventory(ingId), { method: "PUT", body: JSON.stringify(body) }, { includeAuth: true });
}

export function getIngredientPrices(ingId, limit = 30) {
  return httpJson(`${ADMIN_API.ingPrices(ingId)}?limit=${limit}`, { method: "GET", headers: {} }, { includeAuth: true });
}

export function putIngredientPrice(ingId, date, body) {
  return httpJson(ADMIN_API.ingPriceUpsert(ingId, date), { method: "PUT", body: JSON.stringify(body) }, { includeAuth: true });
}

export function deleteIngredientPrice(ingId, date) {
  return httpJson(ADMIN_API.ingPriceDelete(ingId, date), { method: "DELETE" }, { includeAuth: true });
}

export function listInventorySummary({ q = "", onlyInStock = false } = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  params.set("only_in_stock", onlyInStock ? "true" : "false");
  const query = params.toString();
  const url = query ? `${ADMIN_API.inventorySummary}?${query}` : ADMIN_API.inventorySummary;
  return httpArray(url, { method: "GET", headers: {} }, { includeAuth: true });
}

export function exportInventorySummaryExcel({ q = "", onlyInStock = false } = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  params.set("only_in_stock", onlyInStock ? "true" : "false");
  const query = params.toString();
  const url = query ? `${ADMIN_API.inventorySummaryExport}?${query}` : ADMIN_API.inventorySummaryExport;
  return fetchAdminBlob(url);
}

export function mergeInventoryIngredient(sourceIngredientId, targetIngredientId) {
  return httpJson(
    ADMIN_API.inventoryMergeIngredient,
    { method: "POST", body: JSON.stringify({ source_ingredient_id: sourceIngredientId, target_ingredient_id: targetIngredientId }) },
    { includeAuth: true }
  );
}

export function listUnitConversions() {
  return httpArray(ADMIN_API.unitConversions, { method: "GET", headers: {} }, { includeAuth: true });
}

export function upsertUnitConversion(fromUnit, toUnit, factor) {
  return httpJson(
    ADMIN_API.unitConversionUpsert(fromUnit, toUnit),
    { method: "PUT", body: JSON.stringify({ factor }) },
    { includeAuth: true }
  );
}

export function deleteUnitConversion(fromUnit, toUnit) {
  return httpJson(ADMIN_API.unitConversionDelete(fromUnit, toUnit), { method: "DELETE" }, { includeAuth: true });
}

export function listDbBackups() {
  return httpArray(ADMIN_API.backups, { method: "GET", headers: {} }, { includeAuth: true });
}

export function restoreDbBackup(backupFilename) {
  return httpJson(
    ADMIN_API.backupRestore,
    { method: "POST", body: JSON.stringify({ backup_filename: backupFilename }) },
    { includeAuth: true }
  );
}

export function createDbBackup({ reason = "admin_manual_snapshot", comment = "" } = {}) {
  return httpJson(
    ADMIN_API.backupCreate,
    { method: "POST", body: JSON.stringify({ reason, comment }) },
    { includeAuth: true }
  );
}

export function deleteDbBackup(backupFilename) {
  return httpJson(ADMIN_API.backupDelete(backupFilename), { method: "DELETE" }, { includeAuth: true });
}

export function deleteDbBackupsByDateRange({ date = "", dateFrom = "", dateTo = "" } = {}) {
  const payload = {};
  if (date) {
    payload.date = date;
  } else {
    if (dateFrom) payload.date_from = dateFrom;
    if (dateTo) payload.date_to = dateTo;
  }
  return httpJson(
    ADMIN_API.backupBatchDelete,
    { method: "POST", body: JSON.stringify(payload) },
    { includeAuth: true }
  );
}

export function getDbBackupStats() {
  return httpJson(ADMIN_API.backupStats, { method: "GET", headers: {} }, { includeAuth: true });
}

export function updateDbBackupComment(backupFilename, comment = "") {
  return httpJson(
    ADMIN_API.backupComment(backupFilename),
    { method: "PATCH", body: JSON.stringify({ comment }) },
    { includeAuth: true }
  );
}

export function exportIngredientsExcel({ q = "" } = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  const query = params.toString();
  const url = query ? `${ADMIN_API.ingredientsExport}?${query}` : ADMIN_API.ingredientsExport;
  return fetchAdminBlob(url);
}

export function exportDishesExcel({ q = "", ingredientId = "" } = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (ingredientId) params.set("ingredient_id", ingredientId);
  const query = params.toString();
  const url = query ? `${ADMIN_API.dishesExport}?${query}` : ADMIN_API.dishesExport;
  return fetchAdminBlob(url);
}
