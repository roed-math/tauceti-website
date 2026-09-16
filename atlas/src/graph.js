/* Tau Ceti universe renderer. One continuous scene drawn with level of detail:
   galaxies (areas) → constellations (roadmaps) → stars (layers) → planets
   (definitions, theorems, constructions). Only what the camera can see and
   resolve is in the DOM, so panning and zooming stay quick. Every mark is
   flat: solid fills, thin strokes, no gradients. Requires the bundled D3 v5. */
(function () {
  'use strict';
  let instanceCount = 0;
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const BACKGROUND = '#0b1016', ACCENT = '#dfc186', NO_PROGRESS = '#6f7f8c', CREAM = '#e8e4da', DUST = '#8ea1b6';
  const KIND_FILL = { definition: '#7fb8bd', theorem: '#dba57f', construction: '#8fa8d0' };
  const normalizeText = value => String(value == null ? '' : value).replace(/([a-z])([A-Z])/g, '$1 $2').replace(/_/g, ' ');

  function progressValue(value) {
    return typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null;
  }
  // Colour means recorded progress and nothing else: an object brightens
  // from red, through salmon, to white as its roadmap fills in. An object
  // without recorded status has no colour at all.
  function progressColor(value) {
    const progress = progressValue(value);
    if (progress === null) return null;
    const stops = [[200, 68, 58], [232, 150, 120], [247, 243, 233]];
    const index = progress <= 50 ? 0 : 1, fraction = progress <= 50 ? progress / 50 : (progress - 50) / 50;
    return '#' + stops[index].map((channel, i) => Math.round(channel + (stops[index + 1][i] - channel) * fraction).toString(16).padStart(2, '0')).join('');
  }
  const hasProgress = node => progressValue(node.progress) !== null;
  const accentOf = node => progressColor(node.progress) || NO_PROGRESS;
  function progressDescription(node) {
    if (typeof node.progressLabel === 'string' && node.progressLabel.trim()) return node.progressLabel.trim();
    const value = progressValue(node.progress);
    return value === null ? '' : Math.round(value) + '% of layers complete';
  }

  function wrapText(text, maxChars, maxLines) {
    const words = normalizeText(text).split(/\s+/).filter(Boolean), lines = [];
    let line = '';
    for (let word of words) {
      while (word.length > maxChars) { if (line) { lines.push(line); line = ''; } lines.push(word.slice(0, maxChars - 1) + '–'); word = word.slice(maxChars - 1); }
      if (line && line.length + word.length + 1 > maxChars) { lines.push(line); line = ''; }
      line += (line ? ' ' : '') + word;
    }
    if (line) lines.push(line);
    if (lines.length > maxLines) { lines.length = maxLines; lines[maxLines - 1] = lines[maxLines - 1].replace(/[ .,;:–-]+$/, '') + '…'; }
    return lines.length ? lines : ['Untitled'];
  }

  const CAPTIONS = {
    'Shared foundations': ['Shared foundations'],
    'Classical, analytic and computational number theory': ['Classical & analytic', 'number theory'],
    'Arithmetic geometry and Diophantine methods': ['Arithmetic geometry', '& Diophantine'],
    'Modular, Shimura and Galois theory': ['Modular, Shimura', '& Galois'],
    'General automorphic theory': ['Automorphic theory'],
    'Diamonds and geometric Langlands': ['Diamonds & geometric', 'Langlands'],
    'Cohomology and nonarchimedean geometry': ['Cohomology &', 'nonarchimedean geometry'],
    'K-theory, motives, periods and Habiro': ['K-theory, motives', '& periods'],
    'Iwasawa, Euler systems and BSD': ['Iwasawa, Euler', 'systems & BSD'],
    'Function fields and higher local fields': ['Function & higher', 'local fields'],
    'Analysis, probability and PDE': ['Analysis, probability', '& PDE'],
    'Topology, manifolds and Floer theory': ['Topology &', 'Floer theory'],
    'Algebra, representation theory and Lie groups': ['Algebra &', 'representations'],
    'Differential and complex geometry': ['Differential &', 'complex geometry'],
    'Combinatorics and discrete structures': ['Combinatorics &', 'discrete structures'],
    'Computation, optimization and control': ['Computation &', 'optimization'],
    'Logic and foundations': ['Logic & foundations']
  };
  const SMALL_CAPTIONS = {
    'Shared foundations': 'Foundations', 'Classical, analytic and computational number theory': 'Number theory',
    'Arithmetic geometry and Diophantine methods': 'Arith. geometry', 'Modular, Shimura and Galois theory': 'Modular / Galois',
    'General automorphic theory': 'Automorphic', 'Diamonds and geometric Langlands': 'Geom. Langlands',
    'Cohomology and nonarchimedean geometry': 'Cohomology', 'K-theory, motives, periods and Habiro': 'K-theory / motives',
    'Iwasawa, Euler systems and BSD': 'Iwasawa', 'Function fields and higher local fields': 'Function fields',
    'Analysis, probability and PDE': 'Analysis', 'Topology, manifolds and Floer theory': 'Topology',
    'Algebra, representation theory and Lie groups': 'Algebra', 'Differential and complex geometry': 'Geometry',
    'Combinatorics and discrete structures': 'Combinatorics', 'Computation, optimization and control': 'Computation',
    'Logic and foundations': 'Logic'
  };

  class TauGraph {
    constructor(container, options) {
      if (!window.d3) throw new Error('The local graph library did not load. Keep the vendor folder beside the explorer.');
      if (typeof container === 'string') container = document.querySelector(container);
      if (!container) throw new Error('Graph container is missing.');
      this.container = container; this.options = options || {}; this.id = 'tau-graph-' + (++instanceCount);
      this.universe = null; this.selectedId = null; this.hoveredId = null; this.transform = d3.zoomIdentity; this.destroyed = false;
      this.isCoarse = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
      this.showReferences = false; this.lastFocus = null; this.renderScheduled = false; this.busy = false; this.widthCache = new Map();
      this.svg = d3.select(container).append('svg').attr('class', 'tau-graph').attr('xmlns', SVG_NS)
        .attr('width', '100%').attr('height', '100%').attr('role', 'group')
        .attr('aria-label', 'Interactive mathematics universe. Tab to an object and press Enter to open it.')
        .style('display', 'block').style('width', '100%').style('height', '100%').style('background', BACKGROUND).style('touch-action', 'none');
      this.svg.append('style').text(`
        .tau-graph text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif; pointer-events: none; paint-order: stroke fill; stroke: ${BACKGROUND}; stroke-linejoin: round; }
        .tau-graph .tau-node { cursor: pointer; outline: none; }
        .tau-graph .tau-hit { fill: transparent; pointer-events: all; }
        .tau-graph .tau-galaxy-disc, .tau-graph .tau-dust, .tau-graph .tau-constellation-disc, .tau-graph .tau-figure, .tau-graph .tau-orbit, .tau-graph .tau-field, .tau-graph .tau-link, .tau-graph .tau-route, .tau-graph .tau-ring { pointer-events: none; }
        .tau-graph .tau-label-galaxy text { fill: #b3bec9; font-weight: 500; letter-spacing: .2px; stroke-width: 2.5px; }
        .tau-graph .tau-label-galaxy.is-active text { fill: #e2e6eb; }
        .tau-graph .tau-label-constellation text { fill: #c9d2da; font-weight: 400; stroke-width: 2.5px; }
        .tau-graph .tau-label-star text { fill: #dbe1e7; font-weight: 500; stroke-width: 3px; }
        .tau-graph .tau-label-planet text { fill: #c9d2da; font-weight: 500; stroke-width: 2.5px; }
        .tau-graph .tau-label-card text { fill: #8fa0b0; font-weight: 400; stroke-width: 2.5px; }
        .tau-graph .tau-label-card text tspan:first-child { fill: #dfc186; font-size: 8px; letter-spacing: .3px; text-transform: uppercase; }
        .tau-graph .tau-label-moon text { fill: #9fabb8; font-weight: 400; stroke-width: 2px; }
        .tau-graph .tau-system-link { fill: none; stroke: #7d8a99; }
        .tau-graph .tau-moon { pointer-events: none; }
        .tau-graph .tau-label.is-active text { fill: #f0e4c8; }
        .tau-graph .tau-label-hit { fill: transparent; pointer-events: all; cursor: pointer; }
        .tau-graph .tau-figure { fill: none; stroke: #4f5f6d; }
        .tau-graph .tau-orbit { fill: none; stroke: #3a4652; }
        .tau-graph .tau-link { fill: none; stroke: ${ACCENT}; }
        .tau-graph .tau-link.is-reference { stroke: #8fa0b0; }
        .tau-graph .tau-route { fill: none; stroke: #6f8496; }
      `);
      const defs = this.svg.append('defs');
      defs.append('marker').attr('id', this.id + '-arrow').attr('viewBox', '0 -4 9 8').attr('refX', 8).attr('refY', 0)
        .attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto').attr('markerUnits', 'strokeWidth')
        .append('path').attr('d', 'M0,-3.5L8,0L0,3.5Z').attr('fill', ACCENT);
      defs.append('marker').attr('id', this.id + '-arrow-quiet').attr('viewBox', '0 -4 9 8').attr('refX', 8).attr('refY', 0)
        .attr('markerWidth', 7).attr('markerHeight', 7).attr('orient', 'auto').attr('markerUnits', 'strokeWidth')
        .append('path').attr('d', 'M0,-3.5L8,0L0,3.5Z').attr('fill', '#7d8a99');
      this.viewport = this.svg.append('g').attr('class', 'tau-viewport');
      this.layers = {};
      ['field', 'galaxy', 'route', 'constellation', 'figure', 'link', 'star', 'planet', 'label'].forEach(name => { this.layers[name] = this.viewport.append('g').attr('class', 'tau-layer-' + name); });
      // The universe spans thousands of times in scale, so a wheel or trackpad
      // step must move the camera a long way; a pinch keeps a gentler gain.
      this.zoom = d3.zoom().scaleExtent([.015, 900]).clickDistance(6)
        .wheelDelta(() => -d3.event.deltaY * (d3.event.deltaMode === 1 ? .05 : d3.event.deltaMode ? 1 : .002) * (d3.event.ctrlKey ? 1.6 : 3.2))
        .filter(() => !this.busy && !d3.event.button && (!d3.event.ctrlKey || d3.event.type === 'wheel'))
        .on('zoom', () => { this.transform = d3.event.transform; this.viewport.attr('transform', this.transform); this.scheduleRender(); this.scheduleFocus(); });
      this.svg.call(this.zoom).on('dblclick.zoom', null);
      this.svg.on('click.background', () => { if (d3.event.target === this.svg.node()) this.select(null, true); });
      // A pinch is a camera gesture: while two fingers are down, and briefly
      // after they lift, the click a browser may still synthesise is ignored.
      this.gestureTouches = 0; this.suppressClicksUntil = 0;
      const node = this.svg.node();
      const gestureEnded = event => { if (event.touches && event.touches.length) return; if (this.gestureTouches >= 2) this.suppressClicksUntil = Date.now() + 700; this.gestureTouches = 0; };
      node.addEventListener('touchstart', event => { this.gestureTouches = Math.max(this.gestureTouches, event.touches.length); if (event.touches.length >= 2) this.suppressClicksUntil = Infinity; }, { passive: true, capture: true });
      node.addEventListener('touchend', gestureEnded, { passive: true, capture: true });
      node.addEventListener('touchcancel', gestureEnded, { passive: true, capture: true });
      this.width = 800; this.height = 600;
      this.resize = () => {
        if (this.destroyed) return;
        const box = this.container.getBoundingClientRect();
        const previousWidth = this.width, previousHeight = this.height;
        this.width = Math.max(160, box.width || 800); this.height = Math.max(160, box.height || 600);
        this.svg.attr('viewBox', '0 0 ' + this.width + ' ' + this.height);
        this.zoom.extent([[0, 0], [this.width, this.height]]);
        if (this.awaitingFit && box.width > 0 && box.height > 0) { this.awaitingFit = false; this.fitAll(false); return; }
        const aspectBefore = previousWidth / previousHeight, aspectAfter = this.width / this.height;
        if (this.universe && Math.abs(aspectAfter / aspectBefore - 1) > .25 && this.options.onAspectChange) this.options.onAspectChange();
        else this.scheduleRender();
      };
      this.resize();
      if (window.ResizeObserver) { this.observer = new ResizeObserver(this.resize); this.observer.observe(container); }
      else window.addEventListener('resize', this.resize);
    }

    // ----- data -----------------------------------------------------------
    setUniverse(universe, settings) {
      settings = settings || {};
      this.universe = universe; this.busy = false;
      this.selectedId = universe.byId.has(settings.selectedId) ? settings.selectedId : null;
      this.showReferences = !!settings.showReferences;
      this.layers.field.selectAll('*').remove(); this.layers.galaxy.selectAll('*').remove(); this.layers.route.selectAll('*').remove();
      this.layers.constellation.selectAll('*').remove(); this.layers.figure.selectAll('*').remove(); this.layers.link.selectAll('*').remove();
      this.layers.star.selectAll('*').remove(); this.layers.planet.selectAll('*').remove(); this.layers.label.selectAll('*').remove();
      this.drawField(); this.drawGalaxies();
      if (settings.camera) this.restoreCamera(settings.camera);
      else if (settings.keepCamera && this.transform !== d3.zoomIdentity) this.scheduleRender();
      else { this.awaitingFit = true; this.resize(); }
      this.scheduleRender();
      return this;
    }

    setProgress(values) {
      if (!this.universe) return this;
      const progress = values instanceof Map ? values : new Map(Object.entries(values || {}));
      progress.forEach((value, id) => {
        const node = this.universe.byId.get(id);
        if (!node) return;
        if (value && typeof value === 'object') { node.progress = value.progress; node.progressLabel = value.progressLabel; } else node.progress = value;
      });
      this.layers.constellation.selectAll('*').remove(); this.layers.star.selectAll('*').remove();
      this.paintDust();
      this.scheduleRender();
      return this;
    }

    setReferences(show) { this.showReferences = !!show; this.scheduleRender(); return this; }

    // ----- static scenery ---------------------------------------------------
    drawField() {
      const bounds = this.universe.bounds, field = this.layers.field;
      const stars = Array.from({ length: 64 }, (_, index) => ({
        x: bounds.x + (((index * 619 + 89) % 2017) / 2017) * bounds.w, y: bounds.y + (((index * 383 + 53) % 1877) / 1877) * bounds.h,
        r: index % 23 === 0 ? 1.4 : index % 7 === 0 ? .9 : .5, opacity: index % 11 === 0 ? .4 : index % 3 === 0 ? .22 : .12 }));
      field.selectAll('circle').data(stars).enter().append('circle').attr('class', 'tau-field').attr('cx', d => d.x).attr('cy', d => d.y).attr('r', d => d.r).attr('fill', '#c7d3df').attr('opacity', d => d.opacity);
    }

    dustPath(points, radius) {
      return points.map(p => `M${(p.x + radius).toFixed(1)},${p.y.toFixed(1)}a${radius},${radius} 0 1,0 ${-2 * radius},0a${radius},${radius} 0 1,0 ${2 * radius},0`).join('');
    }

    drawGalaxies() {
      const galaxies = this.layers.galaxy.selectAll('g.tau-galaxy').data(this.universe.galaxies, d => d.id).enter().append('g')
        .attr('class', 'tau-galaxy').attr('data-node-id', d => d.id);
      galaxies.append('ellipse').attr('class', 'tau-galaxy-disc').attr('cx', d => d.x).attr('cy', d => d.y).attr('rx', d => d.rx).attr('ry', d => d.ry)
        .attr('fill', '#9db3c9').attr('opacity', .014);
      // Two dust fields per area: a coarse one that reads as a galaxy from far
      // away and a fine one that stays as a faint background inside it. Each
      // brightness class is one path, so an area costs six elements, not
      // hundreds. The dust takes the area's progress colour.
      const graph = this;
      galaxies.each(function (galaxy) {
        const g = d3.select(this), far = g.append('g').attr('class', 'tau-dust tau-dust-far'), near = g.append('g').attr('class', 'tau-dust tau-dust-near');
        const farRadius = Math.max(3, Math.max(galaxy.rx, galaxy.ry) * .019), nearRadius = Math.max(.4, Math.max(galaxy.rx, galaxy.ry) * .0018);
        [0, 1, 2].forEach(cls => {
          const points = galaxy.dust.filter(p => p.cls === cls);
          far.append('path').attr('class', 'tau-dust-path').attr('data-class', cls).attr('d', graph.dustPath(points, farRadius * (cls === 2 ? 1.2 : cls === 1 ? .95 : .7)));
          near.append('path').attr('class', 'tau-dust-path').attr('data-class', cls).attr('d', graph.dustPath(points.filter((_, index) => index % 3 === 0), nearRadius * (cls === 2 ? 1.3 : 1)));
        });
      });
      this.paintDust();
      galaxies.append('ellipse').attr('class', 'tau-ring tau-galaxy-ring').attr('cx', d => d.x).attr('cy', d => d.y).attr('rx', d => d.rx).attr('ry', d => d.ry)
        .attr('fill', 'none').attr('stroke', ACCENT).attr('vector-effect', 'non-scaling-stroke').attr('stroke-width', 1).attr('opacity', 0);
      const routes = this.layers.route.selectAll('path').data(this.universe.routes).enter().append('path').attr('class', 'tau-route tau-sector-route')
        .attr('data-source-area', d => d.source).attr('data-target-area', d => d.target).attr('data-strong', d => String(!!d.strong))
        .attr('d', d => d.path).attr('vector-effect', 'non-scaling-stroke').attr('stroke-width', d => .7 + Math.min(1, Math.log1p(d.dependencies) * .18)).attr('opacity', 0);
      routes.append('title').text(d => `${d.source} ↔ ${d.target}: ${d.dependencies} roadmap prerequisite links`);
    }

    paintDust() {
      this.layers.galaxy.selectAll('g.tau-galaxy').each(function (galaxy) {
        const lit = hasProgress(galaxy), colour = lit ? accentOf(galaxy) : DUST;
        const base = lit ? .4 + .45 * (progressValue(galaxy.progress) / 100) : .34;
        d3.select(this).selectAll('.tau-dust-path').attr('fill', colour).attr('opacity', function () {
          const cls = Number(this.getAttribute('data-class')); return Math.min(.95, base * (cls === 2 ? 1.5 : cls === 1 ? 1 : .5));
        });
      });
    }

    // ----- level of detail ---------------------------------------------------
    scheduleRender() {
      if (this.renderScheduled || this.destroyed) return;
      this.renderScheduled = true;
      requestAnimationFrame(() => { this.renderScheduled = false; this.render(); });
    }

    visibleRect(margin) {
      const k = this.transform.k, t = this.transform;
      const x0 = -t.x / k, y0 = -t.y / k, w = this.width / k, h = this.height / k;
      return { x: x0 - w * margin, y: y0 - h * margin, w: w * (1 + 2 * margin), h: h * (1 + 2 * margin) };
    }

    thresholds() {
      // Screen-space sizes at which each level becomes legible. A galaxy's
      // heading is only useful while the galaxy is smaller than the view.
      const small = this.width < 600 || this.height < 300;
      return { resolve: 22, constellationName: small ? 40 : 44, starName: small ? 46 : 54, system: 26, planetName: small ? 96 : 120, small };
    }

    render() {
      if (!this.universe || this.destroyed) return;
      const k = this.transform.k, rect = this.visibleRect(.15), T = this.thresholds(), universe = this.universe;
      const active = this.isCoarse ? (this.selectedId || this.hoveredId) : (this.hoveredId || this.selectedId);
      const activeNode = universe.byId.get(active) || null;
      const intersects = (x, y, r) => x + r > rect.x && x - r < rect.x + rect.w && y + r > rect.y && y - r < rect.y + rect.h;
      const galaxies = universe.galaxies.filter(g => intersects(g.x, g.y, Math.max(g.rx, g.ry) * 1.2));
      const constellations = [], stars = [], planets = [], labels = [];
      galaxies.forEach(galaxy => {
        const screenW = galaxy.w * k;
        galaxy.headingVisible = screenW < this.width * 1.6 && intersects(galaxy.x, galaxy.y - galaxy.ry, galaxy.rx);
        if (galaxy.headingVisible) {
          const compact = galaxy.w * k < 150 || T.small;
          const lines = compact ? [SMALL_CAPTIONS[galaxy.label] || wrapText(galaxy.label, 16, 1)[0]] : (CAPTIONS[galaxy.label] || wrapText(galaxy.label, 21, 2));
          labels.push({ id: 'galaxy:' + galaxy.id, nodeId: galaxy.id, kind: 'galaxy', x: galaxy.x, y: galaxy.y - galaxy.ry - 20 / k, lines, font: T.small ? 10 : 11, anchor: 'middle', above: true, priority: 100 + galaxy.count, active: active === galaxy.id,
            alternatives: [{ x: galaxy.x, y: galaxy.y + galaxy.ry + 6 / k, above: false }, { x: galaxy.x - galaxy.rx * .5, y: galaxy.y - galaxy.ry - 20 / k, above: true }, { x: galaxy.x + galaxy.rx * .5, y: galaxy.y - galaxy.ry - 20 / k, above: true }, { x: galaxy.x, y: galaxy.y - 4 / k, above: true }] });
        }
        galaxy.constellationIds.forEach(id => {
          const c = universe.byId.get(id);
          const screenR = c.r * k;
          if (!intersects(c.x, c.y, c.r + 40 / k)) return;
          c.resolved = screenR >= T.resolve && !c.unmapped;
          c.nameVisible = (screenR >= 9 && c.spacing * k >= T.constellationName && screenR < Math.min(this.width, this.height) * 1.1) || active === c.id;
          constellations.push(c);
          if (c.nameVisible) { const top = c.y - (c.resolved ? c.r * 1.05 : Math.max(c.r, 4 / k)) - 5 / k, bottom = c.y + (c.resolved ? c.r * 1.05 : Math.max(c.r, 4 / k)) + 6 / k;
            labels.push({ id: 'constellation:' + c.id, nodeId: c.id, kind: 'constellation', x: c.x, y: top, lines: wrapText(c.label, 20, 2), font: 11, anchor: 'middle', above: true, priority: 60 + (active === c.id ? 40 : 0), active: active === c.id, alternatives: [{ x: c.x, y: bottom, above: false }] }); }
          if (!c.resolved) return;
          c.starIds.forEach(starId => {
            const s = universe.byId.get(starId);
            if (!intersects(s.x, s.y, s.room + 30 / k)) return;
            s.systemVisible = s.room * k >= T.system && s.planetIds.length > 0;
            s.nameVisible = s.nearest * k >= T.starName || active === s.id;
            stars.push(s);
            if (s.nameVisible) labels.push({ id: 'star:' + s.id, nodeId: s.id, kind: 'star', x: s.x, y: s.systemVisible ? s.y - s.room * 1.02 - 4 / k : s.y + s.r * 1.9 + 11 / k, lines: wrapText(s.label, 24, 2), font: 11, anchor: 'middle', above: s.systemVisible, priority: 40 + (active === s.id ? 50 : 0), active: active === s.id,
              alternatives: [{ x: s.x, y: s.systemVisible ? s.y + s.room * 1.02 + 11 / k : s.y - s.r * 1.9 - 4 / k, above: !s.systemVisible }] });
            if (!s.systemVisible) return;
            s.planetIds.forEach(planetId => {
              const p = universe.byId.get(planetId), detail = p.r * k;
              // Each planet reveals more as it grows on screen: its name, then
              // its kind and a statement excerpt, then its own structure.
              p.nameVisible = detail >= 8 || s.room * k >= T.planetName || active === p.id;
              p.kindVisible = detail >= 14 && (p.refinement || p.showKind !== false);
              p.cardVisible = detail >= 34 && !!p.summary;
              p.moonsVisible = detail >= 60 && p.moons.length > 0;
              p.moonNamesVisible = detail >= 120;
              planets.push(p);
              if (p.nameVisible) { const left = p.x < s.x - s.r * .2, right = p.x + p.r * 1.4 + 4 / k, leftX = p.x - p.r * 1.4 - 4 / k, font = detail >= 22 ? 11 : 10, diag = p.r * 1.15 + 3 / k;
                const nameLines = wrapText(p.label, 26, 2);
                // Eight places, tried in order: beside the planet on the side
                // away from its star, the other side, below, above, then the
                // four diagonals. A name that fits nowhere waits for more zoom.
                labels.push({ id: 'planet:' + p.id, nodeId: p.id, kind: 'planet', x: left ? leftX : right, y: p.y + 3.5 / k, lines: nameLines, font, anchor: left ? 'end' : 'start', above: false, priority: 20 + (active === p.id ? 60 : 0), active: active === p.id,
                  alternatives: [{ x: left ? right : leftX, y: p.y + 3.5 / k, above: false, anchor: left ? 'start' : 'end' }, { x: p.x, y: p.y + p.r * 1.6 + 11 / k, above: false, anchor: 'middle' }, { x: p.x, y: p.y - p.r * 1.6 - 4 / k, above: true, anchor: 'middle' },
                    { x: p.x + diag, y: p.y + diag + font / k, above: false, anchor: 'start' }, { x: p.x - diag, y: p.y + diag + font / k, above: false, anchor: 'end' }, { x: p.x + diag, y: p.y - diag, above: true, anchor: 'start' }, { x: p.x - diag, y: p.y - diag, above: true, anchor: 'end' }] });
                // The card hangs directly under the name, wherever the name found room.
                if (p.kindVisible) labels.push({ id: 'card:' + p.id, nodeId: p.id, kind: 'card', follows: 'planet:' + p.id, x: p.x, y: p.y, lines: [(p.refinement ? 'reviewed ' : '') + (p.kind || 'target'), ...(p.cardVisible ? wrapText(p.summary, 40, 3) : [])], font: 9, anchor: 'start', above: false, priority: 15 + (active === p.id ? 60 : 0), active: false });
              }
              if (p.moonsVisible) p.moons.forEach((moon, index) => {
                const angle = index / p.moons.length * Math.PI * 2 - Math.PI / 2, ring = p.r * 1.55;
                moon.x = p.x + Math.cos(angle) * ring; moon.y = p.y + Math.sin(angle) * ring; moon.r = p.r * .12; moon.planetId = p.id; moon.id = p.id + '#moon' + index;
                if (p.moonNamesVisible) { const outward = Math.cos(angle) >= 0; labels.push({ id: 'moon:' + moon.id, nodeId: p.id, ownerId: moon.id, kind: 'moon', x: moon.x + (outward ? 1 : -1) * (moon.r + 3 / k), y: moon.y + 3 / k, lines: [wrapText((moon.kind === 'step' ? moon.index + '. ' : moon.kind === 'check' ? 'check: ' : 'if ') + moon.text, 48, 1)[0]], font: 8.5, anchor: outward ? 'start' : 'end', above: false, priority: 10, active: false }); }
              });
            });
          });
        });
      });
      this.visible = { galaxies, constellations, stars, planets, labels };
      this.renderConstellations(constellations, k, active);
      this.renderStars(stars, k, active);
      this.renderPlanets(planets, k, active);
      this.renderLabels(labels, k);
      this.renderLinks(activeNode, k);
      const galaxySelection = this.layers.galaxy.selectAll('g.tau-galaxy');
      galaxySelection.select('.tau-galaxy-ring').attr('opacity', d => active === d.id ? .55 : 0);
      galaxySelection.select('.tau-galaxy-disc').attr('opacity', d => active === d.id ? .04 : .014);
      // Coarse dust is for the far view only; it is gone before a galaxy fills
      // the chart, while the fine dust takes over as a faint background.
      const farFade = Math.max(0, Math.min(1, (.85 - k) / .45)), nearFade = .6 * Math.max(0, Math.min(1, (k - .35) / .4)) * Math.max(0, Math.min(1, (9 - k) / 4));
      galaxySelection.select('.tau-dust-far').attr('opacity', farFade).attr('display', farFade > 0 ? null : 'none');
      galaxySelection.select('.tau-dust-near').attr('opacity', nearFade).attr('display', nearFade > 0 ? null : 'none');
    }

    renderConstellations(items, k, active) {
      const graph = this;
      const join = this.layers.constellation.selectAll('g.tau-constellation').data(items, d => d.id);
      join.exit().remove();
      const enter = join.enter().append('g').attr('class', d => 'tau-node tau-constellation' + (d.unmapped ? ' tau-unmapped-node' : '')).attr('data-node-id', d => d.id).attr('data-level', 'constellation')
        .attr('transform', d => `translate(${d.x},${d.y})`).attr('tabindex', 0).attr('role', 'button').attr('aria-label', d => normalizeText(d.label) + (d.unmapped ? '. Area without a roadmap' : '. Roadmap' + (progressDescription(d) ? ', ' + progressDescription(d) : '')));
      enter.append('circle').attr('class', 'tau-hit');
      enter.append('circle').attr('class', 'tau-constellation-disc').attr('fill', '#b9cad9');
      enter.append('circle').attr('class', 'tau-beacon tau-survey-beacon');
      enter.append('circle').attr('class', 'tau-ring tau-select-ring').attr('fill', 'none').attr('stroke', ACCENT).attr('vector-effect', 'non-scaling-stroke').attr('stroke-width', 1.4);
      enter.append('title').text(d => normalizeText(d.label) + (progressDescription(d) ? '\n' + progressDescription(d) : '') + '\nClick to open');
      this.bindInteractions(enter);
      const all = enter.merge(join);
      all.classed('is-selected', d => d.id === this.selectedId).classed('is-hovered', d => d.id === this.hoveredId).attr('data-progress', d => progressValue(d.progress)).attr('data-resolved', d => String(!!d.resolved));
      // A target never reaches past the midpoint to its nearest neighbour, so
      // a tap lands on the object under the finger and nothing else.
      all.select('.tau-hit').attr('r', d => Math.min(d.resolved ? d.r * 1.08 : Math.max(d.r, (graph.isCoarse ? 14 : 11) / k), Math.max(d.r * .6, (d.spacing || d.r * 4) * .48)));
      all.select('.tau-constellation-disc').attr('r', d => d.r * 1.12).attr('opacity', d => d.resolved ? (active === d.id ? .12 : .07) : 0);
      all.select('.tau-beacon').attr('r', d => d.resolved ? 0 : d.unmapped ? Math.max(2.4 / k, Math.min(d.r, 3 / k)) : Math.max(2.4 / k, Math.min(d.r * .9, (2.4 + Math.min(2.4, d.r * k * .1)) / k)))
        .attr('fill', d => !d.unmapped && hasProgress(d) ? accentOf(d) : BACKGROUND).attr('stroke', d => d.unmapped ? '#8a99a8' : hasProgress(d) ? accentOf(d) : NO_PROGRESS)
        .attr('stroke-width', d => (d.unmapped ? 1 : 1.1) / k).attr('stroke-dasharray', d => d.unmapped ? `${2 / k} ${2 / k}` : null).attr('opacity', d => d.resolved ? 0 : 1);
      all.select('.tau-select-ring').attr('r', d => d.resolved ? d.r * 1.16 : Math.max(d.r * .9, 7 / k)).attr('opacity', d => active === d.id ? .9 : 0);
      // Constellation figures: the faint shape that makes a roadmap a constellation.
      const figures = [];
      items.filter(d => d.resolved).forEach(d => d.figure.forEach((segment, index) => figures.push({ id: d.id + '#' + index, ...segment, constellation: d })));
      const figureJoin = this.layers.figure.selectAll('path.tau-figure').data(figures, d => d.id);
      figureJoin.exit().remove();
      figureJoin.enter().append('path').attr('class', 'tau-figure').attr('vector-effect', 'non-scaling-stroke').merge(figureJoin)
        .attr('d', d => { const a = this.universe.byId.get(d.source), b = this.universe.byId.get(d.target); return `M${a.x},${a.y}L${b.x},${b.y}`; })
        .attr('stroke-width', d => d.real ? .8 : .6).attr('opacity', d => d.real ? .32 : .14);
    }

    renderStars(items, k, active) {
      const graph = this;
      const join = this.layers.star.selectAll('g.tau-star').data(items, d => d.id);
      join.exit().remove();
      const enter = join.enter().append('g').attr('class', 'tau-node tau-star').attr('data-node-id', d => d.id).attr('data-level', 'star')
        .attr('transform', d => `translate(${d.x},${d.y})`).attr('tabindex', 0).attr('role', 'button').attr('aria-label', d => normalizeText(d.label) + '. Layer' + (progressDescription(d) ? ', ' + progressDescription(d) : ''));
      enter.append('circle').attr('class', 'tau-hit');
      enter.append('circle').attr('class', 'tau-star-core').attr('vector-effect', 'non-scaling-stroke');
      enter.append('circle').attr('class', 'tau-ring tau-select-ring').attr('fill', 'none').attr('stroke', ACCENT).attr('vector-effect', 'non-scaling-stroke').attr('stroke-width', 1.6);
      enter.append('title').text(d => normalizeText(d.label) + (progressDescription(d) ? '\n' + progressDescription(d) : '') + '\nClick to open its planets');
      this.bindInteractions(enter);
      const all = enter.merge(join);
      all.classed('is-selected', d => d.id === this.selectedId).classed('is-hovered', d => d.id === this.hoveredId).attr('data-progress', d => progressValue(d.progress));
      all.select('.tau-hit').attr('r', d => Math.min(Math.max(d.r * 1.8, (graph.isCoarse ? 14 : 10) / k), Math.max(d.r * 1.2, (d.nearest || d.r * 6) * .48)));
      all.select('.tau-star-core').attr('r', d => d.r).attr('fill', d => hasProgress(d) ? accentOf(d) : '#1a222c')
        .attr('stroke', d => hasProgress(d) ? accentOf(d) : NO_PROGRESS).attr('stroke-width', d => hasProgress(d) ? 1 : 1.3).attr('stroke-dasharray', d => hasProgress(d) ? null : '2 2');
      all.select('.tau-select-ring').attr('r', d => d.r * 2.2).attr('opacity', d => active === d.id ? 1 : 0);
    }

    renderPlanets(items, k, active) {
      const graph = this;
      const orbits = [];
      const seen = new Set();
      items.forEach(p => { const key = p.starId + '#' + p.orbit.ring; if (seen.has(key)) return; seen.add(key); const star = this.universe.byId.get(p.starId); orbits.push({ id: key, x: star.x, y: star.y, rx: p.orbit.rx, ry: p.orbit.ry }); });
      const orbitJoin = this.layers.planet.selectAll('ellipse.tau-orbit').data(orbits, d => d.id);
      orbitJoin.exit().remove();
      orbitJoin.enter().append('ellipse').attr('class', 'tau-orbit tau-orbit-path').attr('vector-effect', 'non-scaling-stroke').attr('stroke-width', .7).attr('opacity', .7).merge(orbitJoin)
        .attr('cx', d => d.x).attr('cy', d => d.y).attr('rx', d => d.rx).attr('ry', d => d.ry);
      const join = this.layers.planet.selectAll('g.tau-planet').data(items, d => d.id);
      join.exit().remove();
      const enter = join.enter().append('g').attr('class', 'tau-node tau-planet').attr('data-node-id', d => d.id).attr('data-level', 'planet').attr('data-kind', d => d.kind)
        .attr('transform', d => `translate(${d.x},${d.y})`).attr('tabindex', 0).attr('role', 'button').attr('aria-label', d => normalizeText(d.label) + '. ' + (d.kind || 'target') + (d.refinement ? ', source refinement' : ''));
      enter.append('circle').attr('class', 'tau-hit');
      enter.append('circle').attr('class', 'tau-planet-body').attr('stroke', BACKGROUND).attr('vector-effect', 'non-scaling-stroke').attr('stroke-width', 1);
      enter.append('circle').attr('class', 'tau-ring tau-select-ring').attr('fill', 'none').attr('stroke', ACCENT).attr('vector-effect', 'non-scaling-stroke').attr('stroke-width', 1.5);
      enter.append('title').text(d => normalizeText(d.label) + '\n' + (d.kind || 'target') + (d.refinement ? ' · source refinement' : '') + '\nClick to read');
      this.bindInteractions(enter);
      const all = enter.merge(join);
      all.classed('is-selected', d => d.id === this.selectedId).classed('is-hovered', d => d.id === this.hoveredId);
      all.select('.tau-hit').attr('r', d => { const star = graph.universe.byId.get(d.starId); return Math.min(Math.max(d.r * 1.5, (graph.isCoarse ? 12 : 8) / k), (star && star.planetGap ? star.planetGap : d.r * 4) * .48); });
      all.select('.tau-planet-body').attr('r', d => d.r).attr('fill', d => KIND_FILL[d.kind] || KIND_FILL.construction).attr('stroke-dasharray', d => d.refinement ? `${1.5 / k} ${1.5 / k}` : null);
      all.select('.tau-select-ring').attr('r', d => d.r * 1.9).attr('opacity', d => active === d.id ? 1 : 0);
      // Deep zoom: a reviewed refinement shows its hypotheses (open), proof
      // steps (filled) and acceptance checks (accent) as moons, and the
      // prerequisite links among the refinements of the same layer appear.
      const moons = [];
      items.filter(p => p.moonsVisible).forEach(p => p.moons.forEach(moon => moons.push(moon)));
      const moonJoin = this.layers.planet.selectAll('circle.tau-moon').data(moons, d => d.id);
      moonJoin.exit().remove();
      moonJoin.enter().append('circle').attr('class', 'tau-moon').attr('vector-effect', 'non-scaling-stroke').attr('stroke-width', 1).merge(moonJoin)
        .attr('cx', d => d.x).attr('cy', d => d.y).attr('r', d => d.r).attr('data-kind', d => d.kind)
        .attr('fill', d => d.kind === 'hypothesis' ? '#1a222c' : d.kind === 'check' ? ACCENT : '#b9c2cc').attr('stroke', d => d.kind === 'hypothesis' ? '#9aa6b2' : d.kind === 'check' ? ACCENT : '#b9c2cc');
      const stars = new Map(); items.forEach(p => { if (p.kindVisible) stars.set(p.starId, this.universe.byId.get(p.starId)); });
      const internal = [];
      stars.forEach(star => (star.planetEdges || []).forEach((edge, index) => { const a = this.universe.byId.get(edge.source), b = this.universe.byId.get(edge.target); if (a && b) internal.push({ id: star.id + '#' + index, a, b }); }));
      const linkJoin = this.layers.figure.selectAll('path.tau-system-link').data(internal, d => d.id);
      linkJoin.exit().remove();
      linkJoin.enter().append('path').attr('class', 'tau-system-link').attr('vector-effect', 'non-scaling-stroke').attr('stroke-width', .9).attr('opacity', .5).attr('marker-end', 'url(#' + this.id + '-arrow-quiet)').merge(linkJoin)
        .attr('d', d => { const dx = d.b.x - d.a.x, dy = d.b.y - d.a.y, len = Math.max(.001, Math.hypot(dx, dy)), ax = d.a.x + dx / len * d.a.r * 1.3, ay = d.a.y + dy / len * d.a.r * 1.3, bx = d.b.x - dx / len * d.b.r * 1.5, by = d.b.y - dy / len * d.b.r * 1.5; return `M${ax},${ay}L${bx},${by}`; });
    }

    renderLabels(labels, k) {
      // Greedy placement in screen space: higher priority wins, and no text is
      // drawn over another text. A hidden name reappears once there is room.
      const t = this.transform, placed = [];
      labels.sort((a, b) => b.priority - a.priority);
      // Other galaxies' discs are obstacles for an area heading: a heading
      // that would sit on a neighbouring galaxy is as misleading as an overlap.
      const discs = (this.visible ? this.visible.galaxies : []).map(g => ({ id: g.id, x: g.x * k + t.x, y: g.y * k + t.y, rx: g.rx * k, ry: g.ry * k }));
      const onDisc = (box, own) => discs.some(g => g.id !== own && (((box.x + box.w / 2 - g.x) / g.rx) ** 2 + ((box.y + box.h / 2 - g.y) / g.ry) ** 2) < 1);
      // Planet discs and star cores are solid: text never runs across another
      // object. The zoom buttons and the hint in the chart's corners are
      // solid too, so nothing is drawn behind them.
      const solids = [];
      (this.visible ? this.visible.stars : []).forEach(s => { const r = s.r * k; if (r >= 2.5) solids.push({ owner: s.id, x: s.x * k + t.x, y: s.y * k + t.y, r }); });
      (this.visible ? this.visible.planets : []).forEach(p => { const r = p.r * k; if (r >= 2.5) solids.push({ owner: p.id, x: p.x * k + t.x, y: p.y * k + t.y, r }); });
      const overlays = this.overlayBoxes();
      const onSolid = (box, own) => solids.some(s => s.owner !== own && Math.hypot(Math.max(box.x, Math.min(s.x, box.x + box.w)) - s.x, Math.max(box.y, Math.min(s.y, box.y + box.h)) - s.y) < s.r - 1)
        || overlays.some(o => Math.min(box.x + box.w, o.x + o.w) - Math.max(box.x, o.x) > 0 && Math.min(box.y + box.h, o.y + o.h) - Math.max(box.y, o.y) > 0);
      const collides = (box, label) => placed.some(other => Math.min(box.x + box.w, other.x + other.w) - Math.max(box.x, other.x) > -2 && Math.min(box.y + box.h, other.y + other.h) - Math.max(box.y, other.y) > -1)
        || (label.kind === 'galaxy' && onDisc(box, label.nodeId)) || onSolid(box, label.ownerId || label.nodeId);
      const byId = new Map(labels.map(label => [label.id, label]));
      // A name is drawn only when the whole of it fits the chart; a clipped
      // name reads as a different name.
      const onScreen = box => box.x >= 2 && box.x + box.w <= this.width - 2 && box.y >= 2 && box.y + box.h <= this.height - 2;
      labels.forEach(label => {
        // Widths come from measured text where a line has been drawn before;
        // otherwise from an estimate that errs wide. A margin keeps neighbours
        // apart even when the measurement is a frame old.
        const measure = (line, index) => this.widthCache.get(label.font + (label.kind === 'card' && index === 0 ? 'u' : 'n') + '|' + line) ?? line.length * label.font * (label.kind === 'card' && index === 0 ? .84 : .62);
        const w = Math.max(...label.lines.map(measure)) + 8, h = label.lines.length * (label.font + 3) + 3;
        // An area heading or a constellation name may step aside rather than
        // vanish: below its object, or to either side, when the place above
        // is taken. Star and planet names keep their single place.
        const spots = [{ x: label.x, y: label.y, above: label.above }];
        if (label.alternatives) label.alternatives.forEach(spot => spots.push(spot));
        label.shown = false;
        if (label.follows) {
          // A follower hangs under the label it follows, flush with its left
          // or right edge, and disappears with it.
          const lead = byId.get(label.follows);
          if (!lead || !lead.shown) { label.box = { x: 0, y: 0, w: 0, h: 0 }; return; }
          const b = lead.box;
          spots.length = 0; spots.push({ screen: { x: b.x, y: b.y + b.h + 2 } }, { screen: { x: b.x + b.w - w, y: b.y + b.h + 2 } });
        }
        for (const spot of spots) {
          const anchor = spot.screen ? 'start' : spot.anchor || label.anchor, sx = spot.screen ? spot.screen.x : spot.x * k + t.x, sy = spot.screen ? spot.screen.y + label.font : spot.y * k + t.y;
          const box = { x: anchor === 'middle' ? sx - w / 2 : anchor === 'end' ? sx - w : sx, y: spot.above ? sy - h + 3 : sy - label.font, w, h };
          if (!onScreen(box) || collides(box, label)) { label.box = label.box || box; continue; }
          label.shown = true; label.box = box; label.x = spot.screen ? (sx - t.x) / k : spot.x; label.y = spot.screen ? (sy - t.y) / k : spot.y; label.above = !!spot.above; label.anchor = anchor; placed.push(box);
          break;
        }
        if (!label.box) { const sx = label.x * k + t.x, sy = label.y * k + t.y; label.box = { x: sx - w / 2, y: sy - h + 3, w, h }; }
      });
      const shown = labels.filter(label => label.shown);
      const join = this.layers.label.selectAll('g.tau-label').data(shown, d => d.id);
      join.exit().remove();
      const enter = join.enter().append('g').attr('class', d => 'tau-label tau-label-' + d.kind).attr('data-label-for', d => d.nodeId);
      enter.append('rect').attr('class', 'tau-label-hit');
      enter.append('text');
      const graph = this;
      enter.filter(d => d.kind === 'galaxy').on('click', d => { d3.event.stopPropagation(); if (Date.now() < graph.suppressClicksUntil) return; graph.options.onSelect?.(graph.universe.byId.get(d.nodeId)); })
        .on('mouseenter', d => { if (!graph.isCoarse) { graph.hoveredId = d.nodeId; graph.scheduleRender(); } }).on('mouseleave', () => { if (!graph.isCoarse) { graph.hoveredId = null; graph.scheduleRender(); } });
      const all = enter.merge(join);
      all.classed('is-active', d => d.active).attr('transform', d => `translate(${d.x},${d.y}) scale(${1 / k})`);
      const cache = this.widthCache; let measured = false;
      all.select('text').attr('text-anchor', d => d.anchor).attr('font-size', d => d.font).each(function (d) {
        const text = d3.select(this); text.selectAll('tspan').remove();
        d.lines.forEach((line, index) => {
          const span = text.append('tspan').attr('x', 0).attr('y', d.above ? -(d.lines.length - 1 - index) * (d.font + 3) : index * (d.font + 3)).text(line);
          const key = d.font + (d.kind === 'card' && index === 0 ? 'u' : 'n') + '|' + line;
          if (!cache.has(key)) { try { cache.set(key, span.node().getComputedTextLength()); measured = true; } catch (_) { /* detached */ } }
        });
      });
      all.select('rect').attr('x', d => d.anchor === 'middle' ? -d.box.w / 2 : d.anchor === 'end' ? -d.box.w : 0).attr('y', d => d.above ? -d.box.h + 3 : -d.font).attr('width', d => d.box.w).attr('height', d => d.box.h)
        .style('pointer-events', d => d.kind === 'galaxy' ? 'all' : 'none');
      if (measured) this.scheduleRender();
    }

    overlayBoxes() {
      // The corner controls, in chart coordinates, padded by a few pixels.
      const host = this.container && this.container.parentNode;
      if (!host) return [];
      const hint = host.querySelector('.graph-hint'), key = this.width + 'x' + this.height + '|' + (hint ? hint.textContent : '');
      if (this.overlayCache && this.overlayCache.key === key) return this.overlayCache.boxes;
      const base = this.container.getBoundingClientRect();
      const boxes = Array.from(host.querySelectorAll('.graph-tools, .graph-hint')).map(el => el.getBoundingClientRect()).filter(b => b.width > 0 && b.height > 0)
        .map(b => ({ x: b.left - base.left - 4, y: b.top - base.top - 4, w: b.width + 8, h: b.height + 8 }));
      this.overlayCache = { key, boxes };
      return boxes;
    }

    renderLinks(activeNode, k) {
      const links = [];
      if (activeNode) {
        const universe = this.universe;
        const curve = (a, b, bend) => { const dx = b.x - a.x, dy = b.y - a.y, length = Math.max(1, Math.hypot(dx, dy)); const mx = (a.x + b.x) / 2 - dy / length * bend, my = (a.y + b.y) / 2 + dx / length * bend; return `M${a.x},${a.y}Q${mx},${my} ${b.x},${b.y}`; };
        if (activeNode.level === 'star') universe.starEdges.forEach((edge, index) => {
          if (edge.source !== activeNode.id && edge.target !== activeNode.id) return;
          const a = universe.byId.get(edge.source), b = universe.byId.get(edge.target);
          links.push({ id: 'star:' + index, path: curve(a, b, Math.min(12, Math.hypot(b.x - a.x, b.y - a.y) * .12)), arrow: true, reference: false });
        });
        if (activeNode.level === 'constellation') {
          universe.constellationEdges.forEach((edge, index) => {
            if (edge.source !== activeNode.id && edge.target !== activeNode.id) return;
            const a = universe.byId.get(edge.source), b = universe.byId.get(edge.target);
            links.push({ id: 'roadmap:' + index, path: curve(a, b, Math.min(60, Math.hypot(b.x - a.x, b.y - a.y) * .1)), arrow: true, reference: false });
          });
          if (this.showReferences) universe.relatedEdges.forEach((edge, index) => {
            if (edge.source !== activeNode.id && edge.target !== activeNode.id) return;
            const a = universe.byId.get(edge.source), b = universe.byId.get(edge.target);
            links.push({ id: 'related:' + index, path: curve(a, b, 0), arrow: false, reference: true });
          });
        }
        if (activeNode.level === 'galaxy') this.layers.route.selectAll('path.tau-route').attr('opacity', d => d.source === activeNode.id || d.target === activeNode.id ? .6 : 0);
      }
      if (!activeNode || activeNode.level !== 'galaxy') this.layers.route.selectAll('path.tau-route').attr('opacity', 0);
      const join = this.layers.link.selectAll('path.tau-link').data(links, d => d.id);
      join.exit().remove();
      join.enter().append('path').attr('class', d => 'tau-link' + (d.reference ? ' is-reference tau-reference-edge' : '')).attr('vector-effect', 'non-scaling-stroke').merge(join)
        .attr('d', d => d.path).attr('stroke-width', 1.1).attr('opacity', .6).attr('stroke-dasharray', d => d.reference ? '2 6' : null)
        .attr('marker-end', d => d.arrow ? 'url(#' + this.id + '-arrow)' : null);
    }

    bindInteractions(selection) {
      const graph = this;
      selection.on('click', d => { d3.event.stopPropagation(); if (Date.now() < graph.suppressClicksUntil) return; graph.options.onSelect?.(d); })
        .on('mouseenter', d => { if (!graph.isCoarse) { graph.hoveredId = d.id; graph.scheduleRender(); } })
        .on('mouseleave', () => { if (!graph.isCoarse) { graph.hoveredId = null; graph.scheduleRender(); } })
        .on('focus', d => { graph.hoveredId = d.id; graph.scheduleRender(); }).on('blur', () => { graph.hoveredId = null; graph.scheduleRender(); })
        .on('keydown', d => { if (d3.event.key !== 'Enter' && d3.event.key !== ' ') return; d3.event.preventDefault(); d3.event.stopPropagation(); graph.options.onSelect?.(d); });
    }

    // ----- selection ----------------------------------------------------------
    select(id, fromBackground) {
      this.selectedId = this.universe && this.universe.byId.has(id) ? id : null;
      this.scheduleRender();
      if (fromBackground && this.options.onClear) this.options.onClear();
      return this;
    }

    // ----- camera ---------------------------------------------------------------
    footprint(id) {
      const node = this.universe && this.universe.byId.get(id);
      if (!node) return null;
      if (node.level === 'galaxy') return { x: node.x - node.rx, y: node.y - node.ry, w: node.rx * 2, h: node.ry * 2 };
      if (node.level === 'constellation') { const r = Math.max(node.r * 1.45, 26); return { x: node.x - r, y: node.y - r * 1.15, w: r * 2, h: r * 2.15 }; }
      if (node.level === 'star') { const r = Math.max(node.room * 1.35, node.r * 9); return { x: node.x - r, y: node.y - r, w: r * 2, h: r * 2 }; }
      if (node.level === 'planet') return this.footprint(node.starId);
      return null;
    }

    transformFor(rect) {
      // Portrait phones keep the zoom controls clear; a short landscape chart
      // needs its height more than that margin and gets a smaller reserve.
      const reserve = this.width < 600 ? 56 : this.height < 400 ? 24 : 0, usable = this.height - reserve;
      const scale = Math.max(.015, Math.min(900, (this.width - 36) / rect.w, (usable - 36) / rect.h));
      return d3.zoomIdentity.translate(this.width / 2 - (rect.x + rect.w / 2) * scale, usable / 2 - (rect.y + rect.h / 2) * scale).scale(scale);
    }

    travel(transform, animate) {
      this.svg.interrupt();
      if (!animate || (matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)) { this.svg.call(this.zoom.transform, transform); return this; }
      this.busy = true;
      this.svg.transition().duration(240).ease(d3.easeCubicOut).call(this.zoom.transform, transform)
        .on('end.travel', () => { this.busy = false; this.scheduleFocus(); }).on('interrupt.travel', () => { this.busy = false; });
      return this;
    }

    // Headings and names live in screen pixels, so the room kept for them
    // above a frame is converted from pixels at the scale the frame will get.
    transformWithHeadroom(rect, topPx, bottomPx) {
      const first = this.transformFor(rect).k;
      return this.transformFor({ x: rect.x, y: rect.y - topPx / first, w: rect.w, h: rect.h + (topPx + bottomPx) / first });
    }
    zoomTo(id, animate) {
      const rect = this.footprint(id), node = this.universe && this.universe.byId.get(id);
      if (!rect) return this;
      const headroom = node && node.level === 'galaxy' ? 44 : node && node.level === 'constellation' ? 36 : 24;
      return this.travel(this.transformWithHeadroom(rect, headroom, 8), animate !== false);
    }
    fitAll(animate) { if (!this.universe) return this; const b = this.universe.bounds; return this.travel(this.transformWithHeadroom({ x: b.x - 40, y: b.y, w: b.w + 80, h: b.h }, 48, 12), animate !== false); }
    fit(animate) { return this.lastFocus && this.lastFocus.id ? this.zoomTo(this.lastFocus.id, animate) : this.fitAll(animate); }
    zoomIn() { this.svg.transition().duration(140).call(this.zoom.scaleBy, 2.4); return this; }
    zoomOut() { this.svg.transition().duration(140).call(this.zoom.scaleBy, 1 / 2.4); return this; }
    captureCamera() { return { x: this.transform.x, y: this.transform.y, k: this.transform.k, width: this.width, height: this.height }; }
    restoreCamera(camera) {
      if (!camera || ![camera.x, camera.y, camera.k].every(Number.isFinite) || camera.k <= 0) return this;
      const x = camera.x + (this.width - (camera.width || this.width)) / 2, y = camera.y + (this.height - (camera.height || this.height)) / 2;
      this.svg.interrupt(); this.svg.call(this.zoom.transform, d3.zoomIdentity.translate(x, y).scale(camera.k));
      return this;
    }

    // The camera decides what the reader is looking at: the galaxy that fills
    // the view, the constellation under its centre, the star whose system is
    // in front of them. This drives the address bar and breadcrumbs without
    // ever relaying out the scene.
    focus() {
      if (!this.universe) return { level: 'all', id: null };
      const k = this.transform.k, cx = (this.width / 2 - this.transform.x) / k, cy = (this.height / 2 - this.transform.y) / k;
      // An object is "in focus" when the camera is at least a good fraction of
      // the scale that fits it and its centre is near the middle of the view.
      const fitScale = id => this.transformFor(this.footprint(id)).k;
      let galaxy = null;
      this.universe.galaxies.forEach(g => { if (((cx - g.x) / (g.rx * 1.2)) ** 2 + ((cy - g.y) / (g.ry * 1.2)) ** 2 <= 1 && k >= fitScale(g.id) * .6) galaxy = g; });
      if (!galaxy) return { level: 'all', id: null };
      let constellation = null, best = Infinity;
      galaxy.constellationIds.forEach(id => { const c = this.universe.byId.get(id); const d = Math.hypot(cx - c.x, cy - c.y); if (d < c.r * 1.8 + 30 / k && d < best && k >= fitScale(id) * .5) { best = d; constellation = c; } });
      if (!constellation) return { level: 'galaxy', id: galaxy.id };
      let star = null; best = Infinity;
      constellation.starIds.forEach(id => { const s = this.universe.byId.get(id); const d = Math.hypot(cx - s.x, cy - s.y); if (d < s.room * 1.6 + 12 / k && d < best && k >= fitScale(id) * .5) { best = d; star = s; } });
      if (star) return { level: 'star', id: star.id, constellationId: constellation.id, galaxyId: galaxy.id };
      return { level: 'constellation', id: constellation.id, galaxyId: galaxy.id };
    }

    scheduleFocus() {
      clearTimeout(this.focusTimer);
      this.focusTimer = setTimeout(() => {
        if (this.destroyed || this.busy) return;
        const focus = this.focus();
        if (this.lastFocus && this.lastFocus.level === focus.level && this.lastFocus.id === focus.id) return;
        this.lastFocus = focus;
        this.options.onFocus?.(focus);
      }, 90);
    }

    // ----- export and diagnostics ------------------------------------------------
    exportSVG() {
      const source = this.svg.node(), clone = source.cloneNode(true);
      const box = { x: -this.transform.x / this.transform.k, y: -this.transform.y / this.transform.k, w: this.width / this.transform.k, h: this.height / this.transform.k };
      const presentation = ['color', 'fill', 'fill-opacity', 'fill-rule', 'stroke', 'stroke-width', 'stroke-opacity', 'stroke-dasharray', 'stroke-dashoffset', 'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit',
        'opacity', 'font-family', 'font-size', 'font-style', 'font-weight', 'font-variant', 'letter-spacing', 'word-spacing', 'text-anchor', 'dominant-baseline', 'text-decoration', 'paint-order', 'vector-effect', 'visibility', 'display', 'rx', 'ry'];
      const originals = [source, ...source.querySelectorAll('*')], copies = [clone, ...clone.querySelectorAll('*')];
      originals.forEach((element, index) => {
        const copy = copies[index], tag = element.tagName.toLowerCase();
        if (['style', 'title', 'desc', 'defs'].includes(tag)) return;
        const computed = window.getComputedStyle(element);
        copy.removeAttribute('style');
        presentation.forEach(property => {
          let value = computed.getPropertyValue(property);
          if (!value || value === 'auto' || value === 'normal' && ['letter-spacing', 'word-spacing'].includes(property)) return;
          if (/url\(/.test(value)) { const fragment = value.match(/#([^"')]+)["']?\)/); if (!fragment || !source.querySelector('[id="' + fragment[1].replace(/"/g, '') + '"]')) return; value = 'url(#' + fragment[1] + ')'; }
          copy.style.setProperty(property, value, 'important');
        });
        copy.removeAttribute('tabindex'); if (copy.getAttribute('role') === 'button') copy.removeAttribute('role'); copy.removeAttribute('aria-pressed');
      });
      clone.querySelectorAll('style').forEach(style => style.remove());
      clone.querySelectorAll('title').forEach(title => { title.textContent = title.textContent.replace(/\nClick to .*$/, ''); });
      const backdrop = document.createElementNS(SVG_NS, 'rect');
      backdrop.setAttribute('class', 'tau-export-background'); backdrop.setAttribute('x', box.x); backdrop.setAttribute('y', box.y); backdrop.setAttribute('width', box.w); backdrop.setAttribute('height', box.h); backdrop.setAttribute('fill', BACKGROUND);
      clone.insertBefore(backdrop, clone.querySelector('.tau-viewport'));
      clone.setAttribute('xmlns', SVG_NS); clone.setAttribute('width', Math.ceil(this.width)); clone.setAttribute('height', Math.ceil(this.height));
      clone.setAttribute('viewBox', [box.x, box.y, box.w, box.h].join(' ')); clone.setAttribute('role', 'img'); clone.setAttribute('aria-label', 'Tau Ceti mathematics universe');
      clone.style.setProperty('background-color', BACKGROUND);
      clone.querySelector('.tau-viewport').removeAttribute('transform');
      return '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(clone);
    }

    debugState() {
      const universe = this.universe || { galaxies: [], constellations: [], stars: [], planets: [], routes: [] }, visible = this.visible || { galaxies: [], constellations: [], stars: [], planets: [], labels: [] };
      return {
        layout: 'universe', width: this.width, height: this.height, transform: { x: this.transform.x, y: this.transform.y, k: this.transform.k },
        selectedId: this.selectedId, hoveredId: this.hoveredId, focus: this.focus(), lastFocus: this.lastFocus, busy: this.busy, clicksSuppressed: Date.now() < this.suppressClicksUntil,
        counts: { galaxies: universe.galaxies.length, constellations: universe.constellations.length, stars: universe.stars.length, planets: universe.planets.length, routes: universe.routes.length, strongRoutes: universe.routes.filter(r => r.strong).length },
        visible: { galaxies: visible.galaxies.length, constellations: visible.constellations.length, resolved: visible.constellations.filter(c => c.resolved).length, stars: visible.stars.length, planets: visible.planets.length, labels: visible.labels.filter(l => l.shown).length },
        rendered: this.container.querySelectorAll('.tau-layer-constellation g, .tau-layer-star g, .tau-layer-planet g, .tau-layer-label g').length,
        galaxies: universe.galaxies.map(g => ({ id: g.id, label: g.label, x: g.x, y: g.y, rx: g.rx, ry: g.ry, count: g.count, headingVisible: !!g.headingVisible })),
        constellations: universe.constellations.map(c => ({ id: c.id, galaxyId: c.galaxyId, x: c.x, y: c.y, r: c.r, stars: c.starIds.length, resolved: !!c.resolved, nameVisible: !!c.nameVisible, progress: progressValue(c.progress), hasProgress: hasProgress(c), accent: accentOf(c), unmapped: !!c.unmapped })),
        stars: universe.stars.map(s => ({ id: s.id, constellationId: s.constellationId, x: s.x, y: s.y, r: s.r, room: s.room, planets: s.planetIds.length, rank: s.rank, dependencyOrderValid: s.dependencyOrderValid, progress: progressValue(s.progress), accent: accentOf(s) })),
        routes: universe.routes.map(({ source, target, dependencies, witnesses, strong }) => ({ source, target, dependencies, witnesses, strong: !!strong }))
      };
    }

    destroy() {
      this.destroyed = true; clearTimeout(this.focusTimer);
      if (this.observer) this.observer.disconnect(); else window.removeEventListener('resize', this.resize);
      this.svg.interrupt().on('.zoom', null).remove();
    }

    static progressColor(value) { return progressColor(value); }
  }
  window.TauGraph = TauGraph;
})();
