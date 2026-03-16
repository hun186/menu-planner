const API = {
  defaults: "/config/default",
  validate: "/config/validate",
  plan: "/plan",
  ingredients: "/catalog/ingredients",
  dishes: "/catalog/dishes",
  exportExcel: "/export/excel",
};

export async function fetchDefaults() {
  const res = await fetch(API.defaults);
  return await res.json();
}

export async function fetchCatalog() {
  const [r1, r2] = await Promise.all([fetch(API.ingredients), fetch(API.dishes)]);
  return {
    ingredients: await r1.json(),
    dishes: await r2.json(),
  };
}

export async function validateCfg(cfg) {
  const res = await fetch(API.validate, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });
  return await res.json();
}

export async function planMenu(cfg) {
  const res = await fetch(API.plan, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });
  const payload = await res.json().catch(() => ({}));
  return { ok: res.ok, payload };
}

export async function exportExcel(cfg, result) {
  const res = await fetch(API.exportExcel, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cfg, result }),
  });
  return res;
}
