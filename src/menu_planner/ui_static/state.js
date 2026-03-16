export function createAppState() {
  return {
    baseDefaults: null,
    ingredients: [],
    dishes: [],
    ingById: new Map(),
    dishById: new Map(),
    lastCfg: null,
    lastResult: null,
  };
}

export function setCatalog(state, ingredients, dishes) {
  state.ingredients = ingredients;
  state.dishes = dishes;
  state.ingById = new Map(ingredients.map((x) => [x.id, x]));
  state.dishById = new Map(dishes.map((x) => [x.id, x]));
}
