export function createCatalogCache() {
  return {
    ingredients: [],
    dishes: [],
    ingById: new Map(),
    dishById: new Map(),
  };
}

export function setCatalogCache(cache, ingredients, dishes) {
  cache.ingredients = Array.isArray(ingredients) ? ingredients : [];
  cache.dishes = Array.isArray(dishes) ? dishes : [];
  cache.ingById = new Map(cache.ingredients.map((x) => [x.id, x]));
  cache.dishById = new Map(cache.dishes.map((x) => [x.id, x]));
}
