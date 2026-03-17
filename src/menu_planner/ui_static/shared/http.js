function detailToMessage(detail, fallback) {
  if (typeof detail === "string" && detail) return detail;
  if (detail?.message) return detail.message;
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return fallback;
}

export function adminKey() {
  try {
    return localStorage.getItem("menu_admin_key") || "";
  } catch {
    return "";
  }
}

export async function httpJson(url, options = {}, { includeAdminKey = false } = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (includeAdminKey) {
    const key = adminKey();
    if (key) headers["X-Admin-Key"] = key;
  }

  const res = await fetch(url, { ...options, headers });
  const payload = await res.json().catch(() => ({}));

  if (!res.ok) {
    const msg = detailToMessage(payload?.detail, `HTTP ${res.status}`);
    throw new Error(msg);
  }

  return payload;
}

export async function httpArray(url, options = {}, extra = {}) {
  const payload = await httpJson(url, options, extra);
  return Array.isArray(payload) ? payload : [];
}
