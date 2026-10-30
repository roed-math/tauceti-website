/* The "theorems" and "definitions" tiles, on any page that has them (data/library-counts.json,
   written by scripts/library_counts.py from Tau Ceti's source). */
document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  var TC = window.TC;
  if (!TC.$('[data-stat="theorems"], [data-stat="definitions"]')) return;
  TC.local("library-counts.json").then(function (c) {
    var n = c.dates.length - 1, week = Math.max(0, n - 7);
    ["theorems", "definitions"].forEach(function (k) {
      TC.set(k, TC.fmt(c[k][n]), "+" + TC.fmt(c[k][n] - c[k][week]) + " in the last 7 days");
    });
  }).catch(function (e) { TC.set("theorems", "—"); TC.set("definitions", "—"); console.error(e); });
});
