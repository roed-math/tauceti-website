/* One continuous world for the atlas: galaxies are mathematical areas,
   constellations are roadmaps, stars are layers and planets are the
   definitions, theorems and constructions of a layer. Every object has a
   position and a size in the same coordinate system, so the camera can
   travel from the whole universe to a single planet without a layout change. */
(function () {
  'use strict';
  const GOLDEN = Math.PI * (3 - Math.sqrt(5));
  const hash = text => Array.from(String(text)).reduce((seed, character) => ((seed * 31 + character.charCodeAt(0)) >>> 0), 7);

  function placeGalaxies(galaxies, links, aspect) {
    if (!galaxies.length) return;
    const chartW = 5200 * Math.max(.42, Math.min(1, aspect / 1.5)), chartH = Math.max(2200, Math.min(7000, chartW / Math.max(.42, Math.min(2.6, aspect))));
    const gap = aspect < 1 ? 110 : 150;
    const meanCount = galaxies.reduce((sum, galaxy) => sum + galaxy.count, 0) / galaxies.length;
    galaxies.forEach(galaxy => { galaxy.areaWeight = .42 + .58 * Math.sqrt(galaxy.count / Math.max(1, meanCount)); });
    const totalWeight = galaxies.reduce((sum, galaxy) => sum + galaxy.areaWeight, 0);
    // Each area starts in its own direction, the same one it has in the radial layout.
    const seeds = galaxies.map((galaxy, index) => {
      const angle = (Number.isFinite(galaxy.direction) ? galaxy.direction : index * 360 / galaxies.length) * Math.PI / 180;
      return [Math.cos(angle) * 900, Math.sin(angle) * 650];
    });
    const minX = Math.min(...seeds.map(p => p[0])), maxX = Math.max(...seeds.map(p => p[0]));
    const minY = Math.min(...seeds.map(p => p[1])), maxY = Math.max(...seeds.map(p => p[1]));
    galaxies.forEach((galaxy, index) => {
      const seed = seeds[index], variation = .9 + (hash(galaxy.label) % 101) / 500;
      const area = chartW * chartH * .46 * galaxy.areaWeight / totalWeight;
      const shape = (aspect > 1.4 ? 1.32 : .96) * variation;
      galaxy.w = galaxies.length === 1 ? chartW : Math.max(420, Math.sqrt(area * shape));
      galaxy.h = galaxies.length === 1 ? chartH : Math.max(260, area / galaxy.w);
      galaxy.seedX = ((seed[0] - minX) / Math.max(1, maxX - minX) - .5) * chartW * .78 + ((hash(galaxy.label + '|x') % 1000) / 1000 - .5) * galaxy.w * .2;
      galaxy.seedY = ((seed[1] - minY) / Math.max(1, maxY - minY) - .5) * chartH * .78 + ((hash(galaxy.label + '|y') % 1000) / 1000 - .5) * galaxy.h * .2;
      galaxy.x = galaxy.seedX; galaxy.y = galaxy.seedY;
    });
    const byId = new Map(galaxies.map(galaxy => [galaxy.id, galaxy]));
    const degree = new Map(galaxies.map(galaxy => [galaxy.id, 0]));
    links.forEach(link => { const weight = Math.log1p(link.weight); degree.set(link.source, degree.get(link.source) + weight); degree.set(link.target, degree.get(link.target) + weight); });
    for (let pass = 0; pass < 240; pass++) {
      if (pass < 170) {
        galaxies.forEach(galaxy => { galaxy.x += (galaxy.seedX - galaxy.x) * .025; galaxy.y += (galaxy.seedY - galaxy.y) * .025; });
        links.forEach(link => {
          const a = byId.get(link.source), b = byId.get(link.target), weight = Math.log1p(link.weight);
          if (!a || !b) return;
          const dx = b.x - a.x, dy = b.y - a.y, strength = .016 * weight / Math.max(1, degree.get(a.id), degree.get(b.id));
          a.x += dx * strength; a.y += dy * strength; b.x -= dx * strength; b.y -= dy * strength;
        });
      }
      let moved = false;
      galaxies.forEach((a, index) => galaxies.slice(index + 1).forEach(b => {
        let dx = b.x - a.x, dy = b.y - a.y;
        const width = (a.w + b.w) / 2 + gap, height = (a.h + b.h) / 2 + gap;
        if (Math.abs(dx) >= width || Math.abs(dy) >= height) return;
        if (Math.hypot(dx, dy) < .001) { const angle = (hash(a.label + b.label) % 360) * Math.PI / 180; dx = Math.cos(angle); dy = Math.sin(angle); }
        const separation = Math.max(Math.abs(dx) / width, Math.abs(dy) / height);
        const distance = (1 / Math.max(.001, separation) - 1) * .505;
        a.x -= dx * distance; a.y -= dy * distance; b.x += dx * distance; b.y += dy * distance; moved = true;
      }));
      if (pass >= 170 && !moved) break;
    }
    galaxies.forEach(galaxy => { galaxy.rx = galaxy.w / 2; galaxy.ry = galaxy.h / 2; });
  }

  // The radial layout: Mathlib is a small sun at the centre. A galaxy
  // lies farther out the more theory its roadmaps must build before their
  // targets can be stated and proved (their mean distance from Mathlib, on a
  // 0-10 scale), in a direction chosen so that related subjects are
  // neighbours. Overlaps are resolved by turning galaxies around the core,
  // so distance from the centre keeps its meaning.
  const CORE_RADIUS = 60;
  const RESULT_SCALE = { theorem: 1.25, lemma: 1.1, comparison: 1.1, application: 1.1 };
  const REFERENCE_ASPECT = 1204 / 782;
  const GALAXY_GAP = 150;
  // Distance from the centre grows faster than the distance score, so the
  // subjects farthest from Mathlib stand clearly apart from the rest.
  // Galaxies and the roadmaps in them are given room enough to read each roadmap apart from its neighbours.
  const radiusFor = distance => 560 + 200 * distance + 36 * distance * distance;
  const galaxySize = count => 190 + 112 * Math.sqrt(Math.max(1, count));
  // A roadmap's circle grows with its layers, so its figure can be read where its galaxy is in view.
  const constellationSize = (constellation, layers) => constellation.unmapped ? 14 : 12 + 6.5 * Math.sqrt(layers);
  const turn = angle => Math.atan2(Math.sin(angle), Math.cos(angle));

  function placeGalaxiesRadial(galaxies, constellationsOf, aspect) {
    if (!galaxies.length) return;
    // A wide chart spreads the universe sideways and a tall one upward; the
    // orientation never changes, so the map reads the same on every screen.
    const spread = aspect >= 1 ? Math.sqrt(aspect) : Math.pow(aspect, .75);
    const sx = Math.max(.6, Math.min(1.9, spread)), sy = 1 / Math.max(.6, Math.min(1.6, spread));
    galaxies.forEach((galaxy, index) => {
      const known = constellationsOf(galaxy).map(c => c.distance).filter(d => Number.isFinite(d));
      galaxy.distance = known.length ? known.reduce((a, b) => a + b, 0) / known.length : 5;
      galaxy.size = galaxySize(galaxy.count);
      galaxy.w = galaxy.size * 1.08; galaxy.h = galaxy.size * .86;
      galaxy.targetRadius = Math.max(CORE_RADIUS * 3.6 + galaxy.size / 2, radiusFor(galaxy.distance));
      galaxy.preferred = (Number.isFinite(galaxy.direction) ? galaxy.direction : index * 360 / galaxies.length) * Math.PI / 180;
      galaxy.angle = galaxy.preferred; galaxy.radius = galaxy.targetRadius;
    });
    const place = galaxy => { galaxy.x = Math.cos(galaxy.angle) * galaxy.radius * sx; galaxy.y = Math.sin(galaxy.angle) * galaxy.radius * sy; };
    galaxies.forEach(place);
    for (let pass = 0; pass < 600; pass++) {
      let overlapping = false;
      galaxies.forEach((a, index) => galaxies.slice(index + 1).forEach(b => {
        let dx = b.x - a.x, dy = b.y - a.y;
        const distance = Math.hypot(dx, dy), needed = (a.size + b.size) / 2 + GALAXY_GAP;
        if (distance >= needed) return;
        overlapping = true;
        if (distance < .001) { dx = Math.cos(a.angle + Math.PI / 2); dy = Math.sin(a.angle + Math.PI / 2); }
        const push = (needed - Math.max(distance, .001)) / 2 / Math.max(distance, .001);
        // Split each push into a turn about the core and a small radial step.
        [[a, -1], [b, 1]].forEach(([galaxy, sign]) => {
          const px = dx * push * sign, py = dy * push * sign;
          const ux = Math.cos(galaxy.angle), uy = Math.sin(galaxy.angle);
          const radial = px * ux + py * uy, tangential = -px * uy + py * ux;
          galaxy.angle += tangential / Math.max(1, galaxy.radius);
          galaxy.radius += radial * .3;
        });
      }));
      galaxies.forEach(galaxy => {
        galaxy.radius += (galaxy.targetRadius - galaxy.radius) * .06;
        galaxy.angle += turn(galaxy.preferred - galaxy.angle) * .01;
        galaxy.radius = Math.max(galaxy.radius, CORE_RADIUS * 3.6 + galaxy.size / 2);
        place(galaxy);
      });
      if (!overlapping && pass > 60) break;
    }
    galaxies.forEach(galaxy => { galaxy.rx = galaxy.w / 2; galaxy.ry = galaxy.h / 2; });
  }

  // The sector layout (the published pages). Each galaxy is a contiguous sector of the circle round Mathlib (its
  // `sector`, in degrees), and each roadmap lies exactly as far out as its distance from Mathlib, on one scale for
  // the whole map, at the angle in its sector nearest its share of the sector that is clear of the roadmaps already
  // placed, as in a beeswarm plot. Only when no angle is clear does a roadmap step out or in, by at most half a
  // unit of distance. The map is wider than a screen: the reader explores it.
  const SECTOR_CORE = 1200, SECTOR_STEP = 560, SECTOR_NUDGE = 35;
  const sectorRadius = distance => SECTOR_CORE + SECTOR_STEP * Math.max(0, Math.min(10, distance));
  const NUDGES = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7, 8, -8];
  const GOLDEN_SHARE = (Math.sqrt(5) - 1) / 2;

  // Each sector's span: from the rule before it to the rule after it, halfway across the gaps between sectors. A sector's
  // tint and dust fill its span, so that neighbouring sectors meet at the line between them with no empty strip along
  // it (the user, 2026-10-26: "I dont like that it leaves a gap between the lines"); its roadmaps keep to the sector.
  function spans(sectors) {
    const order = sectors.slice().sort((a, b) => a.a0 - b.a0), found = new Map();
    order.forEach((s, index) => {
      const before = order[(index + order.length - 1) % order.length], after = order[(index + 1) % order.length];
      found.set(s.id, [((index ? before.a1 : before.a1 - Math.PI * 2) + s.a0) / 2, (s.a1 + (index < order.length - 1 ? after.a0 : after.a0 + Math.PI * 2)) / 2]);
    });
    return found;
  }

  function placeSectors(galaxies, constellationsOf, span, rim) {
    const cell = 200, grid = new Map(), key = (x, y) => Math.floor(x / cell) + ',' + Math.floor(y / cell);
    const crowding = (x, y, c) => {
      let worst = 0;
      const cx = Math.floor(x / cell), cy = Math.floor(y / cell);
      for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) (grid.get((cx + i) + ',' + (cy + j)) || []).forEach(o => {
        worst = Math.max(worst, (c.wanted + o.wanted) * 1.25 + 24 - Math.hypot(o.x - x, o.y - y));
      });
      return worst;
    };
    const queue = [];
    galaxies.forEach(galaxy => {
      [galaxy.a0, galaxy.a1] = galaxy.sector.map(degrees => degrees * Math.PI / 180);
      const members = constellationsOf(galaxy), known = members.map(c => c.distance).filter(Number.isFinite);
      galaxy.distance = known.length ? known.reduce((a, b) => a + b, 0) / known.length : 5;
      members.forEach(c => {
        c.wanted = constellationSize(c, c.starIds.length);
        c.r = Math.max(8, Math.min(64, c.wanted));
        c.target = sectorRadius(Number.isFinite(c.distance) ? c.distance : galaxy.distance);
        queue.push([galaxy, c]);
      });
    });
    // The nearest roadmaps first, where the circle is shortest; each sector shares its width out by the golden ratio.
    queue.sort((p, q) => p[1].target - q[1].target || p[1].id.localeCompare(q[1].id));
    const turn = new Map();
    queue.forEach(([galaxy, c]) => {
      const index = turn.get(galaxy.id) || 0, span = galaxy.a1 - galaxy.a0;
      turn.set(galaxy.id, index + 1);
      const preferred = galaxy.a0 + span * ((index * GOLDEN_SHARE + .5) % 1);
      let best = null;
      search: for (const nudge of NUDGES) {
        // Never nearer Mathlib than distance 0.
        const radius = c.target + nudge * SECTOR_NUDGE;
        if (radius < SECTOR_CORE) continue;
        const margin = (c.r + 12) / radius, low = Math.min(galaxy.a0 + margin, (galaxy.a0 + galaxy.a1) / 2), high = Math.max(galaxy.a1 - margin, low);
        const step = Math.max(.0015, c.r * .45 / radius), start = Math.max(low, Math.min(high, preferred));
        for (let k = 0; k * step <= high - low + step; k++) {
          for (const sign of k ? [1, -1] : [1]) {
            const angle = start + sign * k * step;
            if (angle < low - 1e-9 || angle > high + 1e-9) continue;
            const x = Math.cos(angle) * radius, y = Math.sin(angle) * radius, crowd = crowding(x, y, c);
            if (!best || crowd < best.crowd - 1e-6) best = { x, y, crowd, angle, radius };
            if (crowd <= 0) break search;
          }
        }
      }
      Object.assign(c, { x: best.x, y: best.y, angle: best.angle, radius: best.radius });
      const at = key(c.x, c.y);
      if (!grid.has(at)) grid.set(at, []);
      grid.get(at).push(c);
    });
    queue.forEach(([, c]) => {
      let nearest = Infinity;
      const cx = Math.floor(c.x / cell), cy = Math.floor(c.y / cell);
      for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) (grid.get((cx + i) + ',' + (cy + j)) || []).forEach(o => { if (o !== c) nearest = Math.min(nearest, Math.hypot(o.x - c.x, o.y - c.y)); });
      c.spacing = Number.isFinite(nearest) ? nearest : 2 * cell;
    });
    galaxies.forEach(galaxy => {
      const members = constellationsOf(galaxy), radii = members.map(c => Math.hypot(c.x, c.y));
      // With the Mathlib disk, every sector starts at its rim, so the disk ends where the sectors begin (the user,
      // 2026-10-26); without it, a little inside its nearest roadmap.
      galaxy.r0 = Number.isFinite(rim) ? rim : Math.max(CORE_RADIUS * 2.4, Math.min(...radii.map((r, i) => r - members[i].r)) - 60);
      galaxy.r1 = Math.max(...radii.map((r, i) => r + members[i].r)) + 60;
      galaxy.hubRadius = radii.slice().sort((a, b) => a - b)[Math.floor(radii.length / 2)];
      wedgeBounds(galaxy);
      [galaxy.b0, galaxy.b1] = span.get(galaxy.id) || [galaxy.a0, galaxy.a1];
      galaxy.outline = wedgePath(galaxy.r0, galaxy.r1, galaxy.b0, galaxy.b1);
      // From its outer end inwards; then, as a last resort when the middle of the map is full, a little beyond its
      // outer end, still on its middle line, where the map is open: the crowded upper half of the overview had ten
      // categories waiting for a name on 2026-10-25, functional analysis (16 roadmaps) among them.
      galaxy.labelSpots = [...spotsAlong((galaxy.a0 + galaxy.a1) / 2, galaxy.r1 + 30, galaxy.r0 - 30, galaxy.a1 - galaxy.a0),
        ...spotsAlong((galaxy.a0 + galaxy.a1) / 2, galaxy.r1 + 1500, galaxy.r1 + 270, 0).reverse()];
    });
  }

  // A sector's bounding box, centre and half-extents, as the camera frames a galaxy.
  function wedgeBounds(item) {
    const angles = [item.a0, item.a1];
    for (let quarter = Math.ceil(item.a0 / (Math.PI / 2)); quarter * Math.PI / 2 < item.a1; quarter++) angles.push(quarter * Math.PI / 2);
    const xs = [], ys = [];
    angles.forEach(angle => [item.r0, item.r1].forEach(radius => { xs.push(Math.cos(angle) * radius); ys.push(Math.sin(angle) * radius); }));
    const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
    Object.assign(item, { x: (left + right) / 2, y: (top + bottom) / 2, rx: (right - left) / 2, ry: (bottom - top) / 2, w: right - left, h: bottom - top });
  }

  function wedgePath(inner, outer, from, to) {
    const point = (radius, angle) => `${(Math.cos(angle) * radius).toFixed(1)},${(Math.sin(angle) * radius).toFixed(1)}`, large = to - from > Math.PI ? 1 : 0;
    return `M${point(inner, from)}L${point(outer, from)}A${outer.toFixed(1)},${outer.toFixed(1)} 0 ${large} 1 ${point(outer, to)}L${point(inner, to)}A${inner.toFixed(1)},${inner.toFixed(1)} 0 ${large} 0 ${point(inner, from)}Z`;
  }

  // Places for a sector's name along its middle, from its outer end inwards: the name takes the first one in view
  // with room, so it stays with the sector wherever the reader is along it.
  function spotsAlong(angle, outer, inner, width = 0) {
    const count = Math.max(2, Math.min(24, Math.ceil((outer - inner) / 240) + 1)), spots = [];
    const anchor = Math.cos(angle) > .3 ? 'start' : Math.cos(angle) < -.3 ? 'end' : 'middle', above = Math.sin(angle) < 0;
    for (let i = 0; i < count; i++) {
      const radius = outer - (outer - inner) * i / (count - 1);
      // On the middle line, then a little to either side of it within the sector.
      [0, .3, -.3].forEach(side => {
        const turn = angle + side * width / 2;
        if (!side || width * radius > 160) spots.push({ x: Math.cos(turn) * radius, y: Math.sin(turn) * radius, above, anchor });
      });
    }
    return spots;
  }

  // A sector's dust: most of it gathered round its roadmaps, the rest spread thinly over the whole sector.
  function sectorDust(galaxy, members) {
    let seed = hash(galaxy.label + '|dust') || 1;
    const random = () => { seed = (seed + 0x6D2B79F5) >>> 0; let t = seed; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const inside = (x, y) => { let angle = Math.atan2(y, x); while (angle < galaxy.b0) angle += Math.PI * 2; const radius = Math.hypot(x, y); return angle <= galaxy.b1 && radius >= galaxy.r0 && radius <= galaxy.r1; };
    const count = Math.max(320, Math.min(900, 240 + 18 * galaxy.count)), points = [];
    let guard = 0;
    while (points.length < count && guard++ < count * 6) {
      if (members.length && random() < .6) {
        const c = members[Math.floor(random() * members.length)], spread = c.r * (1.3 + 1.7 * Math.pow(random(), 1.4)), angle = random() * Math.PI * 2;
        const x = c.x + Math.cos(angle) * spread, y = c.y + Math.sin(angle) * spread, shine = random();
        if (inside(x, y)) points.push({ x, y, radial: spread / (c.r * 3), cls: spread < c.r * 1.8 && shine > .35 ? 2 : shine > .5 ? 1 : 0 });
      } else {
        const radius = Math.sqrt(galaxy.r0 * galaxy.r0 + random() * (galaxy.r1 * galaxy.r1 - galaxy.r0 * galaxy.r0)), angle = galaxy.b0 + random() * (galaxy.b1 - galaxy.b0);
        points.push({ x: Math.cos(angle) * radius, y: Math.sin(angle) * radius, radial: 1, cls: random() > .72 ? 1 : 0 });
      }
    }
    return points;
  }

  // Inside an area, a roadmap closer to Mathlib than the area's average sits
  // on the side facing the core, and a farther one on the outer side.
  function placeConstellationsRadial(galaxy, constellations) {
    const seed = hash(galaxy.label), rotation = (seed % 360) * Math.PI / 180;
    const length = Math.max(1, Math.hypot(galaxy.x, galaxy.y)), ux = galaxy.x / length, uy = galaxy.y / length;
    const rx = Math.max(40, galaxy.rx * .8), ry = Math.max(30, galaxy.ry * .8);
    constellations.forEach((constellation, index) => {
      const angle = index * GOLDEN + rotation;
      const spread = constellations.length === 1 ? 0 : Math.sqrt((index + .45) / constellations.length) * .86;
      const offset = Number.isFinite(constellation.distance) ? Math.max(-.62, Math.min(.62, (constellation.distance - galaxy.distance) * .16)) : 0;
      constellation.x = galaxy.x + Math.cos(angle) * rx * spread + ux * offset * rx;
      constellation.y = galaxy.y + Math.sin(angle) * ry * spread + uy * offset * ry;
    });
    constellations.forEach(constellation => {
      const n = constellation.starIds.length;
      constellation.wanted = constellationSize(constellation, n);
    });
    for (let pass = 0; pass < 200; pass++) {
      let moved = false;
      constellations.forEach((a, index) => constellations.slice(index + 1).forEach(b => {
        const dx = b.x - a.x, dy = b.y - a.y, distance = Math.max(.001, Math.hypot(dx, dy));
        const needed = (a.wanted + b.wanted) * 1.25 + 24;
        if (distance >= needed) return;
        const push = (needed - distance) / 2 / distance;
        a.x -= dx * push; a.y -= dy * push; b.x += dx * push; b.y += dy * push; moved = true;
      }));
      constellations.forEach(c => {
        const ex = (c.x - galaxy.x) / (galaxy.rx * .9), ey = (c.y - galaxy.y) / (galaxy.ry * .9), e = Math.hypot(ex, ey);
        if (e > 1) { c.x = galaxy.x + (c.x - galaxy.x) / e; c.y = galaxy.y + (c.y - galaxy.y) / e; }
      });
      if (!moved) break;
    }
    constellations.forEach(constellation => {
      let nearest = Infinity;
      constellations.forEach(other => { if (other !== constellation) nearest = Math.min(nearest, Math.hypot(other.x - constellation.x, other.y - constellation.y)); });
      constellation.spacing = Number.isFinite(nearest) ? nearest : Math.min(rx, ry);
      constellation.r = Math.max(8, Math.min(64, constellation.wanted, constellation.spacing * .48));
    });
  }

  function placeConstellations(galaxy, constellations) {
    const seed = hash(galaxy.label), rotation = (seed % 360) * Math.PI / 180;
    const rx = Math.max(40, galaxy.rx * .84), ry = Math.max(30, galaxy.ry * .72);
    constellations.forEach((constellation, index) => {
      const angle = index * GOLDEN + rotation;
      const distance = constellations.length === 1 ? 0 : Math.sqrt((index + .45) / constellations.length) * .94;
      constellation.x = galaxy.x + Math.cos(angle) * rx * distance;
      constellation.y = galaxy.y + Math.sin(angle) * ry * distance;
    });
    constellations.forEach(constellation => {
      let nearest = Infinity;
      constellations.forEach(other => { if (other !== constellation) nearest = Math.min(nearest, Math.hypot(other.x - constellation.x, other.y - constellation.y)); });
      constellation.spacing = Number.isFinite(nearest) ? nearest : Math.min(rx, ry);
      // Large roadmaps get proportionally more room, so their layers keep the
      // same spacing as a small roadmap's instead of being squeezed together.
      const wanted = constellationSize(constellation, constellation.starIds.length);
      constellation.r = Math.max(8, Math.min(64, wanted, constellation.spacing * .45));
    });
  }

  // Layers form a small constellation: prerequisites pull neighbours together,
  // repulsion keeps room for names, and the whole figure fits its radius.
  function placeStars(constellation, stars, edges) {
    if (!stars.length) return;
    const order = new Map(stars.map((star, index) => [star.id, index]));
    const indegree = new Map(stars.map(star => [star.id, 0])), outgoing = new Map(stars.map(star => [star.id, []]));
    const ranks = new Map(stars.map(star => [star.id, 0]));
    edges.forEach(edge => { outgoing.get(edge.source).push(edge.target); indegree.set(edge.target, indegree.get(edge.target) + 1); });
    const ready = stars.filter(star => !indegree.get(star.id)).map(star => star.id), visited = new Set();
    while (ready.length) {
      ready.sort((a, b) => order.get(a) - order.get(b));
      const id = ready.shift(); visited.add(id);
      outgoing.get(id).forEach(target => { ranks.set(target, Math.max(ranks.get(target), ranks.get(id) + 1)); indegree.set(target, indegree.get(target) - 1); if (!indegree.get(target)) ready.push(target); });
    }
    stars.forEach(star => { star.rank = ranks.get(star.id); star.dependencyOrderValid = visited.has(star.id); });
    const sorted = stars.slice().sort((a, b) => a.rank - b.rank || order.get(a.id) - order.get(b.id));
    const maxRank = Math.max(1, ...stars.map(star => star.rank)), spread = Math.max(190, Math.sqrt(stars.length) * 105);
    sorted.forEach((star, index) => {
      const angle = index * GOLDEN + .4, radius = spread * Math.sqrt((index + .6) / Math.max(1, stars.length));
      star.lx = Math.cos(angle) * radius * 1.38 + (star.rank / maxRank - .5) * 190; star.ly = Math.sin(angle) * radius * .82;
      star.seedX = star.lx; star.seedY = star.ly;
    });
    const byId = new Map(stars.map(star => [star.id, star]));
    for (let step = 0; step < 140; step++) {
      const force = new Map(stars.map(star => [star.id, { x: (star.seedX - star.lx) * .008, y: (star.seedY - star.ly) * .008 }]));
      edges.forEach(edge => {
        const a = byId.get(edge.source), b = byId.get(edge.target), dx = b.lx - a.lx, dy = b.ly - a.ly, length = Math.max(1, Math.hypot(dx, dy)), pull = (length - 300) * .016;
        force.get(a.id).x += dx / length * pull; force.get(a.id).y += dy / length * pull; force.get(b.id).x -= dx / length * pull; force.get(b.id).y -= dy / length * pull;
      });
      stars.forEach((a, index) => stars.slice(index + 1).forEach(b => {
        let dx = b.lx - a.lx, dy = b.ly - a.ly; if (!dx && !dy) dx = .01;
        const length = Math.max(.01, Math.hypot(dx / 1.35, dy / .8)), push = Math.max(0, 255 - length) * .13;
        force.get(a.id).x -= dx / length * push; force.get(a.id).y -= dy / length * push; force.get(b.id).x += dx / length * push; force.get(b.id).y += dy / length * push;
      }));
      stars.forEach(star => { star.lx += force.get(star.id).x; star.ly += force.get(star.id).y; });
    }
    const cx = stars.reduce((sum, star) => sum + star.lx, 0) / stars.length, cy = stars.reduce((sum, star) => sum + star.ly, 0) / stars.length;
    const extent = Math.max(1, ...stars.map(star => Math.hypot(star.lx - cx, star.ly - cy)));
    const scale = stars.length === 1 ? 0 : constellation.r * .82 / extent;
    stars.forEach(star => { star.x = constellation.x + (star.lx - cx) * scale; star.y = constellation.y + (star.ly - cy) * scale; delete star.lx; delete star.ly; delete star.seedX; delete star.seedY; });
    stars.forEach(star => {
      let nearest = Infinity;
      stars.forEach(other => { if (other !== star) nearest = Math.min(nearest, Math.hypot(other.x - star.x, other.y - star.y)); });
      star.nearest = Number.isFinite(nearest) ? nearest : constellation.r;
      // A star and its planetary system never reach a neighbour: both are
      // bounded by the distance to the nearest other star, so a crowded
      // roadmap draws smaller systems that separate as the camera closes in.
      star.r = Math.max(.45, Math.min(3.2, constellation.r * .055, star.nearest * .15));
      star.room = star.planetIds.length ? Math.max(star.r * 2.4, Math.min(star.nearest * .44, constellation.r * .42)) : star.r * 2.2;
    });
  }

  // A constellation figure: the shortest tree through the stars that prefers
  // real prerequisites. Grouping segments are drawn fainter than real ones.
  function figureOf(stars, edges) {
    if (stars.length < 2) return [];
    const real = new Set(edges.map(edge => [edge.source, edge.target].sort().join('\n')));
    const connected = new Set(stars.slice(0, 1)), pending = new Set(stars.slice(1)), figure = [];
    while (pending.size) {
      let best = null, minimum = Infinity;
      connected.forEach(source => pending.forEach(target => {
        const isReal = real.has([source.id, target.id].sort().join('\n'));
        const distance = Math.hypot(source.x - target.x, source.y - target.y) * (isReal ? .2 : 1);
        if (distance < minimum) { minimum = distance; best = { source: source.id, target: target.id, real: isReal }; }
      }));
      figure.push(best); connected.add(stars.find(star => star.id === best.target)); pending.delete(stars.find(star => star.id === best.target));
    }
    return figure;
  }

  function placePlanets(star, planets) {
    // Rings are spaced so that neighbouring orbits never let two planets touch;
    // a crowded star simply gets more rings, and its room grows to hold them.
    const rings = [4, 7, 10, 13, 16, 19];
    const needed = Math.max(1, rings.findIndex((_, ring) => rings.slice(0, ring + 1).reduce((a, b) => a + b, 0) >= planets.length) + 1);
    if (!Number.isFinite(needed) || needed < 1) return;
    const step = star.room / (.62 + .4 * (needed - 1) + .3);
    let index = 0;
    rings.forEach((capacity, ring) => {
      const radius = step * (.62 + .4 * ring);
      const count = Math.min(capacity, planets.length - index);
      for (let slot = 0; slot < count; slot++, index++) {
        const planet = planets[index], angle = (slot / count) * Math.PI * 2 + ring * .7 + (hash(star.id) % 100) / 100;
        planet.x = star.x + Math.cos(angle) * radius; planet.y = star.y + Math.sin(angle) * radius * .82;
        planet.orbit = { rx: radius, ry: radius * .82, ring };
        // Results are drawn as ringed planets, a little larger than definitions.
        const scale = RESULT_SCALE[planet.kind] || 1;
        planet.r = Math.max(.3, Math.min(star.r * .62, step * .15, radius * Math.PI / Math.max(3, count) * .3)) * scale;
      }
    });
    // The closest pair of planets bounds every hit target of this system.
    let gap = Infinity;
    planets.forEach((a, i) => planets.slice(i + 1).forEach(b => { gap = Math.min(gap, Math.hypot(a.x - b.x, a.y - b.y)); }));
    star.planetGap = Number.isFinite(gap) ? gap : star.room;
  }

  // Seen from afar, an area is a galaxy: a field of faint stars, dense at
  // the centre and thinning outward, with two soft spiral arms. The field is
  // generated once per area, deterministically, and drawn as a few paths.
  function galaxyDust(galaxy) {
    let seed = hash(galaxy.label + '|dust') || 1;
    const random = () => { seed = (seed + 0x6D2B79F5) >>> 0; let t = seed; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const count = Math.max(320, Math.min(760, 260 + 14 * galaxy.count + 4 * galaxy.unmappedCount));
    const tilt = (hash(galaxy.label) % 360) * Math.PI / 180, phase = random() * Math.PI * 2, pitch = 2.4 + random() * 1.4;
    // The disc is seen at an inclination, so the field is flattened along
    // its tilt; a bright core, two arms and a thin halo give it depth.
    const flatten = .62 + (hash(galaxy.label + '|f') % 20) / 100;
    const points = [];
    let guard = 0;
    while (points.length < count && guard++ < count * 14) {
      const halo = random() < .12, radial = halo ? .85 + random() * .3 : Math.pow(random(), .88), angle = random() * Math.PI * 2;
      const arm = .5 + .5 * Math.cos(2 * angle - pitch * Math.log(1 + 4 * radial) + phase);
      if (!halo && random() > .22 + .78 * (radial < .16 ? 1 : arm)) continue;
      const ex = radial * galaxy.rx * .98 * Math.cos(angle), ey = radial * galaxy.ry * .98 * flatten * Math.sin(angle);
      const x = galaxy.x + ex * Math.cos(tilt) - ey * Math.sin(tilt), y = galaxy.y + ex * Math.sin(tilt) + ey * Math.cos(tilt);
      const shine = random();
      points.push({ x, y, radial, cls: halo ? 0 : radial < .28 && shine > .3 ? 2 : shine > .5 ? 1 : 0 });
    }
    return points;
  }

  function routesBetween(galaxies, constellations, edges) {
    const byConstellation = new Map(constellations.map(constellation => [constellation.id, constellation]));
    const routes = new Map();
    edges.forEach(edge => {
      const a = byConstellation.get(edge.source), b = byConstellation.get(edge.target);
      if (!a || !b || a.galaxyId === b.galaxyId) return;
      const pair = [a.galaxyId, b.galaxyId].sort(), key = pair.join('\n');
      if (!routes.has(key)) routes.set(key, { source: pair[0], target: pair[1], dependencies: 0, witnesses: [] });
      const route = routes.get(key); route.dependencies++; route.witnesses.push({ source: edge.source, target: edge.target });
    });
    const byGalaxy = new Map(galaxies.map(galaxy => [galaxy.id, galaxy]));
    const list = Array.from(routes.values()).map(route => {
      const a = byGalaxy.get(route.source), b = byGalaxy.get(route.target);
      // A route leaves from the rim of each galaxy, never across its roadmaps.
      const rim = (g, toward) => { if (g.sector) { const angle = (g.a0 + g.a1) / 2; return { x: Math.cos(angle) * g.hubRadius, y: Math.sin(angle) * g.hubRadius }; }
        const ex = toward.x - g.x, ey = toward.y - g.y, scale = 1 / Math.max(1e-6, Math.hypot(ex / g.rx, ey / g.ry)); return { x: g.x + ex * scale, y: g.y + ey * scale }; };
      const start = rim(a, b), end = rim(b, a);
      const dx = end.x - start.x, dy = end.y - start.y, length = Math.max(1, Math.hypot(dx, dy)), nx = -dy / length, ny = dx / length;
      const bend = ((hash(route.source + route.target) % 2) ? 1 : -1) * Math.min(length * .18, 320);
      const c1 = { x: start.x + dx * .3 + nx * bend, y: start.y + dy * .3 + ny * bend }, c2 = { x: start.x + dx * .7 + nx * bend, y: start.y + dy * .7 + ny * bend };
      return { ...route, path: `M${start.x},${start.y}C${c1.x},${c1.y} ${c2.x},${c2.y} ${end.x},${end.y}` };
    });
    const counts = list.map(route => route.dependencies).sort((a, b) => a - b);
    const threshold = counts.length ? Math.max(3, counts[Math.floor(counts.length * .65)]) : Infinity;
    list.forEach(route => { route.strong = route.dependencies >= threshold; });
    return list;
  }

  // The Mathlib disk (scripts/disk_layout.py): Mathlib's key definitions and theorems round the sun, each as far out
  // as the Mathlib it needs, in the sectors of its area. It is hidden until the sun is clicked (src/graph.js).
  const DISK_SPECKS = 7000;

  function buildDisk(data) {
    const rad = degrees => degrees * Math.PI / 180;
    const sectors = data.sectors.map(s => ({ id: 'disk:' + s.id, sectorId: s.id, label: s.label, short: s.short, code: s.code, field: s.field,
      a0: rad(s.a0), a1: rad(s.a1), items: s.items }));
    const items = data.items.map(row => ({ id: row.id, level: 'mathlib', name: row.n, title: row.t, kind: row.k, sector: row.s, tier: row.l,
      x: Math.cos(rad(row.a)) * row.r, y: Math.sin(rad(row.a)) * row.r, radius: row.r, importance: row.i,
      theorem: ['theorem', 'lemma'].includes(row.k) }));
    // The rest of Mathlib as dust: specks spread over each sector's bands, as many as it has there, up to DISK_SPECKS.
    const bySector = new Map(sectors.map(s => [s.sectorId, s])), bins = data.dust.bins, span = spans(sectors);
    const total = Object.values(data.dust.areas).reduce((sum, counts) => sum + counts.reduce((a, b) => a + b, 0), 0);
    const scale = Math.min(1, DISK_SPECKS / Math.max(1, total)), dust = [];
    let seed = 20261026;
    const random = () => { seed = (seed + 0x6D2B79F5) >>> 0; let x = seed; x = Math.imul(x ^ (x >>> 15), x | 1); x ^= x + Math.imul(x ^ (x >>> 7), x | 61); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
    Object.entries(data.dust.areas).forEach(([sid, counts]) => {
      const s = bySector.get(sid);
      if (!s) return;
      counts.forEach((count, bin) => {
        const r0 = data.inner + (data.outer - data.inner) * bin / bins, r1 = data.inner + (data.outer - data.inner) * (bin + 1) / bins;
        for (let n = Math.round(count * scale); n > 0; n--) {
          const [b0, b1] = span.get(s.id), radius = Math.sqrt(r0 * r0 + random() * (r1 * r1 - r0 * r0)), angle = b0 + random() * (b1 - b0), shine = random();
          dust.push({ x: Math.cos(angle) * radius, y: Math.sin(angle) * radius, cls: shine > .9 ? 2 : shine > .6 ? 1 : 0 });
        }
      });
    });
    return { inner: data.inner, outer: data.outer, commit: data.commit, max: data.max, sectors, items, dust };
  }

  function build(input, viewport) {
    const aspect = viewport && viewport.width && viewport.height ? viewport.width / viewport.height : 1.5;
    const galaxies = input.groups.map(group => ({ id: group.id, level: 'galaxy', label: group.label, short: group.short || '', caption: group.caption || null, code: group.arxiv || null, sector: Array.isArray(group.sector) ? group.sector : null, direction: group.direction, color: group.color, constellationIds: [], count: 0, unmappedCount: 0, progress: group.progress == null ? null : group.progress, progressLabel: group.progressLabel || '' }));
    const galaxyById = new Map(galaxies.map(galaxy => [galaxy.id, galaxy]));
    const constellations = input.constellations.map(item => ({ ...item, level: 'constellation', starIds: item.starIds || [] }))
      .filter(item => galaxyById.has(item.galaxyId));
    constellations.forEach(constellation => {
      const galaxy = galaxyById.get(constellation.galaxyId);
      galaxy.constellationIds.push(constellation.id);
      if (constellation.unmapped) galaxy.unmappedCount++; else galaxy.count++;
    });
    const populated = galaxies.filter(galaxy => galaxy.constellationIds.length);
    const galaxyLinks = new Map();
    input.constellationEdges.forEach(edge => {
      const a = constellations.find(item => item.id === edge.source), b = constellations.find(item => item.id === edge.target);
      if (!a || !b || a.galaxyId === b.galaxyId) return;
      const key = [a.galaxyId, b.galaxyId].sort().join('\n');
      if (!galaxyLinks.has(key)) galaxyLinks.set(key, { source: [a.galaxyId, b.galaxyId].sort()[0], target: [a.galaxyId, b.galaxyId].sort()[1], weight: 0 });
      galaxyLinks.get(key).weight += Math.sqrt(Math.max(1, edge.count || 1));
    });
    const constellationById = new Map(constellations.map(item => [item.id, item]));
    const radial = input.layout !== 'areas';
    const membersOf = galaxy => galaxy.constellationIds.map(id => constellationById.get(id)).sort((a, b) => a.id.localeCompare(b.id));
    // The Mathlib-centred map is the same on every screen: it is laid out for
    // a desktop chart, and a smaller screen shows part of it at the same scale.
    const sectored = radial && populated.length > 0 && populated.every(galaxy => galaxy.sector);
    if (sectored) placeSectors(populated, membersOf, spans(galaxies.filter(galaxy => Array.isArray(galaxy.sector))
      .map(galaxy => ({ id: galaxy.id, a0: galaxy.sector[0] * Math.PI / 180, a1: galaxy.sector[1] * Math.PI / 180 }))), input.disk ? input.disk.outer : null);
    else if (radial) placeGalaxiesRadial(populated, membersOf, REFERENCE_ASPECT);
    else placeGalaxies(populated, Array.from(galaxyLinks.values()), aspect);
    if (!sectored) populated.forEach(galaxy => (radial ? placeConstellationsRadial : placeConstellations)(galaxy, membersOf(galaxy)));
    const stars = [], planets = [];
    constellations.forEach(constellation => {
      const members = constellation.starIds.map(id => ({ ...input.stars.get(id), id, level: 'star', constellationId: constellation.id, planetIds: (input.planets.get(id) || []).map(planet => planet.id) }));
      const edges = input.starEdges.filter(edge => constellation.starIds.includes(edge.source) && constellation.starIds.includes(edge.target));
      placeStars(constellation, members, edges);
      constellation.figure = figureOf(members, edges);
      members.forEach(star => {
        const orbiting = (input.planets.get(star.id) || []).map(planet => ({ ...planet, level: 'planet', starId: star.id, moons: planet.moons || [], summary: planet.summary || '' }));
        placePlanets(star, orbiting);
        const ids = new Set(orbiting.map(planet => planet.id));
        star.planetEdges = (input.planetEdges || []).filter(edge => ids.has(edge.source) && ids.has(edge.target));
        planets.push(...orbiting);
      });
      stars.push(...members);
    });
    // Papers are artefacts on the rim of the roadmap they build on most, in an
    // arc along its bottom edge, clear of the roadmap's name above it.
    const artefacts = [], homed = new Map();
    (input.artefacts || []).forEach(item => { if (!constellationById.has(item.home)) return; if (!homed.has(item.home)) homed.set(item.home, []); homed.get(item.home).push(item); });
    homed.forEach((items, home) => {
      const c = constellationById.get(home), ring = c.r * 1.16, step = Math.min(Math.PI / 9, Math.PI * .8 / items.length);
      c.artefactIds = items.map((item, index) => {
        const angle = Math.PI / 2 + (index - (items.length - 1) / 2) * step;
        artefacts.push({ ...item, level: 'artefact', constellationId: home, x: c.x + Math.cos(angle) * ring, y: c.y + Math.sin(angle) * ring });
        return item.id;
      });
    });
    // A galaxy's name sits just above what is drawn of it: its dust and its roadmaps.
    populated.forEach(galaxy => {
      galaxy.dust = sectored ? sectorDust(galaxy, membersOf(galaxy)) : galaxyDust(galaxy);
      const bright = galaxy.dust.filter(p => p.cls), members = membersOf(galaxy);
      const extent = (values, fallbackLow, fallbackHigh) => {
        const sorted = values.slice().sort((a, b) => a - b);
        return sorted.length ? [sorted[Math.floor(sorted.length * .02)], sorted[Math.ceil(sorted.length * .98) - 1]] : [fallbackLow, fallbackHigh];
      };
      const [dustTop, dustBottom] = extent(bright.map(p => p.y), galaxy.y - galaxy.ry, galaxy.y + galaxy.ry);
      const [dustLeft, dustRight] = extent(bright.map(p => p.x), galaxy.x - galaxy.rx, galaxy.x + galaxy.rx);
      galaxy.top = Math.min(dustTop, ...members.map(c => c.y - c.r));
      galaxy.bottom = Math.max(dustBottom, ...members.map(c => c.y + c.r));
      galaxy.left = Math.min(dustLeft, ...members.map(c => c.x - c.r));
      galaxy.right = Math.max(dustRight, ...members.map(c => c.x + c.r));
    });
    // A field groups areas. Zoomed out, a field with several areas is named
    // once, over the extent of its areas; zooming in names the areas.
    const fields = (input.fields || []).map(field => ({
      id: 'field:' + field.id, level: 'field', label: field.label, short: field.short || '', caption: field.caption || null, code: field.code || null,
      galaxyIds: (field.groupIds || []).filter(id => galaxyById.has(id) && galaxyById.get(id).constellationIds.length)
    })).filter(field => field.galaxyIds.length > 1);
    fields.forEach(field => {
      const members = field.galaxyIds.map(id => galaxyById.get(id));
      members.forEach(galaxy => { galaxy.fieldId = field.id; });
      field.count = members.reduce((total, galaxy) => total + galaxy.count, 0);
      field.left = Math.min(...members.map(g => g.left)); field.right = Math.max(...members.map(g => g.right));
      field.top = Math.min(...members.map(g => g.top)); field.bottom = Math.max(...members.map(g => g.bottom));
      field.x = (field.left + field.right) / 2; field.y = (field.top + field.bottom) / 2;
      field.w = field.right - field.left; field.h = field.bottom - field.top;
      // A divided category is one sector made of its areas' sectors; its name runs along its middle, outside theirs.
      if (sectored) {
        field.a0 = Math.min(...members.map(g => g.a0)); field.a1 = Math.max(...members.map(g => g.a1));
        field.r0 = Math.min(...members.map(g => g.r0)); field.r1 = Math.max(...members.map(g => g.r1));
        field.hubRadius = members.reduce((total, g) => total + g.hubRadius * g.count, 0) / Math.max(1, field.count);
        field.labelSpots = spotsAlong((field.a0 + field.a1) / 2, field.r1 + 130, field.r0 - 90, field.a1 - field.a0);
      }
    });
    // On the sector map, faint guides: a ring at each whole distance from Mathlib, and a rule between neighbouring
    // sectors, stronger between categories than between the areas of one.
    let guides = null;
    if (sectored) {
      // A rule between every two sectors of the map, those without roadmaps too: an area Mathlib's disk needs has its
      // sector before its roadmaps come, and the disk's rules run on from these (src/graph.js, drawDisk).
      const order = galaxies.filter(galaxy => Array.isArray(galaxy.sector)).map(galaxy => ({ code: galaxy.code, a0: galaxy.sector[0] * Math.PI / 180, a1: galaxy.sector[1] * Math.PI / 180 }))
        .sort((a, b) => a.a0 - b.a0), reach = Math.max(...populated.map(g => g.r1));
      guides = {
        rules: order.map((sector, index) => {
          const before = order[(index + order.length - 1) % order.length], end = index ? before.a1 : before.a1 - Math.PI * 2;
          return { angle: (end + sector.a0) / 2, major: !sector.code || sector.code !== before.code };
        }),
        rings: Array.from({ length: 10 }, (_, index) => ({ distance: index + 1, radius: sectorRadius(index + 1) })).filter(ring => ring.radius <= reach + SECTOR_STEP / 2),
        inner: SECTOR_CORE * .55, outer: reach + 120
      };
    }
    const byId = new Map();
    [...fields, ...populated, ...constellations, ...stars, ...planets, ...artefacts].forEach(node => byId.set(node.id, node));
    const core = radial ? { id: 'core:mathlib', level: 'core', x: 0, y: 0, r: CORE_RADIUS, label: 'Mathlib' } : null;
    const disk = sectored && core && input.disk ? buildDisk(input.disk) : null;
    if (disk) disk.items.forEach(item => byId.set(item.id, item));
    const extents = populated.map(galaxy => ({ x0: galaxy.x - galaxy.rx, y0: galaxy.y - galaxy.ry, x1: galaxy.x + galaxy.rx, y1: galaxy.y + galaxy.ry }));
    if (core) extents.push({ x0: -core.r * 3.4, y0: -core.r * 1.7, x1: core.r * 3.4, y1: core.r * 1.7 });
    const left = Math.min(...extents.map(e => e.x0)), top = Math.min(...extents.map(e => e.y0));
    const right = Math.max(...extents.map(e => e.x1)), bottom = Math.max(...extents.map(e => e.y1));
    const bounds = populated.length ? { x: left, y: top, w: right - left, h: bottom - top } : { x: -100, y: -100, w: 200, h: 200 };
    const starIds = new Set(stars.map(star => star.id));
    return {
      fields, galaxies: populated, constellations, stars, planets, artefacts, byId, bounds, aspect, core, disk, layout: sectored ? 'sectors' : radial ? 'radial' : 'areas',
      // The sector map opens on Mathlib with the roadmaps up to this distance from it in view.
      overviewRadius: sectored ? sectorRadius(4.6) : null, guides,
      // The sectors no roadmap is in yet (those of the Mathlib disk's areas): named faintly along their middle.
      emptySectors: sectored ? galaxies.filter(galaxy => Array.isArray(galaxy.sector) && !galaxy.constellationIds.length).map(galaxy => {
        const a0 = galaxy.sector[0] * Math.PI / 180, a1 = galaxy.sector[1] * Math.PI / 180, middle = (a0 + a1) / 2;
        return { id: galaxy.id, label: galaxy.label, short: galaxy.short, code: galaxy.code, caption: galaxy.caption, a0, a1,
          spots: spotsAlong(middle, sectorRadius(3.6), SECTOR_CORE + 150, a1 - a0) };
      }) : [],
      routes: routesBetween(populated, constellations, input.constellationEdges),
      constellationEdges: input.constellationEdges.filter(edge => constellationById.has(edge.source) && constellationById.has(edge.target)),
      artefactEdges: (input.artefactEdges || []).filter(edge => constellationById.has(edge.source) && byId.has(edge.target)),
      starEdges: input.starEdges.filter(edge => starIds.has(edge.source) && starIds.has(edge.target)),
      relatedEdges: (input.relatedEdges || []).filter(edge => constellationById.has(edge.source) && constellationById.has(edge.target))
    };
  }

  window.TauUniverse = Object.freeze({ build });
})();
