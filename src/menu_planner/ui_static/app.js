import { fetchCatalog, fetchDefaults, planMenu, validateCfg, exportExcel } from "./api.js";
import { buildCfgFromFormData, deriveFormDataFromCfg } from "./cfg_transform.js";
import { DOM } from "./dom.js";
import { createAppState, setCatalog } from "./state.js";
import { escapeHtml, formatErrors, pretty, renderResult, setMsg, showErrorDetail } from "./render.js";

const state = createAppState();

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

  const weeklyQuota = {};
  $(DOM.weeklyQuotaInputs).each(function () {
    const meat = $(this).data("meat");
    weeklyQuota[meat] = parseInt($(this).val() || "0", 10);
  });

  return {
    horizonDays: parseInt($(DOM.horizonDays).val() || "30", 10),
    costMin: parseFloat($(DOM.costMin).val() || "0"),
    costMax: parseFloat($(DOM.costMax).val() || "0"),
    meatTypes,
    noConsecutiveMeat: $(DOM.noConsecutiveMeat).is(":checked"),
    weeklyQuota,
    preferInventory: $(DOM.preferInventory).is(":checked"),
    preferExpiry: $(DOM.preferExpiry).is(":checked"),
    inventoryPreferIngredientIds: readChipIds($(DOM.ingredientChips)),
    excludeDishIds: readChipIds($(DOM.excludeDishChips)),
  };
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

  $(DOM.noConsecutiveMeat).prop("checked", form.noConsecutiveMeat);

  $(DOM.weeklyQuotaInputs).each(function () {
    const meat = $(this).data("meat");
    if (form.weeklyQuota[meat] !== undefined) {
      $(this).val(form.weeklyQuota[meat]);
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

$(async function () {
  try {
    setMsg("載入資料中…");
    await loadCatalogIntoState();
    await loadDefaultsAndApply();

    bindIngredientSearch();
    bindDishSearch();

    $(`${DOM.horizonDays},${DOM.costMin},${DOM.costMax},${DOM.noConsecutiveMeat},${DOM.preferInventory},${DOM.preferExpiry},${DOM.dishRoleFilter}`)
      .on("change input", syncCfgTextareaFromForm);
    $(`${DOM.meatTypes} input[type=checkbox]`).on("change", syncCfgTextareaFromForm);
    $(DOM.weeklyQuotaInputs).on("change input", syncCfgTextareaFromForm);

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
        renderResult(payload.result, cfg);
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

    setMsg("就緒。");
  } catch (e) {
    setMsg("初始化失敗：請檢查後端是否啟動、資料庫是否存在。", true);
  }
});
