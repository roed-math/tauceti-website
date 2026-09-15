/* TauCeti offline graph canvas. Requires the bundled D3 v5 script. */
(function () {
  'use strict';
  let instanceCount = 0;
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const finite = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const normalizeText = value => String(value == null ? '' : value).replace(/([a-z])([A-Z])/g, '$1 $2').replace(/_/g, ' ');

  function progressValue(value) {
    return typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null;
  }

  function progressColor(value) {
    const progress = progressValue(value);
    if (progress === null) return null;
    const stops = [[194, 65, 65], [183, 121, 6], [22, 128, 82]];
    const index = progress <= 50 ? 0 : 1;
    const fraction = progress <= 50 ? progress / 50 : (progress - 50) / 50;
    return '#' + stops[index].map((channel, i) => Math.round(channel + (stops[index + 1][i] - channel) * fraction).toString(16).padStart(2, '0')).join('');
  }

  function nodeAccent(node) { return progressColor(node.progress) || node.color || '#557bb5'; }
  function progressLabel(node) {
    if (typeof node.progressLabel === 'string' && node.progressLabel.trim()) return node.progressLabel.trim();
    const value = progressValue(node.progress);
    return value === null ? '' : Math.round(value) + '%';
  }
  function progressDescription(node) {
    if (typeof node.progressLabel === 'string' && node.progressLabel.trim()) return node.progressLabel.trim();
    return progressLabel(node) ? progressLabel(node) + ' of layers complete' : '';
  }

  function wrapText(text, maxChars, maxLines) {
    const words = normalizeText(text).split(/\s+/).filter(Boolean);
    const lines = [];
    let line = '';
    for (let word of words) {
      while (word.length > maxChars) {
        if (line) { lines.push(line); line = ''; }
        lines.push(word.slice(0, maxChars - 1) + '–');
        word = word.slice(maxChars - 1);
      }
      if (line && line.length + word.length + 1 > maxChars) { lines.push(line); line = ''; }
      line += (line ? ' ' : '') + word;
    }
    if (line) lines.push(line);
    if (lines.length > maxLines) {
      lines.length = maxLines;
      lines[maxLines - 1] = lines[maxLines - 1].replace(/[ .,;:–-]+$/, '') + '…';
    }
    return lines.length ? lines : ['Untitled'];
  }

  function dimensions(node) {
    if (node.type === 'group') return { w: 276, h: 108, font: 17, lines: 3, chars: 27 };
    if (node.type === 'stage') return { w: 278, h: 100, font: 14, lines: 3, chars: 32 };
    if (node.type === 'external') return { w: 242, h: 92, font: 14, lines: 3, chars: 29 };
    return { w: 212, h: 88, font: 14, lines: 3, chars: 25 };
  }

  class TauGraph {
    constructor(container, options) {
      if (!window.d3) throw new Error('The local graph library did not load. Keep the vendor folder beside the explorer.');
      if (typeof container === 'string') container = document.querySelector(container);
      if (!container) throw new Error('Graph container is missing.');
      this.container = container;
      this.options = options || {};
      this.id = 'tau-graph-' + (++instanceCount);
      this.nodes = [];
      this.edges = [];
      this.clusters = []; this.vessels = []; this.vesselSubjects = []; this.lobeShapes = [];
      this.nodeMap = new Map();
      this.selectedId = null;
      this.transform = d3.zoomIdentity;
      this.destroyed = false;
      this.svg = d3.select(container).append('svg')
        .attr('class', 'tau-graph').attr('xmlns', SVG_NS)
        .attr('width', '100%').attr('height', '100%')
        .attr('role', 'group').attr('aria-label', 'Interactive roadmap graph. Tab to a node and press Enter to select it, or Shift Enter to open it.')
        .style('display', 'block').style('width', '100%').style('height', '100%')
        .style('background', '#f8fafc').style('touch-action', 'none');
      this.svg.append('style').text(`
        .tau-graph .tau-node { cursor: pointer; outline: none; }
        .tau-graph .tau-card { fill: var(--tau-progress-fill, #ffffff); stroke: #c9d4e1; stroke-width: 1.2; }
        .tau-graph .tau-node:hover .tau-card { stroke: #334b6b; stroke-width: 2; }
        .tau-graph .tau-node:focus .tau-card { stroke: #155eef; stroke-width: 3; }
        .tau-graph .tau-node.is-selected .tau-card { fill: var(--tau-progress-fill, #eff6ff); stroke: #145dc0; stroke-width: 3; }
        .tau-graph .tau-node.is-neighbor .tau-card { stroke: #597392; stroke-width: 1.8; }
        .tau-graph text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; pointer-events: none; }
        .tau-graph .tau-node-title { fill: #152c46; font-weight: 600; }
        .tau-graph .tau-node-subtitle { fill: #61728a; font-size: 11px; }
        .tau-graph .tau-node-progress { font-size: 11px; font-weight: 700; }
        .tau-graph .tau-edge { fill: none; stroke-linecap: round; pointer-events: none; }
        .tau-graph .tau-cluster { fill: #ffffff; fill-opacity: .3; stroke: #dde5ee; stroke-dasharray: 5 5; }
        .tau-graph .tau-vessel { pointer-events: none; }
        .tau-graph .tau-vessel-subject { cursor: pointer; outline: none; }
        .tau-graph .tau-vessel-subject:hover rect, .tau-graph .tau-vessel-subject:focus rect { stroke: #bda06c; stroke-width: 1; }
        .tau-graph .tau-leaf { stroke: #fff; stroke-width: 2; }
        .tau-graph .tau-node.is-selected .tau-leaf, .tau-graph .tau-node.is-hovered .tau-leaf, .tau-graph .tau-node:focus .tau-leaf { stroke: #183c59; stroke-width: 3.5; }
        .tau-graph .tau-leaf-ring { fill: none; stroke: #bb717b; stroke-width: 1; opacity: .2; }
        .tau-graph .is-selected .tau-leaf-ring { stroke: #183c59; opacity: .75; }
        .tau-graph .tau-vessel-hit { fill: transparent; pointer-events: all; }
        .tau-graph .tau-vessel-node-label { pointer-events: none; }
        .tau-graph .tau-vessel-node-label text { fill: #20324a; font-size: 12px; font-weight: 600; }
        .tau-graph .tau-cluster-title { fill: #61728a; font-size: 15px; font-weight: 600; }
      `);
      const defs = this.svg.append('defs');
      ['normal', 'highlight'].forEach(kind => {
        defs.append('marker').attr('id', this.id + '-arrow-' + kind)
          .attr('viewBox', '0 -4 9 8').attr('refX', 8).attr('refY', 0)
          .attr('markerWidth', kind === 'normal' ? 7 : 9).attr('markerHeight', kind === 'normal' ? 7 : 9)
          .attr('orient', 'auto').attr('markerUnits', 'userSpaceOnUse')
          .append('path').attr('d', 'M0,-3.5L8,0L0,3.5Z').attr('fill', kind === 'normal' ? '#8497ae' : '#2668ad');
      });
      this.viewport = this.svg.append('g').attr('class', 'tau-viewport');
      this.clusterLayer = this.viewport.append('g');
      this.edgeLayer = this.viewport.append('g').attr('aria-hidden', 'true');
      this.nodeLayer = this.viewport.append('g');
      this.zoom = d3.zoom().scaleExtent([0.025, 4])
        .filter(() => !d3.event.button && (!d3.event.ctrlKey || d3.event.type === 'wheel'))
        .on('zoom', () => {
          this.transform = d3.event.transform;
          this.viewport.attr('transform', this.transform);
          this.updateVesselLabels();
        });
      this.svg.call(this.zoom).on('dblclick.zoom', null);
      this.svg.on('click.background', () => {
        if (d3.event.target === this.svg.node()) this.select(null);
      });
      this.resize = () => {
        if (this.destroyed) return;
        const box = this.container.getBoundingClientRect();
        this.width = Math.max(160, box.width || 800);
        this.height = Math.max(160, box.height || 600);
        this.svg.attr('viewBox', '0 0 ' + this.width + ' ' + this.height);
        this.zoom.extent([[0, 0], [this.width, this.height]]);
        if (this.awaitingFit && box.width > 0 && box.height > 0) { this.awaitingFit = false; this.fit(false); }
      };
      this.resize();
      if (window.ResizeObserver) { this.observer = new ResizeObserver(this.resize); this.observer.observe(container); }
      else window.addEventListener('resize', this.resize);
    }

    setData(data, settings) {
      settings = settings || {};
      this.layout = settings.layout || 'clusters';
      this.svg.interrupt();
      this.nodes = (data.nodes || []).map(node => Object.assign({}, node, dimensions(node)));
      this.nodeMap = new Map(this.nodes.map(node => [node.id, node]));
      this.edges = (data.edges || []).map((edge, index) => ({
        source: this.nodeMap.get(typeof edge.source === 'object' ? edge.source.id : edge.source),
        target: this.nodeMap.get(typeof edge.target === 'object' ? edge.target.id : edge.target),
        kind: edge.kind || 'stage', id: index
      })).filter(edge => edge.source && edge.target && edge.source !== edge.target);
      this.clusters = [];
      this.vessels = []; this.vesselSubjects = []; this.lobeShapes = []; this.vesselBounds = null; this.hoveredId = null;
      this.svg.classed('tau-vessels-layout', this.layout === 'vessels').attr('data-layout', this.layout)
        .style('background', this.layout === 'vessels' ? '#111927' : '#f8fafc');
      if (this.layout === 'vessels') this.layoutVessels();
      else if (this.layout === 'layers') this.layoutLayers();
      else if (this.layout === 'groups') this.layoutGroups();
      else this.layoutClusters();
      this.draw();
      this.select(settings.selectedId == null ? null : settings.selectedId);
      this.awaitingFit = true;
      this.resize();
      return this;
    }

    layoutVessels() {
      const grouped = new Map();
      this.nodes.forEach(node => {
        const label = node.group || 'Roadmaps';
        if (!grouped.has(label)) grouped.set(label, []);
        grouped.get(label).push(node);
        Object.assign(node, { w: 22, h: 22, radius: 8.5, font: 13 });
      });
      const subjects = Array.from(grouped, ([label, nodes]) => ({ label, nodes: nodes.sort((a, b) => a.id.localeCompare(b.id)) }));
      subjects.sort((a, b) => b.nodes.length - a.nodes.length || a.label.localeCompare(b.label));
      const rose = '#a58b59';
      const branch = (source, target, startWidth, endWidth, kind, group) => {
        const segment = { source, target, startWidth, endWidth, kind, group, color: rose };
        this.vessels.push(segment);
        return segment;
      };
      const root = { x: 0, y: -655 }, fork = { x: 0, y: -490 };
      if (subjects.length > 1) {
        branch(root, fork, 22, 16, 'trunk', null);
        const slots = [[440, -340], [205, -355], [520, -20], [240, -20], [450, 285], [200, 310], [430, 560]];
        const sides = [{ sign: -1, groups: [], weight: 0 }, { sign: 1, groups: [], weight: 0 }];
        subjects.forEach(subject => {
          const side = sides[0].weight <= sides[1].weight ? sides[0] : sides[1];
          side.groups.push(subject); side.weight += subject.nodes.length;
        });
        sides.forEach(side => {
          const top = { x: side.sign * 100, y: -350 };
          const mid = { x: side.sign * 140, y: 0 };
          const base = { x: side.sign * 165, y: 410 };
          branch(fork, top, 15, 11, 'lobe', null);
          branch(top, mid, 11, 7.5, 'lobe', null);
          branch(mid, base, 7.5, 3, 'lobe', null);
          side.groups.forEach((subject, i) => {
            const slot = slots[i % slots.length];
            const overflow = Math.floor(i / slots.length);
            subject.x = side.sign * (slot[0] + overflow * 320);
            subject.y = slot[1] + overflow * 60;
            subject.side = side.sign;
            subject.radius = Math.max(68, Math.min(138, Math.sqrt(subject.nodes.length) * 21.5));
            subject.hub = { x: subject.x - side.sign * subject.radius * .69, y: subject.y - 12 };
            const source = i < 2 ? top : i < 4 ? mid : base;
            branch(source, subject.hub, 6.5, 3.5, 'subject', subject.label);
          });
        });
        this.vesselBounds = { x: -715, y: -685, w: 1430, h: 1420 };
        this.lobeShapes = [
          'M-27,-461C-128,-574 -295,-567 -452,-482C-690,-377 -744,-124 -679,135C-627,425 -534,625 -356,681C-230,718 -68,611 -90,386C-112,179 -83,-213 -27,-461Z',
          'M27,-461C128,-574 307,-553 468,-467C684,-352 742,-93 674,158C628,418 545,635 355,683C225,716 75,611 92,387C109,162 79,-213 27,-461Z'
        ];
      } else if (subjects.length === 1) {
        const subject = subjects[0];
        subject.x = 0; subject.y = 25; subject.side = 1;
        subject.radius = Math.max(120, Math.sqrt(subject.nodes.length) * 31);
        subject.hub = { x: -subject.radius * .9, y: -30 };
        branch({ x: -subject.radius * 1.5, y: -220 }, subject.hub, 15, 6, 'trunk', subject.label);
      }
      subjects.forEach((subject, subjectIndex) => {
        const golden = Math.PI * (3 - Math.sqrt(5));
        subject.nodes.forEach((node, index) => {
          const angle = index * golden + subjectIndex * .77;
          const distance = subject.radius * Math.sqrt((index + .6) / subject.nodes.length);
          node.x = subject.x + Math.cos(angle) * distance * .97;
          node.y = subject.y + Math.sin(angle) * distance * 1.05;
          node.vesselGroup = subject.label;
          node.vesselLabelRank = index;
        });
        // A spatially branching tree joins the circular terminals. Median
        // subdivisions follow the local point cloud, without adding proof edges.
        const grow = (parent, nodes, level) => {
          if (nodes.length <= 2) {
            nodes.forEach(node => branch(parent, node, level ? 1.7 : 3, .85, 'terminal', subject.label));
            return;
          }
          const minX = Math.min(...nodes.map(n => n.x)), maxX = Math.max(...nodes.map(n => n.x));
          const minY = Math.min(...nodes.map(n => n.y)), maxY = Math.max(...nodes.map(n => n.y));
          const axis = maxX - minX > maxY - minY ? 'x' : 'y';
          const ordered = nodes.slice().sort((a, b) => a[axis] - b[axis] || a.id.localeCompare(b.id));
          const split = Math.ceil(ordered.length / 2);
          [ordered.slice(0, split), ordered.slice(split)].forEach((children, side) => {
            const average = { x: children.reduce((s, n) => s + n.x, 0) / children.length,
              y: children.reduce((s, n) => s + n.y, 0) / children.length };
            const joint = { x: parent.x + (average.x - parent.x) * .72,
              y: parent.y + (average.y - parent.y) * .72 + (side ? 2 : -2) };
            const weight = Math.max(1.6, Math.sqrt(children.length) * 1.15);
            branch(parent, joint, weight + .65, weight * .66, 'twig', subject.label);
            grow(joint, children, level + 1);
          });
        };
        grow(subject.hub, subject.nodes, 0);
        this.vesselSubjects.push({ label: subject.label, x: subject.x, y: subject.y,
          labelX: subject.x, labelY: subject.y - subject.radius - 25, radius: subject.radius,
          hub: subject.hub, count: subject.nodes.length, color: subject.nodes[0].color || rose });
      });
      this.vesselStretch = subjects.length > 1 ? { x: 1.4, y: .86 } : { x: 1, y: 1 };
      const points = new Set(this.nodes);
      this.vessels.forEach(segment => { points.add(segment.source); points.add(segment.target); });
      points.forEach(point => { point.x *= this.vesselStretch.x; point.y *= this.vesselStretch.y; });
      this.vesselSubjects.forEach(subject => {
        subject.x *= this.vesselStretch.x; subject.labelX *= this.vesselStretch.x;
        subject.y *= this.vesselStretch.y; subject.labelY *= this.vesselStretch.y;
      });
      if (this.vesselBounds) {
        this.vesselBounds.x *= this.vesselStretch.x; this.vesselBounds.w *= this.vesselStretch.x;
        this.vesselBounds.y *= this.vesselStretch.y; this.vesselBounds.h *= this.vesselStretch.y;
      }
    }

    vesselPath(branch) {
      const a = branch.source, b = branch.target;
      const dx = b.x - a.x, dy = b.y - a.y;
      const length = Math.max(1, Math.hypot(dx, dy));
      const bend = branch.kind === 'trunk' ? 8 : branch.kind === 'lobe' ? 24 : Math.min(22, length * .12);
      const sign = dx >= 0 ? 1 : -1;
      const c1 = { x: a.x + dx * .32 - dy / length * bend * sign, y: a.y + dy * .32 + dx / length * bend * sign };
      const c2 = { x: a.x + dx * .72 - dy / length * bend * sign, y: a.y + dy * .72 + dx / length * bend * sign };
      const left = [], right = [];
      for (let i = 0; i <= 16; i++) {
        const t = i / 16, u = 1 - t;
        const x = u*u*u*a.x + 3*u*u*t*c1.x + 3*u*t*t*c2.x + t*t*t*b.x;
        const y = u*u*u*a.y + 3*u*u*t*c1.y + 3*u*t*t*c2.y + t*t*t*b.y;
        const vx = 3*u*u*(c1.x-a.x) + 6*u*t*(c2.x-c1.x) + 3*t*t*(b.x-c2.x);
        const vy = 3*u*u*(c1.y-a.y) + 6*u*t*(c2.y-c1.y) + 3*t*t*(b.y-c2.y);
        const norm = Math.max(1, Math.hypot(vx, vy));
        const radius = (branch.startWidth * (1-t) + branch.endWidth * t) / 2;
        left.push([x - vy/norm*radius, y + vx/norm*radius]);
        right.push([x + vy/norm*radius, y - vx/norm*radius]);
      }
      return 'M' + left.concat(right.reverse()).map(p => p.join(',')).join('L') + 'Z';
    }

    drawVessels() {
      this.clusterLayer.selectAll('path.tau-lobe-wash').data(this.lobeShapes).enter().append('path')
        .attr('class', 'tau-lobe-wash').attr('d', d => d)
        .attr('transform', `scale(${this.vesselStretch.x},${this.vesselStretch.y})`).attr('fill', '#68809c').attr('opacity', .06);
      this.vesselSelection = this.clusterLayer.selectAll('path.tau-vessel').data(this.vessels).enter().append('path')
        .attr('class', d => 'tau-vessel tau-vessel-' + d.kind).attr('d', d => this.vesselPath(d))
        .attr('fill', d => d.color).attr('opacity', d => /trunk|lobe/.test(d.kind) ? .72 : d.kind === 'subject' ? .59 : .39);
      const captions = {
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
        'Algebra, representation theory and Lie groups': ['Algebra &', 'representations']
      };
      const titles = this.clusterLayer.selectAll('g.tau-vessel-subject').data(this.vesselSubjects).enter().append('g')
        .attr('class', 'tau-vessel-subject tau-vessel-label').attr('data-subject-label', d => d.label)
        .attr('tabindex', 0).attr('role', 'button').attr('aria-label', d => `Open ${d.label}: ${d.count} roadmaps`)
        .on('click', subject => {
          d3.event.stopPropagation();
          if (this.options.onGroupSelect) this.options.onGroupSelect(subject.label);
        })
        .on('keydown', subject => {
          if (d3.event.key !== 'Enter' && d3.event.key !== ' ') return;
          d3.event.preventDefault(); d3.event.stopPropagation();
          if (this.options.onGroupSelect) this.options.onGroupSelect(subject.label);
        });
      titles.each(function(subject) {
        const lines = captions[subject.label] || wrapText(subject.label, 21, 2);
        const g = d3.select(this);
        const width = Math.min(140, Math.max(...lines.map(line => line.length)) * 5.8 + 16);
        g.append('rect').attr('x', -width/2).attr('y', -lines.length*13+1).attr('width', width)
          .attr('height', lines.length*13+16).attr('rx', 5).attr('fill', '#111927').attr('fill-opacity', .91);
        const text = g.append('text').attr('text-anchor', 'middle').attr('fill', '#ddd5bc').attr('font-size', 11).attr('font-weight', 650);
        lines.forEach((line, i) => text.append('tspan').attr('x', 0).attr('y', -(lines.length - 1 - i)*13).text(line));
        g.append('text').attr('text-anchor', 'middle').attr('y', 12).attr('fill', '#9caaaf').attr('font-size', 8.5)
          .text(subject.count + ' roadmaps');
        g.append('title').text(subject.label + '\n' + subject.count + ' roadmaps — click to explore');
      });
      this.clusterLayer.selectAll('circle.tau-vessel-hub').data(this.vesselSubjects).enter().append('circle')
        .attr('class', 'tau-vessel-hub').attr('cx', d => d.hub.x).attr('cy', d => d.hub.y).attr('r', 4)
        .attr('fill', '#bda06c').attr('stroke', '#111927').attr('stroke-width', 1.5);
    }

    updateVesselLabels() {
      if (this.layout !== 'vessels' || !this.nodeSelection) return;
      const scale = this.transform.k || 1;
      const active = this.hoveredId || this.selectedId;
      this.clusterLayer.selectAll('.tau-vessel-subject').attr('transform', subject =>
        `translate(${subject.labelX},${subject.labelY - 10/scale}) scale(${1/scale})`);
      const occupied = [];
      this.nodeSelection.select('.tau-vessel-hit').attr('r', Math.max(11, 6 / scale));
      this.nodeSelection.each(function(node) {
        const visibleActive = node.id === active;
        const x = node.x * scale, y = node.y * scale;
        const box = { x: x + 12, y: y - 18, w: 174, h: 50 };
        const collides = occupied.some(p => box.x < p.x+p.w && box.x+box.w > p.x && box.y < p.y+p.h && box.y+box.h > p.y);
        const visible = visibleActive || (scale > .88 && !collides);
        if (visible && !visibleActive) occupied.push(box);
        d3.select(this).select('.tau-vessel-node-label')
          .attr('transform', `translate(${13/scale},${-9/scale}) scale(${1/scale})`).attr('display', visible ? null : 'none');
      });
    }

    layoutGroups() {
      const count = this.nodes.length;
      const aspect = Math.max(.8, Math.min(1.8, this.width / this.height));
      const cols = Math.max(1, Math.ceil(Math.sqrt(count * aspect * .65)));
      const gapX = 335, gapY = 174;
      this.nodes.forEach((node, index) => { node.x = (index % cols) * gapX; node.y = Math.floor(index / cols) * gapY; });
    }

    layoutClusters() {
      const groups = new Map();
      this.nodes.forEach(node => {
        const key = node.group || 'Roadmaps';
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(node);
      });
      // Deterministic packed subject blocks keep related roadmaps together without an expensive force simulation.
      const totalArea = this.nodes.length * 266 * 126 + groups.size * 48000;
      const targetWidth = Math.max(740, Math.sqrt(totalArea * Math.max(1, this.width / this.height)));
      let shelfX = 0, shelfY = 0, shelfH = 0;
      groups.forEach((nodes, label) => {
        const cols = Math.max(1, Math.min(5, Math.ceil(Math.sqrt(nodes.length * 0.8))));
        const rows = Math.ceil(nodes.length / cols);
        const w = cols * 242 + 44, h = rows * 116 + 72;
        if (shelfX && shelfX + w > targetWidth) { shelfX = 0; shelfY += shelfH + 58; shelfH = 0; }
        const x = shelfX, y = shelfY;
        this.clusters.push({ label, x: x - 128, y: y - 64, w, h, color: nodes[0].color || '#64748b' });
        nodes.forEach((node, index) => {
          node.x = x + (index % cols) * 242;
          node.y = y + 38 + Math.floor(index / cols) * 116;
        });
        shelfX += w + 58;
        shelfH = Math.max(shelfH, h);
      });
    }

    layoutLayers() {
      const ranks = new Map();
      const inferredRanks = new Map(this.nodes.map(node => [node.id, 0]));
      const indegree = new Map(this.nodes.map(node => [node.id, 0]));
      const outgoing = new Map(this.nodes.map(node => [node.id, []]));
      this.edges.forEach(edge => {
        indegree.set(edge.target.id, indegree.get(edge.target.id) + 1);
        outgoing.get(edge.source.id).push(edge.target.id);
      });
      const ready = this.nodes.filter(node => indegree.get(node.id) === 0).map(node => node.id);
      for (let index = 0; index < ready.length; index++) {
        const id = ready[index];
        outgoing.get(id).forEach(target => {
          inferredRanks.set(target, Math.max(inferredRanks.get(target), inferredRanks.get(id) + 1));
          indegree.set(target, indegree.get(target) - 1);
          if (indegree.get(target) === 0) ready.push(target);
        });
      }
      this.nodes.forEach(node => {
        const rank = Math.max(0, node.rank == null ? inferredRanks.get(node.id) : finite(node.rank, inferredRanks.get(node.id)));
        if (!ranks.has(rank)) ranks.set(rank, []);
        ranks.get(rank).push(node);
      });
      const ordered = Array.from(ranks.keys()).sort((a, b) => a - b);
      // Barycentric ordering reduces crossings while preserving deterministic data order on ties.
      const nodeOrder = new Map();
      ordered.forEach((rank, rankIndex) => {
        const nodes = ranks.get(rank);
        nodes.forEach(node => { node.w = node.type === 'stage' ? 258 : 238; node.h = 86; node.lines = 3; node.chars = 29; });
        const score = node => {
          const parents = this.edges.filter(edge => edge.target.id === node.id && nodeOrder.has(edge.source.id));
          return parents.length ? parents.reduce((sum, edge) => sum + nodeOrder.get(edge.source.id), 0) / parents.length : 0;
        };
        nodes.sort((a, b) => score(a) - score(b));
        nodes.forEach((node, index) => {
          node.y = rankIndex * 118;
          node.x = (index - (nodes.length - 1) / 2) * 296;
          nodeOrder.set(node.id, node.x);
        });
      });
    }

    draw() {
      this.clusterLayer.selectAll('*').remove();
      if (this.layout === 'vessels') this.drawVessels();
      if (this.layout === 'clusters' && this.clusters.length > 1) {
        const groups = this.clusterLayer.selectAll('g').data(this.clusters).enter().append('g');
        groups.append('rect').attr('class', 'tau-cluster').attr('x', d => d.x).attr('y', d => d.y)
          .attr('width', d => d.w).attr('height', d => d.h).attr('rx', 14);
        groups.append('text').attr('class', 'tau-cluster-title').attr('x', d => d.x + 15).attr('y', d => d.y + 26)
          .text(d => normalizeText(d.label));
      }
      this.edgeLayer.selectAll('*').remove();
      this.edgeSelection = this.edgeLayer.selectAll('path').data(this.edges).enter().append('path')
        .attr('class', 'tau-edge').attr('stroke', '#91a4b9').attr('stroke-width', 1.2)
        .attr('stroke-dasharray', edge => /declared|area|metadata/.test(edge.kind) ? '6 5' : null)
        .attr('marker-end', 'url(#' + this.id + '-arrow-normal)');
      this.nodeLayer.selectAll('*').remove();
      this.nodeSelection = this.nodeLayer.selectAll('g').data(this.nodes).enter().append('g')
        .attr('class', this.layout === 'vessels' ? 'tau-node tau-vessel-node' : 'tau-node').attr('data-node-id', node => node.id)
        .attr('data-progress', node => progressValue(node.progress))
        .style('--tau-progress-fill', node => progressValue(node.progress) === null ? null : d3.interpolateRgb('#ffffff', nodeAccent(node))(.12))
        .attr('tabindex', 0).attr('role', 'button')
        .attr('aria-label', node => normalizeText(node.label) + (node.subtitle ? '. ' + node.subtitle : '') + (progressDescription(node) ? '. ' + progressDescription(node) : '') + '. Enter selects; Shift Enter opens.')
        .on('click', node => {
          d3.event.stopPropagation();
          this.select(node.id);
          if (this.options.onSelect) this.options.onSelect(node);
        })
        .on('dblclick', node => {
          d3.event.preventDefault(); d3.event.stopPropagation();
          if (this.options.onOpen) this.options.onOpen(node);
        })
        .on('mouseenter', node => {
          if (this.layout !== 'vessels') return;
          this.hoveredId = node.id; this.applyEmphasis();
          this.nodeSelection.filter(n => n.id === node.id).raise();
        })
        .on('mouseleave', () => { if (this.layout === 'vessels') { this.hoveredId = null; this.applyEmphasis(); } })
        .on('focus', node => { if (this.layout === 'vessels') { this.hoveredId = node.id; this.applyEmphasis(); } })
        .on('blur', () => { if (this.layout === 'vessels') { this.hoveredId = null; this.applyEmphasis(); } })
        .on('keydown', node => {
          if (d3.event.key !== 'Enter' && d3.event.key !== ' ') return;
          d3.event.preventDefault(); d3.event.stopPropagation();
          this.select(node.id);
          if (d3.event.shiftKey && this.options.onOpen) this.options.onOpen(node);
          else if (this.options.onSelect) this.options.onSelect(node);
        });
      if (this.layout === 'vessels') {
        this.nodeSelection.append('circle').attr('class', 'tau-vessel-hit').attr('r', 13);
        this.nodeSelection.append('circle').attr('class', 'tau-leaf-ring').attr('r', 12);
        this.nodeSelection.append('circle').attr('class', 'tau-leaf').attr('r', node => node.radius).attr('fill', nodeAccent);
        this.nodeSelection.each(function(node) {
          const group = d3.select(this);
          const label = group.append('g').attr('class', 'tau-vessel-node-label');
          const lines = wrapText(node.label, 26, 3);
          label.append('rect').attr('x', -6).attr('y', -15).attr('width', 184).attr('height', lines.length*15+24)
            .attr('rx', 7).attr('fill', '#fffdfb').attr('stroke', '#e4d6d4').attr('fill-opacity', .97);
          const text = label.append('text');
          lines.forEach((line, i) => text.append('tspan').attr('x', 0).attr('y', i*15).text(line));
          label.append('text').attr('x', 0).attr('y', lines.length*15+7).style('font-size', '10px')
            .style('fill', nodeAccent(node)).text(progressDescription(node) || 'Click to explore');
          group.append('title').text(normalizeText(node.label) + '\n' + progressDescription(node) + '\nClick to inspect · Double-click to open');
        });
      } else {
      this.nodeSelection.append('rect').attr('class', 'tau-card')
        .attr('x', node => -node.w / 2).attr('y', node => -node.h / 2)
        .attr('width', node => node.w).attr('height', node => node.h).attr('rx', 9);
      this.nodeSelection.append('rect').attr('class', 'tau-node-accent').attr('x', node => -node.w / 2 + 1.5).attr('y', node => -node.h / 2 + 9)
        .attr('width', 4).attr('height', node => node.h - 18).attr('rx', 2).attr('fill', nodeAccent);
      this.nodeSelection.each(function (node) {
        const group = d3.select(this);
        const lines = wrapText(node.label, node.chars, node.lines);
        const hasProgress = !!progressLabel(node);
        const hasSubtitle = !!node.subtitle || hasProgress;
        const lineHeight = node.font + 3;
        const startY = -(lines.length - 1) * lineHeight / 2 + (hasSubtitle ? -7 : 4);
        const title = group.append('text').attr('class', 'tau-node-title').attr('font-size', node.font)
          .attr('x', -node.w / 2 + 17).attr('y', startY);
        lines.forEach((line, index) => title.append('tspan').attr('x', -node.w / 2 + 17).attr('dy', index ? lineHeight : 0).text(line));
        if (node.subtitle) group.append('text').attr('class', 'tau-node-subtitle')
          .attr('x', -node.w / 2 + 17).attr('y', node.h / 2 - 11)
          .text(wrapText(node.subtitle, Math.floor((node.w - (hasProgress ? Math.min(node.w / 2, Math.max(42, progressLabel(node).length * 6.1)) + 44 : 30)) / 5.8), 1)[0]);
        if (hasProgress) group.append('text').attr('class', 'tau-node-progress')
          .attr('x', node.w / 2 - 13).attr('y', node.h / 2 - 11).attr('text-anchor', 'end')
          .attr('fill', nodeAccent(node)).text(progressLabel(node));
        group.append('title').text(normalizeText(node.label) + (node.subtitle ? '\n' + node.subtitle : '') + (hasProgress ? '\n' + progressDescription(node) : '') + '\nClick to inspect · Double-click to open');
      });
      }
      const drag = d3.drag().filter(() => !d3.event.button)
        .on('start', () => { if (d3.event.sourceEvent) d3.event.sourceEvent.stopPropagation(); })
        .on('drag', node => {
          node.x += d3.event.dx; node.y += d3.event.dy;
          this.updatePositions();
        });
      this.nodeSelection.call(drag);
      this.updatePositions();
    }

    edgePath(edge) {
      const a = edge.source, b = edge.target;
      const dx = b.x - a.x, dy = b.y - a.y;
      // Clip endpoints to card borders so arrowheads remain visible at every zoom level.
      const clip = (node, vx, vy, padding) => {
        const f = Math.min((node.w / 2 + padding) / Math.max(Math.abs(vx), .001), (node.h / 2 + padding) / Math.max(Math.abs(vy), .001));
        return [node.x + vx * f, node.y + vy * f];
      };
      const lengthForClip = Math.max(1, Math.hypot(dx, dy));
      const start = this.layout === 'vessels' ? [a.x + dx/lengthForClip*11, a.y + dy/lengthForClip*11] : clip(a, dx, dy, 2);
      const end = this.layout === 'vessels' ? [b.x - dx/lengthForClip*13, b.y - dy/lengthForClip*13] : clip(b, -dx, -dy, 4);
      if (this.layout === 'layers' && dy > 0) {
        const sy = a.y + a.h / 2 + 2, ty = b.y - b.h / 2 - 4;
        const middle = (sy + ty) / 2;
        return `M${a.x},${sy}C${a.x},${middle} ${b.x},${middle} ${b.x},${ty}`;
      }
      const bend = Math.min(45, Math.sqrt(dx * dx + dy * dy) * .075);
      const length = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const mx = (start[0] + end[0]) / 2 - dy / length * bend;
      const my = (start[1] + end[1]) / 2 + dx / length * bend;
      return `M${start[0]},${start[1]}Q${mx},${my} ${end[0]},${end[1]}`;
    }

    updatePositions() {
      this.nodeSelection.attr('transform', node => 'translate(' + node.x + ',' + node.y + ')');
      this.edgeSelection.attr('d', edge => this.edgePath(edge));
      if (this.layout === 'vessels' && this.vesselSelection) this.vesselSelection.attr('d', branch => this.vesselPath(branch));
      this.updateVesselLabels();
    }

    select(id) {
      this.selectedId = this.nodeMap.has(id) ? id : null;
      return this.applyEmphasis();
    }

    applyEmphasis() {
      const selected = this.layout === 'vessels' ? (this.hoveredId || this.selectedId) : this.selectedId;
      const neighbors = new Set();
      this.edges.forEach(edge => {
        if (edge.source.id === selected) neighbors.add(edge.target.id);
        if (edge.target.id === selected) neighbors.add(edge.source.id);
      });
      if (!this.nodeSelection) return this;
      this.nodeSelection.classed('is-selected', node => node.id === this.selectedId)
        .classed('is-hovered', node => node.id === this.hoveredId)
        .classed('is-neighbor', node => neighbors.has(node.id))
        .attr('aria-pressed', node => node.id === this.selectedId ? 'true' : 'false')
        .attr('opacity', node => !selected || node.id === selected || neighbors.has(node.id) ? 1 : this.layout === 'vessels' ? .6 : .48);
      this.edgeSelection.attr('opacity', edge => selected ? (edge.source.id === selected || edge.target.id === selected ? .86 : this.layout === 'vessels' ? 0 : .055) : (this.layout === 'vessels' ? 0 : this.edges.length > 150 ? .19 : .43))
        .attr('stroke', edge => edge.source.id === selected || edge.target.id === selected ? '#2668ad' : '#91a4b9')
        .attr('stroke-width', edge => edge.source.id === selected || edge.target.id === selected ? 2.4 : 1.2)
        .attr('marker-end', edge => 'url(#' + this.id + '-arrow-' + (edge.source.id === selected || edge.target.id === selected ? 'highlight' : 'normal') + ')');
      this.edgeSelection.filter(edge => edge.source.id === selected || edge.target.id === selected).raise();
      if (this.layout === 'vessels' && selected) this.nodeSelection.filter(node => node.id === selected).raise();
      this.updateVesselLabels();
      return this;
    }

    bounds() {
      if (!this.nodes.length) return { x: 0, y: 0, w: 100, h: 100 };
      let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
      this.nodes.forEach(node => { left = Math.min(left, node.x - node.w / 2); right = Math.max(right, node.x + node.w / 2); top = Math.min(top, node.y - node.h / 2); bottom = Math.max(bottom, node.y + node.h / 2); });
      if (this.layout === 'vessels') {
        this.vessels.forEach(branch => { [branch.source, branch.target].forEach(p => {left = Math.min(left,p.x-25);right = Math.max(right,p.x+25);top = Math.min(top,p.y-25);bottom = Math.max(bottom,p.y+25);}); });
        this.vesselSubjects.forEach(group => {left = Math.min(left,group.labelX-145);right=Math.max(right,group.labelX+145);top=Math.min(top,group.labelY-70);bottom=Math.max(bottom,group.labelY+30);});
        if (this.vesselBounds) {left=Math.min(left,this.vesselBounds.x);right=Math.max(right,this.vesselBounds.x+this.vesselBounds.w);top=Math.min(top,this.vesselBounds.y);bottom=Math.max(bottom,this.vesselBounds.y+this.vesselBounds.h);}
      }
      this.clusters.forEach(group => { left = Math.min(left, group.x); right = Math.max(right, group.x + group.w); top = Math.min(top, group.y); bottom = Math.max(bottom, group.y + group.h); });
      return { x: left - 30, y: top - 30, w: right - left + 60, h: bottom - top + 60 };
    }

    fit(animate) {
      if (animate === undefined) animate = true;
      const box = this.bounds();
      const scale = Math.max(.025, Math.min(1.15, (this.width - 36) / box.w, (this.height - 36) / box.h));
      const transform = d3.zoomIdentity.translate(this.width / 2 - (box.x + box.w / 2) * scale, this.height / 2 - (box.y + box.h / 2) * scale).scale(scale);
      if (animate) this.svg.transition().duration(260).call(this.zoom.transform, transform);
      else this.svg.call(this.zoom.transform, transform);
      return this;
    }

    focus(id) {
      const node = this.nodeMap.get(id);
      if (!node) return this;
      this.select(id);
      const scale = Math.max(.65, Math.min(1.4, this.transform.k));
      const transform = d3.zoomIdentity.translate(this.width / 2 - node.x * scale, this.height / 2 - node.y * scale).scale(scale);
      this.svg.transition().duration(280).call(this.zoom.transform, transform);
      return this;
    }

    zoomIn() { this.svg.transition().duration(180).call(this.zoom.scaleBy, 1.4); return this; }
    zoomOut() { this.svg.transition().duration(180).call(this.zoom.scaleBy, 1 / 1.4); return this; }

    setProgress(values) {
      const progress = values instanceof Map ? values : new Map(Object.entries(values || {}));
      progress.forEach((value, id) => {
        if (!this.nodeMap.has(id)) return;
        const node = this.nodeMap.get(id);
        if (value && typeof value === 'object') {
          node.progress = value.progress;
          node.progressLabel = value.progressLabel;
        } else node.progress = value;
      });
      this.draw();
      this.select(this.selectedId);
      return this;
    }

    static progressColor(value) { return progressColor(value); }

    exportSVG() {
      const source = this.svg.node();
      const clone = source.cloneNode(true);
      const box = this.bounds();
      // Visible labels can extend past their node, especially after zooming out.
      // getBBox is in the viewport's own coordinates, before its pan/zoom matrix.
      try {
        const visible = this.viewport.node().getBBox();
        const left = Math.min(box.x, visible.x - 18), top = Math.min(box.y, visible.y - 18);
        const right = Math.max(box.x + box.w, visible.x + visible.width + 18);
        const bottom = Math.max(box.y + box.h, visible.y + visible.height + 18);
        Object.assign(box, { x: left, y: top, w: right - left, h: bottom - top });
      } catch (_) { /* Empty or detached SVG: the mathematical layout bounds suffice. */ }

      // Resolve the actual cascade while the source is still inside the app.
      // This captures Voyager's CSS overrides, fonts and custom-property values
      // without exporting any HTML rules, external sheets or font dependencies.
      const presentation = ['color', 'fill', 'fill-opacity', 'fill-rule',
        'stroke', 'stroke-width', 'stroke-opacity', 'stroke-dasharray',
        'stroke-dashoffset', 'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit',
        'opacity', 'font-family', 'font-size', 'font-style', 'font-weight',
        'font-variant', 'letter-spacing', 'word-spacing', 'text-anchor',
        'dominant-baseline', 'text-decoration', 'paint-order', 'vector-effect',
        'visibility', 'display', 'rx', 'ry'];
      const originals = [source, ...source.querySelectorAll('*')];
      const copies = [clone, ...clone.querySelectorAll('*')];
      originals.forEach((element, index) => {
        const copy = copies[index];
        const tag = element.tagName.toLowerCase();
        if (['style', 'title', 'desc', 'defs'].includes(tag)) return;
        const computed = window.getComputedStyle(element);
        copy.removeAttribute('style');
        presentation.forEach(property => {
          let value = computed.getPropertyValue(property);
          if (!value || value === 'auto' || value === 'normal' && ['letter-spacing', 'word-spacing'].includes(property)) return;
          // SVG paints can be returned as an absolute URL by getComputedStyle.
          // Keep local defs local when the exported file receives a new URL.
          if (/url\(/.test(value)) {
            const fragment = value.match(/#([^"')]+)["']?\)/);
            if (!fragment || !source.querySelector('[id="' + fragment[1].replace(/"/g, '') + '"]')) return;
            value = 'url(#' + fragment[1] + ')';
          }
          copy.style.setProperty(property, value, 'important');
        });
        copy.removeAttribute('tabindex');
        if (copy.getAttribute('role') === 'button') copy.removeAttribute('role');
        copy.removeAttribute('aria-pressed');
        if (copy.hasAttribute('aria-label')) copy.setAttribute('aria-label', copy.getAttribute('aria-label').replace(/\. Enter selects; Shift Enter opens\.$/, ''));
      });
      clone.querySelectorAll('style').forEach(style => style.remove());
      clone.querySelectorAll('.tau-node > title').forEach(title => {
        title.textContent = title.textContent.replace(/\nClick to inspect · Double-click to open$/, '');
      });

      let background = null;
      for (let element = source; element && !background; element = element.parentElement) {
        const color = window.getComputedStyle(element).backgroundColor;
        const channels = color.match(/^rgba?\(([^)]+)\)$/);
        const parts = channels ? channels[1].split(/[, /]+/).filter(Boolean) : [];
        if (color && color !== 'transparent' && (!parts.length || parts.length < 4 || Number(parts[3]) > 0)) background = color;
      }
      background = background || (this.layout === 'vessels' ? '#111927' : '#f8fafc');
      const backdrop = document.createElementNS(SVG_NS, 'rect');
      backdrop.setAttribute('class', 'tau-export-background');
      ['x', 'y'].forEach(key => backdrop.setAttribute(key, box[key]));
      backdrop.setAttribute('width', box.w); backdrop.setAttribute('height', box.h);
      backdrop.setAttribute('fill', background);
      clone.insertBefore(backdrop, clone.querySelector('.tau-viewport'));
      clone.setAttribute('xmlns', SVG_NS);
      clone.setAttribute('width', Math.ceil(box.w)); clone.setAttribute('height', Math.ceil(box.h));
      clone.setAttribute('viewBox', [box.x, box.y, box.w, box.h].join(' '));
      clone.setAttribute('role', 'img'); clone.setAttribute('aria-label', 'Tau Ceti roadmap graph');
      clone.style.setProperty('background-color', background);
      clone.querySelector('.tau-viewport').removeAttribute('transform');
      return '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(clone);
    }

    debugState() {
      return { nodes: this.nodes.length, edges: this.edges.length, vesselBranches: this.vessels.length, vesselSubjects: this.vesselSubjects.length,
        branches: this.vessels.map(b => ({kind:b.kind,group:b.group,source:{x:b.source.x,y:b.source.y},target:{x:b.target.x,y:b.target.y},startWidth:b.startWidth,endWidth:b.endWidth})), layout: this.layout, selectedId: this.selectedId,
        width: this.width, height: this.height, transform: { x: this.transform.x, y: this.transform.y, k: this.transform.k },
        positions: this.nodes.map(node => ({ id: node.id, x: node.x, y: node.y, w: node.w, h: node.h, progress: progressValue(node.progress), accent: nodeAccent(node) })) };
    }

    destroy() {
      this.destroyed = true;
      if (this.observer) this.observer.disconnect();
      else window.removeEventListener('resize', this.resize);
      this.svg.interrupt().on('.zoom', null).remove();
    }
  }
  window.TauGraph = TauGraph;
})();
