/* Continuous navigation between the atlas, a roadmap and a layer's planets. */
(function () {
  'use strict';
  const Graph = window.TauGraph;
  const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

  Graph.prototype.captureCamera = function () {
    return { x: this.transform.x, y: this.transform.y, k: this.transform.k,
      width: this.width, height: this.height };
  };

  Graph.prototype.restoreCamera = function (camera) {
    if (!camera || ![camera.x, camera.y, camera.k].every(Number.isFinite) || camera.k <= 0) return this;
    this.svg.interrupt();
    const x = camera.x + (this.width - (camera.width || this.width)) / 2;
    const y = camera.y + (this.height - (camera.height || this.height)) / 2;
    this.semanticReadyAt = Date.now() + 450;
    this.svg.call(this.zoom.transform, d3.zoomIdentity.translate(x, y).scale(camera.k));
    return this;
  };

  Graph.prototype.handleSemanticZoom = function (event) {
    const scale = this.transform.k;
    const previous = this._semanticPreviousScale || scale;
    this._semanticPreviousScale = scale;
    if (!event || this.semantic.busy || Date.now() < this.semanticReadyAt || !this.isSkyLayout) return;
    const touch = event.type.startsWith('touch');
    if (touch && (!event.touches || event.touches.length < 2)) return;
    if (!touch && event.type !== 'wheel' && event.type !== 'toolbar') return;
    const change = scale - previous;
    const direction = event.type === 'toolbar' ? -Math.sign(event.deltaY) :
      Math.abs(change) > previous * .001 ? Math.sign(change) : 0;
    if (!direction) return;
    if (direction < 0 && this.canAscend && scale < this.semantic.ascendThreshold) {
      this.ascend();
      return;
    }
    if (direction < 0 || scale < this.semantic.diveThreshold || this.layout === 'solar-system') return;
    const type = this.layout === 'constellations' ? 'roadmap' : 'stage';
    const svg = this.svg.node(), bounds = svg.getBoundingClientRect();
    const localPoint = (x, y) => {
      const point = svg.createSVGPoint(); point.x = x; point.y = y;
      const matrix = svg.getScreenCTM();
      return matrix ? point.matrixTransform(matrix.inverse()) : { x: x - bounds.left, y: y - bounds.top };
    };
    let point = { x: this.width / 2, y: this.height / 2 };
    if (touch) {
      const fingers = Array.from(event.touches);
      point = localPoint(fingers.reduce((sum, finger) => sum + finger.clientX, 0) / fingers.length,
        fingers.reduce((sum, finger) => sum + finger.clientY, 0) / fingers.length);
    } else if (Number.isFinite(event.clientX) && Number.isFinite(event.clientY)) {
      point = localPoint(event.clientX, event.clientY);
    }
    let candidate = null, distance = Infinity;
    for (const node of this.nodes) {
      if (node.type !== type || node.unmapped) continue;
      const x = node.x * scale + this.transform.x, y = node.y * scale + this.transform.y;
      const d = Math.hypot(x - point.x, y - point.y);
      if (d < distance) { candidate = node; distance = d; }
    }
    const reach = Math.max(touch ? 90 : 65, (candidate?.radius || 14) * scale * 2.5);
    if (candidate && distance < reach) this.dive(candidate.id);
  };

  Graph.prototype.travel = function (direction, node, destination, complete) {
    if (this.semantic.busy) return this;
    this.svg.interrupt();
    const parentCamera = this.captureCamera();
    this.semantic.busy = true;
    this.semantic.lastAction = direction === 'in' ? 'dive' : 'ascend';
    this.options.onTravel?.({ direction, node, parentCamera });
    let finished = false;
    const settle = (arrived) => {
      if (finished) return;
      finished = true;
      this.semantic.busy = false;
      this.semanticReadyAt = Date.now() + 450;
      if (arrived) complete(parentCamera);
      this.options.onSettled?.();
    };
    if (reducedMotion()) {
      this.svg.call(this.zoom.transform, destination);
      settle(true);
    } else {
      this.svg.transition().duration(direction === 'in' ? 650 : 420)
        .ease(d3.easeCubicInOut).call(this.zoom.transform, destination)
        .on('end.cosmic', () => settle(true))
        .on('interrupt.cosmic', () => settle(false));
    }
    return this;
  };

  Graph.prototype.dive = function (id) {
    const node = this.nodeMap.get(id);
    if (!node || this.semantic.busy || node.unmapped || !this.options.onDive) return this;
    if (!(this.layout === 'constellations' && node.type === 'roadmap') &&
        !(this.layout === 'layer-constellations' && node.type === 'stage')) return this;
    const radius = node.type === 'roadmap' ? 55 : node.radius || 14;
    const scale = Math.max(this.transform.k * 1.8, Math.min(this.width, this.height) * .78 / (radius * 2));
    const destination = d3.zoomIdentity.translate(this.width / 2 - node.x * scale,
      this.height / 2 - node.y * scale).scale(scale);
    this.select(id);
    return this.travel('in', node, destination, parentCamera => this.options.onDive(node, { parentCamera }));
  };

  Graph.prototype.ascend = function () {
    if (!this.canAscend || this.semantic.busy || !this.options.onAscend) return this;
    const scale = Math.max(.005, this.semantic.fitScale * .2);
    const cx = (this.width / 2 - this.transform.x) / this.transform.k;
    const cy = (this.height / 2 - this.transform.y) / this.transform.k;
    const destination = d3.zoomIdentity.translate(this.width / 2 - cx * scale,
      this.height / 2 - cy * scale).scale(scale);
    return this.travel('out', null, destination, parentCamera => this.options.onAscend({ parentCamera }));
  };

  function zoomFromControl(graph, factor) {
    if (graph.semantic.busy) return graph;
    const check = () => graph.handleSemanticZoom({ type: 'toolbar', deltaY: factor > 1 ? -1 : 1 });
    if (reducedMotion()) { graph.svg.call(graph.zoom.scaleBy, factor); check(); }
    else graph.svg.transition().duration(180).call(graph.zoom.scaleBy, factor).on('end.semantic', check);
    return graph;
  }
  Graph.prototype.zoomIn = function () { return zoomFromControl(this, 1.4); };
  Graph.prototype.zoomOut = function () { return zoomFromControl(this, 1 / 1.4); };
})();
