/* The top bar: its menu on narrow screens, and the light or dark theme. The choice is kept under
   "tauceti:theme", which the review app reads too; the page's <head> applies it before first paint. */
(function () {
  "use strict";
  var KEY = "tauceti:theme";
  var root = document.documentElement;

  function label(btn) {
    var next = root.dataset.theme === "light" ? "dark" : "light";
    btn.setAttribute("aria-label", "Switch to " + next + " mode");
    btn.title = "Switch to " + next + " mode";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var bar = document.querySelector(".site-nav");
    if (!bar) return;
    var menu = bar.querySelector(".nav-toggle"), links = bar.querySelector(".nav-links");
    if (menu && links) menu.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      menu.setAttribute("aria-expanded", open ? "true" : "false");
    });
    var theme = bar.querySelector(".theme-toggle");
    if (!theme) return;
    label(theme);
    theme.addEventListener("click", function () {
      var next = root.dataset.theme === "light" ? "dark" : "light";
      root.dataset.theme = next;
      try { localStorage.setItem(KEY, next); } catch (e) { /* kept for this page only */ }
      label(theme);
      document.dispatchEvent(new CustomEvent("tc-theme", { detail: next }));
    });
  });
})();
