import { filterBackups, formatBytes } from "./utils.js";

export function createBackupManager({
  dom,
  escapeHtml,
  backupReasonLabels,
  listDbBackups,
  getDbBackupStats,
  deleteDbBackupsByDateRange,
  createDbBackup,
  setStatusMsg,
}) {
  let backupFiles = [];
  let backupStats = {
    count: 0,
    total_size_bytes: 0,
    warning_threshold_bytes: 500 * 1024 * 1024,
    is_over_warning_threshold: false,
  };

  function getFilteredBackups() {
    const date = ($("#db_backup_filter_date").val() || "").trim();
    const keyword = ($("#db_backup_filter_keyword").val() || "").trim();
    return filterBackups(backupFiles, { date, keyword });
  }

  function resolveSelectedBackup(preferred = "") {
    const fromPreferred = String(preferred || "").trim();
    if (fromPreferred) return fromPreferred;

    const selectedMain = ($("#db_backup_select").val() || "").trim();
    const selectedModal = ($("#db_backup_select_modal").val() || "").trim();
    const activeId = document?.activeElement?.id || "";
    if (activeId === "db_backup_select_modal") return selectedModal || selectedMain;
    if (activeId === "db_backup_select") return selectedMain || selectedModal;
    return selectedModal || selectedMain;
  }

  function renderBackupOptions() {
    const selected = resolveSelectedBackup();
    const $allSelects = $("#db_backup_select, #db_backup_select_modal").empty();
    const filteredBackups = getFilteredBackups();
    if (!filteredBackups.length) {
      $allSelects.append("<option value=\"\">（目前無可用備份檔）</option>");
      $("#backup_filter_info").text("目前篩選條件下無備份資料。");
      return;
    }

    filteredBackups.forEach((x) => {
      const modified = x?.modified_at || "";
      const size = Number(x?.size_bytes || 0);
      const label = `${x?.filename || ""}｜${modified}｜${formatBytes(size)}`;
      $allSelects.append(`<option value="${escapeHtml(x?.filename || "")}">${escapeHtml(label)}</option>`);
    });

    $("#backup_filter_info").text(`篩選結果：${filteredBackups.length} / ${backupFiles.length} 筆`);
    const hasSelected = filteredBackups.some((x) => (x?.filename || "") === selected);
    if (selected && hasSelected) {
      $("#db_backup_select, #db_backup_select_modal").val(selected);
    } else if (filteredBackups[0]?.filename) {
      $("#db_backup_select, #db_backup_select_modal").val(filteredBackups[0].filename);
    }
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

  function syncSelectedBackupMeta(preferred = "") {
    const selected = resolveSelectedBackup(preferred);
    $("#db_backup_select, #db_backup_select_modal").val(selected);
    const item = backupFiles.find((x) => (x?.filename || "") === selected) || null;
    const reasonCode = String(item?.action_reason || "").trim();
    let reason = reasonCode || "—";

    if (reasonCode.startsWith("ingredient_merge:")) {
      const payload = reasonCode.replace("ingredient_merge:", "");
      reason = `食材合併（${payload || "未提供 ID"}）`;
    } else if (backupReasonLabels.has(reasonCode)) {
      reason = `${backupReasonLabels.get(reasonCode)}（${reasonCode}）`;
    }

    const comment = item?.comment || "";
    $("#backup_reason_text").text(reason);
    $("#db_backup_comment").val(comment);
    const modifiedAt = item?.modified_at || "—";
    const fileSize = formatBytes(item?.size_bytes || 0);
    const basic = item
      ? `最近資訊：時間 ${modifiedAt}｜大小 ${fileSize}｜原因 ${reason}`
      : "最近資訊：尚未選取備份檔。";
    $("#backup_basic_info").text(basic);
  }

  async function refreshBackupList() {
    const [files, stats] = await Promise.all([listDbBackups(), getDbBackupStats()]);
    backupFiles = Array.isArray(files) ? files : [];
    backupStats = stats || backupStats;
    renderBackupOptions();
    renderBackupUsage();
    syncSelectedBackupMeta();
  }

  function bindBackupFilterEvents() {
    $("#db_backup_filter_date, #db_backup_filter_keyword").on("input change", () => {
      renderBackupOptions();
      syncSelectedBackupMeta();
    });

    $("#db_backup_filter_clear").on("click", () => {
      $("#db_backup_filter_date").val("");
      $("#db_backup_filter_keyword").val("");
      renderBackupOptions();
      syncSelectedBackupMeta();
    });
  }

  async function runBatchDeleteBackups({ date = "", dateFrom = "", dateTo = "", confirmText = "" } = {}) {
    if (!confirm(confirmText || "確定執行批次刪除備份？\n此操作無法復原。")) return false;
    const result = await deleteDbBackupsByDateRange({ date, dateFrom, dateTo });
    await refreshBackupList();
    const count = Number(result?.deleted_count || 0);
    setStatusMsg($(dom.msgBackupModal), `批次刪除完成，共刪除 ${count} 筆備份。`, false);
    return true;
  }

  async function createBackupByPrompt() {
    const reasonInput = window.prompt("請輸入備份原因代碼（可留空使用 admin_manual_snapshot）：", "admin_manual_snapshot");
    if (reasonInput === null) return false;
    const commentInput = window.prompt("可選：輸入備份註解", "") ?? "";
    const reason = String(reasonInput || "").trim() || "admin_manual_snapshot";
    const comment = String(commentInput || "").trim();
    await createDbBackup({ reason, comment });
    await refreshBackupList();
    return true;
  }

  function getBackupCount() {
    return backupFiles.length;
  }

  return {
    bindBackupFilterEvents,
    createBackupByPrompt,
    getBackupCount,
    refreshBackupList,
    resolveSelectedBackup,
    runBatchDeleteBackups,
    syncSelectedBackupMeta,
  };
}
