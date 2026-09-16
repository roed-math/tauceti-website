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

  // The radial layout: Mathlib is a small black hole at the centre. A galaxy
  // lies farther out the more theory its roadmaps must build before their
  // targets can be stated and proved (their mean distance from Mathlib, on a
  // 0-10 scale), in a direction chosen so that related subjects are
  // neighbours. Overlaps are resolved by turning galaxies around the core,
  // so distance from the centre keeps its meaning.
  const CORE_RADIUS = 60;
  const GALAXY_GAP = 70;
  // Distance from the centre grows faster than the distance score, so the
  // subjects farthest from Mathlib stand clearly apart from the rest.
  const radiusFor = distance => 260 + 95 * distance + 17 * distance * distance;
  const galaxySize = count => 170 + 80 * Math.sqrt(Math.max(1, count));
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

  // Inside an area, a roadmap closer to Mathlib than the area's average sits
  // on the side facing the core, and a farther one on the outer side.
  function placeConstellationsRadial(galaxy, constellations) {
    const seed = hash(galaxy.label), rotation = (seed % 360) * Math.PI / 180;
    const length = Math.max(1, Math.hypot(galaxy.x, galaxy.y)), ux = galaxy.x / length, uy = galaxy.y / length;
    const rx = Math.max(40, galaxy.rx * .8), ry = Math.max(30, galaxy.ry * .8);
    constellations.forEach((constellation, index) => {
      const angle = index * GOLDEN + rotation;
      const spread = constellations.length === 1 ? 0 : Math.sqrt((index + .45) / constellations.length) * .78;
      const offset = Number.isFinite(constellation.distance) ? Math.max(-.62, Math.min(.62, (constellation.distance - galaxy.distance) * .16)) : 0;
      constellation.x = galaxy.x + Math.cos(angle) * rx * spread + ux * offset * rx;
      constellation.y = galaxy.y + Math.sin(angle) * ry * spread + uy * offset * ry;
    });
    constellations.forEach(constellation => {
      const n = constellation.starIds.length;
      constellation.wanted = constellation.unmapped ? 14 : 10 + 5.4 * Math.sqrt(n);
    });
    for (let pass = 0; pass < 200; pass++) {
      let moved = false;
      constellations.forEach((a, index) => constellations.slice(index + 1).forEach(b => {
        const dx = b.x - a.x, dy = b.y - a.y, distance = Math.max(.001, Math.hypot(dx, dy));
        const needed = (a.wanted + b.wanted) * 1.02 + 16;
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
      const wanted = constellation.unmapped ? 14 : 10 + 5.4 * Math.sqrt(constellation.starIds.length);
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
        planet.r = Math.max(.3, Math.min(star.r * .62, step * .15, radius * Math.PI / Math.max(3, count) * .34));
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
      const rim = (g, toward) => { const ex = toward.x - g.x, ey = toward.y - g.y, scale = 1 / Math.max(1e-6, Math.hypot(ex / g.rx, ey / g.ry)); return { x: g.x + ex * scale, y: g.y + ey * scale }; };
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

  function build(input, viewport) {
    const aspect = viewport && viewport.width && viewport.height ? viewport.width / viewport.height : 1.5;
    const galaxies = input.groups.map(group => ({ id: group.id, level: 'galaxy', label: group.label, short: group.short || '', caption: group.caption || null, direction: group.direction, color: group.color, constellationIds: [], count: 0, unmappedCount: 0, progress: group.progress == null ? null : group.progress, progressLabel: group.progressLabel || '' }));
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
    if (radial) placeGalaxiesRadial(populated, membersOf, aspect);
    else placeGalaxies(populated, Array.from(galaxyLinks.values()), aspect);
    populated.forEach(galaxy => (radial ? placeConstellationsRadial : placeConstellations)(galaxy, membersOf(galaxy)));
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
    // A galaxy's name sits just above what is drawn of it: its dust and its roadmaps.
    populated.forEach(galaxy => {
      galaxy.dust = galaxyDust(galaxy);
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
    const byId = new Map();
    [...populated, ...constellations, ...stars, ...planets].forEach(node => byId.set(node.id, node));
    const core = radial ? { id: 'core:mathlib', level: 'core', x: 0, y: 0, r: CORE_RADIUS, label: 'Mathlib' } : null;
    const extents = populated.map(galaxy => ({ x0: galaxy.x - galaxy.rx, y0: galaxy.y - galaxy.ry, x1: galaxy.x + galaxy.rx, y1: galaxy.y + galaxy.ry }));
    if (core) extents.push({ x0: -core.r * 3.4, y0: -core.r * 1.7, x1: core.r * 3.4, y1: core.r * 1.7 });
    const left = Math.min(...extents.map(e => e.x0)), top = Math.min(...extents.map(e => e.y0));
    const right = Math.max(...extents.map(e => e.x1)), bottom = Math.max(...extents.map(e => e.y1));
    const bounds = populated.length ? { x: left, y: top, w: right - left, h: bottom - top } : { x: -100, y: -100, w: 200, h: 200 };
    const starIds = new Set(stars.map(star => star.id));
    return {
      galaxies: populated, constellations, stars, planets, byId, bounds, aspect, core, layout: radial ? 'radial' : 'areas',
      routes: routesBetween(populated, constellations, input.constellationEdges),
      constellationEdges: input.constellationEdges.filter(edge => constellationById.has(edge.source) && constellationById.has(edge.target)),
      starEdges: input.starEdges.filter(edge => starIds.has(edge.source) && starIds.has(edge.target)),
      relatedEdges: (input.relatedEdges || []).filter(edge => constellationById.has(edge.source) && constellationById.has(edge.target))
    };
  }

  window.TauUniverse = Object.freeze({ build });
})();
