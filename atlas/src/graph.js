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

  // Progress is the only thing colour encodes on the map. Red, amber and green
  // are recorded states; an object without recorded status has no colour.
  const NO_PROGRESS = '#6f7f8c', BACKGROUND = '#0b1016', ACCENT = '#dfc186';
  function progressColor(value) {
    const progress = progressValue(value);
    if (progress === null) return null;
    const stops = [[217, 108, 96], [212, 165, 79], [103, 175, 140]];
    const index = progress <= 50 ? 0 : 1;
    const fraction = progress <= 50 ? progress / 50 : (progress - 50) / 50;
    return '#' + stops[index].map((channel, i) => Math.round(channel + (stops[index + 1][i] - channel) * fraction).toString(16).padStart(2, '0')).join('');
  }

  function hasProgress(node) { return progressValue(node.progress) !== null; }
  function nodeAccent(node) { return progressColor(node.progress) || NO_PROGRESS; }
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

  function galaxyName(node) {
    const names={
      AInfCohomology:'Integral A-inf cohomology',ArithmeticKTheory:'Arithmetic K-theory',
      AutomorphicGaloisRepresentations:'Modular Galois representations',AutomorphicGaloisRepresentationsPartII:'Automorphic Galois II',
      CompletedCohomologyPartII:'Completed cohomology II',ComplexComparisonPartII:'Complex comparison II',
      AdicSpacesPartII:'Adic spaces II',ReductiveGroupsPartII:'Reductive groups II',ModularCurvesPartII:'Modular curves II',
      ClassicalAdicEtaleCohomology:'Adic étale cohomology',DeformationAndDerivedPatchingAlgebra:'Deformation and patching',
      DiamondEtaleCohomology:'Diamond étale cohomology',DiamondsAndVStacks:'Diamonds and v-stacks',
      FarguesFontaineDiamonds:'Fargues–Fontaine diamonds',FoundationsAndLibraryIntegration:'Shared foundations',
      EulerSystemsCyclotomicMainConjecture:'Cyclotomic main conjecture',PotentialAutomorphyInfrastructure:'Potential automorphy',
      TorsionCohomologyInfrastructure:'Torsion cohomology',EllipticKTheory:'Elliptic K-theory',
      KTheoryFiniteLocalFields:'Finite and local K-theory',SchemeKTheoryOperations:'Scheme K-theory',
      KTheoryLowDegrees:'Low-degree K-theory',StableHomotopyKTheory:'Stable homotopy K-theory',
      MotivesAndAlgebraicCycles:'Motives and cycles',RankZeroOneBSD:'Rank-zero and rank-one BSD',
      'tauceti:TauCetiRoadmap/RepresentationTheory/ClassicalGroups':'Classical representations',
      'tauceti:TauCetiRoadmap/RepresentationTheory/CompactGroups':'Compact representations',
      'tauceti:TauCetiRoadmap/RepresentationTheory/LieHighestWeight':'Highest weight theory',
      'tauceti:TauCetiRoadmap/RepresentationTheory/SchurWeyl':'Schur–Weyl duality',
      'tauceti:TauCetiRoadmap/RepresentationTheory/SpinRepresentations':'Spin representations',
      'tauceti:TauCetiRoadmap/OrthogonalL2Bases':'Orthogonal bases'
    };
    return names[node.id]||normalizeText(node.label).replace(/^The /i,'').split(/,|:| — /)[0].replace(/ And /g,' and ');
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
        .style('background', BACKGROUND).style('touch-action', 'none');
      // Every mark is flat: solid fills, thin strokes, no gradients or glows.
      this.svg.append('style').text(`
        .tau-graph .tau-node { cursor: pointer; outline: none; }
        .tau-graph .tau-card { fill: #131a22; stroke: #2a3541; stroke-width: 1; }
        .tau-graph .tau-node:hover .tau-card { stroke: #4a5866; }
        .tau-graph .tau-node:focus .tau-card { stroke: ${ACCENT}; }
        .tau-graph .tau-node.is-selected .tau-card { stroke: ${ACCENT}; stroke-width: 1.5; }
        .tau-graph .tau-node.is-neighbor .tau-card { stroke: #4a5866; }
        .tau-graph text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif; pointer-events: none; }
        .tau-graph .tau-node-title { fill: #e2e6eb; font-weight: 500; }
        .tau-graph .tau-node-subtitle { fill: #8391a0; font-size: 11px; }
        .tau-graph .tau-node-progress { font-size: 11px; font-weight: 600; }
        .tau-graph .tau-edge { fill: none; stroke-linecap: round; pointer-events: none; }
        .tau-graph .tau-cluster { fill: none; stroke: #222c37; stroke-dasharray: 4 6; }
        .tau-graph .tau-cluster-title { fill: #8391a0; font-size: 13px; font-weight: 500; }
        .tau-graph .tau-constellation-link, .tau-graph .tau-chart-field { pointer-events: none; }
        .tau-graph .tau-constellation-subject { cursor: pointer; outline: none; }
        .tau-graph .tau-constellation-subject text { fill: #b3bec9; font-weight: 500; letter-spacing: .2px; }
        .tau-graph .tau-constellation-subject:hover text, .tau-graph .tau-constellation-subject:focus text, .tau-graph .tau-constellation-subject.is-focused text { fill: #e2e6eb; }
        .tau-graph .tau-star-ring, .tau-graph .tau-space-art, .tau-graph .tau-orbit-path, .tau-graph .tau-survey-beacon { pointer-events: none; }
        .tau-graph .tau-space-art * { pointer-events: none; }
        .tau-graph .tau-orbit-path { fill: none; stroke: #3a4652; stroke-width: .8; opacity: .8; }
        .tau-graph .tau-star-ring { fill: none; stroke-width: 1.4; }
        .tau-graph .tau-planet-node .tau-star-ring { opacity: 0; }
        .tau-graph .tau-node.is-selected .tau-star-ring, .tau-graph .tau-node.is-hovered .tau-star-ring, .tau-graph .tau-node:focus .tau-star-ring { stroke: ${ACCENT} !important; stroke-width: 1.8; opacity: 1 !important; stroke-dasharray: none; }
        .tau-graph .tau-star-hit { fill: transparent; pointer-events: all; }
        .tau-graph .tau-star-node-label { pointer-events: none; }
        .tau-graph .tau-stage-label rect { pointer-events: all; cursor: pointer; }
        .tau-graph .tau-caption-leader, .tau-graph .tau-node-label-leader { fill: none; stroke: #5b6875; opacity: .7; pointer-events: none; }
        .tau-graph .tau-reference-edge { stroke-dasharray: 2 6; }
        .tau-graph .tau-star-node-label rect { fill: transparent; stroke: none; }
        .tau-graph .tau-star-node-label text { fill: #e2e6eb; font-size: 12px; font-weight: 500; paint-order: stroke fill; stroke: ${BACKGROUND}; stroke-width: 3px; stroke-linejoin: round; }
        .tau-graph .tau-galaxy-name text { fill: #c9d2da; font-weight: 400; paint-order: stroke fill; stroke: ${BACKGROUND}; stroke-linejoin: round; }
        .tau-graph .tau-node.is-selected .tau-galaxy-name text, .tau-graph .tau-node.is-hovered .tau-galaxy-name text { fill: #f0e4c8; }
      `);
      const defs = this.svg.append('defs');
      ['normal', 'highlight'].forEach(kind => {
        defs.append('marker').attr('id', this.id + '-arrow-' + kind)
          .attr('viewBox', '0 -4 9 8').attr('refX', 8).attr('refY', 0)
          .attr('markerWidth', kind === 'normal' ? 7 : 9).attr('markerHeight', kind === 'normal' ? 7 : 9)
          .attr('orient', 'auto').attr('markerUnits', 'userSpaceOnUse')
          .append('path').attr('d', 'M0,-3.5L8,0L0,3.5Z').attr('fill', kind === 'normal' ? '#7d8a99' : ACCENT);
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
      // A pinch is a camera gesture. Browsers still synthesise a click for a
      // finger that barely moved, which used to open whatever lay beneath it.
      // While two fingers are down, and briefly after they lift, clicks are
      // ignored; the pinch also records its starting scale so a dive needs a
      // deliberate change of scale rather than a wobble across the threshold.
      this.gestureTouches = 0; this.suppressClicksUntil = 0; this.pinchStartScale = null;
      const svgNode = this.svg.node();
      const gestureEnded = event => {
        if (event.touches && event.touches.length) return;
        if (this.gestureTouches >= 2) this.suppressClicksUntil = Date.now() + 700;
        this.gestureTouches = 0; this.pinchStartScale = null;
      };
      svgNode.addEventListener('touchstart', event => {
        this.gestureTouches = Math.max(this.gestureTouches, event.touches.length);
        if (event.touches.length >= 2) { this.suppressClicksUntil = Infinity; if (this.pinchStartScale === null) this.pinchStartScale = this.transform.k; }
      }, { passive: true, capture: true });
      svgNode.addEventListener('touchend', gestureEnded, { passive: true, capture: true });
      svgNode.addEventListener('touchcancel', gestureEnded, { passive: true, capture: true });
      this.resize = () => {
        if (this.destroyed) return;
        const box = this.container.getBoundingClientRect();
        const previousWidth=this.width,previousHeight=this.height;
        this.width = Math.max(160, box.width || 800);
        this.height = Math.max(160, box.height || 600);
        this.svg.attr('viewBox', '0 0 ' + this.width + ' ' + this.height);
        this.zoom.extent([[0, 0], [this.width, this.height]]);
        if (this.awaitingFit && box.width > 0 && box.height > 0) { this.awaitingFit = false; this.fit(false); }
        else if(this.nodes.length&&!this.semantic.busy&&previousWidth&&previousHeight&&(Math.abs(this.width/previousWidth-1)>(this.layout==='constellations'?.02:.2)||Math.abs(this.height/previousHeight-1)>(this.layout==='constellations'?.02:.2))){
          if(this.layout==='constellations'){this.layoutConstellations();this.draw();this.applyEmphasis();}
          this.fit(false);
        }
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
      this.groupConnections = [];this.sectorRoutes=[];this.sectorRouteSelection=null;
      this.clusters = [];
      this.constellationLinks = []; this.constellationSubjects = []; this.constellationBounds = null; this.hoveredId = null; this.hoveredSubject = null; this.hoveredRoute = null; this.subjectLeaders = null;
      this.isSkyLayout = ['constellations', 'layer-constellations', 'solar-system'].includes(this.layout);
      this.svg.classed('tau-constellations-layout', this.layout === 'constellations')
        .classed('tau-layer-constellations-layout', this.layout === 'layer-constellations')
        .classed('tau-solar-system-layout',this.layout==='solar-system').attr('data-layout', this.layout)
        .style('background', BACKGROUND);
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
        'Shared foundations': [-420, -35],
        'Classical, analytic and computational number theory': [-505, -470],
        'Arithmetic geometry and Diophantine methods': [-55, -310],
        'Modular, Shimura and Galois theory': [395, -170],
        'General automorphic theory': [850, -360],
        'Diamonds and geometric Langlands': [720, 240],
        'Cohomology and nonarchimedean geometry': [-80, 135],
        'K-theory, motives, periods and Habiro': [90, 545],
        'Iwasawa, Euler systems and BSD': [440, 520],
        'Function fields and higher local fields': [740, 800],
        'Analysis, probability and PDE': [-995, 350],
        'Topology, manifolds and Floer theory': [-460, 515],
        'Algebra, representation theory and Lie groups': [-760, 105],
        'Differential and complex geometry': [-1050, 745],
        'Combinatorics and discrete structures': [-850, -565],
        'Computation, optimization and control': [-1380, 10],
        'Logic and foundations': [-1310, -400]
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
      this.constellationLinks=[];this.constellationSubjects=[];this.sectorRoutes=[];
      if(!subjects.length){this.constellationBounds=null;return;}
      // Mathematical neighbourhoods are anchored in an irregular sky, then
      // separated radially. Population controls the area of each cloud; there
      // are no grid cells or shared rows for either galaxies or area headings.
      const small=this.width<600,bottomReserve=small||this.height<300?60:0;
      const usableHeight=Math.max(70,this.height-bottomReserve),shortWide=!small&&this.width/usableHeight>3.6;
      const unit=4;
      const chartW=subjects.length===1?Math.max(650,Math.sqrt(this.nodes.length)*190):Math.max(200,(this.width-44)*unit-60);
      const chartH=subjects.length===1?Math.max(510,chartW*.63):Math.max(100,(usableHeight-44)*unit-60);
      const gap=shortWide?28:small?42:74;
      const meanCount=this.nodes.length/subjects.length;
      subjects.forEach(subject=>{subject.areaWeight=.42+.58*Math.sqrt(subject.nodes.length/meanCount);});
      const totalWeight=subjects.reduce((total,subject)=>total+subject.areaWeight,0);
      const seedValues=subjects.map((subject,index)=>sectors[subject.label]||[Math.cos(index*2.4)*900,Math.sin(index*2.4)*650]);
      const minX=Math.min(...seedValues.map(p=>p[0])),maxX=Math.max(...seedValues.map(p=>p[0]));
      const minY=Math.min(...seedValues.map(p=>p[1])),maxY=Math.max(...seedValues.map(p=>p[1]));
      subjects.forEach((subject,index)=>{
        const seed=seedValues[index],variation=.9+(hash(subject.label)%101)/500;
        const area=chartW*chartH*.46*subject.areaWeight/totalWeight;
        const shape=(shortWide?4.2:small?.96:1.32)*variation;
        subject.w=subjects.length===1?chartW:Math.max(small?265:shortWide?360:430,Math.sqrt(area*shape));
        subject.h=subjects.length===1?chartH:Math.max(shortWide?125:small?180:270,area/subject.w);
        subject.seedX=((seed[0]-minX)/Math.max(1,maxX-minX)-.5)*chartW*.78;
        subject.seedY=((seed[1]-minY)/Math.max(1,maxY-minY)-.5)*chartH*.78;
        // A deterministic offset keeps a narrow chart from settling into rows.
        subject.seedX+=((hash(subject.label+'|x')%1000)/1000-.5)*subject.w*(small?.5:.2);
        subject.seedY+=((hash(subject.label+'|y')%1000)/1000-.5)*subject.h*(small?.5:.2);
        subject.x=subject.seedX;subject.y=subject.seedY;
      });
      const links=this.groupConnections.filter(link=>link.dependencies>0);
      const degree=new Map(subjects.map(subject=>[subject.label,0]));
      links.forEach(link=>{const weight=Math.log1p(link.weight);degree.set(link.source,degree.get(link.source)+weight);degree.set(link.target,degree.get(link.target)+weight);});
      for(let pass=0;pass<240;pass++){
        // A small attraction follows the recorded prerequisite network. The
        // semantic anchors remain stronger, so unrelated topics cannot migrate
        // through the atlas just because another area contains more roadmaps.
        if(pass<170){
          subjects.forEach(subject=>{subject.x+=(subject.seedX-subject.x)*.025;subject.y+=(subject.seedY-subject.y)*.025;});
          links.forEach(link=>{
            const a=subjectMap.get(link.source),b=subjectMap.get(link.target),weight=Math.log1p(link.weight);
            const dx=b.x-a.x,dy=b.y-a.y;
            const strength=.016*weight/Math.max(1,degree.get(a.label),degree.get(b.label));
            a.x+=dx*strength;a.y+=dy*strength;b.x-=dx*strength;b.y-=dy*strength;
          });
        }
        let moved=false;
        subjects.forEach((a,index)=>subjects.slice(index+1).forEach(b=>{
          let dx=b.x-a.x,dy=b.y-a.y;
          const width=(a.w+b.w)/2+gap,height=(a.h+b.h)/2+gap;
          if(Math.abs(dx)>=width||Math.abs(dy)>=height)return;
          if(Math.hypot(dx,dy)<.001){const angle=(hash(a.label+b.label)%360)*Math.PI/180;dx=Math.cos(angle);dy=Math.sin(angle);}
          const separation=Math.max(Math.abs(dx)/width,Math.abs(dy)/height);
          const distance=(1/Math.max(.001,separation)-1)*.505;
          a.x-=dx*distance;a.y-=dy*distance;b.x+=dx*distance;b.y+=dy*distance;moved=true;
        }));
        if(pass>=170&&!moved)break;
      }
      const left=Math.min(...subjects.map(subject=>subject.x-subject.w/2)),top=Math.min(...subjects.map(subject=>subject.y-subject.h/2));
      this.constellationBounds={x:left,y:top,w:Math.max(...subjects.map(subject=>subject.x+subject.w/2))-left,h:Math.max(...subjects.map(subject=>subject.y+subject.h/2))-top};
      const expectedScale=Math.max(.025,Math.min(1.15,(this.width-36)/(this.constellationBounds.w+60),(usableHeight-36)/(this.constellationBounds.h+60)));
      const adjacency=new Set();this.edges.forEach(edge=>{if(!/reference|contains/.test(edge.kind))adjacency.add([edge.source.id,edge.target.id].sort().join('\n'));});
      subjects.forEach(subject=>{
        const seed=hash(subject.label),w=subject.w,h=subject.h;
        const ordinaryHeader=shortWide?Math.min(66,h*.36):Math.min(h*.38,small?92:144);
        // A short landscape chart still needs the same readable heading in
        // screen pixels. Reserve it before packing its roadmap names below.
        const shortHeadingFont=w*expectedScale-12<85?9.5:w*expectedScale-12<125?10.5:11.5;
        const header=shortWide?Math.min(h-18,Math.max(ordinaryHeader,(shortHeadingFont+8)/expectedScale)):ordinaryHeader;
        const left=subject.x-w/2,top=subject.y-h/2;
        const cx=subject.x,cy=top+header+(h-header)/2;
        const rx=Math.max(25,w/2-(shortWide?14:42)),ry=Math.max(9,(h-header)/2-(shortWide?5:small?8:32)),rotation=(seed%360)*Math.PI/180;
        // Golden-angle packing has no artificial row or prerequisite direction.
        // A roadmap's real links are represented in the edge layer below.
        subject.nodes.forEach((node,index)=>{
          const angle=index*Math.PI*(3-Math.sqrt(5))+rotation,distance=subject.nodes.length===1?0:Math.sqrt((index+.45)/subject.nodes.length)*.92;
          node.x=cx+Math.cos(angle)*rx*distance;node.y=cy+Math.sin(angle)*ry*distance;
          node.constellationGroup=subject.label;
          node.surveySize=Math.min(1,Math.max(.18,Math.sqrt((rx*ry)/(Math.max(1,subject.nodes.length)*3500))));
        });
        const connected=new Set(subject.nodes.slice(0,1)),pending=new Set(subject.nodes.slice(1));
        while(pending.size){let nearest=null,minimum=Infinity;
          connected.forEach(source=>pending.forEach(target=>{const sourceEdge=adjacency.has([source.id,target.id].sort().join('\n'));
            const distance=Math.hypot(source.x-target.x,source.y-target.y)*(sourceEdge?.2:1);
            if(distance<minimum){minimum=distance;nearest={source,target,group:subject.label,sourceEdge};}}));
          this.constellationLinks.push(nearest);connected.add(nearest.target);pending.delete(nearest.target);
        }
        // A sparse area's heading sits just above its galaxies rather than at
        // the top of a mostly empty cloud. The reserve is measured in screen
        // pixels at the expected fit, so the heading never touches a core.
        const dotsTop=Math.min(...subject.nodes.map(node=>node.y));
        const labelY=Math.max(top+(shortWide?2:8),Math.min(dotsTop-(shortWide?36:small?46:58)/expectedScale,top+h-40));
        this.constellationSubjects.push({label:subject.label,x:cx,y:cy,labelX:cx,labelY,gap,
          sector:{x:left,y:top,w,h,header},radius:Math.max(rx,ry),count:subject.nodes.length,color:subject.nodes[0].color||'#9aabc1'});
      });
      const regionMap=new Map(this.constellationSubjects.map(subject=>[subject.label,subject])),routes=new Map();
      this.edges.forEach(edge=>{
        if(/reference|contains/.test(edge.kind))return;
        const a=edge.source.group||'Roadmaps',b=edge.target.group||'Roadmaps';if(a===b)return;
        const pair=[a,b].sort(),key=pair.join('\n');
        if(!routes.has(key))routes.set(key,{source:pair[0],target:pair[1],dependencies:0,witnesses:[]});
        const route=routes.get(key);route.dependencies++;route.witnesses.push({source:edge.source.id,target:edge.target.id,kind:edge.kind});
      });
      this.sectorRoutes=Array.from(routes.values()).map(route=>{
        const a=regionMap.get(route.source),b=regionMap.get(route.target);
        const dx=b.x-a.x,dy=b.y-a.y,length=Math.max(1,Math.hypot(dx,dy)),nx=-dy/length,ny=dx/length;
        let points=null,bestCost=Infinity;
        // Try gentle arcs on both sides of the direct connection. The route
        // with the clearest passage between other areas wins deterministically.
        [.10,-.10,.22,-.22,.38,-.38].forEach(bend=>{
          const direction=Math.sign(bend),bounds=this.constellationBounds;
          const c1={x:a.x+dx*.3,y:a.y+dy*.3},c2={x:a.x+dx*.7,y:a.y+dy*.7};
          let clearance=Infinity;
          [c1,c2].forEach(point=>{
            [[point.x,nx*direction,bounds.x+8,bounds.x+bounds.w-8],[point.y,ny*direction,bounds.y+8,bounds.y+bounds.h-8]].forEach(([origin,normal,low,high])=>{
              if(Math.abs(normal)>.0001)clearance=Math.min(clearance,Math.max(0,((normal>0?high:low)-origin)/normal));
            });
          });
          // Keep Bézier controls inside the chart: their convex hull then
          // contains the whole arc, even on a very wide phone viewport.
          const offset=Math.min(length*.42,Math.max(gap*1.4,length*Math.abs(bend)),clearance*.85)*direction;
          c1.x+=nx*offset;c1.y+=ny*offset;c2.x+=nx*offset;c2.y+=ny*offset;
          const samples=Array.from({length:81},(_,index)=>{
            const t=index/80,u=1-t;
            return [u*u*u*a.x+3*u*u*t*c1.x+3*u*t*t*c2.x+t*t*t*b.x,u*u*u*a.y+3*u*u*t*c1.y+3*u*t*t*c2.y+t*t*t*b.y];
          });
          const obscured=samples.filter(point=>this.constellationSubjects.some(subject=>{
            if(subject===a||subject===b)return false;const box=subject.sector;
            return point[0]>box.x-8&&point[0]<box.x+box.w+8&&point[1]>box.y-8&&point[1]<box.y+box.h+8;
          })).length;
          const cost=obscured*100+Math.abs(offset)/length;
          if(cost<bestCost){bestCost=cost;points=samples;}
        });
        return {...route,points,shape:'curve'};
      });
      // Only the strongest routes carry ink at rest. Every route stays in the
      // data and appears when its area or a member roadmap is active.
      const counts=this.sectorRoutes.map(route=>route.dependencies).sort((a,b)=>a-b);
      const threshold=counts.length?Math.max(3,counts[Math.floor(counts.length*.65)]):Infinity;
      this.sectorRoutes.forEach(route=>{route.strong=route.dependencies>=threshold;});
      this.layoutGalaxyNames();
    }

    layoutGalaxyNames() {
      const compact=this.width<600||this.height<300;
      this.constellationSubjects.forEach(subject=>{
        const members=this.nodes.filter(node=>node.constellationGroup===subject.label),sector=subject.sector;
        members.forEach(node=>{node.galaxyName=galaxyName(node);node.galaxyNameLines=wrapText(node.galaxyName,19,2);});
        const ordered=members.slice().sort((a,b)=>Math.max(...b.galaxyNameLines.map(line=>line.length))-Math.max(...a.galaxyNameLines.map(line=>line.length))||a.id.localeCompare(b.id));
        const cores=members.map(node=>{
          const nearest=Math.min(...members.filter(other=>other!==node).map(other=>Math.hypot(other.x-node.x,other.y-node.y)));
          const r=Math.min(8,nearest*.24);return {x:node.x-r,y:node.y-r,w:r*2,h:r*2};
        });
        const overlap=(a,b)=>Math.min(a.x+a.w,b.x+b.w)>Math.max(a.x,b.x)+1e-7&&Math.min(a.y+a.h,b.y+b.h)>Math.max(a.y,b.y)+1e-7;
        // Large names are tried first. A dense area gets uniformly smaller type
        // until every label fits, rather than accepting a tangle of overlaps.
        let font=compact?14:22;
        for(let attempt=0;attempt<28;attempt++,font*=.82){
          const padding=font*.3,placed=[],positions=new Map();let failed=false;
          const left=sector.x+2,right=sector.x+sector.w-2,top=sector.y+sector.header+2,bottom=sector.y+sector.h-2;
          for(const node of ordered){
            const w=Math.max(...node.galaxyNameLines.map(line=>line.length))*font*.68+padding*2,h=node.galaxyNameLines.length*font*1.22+padding*2;
            const candidates=[],add=(x,y)=>candidates.push({x:Math.max(left,Math.min(right-w,x)),y:Math.max(top,Math.min(bottom-h,y)),w,h});
            add(node.x-w/2,node.y+10);add(node.x-w/2,node.y-h-10);add(node.x+10,node.y-h/2);add(node.x-w-10,node.y-h/2);
            placed.forEach(box=>{add(box.x-w-padding,node.y-h/2);add(box.x+box.w+padding,node.y-h/2);add(node.x-w/2,box.y-h-padding);add(node.x-w/2,box.y+box.h+padding);});
            for(let y=top;y+h<=bottom+1e-7;y+=Math.max(.1,h*.55))for(let x=left;x+w<=right+1e-7;x+=Math.max(.1,w*.35))candidates.push({x,y,w,h});
            let best=null,distance=Infinity;
            candidates.forEach(box=>{
              if(box.x<left||box.y<top||box.x+box.w>right+1e-7||box.y+box.h>bottom+1e-7||cores.some(core=>overlap(box,core))||placed.some(other=>overlap(box,other)))return;
              const d=Math.hypot(box.x+w/2-node.x,box.y+h/2-node.y);if(d<distance){distance=d;best=box;}
            });
            if(!best){failed=true;break;}positions.set(node.id,best);placed.push(best);
          }
          if(!failed){members.forEach(node=>{node.galaxyNameFont=font;node.galaxyNameBox=positions.get(node.id);});return;}
        }
      });
    }

    constellationPath(link) {
      return `M${link.source.x},${link.source.y}L${link.target.x},${link.target.y}`;
    }

    sectorRoutePath(route) {
      // Clip only the curved ink, not a visible enclosure, around the clouds
      // and their labels. Cubic segments replace the former horizontal routes.
      const fragments=[];let current=[];
      const finish=()=>{if(current.length>2)fragments.push(current);current=[];};
      (route.points||[]).forEach(point=>{
        const hidden=this.constellationSubjects.some(subject=>{
          const box=subject.sector;
          return point[0]>box.x&&point[0]<box.x+box.w&&point[1]>box.y&&point[1]<box.y+box.h;
        });
        if(hidden)finish();else current.push(point);
      });
      finish();
      // Bézier interpolation of sampled points keeps even a short visible
      // fragment curved, with no right-angle corridor or horizontal separator.
      return fragments.map(points=>{
        let path=`M${points[0][0]},${points[0][1]}`;
        for(let index=1;index<points.length;index++){
          const before=points[Math.max(0,index-2)],a=points[index-1],b=points[index],after=points[Math.min(points.length-1,index+1)];
          path+=`C${a[0]+(b[0]-before[0])/6},${a[1]+(b[1]-before[1])/6} ${b[0]-(after[0]-a[0])/6},${b[1]-(after[1]-a[1])/6} ${b[0]},${b[1]}`;
        }
        return path;
      }).join('');
    }

    drawConstellations() {
      const routes=this.clusterLayer.append('g').attr('class','tau-sector-routes');
      this.sectorRouteSelection=routes.selectAll('path').data(this.sectorRoutes||[]).enter().append('path')
        .attr('class',route=>'tau-sector-route'+(route.strong?' is-strong':' is-quiet')).attr('data-source-area',route=>route.source).attr('data-target-area',route=>route.target)
        .attr('data-strong',route=>String(!!route.strong)).attr('d',route=>this.sectorRoutePath(route)).attr('fill','none')
        .attr('stroke','#6f8496').attr('stroke-width',route=>.6+Math.min(.9,Math.log1p(route.dependencies)*.16))
        .attr('vector-effect','non-scaling-stroke').attr('stroke-linejoin','round').attr('opacity',route=>route.strong?.16:0)
        .attr('role','img').attr('aria-label',route=>`Connections between ${route.source} and ${route.target}: ${route.dependencies} roadmap prerequisite links`)
        .attr('pointer-events',route=>route.strong?'stroke':'none').on('mouseenter',route=>this.highlightSectorRoute(route)).on('mouseleave',()=>this.highlightSectorRoute(null));
      this.sectorRouteSelection.append('title').text(route=>`${route.source} ↔ ${route.target}\n${route.dependencies} roadmap prerequisite links. Select a roadmap to see their direction.`);
      this.constellationSelection=this.clusterLayer.selectAll('path.tau-constellation-link').data(this.constellationLinks).enter().append('path')
        .attr('class',link=>'tau-constellation-link'+(link.sourceEdge?' is-mathematical':' is-grouping'))
        .attr('data-source-edge',link=>String(link.sourceEdge)).attr('d',link=>this.constellationPath(link))
        .attr('fill','none').attr('stroke','#4f5f6d').attr('stroke-width',.7).attr('vector-effect','non-scaling-stroke').attr('opacity',link=>link.sourceEdge?.22:0);
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
        'Algebra, representation theory and Lie groups': ['Algebra &', 'representations'],
        'Differential and complex geometry': ['Differential &', 'complex geometry'],
        'Combinatorics and discrete structures': ['Combinatorics &', 'discrete structures'],
        'Computation, optimization and control': ['Computation &', 'optimization'],
        'Logic and foundations': ['Logic & foundations']
      };
      this.subjectLeaders = this.clusterLayer.append('g').attr('aria-hidden', 'true').selectAll('path').data(this.constellationSubjects).enter().append('path').attr('class', 'tau-caption-leader');
      const titles = this.clusterLayer.selectAll('g.tau-constellation-subject').data(this.constellationSubjects).enter().append('g')
        .attr('class', 'tau-constellation-subject tau-constellation-label').attr('data-subject-label', subject => subject.label)
        .attr('tabindex', 0).attr('role', 'button').attr('aria-label', subject => `Open ${subject.label}: ${subject.count} roadmaps`)
        .on('click', subject => {
          d3.event.stopPropagation();
          if (this.options.onGroupSelect) this.options.onGroupSelect(subject.label);
        })
        .on('mouseenter', subject => { this.hoveredSubject = subject.label; this.updateConstellationLabels(); })
        .on('mouseleave', () => { this.hoveredSubject = null; this.updateConstellationLabels(); })
        .on('focus', subject => { this.hoveredSubject = subject.label; this.updateConstellationLabels(); })
        .on('blur', () => { this.hoveredSubject = null; this.updateConstellationLabels(); })
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
          .attr('height', lines.length*13+18).attr('fill', BACKGROUND).attr('fill-opacity', 0);
        const title = g.append('text').attr('text-anchor', 'middle').attr('font-size', 11);
        lines.forEach((line, index) => title.append('tspan').attr('x', 0).attr('y', -(lines.length - 1 - index)*13).text(line));
        g.append('title').text(subject.label + '\n' + subject.captionCount + ' — click to open');
      });
    }

    highlightSectorRoute(route) {
      if(this.layout!=='constellations')return;
      this.hoveredRoute=route||null;
      this.updateConstellationLabels();
    }

    // The ink a route receives at rest, or while an area, a roadmap or the
    // route itself has the reader's attention. Hidden ink is still data.
    routeOpacity(route, focusGroup, detail) {
      if (this.hoveredRoute) return route === this.hoveredRoute ? .75 : .03;
      if (focusGroup) return route.source === focusGroup || route.target === focusGroup ? .6 : .03;
      return route.strong ? .16 * (1 - detail * .8) : 0;
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
        const stepX=Math.max(24,preferred.w*.3), stepY=Math.max(18,preferred.h*.6);
        for (let y=margin; y+preferred.h<=this.height-margin; y+=stepY) {
          for (let x=margin; x+preferred.w<=this.width-margin; x+=stepX) candidates.push({...preferred,x,y});
        }
      }
      // First look for a spot clear of every core. A caption that must be
      // shown may then cover the fewest small cores, but never a heading,
      // another caption or the chart controls.
      const evaluate = strict => {
        let best=null, score=Infinity;
        candidates.forEach(box => {
          if(occupied.some(other=>other.core&&(strict||other.hard)&&overlap(box,other)>0))return;
          const soft=strict?0:occupied.reduce((sum,other)=>sum+(other.core&&!other.hard?overlap(box,other):0),0);
          const overlaps=occupied.reduce((sum,other)=>sum+(other.core?0:overlap(box,other)),0);
          const distance=Math.hypot(box.x-preferred.x,box.y-preferred.y);
          const value=soft*4000+overlaps*1000+distance;
          if(value<score){score=value;best={...box,overlap:overlaps};}
        });
        return best;
      };
      const best = evaluate(true) || (exhaustive ? evaluate(false) : null);
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
        // At atlas fit, dense sectors need disjoint hit regions: even a small
        // minimum can cover a neighboring galaxy's exact tap position. Larger
        // layer-star and planet targets remain available in the inner scenes.
        node.screenHitRadius=this.layout==='constellations'?Math.min(desired,nearest*.44):Math.min(desired,Math.max(5,nearest*.43));
        node.surveyMarkerRadius=Math.max(.65,Math.min(node.unmapped?1.7:2.15,nearest*.26));
      });
      const occupied = this.nodes.map(node=>({x:node.x*scale+tx-node.screenHitRadius,y:node.y*scale+ty-node.screenHitRadius,w:node.screenHitRadius*2,h:node.screenHitRadius*2,core:true}));
      const smallChart=this.width<600||this.height<300;
      const compactSystem=this.layout==='solar-system'&&smallChart;
      // Leave the mobile zoom controls and their bottom margin unobstructed.
      if(smallChart)occupied.push({x:0,y:Math.max(0,this.height-60),w:this.width,h:60,core:true,hard:true});
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
        const g=d3.select(this),sector=subject.sector;
        if(!sector)return;
        // A phone chart is narrow: headings keep a readable size and may use
        // the clear gap beside their own area rather than shrinking away.
        const smallHeading=graph.width<600||graph.height<300;
        const availableWidth=sector.w*scale-12+(smallHeading?Math.min(40,(subject.gap||0)*scale):0),headerHeight=sector.header*scale;
        const mode=availableWidth<135?'compact':'full';
        const names=mode==='compact'?shortNames:null;
        let lines=graph.width<600||headerHeight<30?[smallNames[subject.label]||subject.captionLines[0]]:mode==='compact'?wrapText(names[subject.label]||smallNames[subject.label]||subject.label,Math.max(12,Math.floor(availableWidth/5.4)),2):subject.captionLines;
        const preferredFont=availableWidth<85?9.5:availableWidth<125?10.5:11;
        // Fit the ink as well as the hit box. A heading must not extend into
        // its neighbour when a narrow viewport is fitted after navigation.
        if(mode==='compact'&&headerHeight>=31&&lines.length===1&&lines[0].length*preferredFont*.57+10>availableWidth){
          const words=lines[0].replace('/', ' / ').split(/\s+/);
          if(words.length>1)lines=wrapText(words.join(' '),Math.max(7,Math.floor((availableWidth-10)/(preferredFont*.57))),2);
        }
        let longest=Math.max(...lines.map(line=>line.length));
        let font=Math.max(smallHeading?9:1,Math.min(preferredFont,Math.max(1,availableWidth-10)/(longest*.62)));
        if(smallHeading&&lines.length===1&&longest*font*.6+16>sector.w*scale+(subject.gap||0)*scale*.45){
          // Rather than run into the neighbouring heading, a long phone
          // heading breaks onto a second line; a single long word shrinks.
          const words=lines[0].replace('/',' / ').split(/\s+/);
          if(words.length>1)lines=wrapText(words.join(' '),Math.max(6,Math.ceil(longest/2)+1),2);
          longest=Math.max(...lines.map(line=>line.length));
          font=Math.max(8,Math.min(font,(sector.w*scale+(subject.gap||0)*scale*.45-16)/(longest*.6)));
        }
        const lineHeight=font+2,h=lines.length*lineHeight+2;
        const width=Math.max(54,longest*font*.6+16);
        const anchor={x:subject.labelX*scale+tx,y:subject.labelY*scale+ty};
        const box={x:anchor.x-width/2,y:anchor.y+2,w:width,h};
        // Each independent cloud reserves room above its own galaxies. During
        // zoom the heading leaves the viewport with its cloud, rather than
        // drifting onto another area or covering a roadmap core.
        const visible=box.x+box.w>0&&box.x<graph.width&&box.y+box.h>0&&box.y<graph.height;
        subject.screenCaption=visible?box:null;g.attr('display',visible?null:'none');if(!visible)return;
        const title=g.select('text');title.selectAll('*').remove();
        lines.forEach((line,index)=>title.append('tspan').attr('x',0).attr('y',font+index*lineHeight).text(line));
        title.attr('font-size',font);
        g.select('rect').attr('x',-width/2).attr('y',0).attr('width',width).attr('height',h);
        g.classed('is-focused',subject.label===graph.hoveredSubject||(active&&graph.nodeMap.get(active)?.group===subject.label))
          .attr('data-caption-compact',String(mode==='compact')).attr('transform',`translate(${(anchor.x-tx)/scale},${(box.y-ty)/scale}) scale(${1/scale})`);
        occupied.push({...box,core:true,hard:true});subject.captionMode=mode;
      });
      if(this.subjectLeaders)this.subjectLeaders.attr('display','none');
      if(this.layout==='constellations'){
        const relative=scale/Math.max(.001,this.semantic.fitScale),detail=Math.max(0,Math.min(1,(relative-1.35)/1.2));
        const focusGroup=active?graph.nodeMap.get(active)?.group:this.hoveredSubject;
        this.nodeSelection.select('.tau-space-art').attr('opacity',node=>.4+.6*detail)
          .attr('transform',node=>`scale(${node.surveySize+(1-node.surveySize)*detail})`);
        this.nodeSelection.select('.tau-survey-beacon').attr('opacity',1-detail).attr('r',node=>node.surveyMarkerRadius/scale).attr('stroke-width',.9/scale);
        if(this.sectorRouteSelection)this.sectorRouteSelection.attr('opacity',route=>this.routeOpacity(route,focusGroup,detail))
          .attr('stroke',route=>route===this.hoveredRoute?ACCENT:'#6f8496');
        if(this.constellationSelection)this.constellationSelection.attr('opacity',link=>link.sourceEdge?.2*(1-detail):0);
        this.edgeSelection.attr('opacity',edge=>active?((edge.source.id===active||edge.target.id===active)?.85:.02):edge.kind==='reference'?.12:detail*.15)
          .attr('stroke-width',edge=>(edge.source.id===active||edge.target.id===active?1.65:1)/scale);
      }
      this.nodeSelection.select('.tau-star-hit').attr('r',node=>node.screenHitRadius/scale);
      if(this.layout==='constellations')this.nodeSelection.each(function(node){
        const name=d3.select(this).select('.tau-galaxy-name'),box=node.galaxyNameBox;
        if(!box)return;
        const font=Math.min(node.galaxyNameFont,12/scale);
        node.galaxyNameScreenFont=font*scale;
        // Text that would render smaller than about eight pixels is noise, not
        // a name. It stays hidden until the reader zooms close enough to read it.
        if(node.galaxyNameScreenFont<8.5){name.attr('display','none');node.galaxyNameVisible=false;return;}
        name.attr('transform',`translate(${box.x+box.w/2-node.x},${box.y-node.y})`).attr('display',null);
        name.select('text').attr('font-size',font).attr('stroke-width',Math.min(font*.18,2/scale));
        name.selectAll('tspan').attr('y',function(){return font*1.18+Number(this.getAttribute('data-line'))*font*1.22;});
        node.galaxyNameVisible=true;
        // Give the active full title real space among the persistent names.
        if(node.id!==active){
          const nameBox={x:(box.x+box.w/2)*scale+tx-Math.max(...node.galaxyNameLines.map(line=>line.length))*font*.34*scale,y:box.y*scale+ty,w:Math.max(...node.galaxyNameLines.map(line=>line.length))*font*.68*scale,h:node.galaxyNameLines.length*font*1.22*scale,core:true,hard:true};
          if(nameBox.x+nameBox.w>0&&nameBox.x<graph.width&&nameBox.y+nameBox.h>0&&nameBox.y<graph.height)occupied.push(nameBox);
        }
      });
      // Layer titles retain their space before transient landmark previews.
      const ordered=this.nodes.slice().sort((a,b)=>(b.type==='stage')-(a.type==='stage')||(b.id===active)-(a.id===active));
      const elements=new Map(); this.nodeSelection.each(function(node){elements.set(node.id,this);});
      ordered.forEach(node => {
        const g=d3.select(elements.get(node.id)), label=g.select('.tau-star-node-label');
        if(label.empty())return;
        const isActive=node.id===active, stage=node.type==='stage';
        const eligible=graph.layout==='constellations'?isActive:compactSystem ? (node.type==='landmark'&&isActive) : isActive || stage || graph.layout==='solar-system' || scale>(node.type==='landmark'?.68:.88);
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
        if(graph.layout==='constellations'){g.select('.tau-galaxy-name').attr('display','none');node.galaxyNameVisible=false;}
        label.attr('display',null).attr('transform',`translate(${(chosen.x-x+6)/scale},${(chosen.y-y+15)/scale}) scale(${1/scale})`);
        // A caption that had to move away from its object keeps a thin leader
        // back to it, so a displaced name is never mistaken for a neighbour's.
        const moved=Math.hypot(chosen.x-preferred.x,chosen.y-preferred.y)>10;
        g.select('.tau-node-label-leader').attr('display',moved?null:'none')
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
      // A sparse field of flat points gives the sky depth without washes,
      // gradients or anything that could be mistaken for data.
      const stars=Array.from({length:this.layout==='constellations'?48:90},(_,index)=>({
        x:bounds.x+(((index*619+89)%2017)/2017)*bounds.w,y:bounds.y+(((index*383+53)%1877)/1877)*bounds.h,
        r:index%23===0?1.2:index%7===0?.8:.45,opacity:index%11===0?.4:index%3===0?.22:.12}));
      field.selectAll('circle').data(stars).enter().append('circle').attr('class','tau-distant-star')
        .attr('cx',d=>d.x).attr('cy',d=>d.y).attr('r',d=>d.r).attr('fill','#c7d3df').attr('opacity',d=>d.opacity);
      if(this.layout==='solar-system')this.clusterLayer.append('g').attr('aria-hidden','true').selectAll('ellipse').data(this.orbits).enter().append('ellipse')
        .attr('class','tau-orbit-path tau-solar-orbit').attr('cx',0).attr('cy',0).attr('rx',d=>d.rx).attr('ry',d=>d.ry)
        .attr('transform',d=>`rotate(${d.rotation})`).attr('data-planet-id',d=>d.id);
    }

    drawSpaceNode(element,node) {
      const art=d3.select(element).append('g').attr('class','tau-space-art');
      const hash=Array.from(node.id).reduce((n,c)=>(n*31+c.charCodeAt(0))>>>0,7);
      if(node.type==='roadmap'||node.type==='unmapped'){
        // A galaxy is a soft flat disc with a small core. The core carries the
        // progress colour; without recorded progress it is an open ring.
        const size=.72+((hash>>>7)%53)/100,tilt=(hash%170)-85,flatten=.6+((hash>>>6)%7)*.05;
        const body=art.append('g').attr('class','tau-galaxy-morphology-diffuse')
          .attr('transform',`rotate(${tilt}) scale(${size})`).attr('opacity',node.unmapped?.4:1);
        d3.select(element).attr('data-morphology','diffuse');
        node.visualMorphology='diffuse';
        body.append('ellipse').attr('class','tau-galaxy-glow').attr('rx',54).attr('ry',42*flatten).attr('fill','#9db3c9').attr('opacity',.09);
        body.append('ellipse').attr('class','tau-galaxy-cloud').attr('rx',32).attr('ry',25*flatten).attr('fill','#b9cad9').attr('opacity',.15);
        if(node.unmapped)art.append('ellipse').attr('class','tau-star-ring').attr('rx',36).attr('ry',27)
          .attr('stroke','#8a99a8').attr('stroke-dasharray','3 6').attr('stroke-width',1).attr('opacity',.8);
        else{
          art.append('circle').attr('class','tau-galaxy-core').attr('r',6.5).attr('fill',hasProgress(node)?nodeAccent(node):BACKGROUND)
            .attr('stroke',hasProgress(node)?nodeAccent(node):NO_PROGRESS).attr('stroke-width',1.6);
          art.append('circle').attr('class','tau-star-ring').attr('r',11).attr('stroke',ACCENT).attr('opacity',0);
        }
      }else if(node.type==='landmark'){
        // Planets are flat discs coloured by kind; the kind is also named in
        // the label and the reading pane.
        const kind=['definition','theorem'].includes(node.landmarkKind)?node.landmarkKind:'construction',r=node.radius||24;
        const fill={definition:'#7fb8bd',theorem:'#dba57f',construction:'#8fa8d0'}[kind];
        art.append('circle').attr('class','tau-planet-body tau-landmark-core').attr('r',r).attr('fill',fill).attr('stroke',BACKGROUND).attr('stroke-width',1.5);
        art.append('circle').attr('class','tau-star-ring').attr('r',r+5).attr('stroke','#d2dfed');
      }else{
        // A layer star: a flat cream disc with a progress ring around it.
        const r=node.radius||14;
        art.append('circle').attr('class','tau-stellar-core tau-star-core').attr('r',r).attr('fill','#e8e4da');
        art.append('circle').attr('class','tau-star-ring').attr('r',r+5).attr('stroke',nodeAccent(node))
          .attr('stroke-dasharray',hasProgress(node)?null:'2 3').attr('opacity',hasProgress(node)?.95:.7);
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
          if (Date.now() < this.suppressClicksUntil) return;
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
        // At atlas scale each galaxy is a point: filled with its progress
        // colour, or an open ring when no progress is recorded.
        if(this.layout==='constellations')this.nodeSelection.append('circle').attr('class','tau-survey-beacon tau-space-art-marker')
          .attr('fill',node=>!node.unmapped&&hasProgress(node)?nodeAccent(node):BACKGROUND)
          .attr('stroke',node=>node.unmapped?'#8a99a8':hasProgress(node)?nodeAccent(node):NO_PROGRESS).attr('pointer-events','none');
        if(this.layout==='constellations')this.nodeSelection.each(function(node){
          const name=d3.select(this).append('g').attr('class','tau-galaxy-name').attr('aria-hidden','true').attr('pointer-events','none');
          const title=name.append('text').attr('stroke',BACKGROUND).attr('stroke-width',2)
            .attr('paint-order','stroke fill').attr('stroke-linejoin','round').attr('text-anchor','middle');
          (node.galaxyNameLines||wrapText(node.label,19,2)).forEach((line,index)=>title.append('tspan').attr('x',0).attr('data-line',index).text(line));
        });
        this.nodeSelection.each(function(node) {
          const group = d3.select(this);
          group.append('path').attr('class','tau-node-label-leader').attr('display','none');
          const label = group.append('g').attr('class', 'tau-star-node-label' + (node.type === 'stage' ? ' tau-stage-label' : node.type === 'landmark' ? ' tau-landmark-label' : ''));
          const lines = wrapText(node.label, 26, 3);
          const labelWidth=Math.max(70,Math.min(184,Math.round(Math.max(...lines.map(line=>line.length))*6.4+16)));
          node.labelBox={w:labelWidth,h:lines.length*15+24};
          label.append('rect').attr('x', -6).attr('y', -15).attr('width', labelWidth).attr('height', lines.length*15+24).attr('rx', 3);
          const text = label.append('text');
          lines.forEach((line, i) => text.append('tspan').attr('x', 0).attr('y', i*15).text(line));
          label.append('text').attr('x', 0).attr('y', lines.length*15+7).style('font-size', '10px')
            .style('fill', hasProgress(node) ? nodeAccent(node) : '#8391a0').text(node.type === 'landmark' ? (node.landmarkKind || 'Mathematical landmark') : progressDescription(node) || '');
          group.append('title').text([normalizeText(node.label),progressDescription(node),'Click to inspect · Double-click to open'].filter(Boolean).join('\n'));
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
        .attr('stroke', edge => edge.source.id === selected || edge.target.id === selected ? ACCENT : '#7d8a99')
        .attr('stroke-width', edge => edge.source.id === selected || edge.target.id === selected ? 2.1 : this.layout==='constellations'?1.15:1.3)
        .attr('marker-end', edge => /contains|reference/.test(edge.kind) ? null : 'url(#' + this.id + '-arrow-' + (edge.source.id === selected || edge.target.id === selected ? 'highlight' : 'normal') + ')');
      this.edgeSelection.filter(edge => edge.source.id === selected || edge.target.id === selected).raise();
      this.updateConstellationLabels();
      return this;
    }

    bounds() {
      if (!this.nodes.length) return { x: 0, y: 0, w: 100, h: 100 };
      // Each heading travels with its cloud. Bounds include all of the free
      // positions without reinstating a row or column arrangement.
      if(this.layout==='constellations'&&this.constellationBounds){const b=this.constellationBounds;return {x:b.x-30,y:b.y-30,w:b.w+60,h:b.h+60};}
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
      const bottomReserve=this.layout==='constellations'&&(this.width<600||this.height<300)?60:0;
      const usableHeight=this.height-bottomReserve;
      const scale = Math.max(.025, Math.min(1.15, (this.width - 36) / box.w, (usableHeight - 36) / box.h));
      const transform = d3.zoomIdentity.translate(this.width / 2 - (box.x + box.w / 2) * scale, usableHeight / 2 - (box.y + box.h / 2) * scale).scale(scale);
      this.semantic.fitScale=scale;this.semantic.diveThreshold=scale*2.35;this.semantic.ascendThreshold=scale*.68;
      this.semanticParentCamera={x:transform.x,y:transform.y,k:transform.k};
      if (animate) this.svg.transition().duration(160).call(this.zoom.transform, transform);
      else this.svg.call(this.zoom.transform, transform);
      return this;
    }

    focus(id) {
      const node = this.nodeMap.get(id);
      if (!node) return this;
      this.select(id);
      const scale = Math.max(.65, Math.min(1.4, this.transform.k));
      const transform = d3.zoomIdentity.translate(this.width / 2 - node.x * scale, this.height / 2 - node.y * scale).scale(scale);
      this.svg.transition().duration(180).call(this.zoom.transform, transform);
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
      background = background || BACKGROUND;
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
      return { nodes: this.nodes.length, edges: this.edges.length, constellationLinks: this.constellationLinks.length, constellationSubjects: this.constellationSubjects.length, groupConnections: this.groupConnections || [], sectorRoutes:(this.sectorRoutes||[]).map(({source,target,dependencies,witnesses,shape,strong})=>({source,target,dependencies,witnesses,shape,strong:!!strong})), arrangement:this.layout==='constellations'?'organic':null,subjects:this.constellationSubjects.map(subject=>({label:subject.label,x:subject.x,y:subject.y,sector:subject.sector,caption:subject.screenCaption||null})),
        clicksSuppressed: Date.now() < this.suppressClicksUntil, hoveredSubject: this.hoveredSubject || null,
        links: this.constellationLinks.map(link => ({group:link.group,sourceEdge:link.sourceEdge,source:{x:link.source.x,y:link.source.y},target:{x:link.target.x,y:link.target.y}})), layout: this.layout, selectedId: this.selectedId, semantic:{...this.semantic,canAscend:this.canAscend},orbits:(this.orbits||[]).length,
        width: this.width, height: this.height, transform: { x: this.transform.x, y: this.transform.y, k: this.transform.k },
        positions: this.nodes.map(node => ({ id: node.id, x: node.x, y: node.y, w: node.w, h: node.h, rank: node.rank == null ? null : node.rank, dependencyRank: node.rank == null ? null : node.rank, dependencyOrderValid: node.dependencyOrderValid, caption: node.screenCaption || null, galaxyName:node.galaxyName||null,galaxyNameVisible:this.layout==='constellations'&&node.galaxyNameVisible===true,galaxyNameFont:node.galaxyNameFont||null,galaxyNameScreenFont:node.galaxyNameScreenFont||null,galaxyNameBox:node.galaxyNameBox||null,progress: progressValue(node.progress), hasProgress: hasProgress(node), accent: nodeAccent(node) })) };
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
