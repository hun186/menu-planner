function readAuthUser() {
  try {
    return JSON.parse(localStorage.getItem("menu_auth_user") || "null");
  } catch (_e) {
    return null;
  }
}

function roleLabel(role) {
  if (role === "superuser") return "最高級全能者";
  if (role === "db_operator") return "資料庫操作者";
  if (role === "data_editor") return "資料修改者";
  if (role === "data_reader") return "資料閱讀者";
  return role || "未登入";
}

function renderNavAuthStatus(nav) {
  let status = nav.querySelector(".nav-auth-status");
  if (!status) {
    status = document.createElement("a");
    status.className = "nav-auth-status";
    status.href = "/account.html";
    status.setAttribute("aria-label", "目前登入帳號與權限等級");
    nav.querySelector(".top-nav-inner")?.appendChild(status);
  }
  const user = readAuthUser();
  if (user?.username) {
    status.textContent = `${user.username}｜${roleLabel(user.role)}`;
    status.title = `目前登入：${user.username}；帳號等級：${roleLabel(user.role)}`;
  } else {
    status.textContent = "未登入｜訪客";
    status.title = "未登入訪客：可使用排菜、查詢與匯出；資料維護需登入。";
  }
}

document.querySelectorAll('.top-nav').forEach((nav) => {
  const toggle = nav.querySelector('.nav-toggle');
  const links = nav.querySelector('.nav-links');
  renderNavAuthStatus(nav);
  window.addEventListener("storage", (event) => {
    if (event.key === "menu_auth_user") renderNavAuthStatus(nav);
  });
  window.addEventListener("menu-auth-changed", () => renderNavAuthStatus(nav));

  if (!toggle || !links) return;

  const closeMenu = () => {
    links.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
  };

  toggle.addEventListener('click', () => {
    const isOpen = links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  });

  links.querySelectorAll('a').forEach((a) => a.addEventListener('click', closeMenu));
  window.addEventListener('resize', () => {
    if (window.innerWidth > 768) closeMenu();
  });
});
