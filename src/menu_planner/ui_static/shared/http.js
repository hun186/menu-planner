function detailToMessage(detail, fallback) {
  if (typeof detail === "string" && detail) return detail;
  if (detail?.message) return detail.message;
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return fallback;
}

export function authToken() {
  try {
    return localStorage.getItem("menu_auth_token") || "";
  } catch {
    return "";
  }
}

export function authUser() {
  try {
    return JSON.parse(localStorage.getItem("menu_auth_user") || "null");
  } catch {
    return null;
  }
}

export function saveAuthSession(token, user) {
  localStorage.setItem("menu_auth_token", token || "");
  localStorage.setItem("menu_auth_user", JSON.stringify(user || null));
}

export function clearAuthSession() {
  localStorage.removeItem("menu_auth_token");
  localStorage.removeItem("menu_auth_user");
}

export async function httpJson(url, options = {}, { includeAuth = false } = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (includeAuth) {
    const token = authToken();
    if (token) headers.Authorization = `Bearer ${token}`;
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
