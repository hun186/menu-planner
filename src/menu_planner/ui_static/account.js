import {
  approveAuthUser,
  changePasswordAuth,
  deleteAuthUser,
  getAuthMe,
  listAuthUsers,
  loginAuth,
  logoutAuth,
  recoverPasswordAuth,
  forgotPasswordAuth,
  issuePasswordResetToken,
  registerAuth,
  rejectAuthUser,
} from "./admin/api.js";
import { authToken, authUser, clearAuthSession, saveAuthSession } from "./shared/http.js";
import { escapeHtml } from "./shared/html.js";

const ROLE_LABELS = {
  data_reader: "資料閱讀者",
  data_editor: "資料修改者",
  db_operator: "資料庫操作者",
  superuser: "最高級全能者",
};

function roleLabel(role) {
  return ROLE_LABELS[role] || role || "資料閱讀者";
}

function permissionSummary(user = authUser()) {
  if (!user?.username) {
    return "尚未登入：目前只能使用排菜、查詢與匯出等公開功能。";
  }
  if (user.role === "superuser") {
    return `目前登入 ${user.username}（最高級全能者）：可維護資料、建立/還原/刪除備份，並審核帳號。`;
  }
  if (user.role === "db_operator") {
    return `目前登入 ${user.username}（資料庫操作者）：可維護資料庫內容、建立/還原/刪除備份與編輯備份註解；不能審核帳號。`;
  }
  return `目前登入 ${user.username}（${roleLabel(user.role)}）：可維護資料庫內容、建立備份與編輯備份註解；不能審核帳號、還原或刪除備份。`;
}

function renderAuthStatus(user = authUser()) {
  const $status = $("#auth_status");
  if (!$status.length) return;
  if (user?.username) {
    $status.html(`目前登入：<strong>${escapeHtml(user.username)}</strong>（${escapeHtml(roleLabel(user.role))}）`);
  } else {
    $status.text("尚未登入；資料維護需要資料修改者以上權限，帳號審核需要最高級全能者；危險備份操作需要資料庫操作者以上權限。");
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
            ${(payload.role_options || ["superuser", "db_operator", "data_editor", "data_reader"].map((role) => ({ value: role, label: roleLabel(role) }))).map((option) => `<option value="${escapeHtml(option.value)}" ${option.value === u.role ? "selected" : ""}>${escapeHtml(option.label || roleLabel(option.value))}</option>`).join("")}
          </select>
          <button class="auth-approve" data-user="${escapeHtml(u.username || "")}">核准</button>
          <button class="auth-reject" data-user="${escapeHtml(u.username || "")}">拒絕</button>
          <button class="auth-reset-token" data-user="${escapeHtml(u.username || "")}">產生重設 token</button>
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
  $("#auth_logout").on("click", async () => {
    try {
      if (authToken()) await logoutAuth();
    } catch (_) {
      // Local cleanup should still happen if the token was already invalid.
    }
    clearAuthSession();
    renderAuthStatus(null);
    $("#auth_users_tbl tbody").html("");
    $("#msg_auth").text("已登出；伺服器端 token 已失效。").removeClass("err");
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
  $("#auth_change_password").on("click", async () => {
    try {
      const payload = await changePasswordAuth($("#auth_password").val() || "", $("#auth_new_password").val() || "");
      clearAuthSession();
      renderAuthStatus(null);
      $("#msg_auth").text(payload.message || "密碼已變更，請重新登入。").removeClass("err");
    } catch (e) {
      $("#msg_auth").text(`密碼變更失敗：${e?.message || e}`).addClass("err");
    }
  });
  $("#auth_forgot_password").on("click", async () => {
    try {
      const payload = await forgotPasswordAuth(($("#auth_username").val() || "").trim());
      $("#msg_auth").text(payload.message || "已送出忘記密碼申請。").removeClass("err");
    } catch (e) {
      $("#msg_auth").text(`忘記密碼申請失敗：${e?.message || e}`).addClass("err");
    }
  });
  $("#auth_recover_password").on("click", async () => {
    try {
      const payload = await recoverPasswordAuth(($("#auth_username").val() || "").trim(), $("#auth_reset_token").val() || "", $("#auth_new_password").val() || "");
      $("#msg_auth").text(payload.message || "密碼已重設，請重新登入。").removeClass("err");
    } catch (e) {
      $("#msg_auth").text(`密碼重設失敗：${e?.message || e}`).addClass("err");
    }
  });
  $("#auth_users_reload").on("click", refreshAuthUsers);
  $("#auth_users_tbl").on("click", ".auth-approve", async function () {
    const username = $(this).data("user");
    const role = $(this).siblings(".auth-role").val() || "data_reader";
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
  $("#auth_users_tbl").on("click", ".auth-reset-token", async function () {
    const payload = await issuePasswordResetToken($(this).data("user"));
    $("#msg_auth").text(`${payload.username} 的一次性重設 token：${payload.reset_token}`).removeClass("err");
  });
}

$(bindAuthUI);
