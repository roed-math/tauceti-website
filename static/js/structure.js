document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  var TC = window.TC;
  var data;

  function count(r, s) { return r.states.filter(function (x) { return x === s; }).length; }

  function segments(r) {
    var segs = TC.el("div", { class: "segs", "aria-hidden": "true" });
    if (r.completed && !r.states.length) {
      segs.append(TC.el("div", { class: "seg complete", title: "archived as complete" }));
      return segs;
    }
    r.states.forEach(function (s, i) {
      segs.append(TC.el("div", { class: "seg " + (r.completed ? "complete" : s), title: (r.layer_ids[i] || "") + ": " + (r.completed ? "archived as complete" : s) }));
    });
    return segs;
  }

  // Report prose carries Markdown code spans; render those as <code> and keep the rest as text.
  function richText(str) {
    var p = TC.el("span");
    String(str || "").split(/(`[^`]+`)/).forEach(function (part) {
      if (/^`[^`]+`$/.test(part)) p.append(TC.el("code", { text: part.slice(1, -1) }));
      else p.append(document.createTextNode(part.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")));
    });
    return p;
  }

  function row(r, child) {
    var done = count(r, "done"), n = r.states.length;
    var name = TC.el("div", { class: "rm-name" }, [document.createTextNode(r.name)]);
    if (r.completed) name.append(TC.el("span", { class: "badge", text: "complete" }));
    name.append(TC.el("small", { text: r.title || "" }));
    var meta = TC.el("div", { class: "rm-meta" }, [
      document.createTextNode(n ? done + "/" + n + " layers" : r.completed ? "archived" : "no layers"),
      TC.el("br"),
      // Sub-roadmaps carry their umbrella's label, so their merges are counted on the umbrella.
      document.createTextNode(r.activity ? TC.fmt(r.activity.total || 0) + " PRs" : r.parent ? "PRs under " + r.parent : ""),
    ]);
    var body = TC.el("div", { class: "rm-body" });
    var st = r.status || {};
    if (st.glance) body.append(TC.el("p", null, [richText(st.glance)]));
    if (st.frontier && st.frontier.length) {
      body.append(TC.el("p", { class: "small muted", text: "Next milestones" }));
      body.append(TC.el("ul", null, st.frontier.slice(0, 4).map(function (f) {
        return TC.el("li", null, [TC.el("b", { text: f.name + " " }), richText((f.text || "").replace(/^—\s*/, "— "))]);
      })));
    }
    if (n) {
      var rem = (r.assessment || {}).remaining || {};
      body.append(TC.el("ul", { class: "layers" }, r.layers.map(function (l, i) {
        var s = r.completed ? "done" : r.states[i];
        var li = TC.el("li", null, [TC.el("span", { class: "state " + s, text: s }), document.createTextNode(l)]);
        var note = rem[r.layer_ids[i]];
        if (note && s !== "done") li.append(TC.el("div", { class: "small muted", style: "margin-left:4.6rem" }, [document.createTextNode("Remaining: "), richText(note)]));
        return li;
      })));
    }
    var dir = r.readme.replace(/\/README\.md$/, "");
    var links = TC.el("p", { class: "small" }, [
      TC.el("a", { href: TC.ROADMAP_BLOB + r.readme, text: "README" }), document.createTextNode(" · "),
      TC.el("a", { href: TC.ROADMAP_BLOB + dir + "/STATUS.md", text: "latest report" }), document.createTextNode(" · "),
      TC.el("a", { href: "https://github.com/TauCetiProject/TauCeti/pulls?q=" + encodeURIComponent("label:roadmap/" + (r.parent || r.name)), text: "pull requests" }),
    ]);
    if (st.ts) links.append(TC.el("span", { class: "muted", text: " · report " + TC.ago(st.ts) }));
    (r.links || []).forEach(function (l) {
      if (l && l.url) { links.append(document.createTextNode(" · ")); links.append(TC.el("a", { href: l.url, text: l.label || "more" })); }
    });
    body.append(links);
    var d = TC.el("details", { class: "rm" + (child ? " child" : ""), id: "rm-" + r.name }, [
      TC.el("summary", null, [name, segments(r), meta]), body,
    ]);
    d.dataset.search = [r.name, r.title, r.topic, r.arxiv, r.parent || ""].join(" ").toLowerCase();
    return d;
  }

  function render() {
    var q = TC.$("#q").value.trim().toLowerCase();
    var hideDone = TC.$("#hide-done").checked;
    var sort = TC.$("#sort").value;
    var rows = data.rows.filter(function (r) { return !r.retired && !(hideDone && r.completed); });
    var children = {};
    rows.forEach(function (r) { if (r.parent_id) (children[r.parent_id] = children[r.parent_id] || []).push(r); });
    var key = {
      layers: function (r) { return -(count(r, "done") + (r.completed ? 1000 : 0)); },
      activity: function (r) { return -((r.activity || {}).total || 0); },
      name: function () { return 0; },
    }[sort];
    function cmp(a, b) { return key(a) - key(b) || a.name.localeCompare(b.name); }
    var groups = {};
    rows.forEach(function (r) { if (!r.parent_id) (groups[r.topic] = groups[r.topic] || []).push(r); });
    var board = TC.$("#board");
    board.replaceChildren();
    var shown = 0;
    data.topics.forEach(function (topic) {
      var list = (groups[topic] || []).sort(cmp);
      var els = [];
      list.forEach(function (r) {
        var kids = (children[r.id] || []).sort(cmp);
        var kidEls = kids.map(function (k) { return row(k, true); });
        var parentEl = row(r, false);
        var match = function (e) { return !q || e.dataset.search.indexOf(q) >= 0; };
        var anyKid = kidEls.some(match);
        if (match(parentEl) || anyKid) {
          els.push(parentEl);
          kidEls.forEach(function (k) { if (match(parentEl) || match(k)) els.push(k); });
        }
      });
      if (!els.length) return;
      shown += els.length;
      var arxiv = list[0].arxiv;
      var layers = 0, done = 0;
      list.concat.apply(list, list.map(function (r) { return children[r.id] || []; })).forEach(function (r) { layers += r.states.length; done += count(r, "done"); });
      board.append(TC.el("section", { class: "topic-group", id: "topic-" + arxiv }, [
        TC.el("h3", null, [document.createTextNode(topic), TC.el("span", { class: "muted", text: arxiv + " · " + list.length + " roadmaps · " + done + "/" + layers + " layers done" })]),
      ].concat(els)));
    });
    if (!shown) board.append(TC.el("p", { class: "muted", text: "No roadmap matches that filter." }));
  }

  TC.live("progress.json").then(function (p) {
    data = p;
    TC.$("#board-meta").textContent = "Roadmaps as of TauCetiRoadmap " + p.roadmap_head.slice(0, 7) + "; activity through " + TC.dayYear(p.cutoff) + ".";
    render();
    ["#q", "#sort", "#hide-done"].forEach(function (s) { TC.$(s).addEventListener("input", render); });
    function goToHash() {
      var t = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (!t) return;
      if (t.tagName === "DETAILS") t.open = true;
      var go = function () { t.scrollIntoView({ block: "start" }); };
      requestAnimationFrame(go);
      if (document.fonts) document.fonts.ready.then(go);  // the display face shifts layout when it arrives
    }
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    goToHash();
    window.addEventListener("hashchange", goToHash);
  }).catch(function (e) { TC.fail("#board", e); });
});
