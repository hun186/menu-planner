import { listInventorySummary } from "./admin/api.js";
import { escapeHtml } from "./shared/html.js";

function setMsg(text, isError = false) {
  $("#inv_msg").text(text || "").toggleClass("err", !!isError);
}

function readQueryFromLocation() {
  const params = new URLSearchParams(window.location.search || "");
  const q = (params.get("q") || "").trim();
  const onlyInStock = ["1", "true", "yes"].includes((params.get("only_in_stock") || "").toLowerCase());
  return { q, onlyInStock };
}

function applyQueryToControls({ q, onlyInStock }) {
  $("#inv_q").val(q || "");
  $("#inv_only_stock").prop("checked", !!onlyInStock);
}

function pushQueryToUrl({ q, onlyInStock }) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (onlyInStock) params.set("only_in_stock", "true");
  const query = params.toString();
  const next = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState({}, "", next);
}

function renderRows(list) {
  const $tb = $("#inv_tbl tbody").empty();
  if (!Array.isArray(list) || !list.length) {
    $tb.append("<tr><td colspan=\"9\" class=\"muted\">查無資料。</td></tr>");
    return;
  }

  list.forEach((row) => {
    const qtyText = row.qty_on_hand === null || row.qty_on_hand === undefined ? "—" : Number(row.qty_on_hand).toFixed(2);
    const expiryText = row.expiry_date || "—";
    const updatedText = row.updated_at || "—";
    const $tr = $(`
      <tr>
        <td>${escapeHtml(row.ingredient_id || "")}</td>
        <td>${escapeHtml(row.ingredient_name || "")}</td>
        <td>${escapeHtml(row.category || "")}</td>
        <td>${escapeHtml(qtyText)}</td>
        <td>${escapeHtml(row.inventory_unit || row.default_unit || "—")}</td>
        <td>${escapeHtml(updatedText)}</td>
        <td>${escapeHtml(expiryText)}</td>
        <td>${escapeHtml(String(row.dish_ref_count ?? 0))}</td>
        <td><a class="btn-link" href="/admin?q=${encodeURIComponent(row.ingredient_id || "")}">去食材管理</a></td>
      </tr>
    `);
    $tb.append($tr);
  });
}

async function loadAndRender() {
  const q = ($("#inv_q").val() || "").trim();
  const onlyInStock = $("#inv_only_stock").is(":checked");
  pushQueryToUrl({ q, onlyInStock });
  setMsg("載入中…");
  try {
    const list = await listInventorySummary({ q, onlyInStock });
    renderRows(list);
    setMsg(`完成，共 ${Array.isArray(list) ? list.length : 0} 筆。`);
  } catch (e) {
    renderRows([]);
    setMsg(`載入失敗：${e.message || String(e)}`, true);
  }
}

$(function () {
  const preset = readQueryFromLocation();
  applyQueryToControls(preset);

  const debounced = (() => {
    let timer = null;
    return () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        loadAndRender();
      }, 250);
    };
  })();

  $("#inv_refresh").on("click", loadAndRender);
  $("#inv_only_stock").on("change", loadAndRender);
  $("#inv_q").on("input", debounced);
  loadAndRender();
});
