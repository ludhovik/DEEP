// The title owns viewer feedback. A notice survives unrelated progress updates
// until dismissed, or cleared by a successful retry of the same operation.
export function createViewerStatus({ status, panel, warningButton, notice, noticeText,
  dismissButton, onReveal = () => {} }) {
  let active = null;
  let version = 0;
  const render = () => {
    notice.hidden = warningButton.hidden = !active;
    panel.classList.toggle("has-warning", Boolean(active));
    notice.dataset.level = active?.level || "info";
    noticeText.textContent = active?.text || "";
    warningButton.title = active ? `${active.text} — click to expand the title` : "";
    warningButton.setAttribute("aria-label", active ? `Show warning: ${active.text}` : "Show warning");
  };
  const clear = (scope = null, expectedVersion = version) => {
    if (!active || expectedVersion !== version || (scope !== null && active.scope !== scope)) return;
    active = null;
    render();
  };
  warningButton.addEventListener("click", () => {
    if (!active) return;
    onReveal();
    notice.scrollIntoView?.({ block: "nearest" });
    notice.focus?.({ preventScroll: true });
  });
  dismissButton.addEventListener("click", () => clear());
  render();
  return {
    get version() { return version; },
    set(text, { level = "info", scope = null } = {}) {
      if (level === "error" || level === "warning") {
        active = { text: String(text), level, scope };
        version++;
        render();
      } else {
        status.textContent = String(text);
      }
    },
    clear,
  };
}
