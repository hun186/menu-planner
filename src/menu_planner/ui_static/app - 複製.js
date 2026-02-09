(function () {
  const API = {
    defaults: "/config/default",
    validate: "/config/validate",
    plan: "/plan"
  };

  function setMsg(text, isError) {
    $("#msg").text(text).toggleClass("err", !!isError);
  }

  function pretty(obj) {
    return JSON.stringify(obj, null, 2);
  }

  function readCfgFromForm(baseCfg) {
    const cfg = JSON.parse(JSON.stringify(baseCfg || {}));

    cfg.horizon_days = parseInt($("#horizon_days").val() || "30", 10);

    cfg.hard = cfg.hard || {};
    cfg.hard.cost_range_per_person_per_day = {
      min: parseFloat($("#cost_min").val() || "0"),
      max: parseFloat($("#cost_max").val() || "0")
    };

    cfg.hard.no_consecutive_same_main_meat = $("#no_consecutive_meat").is(":checked");

    const meats = [];
    $("#meat_types input[type=checkbox]:checked").each(function () {
      meats.push($(this).val());
    });
    cfg.hard.allowed_main_meat_types = meats;

    cfg.soft = cfg.soft || {};
    cfg.soft.prefer_use_inventory = $("#prefer_inventory").is(":checked");
    cfg.soft.prefer_near_expiry = $("#prefer_expiry").is(":checked");

    return cfg;
  }

  async function loadDefaults() {
    const res = await fetch(API.defaults);
    const cfg = await res.json();
    $("#cfg_json").val(pretty(cfg));
    setMsg("已載入預設設定。");
    return cfg;
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

    days.forEach(d => {
      const main = d.items.main.name;
      const sides = d.items.sides.map(x => x.name).join("、");
      const soup = d.items.soup.name;
      const fruit = d.items.fruit.name;
      const cost = d.day_cost;
      const score = (d.score ?? "");
      html += `<tr>
        <td>${d.date}</td>
        <td>${main}</td>
        <td>${sides}</td>
        <td>${soup}</td>
        <td>${fruit}</td>
        <td>${cost}</td>
        <td>${score}</td>
      </tr>`;

      const breakdown = d.score_breakdown || {};
      const bRows = Object.keys(breakdown).map(k => `<div class="bd"><span>${k}</span><span>${breakdown[k]}</span></div>`).join("");

      html += `<tr class="explain">
        <td colspan="7">
          <details>
            <summary>可解釋明細</summary>
            <div class="explain-box">
              <div class="ex-title">打分拆解</div>
              <div class="bd-list">${bRows || "<div class='muted'>（無）</div>"}</div>

              <div class="ex-title">庫存/到期</div>
              <pre class="pre">${pretty({
                main: d.items.main.used_inventory_ingredients,
                soup: d.items.soup.used_inventory_ingredients,
                sides: d.items.sides.map(x => x.used_inventory_ingredients)
              })}</pre>
            </div>
          </details>
        </td>
      </tr>`;
    });

    html += `</tbody></table>`;
    $("#result").html(html);
  }

  let baseDefaults = null;

  $(async function () {
    baseDefaults = await loadDefaults();

    $("#btn_load_defaults").on("click", async () => {
      baseDefaults = await loadDefaults();
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
      try {
        // 先用表單覆蓋 defaults，再寫回 textarea（讓使用者知道送出的 JSON 長什麼樣）
        const cfg = readCfgFromForm(baseDefaults);
        $("#cfg_json").val(pretty(cfg));

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
          setMsg("產生失敗：\n- " + (payload.errors || []).join("\n- "), true);
          return;
        }

        setMsg("完成。");
        renderResult(payload.result);
      } catch (e) {
        setMsg("產生失敗：請檢查 console 或後端 log。", true);
      }
    });
  });
})();
