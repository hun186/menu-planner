import { fetchCatalog, fetchCatalogSummary, fetchDefaults, planMenu, validateCfg, exportExcel } from "./api.js";
import { buildCfgFromFormData, deriveFormDataFromCfg } from "./cfg_transform.js";
import { DOM } from "./dom.js";
import { createAppState, setCatalog } from "./state.js";
import { escapeHtml, formatErrors, pretty, renderResult, setMsg, showErrorDetail } from "./render.js";

const state = createAppState();
const EDITOR_MODAL_ID = "#dish_editor_modal";

function addChip($box, id, label, onChanged) {
  if ($box.find(`.chip[data-id="${id}"]`).length) return;
  const $c = $("<span class=\"chip\" data-id=\"\"><span class=\"t\"></span><span class=\"x\">×</span></span>");
  $c.attr("data-id", id);
  $c.find(".t").text(label);
  $c.on("click", function () {
    $(this).remove();
    onChanged();
  });
  $box.append($c);
}

function readChipIds($box) {
  const ids = [];
  $box.find(".chip").each(function () {
    ids.push($(this).data("id"));
  });
  return ids;
}

function clearChips($box) {
  $box.empty();
}

function showSuggest($el, items, onPick) {
  if (!items.length) {
    $el.hide();
    $el.empty();
    return;
  }
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
    scheduleWeekdays,
    costMin: parseFloat($(DOM.costMin).val() || "0"),
    costMax: parseFloat($(DOM.costMax).val() || "0"),
    meatTypes,
    noConsecutiveMeat: $(DOM.noConsecutiveMeat).is(":checked"),
    weeklyQuota,
    repeatLimits,
    preferInventory: $(DOM.preferInventory).is(":checked"),
    preferExpiry: $(DOM.preferExpiry).is(":checked"),
    inventoryPreferIngredientIds: readChipIds($(DOM.ingredientChips)),
    excludeDishIds: readChipIds($(DOM.excludeDishChips)),
    forceIncludeDates: readChipIds($(DOM.includeDateChips)),
    forceExcludeDates: readChipIds($(DOM.excludeDateChips)),
  };
}

function updateWeekdayHint(weekdays) {
  const labels = {
    1: "週一",
    2: "週二",
    3: "週三",
    4: "週四",
    5: "週五",
    6: "週六",
    7: "週日",
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

  clearChips($(DOM.ingredientChips));
  form.inventoryPreferIngredientIds.forEach((id) => {
    const ing = state.ingById.get(id);
    addChip($(DOM.ingredientChips), id, ing ? ing.name : id, syncCfgTextareaFromForm);
  });

  clearChips($(DOM.excludeDishChips));
  form.excludeDishIds.forEach((id) => {
    const d = state.dishById.get(id);
    addChip($(DOM.excludeDishChips), id, d ? `[${d.role}] ${d.name}` : id, syncCfgTextareaFromForm);
  });

  clearChips($(DOM.includeDateChips));
  form.forceIncludeDates.forEach((ds) => {
    addChip($(DOM.includeDateChips), ds, ds, syncCfgTextareaFromForm);
  });

  clearChips($(DOM.excludeDateChips));
  form.forceExcludeDates.forEach((ds) => {
    addChip($(DOM.excludeDateChips), ds, ds, syncCfgTextareaFromForm);
  });
}

function syncCfgTextareaFromForm() {
  if (!state.baseDefaults) return;
  const cfg = buildCfgFromFormData(state.baseDefaults, readFormData());
  $(DOM.cfgJson).val(pretty(cfg));
  state.lastCfg = cfg;
}

async function loadDefaultsAndApply() {
  const cfg = await fetchDefaults();
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

function applyDishEdit({ dayIndex, slot, dishId }) {
  const day = findDayByIndex(dayIndex);
  const dish = state.dishById.get(dishId);
  if (!day || !dish) return false;

  day.items = day.items || {};
  if (slot === "main" || slot === "veg" || slot === "soup" || slot === "fruit") {
    day.items[slot] = normalizeDishForResult(day.items[slot], dish);
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

  function fillOptions(role, currentId) {
    const candidates = state.dishes
      .filter((d) => d.role === role)
      .sort((a, b) => (a.name || "").localeCompare((b.name || ""), "zh-Hant"));
    $select.empty();
    candidates.forEach((d) => {
      const $opt = $("<option></option>");
      $opt.val(d.id);
      $opt.text(d.name || d.id);
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

  modal.on("click", "[data-action=save]", () => {
    const dishId = String($select.val() || "");
    if (!dishId || ctx.dayIndex === null) return;
    const ok = applyDishEdit({ dayIndex: ctx.dayIndex, slot: ctx.slot, dishId });
    if (!ok) {
      setMsg("調整失敗：找不到要更新的項目。", true);
      return;
    }
    renderResult(state.lastResult, state.lastCfg, { editable: true });
    setMsg("已套用手動調整（可直接匯出 Excel）。");
    modal.addClass("hide");
  });
}

function bindIngredientSearch() {
  const $input = $(DOM.ingredientSearch);
  const $suggest = $(DOM.ingredientSuggest);
  const $chips = $(DOM.ingredientChips);

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
      addChip($chips, it.id, it.label, syncCfgTextareaFromForm);
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
  const $chips = $(DOM.excludeDishChips);

  function run() {
    const q = ($input.val() || "").trim().toLowerCase();
    if (!q) {
      $suggest.hide();
      return;
    }
    const role = $role.val();
    const hits = state.dishes
      .filter((d) => (!role || d.role === role))
      .filter((d) => (d.name || "").toLowerCase().includes(q))
      .slice(0, 12)
      .map((d) => ({ id: d.id, label: `[${d.role}] ${d.name}`, meta: d.meat_type || d.cuisine || "" }));

    showSuggest($suggest, hits, (it) => {
      addChip($chips, it.id, it.label, syncCfgTextareaFromForm);
      $input.val("");
      syncCfgTextareaFromForm();
    });
  }

  $input.on("input focus", run);
  $role.on("change", run);

  $(document).on("click", (e) => {
    if (!$(e.target).closest(`${DOM.dishSearch}, ${DOM.dishSuggest}, ${DOM.dishRoleFilter}`).length) {
      $suggest.hide();
    }
  });
}

function bindSpecialDateOverrides() {
  $(DOM.includeDateAdd).on("click", () => {
    const ds = String($(DOM.includeDateInput).val() || "").trim();
    if (!ds) return;
    addChip($(DOM.includeDateChips), ds, ds, syncCfgTextareaFromForm);
    $(DOM.includeDateInput).val("");
    syncCfgTextareaFromForm();
  });

  $(DOM.excludeDateAdd).on("click", () => {
    const ds = String($(DOM.excludeDateInput).val() || "").trim();
    if (!ds) return;
    addChip($(DOM.excludeDateChips), ds, ds, syncCfgTextareaFromForm);
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
    bindSpecialDateOverrides();

    $(`${DOM.horizonDays},${DOM.costMin},${DOM.costMax},${DOM.noConsecutiveMeat},${DOM.preferInventory},${DOM.preferExpiry},${DOM.dishRoleFilter}`)
      .on("change input", syncCfgTextareaFromForm);
    $(`${DOM.meatTypes} input[type=checkbox]`).on("change", syncCfgTextareaFromForm);
    $(DOM.scheduleWeekdayChecks).on("change", () => {
      updateWeekdayHint(readFormData().scheduleWeekdays);
      syncCfgTextareaFromForm();
    });
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

    bindResultEditing();
    setMsg("就緒。");
  } catch (e) {
    $(DOM.dbSummary).text("資料庫摘要載入失敗。");
    setMsg("初始化失敗：請檢查後端是否啟動、資料庫是否存在。", true);
  }
});
