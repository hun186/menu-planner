export function createIngredientLookup({ catalog, searchIngredients, escapeHtml, debounce }) {
  let ingLabelToId = new Map();
  let ingredientSuggestSeq = 0;

  function rebuildIngredientDatalist(items = []) {
    ingLabelToId = new Map();
    const $dl = $("#dl_ingredients").empty();

    items.forEach((x) => {
      const label = `${x.category}｜${x.name} (${x.id})`;
      ingLabelToId.set(label, x.id);
      $dl.append(`<option value="${escapeHtml(label)}"></option>`);
    });
  }

  function resolveIngredientId(inputText) {
    const t = (inputText || "").trim();
    if (!t) return null;

    if (catalog.ingById.has(t)) return t;

    const m = t.match(/\(([^()]+)\)\s*$/);
    if (m) return m[1];

    if (ingLabelToId.has(t)) return ingLabelToId.get(t);

    const exact = catalog.ingredients.filter((x) => x.name === t);
    if (exact.length === 1) return exact[0].id;

    return /^[\w.-]+$/u.test(t) ? t : null;
  }

  const debouncedSuggestIngredients = debounce(async (keyword) => {
    if (!keyword) {
      ingredientSuggestSeq += 1;
      rebuildIngredientDatalist([]);
      return;
    }
    const requestSeq = ++ingredientSuggestSeq;
    const items = await searchIngredients(keyword, 20).catch(() => []);
    if (requestSeq !== ingredientSuggestSeq) return;
    rebuildIngredientDatalist(items);
  }, 250);

  return {
    rebuildIngredientDatalist,
    resolveIngredientId,
    debouncedSuggestIngredients,
  };
}
