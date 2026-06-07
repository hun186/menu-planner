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

  cfg.per_day_roles = formData.perDayRoles;
  cfg.per_weekday_roles = formData.perWeekdayRoles;
  cfg.side_soup_protein_limit = formData.sideSoupProteinLimit ?? 2;
  cfg.per_weekday_side_soup_protein_limit = formData.perWeekdaySideSoupProteinLimits || {};
  cfg.prep_time_limit_minutes = formData.prepTimeLimitMinutes ?? 90;
  cfg.per_weekday_prep_time_limit_minutes = formData.perWeekdayPrepTimeLimits || {};

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
  cfg.hard.dish_allowed_weekdays = formData.dishAllowedWeekdays || {};
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
    perDayRoles: cfg?.per_day_roles || { main: 1, noodle: 0, side: 2, veg: 1, soup: 1, fruit: 1 },
    perWeekdayRoles: cfg?.per_weekday_roles || {},
    sideSoupProteinLimit: cfg?.side_soup_protein_limit ?? 2,
    perWeekdaySideSoupProteinLimits: cfg?.per_weekday_side_soup_protein_limit || {},
    prepTimeLimitMinutes: cfg?.prep_time_limit_minutes ?? 90,
    perWeekdayPrepTimeLimits: cfg?.per_weekday_prep_time_limit_minutes || {},
    weeklyQuota: hard.weekly_max_main_meat || {},
    repeatLimits: hard.repeat_limits || {},
    preferInventory: !!soft.prefer_use_inventory,
    preferExpiry: !!soft.prefer_near_expiry,
    inventoryPreferIngredientIds: soft.inventory_prefer_ingredient_ids || [],
    excludeDishIds: hard.exclude_dish_ids || [],
    dishAllowedWeekdays: hard.dish_allowed_weekdays || {},
    forceIncludeDates: schedule.force_include_dates || [],
    forceExcludeDates: schedule.force_exclude_dates || [],
    peopleOverrides: schedule.people_overrides || {},
  };
}
