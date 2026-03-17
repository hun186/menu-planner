import { httpArray, httpJson } from "../shared/http.js";

export const ADMIN_API = {
  ingredients: "/catalog/ingredients",
  dishes: "/catalog/dishes",
  ingUpsert: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}`,
  ingDelete: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}`,
  dishUpsert: (id) => `/admin/catalog/dishes/${encodeURIComponent(id)}`,
  dishDelete: (id) => `/admin/catalog/dishes/${encodeURIComponent(id)}`,
  dishIngGet: (dishId) => `/admin/catalog/dishes/${encodeURIComponent(dishId)}/ingredients`,
  dishIngPut: (dishId) => `/admin/catalog/dishes/${encodeURIComponent(dishId)}/ingredients`,
  ingPrices: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}/prices`,
  ingPriceUpsert: (id, date) => `/admin/catalog/ingredients/${encodeURIComponent(id)}/prices/${encodeURIComponent(date)}`,
  ingPriceDelete: (id, date) => `/admin/catalog/ingredients/${encodeURIComponent(id)}/prices/${encodeURIComponent(date)}`,
  ingInventory: (id) => `/admin/catalog/ingredients/${encodeURIComponent(id)}/inventory`,
};

export async function loadCatalog() {
  const [ingredients, dishes] = await Promise.all([
    httpArray(ADMIN_API.ingredients, { method: "GET", headers: {} }),
    httpArray(ADMIN_API.dishes, { method: "GET", headers: {} }),
  ]);
  return { ingredients, dishes };
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
