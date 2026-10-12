/* The live galaxy: Tau Ceti's open pull requests twinkle beside their roadmaps.

   Every 90 seconds the page asks GitHub's search API for the repository's open pull
   requests. The search API has its own allowance, ten requests a minute without a token,
   and one look takes a request per hundred open pull requests, so a look is never asked
   within a minute of the last one, and a refusal waits for GitHub's reset. Nothing is
   asked while the page is hidden.

   A pull request's `roadmap/<Name>` labels say which roadmaps it twinkles beside; one
   without a roadmap (`roadmap/none`) is not shown. A pull request opened while the page
   is open appears with a flash; one that lands flares and fades away, and one closed
   without landing fades quietly.

   Tau Ceti lands pull requests through bors, which pushes the squashed commit to main
   and then closes the pull request instead of merging it, so GitHub never marks it
   merged. A pull request that leaves the open list is therefore looked for among main's
   recent commits, whose first lines end in "(#1234)": one found there has landed.

   The last list seen is kept in the browser's storage, so a page opened while GitHub is
   refusing requests still shows the stars as they were (marked as such in the header)
   until a look succeeds. */
(function () {
  'use strict';

  const SEARCH = 'https://api.github.com/search/issues';
  const API = 'https://api.github.com';
  const INTERVAL = 90 * 1000;
  const MIN_GAP = 60 * 1000;         // never two looks within this, however often the tab is shown
  const OVERLAP = 5 * 60 * 1000;     // a pull request opened this soon before the page counts as new
  const LINGER = 9 * 1000;           // a landed or closed pull request's fade, before it is dropped
  const LANDED = 60 * 60 * 1000;     // bors closes a pull request some minutes after its commit lands
  const CACHE_KEY = 'tauceti-live-v1';
  const CACHE_AGE = 3 * 60 * 60 * 1000;   // a remembered list older than this is not shown

  function create(options) {
    const repo = options.repo, labelPrefix = options.labelPrefix || 'roadmap/', idPrefix = options.idPrefix || '';
    const branch = options.branch || 'main';
    const known = options.roadmapIds || new Set(), onChange = options.onChange || (() => {});
    const open = new Map();            // number -> pull request
    const leaving = new Map();         // number -> { pull request, state: 'merged' | 'closed', at }
    let coreWaitUntil = 0;             // the core API's allowance is sixty requests an hour without a token
    let started = Date.now(), lastAttempt = 0, first = true, remembered = false, rememberedNote = '';
    let timer = null, running = false, paused = false;
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

    // Oldest first: a pull request opened while the pages are fetched joins the end of the list instead of
    // shifting every page by one, which made the default "best match" order repeat some pull requests and
    // skip others.
    async function search(query) {
      const items = [];
      for (let page = 1; page <= 10; page += 1) {
        const response = await fetch(`${SEARCH}?q=${encodeURIComponent(query)}&sort=created&order=asc&per_page=100&page=${page}`,
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

    // The pull requests whose commits reached main in the last hour: a squashed commit's first line ends in
    // "(#1234)", and a merge commit's starts "Merge pull request #1234". One request to the core API, asked only
    // when a pull request has left the open list; when it fails or the allowance is spent, those pull requests
    // fade as closed.
    async function landedOnMain() {
      const landed = new Set();
      if (Date.now() < coreWaitUntil) return landed;
      const since = new Date(Date.now() - LANDED).toISOString().replace(/\.\d+Z$/, 'Z');
      try {
        const response = await fetch(`${API}/repos/${repo}/commits?sha=${encodeURIComponent(branch)}&since=${since}&per_page=100`,
                                     { headers: { Accept: 'application/vnd.github+json' } });
        if (!response.ok) {
          const reset = Number(response.headers.get('x-ratelimit-reset')) * 1000 || 0;
          coreWaitUntil = reset > Date.now() ? reset : Date.now() + 15 * 60 * 1000;
          return landed;
        }
        for (const commit of await response.json()) {
          const subject = ((commit.commit && commit.commit.message) || '').split('\n')[0];
          const match = /\(#(\d+)\)\s*$/.exec(subject) || /^Merge pull request #(\d+)\b/.exec(subject);
          if (match) landed.add(Number(match[1]));
        }
      } catch (error) {
        coreWaitUntil = Date.now() + INTERVAL;
      }
      return landed;
    }

    // The browser keeps the last list seen. Storage can be blocked or full; the page works without it.
    function remember() {
      try {
        localStorage.setItem(CACHE_KEY, JSON.stringify({ repo, at: Date.now(),
          prs: [...open.values()].map(pr => ({ ...pr, fresh: false })) }));
      } catch (error) { /* nothing to do */ }
    }

    function recall() {
      try {
        const saved = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
        if (!saved || saved.repo !== repo || !Array.isArray(saved.prs) || !(Date.now() - saved.at < CACHE_AGE)) return false;
        saved.prs.forEach(pr => open.set(pr.number, { ...pr, fresh: false,
                                                      roadmaps: (pr.roadmaps || []).filter(id => known.has(id)) }));
        const at = new Date(saved.at);
        rememberedNote = `Showing the pull requests open at ${at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        status = { ...status, updated: at, error: rememberedNote };
        return open.size > 0;
      } catch (error) {
        return false;
      }
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
      if (Date.now() - lastAttempt < MIN_GAP) { schedule(MIN_GAP - (Date.now() - lastAttempt)); return; }
      running = true;
      lastAttempt = Date.now();
      const now = Date.now();
      try {
        const current = await search(`repo:${repo} is:pr is:open`);
        const openNow = new Map(current.map(item => [item.number, item]));
        // The first look after a remembered list was shown drops what has gone since without a display;
        // after that, a pull request that leaves the open list flares if it landed and fades if it was closed.
        const quiet = first && remembered;
        const gone = [...open.keys()].filter(number => !openNow.has(number));
        const landed = gone.length && !quiet ? await landedOnMain() : new Set();
        gone.forEach(number => {
          const pr = open.get(number);
          open.delete(number);
          if (!quiet) leaving.set(number, { pr, state: landed.has(number) ? 'merged' : 'closed', at: now });
        });
        openNow.forEach((item, number) => {
          if (!open.has(number)) open.set(number, pull(item, !first && Date.parse(item.created_at) > started - OVERLAP));
          else open.set(number, { ...pull(item, open.get(number).fresh) });
        });
        first = false;
        status = { ...status, updated: new Date(now), error: null };
        remember();
        schedule(INTERVAL);
      } catch (error) {
        const wait = error.reset && error.reset > Date.now() ? error.reset - Date.now() + 5000 : 3 * INTERVAL;
        const why = error.status === 403 || error.status === 429 ? 'GitHub asked us to wait' : 'GitHub could not be reached';
        status = { ...status, error: remembered && first ? `${rememberedNote}; ${why}` : why };
        schedule(Math.max(wait, MIN_GAP));
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
      remembered = recall();
      if (remembered) publish();
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
