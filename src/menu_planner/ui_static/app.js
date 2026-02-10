(function () {
  const API = {
    defaults: "/config/default",
    validate: "/config/validate",
    plan: "/plan",
    ingredients: "/catalog/ingredients",
    dishes: "/catalog/dishes",
    exportExcel: "/export/excel"
  };

  let baseDefaults = null;
  let ING = [];           // ingredients list
  let DISHES = [];        // dishes list
  let dishById = new Map();
  let ingById = new Map();

  let lastCfg = null;
  let lastResult = null;

  function setMsg(text, isError) {
    $("#msg").text(text).toggleClass("err", !!isError);
  }
  function pretty(obj) { return JSON.stringify(obj, null, 2); }

  function formatErrors(errs) {
    if (!errs || !errs.length) return "（無更多資訊）";
  
    return errs.map(e => {
      if (typeof e === "string") return e;
      if (!e || typeof e !== "object") return String(e);
  
      const code = e.code ? `[${e.code}] ` : "";
      const msg = e.message || "(no message)";
  
      // ✅ 把 traceback 印出來
      const trace = (e.details && e.details.trace) ? ("\n" + e.details.trace) : "";
  
      // 其他你想補的細節也可放這裡（避免只看到 message）
      const extra = (e.details && !e.details.trace) ? ("\n" + JSON.stringify(e.details, null, 2)) : "";
  
      return code + msg + trace + extra;
    }).join("\n\n- ");
  }

  function showErrorDetail(payload) {
    const errs = payload?.errors || [];
    const trace = errs.map(e => e?.details?.trace).filter(Boolean).join("\n\n");
    const text = trace || JSON.stringify(payload, null, 2);
  
    $("#result").html(`
      <div class="errbox">
        <details open>
          <summary>錯誤詳情（含 traceback）</summary>
          <pre class="pre">${escapeHtml(text)}</pre>
        </details>
      </div>
    `);
  }

  // -------- chips helpers --------
  function addChip($box, id, label) {
    if ($box.find(`.chip[data-id="${id}"]`).length) return;
    const $c = $(`<span class="chip" data-id="${id}"><span class="t"></span><span class="x">×</span></span>`);
    $c.find(".t").text(label);
    $c.on("click", function () { $(this).remove(); syncCfgTextareaFromForm(); });
    $box.append($c);
  }
  function readChipIds($box) {
    const ids = [];
    $box.find(".chip").each(function () { ids.push($(this).data("id")); });
    return ids;
  }
  function clearChips($box) { $box.empty(); }

  // -------- suggest dropdown --------
  function showSuggest($el, items, onPick) {
    if (!items.length) { $el.hide(); $el.empty(); return; }
    $el.empty();
    items.forEach(it => {
      const $row = $(`<div class="item"></div>`);
      $row.append(`<div>${escapeHtml(it.label)}</div>`);
      $row.append(`<div class="meta">${escapeHtml(it.meta || "")}</div>`);
      $row.on("click", () => { onPick(it); $el.hide(); });
      $el.append($row);
    });
    $el.show();
  }
  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  }

  // -------- form <-> cfg --------
  function buildCfgFromForm(baseCfg) {
    const cfg = JSON.parse(JSON.stringify(baseCfg || {}));

    cfg.horizon_days = parseInt($("#horizon_days").val() || "30", 10);

    cfg.hard = cfg.hard || {};
    cfg.soft = cfg.soft || {};
    cfg.weights = cfg.weights || {};
    cfg.search = cfg.search || {};

    cfg.hard.cost_range_per_person_per_day = {
      min: parseFloat($("#cost_min").val() || "0"),
      max: parseFloat($("#cost_max").val() || "0")
    };

    // meat types allowed
    const meats = [];
    $("#meat_types input[type=checkbox]:checked").each(function () { meats.push($(this).val()); });
    cfg.hard.allowed_main_meat_types = meats;

    cfg.hard.no_consecutive_same_main_meat = $("#no_consecutive_meat").is(":checked");

    // weekly quota table
    const weekly = {};
    $("#weekly_quota_table .quota").each(function () {
      const meat = $(this).data("meat");
      const v = parseInt($(this).val() || "0", 10);
      weekly[meat] = v;
    });
    cfg.hard.weekly_max_main_meat = weekly;

    // prefer flags
    cfg.soft.prefer_use_inventory = $("#prefer_inventory").is(":checked");
    cfg.soft.prefer_near_expiry = $("#prefer_expiry").is(":checked");

    // preferred ingredients
    cfg.soft.inventory_prefer_ingredient_ids = readChipIds($("#ingredient_chips"));

    // exclude dishes
    cfg.hard.exclude_dish_ids = readChipIds($("#exclude_dish_chips"));

    return cfg;
  }

  function applyCfgToForm(cfg) {
    $("#horizon_days").val(cfg.horizon_days ?? 30);

    const cr = (cfg.hard && cfg.hard.cost_range_per_person_per_day) || {};
    $("#cost_min").val(cr.min ?? 0);
    $("#cost_max").val(cr.max ?? 0);

    // meat types
    const allowed = new Set(((cfg.hard && cfg.hard.allowed_main_meat_types) || []));
    $("#meat_types input[type=checkbox]").each(function () {
      const v = $(this).val();
      $(this).prop("checked", allowed.size ? allowed.has(v) : true);
    });

    $("#no_consecutive_meat").prop("checked", !!(cfg.hard && cfg.hard.no_consecutive_same_main_meat));

    // weekly quota
    const weekly = (cfg.hard && cfg.hard.weekly_max_main_meat) || {};
    $("#weekly_quota_table .quota").each(function () {
      const meat = $(this).data("meat");
      if (weekly[meat] !== undefined) $(this).val(weekly[meat]);
    });

    $("#prefer_inventory").prop("checked", !!(cfg.soft && cfg.soft.prefer_use_inventory));
    $("#prefer_expiry").prop("checked", !!(cfg.soft && cfg.soft.prefer_near_expiry));

    // chips
    clearChips($("#ingredient_chips"));
    (cfg.soft && cfg.soft.inventory_prefer_ingredient_ids || []).forEach(id => {
      const ing = ingById.get(id);
      addChip($("#ingredient_chips"), id, ing ? ing.name : id);
    });

    clearChips($("#exclude_dish_chips"));
    (cfg.hard && cfg.hard.exclude_dish_ids || []).forEach(id => {
      const d = dishById.get(id);
      addChip($("#exclude_dish_chips"), id, d ? `[${d.role}] ${d.name}` : id);
    });
  }

  function syncCfgTextareaFromForm() {
    if (!baseDefaults) return;
    const cfg = buildCfgFromForm(baseDefaults);
    $("#cfg_json").val(pretty(cfg));
    lastCfg = cfg;
  }

  // -------- API calls --------
  async function loadDefaults() {
    const res = await fetch(API.defaults);
    const cfg = await res.json();
    baseDefaults = cfg;
    $("#cfg_json").val(pretty(cfg));
    applyCfgToForm(cfg);
    syncCfgTextareaFromForm();
    setMsg("已載入預設設定。");
  }

  async function loadCatalog() {
    const [r1, r2] = await Promise.all([fetch(API.ingredients), fetch(API.dishes)]);
    ING = await r1.json();
    DISHES = await r2.json();
    ingById = new Map(ING.map(x => [x.id, x]));
    dishById = new Map(DISHES.map(x => [x.id, x]));
  }

  async function validateCfg(cfg) {
    const res = await fetch(API.validate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg)
    });
    return await res.json();
  }

  function renderResult(r) {
	  
    const errByDay = new Map();
    (r.errors || []).forEach(e => {
      const k = e.day_index;
      if (k === undefined || k === null) return;
      if (!errByDay.has(k)) errByDay.set(k, []);
      errByDay.get(k).push(e);
    });

    const s = r.summary || {};
    const days = r.days || [];

    let html = "";
    html += `<div class="summary">
      <div><b>天數</b>：${s.days}</div>
      <div><b>總成本</b>：${s.total_cost}</div>
      <div><b>平均/日</b>：${s.avg_cost_per_day}</div>
      <div><b>總分數</b>：${s.total_score}</div>
    </div>`;

    html += `<table class="tbl">
      <thead>
        <tr>
          <th>日期</th><th>主菜</th><th>配菜</th><th>湯</th><th>水果</th><th>成本</th><th>分數</th>
        </tr>
      </thead>
      <tbody>`;

    days.forEach((d, idx) => {
      const dayIndex = (d.day_index ?? idx);
      const dayErrs = errByDay.get(dayIndex) || [];
      const isFailed = (dayErrs.length > 0) || !!d.failed;
    
      // 失敗日：顯示原因，不要硬取 sides/soup/fruit
      if (isFailed) {
        const mainName =
          (d.items && d.items.main && d.items.main.name)
            ? d.items.main.name
            : "(主菜已排但明細不足)";
    
        const reason =
          dayErrs.map(e => (e.message || e.code)).filter(Boolean).join(" / ")
          || "當天無可行組合";
    
        html += `<tr class="row-failed">
          <td>${d.date || ""}</td>
          <td>${escapeHtml(mainName)}</td>
          <td colspan="3"><span class="warn">⚠️ 排程失敗</span>：${escapeHtml(reason)}</td>
          <td>${d.day_cost ?? ""}</td>
          <td></td>
        </tr>`;
    
        const detailJson = dayErrs.length ? pretty(dayErrs) : pretty({ message: reason });
        html += `<tr class="explain">
          <td colspan="7">
            <details open>
              <summary>原因與建議</summary>
              <pre class="pre">${escapeHtml(detailJson)}</pre>
            </details>
          </td>
        </tr>`;
        return;
      }
    
      // 成功日：安全取值
      const main = d.items?.main?.name || "";
      const sides = (d.items?.sides || []).map(x => x?.name).filter(Boolean).join("、");
      const soup = d.items?.soup?.name || "";
      const fruit = d.items?.fruit?.name || "";
      const cost = d.day_cost ?? "";
      const score = (d.score ?? "");
    
      html += `<tr>
        <td>${d.date}</td>
        <td>${escapeHtml(main)}</td>
        <td>${escapeHtml(sides)}</td>
        <td>${escapeHtml(soup)}</td>
        <td>${escapeHtml(fruit)}</td>
        <td>${cost}</td>
        <td>${score}</td>
      </tr>`;
    
      const breakdown = d.score_breakdown || {};
      const bRows = Object.keys(breakdown)
        .map(k => `<div class="bd"><span>${escapeHtml(k)}</span><span>${breakdown[k]}</span></div>`)
        .join("");
    
      html += `<tr class="explain">
        <td colspan="7">
          <details>
            <summary>可解釋明細</summary>
            <div class="explain-box">
              <div class="ex-title">打分拆解</div>
              <div class="bd-list">${bRows || "<div class='muted'>（無）</div>"}</div>
              <div class="ex-title">庫存使用（ID）</div>
              <pre class="pre">${escapeHtml(pretty({
                main: d.items?.main?.used_inventory_ingredients,
                soup: d.items?.soup?.used_inventory_ingredients,
                sides: (d.items?.sides || []).map(x => x?.used_inventory_ingredients)
              }))}</pre>
            </div>
          </details>
        </td>
      </tr>`;
    });
    // ✅ 補齊表格結尾 + 把結果塞回畫面
    html += `</tbody></table>`;
    $("#result").html(html);
  } // ✅ renderResult 結束
  
  async function downloadExcel(cfg) {
    const res = await fetch(API.exportExcel, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg)
    });
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json()).detail; } catch (e) {}
      let msg = "";
      if (Array.isArray(detail)) msg = detail.join(" / ");
      else if (detail && typeof detail === "object") msg = detail.message || JSON.stringify(detail);
      else msg = String(detail || "");
      throw new Error("匯出失敗：" + msg);
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);

    // 嘗試從 header 拿檔名
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

  // -------- search interactions --------
  function bindIngredientSearch() {
    const $input = $("#ingredient_search");
    const $suggest = $("#ingredient_suggest");
    const $chips = $("#ingredient_chips");

    $input.on("input focus", function () {
      const q = ($input.val() || "").trim().toLowerCase();
      if (!q) { $suggest.hide(); return; }
      const hits = ING
        .filter(x => (x.name || "").toLowerCase().includes(q))
        .slice(0, 12)
        .map(x => ({ id: x.id, label: x.name, meta: x.category || "" }));
      showSuggest($suggest, hits, (it) => {
        addChip($chips, it.id, it.label);
        $input.val("");
        syncCfgTextareaFromForm();
      });
    });

    $(document).on("click", function (e) {
      if (!$(e.target).closest("#ingredient_search, #ingredient_suggest").length) $suggest.hide();
    });
  }

  function bindDishSearch() {
    const $input = $("#dish_search");
    const $role = $("#dish_role_filter");
    const $suggest = $("#dish_suggest");
    const $chips = $("#exclude_dish_chips");

    function run() {
      const q = ($input.val() || "").trim().toLowerCase();
      if (!q) { $suggest.hide(); return; }
      const role = $role.val();
      const hits = DISHES
        .filter(d => (!role || d.role === role))
        .filter(d => (d.name || "").toLowerCase().includes(q))
        .slice(0, 12)
        .map(d => ({ id: d.id, label: `[${d.role}] ${d.name}`, meta: d.meat_type || d.cuisine || "" }));
      showSuggest($suggest, hits, (it) => {
        addChip($chips, it.id, it.label);
        $input.val("");
        syncCfgTextareaFromForm();
      });
    }

    $input.on("input focus", run);
    $role.on("change", run);

    $(document).on("click", function (e) {
      if (!$(e.target).closest("#dish_search, #dish_suggest, #dish_role_filter").length) $suggest.hide();
    });
  }

  // -------- main init --------
  $(async function () {
    try {
      setMsg("載入資料中…");
      await loadCatalog();
      await loadDefaults();

      bindIngredientSearch();
      bindDishSearch();

      // 表單變動就同步 JSON（讓右側 JSON 始終對得上）
      $("#horizon_days,#cost_min,#cost_max,#no_consecutive_meat,#prefer_inventory,#prefer_expiry,#dish_role_filter")
        .on("change input", syncCfgTextareaFromForm);
      $("#meat_types input[type=checkbox]").on("change", syncCfgTextareaFromForm);
      $("#weekly_quota_table .quota").on("change input", syncCfgTextareaFromForm);

      $("#btn_load_defaults").on("click", async () => {
        await loadDefaults();
        lastResult = null;
        $("#btn_export_excel").prop("disabled", true);
      });

      $("#btn_apply_json").on("click", () => {
        try {
          const cfg = JSON.parse($("#cfg_json").val());
          applyCfgToForm(cfg);
          syncCfgTextareaFromForm();
          setMsg("已套用 JSON 到表單。");
        } catch (e) {
          setMsg("JSON 解析失敗：請檢查格式。", true);
        }
      });

      $("#btn_validate").on("click", async () => {
        try {
          const cfg = JSON.parse($("#cfg_json").val());
          const v = await validateCfg(cfg);
          if (v.ok) setMsg("驗證通過。");
          else setMsg("驗證失敗：\n- " + v.errors.join("\n- "), true);
        } catch (e) {
          setMsg("JSON 解析失敗：請檢查格式。", true);
        }
      });

      $("#btn_plan").on("click", async () => {
        setMsg("排程中…");
        $("#btn_export_excel").prop("disabled", true);

        try {
          // 以表單為準，更新 JSON
          syncCfgTextareaFromForm();
          const cfg = JSON.parse($("#cfg_json").val());
          lastCfg = cfg;

          const v = await validateCfg(cfg);
          if (!v.ok) {
            setMsg("驗證失敗：\n- " + v.errors.join("\n- "), true);
            return;
          }

          const res = await fetch(API.plan, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(cfg)
          });
          const payload = await res.json();
		  
          if (!payload.ok) {
            console.error("PLAN ERROR payload =", payload);
            setMsg("產生失敗：\n- " + formatErrors(payload.errors), true);
            showErrorDetail(payload);   // ✅ 直接把 traceback 印在 result 區
            return;
          }

          lastResult = payload.result;
          setMsg("完成。");
          renderResult(payload.result);
          $("#btn_export_excel").prop("disabled", false);
        } catch (e) {
          setMsg("產生失敗：請檢查 console 或後端 log。", true);
        }
      });

      $("#btn_export_excel").on("click", async () => {
        try {
          // 若使用者又改了表單，先同步一次
          syncCfgTextareaFromForm();
          const cfg = JSON.parse($("#cfg_json").val());
          await downloadExcel(cfg);
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
})();
