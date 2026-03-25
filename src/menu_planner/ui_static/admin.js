import { deleteDbBackup, deleteDish, deleteIngredient, deleteIngredientPrice, exportDishesExcel, exportIngredientsExcel, getDbBackupStats, getDishIngredients, getIngredientInventory, getIngredientPrices, listDbBackups, listDishCostPreview, loadCatalogPage, previewDishCost, putDishIngredients, putIngredientInventory, putIngredientPrice, renameDish, renameIngredient, restoreDbBackup, searchIngredients, updateDbBackupComment, upsertDish, upsertIngredient } from "./admin/api.js";
import { createCatalogCache, setCatalogCache } from "./shared/catalog_cache.js";
import { adminKey } from "./shared/http.js";
import { escapeHtml } from "./shared/html.js";

export function shouldRenameEntity(sourceId, targetId) {
  const source = String(sourceId || "").trim();
  const target = String(targetId || "").trim();
  return Boolean(source) && source !== target;
}

if (typeof window !== "undefined" && typeof document !== "undefined" && typeof window.$ !== "undefined") {
  (function () {

  const DOM = {
    msgIng: "#msg_ing",
    msgDish: "#msg_dish",
    msgDishIngredients: "#msg_di",
    msgDishCost: "#msg_di_cost",
    msgIngMeta: "#msg_ing_meta",
    msgBackup: "#msg_backup",
    ingredientEditorFields: "#ing_id,#ing_name,#ing_category,#ing_protein,#ing_unit",
    dishEditorFields: "#dish_id,#dish_name,#dish_meat,#dish_cuisine,#dish_tags",
  };

  const catalog = createCatalogCache();

  let editingIngredientId = null;
  let editingDishId = null;
  let ingLabelToId = new Map();
  let editingIngId = null;
  let dishCostById = new Map();
  let backupFiles = [];
  let backupStats = { count: 0, total_size_bytes: 0, warning_threshold_bytes: 500 * 1024 * 1024, is_over_warning_threshold: false };
  const ingredientSort = { key: "id", direction: "asc" };
  const dishSort = { key: "id", direction: "asc" };
  const ingredientPager = { page: 1, pageSize: 50, total: 0, totalPages: 1, q: "" };
  const dishPager = { page: 1, pageSize: 50, total: 0, totalPages: 1, q: "", ingredientId: "", ingredientLabel: "" };
  let catalogLoadSeq = 0;
  let ingredientSuggestSeq = 0;

  function readInitialIngredientQuery() {
    const params = new URLSearchParams(window.location.search || "");
    return (params.get("q") || "").trim();
  }
  
  function setMsg($el, text, isError) {
    $el.css("color", isError ? "#b42318" : "#1a7f37").text(text || "");
    requestAnimationFrame(syncEditorPaneHeights);
  }

  function clearMsg(selector) {
    setMsg($(selector), "", false);
  }

  function clearFields(selector) {
    $(selector).val("");
  }

  function scrollToEditor(editorSelector, focusSelector) {
    const el = document.querySelector(editorSelector);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (focusSelector) {
      $(focusSelector).trigger("focus");
    }
  }

  async function runWithMsg(msgSelector, fn, successText) {
    try {
      await fn();
      if (successText) {
        setMsg($(msgSelector), successText, false);
      }
    } catch (e) {
      setMsg($(msgSelector), e.message || String(e), true);
    }
  }


  function syncEditorPaneHeights() {
    const panes = Array.from(document.querySelectorAll(".manage-card .editor-pane"));
    if (!panes.length) return;

    panes.forEach((pane) => {
      pane.style.minHeight = "0px";
    });

    const maxBottom = panes.reduce((mx, pane) => Math.max(mx, pane.offsetTop + pane.offsetHeight), 0);
    panes.forEach((pane) => {
      const targetHeight = Math.max(0, maxBottom - pane.offsetTop);
      pane.style.minHeight = `${targetHeight}px`;
    });
  }

  function debounce(fn, wait = 300) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
  }

  async function downloadExcelFromResponse(res) {
    const blob = await res.blob();
    const contentDisposition = res.headers.get("Content-Disposition") || "";
    const match = contentDisposition.match(/filename=\"([^\"]+)\"/i);
    const filename = match?.[1] || "export.xlsx";
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  async function reloadCatalog() {
    const requestSeq = ++catalogLoadSeq;
    const { ingredients, dishes } = await loadCatalogPage({
      ingredientPage: ingredientPager.page,
      ingredientPageSize: ingredientPager.pageSize,
      ingredientQ: ingredientPager.q,
      dishPage: dishPager.page,
      dishPageSize: dishPager.pageSize,
      dishQ: dishPager.q,
      dishIngredientId: dishPager.ingredientId,
    });
    if (requestSeq !== catalogLoadSeq) return;

    const ingItems = Array.isArray(ingredients?.items) ? ingredients.items : [];
    const dishItems = Array.isArray(dishes?.items) ? dishes.items : [];
    setCatalogCache(catalog, ingItems, dishItems);
    ingredientPager.total = Number(ingredients?.total || 0);
    ingredientPager.totalPages = Math.max(1, Number(ingredients?.total_pages || 1));
    dishPager.total = Number(dishes?.total || 0);
    dishPager.totalPages = Math.max(1, Number(dishes?.total_pages || 1));

    $("#ing_page_info").text(`第 ${ingredientPager.page} / ${ingredientPager.totalPages} 頁，共 ${ingredientPager.total} 筆`);
    $("#dish_page_info").text(`第 ${dishPager.page} / ${dishPager.totalPages} 頁，共 ${dishPager.total} 筆`);
    const dishFilterHint = dishPager.ingredientId
      ? `目前僅顯示有使用「${dishPager.ingredientLabel || dishPager.ingredientId}」的菜色。`
      : "目前顯示全部菜色。";
    $("#dish_ing_filter_hint").text(dishFilterHint);
    $("#ing_prev_page").prop("disabled", ingredientPager.page <= 1);
    $("#ing_next_page").prop("disabled", ingredientPager.page >= ingredientPager.totalPages);
    $("#dish_prev_page").prop("disabled", dishPager.page <= 1);
    $("#dish_next_page").prop("disabled", dishPager.page >= dishPager.totalPages);
    $("#ing_page_jump").val(ingredientPager.page);
    $("#dish_page_jump").val(dishPager.page);
    await reloadDishCostPreview(dishItems.map(x => x.id));
  }

  function renderBackupOptions() {
    const $sel = $("#db_backup_select").empty();
    if (!backupFiles.length) {
      $sel.append(`<option value="">（目前無可用備份檔）</option>`);
      return;
    }
    backupFiles.forEach((x) => {
      const modified = x?.modified_at || "";
      const size = Number(x?.size_bytes || 0);
      const label = `${x?.filename || ""}｜${modified}｜${formatBytes(size)}`;
      $sel.append(`<option value="${escapeHtml(x?.filename || "")}">${escapeHtml(label)}</option>`);
    });
  }

  function formatBytes(sizeBytes) {
    const size = Number(sizeBytes || 0);
    if (size < 1024) return `${size} bytes`;
    const kb = size / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    return `${(mb / 1024).toFixed(2)} GB`;
  }

  function renderBackupUsage() {
    const total = Number(backupStats?.total_size_bytes || 0);
    const threshold = Number(backupStats?.warning_threshold_bytes || 0);
    const count = Number(backupStats?.count || backupFiles.length || 0);
    const over = Boolean(backupStats?.is_over_warning_threshold);
    const summary = `目前備份：${count} 筆，已使用 ${formatBytes(total)}。每日自動備份上限為 50 筆。`;
    const warning = over
      ? `⚠ 備份容量已達 ${formatBytes(total)}（≥ ${formatBytes(threshold)}），建議盡快刪除過舊備份。`
      : "";
    const text = warning ? `${summary} ${warning}` : summary;
    $("#backup_usage_info").text(text).toggleClass("warn-text", over);
  }

  function syncSelectedBackupMeta() {
    const selected = ($("#db_backup_select").val() || "").trim();
    const item = backupFiles.find((x) => (x?.filename || "") === selected) || null;
    const reason = item?.action_reason || "—";
    const comment = item?.comment || "";
    $("#backup_reason_text").text(reason);
    $("#db_backup_comment").val(comment);
  }

  async function refreshBackupList() {
    const [files, stats] = await Promise.all([listDbBackups(), getDbBackupStats()]);
    backupFiles = Array.isArray(files) ? files : [];
    backupStats = stats || backupStats;
    renderBackupOptions();
    renderBackupUsage();
    syncSelectedBackupMeta();
  }

  async function reloadDishCostPreview(dishIds = []) {
    try {
      const list = await listDishCostPreview(dishIds);
      dishCostById = new Map((Array.isArray(list) ? list : []).map(x => [x.dish_id, x]));
    } catch (_e) {
      dishCostById = new Map();
    }
  }

  function formatCostWarningReason(reason) {
    switch (reason) {
      case "ingredient_not_found":
        return "食材不存在";
      case "missing_price":
        return "缺少價格";
      case "unit_mismatch":
        return "單位不相容";
      default:
        return "成本資料異常";
    }
  }

  function formatCostWarningItem(w, idx, separator = "：") {
    const ing = w?.ingredient_name || w?.ingredient_id || "未知食材";
    const reason = formatCostWarningReason(w?.reason);
    const unitText = w?.reason === "unit_mismatch" && w?.unit && w?.price_unit
      ? `（${w.unit} → ${w.price_unit}）`
      : "";
    return `${idx + 1}. ${ing}${separator}${reason}${unitText}`;
  }

  function buildDishCostWarningTitle(cost) {
    const warnings = Array.isArray(cost?.warnings) ? cost.warnings : [];
    if (!warnings.length) return "";
    const lines = warnings.map((w, idx) => formatCostWarningItem(w, idx));
    return `成本計算異常：\n${lines.join("\n")}`;
  }

  function formatDishCostCell(dishId) {
    const c = dishCostById.get(dishId);
    if (!c) return { text: "—", title: "", warningCount: 0 };
    const base = Number(c.per_serving_cost || 0).toFixed(2);
    const warningCount = Number(c.warning_count || 0);
    const warningTitle = warningCount > 0 ? buildDishCostWarningTitle(c) : "";
    return {
      text: base,
      title: warningTitle,
      warningCount,
    };
  }
  
  function rebuildIngredientDatalist(items = []) {
    ingLabelToId = new Map();
    const $dl = $("#dl_ingredients").empty();
  
    items.forEach(x => {
      // 顯示用：分類｜名稱 (id) 讓人更好辨認
      const label = `${x.category}｜${x.name} (${x.id})`;
      ingLabelToId.set(label, x.id);
  
      // datalist option 的 value 就放 label
      $dl.append(`<option value="${escapeHtml(label)}"></option>`);
    });
  }


  function normalizeTags(s) {
    const t = (s || "").trim();
    if (!t) return [];
    if (t.startsWith("[")) {
      try {
        const v = JSON.parse(t);
        return Array.isArray(v) ? v : [];
      } catch (e) {
        return [];
      }
    }
    // 逗號分隔
    return t.split(",").map(x => x.trim()).filter(Boolean);
  }

  function genId(prefix) {
    return `${prefix}_${Date.now()}`;
  }

  function compareNullable(a, b) {
    const aNull = a === null || a === undefined || a === "";
    const bNull = b === null || b === undefined || b === "";
    if (aNull && bNull) return 0;
    if (aNull) return 1;
    if (bNull) return -1;
    const aNum = typeof a === "number" ? a : Number.NaN;
    const bNum = typeof b === "number" ? b : Number.NaN;
    if (!Number.isNaN(aNum) && !Number.isNaN(bNum)) {
      return aNum - bNum;
    }
    return String(a).localeCompare(String(b), "zh-Hant", { numeric: true, sensitivity: "base" });
  }

  function applySortArrow(selector, key, direction) {
    document.querySelectorAll(selector).forEach((th) => {
      const baseLabel = th.dataset.baseLabel || th.textContent.trim().replace(/\s[▲▼]$/, "");
      th.dataset.baseLabel = baseLabel;
      if (th.dataset.ingSortKey === key || th.dataset.dishSortKey === key) {
        th.textContent = `${baseLabel} ${direction === "asc" ? "▲" : "▼"}`;
      } else {
        th.textContent = baseLabel;
      }
    });
  }

  function renderIngredients() {
    const list = [...catalog.ingredients].sort((a, b) => {
      const result = compareNullable(a?.[ingredientSort.key], b?.[ingredientSort.key]);
      return ingredientSort.direction === "asc" ? result : -result;
    });
    applySortArrow("#ing_tbl thead th[data-ing-sort-key]", ingredientSort.key, ingredientSort.direction);

    const $tb = $("#ing_tbl tbody").empty();
    list.forEach(x => {
      const $tr = $(`
        <tr>
          <td>${escapeHtml(x.id)}</td>
          <td>${escapeHtml(x.name)}</td>
          <td>${escapeHtml(x.category)}</td>
          <td>${escapeHtml(x.protein_group || "")}</td>
          <td>${escapeHtml(x.default_unit)}</td>
          <td>
            <div class="row-actions">
              <button class="btn_edit" title="編輯">修</button>
              <button class="btn_meta" title="價格/庫存">價/庫</button>
              <button class="btn_inventory" title="庫存統整">總</button>
              <button class="btn_find_dishes" title="找菜名">菜</button>
              <button class="btn_del" title="刪除">刪</button>
            </div>
          </td>
        </tr>
      `);

      $tr.find(".btn_edit").on("click", () => {
        editingIngredientId = x.id;
        $("#ing_source_id").val(x.id);
        $("#ing_id").val(x.id);
        $("#ing_name").val(x.name);
        $("#ing_category").val(x.category);
        $("#ing_protein").val(x.protein_group || "");
        $("#ing_unit").val(x.default_unit);
        clearMsg(DOM.msgIng);
        scrollToEditor(".grid .manage-card:first-child .editor-pane", "#ing_name");
      });
	  
      $tr.find(".btn_meta").on("click", async () => {
        await runWithMsg(DOM.msgIng, async () => {
          await openIngMeta(x.id);
        });
      });

      $tr.find(".btn_inventory").on("click", () => {
        window.location.href = `/inventory.html?q=${encodeURIComponent(x.id)}`;
      });

      $tr.find(".btn_find_dishes").on("click", async () => {
        await runWithMsg(DOM.msgDish, async () => {
          await applyDishIngredientFilter(x.id, x.name);
          document.getElementById("dish_ing_filter")?.scrollIntoView({ behavior: "smooth", block: "center" });
          $("#dish_ing_filter").trigger("focus");
        }, `已過濾：顯示有使用「${x.name}」的菜色。`);
      });

      $tr.find(".btn_del").on("click", async () => {
        if (!confirm(`確定刪除食材：${x.name}（${x.id}）？`)) return;
        await runWithMsg(DOM.msgIng, async () => {
          await deleteIngredient(x.id);
          await reloadCatalog();
          renderAll();
        }, "已刪除食材。");
      });
	  

      $tb.append($tr);
    });
  }

  function renderDishes() {
    const list = [...catalog.dishes].sort((a, b) => {
      const aVal = dishSort.key === "cost" ? Number(dishCostById.get(a.id)?.per_serving_cost ?? -1) : a?.[dishSort.key];
      const bVal = dishSort.key === "cost" ? Number(dishCostById.get(b.id)?.per_serving_cost ?? -1) : b?.[dishSort.key];
      const result = compareNullable(aVal, bVal);
      return dishSort.direction === "asc" ? result : -result;
    });
    applySortArrow("#dish_tbl thead th[data-dish-sort-key]", dishSort.key, dishSort.direction);

    const $tb = $("#dish_tbl tbody").empty();
    list.forEach(x => {
      const costCell = formatDishCostCell(x.id);
      const warningAttr = costCell.title ? ` data-tooltip="${escapeHtml(costCell.title)}"` : "";
      const warningBadge = costCell.warningCount > 0
        ? `<span class="cost-warning-icon" tabindex="0" role="img" aria-label="成本警示，共 ${costCell.warningCount} 項"${warningAttr}>⚠️${costCell.warningCount}</span>`
        : "";
      const $tr = $(`
        <tr>
          <td>${escapeHtml(x.id)}</td>
          <td>${escapeHtml(x.name)}</td>
          <td>${escapeHtml(x.role)}</td>
          <td>${escapeHtml(x.meat_type || "")}</td>
          <td>${escapeHtml(x.cuisine || "")}</td>
          <td class="dish-cost-cell">
            <span class="dish-cost-value">${escapeHtml(costCell.text)}</span>${warningBadge}
          </td>
          <td>
            <div class="row-actions">
              <button class="btn_edit" title="編輯">修</button>
              <button class="btn_ing" title="編輯食材">材</button>
              <button class="btn_del" title="刪除">刪</button>
            </div>
          </td>
        </tr>
      `);

      $tr.find(".btn_edit").on("click", () => {
        editingDishId = x.id;
        $("#dish_source_id").val(x.id);
        $("#dish_id").val(x.id);
        $("#dish_name").val(x.name);
        $("#dish_role").val(x.role);
        $("#dish_meat").val(x.meat_type || "");
        $("#dish_cuisine").val(x.cuisine || "");

        // 後端若回 tags_json，這裡也能接
        const tags = x.tags || (() => {
          try { return JSON.parse(x.tags_json || "[]"); } catch { return []; }
        })();
        $("#dish_tags").val(Array.isArray(tags) ? JSON.stringify(tags) : "[]");
        clearMsg(DOM.msgDish);
        scrollToEditor(".grid .manage-card:nth-child(2) .editor-pane", "#dish_name");
      });

      $tr.find(".btn_del").on("click", async () => {
        if (!confirm(`確定刪除菜色：${x.name}（${x.id}）？`)) return;
        await runWithMsg(DOM.msgDish, async () => {
          await deleteDish(x.id);
          await reloadCatalog();
          renderAll();
        }, "已刪除菜色。");
      });

      $tr.find(".btn_ing").on("click", async () => {
        await runWithMsg(DOM.msgDish, async () => {
          await openDishIngredients(x.id);
        });
      });

      $tb.append($tr);
    });
  }

  function renderAll() {
    renderIngredients();
    renderDishes();
    syncEditorPaneHeights();
  }

  function resolveIngredientId(inputText) {
    const t = (inputText || "").trim();
    if (!t) return null;
  
    // 1) 直接輸入 ID
    if (catalog.ingById.has(t)) return t;
  
    // 2) 從 "... (id)" 抓 id
    const m = t.match(/\(([^()]+)\)\s*$/);
    if (m) return m[1];
  
    // 3) 完整 label
    if (ingLabelToId.has(t)) return ingLabelToId.get(t);

    // 4) 最後：若只輸入名稱，嘗試唯一匹配（僅當前頁資料）
    const exact = catalog.ingredients.filter(x => x.name === t);
    if (exact.length === 1) return exact[0].id;

    // 5) 退而求其次：允許看起來像 ID 的值（後端會最終驗證）
    return /^[\w.-]+$/u.test(t) ? t : null;
  }

  const debouncedSuggestIngredients = debounce(async (keyword) => {
    if (!keyword) {
      // 未輸入時不預載部分清單，避免誤以為食材只有這些
      ingredientSuggestSeq += 1;
      rebuildIngredientDatalist([]);
      return;
    }
    const requestSeq = ++ingredientSuggestSeq;
    const items = await searchIngredients(keyword, 20).catch(() => []);
    if (requestSeq !== ingredientSuggestSeq) return;
    rebuildIngredientDatalist(items);
  }, 250);
  
  async function saveIngredient() {
    const sourceId = ($("#ing_source_id").val() || "").trim();
    const id = ($("#ing_id").val() || "").trim() || genId("ing");
    const body = {
      name: ($("#ing_name").val() || "").trim(),
      category: ($("#ing_category").val() || "").trim(),
      protein_group: ($("#ing_protein").val() || "").trim() || null,
      default_unit: ($("#ing_unit").val() || "").trim()
    };

    if (!body.name || !body.category || !body.default_unit) {
      throw new Error("食材：名稱 / 分類 / 預設單位 為必填。");
    }

    if (shouldRenameEntity(sourceId, id)) {
      await renameIngredient(sourceId, id, body);
    } else {
      await upsertIngredient(id, body);
    }

    editingIngredientId = id;
    $("#ing_source_id").val(id);
    $("#ing_id").val(id); // 若自動產生，回填給使用者
    await reloadCatalog();
    renderAll();
  }

  async function saveDish() {
    const sourceId = ($("#dish_source_id").val() || "").trim();
    const id = ($("#dish_id").val() || "").trim() || genId("dish");
    const body = {
      name: ($("#dish_name").val() || "").trim(),
      role: ($("#dish_role").val() || "main").trim(),
      cuisine: ($("#dish_cuisine").val() || "").trim() || null,
      meat_type: ($("#dish_meat").val() || "").trim() || null,
      tags: normalizeTags($("#dish_tags").val())
    };

    if (!body.name || !body.role) {
      throw new Error("菜色：名稱 / 角色 為必填。");
    }

    if (shouldRenameEntity(sourceId, id)) {
      await renameDish(sourceId, id, body);
    } else {
      await upsertDish(id, body);
    }

    editingDishId = id;
    $("#dish_source_id").val(id);
    $("#dish_id").val(id);
    await reloadCatalog();
    renderAll();
  }

  function ingSelect(value) {
    const $sel = $(`<select class="di_ing"></select>`);
    catalog.ingredients.forEach(x => {
      const $op = $(`<option></option>`)
        .val(x.id)
        .text(`${x.name} (${x.id})`);
      if (x.id === value) $op.prop("selected", true);
      $sel.append($op);
    });
    return $sel;
  }

  function addDishIngRow(row) {
    const $tr = $(`<tr></tr>`);
  
    const initId = row?.ingredient_id || "";
    const initIng = initId ? catalog.ingById.get(initId) : null;
    const initLabel = initIng ? `${initIng.category}｜${initIng.name} (${initIng.id})` : initId;
  
    const $ing = $(`<input class="di_ing_input" list="dl_ingredients" placeholder="輸入食材名稱或ID">`)
      .val(initLabel)
      .data("ing_id", initId || "");
  
    // 當使用者改輸入時，嘗試解析成 id，存到 data
    $ing.on("input change blur", function () {
      const rawText = $(this).val();
      const id = resolveIngredientId(rawText);
      $(this).data("ing_id", id || "");
      $(this).css("border-color", id ? "" : "#ef4444");
      debouncedSuggestIngredients((rawText || "").trim());
    });
  
    const $qty = $(`<input class="di_qty" type="number" step="0.1">`).val(row?.qty ?? 100);
    const $unit = $(`<input class="di_unit" type="text">`).val(row?.unit ?? "g");
    const $openIng = $(`<button type="button" class="di_open_ing">食材管理</button>`);
    $openIng.on("click", async () => {
      await runWithMsg(DOM.msgDishIngredients, async () => {
        await filterIngredientListFromDishRow($ing);
      });
    });
  
    const $del = $(`<button type="button">刪除</button>`).on("click", () => $tr.remove());
    const $actions = $(`<div class="di_actions"></div>`).append($openIng, $del);
  
    $tr.append($("<td></td>").append($ing));
    $tr.append($("<td></td>").append($qty));
    $tr.append($("<td></td>").append($unit));
    $tr.append($("<td></td>").append($actions));
  
    $("#di_tbl tbody").append($tr);
  }
  
  async function openDishIngredients(dishId) {
    editingDishId = dishId;
    const dish = catalog.dishById.get(dishId);
    $("#modal_title").text(`編輯菜色食材：${dish?.name || ""}（${dishId}）`);
    $("#di_tbl tbody").empty();
    clearMsg(DOM.msgDishIngredients);

    const items = await getDishIngredients(dishId);
    (Array.isArray(items) ? items : []).forEach(r => addDishIngRow(r));
    if (!items || !items.length) addDishIngRow(null);

    $("#modal").removeClass("hide");
  }

  async function filterIngredientListFromDishRow($ingInput) {
    const rawText = ($ingInput.val() || "").trim();
    const resolvedId = $ingInput.data("ing_id") || resolveIngredientId(rawText);
    if (!resolvedId) {
      throw new Error("請先選擇有效食材，再開啟食材管理。");
    }

    let ing = catalog.ingById.get(resolvedId);
    if (!ing) {
      const found = await searchIngredients(resolvedId, 20);
      ing = (Array.isArray(found) ? found : []).find(x => x?.id === resolvedId) || null;
    }
    if (!ing) {
      throw new Error(`找不到食材：${resolvedId}`);
    }

    const keyword = (ing.name || rawText || "").trim();
    ingredientPager.q = keyword;
    ingredientPager.page = 1;
    $("#ing_q").val(keyword);
    clearFields(DOM.ingredientEditorFields);
    clearMsg(DOM.msgIng);
    await reloadCatalog();
    renderAll();
    $("#modal").addClass("hide");
    document.getElementById("ing_q")?.scrollIntoView({ behavior: "smooth", block: "center" });
    $("#ing_q").trigger("focus");
  }

  async function applyDishIngredientFilter(ingredientId, ingredientName = "") {
    const id = String(ingredientId || "").trim();
    if (!id) {
      throw new Error("請輸入有效食材，再套用菜色過濾。");
    }
    dishPager.ingredientId = id;
    dishPager.ingredientLabel = ingredientName || id;
    dishPager.page = 1;
    $("#dish_ing_filter").val(ingredientName ? `${ingredientName} (${id})` : id);
    await reloadCatalog();
    renderDishes();
  }

  async function saveDishIngredients() {
    const dishId = editingDishId;
    const rows = collectDishIngredientRows();
    await putDishIngredients(dishId, rows);
  }

  function collectDishIngredientRows() {
    const rows = [];
    const bad = [];

    $("#di_tbl tbody tr").each(function (i) {
      const $ing = $(this).find(".di_ing_input");
      const ingredient_id = $ing.data("ing_id") || resolveIngredientId($ing.val());
      const qty = parseFloat($(this).find(".di_qty").val() || "0");
      const unit = ($(this).find(".di_unit").val() || "").trim();

      if (!ingredient_id) {
        bad.push(i + 1);
        $ing.css("border-color", "#ef4444");
        return;
      }
      if (!(qty > 0) || !unit) return;

      rows.push({ ingredient_id, qty, unit });
    });

    if (bad.length) {
      throw new Error(`第 ${bad.join(", ")} 列食材無法辨識，請從提示清單選或直接輸入正確 ID。`);
    }

    return rows;
  }

  async function refreshDishCostPreview() {
    const rows = collectDishIngredientRows();
    if (!rows.length) {
      setMsg($(DOM.msgDishCost), "尚無有效食材用量，無法估算成本。", true);
      return;
    }

    const preview = await previewDishCost(rows, 1);
    const warnings = Array.isArray(preview.warnings) ? preview.warnings : [];
    const warningCount = warnings.length;
    const warningDetail = warningCount > 0
      ? `；異常明細：${warnings.map((w, idx) => formatCostWarningItem(w, idx, "-")).join("；")}`
      : "";
    const warningText = warningCount > 0
      ? `（⚠️ ${warningCount} 項警示：可能是單位對不上或缺價格${warningDetail}）`
      : "";
    setMsg($(DOM.msgDishCost), `預估 1 人份成本：${preview.per_serving_cost.toFixed(2)} ${warningText}`, warningCount > 0);
  }

function todayStr() {
  const d = new Date();
  const mm = String(d.getMonth()+1).padStart(2,"0");
  const dd = String(d.getDate()).padStart(2,"0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

  function addPriceRow(row) {
    const $tr = $(`
      <tr>
        <td><input class="p_date" type="date"></td>
        <td><input class="p_val" type="number" step="0.1"></td>
        <td><input class="p_unit" type="text" placeholder="g/ml/顆/份"></td>
        <td><button class="p_del">刪除</button></td>
      </tr>
    `);
  
    $tr.find(".p_date").val(row?.price_date || todayStr());
    $tr.find(".p_val").val(row?.price_per_unit ?? 0);
    $tr.find(".p_unit").val(row?.unit || "g");
  
    $tr.find(".p_del").on("click", async () => {
      const date = $tr.find(".p_date").val();
      if (date && confirm(`刪除 ${date} 的價格紀錄？`)) {
        try {
          await deleteIngredientPrice(editingIngId, date);
          $tr.remove();
        } catch (e) {
          setMsg($(DOM.msgIngMeta), e.message || String(e), true);
        }
      } else {
        $tr.remove();
      }
    });
  
    $("#price_tbl tbody").append($tr);
  }
  
  async function openIngMeta(ingId) {
    editingIngId = ingId;
    const ing = catalog.ingById.get(ingId);
    $("#modal_ing_title").text(`價格/庫存：${ing?.name || ""}（${ingId}）`);
    clearMsg(DOM.msgIngMeta);
  
    // inventory
    const inv = await getIngredientInventory(ingId).catch(() => null);
    $("#inv_qty").val(inv?.qty_on_hand ?? 0);
    $("#inv_unit").val(inv?.unit ?? (ing?.default_unit || "g"));
    $("#inv_updated").val(inv?.updated_at ?? todayStr());
    $("#inv_expiry").val(inv?.expiry_date ?? "");
  
    // prices
    $("#price_tbl tbody").empty();
    const prices = await getIngredientPrices(ingId, 30);
    (Array.isArray(prices) ? prices : []).reverse().forEach(p => addPriceRow(p));
    if (!prices || !prices.length) addPriceRow(null);
  
    $("#modal_ing").removeClass("hide");
  }
  
  function bindUI() {
    const onResize = debounce(syncEditorPaneHeights, 120);
    window.addEventListener("resize", onResize);

    const onIngredientSearchInput = debounce(async () => {
      ingredientPager.q = ($("#ing_q").val() || "").trim();
      ingredientPager.page = 1;
      await reloadCatalog();
      renderIngredients();
    }, 250);

    const onDishSearchInput = debounce(async () => {
      dishPager.q = ($("#dish_q").val() || "").trim();
      dishPager.page = 1;
      await reloadCatalog();
      renderDishes();
    }, 250);

    $("#ing_q").on("input", onIngredientSearchInput);
    $("#ing_tbl thead").on("click", "th[data-ing-sort-key]", function () {
      const key = $(this).data("ing-sort-key");
      if (!key) return;
      if (ingredientSort.key === key) {
        ingredientSort.direction = ingredientSort.direction === "asc" ? "desc" : "asc";
      } else {
        ingredientSort.key = key;
        ingredientSort.direction = "asc";
      }
      renderIngredients();
    });

    $("#dish_tbl thead").on("click", "th[data-dish-sort-key]", function () {
      const key = $(this).data("dish-sort-key");
      if (!key) return;
      if (dishSort.key === key) {
        dishSort.direction = dishSort.direction === "asc" ? "desc" : "asc";
      } else {
        dishSort.key = key;
        dishSort.direction = "asc";
      }
      renderDishes();
    });

    $("#dish_q").on("input", onDishSearchInput);
    $("#dish_ing_filter").on("input", function () {
      const keyword = ($(this).val() || "").trim();
      debouncedSuggestIngredients(keyword);
    });
    $("#dish_ing_filter_apply").on("click", async () => {
      await runWithMsg(DOM.msgDish, async () => {
        const rawText = ($("#dish_ing_filter").val() || "").trim();
        const resolvedId = resolveIngredientId(rawText);
        if (!resolvedId) {
          throw new Error("食材過濾只接受食材名稱/ID，請從提示清單選取或輸入正確 ID。");
        }
        let ing = catalog.ingById.get(resolvedId);
        if (!ing) {
          const found = await searchIngredients(resolvedId, 20);
          ing = (Array.isArray(found) ? found : []).find(x => x?.id === resolvedId) || null;
        }
        await applyDishIngredientFilter(resolvedId, ing?.name || "");
      }, "已套用食材過濾。");
    });

    $("#dish_ing_filter_clear").on("click", async () => {
      await runWithMsg(DOM.msgDish, async () => {
        dishPager.ingredientId = "";
        dishPager.ingredientLabel = "";
        dishPager.page = 1;
        $("#dish_ing_filter").val("");
        await reloadCatalog();
        renderDishes();
      }, "已清除食材過濾。");
    });

    $("#ing_page_size").on("change", async function () {
      ingredientPager.pageSize = Number($(this).val() || 50);
      ingredientPager.page = 1;
      await reloadCatalog();
      renderIngredients();
    });

    $("#dish_page_size").on("change", async function () {
      dishPager.pageSize = Number($(this).val() || 50);
      dishPager.page = 1;
      await reloadCatalog();
      renderDishes();
    });

    $("#ing_prev_page").on("click", async () => {
      if (ingredientPager.page <= 1) return;
      ingredientPager.page -= 1;
      await reloadCatalog();
      renderIngredients();
    });

    $("#ing_next_page").on("click", async () => {
      if (ingredientPager.page >= ingredientPager.totalPages) return;
      ingredientPager.page += 1;
      await reloadCatalog();
      renderIngredients();
    });

    $("#dish_prev_page").on("click", async () => {
      if (dishPager.page <= 1) return;
      dishPager.page -= 1;
      await reloadCatalog();
      renderDishes();
    });

    $("#dish_next_page").on("click", async () => {
      if (dishPager.page >= dishPager.totalPages) return;
      dishPager.page += 1;
      await reloadCatalog();
      renderDishes();
    });

    $("#ing_jump_btn").on("click", async () => {
      const target = Number($("#ing_page_jump").val() || 1);
      ingredientPager.page = Math.min(Math.max(1, target), ingredientPager.totalPages);
      await reloadCatalog();
      renderIngredients();
    });

    $("#dish_jump_btn").on("click", async () => {
      const target = Number($("#dish_page_jump").val() || 1);
      dishPager.page = Math.min(Math.max(1, target), dishPager.totalPages);
      await reloadCatalog();
      renderDishes();
    });

    $("#ing_clear").on("click", () => {
      editingIngredientId = null;
      $("#ing_source_id").val("");
      clearFields(DOM.ingredientEditorFields);
      clearMsg(DOM.msgIng);
    });

    $("#dish_clear").on("click", () => {
      editingDishId = null;
      $("#dish_source_id").val("");
      clearFields(DOM.dishEditorFields);
      $("#dish_role").val("main");
      clearMsg(DOM.msgDish);
    });

    $("#ing_save").on("click", async () => {
      await runWithMsg(DOM.msgIng, async () => {
        await saveIngredient();
      }, "已儲存食材。");
    });

    $("#dish_save").on("click", async () => {
      await runWithMsg(DOM.msgDish, async () => {
        await saveDish();
      }, "已儲存菜色。");
    });

    $("#ing_export_excel").on("click", async () => {
      await runWithMsg(DOM.msgIng, async () => {
        const res = await exportIngredientsExcel({ q: ingredientPager.q });
        await downloadExcelFromResponse(res);
      }, "食材 Excel 匯出完成。");
    });

    $("#dish_export_excel").on("click", async () => {
      await runWithMsg(DOM.msgDish, async () => {
        const res = await exportDishesExcel({ q: dishPager.q, ingredientId: dishPager.ingredientId });
        await downloadExcelFromResponse(res);
      }, "菜名 Excel 匯出完成。");
    });

    $("#db_backup_reload").on("click", async () => {
      await runWithMsg(DOM.msgBackup, async () => {
        await refreshBackupList();
      }, `已載入備份清單，共 ${backupFiles.length} 筆。`);
    });

    $("#db_backup_restore").on("click", async () => {
      await runWithMsg(DOM.msgBackup, async () => {
        const selected = ($("#db_backup_select").val() || "").trim();
        if (!selected) throw new Error("請先選擇備份檔。");
        if (!confirm(`確定還原備份檔：${selected}？\n還原前會先備份目前資料庫。`)) return;
        await restoreDbBackup(selected);
        await refreshBackupList();
        await reloadCatalog();
        renderAll();
      }, "已完成備份還原，且已重新載入資料。");
    });

    $("#db_backup_delete").on("click", async () => {
      await runWithMsg(DOM.msgBackup, async () => {
        const selected = ($("#db_backup_select").val() || "").trim();
        if (!selected) throw new Error("請先選擇要刪除的備份檔。");
        if (!confirm(`確定刪除備份檔：${selected}？\n此操作無法復原。`)) return;
        await deleteDbBackup(selected);
        await refreshBackupList();
      }, "已刪除備份檔。");
    });

    $("#db_backup_select").on("change", () => {
      syncSelectedBackupMeta();
    });

    $("#db_backup_save_comment").on("click", async () => {
      await runWithMsg(DOM.msgBackup, async () => {
        const selected = ($("#db_backup_select").val() || "").trim();
        if (!selected) throw new Error("請先選擇要註解的備份檔。");
        const comment = ($("#db_backup_comment").val() || "").trim();
        await updateDbBackupComment(selected, comment);
        await refreshBackupList();
      }, "已儲存備份註解。");
    });

    $("#modal_close").on("click", () => $("#modal").addClass("hide"));
    $("#di_add").on("click", () => addDishIngRow(null));
    $("#di_preview_cost").on("click", async () => {
      await runWithMsg(DOM.msgDishCost, async () => {
        await refreshDishCostPreview();
      });
    });
    $("#di_save").on("click", async () => {
      await runWithMsg(DOM.msgDishIngredients, async () => {
        await saveDishIngredients();
        await reloadDishCostPreview(catalog.dishes.map(x => x.id));
        renderDishes();
        $("#modal").addClass("hide");
      }, "已更新食材清單。");
    });

    $("#modal_ing_close").on("click", () => $("#modal_ing").addClass("hide"));
    
    $("#inv_save").on("click", async () => {
      await runWithMsg(DOM.msgIngMeta, async () => {
        const body = {
          qty_on_hand: parseFloat($("#inv_qty").val() || "0"),
          unit: ($("#inv_unit").val() || "").trim(),
          updated_at: $("#inv_updated").val() || todayStr(),
          expiry_date: $("#inv_expiry").val() || null
        };
        if (!body.unit) throw new Error("庫存單位必填。");
        await putIngredientInventory(editingIngId, body);
      }, "已儲存庫存。");
    });
    
    $("#price_add").on("click", () => addPriceRow(null));
    
    $("#price_save").on("click", async () => {
      await runWithMsg(DOM.msgIngMeta, async () => {
        const ops = [];
        $("#price_tbl tbody tr").each(function () {
          const d = $(this).find(".p_date").val();
          const v = parseFloat($(this).find(".p_val").val() || "0");
          const u = ($(this).find(".p_unit").val() || "").trim();
          if (!d || !(v > 0) || !u) return;
          ops.push({ d, v, u });
        });
    
        if (!ops.length) throw new Error("請至少填一筆有效價格（日期/單價/單位）。");
    
        for (const x of ops) {
          await putIngredientPrice(editingIngId, x.d, { price_per_unit: x.v, unit: x.u });
        }
        await reloadDishCostPreview(catalog.dishes.map(x => x.id));
        renderDishes();

      }, "已儲存價格。");
    });

    // admin key
    $("#admin_key").val(adminKey());
    $("#save_admin_key").on("click", () => {
      localStorage.setItem("menu_admin_key", ($("#admin_key").val() || "").trim());
      alert("已儲存。");
    });
    $("#clear_admin_key").on("click", () => {
      localStorage.removeItem("menu_admin_key");
      $("#admin_key").val("");
      alert("已清除。");
    });
  }

  $(async function () {
    bindUI();
    ingredientPager.q = readInitialIngredientQuery();
    if (ingredientPager.q) {
      $("#ing_q").val(ingredientPager.q);
    }
    await reloadCatalog();
    await refreshBackupList();
    rebuildIngredientDatalist([]);
    renderAll();
    syncEditorPaneHeights();
  });
  })();
}
