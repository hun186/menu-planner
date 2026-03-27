export function shouldRenameEntity(sourceId, targetId) {
  const source = String(sourceId || "").trim();
  const target = String(targetId || "").trim();
  return Boolean(source) && source !== target;
}

export function filterBackups(files, { date = "", keyword = "" } = {}) {
  const normalizedDate = String(date || "").trim();
  const normalizedKeyword = String(keyword || "").trim().toLowerCase();
  const list = Array.isArray(files) ? files : [];
  return list.filter((item) => {
    const modifiedAt = String(item?.modified_at || "");
    const comment = String(item?.comment || "");
    const reason = String(item?.action_reason || "");
    const filename = String(item?.filename || "");
    if (normalizedDate && !modifiedAt.startsWith(normalizedDate)) {
      return false;
    }
    if (!normalizedKeyword) return true;
    const haystack = `${filename} ${comment} ${reason} ${modifiedAt}`.toLowerCase();
    return haystack.includes(normalizedKeyword);
  });
}

export function formatBytes(sizeBytes) {
  const size = Number(sizeBytes || 0);
  if (size < 1024) return `${size} bytes`;
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

export function formatCostWarningReason(reason) {
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

export function formatCostWarningItem(w, idx, separator = "：") {
  const ing = w?.ingredient_name || w?.ingredient_id || "未知食材";
  const reason = formatCostWarningReason(w?.reason);
  const unitText = w?.reason === "unit_mismatch" && w?.unit && w?.price_unit
    ? `（${w.unit} → ${w.price_unit}）`
    : "";
  return `${idx + 1}. ${ing}${separator}${reason}${unitText}`;
}

export function buildDishCostWarningTitle(cost) {
  const warnings = Array.isArray(cost?.warnings) ? cost.warnings : [];
  if (!warnings.length) return "";
  const lines = warnings.map((w, idx) => formatCostWarningItem(w, idx));
  return `成本計算異常：\n${lines.join("\n")}`;
}

export function compareNullable(a, b) {
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

export function todayStr() {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}
