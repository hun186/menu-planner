function clone(x) {
  return JSON.parse(JSON.stringify(x || {}));
}

export function buildCfgFromFormData(baseCfg, formData) {
  const cfg = clone(baseCfg);

  cfg.horizon_days = formData.horizonDays;
  cfg.people = formData.defaultPeople;
  cfg.schedule = cfg.schedule || {};
  cfg.schedule.weekdays = formData.scheduleWeekdays;
  cfg.schedule.force_include_dates = formData.forceIncludeDates;
  cfg.schedule.force_exclude_dates = formData.forceExcludeDates;
  cfg.schedule.people_overrides = formData.peopleOverrides;

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
  cfg.hard.repeat_limits = {
    ...(cfg.hard.repeat_limits || {}),
    ...(formData.repeatLimits || {}),
  };

  cfg.soft.prefer_use_inventory = formData.preferInventory;
  cfg.soft.prefer_near_expiry = formData.preferExpiry;
  cfg.soft.inventory_prefer_ingredient_ids = formData.inventoryPreferIngredientIds;

  cfg.hard.exclude_dish_ids = formData.excludeDishIds;
  return cfg;
}

export function deriveFormDataFromCfg(cfg) {
  const hard = cfg?.hard || {};
  const soft = cfg?.soft || {};
  const schedule = cfg?.schedule || {};
  const costRange = hard.cost_range_per_person_per_day || {};

  return {
    horizonDays: cfg?.horizon_days ?? 30,
    defaultPeople: cfg?.people ?? 250,
    scheduleWeekdays: schedule.weekdays || [1, 2, 3, 4, 5],
    costMin: costRange.min ?? 0,
    costMax: costRange.max ?? 0,
    meatTypes: hard.allowed_main_meat_types || [],
    noConsecutiveMeat: !!hard.no_consecutive_same_main_meat,
    weeklyQuota: hard.weekly_max_main_meat || {},
    repeatLimits: hard.repeat_limits || {},
    preferInventory: !!soft.prefer_use_inventory,
    preferExpiry: !!soft.prefer_near_expiry,
    inventoryPreferIngredientIds: soft.inventory_prefer_ingredient_ids || [],
    excludeDishIds: hard.exclude_dish_ids || [],
    forceIncludeDates: schedule.force_include_dates || [],
    forceExcludeDates: schedule.force_exclude_dates || [],
    peopleOverrides: schedule.people_overrides || {},
  };
}
