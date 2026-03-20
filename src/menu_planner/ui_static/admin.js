import { deleteDish, deleteIngredient, deleteIngredientPrice, getDishIngredients, getIngredientInventory, getIngredientPrices, listDishCostPreview, loadCatalogPage, previewDishCost, putDishIngredients, putIngredientInventory, putIngredientPrice, searchIngredients, upsertDish, upsertIngredient } from "./admin/api.js";
import { createCatalogCache, setCatalogCache } from "./shared/catalog_cache.js";
import { adminKey } from "./shared/http.js";
import { escapeHtml } from "./shared/html.js";

(function () {

  const DOM = {
    msgIng: "#msg_ing",
    msgDish: "#msg_dish",
    msgDishIngredients: "#msg_di",
    msgDishCost: "#msg_di_cost",
    msgIngMeta: "#msg_ing_meta",
    ingredientEditorFields: "#ing_id,#ing_name,#ing_category,#ing_protein,#ing_unit",
    dishEditorFields: "#dish_id,#dish_name,#dish_meat,#dish_cuisine,#dish_tags",
  };

  const catalog = createCatalogCache();

  let editingDishId = null;
  let ingLabelToId = new Map();
  let editingIngId = null;
  let dishCostById = new Map();
  const ingredientPager = { page: 1, pageSize: 50, total: 0, totalPages: 1, q: "" };
  const dishPager = { page: 1, pageSize: 50, total: 0, totalPages: 1, q: "" };
  let catalogLoadSeq = 0;
  let ingredientSuggestSeq = 0;
  
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

    const maxHeight = panes.reduce((mx, pane) => Math.max(mx, pane.offsetHeight), 0);
    panes.forEach((pane) => {
      pane.style.minHeight = `${maxHeight}px`;
    });
  }

  function debounce(fn, wait = 300) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
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
    $("#ing_prev_page").prop("disabled", ingredientPager.page <= 1);
    $("#ing_next_page").prop("disabled", ingredientPager.page >= ingredientPager.totalPages);
    $("#dish_prev_page").prop("disabled", dishPager.page <= 1);
    $("#dish_next_page").prop("disabled", dishPager.page >= dishPager.totalPages);
    $("#ing_page_jump").val(ingredientPager.page);
    $("#dish_page_jump").val(dishPager.page);
    await reloadDishCostPreview(dishItems.map(x => x.id));
  }

  async function reloadDishCostPreview(dishIds = []) {
    try {
      const list = await listDishCostPreview(dishIds);
      dishCostById = new Map((Array.isArray(list) ? list : []).map(x => [x.dish_id, x]));
    } catch (_e) {
      dishCostById = new Map();
    }
  }

  function formatDishCostText(dishId) {
    const c = dishCostById.get(dishId);
    if (!c) return "—";
    const base = Number(c.per_serving_cost || 0).toFixed(2);
    const warningCount = Number(c.warning_count || 0);
    return warningCount > 0 ? `${base} ⚠️${warningCount}` : base;
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

  function renderIngredients() {
    const list = catalog.ingredients;

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
            <button class="btn_edit">編輯</button>
			<button class="btn_meta">價格/庫存</button>
            <button class="btn_del">刪除</button>
          </td>
        </tr>
      `);

      $tr.find(".btn_edit").on("click", () => {
        $("#ing_id").val(x.id);
        $("#ing_name").val(x.name);
        $("#ing_category").val(x.category);
        $("#ing_protein").val(x.protein_group || "");
        $("#ing_unit").val(x.default_unit);
        clearMsg(DOM.msgIng);
      });
	  
      $tr.find(".btn_meta").on("click", async () => {
        await runWithMsg(DOM.msgIng, async () => {
          await openIngMeta(x.id);
        });
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
    const list = catalog.dishes;

    const $tb = $("#dish_tbl tbody").empty();
    list.forEach(x => {
      const $tr = $(`
        <tr>
          <td>${escapeHtml(x.id)}</td>
          <td>${escapeHtml(x.name)}</td>
          <td>${escapeHtml(x.role)}</td>
          <td>${escapeHtml(x.meat_type || "")}</td>
          <td>${escapeHtml(x.cuisine || "")}</td>
          <td>${escapeHtml(formatDishCostText(x.id))}</td>
          <td>
            <button class="btn_edit">編輯</button>
            <button class="btn_ing">編輯食材</button>
            <button class="btn_del">刪除</button>
          </td>
        </tr>
      `);

      $tr.find(".btn_edit").on("click", () => {
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
    const requestSeq = ++ingredientSuggestSeq;
    const items = await searchIngredients(keyword, 20).catch(() => []);
    if (requestSeq !== ingredientSuggestSeq) return;
    rebuildIngredientDatalist(items);
  }, 250);
  
  async function saveIngredient() {
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

    await upsertIngredient(id, body);

    $("#ing_id").val(id); // 若自動產生，回填給使用者
    await reloadCatalog();
    renderAll();
  }

  async function saveDish() {
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

    await upsertDish(id, body);

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
        await openIngredientEditorFromDishRow($ing);
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

  async function openIngredientEditorFromDishRow($ingInput) {
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

    $("#ing_id").val(ing.id);
    $("#ing_name").val(ing.name || "");
    $("#ing_category").val(ing.category || "");
    $("#ing_protein").val(ing.protein_group || "");
    $("#ing_unit").val(ing.default_unit || "");
    clearMsg(DOM.msgIng);
    $("#modal").addClass("hide");
    document.getElementById("ing_id")?.scrollIntoView({ behavior: "smooth", block: "center" });
    $("#ing_name").trigger("focus");
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
    const warningCount = Array.isArray(preview.warnings) ? preview.warnings.length : 0;
    const warningText = warningCount > 0
      ? `（⚠️ ${warningCount} 項警示：可能是單位對不上或缺價格）`
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
    $("#dish_q").on("input", onDishSearchInput);

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
      clearFields(DOM.ingredientEditorFields);
      clearMsg(DOM.msgIng);
    });

    $("#dish_clear").on("click", () => {
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
    await reloadCatalog();
    const initialSuggestions = await searchIngredients("", 20).catch(() => []);
    rebuildIngredientDatalist(initialSuggestions);
    renderAll();
    syncEditorPaneHeights();
  });
})();
