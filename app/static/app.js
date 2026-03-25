document.addEventListener("DOMContentLoaded", () => {
  document.body.classList.add("ready");
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
