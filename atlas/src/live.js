/* The live galaxy: Tau Ceti's open pull requests twinkle beside their roadmaps.

   Every 90 seconds the page asks GitHub's search API for the repository's open pull
   requests and for those merged since the last look. The search API has its own
   allowance, ten requests a minute without a token, and one look takes about four.
   A pull request's `roadmap/<Name>` labels say which roadmaps it twinkles beside; one
   without a roadmap (`roadmap/none`) is not shown. A pull request opened while the page
   is open appears with a flash, and a merged one flares and fades away. Nothing is
   asked while the page is hidden, and a refusal from GitHub waits for its reset. */
(function () {
  'use strict';

  const SEARCH = 'https://api.github.com/search/issues';
  const INTERVAL = 90 * 1000;
  const RECENT = 15 * 60 * 1000;     // merges this recent flare once when the page opens
  const OVERLAP = 5 * 60 * 1000;     // the search index lags: each look reaches back this far
  const LINGER = 9 * 1000;           // a merged or closed pull request's fade, before it is dropped

  function create(options) {
    const repo = options.repo, labelPrefix = options.labelPrefix || 'roadmap/', idPrefix = options.idPrefix || '';
    const known = options.roadmapIds || new Set(), onChange = options.onChange || (() => {});
    const open = new Map();            // number -> pull request
    const leaving = new Map();         // number -> { pull request, state: 'merged' | 'closed', at }
    const seenMerged = new Set();
    let started = Date.now(), lastLook = started - RECENT, first = true, timer = null, running = false, paused = false;
    let status = { open: 0, shown: 0, roadmaps: 0, updated: null, error: null };

    function roadmapsOf(item) {
      const ids = [];
      for (const label of item.labels || []) {
        const name = typeof label === 'string' ? label : label.name;
        if (!name || !name.startsWith(labelPrefix)) continue;
        const id = idPrefix + name.slice(labelPrefix.length);
        if (known.has(id) && !ids.includes(id)) ids.push(id);
      }
      return ids;
    }

    function pull(item, fresh) {
      return { number: item.number, title: item.title || '', url: item.html_url, user: item.user && item.user.login || '',
               created: Date.parse(item.created_at) || 0, roadmaps: roadmapsOf(item), fresh: !!fresh };
    }

    async function search(query) {
      const items = [];
      for (let page = 1; page <= 10; page += 1) {
        const response = await fetch(`${SEARCH}?q=${encodeURIComponent(query)}&per_page=100&page=${page}`,
                                     { headers: { Accept: 'application/vnd.github+json' } });
        if (!response.ok) {
          const reset = Number(response.headers.get('x-ratelimit-reset')) * 1000 || 0;
          throw Object.assign(new Error(`GitHub answered ${response.status}`), { status: response.status, reset });
        }
        const body = await response.json();
        items.push(...(body.items || []));
        if ((body.items || []).length < 100 || items.length >= body.total_count) break;
      }
      return items;
    }

    function items() {
      const out = [];
      const add = (pr, state, at) => pr.roadmaps.forEach(id => out.push({
        key: `${pr.number}@${id}`, roadmapId: id, number: pr.number, title: pr.title, url: pr.url, user: pr.user,
        state, fresh: pr.fresh, at }));
      open.forEach(pr => add(pr, 'open', null));
      leaving.forEach(entry => add(entry.pr, entry.state, entry.at));
      return out;
    }

    function publish() {
      const shown = [...open.values()].filter(pr => pr.roadmaps.length);
      status = { ...status, open: open.size, shown: shown.length, roadmaps: new Set(shown.flatMap(pr => pr.roadmaps)).size };
      onChange(paused ? [] : items(), { ...status, paused });
    }

    async function look() {
      if (running || paused) return;
      if (document.visibilityState === 'hidden') { schedule(INTERVAL); return; }
      running = true;
      const since = new Date(Math.min(lastLook, Date.now() - OVERLAP)).toISOString().replace(/\.\d+Z$/, 'Z');
      const now = Date.now();
      try {
        const [current, merged] = await Promise.all([
          search(`repo:${repo} is:pr is:open`),
          search(`repo:${repo} is:pr is:merged merged:>=${since}`)]);
        const mergedNow = new Map(merged.map(item => [item.number, item]));
        const openNow = new Map(current.map(item => [item.number, item]));
        // A pull request that has gone from the open list flares if it merged, and fades quietly if it closed.
        open.forEach((pr, number) => {
          if (openNow.has(number)) return;
          leaving.set(number, { pr, state: mergedNow.has(number) ? 'merged' : 'closed', at: now });
          open.delete(number);
          if (mergedNow.has(number)) seenMerged.add(number);
        });
        openNow.forEach((item, number) => {
          if (!open.has(number)) open.set(number, pull(item, !first && Date.parse(item.created_at) > started - OVERLAP));
          else open.set(number, { ...pull(item, open.get(number).fresh) });
        });
        // Merges not seen open (they opened and merged between looks, or before the page opened) flare too.
        mergedNow.forEach((item, number) => {
          if (seenMerged.has(number) || open.has(number) || leaving.has(number)) return;
          seenMerged.add(number);
          leaving.set(number, { pr: pull(item, false), state: 'merged', at: now });
        });
        lastLook = now; first = false;
        status = { ...status, updated: new Date(now), error: null };
        schedule(INTERVAL);
      } catch (error) {
        const wait = error.reset && error.reset > Date.now() ? error.reset - Date.now() + 5000 : 3 * INTERVAL;
        status = { ...status, error: error.status === 403 || error.status === 429 ? 'GitHub asked us to wait' : 'GitHub could not be reached' };
        schedule(wait);
      } finally {
        running = false;
      }
      publish();
      setTimeout(() => { prune(); publish(); }, LINGER + 500);
    }

    function prune() {
      const cutoff = Date.now() - LINGER;
      leaving.forEach((entry, number) => { if (entry.at < cutoff) leaving.delete(number); });
      open.forEach(pr => { pr.fresh = false; });
    }

    function schedule(delay) {
      clearTimeout(timer);
      if (!paused) timer = setTimeout(look, delay);
    }

    function start() {
      paused = false; started = Date.now();
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && !paused && !running) look(); });
      look();
      return api;
    }

    function setPaused(value) {
      paused = !!value;
      if (paused) clearTimeout(timer); else look();
      publish();
    }

    const api = { start, setPaused, status: () => ({ ...status, paused }) };
    return api;
  }

  window.TauLive = Object.freeze({ create });
}());
