import { deleteDish, deleteIngredient, deleteIngredientPrice, getDishIngredients, getIngredientInventory, getIngredientPrices, listDishCostPreview, loadCatalog, previewDishCost, putDishIngredients, putIngredientInventory, putIngredientPrice, upsertDish, upsertIngredient } from "./admin/api.js";
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
  
  function setMsg($el, text, isError) {
    $el.css("color", isError ? "#b42318" : "#1a7f37").text(text || "");
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

  async function reloadCatalog() {
    const { ingredients, dishes } = await loadCatalog();
    setCatalogCache(catalog, ingredients, dishes);
    await reloadDishCostPreview();
  }

  async function reloadDishCostPreview() {
    try {
      const list = await listDishCostPreview();
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
  
  function rebuildIngredientDatalist() {
    ingLabelToId = new Map();
    const $dl = $("#dl_ingredients").empty();
  
    catalog.ingredients.forEach(x => {
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
    const q = ($("#ing_q").val() || "").trim().toLowerCase();
    const list = catalog.ingredients.filter(x =>
      !q ||
      (x.id || "").toLowerCase().includes(q) ||
      (x.name || "").toLowerCase().includes(q)
    );

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
		  rebuildIngredientDatalist();
          renderAll();
        }, "已刪除食材。");
      });
	  

      $tb.append($tr);
    });
  }

  function renderDishes() {
    const q = ($("#dish_q").val() || "").trim().toLowerCase();
    const list = catalog.dishes.filter(x =>
      !q ||
      (x.id || "").toLowerCase().includes(q) ||
      (x.name || "").toLowerCase().includes(q)
    );

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
  }

  function resolveIngredientId(inputText) {
    const t = (inputText || "").trim();
    if (!t) return null;
  
    // 1) 直接輸入 ID
    if (catalog.ingById.has(t)) return t;
  
    // 2) 從 "... (id)" 抓 id
    const m = t.match(/\(([^()]+)\)\s*$/);
    if (m && catalog.ingById.has(m[1])) return m[1];
  
    // 3) 完整 label
    if (ingLabelToId.has(t)) return ingLabelToId.get(t);
  
    // 4) 最後：若只輸入名稱，嘗試唯一匹配
    const exact = catalog.ingredients.filter(x => x.name === t);
    if (exact.length === 1) return exact[0].id;
  
    return null;
  }
  
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
    const initLabel = initIng ? `${initIng.category}｜${initIng.name} (${initIng.id})` : "";
  
    const $ing = $(`<input class="di_ing_input" list="dl_ingredients" placeholder="輸入食材名稱或ID">`)
      .val(initLabel)
      .data("ing_id", initId || "");
  
    // 當使用者改輸入時，嘗試解析成 id，存到 data
    $ing.on("input change blur", function () {
      const id = resolveIngredientId($(this).val());
      $(this).data("ing_id", id || "");
      $(this).css("border-color", id ? "" : "#ef4444");
    });
  
    const $qty = $(`<input class="di_qty" type="number" step="0.1">`).val(row?.qty ?? 100);
    const $unit = $(`<input class="di_unit" type="text">`).val(row?.unit ?? "g");
  
    const $del = $(`<button>刪除</button>`).on("click", () => $tr.remove());
  
    $tr.append($("<td></td>").append($ing));
    $tr.append($("<td></td>").append($qty));
    $tr.append($("<td></td>").append($unit));
    $tr.append($("<td></td>").append($del));
  
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
    $("#ing_q").on("input", renderIngredients);
    $("#dish_q").on("input", renderDishes);

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
        await reloadDishCostPreview();
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
        await reloadDishCostPreview();
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
	rebuildIngredientDatalist();
    renderAll();
  });
})();
