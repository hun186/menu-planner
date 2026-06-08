import {
  approveAuthUser,
  deleteAuthUser,
  getAuthMe,
  listAuthUsers,
  loginAuth,
  registerAuth,
  rejectAuthUser,
} from "./admin/api.js";
import { authToken, authUser, clearAuthSession, saveAuthSession } from "./shared/http.js";
import { escapeHtml } from "./shared/html.js";

const ROLE_LABELS = {
  user: "普通帳號",
  manager: "資料管理帳號",
  backup_manager: "備份管理員",
  superuser: "超級管理者",
};

function roleLabel(role) {
  return ROLE_LABELS[role] || role || "普通帳號";
}

function permissionSummary(user = authUser()) {
  if (!user?.username) {
    return "尚未登入：目前只能使用排菜、查詢與匯出等公開功能。";
  }
  if (user.role === "superuser") {
    return `目前登入 ${user.username}（超級管理者）：可維護資料、建立/還原/刪除備份，並審核帳號。`;
  }
  if (user.role === "backup_manager") {
    return `目前登入 ${user.username}（備份管理員）：可維護資料庫內容、建立/還原/刪除備份與編輯備份註解；不能審核帳號。`;
  }
  return `目前登入 ${user.username}（${roleLabel(user.role)}）：可維護資料庫內容、建立備份與編輯備份註解；不能審核帳號、還原或刪除備份。`;
}

function renderAuthStatus(user = authUser()) {
  const $status = $("#auth_status");
  if (!$status.length) return;
  if (user?.username) {
    $status.html(`目前登入：<strong>${escapeHtml(user.username)}</strong>（${escapeHtml(roleLabel(user.role))}）`);
  } else {
    $status.text("尚未登入；資料維護需要已啟用帳號，帳號審核需要超級管理者；危險備份操作需要備份管理員或超級管理者。");
  }
  $("#permission_summary").text(permissionSummary(user));
  window.dispatchEvent(new Event("menu-auth-changed"));
}

async function refreshAuthUsers() {
  const $body = $("#auth_users_tbl tbody");
  if (!$body.length) return;
  try {
    const payload = await listAuthUsers();
    const users = Array.isArray(payload?.users) ? payload.users : [];
    $body.html(users.map((u) => `
      <tr>
        <td>${escapeHtml(u.username || "")}</td>
        <td>${escapeHtml(u.full_name || "")}</td>
        <td>${escapeHtml(roleLabel(u.role))}</td>
        <td>${escapeHtml(u.status || "")}</td>
        <td>${escapeHtml(u.department || "")}</td>
        <td>
          <select class="auth-role" data-user="${escapeHtml(u.username || "")}">
            ${["user", "manager", "backup_manager", "superuser"].map((role) => `<option value="${role}" ${role === u.role ? "selected" : ""}>${roleLabel(role)}</option>`).join("")}
          </select>
          <button class="auth-approve" data-user="${escapeHtml(u.username || "")}">核准</button>
          <button class="auth-reject" data-user="${escapeHtml(u.username || "")}">拒絕</button>
          <button class="auth-delete" data-user="${escapeHtml(u.username || "")}">刪除</button>
        </td>
      </tr>
    `).join(""));
    $("#msg_auth").text(`已載入 ${users.length} 個帳號。`).removeClass("err");
  } catch (e) {
    $body.html("");
    $("#msg_auth").text(`帳號清單載入失敗：${e?.message || e}`).addClass("err");
  }
}

function bindAuthUI() {
  renderAuthStatus();
  $("#auth_login").on("click", async () => {
    try {
      const username = ($("#auth_username").val() || "").trim();
      const password = $("#auth_password").val() || "";
      const payload = await loginAuth(username, password);
      saveAuthSession(payload.access_token, payload.user);
      renderAuthStatus(payload.user);
      $("#msg_auth").text("登入成功。後續資料維護操作會自動附加 Bearer Token。").removeClass("err");
      await refreshAuthUsers();
    } catch (e) {
      $("#msg_auth").text(`登入失敗：${e?.message || e}`).addClass("err");
    }
  });
  $("#auth_register").on("click", async () => {
    try {
      const payload = await registerAuth({
        username: ($("#auth_username").val() || "").trim(),
        password: $("#auth_password").val() || "",
        fullName: ($("#auth_full_name").val() || "").trim(),
        department: ($("#auth_department").val() || "").trim(),
        note: ($("#auth_note").val() || "").trim(),
      });
      $("#msg_auth").text(payload.message || "帳號已建立。").removeClass("err");
    } catch (e) {
      $("#msg_auth").text(`註冊失敗：${e?.message || e}`).addClass("err");
    }
  });
  $("#auth_logout").on("click", () => {
    clearAuthSession();
    renderAuthStatus(null);
    $("#auth_users_tbl tbody").html("");
    $("#msg_auth").text("已登出。").removeClass("err");
  });
  $("#auth_refresh_me").on("click", async () => {
    try {
      const payload = await getAuthMe();
      saveAuthSession(authToken(), payload.user);
      renderAuthStatus(payload.user);
      $("#msg_auth").text("登入狀態有效。").removeClass("err");
    } catch (e) {
      $("#msg_auth").text(`登入狀態檢查失敗：${e?.message || e}`).addClass("err");
    }
  });
  $("#auth_users_reload").on("click", refreshAuthUsers);
  $("#auth_users_tbl").on("click", ".auth-approve", async function () {
    const username = $(this).data("user");
    const role = $(this).siblings(".auth-role").val() || "user";
    await approveAuthUser(username, role);
    await refreshAuthUsers();
  });
  $("#auth_users_tbl").on("click", ".auth-reject", async function () {
    await rejectAuthUser($(this).data("user"));
    await refreshAuthUsers();
  });
  $("#auth_users_tbl").on("click", ".auth-delete", async function () {
    const username = $(this).data("user");
    if (!confirm(`確定刪除帳號 ${username}？`)) return;
    await deleteAuthUser(username);
    await refreshAuthUsers();
  });
}

$(bindAuthUI);
