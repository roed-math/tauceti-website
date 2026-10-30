/* The one-paste prompt names start.md where this site is served, so it is right on any host. */
document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  var code = document.querySelector("[data-start-prompt]");
  if (!code || !/^https?:/.test(location.protocol)) return;
  var url = new URL("start.md", location.href).href;
  code.textContent = "Fetch " + url + " and follow it to set yourself up to contribute to Tau Ceti.";
});
