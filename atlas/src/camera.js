/* Camera routes through the universe: the address-bar view is a place the
   camera can travel to, and the parent of any place is the next larger one. */
(function () {
  'use strict';
  const Graph = window.TauGraph;

  // Travel to the object a view names. A collection of roadmaps is the box
  // around its child constellations; the whole atlas is everything.
  Graph.prototype.zoomToView = function (view, animate) {
    if (!this.universe) return this;
    if (view.layer && this.universe.byId.has(view.layer)) return this.zoomTo(view.layer, animate);
    if (view.id && this.universe.byId.has(view.id)) return this.zoomTo(view.id, animate);
    if (view.ids && view.ids.length) {
      const nodes = view.ids.map(id => this.universe.byId.get(id)).filter(Boolean);
      if (nodes.length) {
        const left = Math.min(...nodes.map(n => n.x - (n.r || 20))), right = Math.max(...nodes.map(n => n.x + (n.r || 20)));
        const top = Math.min(...nodes.map(n => n.y - (n.r || 20) * 1.3)), bottom = Math.max(...nodes.map(n => n.y + (n.r || 20)));
        return this.travel(this.transformFor({ x: left - 20, y: top - 20, w: right - left + 40, h: bottom - top + 40 }), animate !== false);
      }
    }
    return this.fitAll(animate);
  };

  // One step outward: a star's constellation, a constellation's galaxy, or
  // the whole universe.
  Graph.prototype.parentOf = function (id) {
    const node = this.universe && this.universe.byId.get(id);
    if (!node) return null;
    if (node.level === 'planet') return node.starId;
    if (node.level === 'star') return node.constellationId;
    if (node.level === 'constellation') return node.galaxyId;
    return null;
  };
})();
