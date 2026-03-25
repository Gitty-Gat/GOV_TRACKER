document.addEventListener("DOMContentLoaded", () => {
  document.body.classList.add("ready");
  const shell = document.querySelector(".page-shell");
  const toggle = document.querySelector("[data-sidebar-toggle]");
  const storageKey = "civic-ledger.sidebar-collapsed";

  const applySidebarState = (collapsed) => {
    if (!shell || !toggle) {
      return;
    }
    shell.classList.toggle("sidebar-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.querySelector("span").textContent = collapsed ? "Show" : "Hide";
  };

  if (shell && toggle) {
    const savedState = window.localStorage.getItem(storageKey) === "true";
    const startsCollapsed = window.innerWidth <= 1100 ? true : savedState;
    applySidebarState(startsCollapsed);
    toggle.addEventListener("click", () => {
      const collapsed = !shell.classList.contains("sidebar-collapsed");
      applySidebarState(collapsed);
      window.localStorage.setItem(storageKey, String(collapsed));
    });
  }

  document.querySelectorAll("img[data-fallback-src]").forEach((image) => {
    image.addEventListener(
      "error",
      () => {
        const fallback = image.dataset.fallbackSrc;
        if (fallback && image.src !== fallback) {
          image.src = fallback;
          return;
        }
        const wrapper = image.parentElement;
        if (wrapper) {
          const name = image.getAttribute("alt") || "?";
          const fallbackEl = document.createElement("div");
          fallbackEl.className = image.classList.contains("profile-photo") ? "profile-photo fallback" : "avatar-fallback";
          fallbackEl.textContent = name.slice(0, 1);
          wrapper.replaceChild(fallbackEl, image);
        }
      },
      { once: true },
    );
  });
});
