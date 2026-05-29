(function () {
  "use strict";

  function getOrCreateBanner() {
    var banner = document.getElementById("js_error_banner");
    if (banner) return banner;

    banner = document.createElement("div");
    banner.id = "js_error_banner";
    banner.className = "js-error-banner";
    banner.setAttribute("role", "alert");
    banner.setAttribute("aria-live", "assertive");
    document.body.insertBefore(banner, document.body.firstChild);
    return banner;
  }

  function fileNameFromUrl(url) {
    if (!url) return "unknown";
    try {
      var parsed = new URL(url, window.location.href);
      return parsed.pathname.split("/").pop() || parsed.pathname || url;
    } catch (e) {
      return String(url).split("/").pop() || String(url);
    }
  }

  function showFrontendError(message, filename, lineno, colno) {
    var banner = getOrCreateBanner();
    var location = filename ? "（" + fileNameFromUrl(filename) + (lineno ? ":" + lineno : "") + (colno ? ":" + colno : "") + "）" : "";
    var detail = message || "未知錯誤";

    banner.textContent = "前端程式發生錯誤，部分按鈕可能無法使用。請重新整理頁面；若仍發生，請回報以下訊息：" + detail + location;
    banner.removeAttribute("hidden");
  }

  window.addEventListener("error", function (event) {
    if (event && event.target && event.target !== window && !event.message) {
      showFrontendError("資源載入失敗", event.target.src || event.target.href || "", 0, 0);
      return;
    }
    showFrontendError(event && event.message, event && event.filename, event && event.lineno, event && event.colno);
  }, true);

  window.addEventListener("unhandledrejection", function (event) {
    var reason = event && event.reason;
    var message = reason && reason.message ? reason.message : String(reason || "Promise rejected");
    showFrontendError(message, "", 0, 0);
  });
})();
