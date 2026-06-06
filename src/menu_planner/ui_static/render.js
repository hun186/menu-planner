import { DOM } from "./dom.js";
import { scoreLabel, scoreReason, summarizeBreakdown } from "./score_explain.js";
import { escapeHtml as _escapeHtml } from "./shared/html.js";

export function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

export function setMsg(text, isError = false) {
  $(DOM.msg).text(text).toggleClass("err", !!isError);
}

export function escapeHtml(s) {
  return _escapeHtml(s);
}

export function formatErrors(errs) {
  if (!errs || !errs.length) return "（無更多資訊）";
  return errs.map((e) => {
    if (typeof e === "string") return e;
    if (!e || typeof e !== "object") return String(e);
    const code = e.code ? `[${e.code}] ` : "";
    const msg = e.message || "(no message)";
    const trace = e.details?.trace ? (`\n${e.details.trace}`) : "";
    const extra = (e.details && !e.details.trace) ? (`\n${JSON.stringify(e.details, null, 2)}`) : "";
    return code + msg + trace + extra;
  }).join("\n\n- ");
}

export function showErrorDetail(payload) {
  const errs = payload?.errors || [];
  const trace = errs.map((e) => e?.details?.trace).filter(Boolean).join("\n\n");
  const text = trace || JSON.stringify(payload, null, 2);

  $(DOM.result).html(`
    <div class="errbox">
      <details open>
        <summary>錯誤詳情（含 traceback）</summary>
        <pre class="pre">${escapeHtml(text)}</pre>
      </details>
    </div>
  `);
}

export function shouldRenderFailedRow(day, dayErrs = []) {
  const hasError = (dayErrs?.length || 0) > 0 || !!day?.failed;
  if (!hasError) return false;

  const items = day?.items || {};
  const hasSides = Array.isArray(items.sides) && items.sides.length > 0;
  const hasVeg = !!(items.veg?.id || items.veg?.name);
  const hasSoup = !!(items.soup?.id || items.soup?.name);
  const hasFruit = !!(items.fruit?.id || items.fruit?.name);

  // 若配菜/蔬菜/湯/水果全空，代表該日幾乎無可用內容，才渲染成「整列失敗」。
  return !(hasSides || hasVeg || hasSoup || hasFruit);
}



function renderProcurementDetail(day) {
  const procurement = day?.procurement || {};
  const dishes = procurement?.dishes || [];
  if (!dishes.length) return "<div class='muted'>（無採買明細）</div>";

  const rows = [];
  dishes.forEach((dish) => {
    (dish.ingredients || []).forEach((ing) => {
      rows.push(`<tr>
        <td>${escapeHtml(dish.dish_name || "")}</td>
        <td>${escapeHtml(ing.ingredient_name || "")}</td>
        <td>${ing.qty_per_person ?? ""}</td>
        <td>${procurement.people ?? 250}</td>
        <td>${ing.qty_for_people ?? ""} ${escapeHtml(ing.qty_unit || "")}</td>
        <td>${ing.unit_price ?? ""} ${escapeHtml(ing.unit_price_unit || "")}</td>
        <td>${ing.line_total ?? ""}</td>
      </tr>`);
    });
  });

  return `<div class="ex-title">採買估算（依人數 ${procurement.people ?? 250}，日小計 ${procurement.day_total ?? 0}）</div>
    <table class="tbl">
      <thead><tr><th>菜名</th><th>食材</th><th>每人用量</th><th>人數</th><th>需求量</th><th>單價</th><th>小計</th></tr></thead>
      <tbody>${rows.join("")}</tbody>
    </table>`;
}

function renderEditableDish({ name, dayIndex, role, slot, dishId }) {
  const label = name || "（未指定）";
  const did = dishId || "";
  return `<button type="button" class="dish-edit-trigger" data-day-index="${dayIndex}" data-role="${role}" data-slot="${slot}" data-dish-id="${did}">${escapeHtml(label)}</button>`;
}

function isoWeekdayFromDateString(dateText) {
  if (typeof dateText !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(dateText)) return null;
  const date = new Date(`${dateText}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;
  const utcDay = date.getUTCDay();
  return utcDay === 0 ? 7 : utcDay;
}

function editableRoleSlotCount(cfg, dateText, role, fallbackCount) {
  const fallback = Number.isFinite(Number(fallbackCount)) && Number(fallbackCount) >= 0 ? Number(fallbackCount) : 0;
  const weekday = isoWeekdayFromDateString(dateText);
  const weekdayRoles = cfg?.per_weekday_roles || {};
  const dayRoles = cfg?.per_day_roles || {};
  const raw = weekday !== null && Object.prototype.hasOwnProperty.call(weekdayRoles, String(weekday))
    ? weekdayRoles[String(weekday)]?.[role]
    : dayRoles?.[role];
  const count = Number(raw);
  return Number.isFinite(count) && count >= 0 ? count : fallback;
}

export function renderResult(result, cfg, options = {}) {
  const editable = !!options.editable;
  const errByDay = new Map();
  (result.errors || []).forEach((e) => {
    const k = e.day_index;
    if (k === undefined || k === null) return;
    if (!errByDay.has(k)) errByDay.set(k, []);
    errByDay.get(k).push(e);
  });

  const s = result.summary || {};
  const days = result.days || [];
  const defaultPeople = Number(cfg?.people || s?.people || 250);
  const peopleOverrides = cfg?.schedule?.people_overrides || s?.people_overrides || {};

  let html = "";
  const rawTotal = Number(s.total_score ?? 0);
  const fitTotal = -rawTotal;

  html += `<div class="score-legend">
    <div><b>分數解讀</b>：系統把「扣分（+）」與「加分（-）」加總，<b>原始分數越低越好</b>。</div>
    <div>為了直覺，另外顯示 <b>目標匹配度 = -原始分數（越高越好）</b>。</div>
    <div class="muted">常見加分：使用庫存、使用近到期。常見扣分：成本超限、主菜連續同肉／同菜系。</div>
  </div>`;

  html += `<div class="summary">
    <div><b>天數</b>：${s.days}</div>
    <div><b>總成本</b>：${s.total_cost}</div>
    <div><b>平均/日</b>：${s.avg_cost_per_day}</div>
    <div><b>目標匹配度</b>：${fitTotal.toFixed(2)}</div>
  </div>`;

  html += `<table class="tbl">
    <thead>
      <tr>
        <th>日期</th><th>人數</th><th>主菜</th><th>麵食</th><th>配菜</th><th>純蔬配菜</th><th>湯</th><th>水果</th><th>成本</th><th>目標匹配度</th>
      </tr>
    </thead>
    <tbody>`;

  days.forEach((d, idx) => {
    const dayIndex = d.day_index ?? idx;
    const isScheduled = (d.is_scheduled !== undefined && d.is_scheduled !== null) ? !!d.is_scheduled : true;
    const dayErrs = errByDay.get(dayIndex) || [];
    const isFailed = shouldRenderFailedRow(d, dayErrs);

    if (!isScheduled) {
      html += `<tr class="row-offday">
        <td>${d.date || ""}</td>
        <td></td>
        <td colspan="6"><span class="muted">免排日（依排程設定）</span></td>
        <td></td>
        <td></td>
      </tr>`;
      return;
    }

    if (isFailed) {
      const mainName = d.items?.main?.name || "(主菜已排但明細不足)";
      const reason = dayErrs.map((e) => (e.message || e.code)).filter(Boolean).join(" / ") || "當天無可行組合";
      html += `<tr class="row-failed">
        <td>${d.date || ""}</td>
        <td>${defaultPeople}</td>
        <td>${escapeHtml(mainName)}</td>
        <td colspan="5"><span class="warn">⚠️ 排程失敗</span>：${escapeHtml(reason)}</td>
        <td>${d.day_cost ?? ""}</td>
        <td></td>
      </tr>`;

      const detailJson = dayErrs.length ? pretty(dayErrs) : pretty({ message: reason });
      html += `<tr class="explain">
        <td colspan="10">
          <details open>
            <summary>原因與建議</summary>
            <pre class="pre">${escapeHtml(detailJson)}</pre>
          </details>
        </td>
      </tr>`;
      return;
    }

    const mainObj = d.items?.main || {};
    const mainObjs = Array.isArray(d.items?.mains) && d.items.mains.length ? d.items.mains : (mainObj?.id || mainObj?.name ? [mainObj] : []);
    const noodleObj = d.items?.noodle || {};
    const noodleObjs = Array.isArray(d.items?.noodles) && d.items.noodles.length ? d.items.noodles : (noodleObj?.id || noodleObj?.name ? [noodleObj] : []);
    const sideObjs = d.items?.sides || [];
    const vegObj = d.items?.veg || {};
    const vegObjs = Array.isArray(d.items?.vegs) && d.items.vegs.length ? d.items.vegs : (vegObj?.id || vegObj?.name ? [vegObj] : []);
    const soupObj = d.items?.soup || {};
    const soupObjs = Array.isArray(d.items?.soups) && d.items.soups.length ? d.items.soups : (soupObj?.id || soupObj?.name ? [soupObj] : []);
    const fruitObj = d.items?.fruit || {};
    const fruitObjs = Array.isArray(d.items?.fruits) && d.items.fruits.length ? d.items.fruits : (fruitObj?.id || fruitObj?.name ? [fruitObj] : []);

    const main = mainObjs.map((x) => x?.name).filter(Boolean).join("、");
    const noodle = noodleObjs.map((x) => x?.name).filter(Boolean).join("、");
    const sides = sideObjs.map((x) => x?.name).filter(Boolean).join("、");
    const veg = vegObjs.map((x) => x?.name).filter(Boolean).join("、");
    const soup = soupObjs.map((x) => x?.name).filter(Boolean).join("、");
    const fruit = fruitObjs.map((x) => x?.name).filter(Boolean).join("、");
    const cost = d.day_cost ?? "";
    const rawScore = Number(d.score ?? 0);
    const fitness = (d.score_fitness !== undefined && d.score_fitness !== null) ? Number(d.score_fitness) : -rawScore;

    const mainCell = editable && isScheduled
      ? mainObjs.map((it, i) => renderEditableDish({ name: it?.name || `（選擇主菜${i + 1}）`, dayIndex, role: "main", slot: i === 0 ? "main" : `main_${i}`, dishId: it?.id })).join("<span class=\"dish-sep\">、</span>")
      : escapeHtml(main);

    const noodleCell = editable && isScheduled
      ? noodleObjs.map((it, i) => renderEditableDish({ name: it?.name || `（選擇麵食${i + 1}）`, dayIndex, role: "noodle", slot: i === 0 ? "noodle" : `noodle_${i}`, dishId: it?.id })).join("<span class=\"dish-sep\">、</span>")
      : escapeHtml(noodle);

    const sideSlotCount = editableRoleSlotCount(cfg, d.date, "side", 2);
    const sideCell = editable && isScheduled
      ? Array.from({ length: Math.max(sideObjs.length, sideSlotCount) }, (_, i) => {
        const it = sideObjs[i] || {};
        return renderEditableDish({
          name: it?.name || `（選擇配菜${i + 1}）`,
          dayIndex,
          role: "side",
          slot: `side_${i}`,
          dishId: it?.id,
        });
      }).join("<span class=\"dish-sep\">、</span>")
      : escapeHtml(sides);

    const vegCell = editable && isScheduled
      ? vegObjs.map((it, i) => renderEditableDish({ name: it?.name || `（選擇純蔬${i + 1}）`, dayIndex, role: "veg", slot: i === 0 ? "veg" : `veg_${i}`, dishId: it?.id })).join("<span class=\"dish-sep\">、</span>")
      : escapeHtml(veg);

    const soupCell = editable && isScheduled
      ? soupObjs.map((it, i) => renderEditableDish({ name: it?.name || `（選擇湯品${i + 1}）`, dayIndex, role: "soup", slot: i === 0 ? "soup" : `soup_${i}`, dishId: it?.id })).join("<span class=\"dish-sep\">、</span>")
      : escapeHtml(soup);

    const fruitCell = editable && isScheduled
      ? fruitObjs.map((it, i) => renderEditableDish({ name: it?.name || `（選擇水果${i + 1}）`, dayIndex, role: "fruit", slot: i === 0 ? "fruit" : `fruit_${i}`, dishId: it?.id })).join("<span class=\"dish-sep\">、</span>")
      : escapeHtml(fruit);

    const dayPeople = Number(peopleOverrides[d.date] ?? d.procurement?.people ?? defaultPeople);
    const peopleCell = editable && isScheduled
      ? `<input class="day-people-input" type="number" min="1" data-date="${escapeHtml(d.date || "")}" value="${dayPeople}" title="可覆寫單日用餐人數" />`
      : String(dayPeople);

    html += `<tr>
      <td>${d.date}</td>
      <td>${peopleCell}</td>
      <td>${mainCell}</td>
      <td>${noodleCell}</td>
      <td>${sideCell}</td>
      <td>${vegCell}</td>
      <td>${soupCell}</td>
      <td>${fruitCell}</td>
      <td>${cost}</td>
      <td><b>${fitness.toFixed(1)}</b></td>
    </tr>`;

    if (dayErrs.length > 0 || d.failed) {
      const reason = dayErrs.map((e) => (e.message || e.code)).filter(Boolean).join(" / ") || d.message || "部分欄位未滿足限制";
      const detailJson = dayErrs.length ? pretty(dayErrs) : pretty({ message: reason, reason_code: d.reason_code, details: d.details });
      html += `<tr class="explain">
        <td colspan="10">
          <details open>
            <summary>⚠️ 部分限制未滿足：${escapeHtml(reason)}</summary>
            <pre class="pre">${escapeHtml(detailJson)}</pre>
          </details>
        </td>
      </tr>`;
    }

    const breakdown = d.score_breakdown || {};
    const sum = summarizeBreakdown(breakdown);
    const entries = Object.entries(breakdown)
      .map(([k, v]) => {
        const vv = Number(v) || 0;
        return {
          key: k,
          label: scoreLabel(k),
          value: vv,
          abs: Math.abs(vv).toFixed(2),
          isBonus: vv < 0,
          reason: scoreReason(k, vv, d, cfg),
        };
      })
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

    const bRows = entries.map((e) => {
      const tag = e.isBonus ? "加分" : "扣分";
      const cls = e.isBonus ? "good" : "bad";
      const reasonTxt = e.reason ? `<span class="meta">（${escapeHtml(e.reason)}）</span>` : "";
      return `<div class="bd ${cls}">
        <span>${escapeHtml(e.label)}${reasonTxt}</span>
        <span class="v">${tag} ${e.abs}</span>
      </div>`;
    }).join("");

    const daySummary = `今日小結：加分 ${sum.bonus.toFixed(1)} ／ 扣分 ${sum.penalty.toFixed(1)} ／ 原始 ${sum.raw.toFixed(1)}（目標匹配度 ${sum.fitness.toFixed(1)}）`;

    html += `<tr class="explain">
      <td colspan="10">
        <details>
          <summary>可解釋明細</summary>
          <div class="explain-box">
            <div class="ex-title">${escapeHtml(daySummary)}</div>
            <div class="ex-title">打分拆解（影響大 → 小）</div>
            <div class="bd-list">${bRows || "<div class='muted'>（無）</div>"}</div>
            ${renderProcurementDetail(d)}
            <div class="ex-title">庫存使用（ID）</div>
            <pre class="pre">${escapeHtml(pretty({
              main: d.items?.main?.used_inventory_ingredients,
              soup: d.items?.soup?.used_inventory_ingredients,
              veg: d.items?.veg?.used_inventory_ingredients,
              sides: (d.items?.sides || []).map((x) => x?.used_inventory_ingredients),
            }))}</pre>
          </div>
        </details>
      </td>
    </tr>`;
  });

  html += "</tbody></table>";
  $(DOM.result).html(html);
}
