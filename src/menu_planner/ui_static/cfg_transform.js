function clone(x) {
  return JSON.parse(JSON.stringify(x || {}));
}

export function buildCfgFromFormData(baseCfg, formData) {
  const cfg = clone(baseCfg);

  cfg.horizon_days = formData.horizonDays;

  cfg.hard = cfg.hard || {};
  cfg.soft = cfg.soft || {};
  cfg.weights = cfg.weights || {};
  cfg.search = cfg.search || {};

  cfg.hard.cost_range_per_person_per_day = {
    min: formData.costMin,
    max: formData.costMax,
  };

  cfg.hard.allowed_main_meat_types = formData.meatTypes;
  cfg.hard.no_consecutive_same_main_meat = formData.noConsecutiveMeat;
  cfg.hard.weekly_max_main_meat = formData.weeklyQuota;

  cfg.soft.prefer_use_inventory = formData.preferInventory;
  cfg.soft.prefer_near_expiry = formData.preferExpiry;
  cfg.soft.inventory_prefer_ingredient_ids = formData.inventoryPreferIngredientIds;

  cfg.hard.exclude_dish_ids = formData.excludeDishIds;
  return cfg;
}

export function deriveFormDataFromCfg(cfg) {
  const hard = cfg?.hard || {};
  const soft = cfg?.soft || {};
  const costRange = hard.cost_range_per_person_per_day || {};

  return {
    horizonDays: cfg?.horizon_days ?? 30,
    costMin: costRange.min ?? 0,
    costMax: costRange.max ?? 0,
    meatTypes: hard.allowed_main_meat_types || [],
    noConsecutiveMeat: !!hard.no_consecutive_same_main_meat,
    weeklyQuota: hard.weekly_max_main_meat || {},
    preferInventory: !!soft.prefer_use_inventory,
    preferExpiry: !!soft.prefer_near_expiry,
    inventoryPreferIngredientIds: soft.inventory_prefer_ingredient_ids || [],
    excludeDishIds: hard.exclude_dish_ids || [],
  };
}
