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
      this.clusters = []; this.constellationLinks = []; this.constellationSubjects = [];
      this.nodeMap = new Map();
      this.selectedId = null;
      this.transform = d3.zoomIdentity;
      this.destroyed = false;
      this.semantic={fitScale:1,diveThreshold:2.35,ascendThreshold:.68,busy:false,lastAction:null};
      this.isCoarse=!!(window.matchMedia&&window.matchMedia('(pointer: coarse)').matches);
      this.travelTimer=null;this.semanticReadyAt=0;this.canAscend=false;
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
        .tau-graph .tau-constellation-link, .tau-graph .tau-chart-field { pointer-events: none; }
        .tau-graph .tau-constellation-subject { cursor: pointer; outline: none; }
        .tau-graph .tau-constellation-subject:hover rect, .tau-graph .tau-constellation-subject:focus rect { stroke: #bda06c; stroke-width: 1; }
        .tau-graph .tau-star-halo, .tau-graph .tau-star-ring, .tau-graph .tau-star-core, .tau-graph .tau-star-spark, .tau-graph .tau-space-art, .tau-graph .tau-orbit-path { pointer-events: none; }
        .tau-graph .tau-space-art * { pointer-events: none; }
        .tau-graph .tau-galaxy-core, .tau-graph .tau-stellar-core, .tau-graph .tau-planet-body { stroke: none; }
        .tau-graph .tau-orbit-path { fill:none; stroke:#71849c; stroke-width:.8; opacity:.29; }
        .tau-graph .tau-planet-node .tau-star-ring { opacity:.18; }
        .tau-graph .tau-planet-node.is-selected .tau-star-ring { opacity:1; }
        .tau-graph .tau-star-core { stroke: #eddfd2; stroke-width: .45; }
        .tau-graph .tau-star-halo { opacity: .13; }
        .tau-graph .tau-star-spark { fill: #fff4dc; opacity: .9; }
        .tau-graph .tau-node.is-selected .tau-star-ring, .tau-graph .tau-node.is-hovered .tau-star-ring, .tau-graph .tau-node:focus .tau-star-ring { stroke: #dfc48e; stroke-width: 1.7; opacity: 1; }
        .tau-graph .tau-star-ring { fill: none; stroke-width: .7; opacity: .5; }
        .tau-graph .tau-star-hit { fill: transparent; pointer-events: all; }
        .tau-graph .tau-star-node-label { pointer-events: none; }
        .tau-graph .tau-stage-label rect { pointer-events: all; cursor: pointer; }
        .tau-graph .tau-caption-leader, .tau-graph .tau-node-label-leader { fill: none; stroke: #8396a8; opacity: .45; pointer-events: none; }
        .tau-graph .tau-reference-edge { stroke-dasharray: 2 6; }
        .tau-graph .tau-star-node-label text { fill: #e5e5dc; font-size: 12px; font-weight: 600; }
        .tau-graph .tau-cluster-title { fill: #61728a; font-size: 15px; font-weight: 600; }
      `);
      const defs = this.svg.append('defs');
      const radial=(name,stops,extra={})=>{
        const gradient=defs.append('radialGradient').attr('id',this.id+'-'+name);
        Object.entries(extra).forEach(([key,value])=>gradient.attr(key,value));
        stops.forEach(([offset,color,opacity])=>gradient.append('stop').attr('offset',offset).attr('stop-color',color).attr('stop-opacity',opacity));
      };
      radial('galaxy-glow',[[0,'#fff2da',.72],[.14,'#dccbbb',.48],[.42,'#778cab',.19],[1,'#425671',0]]);
      radial('galaxy-disk',[[0,'#fff9e8',1],[.13,'#efd6b6',.91],[.37,'#a9a5ad',.54],[.72,'#66809f',.14],[1,'#425671',0]]);
      radial('galaxy-disk-cool',[[0,'#f5f4ff',1],[.13,'#cad7ed',.91],[.37,'#8a9fc7',.54],[.72,'#496f9e',.14],[1,'#334768',0]]);
      radial('galaxy-disk-warm',[[0,'#fff3d6',1],[.13,'#ecd0a9',.91],[.37,'#b09a8e',.54],[.72,'#876b81',.14],[1,'#59465b',0]]);
      radial('stellar-light',[[0,'#fffdf4',1],[.22,'#fff6d3',1],[.48,'#f0c884',.82],[1,'#b97742',.14]]);
      radial('stellar-glow',[[0,'#fff3d0',.65],[.12,'#eacb95',.26],[.4,'#cf9b62',.07],[1,'#a27e5d',0]]);
      radial('nebula-blue',[[0,'#46688d',.19],[.35,'#29496a',.08],[1,'#112034',0]]);
      radial('nebula-dust',[[0,'#9a7763',.13],[.5,'#67556a',.035],[1,'#142132',0]]);
      radial('planet-definition',[[0,'#e0eee3',1],[.3,'#90bdbe',1],[.68,'#446d83',1],[1,'#16233b',1]],{cx:'29%',cy:'26%',r:'75%'});
      radial('planet-theorem',[[0,'#f4dcc0',1],[.32,'#cfa084',1],[.7,'#87595b',1],[1,'#281d31',1]],{cx:'29%',cy:'26%',r:'75%'});
      radial('planet-construction',[[0,'#e0e8f4',1],[.33,'#91aaca',1],[.7,'#4b658e',1],[1,'#1d2947',1]],{cx:'29%',cy:'26%',r:'75%'});

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
      this.zoom = d3.zoom().scaleExtent([0.025, 8]).clickDistance(6)
        .filter(() => !this.semantic.busy && !d3.event.button && (!d3.event.ctrlKey || d3.event.type === 'wheel'))
        .on('zoom', () => {
          this.transform = d3.event.transform;
          this.viewport.attr('transform', this.transform);
          this.updateConstellationLabels();
          this.handleSemanticZoom(d3.event.sourceEvent);
        });
      this.svg.call(this.zoom).on('dblclick.zoom', null);
      this.svg.on('click.background', () => {
        if (d3.event.target === this.svg.node()) this.select(null);
      });
      this.resize = () => {
        if (this.destroyed) return;
        const box = this.container.getBoundingClientRect();
        const previousWidth=this.width,previousHeight=this.height;
        this.width = Math.max(160, box.width || 800);
        this.height = Math.max(160, box.height || 600);
        this.svg.attr('viewBox', '0 0 ' + this.width + ' ' + this.height);
        this.zoom.extent([[0, 0], [this.width, this.height]]);
        if (this.awaitingFit && box.width > 0 && box.height > 0) { this.awaitingFit = false; this.fit(false); }
        else if(this.nodes.length&&!this.semantic.busy&&previousWidth&&previousHeight&&(Math.abs(this.width/previousWidth-1)>.2||Math.abs(this.height/previousHeight-1)>.2))this.fit(false);
        else this.updateConstellationLabels();
      };
      this.resize();
      if (window.ResizeObserver) { this.observer = new ResizeObserver(this.resize); this.observer.observe(container); }
      else window.addEventListener('resize', this.resize);
    }

    setData(data, settings) {
      settings = settings || {};
      this.layout = settings.layout || 'clusters';
      this.svg.interrupt();
      const currentBox=this.container.getBoundingClientRect();
      this.width=Math.max(160,currentBox.width||this.width||800);this.height=Math.max(160,currentBox.height||this.height||600);
      this.svg.attr('viewBox',`0 0 ${this.width} ${this.height}`);this.zoom.extent([[0,0],[this.width,this.height]]);
      clearTimeout(this.travelTimer);this.travelTimer=null;
      this.canAscend=!!settings.canAscend;
      this.semantic.busy=false;this.semanticReadyAt=Date.now()+400;
      this.semanticParentCamera=null;this.orbits=[];
      this.nodes = (data.nodes || []).map(node => Object.assign({}, node, dimensions(node)));
      this.nodeMap = new Map(this.nodes.map(node => [node.id, node]));
      this.edges = (data.edges || []).map((edge, index) => ({
        source: this.nodeMap.get(typeof edge.source === 'object' ? edge.source.id : edge.source),
        target: this.nodeMap.get(typeof edge.target === 'object' ? edge.target.id : edge.target),
        kind: edge.kind || 'stage', weight: Math.max(1, finite(edge.stageCount, 1)), id: index
      })).filter(edge => edge.source && edge.target && edge.source !== edge.target);
      this.relatedEdges = (data.relatedEdges || []).map(edge => ({ source: this.nodeMap.get(edge.source), target: this.nodeMap.get(edge.target), kind: 'reference', weight: .2 })).filter(edge => edge.source && edge.target);
      this.groupConnections = [];
      this.clusters = [];
      this.constellationLinks = []; this.constellationSubjects = []; this.constellationBounds = null; this.hoveredId = null; this.subjectLeaders = null;
      this.isSkyLayout = ['constellations', 'layer-constellations', 'solar-system'].includes(this.layout);
      this.svg.classed('tau-constellations-layout', this.layout === 'constellations')
        .classed('tau-layer-constellations-layout', this.layout === 'layer-constellations')
        .classed('tau-solar-system-layout',this.layout==='solar-system').attr('data-layout', this.layout)
        .style('background', this.isSkyLayout ? '#050a14' : '#f8fafc');
      if (this.layout === 'constellations') this.layoutConstellations();
      else if (this.layout === 'layer-constellations') this.layoutLayerConstellations();
      else if (this.layout === 'solar-system') this.layoutSolarSystem();
      else if (this.layout === 'layers') this.layoutLayers();
      else if (this.layout === 'groups') this.layoutGroups();
      else this.layoutClusters();
      this.draw();
      this.select(settings.selectedId == null ? null : settings.selectedId);
      this.awaitingFit = true;
      this.resize();
      return this;
    }

    layoutConstellations() {
      const grouped = new Map();
      this.nodes.forEach(node => {
        const label = node.group || 'Roadmaps';
        if (!grouped.has(label)) grouped.set(label, []);
        grouped.get(label).push(node);
        Object.assign(node, { w: 74, h: 54, radius: 13, font: 13 });
      });
      // Fixed chart coordinates preserve a subject's location when filters change.
      // Their asymmetric arrangement leaves clear spaces between constellations.
      const sectors = {
        'Shared foundations': [-940, -240],
        'Classical, analytic and computational number theory': [-505, -370],
        'Arithmetic geometry and Diophantine methods': [-70, -310],
        'Modular, Shimura and Galois theory': [380, -195],
        'General automorphic theory': [835, -340],
        'Diamonds and geometric Langlands': [760, 100],
        'Cohomology and nonarchimedean geometry': [-235, 70],
        'K-theory, motives, periods and Habiro': [225, 205],
        'Iwasawa, Euler systems and BSD': [680, 515],
        'Function fields and higher local fields': [-20, 505],
        'Analysis, probability and PDE': [-995, 350],
        'Topology, manifolds and Floer theory': [-530, 475],
        'Algebra, representation theory and Lie groups': [-680, 105],
        'Differential and complex geometry': [-1100, 650],
        'Combinatorics and discrete structures': [-650, -650],
        'Computation, optimization and control': [-1320, 50],
        'Logic and foundations': [-1100, -550]
      };
      const hash = text => Array.from(text).reduce((seed, character) => ((seed * 31 + character.charCodeAt(0)) >>> 0), 7);
      const subjects = Array.from(grouped, ([label, nodes]) => ({ label, nodes: nodes.sort((a, b) => a.id.localeCompare(b.id)) }));
      subjects.sort((a, b) => a.label.localeCompare(b.label));
      const subjectMap = new Map(subjects.map(subject => [subject.label, subject]));
      const connections = new Map();
      this.edges.filter(edge => edge.kind !== 'reference' || !this.relatedEdges.length).concat(this.relatedEdges).forEach(edge => {
        const a = edge.source.group || 'Roadmaps', b = edge.target.group || 'Roadmaps';
        if (a === b || !subjectMap.has(a) || !subjectMap.has(b)) return;
        const pair = [a, b].sort(), key = pair.join('\n');
        if (!connections.has(key)) connections.set(key, { source: pair[0], target: pair[1], dependencies: 0, references: 0, weight: 0 });
        const link = connections.get(key);
        if (edge.kind === 'reference') { link.references++; link.weight += .2; }
        else { link.dependencies++; link.weight += Math.sqrt(edge.weight); }
      });
      this.groupConnections = Array.from(connections.values());
      subjects.forEach((subject, index) => {
        const angle = index * Math.PI * (3 - Math.sqrt(5));
        const seed = subjects.length === 1 ? [0, 0] : sectors[subject.label] || [Math.cos(angle) * 790, Math.sin(angle) * 420];
        Object.assign(subject, { x: seed[0], y: seed[1], seedX: seed[0], seedY: seed[1], radius: Math.max(54, Math.sqrt(subject.nodes.length) * 34) });
      });
      // A bounded spring relaxation brings areas with more mathematical links
      // closer, while the anchor force keeps a stable navigable subject atlas.
      // Collision spacing reserves room for both stars and screen-sized labels.
      for (let step = 0; step < 160; step++) {
        const forces = new Map(subjects.map(subject => [subject.label, { x: (subject.seedX-subject.x)*.035, y: (subject.seedY-subject.y)*.035 }]));
        this.groupConnections.forEach(link => {
          const a = subjectMap.get(link.source), b = subjectMap.get(link.target);
          const dx = b.x-a.x, dy = b.y-a.y, length = Math.max(1, Math.hypot(dx, dy));
          const strength = Math.min(.024, Math.log1p(link.weight)*.005);
          const pull = Math.max(0, length - 490) * strength;
          forces.get(a.label).x += dx/length*pull; forces.get(a.label).y += dy/length*pull;
          forces.get(b.label).x -= dx/length*pull; forces.get(b.label).y -= dy/length*pull;
        });
        subjects.forEach((a, i) => subjects.slice(i+1).forEach(b => {
          const dx = b.x-a.x, dy = (b.y-a.y)*1.16, length = Math.max(1, Math.hypot(dx, dy));
          const clearance = Math.max(390, a.radius+b.radius+140);
          const push = Math.max(0, clearance-length)*.2;
          forces.get(a.label).x -= dx/length*push; forces.get(a.label).y -= dy/length*push;
          forces.get(b.label).x += dx/length*push; forces.get(b.label).y += dy/length*push;
        }));
        subjects.forEach(subject => { subject.x += forces.get(subject.label).x; subject.y += forces.get(subject.label).y; });
      }
      const adjacency = new Set();
      this.edges.forEach(edge => { if (edge.kind !== 'reference') adjacency.add([edge.source.id, edge.target.id].sort().join('\n')); });
      subjects.forEach((subject, subjectIndex) => {
        const seed = hash(subject.label);
        const slot = [subject.x, subject.y];
        const radius = Math.max(54, Math.sqrt(subject.nodes.length) * 34);
        const rotation = (seed % 360) * Math.PI / 180;
        const stretch = .86 + (seed % 5) * .045;
        subject.nodes.forEach((node, index) => {
          const angle = index * Math.PI * (3 - Math.sqrt(5)) + rotation;
          const distance = subject.nodes.length === 1 ? 0 : radius * Math.sqrt((index + .45) / subject.nodes.length);
          const wobble = .91 + (hash(node.id) % 17) / 100;
          node.x = slot[0] + Math.cos(angle) * distance * wobble * 1.15;
          node.y = slot[1] + Math.sin(angle) * distance * wobble * stretch;
          node.constellationGroup = subject.label;
        });
        // A minimum spanning tree makes one readable geometric asterism per area.
        // These undirected lines group the chart; real proof dependencies remain
        // in the separate edge layer and are revealed by node selection.
        const connected = new Set(subject.nodes.slice(0, 1));
        const pending = new Set(subject.nodes.slice(1));
        while (pending.size) {
          let nearest = null, minimum = Infinity;
          connected.forEach(source => pending.forEach(target => {
            const sourceEdge = adjacency.has([source.id, target.id].sort().join('\n'));
            const distance = Math.hypot(source.x - target.x, source.y - target.y) * (sourceEdge ? .2 : 1);
            if (distance < minimum) { minimum = distance; nearest = { source, target, group: subject.label, sourceEdge }; }
          }));
          this.constellationLinks.push(nearest);
          connected.add(nearest.target); pending.delete(nearest.target);
        }
        const minY = Math.min(...subject.nodes.map(node => node.y));
        this.constellationSubjects.push({ label: subject.label, x: slot[0], y: slot[1],
          labelX: slot[0], labelY: minY - 31, radius, count: subject.nodes.length,
          color: subject.nodes[0].color || '#9aabc1' });
      });
      if (subjects.length > 1) {
        this.nodes.forEach(node => { node.x *= 1.25; node.y *= .9; });
        this.constellationSubjects.forEach(subject => { subject.x *= 1.25; subject.labelX *= 1.25; subject.y *= .9; subject.labelY *= .9; });
        const left = Math.min(...this.nodes.map(node => node.x)) - 75, top = Math.min(...this.nodes.map(node => node.y)) - 150;
        this.constellationBounds = { x: left, y: top, w: Math.max(...this.nodes.map(node => node.x)) - left + 75, h: Math.max(...this.nodes.map(node => node.y)) - top + 75 };
      }
    }

    constellationPath(link) {
      return `M${link.source.x},${link.source.y}L${link.target.x},${link.target.y}`;
    }

    drawConstellations() {
      const field = this.clusterLayer.append('g').attr('class', 'tau-chart-field').attr('aria-hidden', 'true');
      if (this.constellationSubjects.length > 1) {
        // Quiet reference arcs and fixed background stars give the map the texture
        // of a celestial chart without motion, image assets or filter effects.
        field.append('path').attr('class', 'tau-chart-orbit')
          .attr('d', 'M-1110,370C-680,-490 360,-735 1050,-145').attr('fill', 'none')
          .attr('stroke', '#72859e').attr('stroke-width', .8).attr('stroke-dasharray', '3 13').attr('opacity', .19);
        field.append('path').attr('class', 'tau-chart-orbit')
          .attr('d', 'M-1040,535C-380,830 525,640 1035,-400').attr('fill', 'none')
          .attr('stroke', '#72859e').attr('stroke-width', .8).attr('stroke-dasharray', '3 13').attr('opacity', .14);
        const stars = Array.from({ length: 74 }, (_, index) => ({
          x: -1080 + ((index * 613 + 179) % 2117),
          y: -540 + ((index * 347 + 67) % 1181),
          r: index % 11 === 0 ? 1.4 : .8,
          opacity: index % 7 === 0 ? .42 : .2
        }));
        field.selectAll('circle').data(stars).enter().append('circle').attr('class', 'tau-chart-star')
          .attr('cx', star => star.x).attr('cy', star => star.y).attr('r', star => star.r)
          .attr('fill', '#a9bad2').attr('opacity', star => star.opacity);
      }
      this.constellationSelection = this.clusterLayer.selectAll('path.tau-constellation-link').data(this.constellationLinks).enter().append('path')
        .attr('class', link => 'tau-constellation-link' + (link.sourceEdge ? ' is-mathematical' : ' is-grouping'))
        .attr('data-source-edge', link => link.sourceEdge ? 'true' : 'false').attr('d', link => this.constellationPath(link))
        .attr('fill', 'none').attr('stroke', '#70869e').attr('stroke-width', 1.25)
        .attr('stroke-dasharray', link => link.sourceEdge ? null : '2 8').attr('opacity', 0);
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
      this.subjectLeaders = this.clusterLayer.append('g').attr('aria-hidden', 'true').selectAll('path').data(this.constellationSubjects).enter().append('path').attr('class', 'tau-caption-leader');
      const titles = this.clusterLayer.selectAll('g.tau-constellation-subject').data(this.constellationSubjects).enter().append('g')
        .attr('class', 'tau-constellation-subject tau-constellation-label').attr('data-subject-label', subject => subject.label)
        .attr('tabindex', 0).attr('role', 'button').attr('aria-label', subject => `Open ${subject.label}: ${subject.count} roadmaps`)
        .on('click', subject => {
          d3.event.stopPropagation();
          if (this.options.onGroupSelect) this.options.onGroupSelect(subject.label);
        })
        .on('keydown', subject => {
          if (d3.event.key !== 'Enter' && d3.event.key !== ' ') return;
          d3.event.preventDefault(); d3.event.stopPropagation();
          if (this.options.onGroupSelect) this.options.onGroupSelect(subject.label);
        });
      const thisGraph=this;
      titles.each(function(subject) {
        const members=thisGraph.nodes.filter(n=>n.group===subject.label),planned=members.filter(n=>n.unmapped).length;subject.captionCount=(members.length-planned)+' roadmaps'+(planned?' · '+planned+' unmapped':'');
        const lines = captions[subject.label] || wrapText(subject.label, 21, 2);
        subject.captionLines = lines; subject.captionMode = null;
        const g = d3.select(this).attr('aria-label', `Open ${subject.label}: ${subject.captionCount}`);
        const width = Math.max(...lines.map(line => line.length)) * 6 + 18;
        g.append('rect').attr('x', -width/2).attr('y', -lines.length*13+1).attr('width', width)
          .attr('height', lines.length*13+18).attr('rx', 3).attr('fill', '#0d1728').attr('fill-opacity', .88);
        const title = g.append('text').attr('text-anchor', 'middle').attr('fill', '#e1dfd3').attr('font-size', 11).attr('font-weight', 600);
        lines.forEach((line, index) => title.append('tspan').attr('x', 0).attr('y', -(lines.length - 1 - index)*13).text(line));
        g.append('text').attr('class', 'tau-constellation-count').attr('text-anchor', 'middle').attr('y', 13)
          .attr('fill', '#8c9db3').attr('font-size', 8.5).text(subject.captionCount || subject.count + ' roadmaps');
        g.append('title').text(subject.label + '\n' + subject.captionCount + ' — click to explore');
      });
    }

    labelPlacement(preferred, occupied, exhaustive) {
      const gap = 5, margin = 8;
      const inside = box => ({ x: Math.max(margin, Math.min(this.width-box.w-margin, box.x)),
        y: Math.max(margin, Math.min(this.height-box.h-margin, box.y)), w: box.w, h: box.h });
      const overlap = (a, b) => Math.max(0, Math.min(a.x+a.w+gap,b.x+b.w+gap)-Math.max(a.x,b.x)) *
        Math.max(0, Math.min(a.y+a.h+gap,b.y+b.h+gap)-Math.max(a.y,b.y));
      const candidates = [];
      const add = (dx, dy) => candidates.push(inside({ ...preferred, x: preferred.x+dx, y: preferred.y+dy }));
      add(0,0);
      for (let ring=1; ring<=(exhaustive ? 4 : 1); ring++) {
        const dx=(preferred.w*.55+8)*ring, dy=(preferred.h+8)*ring;
        [[0,-dy],[-dx,0],[dx,0],[0,dy],[-dx,-dy],[dx,-dy],[-dx,dy],[dx,dy]].forEach(([x,y])=>add(x,y));
      }
      if (exhaustive) {
        for (let y=margin; y+preferred.h<=this.height-margin; y+=preferred.h+gap) {
          for (let x=margin; x+preferred.w<=this.width-margin; x+=Math.max(35,preferred.w*.5)) candidates.push({...preferred,x,y});
        }
      }
      let best=null, score=Infinity;
      candidates.forEach(box => {
        // Captions must never cover a node's clickable core, even when the
        // available space forces a compromise between two text labels.
        if(occupied.some(other=>other.core&&overlap(box,other)>0))return;
        const overlaps=occupied.reduce((sum,other)=>sum+overlap(box,other),0);
        const distance=Math.hypot(box.x-preferred.x,box.y-preferred.y);
        const value=overlaps*1000+distance;
        if(value<score){score=value;best={...box,overlap:overlaps};}
      });
      return best && (exhaustive || best.overlap===0) ? best : null;
    }

    updateConstellationLabels() {
      if (!this.isSkyLayout || !this.nodeSelection) return;
      const scale = this.transform.k || 1, tx=this.transform.x, ty=this.transform.y;
      const active = this.isCoarse ? (this.selectedId || this.hoveredId) : (this.hoveredId || this.selectedId);
      this.nodes.forEach(node=>{
        let nearest=Infinity;
        this.nodes.forEach(other=>{if(node!==other)nearest=Math.min(nearest,Math.hypot(node.x-other.x,node.y-other.y)*scale);});
        const desired=Math.max(this.isCoarse&&this.layout!=='constellations'?22:7,(node.radius||10)*scale+3);
        node.screenHitRadius=Math.min(desired,Math.max(5,nearest*.43));
      });
      const occupied = this.nodes.map(node=>({x:node.x*scale+tx-node.screenHitRadius,y:node.y*scale+ty-node.screenHitRadius,w:node.screenHitRadius*2,h:node.screenHitRadius*2,core:true}));
      const smallChart=this.width<600||this.height<300;
      const compactSystem=this.layout==='solar-system'&&smallChart;
      // Leave the mobile zoom controls and their bottom margin unobstructed.
      if(smallChart)occupied.push({x:0,y:Math.max(0,this.height-60),w:this.width,h:60,core:true});
      const compact = this.width < 760;
      const shortNames = {
        'Shared foundations':'Foundations',
        'Classical, analytic and computational number theory':'Classical number theory',
        'Arithmetic geometry and Diophantine methods':'Arithmetic geometry',
        'Modular, Shimura and Galois theory':'Modular & Galois',
        'General automorphic theory':'Automorphic theory',
        'Diamonds and geometric Langlands':'Geometric Langlands',
        'Cohomology and nonarchimedean geometry':'Cohomology',
        'K-theory, motives, periods and Habiro':'K-theory & motives',
        'Iwasawa, Euler systems and BSD':'Iwasawa theory',
        'Function fields and higher local fields':'Function fields',
        'Analysis, probability and PDE':'Analysis & probability',
        'Topology, manifolds and Floer theory':'Topology & Floer',
        'Algebra, representation theory and Lie groups':'Algebra & representations',
        'Differential and complex geometry':'Differential geometry',
        'Combinatorics and discrete structures':'Combinatorics',
        'Computation, optimization and control':'Computation & control',
        'Logic and foundations':'Logic & foundations'
      };
      const smallNames={
        'Shared foundations':'Foundations','Classical, analytic and computational number theory':'Number theory',
        'Arithmetic geometry and Diophantine methods':'Arith. geometry','Modular, Shimura and Galois theory':'Modular/Galois',
        'General automorphic theory':'Automorphic','Diamonds and geometric Langlands':'Geom. Langlands',
        'Cohomology and nonarchimedean geometry':'Cohomology','K-theory, motives, periods and Habiro':'K-theory/motives',
        'Iwasawa, Euler systems and BSD':'Iwasawa','Function fields and higher local fields':'Function fields',
        'Analysis, probability and PDE':'Analysis','Topology, manifolds and Floer theory':'Topology',
        'Algebra, representation theory and Lie groups':'Algebra','Differential and complex geometry':'Geometry',
        'Combinatorics and discrete structures':'Combinatorics','Computation, optimization and control':'Computation',
        'Logic and foundations':'Logic'
      };
      const graph=this;
      this.clusterLayer.selectAll('.tau-constellation-subject').each(function(subject) {
        const g=d3.select(this), mode=graph.width<480?'small':compact?'compact':'full';
        if(subject.captionMode!==mode) {
          const lines=compact ? [(mode==='small'?smallNames[subject.label]:shortNames[subject.label]) || subject.captionLines[0]] : subject.captionLines;
          const title=g.select('text'); title.selectAll('*').remove();
          lines.forEach((line,index)=>title.append('tspan').attr('x',0).attr('y',index*13).text(line));
          title.attr('font-size',compact?10:11);
          g.select('.tau-constellation-count').attr('y',lines.length*13+1).attr('display',compact?'none':null);
          const width=Math.max(...lines.map(line=>line.length))*(compact?5.3:6)+18;
          subject.captionBox={w:width,h:compact?24:lines.length*13+21};
          g.select('rect').attr('x',-width/2).attr('y',-13).attr('width',width).attr('height',subject.captionBox.h);
          subject.captionMode=mode;
        }
        const anchor={x:subject.labelX*scale+tx,y:subject.labelY*scale+ty};
        if(anchor.x < -180 || anchor.x>graph.width+180 || anchor.y < -110 || anchor.y>graph.height+110) {
          g.attr('display','none'); subject.screenCaption=null; return;
        }
        const box=graph.labelPlacement({x:anchor.x-subject.captionBox.w/2,y:anchor.y-subject.captionBox.h,
          ...subject.captionBox},occupied,true);
        if(!box){g.attr('display','none');subject.screenCaption=null;return;}
        occupied.push(box); subject.screenCaption=box;
        const origin={x:box.x+box.w/2,y:box.y+13};
        g.attr('display',null).attr('data-caption-compact',String(compact))
          .attr('transform',`translate(${(origin.x-tx)/scale},${(origin.y-ty)/scale}) scale(${1/scale})`);
        subject.captionLeader={
          x1:subject.labelX,y1:subject.labelY+12,
          x2:(Math.max(box.x,Math.min(box.x+box.w,anchor.x))-tx)/scale,
          y2:(Math.max(box.y,Math.min(box.y+box.h,anchor.y))-ty)/scale,
          moved:Math.hypot(box.x-(anchor.x-box.w/2),box.y-(anchor.y-box.h))>10
        };
      });
      if(this.subjectLeaders) this.subjectLeaders.attr('display',subject=>subject.screenCaption&&subject.captionLeader.moved?null:'none')
        .attr('d',subject=>{const p=subject.captionLeader;return p?`M${p.x1},${p.y1}L${p.x2},${p.y2}`:'';})
        .attr('stroke-width',.65/scale);
      this.nodeSelection.select('.tau-star-hit').attr('r',node=>node.screenHitRadius/scale);
      // Layer titles retain their space before transient landmark previews.
      const ordered=this.nodes.slice().sort((a,b)=>(b.type==='stage')-(a.type==='stage')||(b.id===active)-(a.id===active));
      const elements=new Map(); this.nodeSelection.each(function(node){elements.set(node.id,this);});
      ordered.forEach(node => {
        const g=d3.select(elements.get(node.id)), label=g.select('.tau-star-node-label');
        if(label.empty())return;
        const isActive=node.id===active, stage=node.type==='stage';
        const eligible=compactSystem ? (node.type==='landmark'&&isActive) : isActive || stage || graph.layout==='solar-system' || scale>(node.type==='landmark'?.68:.88);
        const x=node.x*scale+tx,y=node.y*scale+ty;
        if(!eligible || !isActive && (x < -160 || x>graph.width+160 || y < -90 || y>graph.height+90)) {
          label.attr('display','none');g.select('.tau-node-label-leader').attr('display','none');node.screenCaption=null;return;
        }
        const size=node.labelBox||{w:184,h:54},hitRadius=node.screenHitRadius;
        const preferred=stage?{x:x-size.w/2,y:y-size.h-Math.max(18,hitRadius+8),...size}:{x:x+13,y:y-24,...size};
        const box=graph.labelPlacement(preferred,occupied,isActive||stage||graph.layout==='solar-system');
        if(!box||box.overlap>0) {label.attr('display','none');g.select('.tau-node-label-leader').attr('display','none');node.screenCaption=null;return;}
        const chosen=box;
        occupied.push(chosen);node.screenCaption=chosen;
        label.attr('display',null).attr('transform',`translate(${(chosen.x-x+6)/scale},${(chosen.y-y+15)/scale}) scale(${1/scale})`);
        const moved=Math.hypot(chosen.x-preferred.x,chosen.y-preferred.y)>10;
        g.select('.tau-node-label-leader').attr('display',stage&&moved?null:'none')
          .attr('d',`M0,0L${(Math.max(chosen.x,Math.min(chosen.x+chosen.w,x))-x)/scale},${(Math.max(chosen.y,Math.min(chosen.y+chosen.h,y))-y)/scale}`)
          .attr('stroke-width',.65/scale);
      });
    }

    layoutLayerConstellations() {
      const stages = this.nodes.filter(node => node.type === 'stage');
      const landmarkMap = new Map(stages.map(stage => [stage.id, []]));
      this.nodes.filter(node => node.type === 'landmark').forEach(node => {
        const stage = landmarkMap.get(node.stageId || node.ownerStageId);
        if (stage) stage.push(node);
      });
      const sourceOrder=new Map(stages.map((stage,index)=>[stage.id,index]));
      const indegree=new Map(stages.map(stage=>[stage.id,0])),outgoing=new Map(stages.map(stage=>[stage.id,[]]));
      const ranks=new Map(stages.map(stage=>[stage.id,0]));
      this.edges.forEach(edge=>{
        if(/contains|reference/.test(edge.kind)||!indegree.has(edge.source.id)||!indegree.has(edge.target.id))return;
        outgoing.get(edge.source.id).push(edge.target.id);indegree.set(edge.target.id,indegree.get(edge.target.id)+1);
      });
      const ready=stages.filter(stage=>!indegree.get(stage.id)).map(stage=>stage.id),visited=new Set();
      while(ready.length){
        ready.sort((a,b)=>sourceOrder.get(a)-sourceOrder.get(b));
        const id=ready.shift();visited.add(id);
        outgoing.get(id).forEach(target=>{ranks.set(target,Math.max(ranks.get(target),ranks.get(id)+1));indegree.set(target,indegree.get(target)-1);if(!indegree.get(target))ready.push(target);});
      }
      // Unexpected cycles retain their source order; no prerequisite is fabricated.
      stages.forEach(stage=>{stage.rank=ranks.get(stage.id);stage.dependencyOrderValid=visited.has(stage.id);});
      stages.sort((a,b)=>a.rank-b.rank||sourceOrder.get(a.id)-sourceOrder.get(b.id));
      const maxRank=Math.max(1,...stages.map(stage=>stage.rank));
      const spread=Math.max(190,Math.sqrt(stages.length)*105);
      stages.forEach((stage,index)=>{
        const angle=index*Math.PI*(3-Math.sqrt(5))+.4;
        const radius=spread*Math.sqrt((index+.6)/Math.max(1,stages.length));
        Object.assign(stage,{x:Math.cos(angle)*radius*1.38+(stage.rank/maxRank-.5)*190,
          y:Math.sin(angle)*radius*.82,w:60,h:60,radius:14});
        stage.seedX=stage.x;stage.seedY=stage.y;
      });
      const stageIds=new Set(stages.map(stage=>stage.id));
      const links=this.edges.filter(edge=>stageIds.has(edge.source.id)&&stageIds.has(edge.target.id)&&! /contains|reference/.test(edge.kind));
      // Actual prerequisites draw neighboring stars together. Repulsion reserves
      // space for their names, without putting the layers into artificial rows.
      for(let step=0;step<160;step++){
        const force=new Map(stages.map(stage=>[stage.id,{x:(stage.seedX-stage.x)*.008,y:(stage.seedY-stage.y)*.008}]));
        links.forEach(edge=>{
          const a=edge.source,b=edge.target,dx=b.x-a.x,dy=b.y-a.y,length=Math.max(1,Math.hypot(dx,dy));
          const pull=(length-300)*.016;
          force.get(a.id).x+=dx/length*pull;force.get(a.id).y+=dy/length*pull;
          force.get(b.id).x-=dx/length*pull;force.get(b.id).y-=dy/length*pull;
        });
        stages.forEach((a,index)=>stages.slice(index+1).forEach(b=>{
          let dx=b.x-a.x,dy=b.y-a.y;
          if(!dx&&!dy)dx=.01;
          const length=Math.max(.01,Math.hypot(dx/1.35,dy/.8)),push=Math.max(0,255-length)*.13;
          force.get(a.id).x-=dx/length*push;force.get(a.id).y-=dy/length*push;
          force.get(b.id).x+=dx/length*push;force.get(b.id).y+=dy/length*push;
        }));
        stages.forEach(stage=>{stage.x+=force.get(stage.id).x;stage.y+=force.get(stage.id).y;});
      }
      // Older callers may still supply landmarks; keep those finite but reserve
      // the planetary layout for the dedicated solar-system view.
      stages.forEach(stage=>(landmarkMap.get(stage.id)||[]).forEach((node,index)=>{
        Object.assign(node,{x:stage.x+35+index*22,y:stage.y+45,w:20,h:20,radius:7,progress:null});
      }));
      // Outside prerequisites sit in a compact sideband beside the layer grid.
      const boundary=this.nodes.filter(node=>node.type!=='stage'&&node.type!=='landmark');
      const maxX=stages.length?Math.max(...stages.map(stage=>stage.x)):0;
      boundary.forEach((node,index)=>Object.assign(node,{x:maxX+420+(index%2)*130,y:Math.floor(index/2)*130+40,w:22,h:22,radius:6}));
      const orphans=this.nodes.filter(node=>!Number.isFinite(node.x)||!Number.isFinite(node.y));
      orphans.forEach((node,index)=>Object.assign(node,{x:maxX+420,y:boundary.length*65+index*90,w:15,h:15,radius:3.5}));
    }

    layoutSolarSystem() {
      const star=this.nodes.find(node=>node.type==='stage')||this.nodes[0];
      if(!star)return;
      Object.assign(star,{x:0,y:0,w:130,h:130,radius:42,solarCentral:true});
      const planets=this.nodes.filter(node=>node!==star),rotation=-.22;
      this.orbits=[];
      planets.forEach((node,index)=>{
        const radius=185+index*100,angle=[-.62,2.45,.3,3.7,1.22,5.13][index%6]+Math.floor(index/6)*.3;
        const ex=Math.cos(angle)*radius,ey=Math.sin(angle)*radius*.59;
        Object.assign(node,{x:ex*Math.cos(rotation)-ey*Math.sin(rotation),y:ex*Math.sin(rotation)+ey*Math.cos(rotation),
          w:70,h:70,radius:node.landmarkKind==='theorem'?27:node.landmarkKind==='definition'?22:25,progress:null,orbitIndex:index});
        this.orbits.push({id:node.id,cx:0,cy:0,rx:radius,ry:radius*.59,rotation:rotation*180/Math.PI});
      });
    }

    drawDeepSpace() {
      if(!this.nodes.length)return;
      const bounds=this.bounds(),field=this.clusterLayer.insert('g',':first-child').attr('class','tau-deep-space tau-space-art').attr('aria-hidden','true');
      const cx=bounds.x+bounds.w/2,cy=bounds.y+bounds.h/2;
      const washes=[{x:cx-bounds.w*.17,y:cy-bounds.h*.07,rx:bounds.w*.54,ry:bounds.h*.32,angle:-24,paint:'nebula-blue'},
        {x:cx+bounds.w*.21,y:cy+bounds.h*.15,rx:bounds.w*.42,ry:bounds.h*.23,angle:31,paint:'nebula-dust'}];
      field.selectAll('ellipse').data(washes).enter().append('ellipse').attr('class','tau-nebula-wash')
        .attr('cx',d=>d.x).attr('cy',d=>d.y).attr('rx',d=>d.rx).attr('ry',d=>d.ry)
        .attr('transform',d=>`rotate(${d.angle} ${d.x} ${d.y})`).attr('fill',d=>`url(#${this.id}-${d.paint})`);
      const stars=Array.from({length:this.layout==='constellations'?220:145},(_,index)=>({
        x:bounds.x+(((index*619+89)%2017)/2017)*bounds.w,y:bounds.y+(((index*383+53)%1877)/1877)*bounds.h,
        r:index%23===0?1.5:index%7===0?.85:.43,opacity:index%11===0?.67:index%3===0?.3:.15}));
      field.selectAll('circle').data(stars).enter().append('circle').attr('class','tau-distant-star')
        .attr('cx',d=>d.x).attr('cy',d=>d.y).attr('r',d=>d.r).attr('fill','#d9e8f5').attr('opacity',d=>d.opacity);
      if(this.layout==='solar-system')this.clusterLayer.append('g').attr('aria-hidden','true').selectAll('ellipse').data(this.orbits).enter().append('ellipse')
        .attr('class','tau-orbit-path tau-solar-orbit').attr('cx',0).attr('cy',0).attr('rx',d=>d.rx).attr('ry',d=>d.ry)
        .attr('transform',d=>`rotate(${d.rotation})`).attr('data-planet-id',d=>d.id);
    }

    drawSpaceNode(element,node) {
      const art=d3.select(element).append('g').attr('class','tau-space-art');
      const paint=name=>`url(#${this.id}-${name})`;
      const hash=Array.from(node.id).reduce((n,c)=>(n*31+c.charCodeAt(0))>>>0,7);
      if(node.type==='roadmap'||node.type==='unmapped'){
        const types=['spiral','barred','edge-on','elliptical'];
        const morphology=node.unmapped?'diffuse':types[hash%types.length];
        const size=.72+((hash>>>7)%53)/100,tilt=(hash%170)-85;
        const disk=paint((hash>>>4)%3===0?'galaxy-disk-cool':(hash>>>4)%3===1?'galaxy-disk-warm':'galaxy-disk');
        const body=art.append('g').attr('class','tau-galaxy-morphology-'+morphology).attr('transform',`rotate(${tilt}) scale(${size})`);
        d3.select(element).attr('data-morphology',morphology);
        node.visualMorphology=morphology;
        if(morphology==='diffuse'){
          body.append('ellipse').attr('class','tau-galaxy-glow').attr('rx',58).attr('ry',41).attr('fill',paint('galaxy-glow')).attr('opacity',.32);
          body.append('ellipse').attr('class','tau-galaxy-dust').attr('cx',9).attr('cy',-4).attr('rx',34).attr('ry',23).attr('fill',disk).attr('opacity',.19);
          body.append('ellipse').attr('class','tau-star-ring').attr('rx',39).attr('ry',29).attr('stroke','#92a4bd').attr('stroke-dasharray','2 7').attr('opacity',.4);
        }else if(morphology==='elliptical'){
          body.append('ellipse').attr('class','tau-galaxy-glow').attr('rx',44).attr('ry',34).attr('fill',paint('galaxy-glow'));
          body.append('ellipse').attr('class','tau-galaxy-dust').attr('rx',29).attr('ry',22).attr('fill',disk).attr('opacity',.72);
          body.append('ellipse').attr('class','tau-galaxy-core').attr('rx',10).attr('ry',8).attr('fill',disk).attr('opacity',.84);
        }else if(morphology==='edge-on'){
          body.append('ellipse').attr('class','tau-galaxy-glow').attr('rx',61).attr('ry',23).attr('fill',paint('galaxy-glow'));
          body.append('ellipse').attr('class','tau-galaxy-dust').attr('rx',48).attr('ry',9).attr('fill',disk);
          body.append('ellipse').attr('class','tau-galaxy-core').attr('rx',13).attr('ry',11).attr('fill',disk).attr('opacity',.87);
          body.append('path').attr('class','tau-galaxy-dust-lane').attr('d','M-45,3Q-5,-2 46,-2').attr('fill','none').attr('stroke','#080f1a').attr('stroke-width',2.7).attr('stroke-opacity',.72);
          body.append('path').attr('class','tau-galaxy-arm').attr('d','M-39,6Q0,12 39,2').attr('fill','none').attr('stroke','#adc1da').attr('stroke-width',1.1).attr('stroke-opacity',.18);
        }else{
          const flatten=.77+((hash>>>6)%4)*.06;
          body.append('ellipse').attr('class','tau-galaxy-glow').attr('rx',56).attr('ry',49*flatten).attr('fill',paint('galaxy-glow')).attr('opacity',.81);
          body.append('ellipse').attr('class','tau-galaxy-dust').attr('rx',41).attr('ry',38*flatten).attr('fill',disk).attr('opacity',.53);
          const spiral=body.append('g').attr('transform',`scale(1 ${flatten})`);
          spiral.append('path').attr('class','tau-galaxy-arm')
            .attr('d','M-37,17C-45,-11 -14,-42 18,-26C40,-14 28,13 7,14C-8,15 -12,2 -4,-5M37,-17C45,11 14,42 -18,26C-40,14 -28,-13 -7,-14C8,-15 12,-2 4,5')
            .attr('fill','none').attr('stroke',(hash>>>4)%3===1?'#e8d5bf':'#c6d7ed').attr('stroke-width',5).attr('stroke-opacity',.2);
          spiral.append('path').attr('class','tau-galaxy-dust-lane')
            .attr('d','M-34,13C-34,-12 -8,-32 14,-20C30,-11 23,8 8,10M34,-13C34,12 8,32 -14,20C-30,11 -23,-8 -8,-10')
            .attr('fill','none').attr('stroke','#111a2b').attr('stroke-width',2.1).attr('stroke-opacity',.38);
          if(morphology==='barred')spiral.append('ellipse').attr('class','tau-galaxy-bar').attr('rx',19).attr('ry',3.2).attr('transform','rotate(27)').attr('fill',disk).attr('opacity',.82);
          body.append('ellipse').attr('class','tau-galaxy-core').attr('rx',9).attr('ry',7).attr('fill',disk);
          const dust=Array.from({length:8},(_,i)=>{const angle=i*2.3+hash%9,radius=16+i*3;return{x:Math.cos(angle)*radius,y:Math.sin(angle)*radius*flatten,opacity:.14+(i%3)*.1};});
          body.selectAll('circle').data(dust).enter().append('circle').attr('cx',d=>d.x).attr('cy',d=>d.y).attr('r',.65).attr('fill','#edf0e8').attr('opacity',d=>d.opacity);
        }
        if(!node.unmapped)art.append('path').attr('class','tau-star-ring')
          .attr('d','M-29,25A39,32 0 0 0 29,25').attr('stroke',nodeAccent(node)).attr('stroke-width',1.05).attr('opacity',.66);
      }else if(node.type==='landmark'){
        const kind=['definition','theorem'].includes(node.landmarkKind)?node.landmarkKind:'construction',r=node.radius||24;
        art.append('circle').attr('class','tau-planet-halo').attr('r',r*1.6).attr('fill',paint('stellar-glow')).attr('opacity',.3);
        if(kind==='construction')art.append('ellipse').attr('class','tau-planet-ring').attr('rx',r*1.7).attr('ry',r*.53).attr('transform','rotate(-23)').attr('fill','none').attr('stroke','#8da6c6').attr('stroke-opacity',.48).attr('stroke-width',2.3);
        art.append('circle').attr('class','tau-planet-body tau-landmark-core').attr('r',r).attr('fill',paint('planet-'+kind));
        art.append('path').attr('class','tau-planet-shade').attr('d',`M${-r*.73},${-r*.36}Q0,${-r*.75} ${r*.77},${-r*.3}M${-r*.92},${r*.05}Q0,${-r*.22} ${r*.89},${r*.12}`)
          .attr('fill','none').attr('stroke',kind==='theorem'?'#efd4b2':'#d1e6ed').attr('stroke-width',r*.11).attr('stroke-opacity',.12);
        art.append('circle').attr('class','tau-star-ring').attr('r',r+5).attr('stroke','#d2dfed');
      }else{
        const r=node.radius||14,central=this.layout==='solar-system'&&node.solarCentral;
        art.append('circle').attr('class','tau-stellar-glow').attr('r',r*(central?4.2:4.6)).attr('fill',paint('stellar-glow'));
        art.append('circle').attr('class','tau-star-corona').attr('r',r*1.65).attr('fill',paint('stellar-light')).attr('opacity',.12);
        art.append('circle').attr('class','tau-stellar-core tau-star-core').attr('r',r).attr('fill',paint('stellar-light'));
        art.append('path').attr('class','tau-star-rays').attr('d',`M${-r*2.2},0H${r*2.2}M0,${-r*2.2}V${r*2.2}`)
          .attr('stroke','#f6e9c9').attr('stroke-width',.7).attr('stroke-opacity',central?.24:.35);
        art.append('circle').attr('class','tau-star-ring').attr('r',r+7).attr('stroke',nodeAccent(node)).attr('opacity',.7);
      }
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
      if (this.layout === 'constellations') this.drawConstellations();
      if(this.isSkyLayout)this.drawDeepSpace();
      if (this.layout === 'clusters' && this.clusters.length > 1) {
        const groups = this.clusterLayer.selectAll('g').data(this.clusters).enter().append('g');
        groups.append('rect').attr('class', 'tau-cluster').attr('x', d => d.x).attr('y', d => d.y)
          .attr('width', d => d.w).attr('height', d => d.h).attr('rx', 14);
        groups.append('text').attr('class', 'tau-cluster-title').attr('x', d => d.x + 15).attr('y', d => d.y + 26)
          .text(d => normalizeText(d.label));
      }
      this.edgeLayer.selectAll('*').remove();
      this.edgeSelection = this.edgeLayer.selectAll('path').data(this.edges).enter().append('path')
        .attr('class', edge => 'tau-edge' + (edge.kind === 'contains' ? ' tau-layer-containment' : '') + (edge.kind === 'reference' ? ' tau-reference-edge' : '')).attr('stroke', '#91a4b9').attr('stroke-width', 1.2)
        .attr('stroke-dasharray', edge => edge.kind==='reference'?'2 6':/declared|area|metadata/.test(edge.kind) ? '6 5' : null)
        .attr('marker-end', 'url(#' + this.id + '-arrow-normal)');
      this.nodeLayer.selectAll('*').remove();
      this.nodeSelection = this.nodeLayer.selectAll('g').data(this.nodes).enter().append('g')
        .attr('class', node => this.isSkyLayout ? 'tau-node tau-star-node' + (node.type === 'stage' ? ' tau-stage-constellation-node'+(this.layout==='solar-system'?' tau-solar-star':'') : node.type === 'landmark' ? ' tau-landmark-node'+(this.layout==='solar-system'?' tau-planet-node':'') : ' tau-galaxy-node'+(node.unmapped?' tau-unmapped-node':'')) : 'tau-node').attr('data-node-id', node => node.id)
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
          if (!this.isSkyLayout) return;
          this.hoveredId = node.id; this.applyEmphasis();
        })
        .on('mouseleave', () => { if (this.isSkyLayout) { this.hoveredId = null; this.applyEmphasis(); } })
        .on('focus', node => { if (this.isSkyLayout) { this.hoveredId = node.id; this.applyEmphasis(); } })
        .on('blur', () => { if (this.isSkyLayout) { this.hoveredId = null; this.applyEmphasis(); } })
        .on('keydown', node => {
          if (d3.event.key !== 'Enter' && d3.event.key !== ' ') return;
          d3.event.preventDefault(); d3.event.stopPropagation();
          this.select(node.id);
          if (d3.event.shiftKey && this.options.onOpen) this.options.onOpen(node);
          else if (this.options.onSelect) this.options.onSelect(node);
        });
      if (this.isSkyLayout) {
        this.nodeSelection.append('circle').attr('class', 'tau-star-hit').attr('r', 13);
        this.nodeSelection.each((node,index,elements)=>this.drawSpaceNode(elements[index],node));
        this.nodeSelection.each(function(node) {
          const group = d3.select(this);
          group.append('path').attr('class','tau-node-label-leader').attr('display','none');
          const label = group.append('g').attr('class', 'tau-star-node-label' + (node.type === 'stage' ? ' tau-stage-label' : node.type === 'landmark' ? ' tau-landmark-label' : ''));
          const lines = wrapText(node.label, 26, 3);
          node.labelBox={w:184,h:lines.length*15+24};
          label.append('rect').attr('x', -6).attr('y', -15).attr('width', 184).attr('height', lines.length*15+24)
            .attr('rx', 4).attr('fill', '#132035').attr('stroke', '#5d6c81').attr('fill-opacity', .98);
          const text = label.append('text');
          lines.forEach((line, i) => text.append('tspan').attr('x', 0).attr('y', i*15).text(line));
          label.append('text').attr('x', 0).attr('y', lines.length*15+7).style('font-size', '10px')
            .style('fill', nodeAccent(node)).text(node.type === 'landmark' ? (node.landmarkKind || 'Mathematical landmark') : progressDescription(node) || 'Click to explore');
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
      const drag = d3.drag().clickDistance(6).filter(() => !d3.event.button && !String(d3.event.type).startsWith('touch'))
        .on('start', () => { if (d3.event.sourceEvent) d3.event.sourceEvent.stopPropagation(); })
        .on('drag', node => {
          node.x += d3.event.dx; node.y += d3.event.dy;
          this.updatePositions();
        });
      // Sky objects keep their mathematical placement and planetary orbits.
      // Dragging a star therefore pans the SVG rather than moving the node.
      if(!this.isSkyLayout)this.nodeSelection.call(drag);
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
      const start = this.isSkyLayout ? [a.x + dx/lengthForClip*11, a.y + dy/lengthForClip*11] : clip(a, dx, dy, 2);
      const end = this.isSkyLayout ? [b.x - dx/lengthForClip*13, b.y - dy/lengthForClip*13] : clip(b, -dx, -dy, 4);
      if (edge.kind === 'contains') return `M${start[0]},${start[1]}L${end[0]},${end[1]}`;
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
      if (this.layout === 'constellations' && this.constellationSelection) this.constellationSelection.attr('d', link => this.constellationPath(link));
      this.updateConstellationLabels();
    }

    select(id) {
      this.selectedId = this.nodeMap.has(id) ? id : null;
      return this.applyEmphasis();
    }

    applyEmphasis() {
      const selected = this.isSkyLayout ? (this.isCoarse ? (this.selectedId||this.hoveredId) : (this.hoveredId || this.selectedId)) : this.selectedId;
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
        .attr('opacity', node => !selected || node.id === selected || neighbors.has(node.id) ? 1 : this.layout === 'constellations' ? .6 : .48);
      this.edgeSelection.attr('opacity', edge => this.layout==='solar-system'&&edge.kind==='contains'?0:selected ? (edge.source.id === selected || edge.target.id === selected ? .82 : this.layout === 'constellations' ? .035 : .11) : (this.layout === 'constellations' ? (edge.kind==='reference'?.14:.13) : this.edges.length > 150 ? .2 : .47))
        .attr('stroke', edge => edge.source.id === selected || edge.target.id === selected ? '#d8bb82' : '#92a8be')
        .attr('stroke-width', edge => edge.source.id === selected || edge.target.id === selected ? 2.1 : this.layout==='constellations'?1.15:1.3)
        .attr('marker-end', edge => /contains|reference/.test(edge.kind) ? null : 'url(#' + this.id + '-arrow-' + (edge.source.id === selected || edge.target.id === selected ? 'highlight' : 'normal') + ')');
      this.edgeSelection.filter(edge => edge.source.id === selected || edge.target.id === selected).raise();
      this.updateConstellationLabels();
      return this;
    }

    bounds() {
      if (!this.nodes.length) return { x: 0, y: 0, w: 100, h: 100 };
      let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
      this.nodes.forEach(node => { left = Math.min(left, node.x - node.w / 2); right = Math.max(right, node.x + node.w / 2); top = Math.min(top, node.y - node.h / 2); bottom = Math.max(bottom, node.y + node.h / 2); });
      if (this.layout === 'constellations') {
        this.constellationSubjects.forEach(group => {left = Math.min(left,group.labelX-145);right=Math.max(right,group.labelX+145);top=Math.min(top,group.labelY-70);bottom=Math.max(bottom,group.labelY+30);});
        if (this.constellationBounds) {left=Math.min(left,this.constellationBounds.x);right=Math.max(right,this.constellationBounds.x+this.constellationBounds.w);top=Math.min(top,this.constellationBounds.y);bottom=Math.max(bottom,this.constellationBounds.y+this.constellationBounds.h);}
      }
      if (this.layout === 'layer-constellations') { left -= 155; right += 155; top -= 110; bottom += 85; }
      if(this.layout==='solar-system'){
        this.orbits.forEach(orbit=>{left=Math.min(left,-orbit.rx);right=Math.max(right,orbit.rx);top=Math.min(top,-orbit.ry-80);bottom=Math.max(bottom,orbit.ry+80);});
        left-=140;right+=140;top-=80;bottom+=80;
      }
      this.clusters.forEach(group => { left = Math.min(left, group.x); right = Math.max(right, group.x + group.w); top = Math.min(top, group.y); bottom = Math.max(bottom, group.y + group.h); });
      return { x: left - 30, y: top - 30, w: right - left + 60, h: bottom - top + 60 };
    }

    fit(animate) {
      if (animate === undefined) animate = true;
      const box = this.bounds();
      const scale = Math.max(.025, Math.min(1.15, (this.width - 36) / box.w, (this.height - 36) / box.h));
      const transform = d3.zoomIdentity.translate(this.width / 2 - (box.x + box.w / 2) * scale, this.height / 2 - (box.y + box.h / 2) * scale).scale(scale);
      this.semantic.fitScale=scale;this.semantic.diveThreshold=scale*2.35;this.semantic.ascendThreshold=scale*.68;
      this.semanticParentCamera={x:transform.x,y:transform.y,k:transform.k};
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
      background = background || (this.layout === 'constellations' ? '#0d1728' : '#f8fafc');
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
      return { nodes: this.nodes.length, edges: this.edges.length, constellationLinks: this.constellationLinks.length, constellationSubjects: this.constellationSubjects.length, groupConnections: this.groupConnections || [],
        links: this.constellationLinks.map(link => ({group:link.group,sourceEdge:link.sourceEdge,source:{x:link.source.x,y:link.source.y},target:{x:link.target.x,y:link.target.y}})), layout: this.layout, selectedId: this.selectedId, semantic:{...this.semantic,canAscend:this.canAscend},orbits:(this.orbits||[]).length,
        width: this.width, height: this.height, transform: { x: this.transform.x, y: this.transform.y, k: this.transform.k },
        positions: this.nodes.map(node => ({ id: node.id, x: node.x, y: node.y, w: node.w, h: node.h, rank: node.rank == null ? null : node.rank, dependencyRank: node.rank == null ? null : node.rank, dependencyOrderValid: node.dependencyOrderValid, caption: node.screenCaption || null, progress: progressValue(node.progress), accent: nodeAccent(node) })) };
    }

    destroy() {
      this.destroyed = true;clearTimeout(this.travelTimer);
      if (this.observer) this.observer.disconnect();
      else window.removeEventListener('resize', this.resize);
      this.svg.interrupt().on('.zoom', null).remove();
    }
  }
  window.TauGraph = TauGraph;
})();
