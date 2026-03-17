import { createCatalogCache, setCatalogCache } from "./shared/catalog_cache.js";

export function createAppState() {
  return {
    baseDefaults: null,
    ...createCatalogCache(),
    lastCfg: null,
    lastResult: null,
  };
}

export function setCatalog(state, ingredients, dishes) {
  setCatalogCache(state, ingredients, dishes);
}
