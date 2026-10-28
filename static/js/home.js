document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  var TC = window.TC;

  TC.live("roadmap-completion.json").then(function (rc) {
    var f = rc.forecast;
    TC.set("loc", TC.fmt(f.library_lines), "as of " + TC.dayYear(f.last_full_day));
    TC.set("growth", TC.fmt(f.library_growth_lines_per_day));
    var h = rc.history[rc.history.length - 1];
    TC.set("roadmaps", TC.fmt(h.roadmaps), h.completed_roadmaps + " archived as complete");
  }).catch(function (e) { TC.set("loc", "—"); TC.set("growth", "—"); console.error(e); });

  TC.live("progress.json").then(function (p) {
    TC.set("merged", TC.fmt(p.global.total), TC.fmt(p.global.open) + " open now");
  }).catch(function (e) { TC.set("merged", "—"); console.error(e); });

  TC.live("pr-stats.json").then(function (s) {
    TC.set("contributors", TC.fmt(Object.keys(s.merge_totals_by_contributor).length));
  }).catch(function (e) { TC.set("contributors", "—"); console.error(e); });

  fetch("https://raw.githubusercontent.com/TauCetiProject/TauCeti/main/lean-toolchain")
    .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
    .then(function (t) { TC.$$("[data-toolchain]").forEach(function (e) { e.textContent = t.trim(); }); })
    .catch(function () { TC.$$("[data-toolchain]").forEach(function (e) { e.textContent = "see the file"; }); });

  TC.local("examples.json").then(function (ex) {
    var box = TC.$("#examples");
    box.replaceChildren();
    if (ex.imports && ex.imports.length) TC.$("[data-imports]").textContent = ex.imports.map(function (i) { return "import " + i; }).join("\n");
    ex.examples.forEach(function (e) {
      var title = (e.summary.split(" — ")[0] || e.id).trim();
      var rest = e.summary.indexOf(" — ") >= 0 ? e.summary.slice(e.summary.indexOf(" — ") + 3) : "";
      var pre = TC.el("pre", { class: "lean" });
      var code = TC.el("code");
      code.innerHTML = TC.highlightLean(e.code);  // highlightLean escapes its input
      pre.append(code);
      box.append(TC.el("div", { class: "panel example" }, [
        TC.el("h3", { text: title }),
        rest ? TC.el("p", { text: rest.charAt(0).toUpperCase() + rest.slice(1) }) : null,
        TC.copyable(pre),
      ]));
    });
  }).catch(function (e) { TC.fail("#examples", e); });
});
