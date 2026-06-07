import {
  fetchCatalog,
  fetchCatalogSummary,
  fetchDefaults,
  planMenu,
  validateCfg,
  exportExcel,
  enrichResult,
} from "./api.js";
import { buildCfgFromFormData, deriveFormDataFromCfg } from "./cfg_transform.js";
import { DOM } from "./dom.js";
import { createAppState, setCatalog } from "./state.js";
import { escapeHtml, formatErrors, pretty, renderResult, setMsg, showErrorDetail } from "./render.js";

const state = createAppState();
const EDITOR_MODAL_ID = "#dish_editor_modal";
const SUGGEST_RESULT_LIMIT = 12;

const WEEKDAY_LABELS = new Map([
  [1, "星期一"],
  [2, "星期二"],
  [3, "星期三"],
  [4, "星期四"],
  [5, "星期五"],
  [6, "星期六"],
  [7, "星期日"],
]);

const ROLE_LABELS = new Map([
  ["main", "主菜"],
  ["noodle", "麵食"],
  ["side", "配菜"],
  ["veg", "純蔬配菜"],
  ["soup", "湯"],
  ["fruit", "水果"],
]);

const ROLE_KEYS = ["main", "noodle", "side", "veg", "soup", "fruit"];
const DEFAULT_WEEKDAY_ROLE_COUNTS = { main: 1, noodle: 0, side: 2, veg: 1, soup: 1, fruit: 1 };


function normalizeWeekdays(value) {
  const source = Array.isArray(value) && value.length ? value : [1, 2, 3, 4, 5, 6, 7];
  const out = [];
  source.forEach((item) => {
    const wd = Number(item);
    if (Number.isInteger(wd) && wd >= 1 && wd <= 7 && !out.includes(wd)) out.push(wd);
  });
  return out.length ? out.sort((a, b) => a - b) : [1, 2, 3, 4, 5, 6, 7];
}

function formatWeekdays(value) {
  const weekdays = normalizeWeekdays(value);
  if (weekdays.length === 7) return "全週";
  return weekdays.map((wd) => WEEKDAY_LABELS.get(wd) || `星期${wd}`).join("、");
}

function readWeekdayPicker() {
  const weekdays = [];
  $(DOM.allowedDishWeekdayChecks).each(function () {
    if ($(this).is(":checked")) weekdays.push(Number($(this).val()));
  });
  return normalizeWeekdays(weekdays);
}

function resetWeekdayPicker(weekdays = [1, 2, 3, 4, 5, 6, 7]) {
  const allowed = new Set(normalizeWeekdays(weekdays));
  $(DOM.allowedDishWeekdayChecks).each(function () {
    $(this).prop("checked", allowed.has(Number($(this).val())));
  });
}

// The visual CSS class remains "chip", but code uses "selected item" wording for clarity.
function createSelectedItemElement(className) {
  return $("<span></span>")
    .addClass(className)
    .attr("data-id", "")
    .append($("<span></span>").addClass("t"))
    .append($("<span></span>").addClass("x").text("×"));
}

function addSelectedItem($box, id, label, onChanged) {
  if ($box.find(`.chip[data-id="${id}"]`).length) return;
  const $c = createSelectedItemElement("chip");
  $c.attr("data-id", id);
  $c.find(".t").text(label);
  $c.on("click", function () {
    $(this).remove();
    onChanged();
  });
  $box.append($c);
}

function readSelectedItemIds($box) {
  const ids = [];
  $box.find(".chip").each(function () {
    ids.push($(this).data("id"));
  });
  return ids;
}

function clearSelectedItems($box) {
  $box.empty();
}

function getWeekdayLabel(weekday) {
  const wd = Number(weekday);
  return WEEKDAY_LABELS.get(wd) || `星期${wd}`;
}

function normalizeWeekdayRoleCounts(counts = {}) {
  const normalized = {};
  ROLE_KEYS.forEach((role) => {
    const value = parseInt(counts[role] ?? DEFAULT_WEEKDAY_ROLE_COUNTS[role] ?? 0, 10);
    normalized[role] = Number.isFinite(value) && value >= 0 ? value : 0;
  });
  return normalized;
}

function updateWeekdayRoleAddOptions() {
  const used = new Set();
  $(DOM.weekdayRoleTableBody).find("tr[data-weekday]").each(function () {
    used.add(String($(this).data("weekday")));
  });
  const $options = $(DOM.weekdayRoleAddSelect).find("option");
  $options.each(function () {
    $(this).prop("disabled", used.has(String($(this).val())));
  });
  const $current = $(DOM.weekdayRoleAddSelect).find("option:selected");
  if (!$current.length || $current.prop("disabled")) {
    const $firstAvailable = $options.filter(function () { return !$(this).prop("disabled"); }).first();
    if ($firstAvailable.length) $(DOM.weekdayRoleAddSelect).val($firstAvailable.val());
  }
  $(DOM.weekdayRoleAdd).prop("disabled", !$options.filter(function () { return !$(this).prop("disabled"); }).length);
}

function createWeekdayRoleOverrideRow(weekday, counts = {}) {
  const wd = Number(weekday);
  const normalized = normalizeWeekdayRoleCounts(counts);
  const $row = $("<tr></tr>").attr("data-weekday", wd);
  $row.append($("<td></td>").text(getWeekdayLabel(wd)));
  ROLE_KEYS.forEach((role) => {
    const $input = $("<input>", {
      class: "weekday-role-count",
      "data-weekday": wd,
      "data-role": role,
      type: "number",
      min: 0,
      value: normalized[role],
      "aria-label": `${getWeekdayLabel(wd)}${ROLE_LABELS.get(role) || role}數量`,
    });
    $row.append($("<td></td>").append($input));
  });
  const $delete = $("<button>", {
    type: "button",
    class: "weekday-role-delete",
    "data-weekday": wd,
    "aria-label": `刪除${getWeekdayLabel(wd)}覆寫`,
  }).text("刪除");
  $row.append($("<td></td>").append($delete));
  return $row;
}

function addWeekdayRoleOverride(weekday, counts = {}, onChanged = syncCfgTextareaFromForm) {
  const wd = Number(weekday);
  if (!Number.isInteger(wd) || wd < 1 || wd > 7) return;
  const $body = $(DOM.weekdayRoleTableBody);
  const selector = `tr[data-weekday="${wd}"]`;
  const $existing = $body.find(selector);
  const $row = createWeekdayRoleOverrideRow(wd, counts);
  if ($existing.length) $existing.replaceWith($row);
  else $body.append($row);
  const rows = $body.find("tr[data-weekday]").get().sort((a, b) => Number($(a).data("weekday")) - Number($(b).data("weekday")));
  $body.append(rows);
  updateWeekdayRoleAddOptions();
  if (onChanged) onChanged();
}

function renderWeekdayRoleOverrides(perWeekdayRoles = {}) {
  $(DOM.weekdayRoleTableBody).empty();
  Object.entries(perWeekdayRoles || {})
    .map(([weekday, counts]) => [Number(weekday), counts])
    .filter(([weekday]) => Number.isInteger(weekday) && weekday >= 1 && weekday <= 7)
    .sort(([a], [b]) => a - b)
    .forEach(([weekday, counts]) => addWeekdayRoleOverride(weekday, counts, null));
  updateWeekdayRoleAddOptions();
}

function readDishAllowedRules() {
  const out = {};
  $(DOM.allowedDishRules).find(".allowed-dish-rule").each(function () {
    const id = String($(this).data("id") || "").trim();
    if (!id) return;
    const weekdays = normalizeWeekdays(String($(this).attr("data-weekdays") || "")
      .split(",")
      .map((x) => Number(x)));
    if (weekdays.length < 7) out[id] = weekdays;
  });
  return out;
}

function addDishAllowedRule(dishId, weekdays, onChanged) {
  const id = String(dishId || "").trim();
  if (!id) return;
  const normalized = normalizeWeekdays(weekdays);
  const existing = $(DOM.allowedDishRules).find(".allowed-dish-rule").filter(function () {
    return String($(this).data("id") || "") === id;
  });
  if (normalized.length === 7) {
    existing.remove();
    onChanged();
    return;
  }

  const dish = state.dishById.get(id);
  const title = dish ? `[${dish.role}] ${dish.name}` : id;
  const text = `${title}：${formatWeekdays(normalized)}`;
  const $rule = existing.length ? existing : createSelectedItemElement("chip allowed-dish-rule");
  $rule.attr("data-id", id);
  $rule.attr("data-weekdays", normalized.join(","));
  $rule.find(".t").text(text);
  $rule.off("click").on("click", function () {
    $(this).remove();
    onChanged();
  });
  if (!existing.length) $(DOM.allowedDishRules).append($rule);
  onChanged();
}

function clearDishAllowedRules() {
  $(DOM.allowedDishRules).empty();
}

function formatRole(role) {
  return ROLE_LABELS.get(role) || role || "—";
}

function getCatalogDishAllowedWeekdayItems() {
  return (state.dishes || [])
    .map((dish) => ({
      ...dish,
      allowed_weekdays: normalizeWeekdays(dish.allowed_weekdays),
    }))
    .filter((dish) => dish.id && dish.allowed_weekdays.length < 7)
    .sort((a, b) => {
      const roleCompare = formatRole(a.role).localeCompare(formatRole(b.role), "zh-Hant");
      if (roleCompare !== 0) return roleCompare;
      return (a.name || a.id || "").localeCompare((b.name || b.id || ""), "zh-Hant");
    });
}

function getCatalogDishAllowedWeekdayRules() {
  const rules = {};
  getCatalogDishAllowedWeekdayItems().forEach((dish) => {
    rules[dish.id] = dish.allowed_weekdays;
  });
  return rules;
}

function ensureDbAllowedWeekdaysModal() {
  if ($("#db_allowed_weekdays_modal").length) return;
  const html = `
    <div id="db_allowed_weekdays_modal" class="mp-modal hide">
      <div class="mp-modal-card">
        <div class="mp-modal-hd">
          <div class="mp-modal-title">資料庫已設定允許供應日的菜色</div>
          <button type="button" data-action="close">關閉</button>
        </div>
        <div class="hint">
          這裡列出後臺資料庫中不是「全週」的菜色限制。載入預設設定時會先帶入這些資料庫預設；使用者在排菜頁對同一菜色新增規則時，會覆寫資料庫預設且只影響本次排菜 JSON。
        </div>
        <div id="db_allowed_weekdays_modal_body" style="margin-top:10px;"></div>
      </div>
    </div>`;
  $("body").append(html);
  const $modal = $("#db_allowed_weekdays_modal");
  $modal.on("click", "[data-action=close]", () => $modal.addClass("hide"));
  $modal.on("click", (event) => {
    if (event.target === $modal[0]) $modal.addClass("hide");
  });
}

function renderDbAllowedWeekdaysModal() {
  ensureDbAllowedWeekdaysModal();
  const items = getCatalogDishAllowedWeekdayItems();
  const $body = $("#db_allowed_weekdays_modal_body").empty();
  if (!items.length) {
    $body.append(`<div class="hint">目前資料庫沒有特別限制允許供應日的菜色；所有菜色皆視為全週可用。</div>`);
    return;
  }
  const rows = items.map((dish) => `
    <tr>
      <td>${escapeHtml(formatRole(dish.role))}</td>
      <td>${escapeHtml(dish.name || dish.id)}</td>
      <td>${escapeHtml(dish.id)}</td>
      <td>${escapeHtml(formatWeekdays(dish.allowed_weekdays))}</td>
    </tr>`).join("");
  $body.append(`
    <table class="mini-table">
      <thead><tr><th>角色</th><th>菜名</th><th>ID</th><th>允許供應日</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`);
}

function mergeCatalogDishAllowedWeekdaysIntoCfg(cfg) {
  const catalogRules = getCatalogDishAllowedWeekdayRules();
  if (!Object.keys(catalogRules).length) return cfg;
  const next = JSON.parse(JSON.stringify(cfg || {}));
  next.hard = next.hard || {};
  next.hard.dish_allowed_weekdays = {
    ...catalogRules,
    ...(next.hard.dish_allowed_weekdays || {}),
  };
  return next;
}

function showSuggest($el, items, onPick, options = {}) {
  if (!items.length) {
    $el.hide();
    $el.empty();
    return;
  }
  const totalCount = Number(options.totalCount ?? items.length);
  const limit = Number(options.limit ?? items.length);
  const isLimited = totalCount > items.length && items.length <= limit;
  $el.empty();
  items.forEach((it) => {
    const $row = $("<div class=\"item\"></div>");
    $row.append(`<div>${escapeHtml(it.label)}</div>`);
    $row.append(`<div class=\"meta\">${escapeHtml(it.meta || "")}</div>`);
    $row.on("click", () => {
      onPick(it);
      $el.hide();
    });
    $el.append($row);
  });
  if (isLimited) {
    const $notice = $("<div class=\"suggest-note\"></div>");
    $notice.text(`僅顯示前 ${items.length} 筆，共 ${totalCount} 筆符合；請輸入更完整關鍵字或調整角色篩選。`);
    $el.append($notice);
  }
  $el.show();
}

function readFormData() {
  const meatTypes = [];
  $(`${DOM.meatTypes} input[type=checkbox]:checked`).each(function () {
    meatTypes.push($(this).val());
  });
  const scheduleWeekdays = [];
  $(DOM.scheduleWeekdayChecks).each(function () {
    if ($(this).is(":checked")) {
      scheduleWeekdays.push(parseInt($(this).val(), 10));
    }
  });


  const perDayRoles = {};
  $(DOM.dailyRoleInputs).each(function () {
    perDayRoles[$(this).data("role")] = parseInt($(this).val() || "0", 10);
  });
  const perWeekdayRoles = {};
  $(DOM.weekdayRoleInputs).each(function () {
    const weekday = String($(this).data("weekday"));
    const role = $(this).data("role");
    perWeekdayRoles[weekday] = perWeekdayRoles[weekday] || {};
    perWeekdayRoles[weekday][role] = parseInt($(this).val() || "0", 10);
  });

  const prepTimeLimitMinutes = parseInt($(DOM.prepTimeLimitMinutes).val() || "90", 10);
  const perWeekdayPrepTimeLimits = {};
  $(DOM.weekdayPrepLimitInputs).each(function () {
    const raw = String($(this).val() || "").trim();
    if (!raw) return;
    const weekday = String($(this).data("weekday"));
    perWeekdayPrepTimeLimits[weekday] = parseInt(raw, 10);
  });

  const weeklyQuota = {};
  $(DOM.weeklyQuotaInputs).each(function () {
    const meat = $(this).data("meat");
    weeklyQuota[meat] = parseInt($(this).val() || "0", 10);
  });
  const repeatLimits = {};
  $(DOM.repeatLimitInputs).each(function () {
    const k = $(this).data("key");
    repeatLimits[k] = parseInt($(this).val() || "1", 10);
  });

  return {
    horizonDays: parseInt($(DOM.horizonDays).val() || "30", 10),
    defaultPeople: parseInt($(DOM.defaultPeople).val() || "250", 10),
    scheduleWeekdays,
    costMin: parseFloat($(DOM.costMin).val() || "0"),
    costMax: parseFloat($(DOM.costMax).val() || "0"),
    meatTypes,
    noConsecutiveMeat: $(DOM.noConsecutiveMeat).is(":checked"),
    perDayRoles,
    perWeekdayRoles,
    prepTimeLimitMinutes,
    perWeekdayPrepTimeLimits,
    weeklyQuota,
    repeatLimits,
    preferInventory: $(DOM.preferInventory).is(":checked"),
    preferExpiry: $(DOM.preferExpiry).is(":checked"),
    inventoryPreferIngredientIds: readSelectedItemIds($(DOM.ingredientSelectedItems)),
    excludeDishIds: readSelectedItemIds($(DOM.excludeDishSelectedItems)),
    dishAllowedWeekdays: readDishAllowedRules(),
    forceIncludeDates: readSelectedItemIds($(DOM.includeDateSelectedItems)),
    forceExcludeDates: readSelectedItemIds($(DOM.excludeDateSelectedItems)),
    peopleOverrides: (state.lastCfg?.schedule?.people_overrides) || {},
  };
}

function updateWeekdayHint(weekdays) {
  const labels = {
    1: "星期一",
    2: "星期二",
    3: "星期三",
    4: "星期四",
    5: "星期五",
    6: "星期六",
    7: "星期日",
  };
  const normalized = [...new Set((weekdays || []).map((x) => parseInt(x, 10)).filter((x) => x >= 1 && x <= 7))]
    .sort((a, b) => a - b);
  const text = normalized.length
    ? `目前排程星期：${normalized.map((x) => labels[x]).join("、")}`
    : "目前排程星期：未選擇（將不會排任何日期）";
  $(DOM.scheduleWeekdayHint).text(text);
}

function applyCfgToForm(cfg) {
  const form = deriveFormDataFromCfg(cfg);

  $(DOM.horizonDays).val(form.horizonDays);
  $(DOM.defaultPeople).val(form.defaultPeople);
  $(DOM.costMin).val(form.costMin);
  $(DOM.costMax).val(form.costMax);

  const allowed = new Set(form.meatTypes);
  $(`${DOM.meatTypes} input[type=checkbox]`).each(function () {
    const v = $(this).val();
    $(this).prop("checked", allowed.size ? allowed.has(v) : true);
  });

  const scheduleWeekdays = new Set((form.scheduleWeekdays || []).map((x) => parseInt(x, 10)));
  $(DOM.scheduleWeekdayChecks).each(function () {
    const v = parseInt($(this).val(), 10);
    $(this).prop("checked", scheduleWeekdays.has(v));
  });
  updateWeekdayHint(form.scheduleWeekdays || []);

  $(DOM.noConsecutiveMeat).prop("checked", form.noConsecutiveMeat);

  $(DOM.dailyRoleInputs).each(function () {
    const role = $(this).data("role");
    if ((form.perDayRoles || {})[role] !== undefined) $(this).val(form.perDayRoles[role]);
  });
  renderWeekdayRoleOverrides(form.perWeekdayRoles || {});
  $(DOM.prepTimeLimitMinutes).val(form.prepTimeLimitMinutes ?? 90);
  const prepOverrides = form.perWeekdayPrepTimeLimits || {};
  $(DOM.weekdayPrepLimitInputs).each(function () {
    const weekday = String($(this).data("weekday"));
    $(this).val(prepOverrides[weekday] ?? "");
  });

  $(DOM.weeklyQuotaInputs).each(function () {
    const meat = $(this).data("meat");
    if (form.weeklyQuota[meat] !== undefined) {
      $(this).val(form.weeklyQuota[meat]);
    }
  });
  $(DOM.repeatLimitInputs).each(function () {
    const key = $(this).data("key");
    if (form.repeatLimits[key] !== undefined) {
      $(this).val(form.repeatLimits[key]);
    }
  });

  $(DOM.preferInventory).prop("checked", form.preferInventory);
  $(DOM.preferExpiry).prop("checked", form.preferExpiry);

  clearSelectedItems($(DOM.ingredientSelectedItems));
  form.inventoryPreferIngredientIds.forEach((id) => {
    const ing = state.ingById.get(id);
    addSelectedItem($(DOM.ingredientSelectedItems), id, ing ? ing.name : id, syncCfgTextareaFromForm);
  });

  clearSelectedItems($(DOM.excludeDishSelectedItems));
  form.excludeDishIds.forEach((id) => {
    const d = state.dishById.get(id);
    addSelectedItem($(DOM.excludeDishSelectedItems), id, d ? `[${d.role}] ${d.name}` : id, syncCfgTextareaFromForm);
  });

  clearDishAllowedRules();
  Object.entries(form.dishAllowedWeekdays || {}).forEach(([id, weekdays]) => {
    addDishAllowedRule(id, weekdays, syncCfgTextareaFromForm);
  });
  resetWeekdayPicker();

  clearSelectedItems($(DOM.includeDateSelectedItems));
  form.forceIncludeDates.forEach((ds) => {
    addSelectedItem($(DOM.includeDateSelectedItems), ds, ds, syncCfgTextareaFromForm);
  });

  clearSelectedItems($(DOM.excludeDateSelectedItems));
  form.forceExcludeDates.forEach((ds) => {
    addSelectedItem($(DOM.excludeDateSelectedItems), ds, ds, syncCfgTextareaFromForm);
  });
}

function syncCfgTextareaFromForm() {
  if (!state.baseDefaults) return;
  const cfg = buildCfgFromFormData(state.baseDefaults, readFormData());
  $(DOM.cfgJson).val(pretty(cfg));
  state.lastCfg = cfg;
}

function applyPeopleOverride({ date, people }) {
  if (!state.lastResult) return;
  const day = (state.lastResult.days || []).find((d) => d.date === date);
  if (!day?.procurement) return;
  const currentPeople = Number(day.procurement.people || 250);
  const nextPeople = Math.max(1, parseInt(people || "250", 10));
  if (!Number.isFinite(nextPeople) || nextPeople === currentPeople) return;
  const ratio = nextPeople / Math.max(1, currentPeople);

  (day.procurement.dishes || []).forEach((dish) => {
    let dishTotal = 0;
    (dish.ingredients || []).forEach((ing) => {
      if (ing.qty_for_people !== null && ing.qty_for_people !== undefined) {
        ing.qty_for_people = Math.round(Number(ing.qty_per_person || 0) * nextPeople * 10000) / 10000;
      }
      if (ing.line_total !== null && ing.line_total !== undefined && ing.line_total !== "") {
        ing.line_total = Math.round(Number(ing.line_total) * ratio * 100) / 100;
        dishTotal += Number(ing.line_total || 0);
      }
    });
    dish.dish_total = Math.round(dishTotal * 100) / 100;
  });
  day.procurement.day_total = Math.round((day.procurement.day_total || 0) * ratio * 100) / 100;
  day.procurement.people = nextPeople;
}

async function loadDefaultsAndApply() {
  const cfg = mergeCatalogDishAllowedWeekdaysIntoCfg(await fetchDefaults());
  state.baseDefaults = cfg;
  $(DOM.cfgJson).val(pretty(cfg));
  applyCfgToForm(cfg);
  syncCfgTextareaFromForm();
  setMsg("已載入預設設定。");
}

async function loadCatalogIntoState() {
  const { ingredients, dishes } = await fetchCatalog();
  setCatalog(state, ingredients, dishes);
}

async function downloadExcel(cfg, result) {
  const res = await exportExcel(cfg, result);
  if (!res.ok) {
    let payload = {};
    try {
      payload = await res.json();
    } catch (e) {}
    const detail = payload?.detail || {};
    const errs = detail?.errors || [];
    const msg = errs.length ? formatErrors(errs) : (detail?.message || JSON.stringify(detail || payload || {}));
    throw new Error(`匯出失敗：${msg}`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  let filename = "menu_plan.xlsx";
  const cd = res.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename="([^"]+)"/);
  if (m && m[1]) filename = m[1];

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function ensureDishEditorModal() {
  if ($(EDITOR_MODAL_ID).length) return;
  const html = `
    <div id="dish_editor_modal" class="mp-modal hide">
      <div class="mp-modal-card">
        <div class="mp-modal-hd">
          <div class="mp-modal-title">調整菜色</div>
          <button type="button" data-action="close">關閉</button>
        </div>
        <div class="row top">
          <label>搜尋</label>
          <div class="grow">
            <input id="dish_editor_search" type="text" placeholder="輸入菜名關鍵字" />
          </div>
        </div>
        <div class="row top">
          <label>候選菜色</label>
          <div class="grow">
            <select id="dish_editor_select" size="12" class="editor-select"></select>
          </div>
        </div>
        <div class="btns">
          <button type="button" class="primary" data-action="save">套用</button>
          <button type="button" data-action="cancel">取消</button>
        </div>
      </div>
    </div>`;
  $("body").append(html);
}

function findDayByIndex(dayIndex) {
  const days = state.lastResult?.days || [];
  return days.find((d, idx) => (d.day_index ?? idx) === dayIndex);
}

function normalizeDishForResult(base, dish) {
  return {
    ...(base || {}),
    id: dish.id,
    name: dish.name,
    role: dish.role,
    meat_type: dish.meat_type,
    cuisine: dish.cuisine,
    cost: dish.cost,
  };
}

function round2(v) {
  return Math.round(Number(v || 0) * 100) / 100;
}

function toNum(v, fallback = null) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function recomputeDayMetrics(day, cfg) {
  if (!day || typeof day !== "object") return;
  const people = Math.max(1, toNum(day?.procurement?.people, toNum(cfg?.people, 250)));
  const dayTotal = toNum(day?.procurement?.day_total, null);
  if (dayTotal !== null) {
    day.day_cost = round2(dayTotal / people);
  }

  const breakdown = { ...(day.score_breakdown || {}) };
  const hard = cfg?.hard || {};
  const weights = cfg?.weights || {};
  const cr = hard?.cost_range_per_person_per_day || {};
  const maxv = toNum(cr?.max, null);
  const minv = toNum(cr?.min, null);
  const dayCost = toNum(day.day_cost, 0);

  delete breakdown.cost_over_max;
  delete breakdown.cost_under_min;
  if (maxv !== null && dayCost > maxv) {
    breakdown.cost_over_max = round2((dayCost - maxv) * Number(weights.cost_over_max_penalty || 0));
  }
  if (minv !== null && dayCost < minv) {
    breakdown.cost_under_min = round2((minv - dayCost) * Number(weights.cost_under_min_penalty || 0));
  }

  const raw = round2(Object.values(breakdown).reduce((acc, v) => acc + Number(v || 0), 0));
  const penalty = round2(Object.values(breakdown).reduce((acc, v) => acc + (Number(v || 0) > 0 ? Number(v) : 0), 0));
  const bonus = round2(Object.values(breakdown).reduce((acc, v) => acc + (Number(v || 0) < 0 ? -Number(v) : 0), 0));
  const fitness = round2(-raw);

  day.score_breakdown = breakdown;
  day.score = raw;
  day.score_fitness = fitness;
  day.score_summary = {
    bonus,
    penalty,
    raw,
    fitness,
  };
}

function recomputeResultSummary(result, cfg) {
  const days = result?.days || [];
  let totalCost = 0;
  let totalScore = 0;
  let totalFitness = 0;
  days.forEach((day) => {
    recomputeDayMetrics(day, cfg);
    totalCost += Number(day.day_cost || 0);
    totalScore += Number(day.score || 0);
    totalFitness += Number(day.score_fitness || 0);
  });

  result.summary = result.summary || {};
  result.summary.days = days.length;
  result.summary.total_cost = round2(totalCost);
  result.summary.avg_cost_per_day = round2(totalCost / Math.max(days.length, 1));
  result.summary.total_score = round2(totalScore);
  result.summary.total_fitness = round2(totalFitness);
}

function applyDishEdit({ dayIndex, slot, dishId }) {
  const day = findDayByIndex(dayIndex);
  const dish = state.dishById.get(dishId);
  if (!day || !dish) return false;

  day.items = day.items || {};
  if (slot === "main" || slot === "veg" || slot === "soup" || slot === "fruit" || slot === "noodle") {
    day.items[slot] = normalizeDishForResult(day.items[slot], dish);
    const plural = `${slot}s`;
    if (Array.isArray(day.items[plural])) day.items[plural][0] = day.items[slot];
  } else if (slot.startsWith("main_") || slot.startsWith("noodle_") || slot.startsWith("veg_") || slot.startsWith("soup_") || slot.startsWith("fruit_")) {
    const [role, idxRaw] = slot.split("_");
    const idx = parseInt(idxRaw, 10);
    if (Number.isNaN(idx)) return false;
    const plural = `${role}s`;
    const arr = Array.isArray(day.items[plural]) ? day.items[plural] : [];
    arr[idx] = normalizeDishForResult(arr[idx], dish);
    day.items[plural] = arr;
    if (idx === 0) day.items[role] = arr[0];
  } else if (slot.startsWith("side_")) {
    const idx = parseInt(slot.slice(5), 10);
    if (Number.isNaN(idx)) return false;
    const sides = Array.isArray(day.items.sides) ? day.items.sides : [];
    sides[idx] = normalizeDishForResult(sides[idx], dish);
    day.items.sides = sides;
  } else {
    return false;
  }

  day.manual_adjusted = true;
  return true;
}

function bindResultEditing() {
  ensureDishEditorModal();
  const modal = $(EDITOR_MODAL_ID);
  const $search = $("#dish_editor_search");
  const $select = $("#dish_editor_select");
  const ctx = { dayIndex: null, slot: null, role: null };

  function effectiveDishRoleForEdit(dish) {
    if (dish?.role === "main" && String(dish?.meat_type || "").trim().toLowerCase() === "noodles") {
      return "noodle";
    }
    return dish?.role || "";
  }

  function isDishCandidateForEditRole(dish, role) {
    if (!dish || !role) return false;
    // Keep the editor consistent with planner fallback: legacy main dishes whose
    // protein/meat type is noodles are scheduled as noodle-role dishes.
    return effectiveDishRoleForEdit(dish) === role;
  }

  function fillOptions(role, currentId) {
    const candidates = state.dishes
      .filter((d) => isDishCandidateForEditRole(d, role))
      .sort((a, b) => (a.name || "").localeCompare((b.name || ""), "zh-Hant"));
    $select.empty();
    candidates.forEach((d) => {
      const effectiveRole = effectiveDishRoleForEdit(d) === "noodle" && d.role !== "noodle" ? "麵食 fallback" : formatRole(d.role);
      const $opt = $("<option></option>");
      $opt.val(d.id);
      $opt.text(`${d.name || d.id}（${effectiveRole}）`);
      $select.append($opt);
    });
    if (currentId) $select.val(currentId);
  }

  function applyFilter() {
    const q = ($search.val() || "").trim().toLowerCase();
    $select.find("option").each(function () {
      const txt = ($(this).text() || "").toLowerCase();
      $(this).prop("hidden", !!q && !txt.includes(q));
    });
  }

  $(document).on("click", ".dish-edit-trigger", function () {
    const dayIndex = parseInt($(this).data("day-index"), 10);
    const slot = String($(this).data("slot") || "");
    const role = String($(this).data("role") || "");
    const currentId = String($(this).data("dish-id") || "");
    if (!role || !slot || Number.isNaN(dayIndex)) return;

    ctx.dayIndex = dayIndex;
    ctx.slot = slot;
    ctx.role = role;
    fillOptions(role, currentId);
    $search.val("");
    applyFilter();
    modal.removeClass("hide");
  });

  $search.on("input", applyFilter);

  modal.on("click", "[data-action=close],[data-action=cancel]", () => {
    modal.addClass("hide");
  });

  modal.on("click", "[data-action=save]", async () => {
    const dishId = String($select.val() || "");
    if (!dishId || ctx.dayIndex === null) return;
    const ok = applyDishEdit({ dayIndex: ctx.dayIndex, slot: ctx.slot, dishId });
    if (!ok) {
      setMsg("調整失敗：找不到要更新的項目。", true);
      return;
    }
    setMsg("正在同步調整後的成本與評分…");
    try {
      const sync = await enrichResult(state.lastCfg, state.lastResult);
      if (sync.ok && sync.payload?.ok && sync.payload?.result) {
        state.lastResult = sync.payload.result;
      }
    } catch (e) {
      // ignore: fallback to local recompute
    }
    recomputeResultSummary(state.lastResult, state.lastCfg);
    renderResult(state.lastResult, state.lastCfg, { editable: true });
    setMsg("已套用手動調整，成本/目標匹配度與可解釋結果已同步更新。");
    modal.addClass("hide");
  });
}

function bindIngredientSearch() {
  const $input = $(DOM.ingredientSearch);
  const $suggest = $(DOM.ingredientSuggest);
  const $selectedItems = $(DOM.ingredientSelectedItems);

  $input.on("input focus", function () {
    const q = ($input.val() || "").trim().toLowerCase();
    if (!q) {
      $suggest.hide();
      return;
    }
    const hits = state.ingredients
      .filter((x) => (x.name || "").toLowerCase().includes(q))
      .slice(0, 12)
      .map((x) => ({ id: x.id, label: x.name, meta: x.category || "" }));

    showSuggest($suggest, hits, (it) => {
      addSelectedItem($selectedItems, it.id, it.label, syncCfgTextareaFromForm);
      $input.val("");
      syncCfgTextareaFromForm();
    });
  });

  $(document).on("click", (e) => {
    if (!$(e.target).closest(`${DOM.ingredientSearch}, ${DOM.ingredientSuggest}`).length) {
      $suggest.hide();
    }
  });
}

function bindDishSearch() {
  const $input = $(DOM.dishSearch);
  const $role = $(DOM.dishRoleFilter);
  const $suggest = $(DOM.dishSuggest);
  const $selectedItems = $(DOM.excludeDishSelectedItems);

  function run() {
    const q = ($input.val() || "").trim().toLowerCase();
    if (!q) {
      $suggest.hide();
      return;
    }
    const role = $role.val();
    const matches = state.dishes
      .filter((d) => (!role || d.role === role))
      .filter((d) => (d.name || "").toLowerCase().includes(q));
    const hits = matches
      .slice(0, SUGGEST_RESULT_LIMIT)
      .map((d) => ({ id: d.id, label: `[${d.role}] ${d.name}`, meta: d.meat_type || d.cuisine || "" }));

    showSuggest($suggest, hits, (it) => {
      addSelectedItem($selectedItems, it.id, it.label, syncCfgTextareaFromForm);
      $input.val("");
      syncCfgTextareaFromForm();
    }, { totalCount: matches.length, limit: SUGGEST_RESULT_LIMIT });
  }

  $input.on("input focus", run);
  $role.on("change", run);

  $(document).on("click", (e) => {
    if (!$(e.target).closest(`${DOM.dishSearch}, ${DOM.dishSuggest}, ${DOM.dishRoleFilter}`).length) {
      $suggest.hide();
    }
  });
}


function bindDishAllowedWeekdayRules() {
  const $input = $(DOM.allowedDishSearch);
  const $role = $(DOM.allowedDishRoleFilter);
  const $suggest = $(DOM.allowedDishSuggest);

  function run() {
    const q = ($input.val() || "").trim().toLowerCase();
    if (!q) {
      $suggest.hide();
      return;
    }
    const role = $role.val();
    const matches = state.dishes
      .filter((d) => (!role || d.role === role))
      .filter((d) => (d.name || "").toLowerCase().includes(q) || (d.id || "").toLowerCase().includes(q));
    const hits = matches
      .slice(0, SUGGEST_RESULT_LIMIT)
      .map((d) => ({ id: d.id, label: `[${d.role}] ${d.name}`, meta: d.meat_type || d.cuisine || d.id }));

    showSuggest($suggest, hits, (it) => {
      addDishAllowedRule(it.id, readWeekdayPicker(), syncCfgTextareaFromForm);
      $input.val("");
      $suggest.hide();
    }, { totalCount: matches.length, limit: SUGGEST_RESULT_LIMIT });
  }

  $input.on("input focus", run);
  $role.on("change", run);
  $(DOM.allowedDishWeekdayChecks).on("change", syncCfgTextareaFromForm);
  $(DOM.allowedDishDbRulesBtn).on("click", () => {
    renderDbAllowedWeekdaysModal();
    $("#db_allowed_weekdays_modal").removeClass("hide");
  });

  $(document).on("click", (e) => {
    if (!$(e.target).closest(`${DOM.allowedDishSearch}, ${DOM.allowedDishSuggest}, ${DOM.allowedDishRoleFilter}`).length) {
      $suggest.hide();
    }
  });
}

function bindSpecialDateOverrides() {
  $(DOM.includeDateAdd).on("click", () => {
    const ds = String($(DOM.includeDateInput).val() || "").trim();
    if (!ds) return;
    addSelectedItem($(DOM.includeDateSelectedItems), ds, ds, syncCfgTextareaFromForm);
    $(DOM.includeDateInput).val("");
    syncCfgTextareaFromForm();
  });

  $(DOM.excludeDateAdd).on("click", () => {
    const ds = String($(DOM.excludeDateInput).val() || "").trim();
    if (!ds) return;
    addSelectedItem($(DOM.excludeDateSelectedItems), ds, ds, syncCfgTextareaFromForm);
    $(DOM.excludeDateInput).val("");
    syncCfgTextareaFromForm();
  });
}

function renderCatalogSummary(summary) {
  const roleLabels = {
    main: "主菜",
    side: "配菜",
    veg: "純蔬配菜",
    soup: "湯",
    fruit: "水果",
  };
  const roleOrder = ["main", "side", "veg", "soup", "fruit"];
  const rows = roleOrder.map((role) => {
    const dishCount = summary?.dish_count_by_role?.[role] ?? 0;
    const ingredientCount = summary?.ingredient_count_by_role?.[role] ?? 0;
    return `
      <tr>
        <td>${escapeHtml(roleLabels[role])}</td>
        <td>${dishCount}</td>
        <td>${ingredientCount}</td>
      </tr>`;
  }).join("");

  const inventory = summary?.inventory || {};
  const html = `
    <table class="mini-table">
      <thead>
        <tr><th>角色</th><th>菜名數量</th><th>食材數量</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="hint" style="margin-top:8px;">
      庫存統計（${escapeHtml(summary?.today || "")}）：有效庫存筆數 ${inventory.valid_row_count ?? 0}、
      有效庫存食材數 ${inventory.valid_ingredient_count ?? 0}、有效庫存總量 ${Number(inventory.valid_qty_sum ?? 0).toFixed(2)}。
      <br />（有效＝庫存量 &gt; 0 且未過期）
    </div>
    <div class="btns">
      <a class="btn-link" href="/inventory.html">查看庫存統整</a>
    </div>
  `;
  $(DOM.dbSummary).html(html);
}

$(async function () {
  try {
    setMsg("載入資料中…");
    await Promise.all([loadCatalogIntoState(), fetchCatalogSummary().then(renderCatalogSummary)]);
    await loadDefaultsAndApply();

    bindIngredientSearch();
    bindDishSearch();
    bindDishAllowedWeekdayRules();
    bindSpecialDateOverrides();

    $(`${DOM.horizonDays},${DOM.defaultPeople},${DOM.costMin},${DOM.costMax},${DOM.noConsecutiveMeat},${DOM.preferInventory},${DOM.preferExpiry},${DOM.dishRoleFilter}`)
      .on("change input", syncCfgTextareaFromForm);
    $(`${DOM.meatTypes} input[type=checkbox]`).on("change", syncCfgTextareaFromForm);
    $(DOM.scheduleWeekdayChecks).on("change", () => {
      updateWeekdayHint(readFormData().scheduleWeekdays);
      syncCfgTextareaFromForm();
    });
    $(DOM.dailyRoleInputs).on("change input", syncCfgTextareaFromForm);
    $(DOM.weekdayRoleAdd).on("click", () => {
      addWeekdayRoleOverride($(DOM.weekdayRoleAddSelect).val(), DEFAULT_WEEKDAY_ROLE_COUNTS, syncCfgTextareaFromForm);
    });
    $(DOM.weekdayRoleTable).on("change input", ".weekday-role-count", syncCfgTextareaFromForm);
    $(DOM.weekdayRoleTable).on("click", ".weekday-role-delete", function () {
      $(this).closest("tr[data-weekday]").remove();
      updateWeekdayRoleAddOptions();
      syncCfgTextareaFromForm();
    });
    $(DOM.prepTimeLimitMinutes).on("change input", syncCfgTextareaFromForm);
    $(DOM.weekdayPrepLimitInputs).on("change input", syncCfgTextareaFromForm);
    $(DOM.weeklyQuotaInputs).on("change input", syncCfgTextareaFromForm);
    $(DOM.repeatLimitInputs).on("change input", syncCfgTextareaFromForm);

    $(DOM.btnLoadDefaults).on("click", async () => {
      await loadDefaultsAndApply();
      state.lastResult = null;
      state.lastCfg = null;
      $(DOM.btnExportExcel).prop("disabled", true);
    });

    $(DOM.btnApplyJson).on("click", () => {
      try {
        const cfg = JSON.parse($(DOM.cfgJson).val());
        state.lastCfg = cfg;
        applyCfgToForm(cfg);
        syncCfgTextareaFromForm();
        setMsg("已套用 JSON 到表單。");
      } catch (e) {
        setMsg("JSON 解析失敗：請檢查格式。", true);
      }
    });

    $(DOM.btnValidate).on("click", async () => {
      try {
        const cfg = JSON.parse($(DOM.cfgJson).val());
        const v = await validateCfg(cfg);
        if (v.ok) setMsg("驗證通過。");
        else setMsg(`驗證失敗：\n- ${v.errors.join("\n- ")}`, true);
      } catch (e) {
        setMsg("JSON 解析失敗：請檢查格式。", true);
      }
    });

    $(DOM.btnPlan).on("click", async () => {
      setMsg("排程中…");
      $(DOM.btnExportExcel).prop("disabled", true);

      try {
        syncCfgTextareaFromForm();
        const cfg = JSON.parse($(DOM.cfgJson).val());
        state.lastCfg = cfg;

        const v = await validateCfg(cfg);
        if (!v.ok) {
          setMsg(`驗證失敗：\n- ${v.errors.join("\n- ")}`, true);
          return;
        }

        const { ok, payload } = await planMenu(cfg);
        if (!ok) {
          const errPayload = payload?.detail?.errors ? payload.detail : (payload || { errors: [{ message: "Unknown error" }] });
          setMsg(`產生失敗：\n- ${formatErrors(errPayload.errors)}`, true);
          showErrorDetail(errPayload);
          return;
        }

        if (!payload.ok) {
          setMsg(`產生失敗：\n- ${formatErrors(payload.errors)}`, true);
          showErrorDetail(payload);
          return;
        }

        state.lastResult = payload.result;
        setMsg("完成。");
        renderResult(payload.result, cfg, { editable: true });
        $(DOM.btnExportExcel).prop("disabled", false);
      } catch (e) {
        setMsg("產生失敗：請檢查 console 或後端 log。", true);
      }
    });

    $(DOM.btnExportExcel).on("click", async () => {
      try {
        if (!state.lastResult || !state.lastCfg) {
          throw new Error("尚未產生菜單，請先按「產生菜單」。");
        }
        await downloadExcel(state.lastCfg, state.lastResult);
        setMsg("Excel 已下載。");
      } catch (e) {
        setMsg(String(e.message || e), true);
      }
    });

    $(document).on("change", ".day-people-input", function () {
      const date = String($(this).data("date") || "");
      const people = Math.max(1, parseInt($(this).val() || "250", 10));
      if (!date || !state.lastCfg) return;
      state.lastCfg.schedule = state.lastCfg.schedule || {};
      const overrides = { ...(state.lastCfg.schedule.people_overrides || {}) };
      if (people === Number(state.lastCfg.people || 250)) {
        delete overrides[date];
      } else {
        overrides[date] = people;
      }
      state.lastCfg.schedule.people_overrides = overrides;
      $(DOM.cfgJson).val(pretty(state.lastCfg));
      applyPeopleOverride({ date, people });
      renderResult(state.lastResult, state.lastCfg, { editable: true });
      setMsg(`已更新 ${date} 用餐人數為 ${people}（匯出 Excel 將套用）。`);
    });

    bindResultEditing();
    setMsg("就緒。");
  } catch (e) {
    $(DOM.dbSummary).text("資料庫摘要載入失敗。");
    setMsg("初始化失敗：請檢查後端是否啟動、資料庫是否存在。", true);
  }
});
