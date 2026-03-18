const SCORE_ITEM_META = {
  cost_over_max: {
    label: "成本超過上限",
    tip: "超過每日成本上限會扣分，超越越多扣越多。",
  },
  cost_under_min: {
    label: "成本低於下限",
    tip: "低於每日成本下限會扣分，避免菜單過度節省導致品質偏差。",
  },
  consecutive_same_meat: {
    label: "主菜連續同肉類",
    tip: "主菜連續兩天同肉類會扣分（避免吃膩）。",
  },
  cuisine_consecutive: {
    label: "主菜連續同菜系",
    tip: "主菜連續兩天同菜系會扣分（提高多樣性）。",
  },
  use_inventory_bonus_main: {
    label: "主菜使用庫存（加分）",
    tip: "主菜命中庫存比例越高，加分越多。",
  },
  use_inventory_bonus_others: {
    label: "湯/配菜使用庫存（加分）",
    tip: "湯與配菜命中庫存也會加分（權重較低）。",
  },
  prefer_ingredient_bonus: {
    label: "命中偏好食材（加分）",
    tip: "當天菜色若命中你選的偏好食材，會再給額外加分。",
  },
  near_expiry_bonus: {
    label: "使用近到期食材（加分）",
    tip: "越接近到期（天數越小）加分越多，促進先進先出。",
  },
};

export function scoreLabel(key) {
  return SCORE_ITEM_META[key]?.label || key;
}

function getCostRange(cfg) {
  const cr = cfg?.hard?.cost_range_per_person_per_day || {};
  const minv = cr.min ?? null;
  const maxv = cr.max ?? null;
  return { minv, maxv };
}

function collectNearExpiryHints(day) {
  const out = [];
  const push = (dish) => {
    const name = dish?.name;
    const days = dish?.near_expiry_days_min;
    if (name && (days !== undefined && days !== null) && days <= 7) {
      out.push({ name, days: Number(days) });
    }
  };
  push(day?.items?.main);
  push(day?.items?.soup);
  push(day?.items?.veg);
  (day?.items?.sides || []).forEach(push);

  out.sort((a, b) => a.days - b.days);
  return out.slice(0, 3).map((x) => `${x.name}（${x.days}天）`);
}

export function summarizeBreakdown(breakdown) {
  let bonus = 0;
  let penalty = 0;
  Object.values(breakdown || {}).forEach((v0) => {
    const v = Number(v0) || 0;
    if (v < 0) bonus += -v;
    else penalty += v;
  });
  const raw = penalty - bonus;
  const fitness = bonus - penalty;
  return { bonus, penalty, raw, fitness };
}

export function scoreReason(key, value, day, cfg) {
  const v = Number(value) || 0;

  if (key === "cost_over_max") {
    const { maxv } = getCostRange(cfg);
    const dc = Number(day?.day_cost);
    if (maxv !== null && !Number.isNaN(dc)) {
      const over = dc - Number(maxv);
      if (over > 0) return `超出上限 ${over.toFixed(2)}`;
    }
  }

  if (key === "cost_under_min") {
    const { minv } = getCostRange(cfg);
    const dc = Number(day?.day_cost);
    if (minv !== null && !Number.isNaN(dc)) {
      const under = Number(minv) - dc;
      if (under > 0) return `低於下限 ${under.toFixed(2)}`;
    }
  }

  if (key === "use_inventory_bonus_main") {
    const hit = day?.items?.main?.inventory_hit_ratio;
    if (hit !== undefined && hit !== null) return `主菜庫存命中 ${(Number(hit) * 100).toFixed(0)}%`;
  }

  if (key === "use_inventory_bonus_others") {
    const soup = Number(day?.items?.soup?.inventory_hit_ratio || 0);
    const sides = (day?.items?.sides || []).reduce((a, x) => a + Number(x?.inventory_hit_ratio || 0), 0);
    const veg = Number(day?.items?.veg?.inventory_hit_ratio || 0);
    const sum = soup + sides + veg;
    if (sum > 0) return `湯+配菜庫存命中合計 ${(sum * 100).toFixed(0)}%（加權前）`;
  }

  if (key === "near_expiry_bonus") {
    const hints = collectNearExpiryHints(day);
    if (hints.length) return `近到期：${hints.join("、")}`;
  }

  if (key === "prefer_ingredient_bonus") {
    const preferred = new Set((cfg?.soft?.inventory_prefer_ingredient_ids || []).map((x) => String(x || "").trim()).filter(Boolean));
    if (!preferred.size) return "未設定偏好食材";
    const used = [];
    const push = (dish) => (dish?.used_inventory_ingredients || []).forEach((id) => used.push(String(id || "").trim()));
    push(day?.items?.main);
    push(day?.items?.soup);
    push(day?.items?.veg);
    (day?.items?.sides || []).forEach(push);
    const hitCount = used.filter((id) => preferred.has(id)).length;
    if (hitCount > 0) return `命中偏好食材 ${hitCount} 項`;
    return "當日未命中偏好食材";
  }

  return SCORE_ITEM_META[key]?.tip || (v === 0 ? "" : "");
}
