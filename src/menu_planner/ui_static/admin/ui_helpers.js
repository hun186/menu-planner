export function setMsg(syncEditorPaneHeights, $el, text, isError) {
  $el.css("color", isError ? "#b42318" : "#1a7f37").text(text || "");
  requestAnimationFrame(syncEditorPaneHeights);
}

export function clearMsg(setMsgFn, selector) {
  setMsgFn($(selector), "", false);
}

export function clearFields(selector) {
  $(selector).val("");
}

export function scrollToEditor(editorSelector, focusSelector) {
  const el = document.querySelector(editorSelector);
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  if (focusSelector) {
    $(focusSelector).trigger("focus");
  }
}

export async function runWithMsg(setMsgFn, msgSelector, fn, successText) {
  try {
    const result = await fn();
    if (result === false) return;
    if (successText) {
      setMsgFn($(msgSelector), successText, false);
    }
  } catch (e) {
    setMsgFn($(msgSelector), e.message || String(e), true);
  }
}

export function syncEditorPaneHeights() {
  const panes = Array.from(document.querySelectorAll(".manage-card .editor-pane"));
  if (!panes.length) return;

  panes.forEach((pane) => {
    pane.style.minHeight = "0px";
  });

  const maxBottom = panes.reduce((mx, pane) => Math.max(mx, pane.offsetTop + pane.offsetHeight), 0);
  panes.forEach((pane) => {
    const targetHeight = Math.max(0, maxBottom - pane.offsetTop);
    pane.style.minHeight = `${targetHeight}px`;
  });
}

export function debounce(fn, wait = 300) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

export async function downloadExcelFromResponse(res) {
  const blob = await res.blob();
  const contentDisposition = res.headers.get("Content-Disposition") || "";
  const match = contentDisposition.match(/filename=\"([^\"]+)\"/i);
  const filename = match?.[1] || "export.xlsx";
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
