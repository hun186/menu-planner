import { adminKey, httpArray, httpJson } from "../shared/http.js";

export const ADMIN_API = {
  ingredients: "/admin/catalog/ingredients",
  dishes: "/admin/catalog/dishes",
  ingUpsert: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}`,
  ingDelete: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}`,
  dishUpsert: (id) => `/admin/catalog/dishes/${encodeURIComponent(id)}`,
  dishDelete: (id) => `/admin/catalog/dishes/${encodeURIComponent(id)}`,
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
  ingredientsExport: "/admin/catalog/ingredients/export",
  dishesExport: "/admin/catalog/dishes/export",
};

async function fetchAdminBlob(url) {
  const headers = {};
  const key = adminKey();
  if (key) headers["X-Admin-Key"] = key;
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

export async function loadCatalogPage({
  ingredientPage = 1,
  ingredientPageSize = 50,
  ingredientQ = "",
  dishPage = 1,
  dishPageSize = 50,
  dishQ = "",
  dishIngredientId = "",
} = {}) {
  const ingParams = new URLSearchParams({
    page: String(ingredientPage),
    page_size: String(ingredientPageSize),
  });
  if (ingredientQ) ingParams.set("q", ingredientQ);

  const dishParams = new URLSearchParams({
    page: String(dishPage),
    page_size: String(dishPageSize),
  });
  if (dishQ) dishParams.set("q", dishQ);
  if (dishIngredientId) dishParams.set("ingredient_id", dishIngredientId);

  const [ingredients, dishes] = await Promise.all([
    httpJson(`${ADMIN_API.ingredients}?${ingParams.toString()}`, { method: "GET", headers: {} }, { includeAdminKey: true }),
    httpJson(`${ADMIN_API.dishes}?${dishParams.toString()}`, { method: "GET", headers: {} }, { includeAdminKey: true }),
  ]);

  return { ingredients, dishes };
}

export async function searchIngredients(q = "", limit = 20) {
  const params = new URLSearchParams({
    page: "1",
    page_size: String(limit),
  });
  if (q) params.set("q", q);
  const payload = await httpJson(`${ADMIN_API.ingredients}?${params.toString()}`, { method: "GET", headers: {} }, { includeAdminKey: true });
  return Array.isArray(payload?.items) ? payload.items : [];
}

export function upsertIngredient(id, body) {
  return httpJson(ADMIN_API.ingUpsert(id), { method: "PUT", body: JSON.stringify(body) }, { includeAdminKey: true });
}

export function deleteIngredient(id) {
  return httpJson(ADMIN_API.ingDelete(id), { method: "DELETE" }, { includeAdminKey: true });
}

export function upsertDish(id, body) {
  return httpJson(ADMIN_API.dishUpsert(id), { method: "PUT", body: JSON.stringify(body) }, { includeAdminKey: true });
}

export function deleteDish(id) {
  return httpJson(ADMIN_API.dishDelete(id), { method: "DELETE" }, { includeAdminKey: true });
}

export function getDishIngredients(dishId) {
  return httpJson(ADMIN_API.dishIngGet(dishId), { method: "GET", headers: {} }, { includeAdminKey: true });
}

export function putDishIngredients(dishId, rows) {
  return httpJson(ADMIN_API.dishIngPut(dishId), { method: "PUT", body: JSON.stringify(rows) }, { includeAdminKey: true });
}

export function previewDishCost(rows, servings = 1) {
  return httpJson(
    ADMIN_API.dishCostPreview,
    { method: "POST", body: JSON.stringify({ items: rows, servings }) },
    { includeAdminKey: true }
  );
}

export function listDishCostPreview(dishIds = []) {
  const params = new URLSearchParams();
  (dishIds || []).forEach(id => params.append("dish_id", id));
  const query = params.toString();
  const url = query ? `${ADMIN_API.dishCostPreview}?${query}` : ADMIN_API.dishCostPreview;
  return httpArray(url, { method: "GET", headers: {} }, { includeAdminKey: true });
}

export function getIngredientInventory(ingId) {
  return httpJson(ADMIN_API.ingInventory(ingId), { method: "GET", headers: {} }, { includeAdminKey: true });
}

export function putIngredientInventory(ingId, body) {
  return httpJson(ADMIN_API.ingInventory(ingId), { method: "PUT", body: JSON.stringify(body) }, { includeAdminKey: true });
}

export function getIngredientPrices(ingId, limit = 30) {
  return httpJson(`${ADMIN_API.ingPrices(ingId)}?limit=${limit}`, { method: "GET", headers: {} }, { includeAdminKey: true });
}

export function putIngredientPrice(ingId, date, body) {
  return httpJson(ADMIN_API.ingPriceUpsert(ingId, date), { method: "PUT", body: JSON.stringify(body) }, { includeAdminKey: true });
}

export function deleteIngredientPrice(ingId, date) {
  return httpJson(ADMIN_API.ingPriceDelete(ingId, date), { method: "DELETE" }, { includeAdminKey: true });
}

export function listInventorySummary({ q = "", onlyInStock = false } = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  params.set("only_in_stock", onlyInStock ? "true" : "false");
  const query = params.toString();
  const url = query ? `${ADMIN_API.inventorySummary}?${query}` : ADMIN_API.inventorySummary;
  return httpArray(url, { method: "GET", headers: {} }, { includeAdminKey: true });
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
    { includeAdminKey: true }
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
