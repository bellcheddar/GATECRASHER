/* In-page search. BUILD_SPEC 5.7 and Stage 4.
 *
 * The index is BM25 over this project's own prose and its measured data: no publisher text
 * is chunked or shipped. Scoring happens here because there is no server and no runtime
 * model, and for a couple of hundred documents that is instant.
 *
 * "Not stated in this paper" is a first-class answer and is styled as information rather
 * than as an error. It appears when fewer than half of the query's distinct words occur
 * anywhere in the index, which is a fact about the corpus's vocabulary rather than a tuned
 * score threshold. "Any word matches" was the first rule, and one common word defeated it:
 * "zzzqqq nonsense term" returned a CDK2 data issue because that note uses the word "term".
 * A single-word query behaves as before, and one typo among real words still finds hits.
 */

const TOKEN = /[a-z0-9][a-z0-9\-']*/g;

export function initSearch(state) {
  const el = {
    input: document.getElementById('search-input'),
    results: document.getElementById('search-results'),
  };
  if (!el.input || !el.results) return { render() {} };

  let index = null;
  let loading = null;

  async function load() {
    if (index) return index;
    if (!loading) {
      loading = fetch('data/search.json', { cache: 'no-cache' })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => { index = data; return data; })
        .catch(() => null);
    }
    return loading;
  }

  function tokenise(text) {
    return (text.toLowerCase().match(TOKEN) || []).filter((t) => t.length > 1);
  }

  /* BM25, with the statistics precomputed by gc retrieval. */
  function score(query) {
    const terms = tokenise(query);
    if (!terms.length || !index) return { hits: [], stated: false };
    const { k1, b, avg_len: avgLen, idf, units } = index;

    const distinct = [...new Set(terms)];
    const known = distinct.filter((term) => term in idf).length;
    const stated = known > 0 && known * 2 >= distinct.length;
    if (!stated) return { hits: [], stated };

    const hits = [];
    for (const unit of units) {
      let total = 0;
      for (const term of terms) {
        const tf = unit.tf[term];
        if (!tf) continue;
        const weight = idf[term] || 0;
        total += weight * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (unit.len / avgLen))));
      }
      if (total > 0) hits.push({ unit, score: total });
    }
    hits.sort((a, b2) => b2.score - a.score);
    return { hits: hits.slice(0, 8), stated };
  }

  /* A snippet centred on the first matched term, so the reader sees why it matched. */
  function snippet(text, terms) {
    const lower = text.toLowerCase();
    let at = -1;
    for (const term of terms) {
      at = lower.indexOf(term);
      if (at >= 0) break;
    }
    const start = at < 0 ? 0 : Math.max(0, at - 70);
    const piece = text.slice(start, start + 200).trim();
    return (start > 0 ? '…' : '') + piece + (start + 200 < text.length ? '…' : '');
  }

  function label(kind) {
    return {
      beat: 'story', beat_plain: 'story, plain', edit: 'edit', edit_plain: 'edit, plain',
      structure: 'structure', structure_plain: 'structure, plain', compound: 'compound',
      issue: 'data issue', paper: 'paper', problem: 'the problem',
    }[kind] || kind;
  }

  function open(unit) {
    const focus = unit.focus || {};
    const patch = {};
    if (focus.tab) patch.tab = focus.tab;
    if (focus.compound) patch.compound = focus.compound;
    if (focus.structure) patch.structure = focus.structure;
    if (focus.residues && focus.residues.length) patch.residues = focus.residues;
    if (focus.edit) patch.edit = focus.edit;
    if (focus.beat) patch.beat = focus.beat;
    /* Story and campaign text lives in drawers now, so a hit there pulls its drawer out. */
    if (focus.drawer) patch.drawer = focus.drawer;

    /* A hit in another paper switches papers first: the app serialises that, so the
     * selection lands on the bundle the reader asked for rather than the previous one. */
    if (unit.slug !== state.get('paper')) {
      window.dispatchEvent(new CustomEvent('gatecrasher:open', {
        detail: { slug: unit.slug, patch },
      }));
    } else {
      state.set(patch, 'search:hit');
    }
    close();
  }

  function close() {
    el.results.hidden = true;
    el.results.replaceChildren();
  }

  function render(query) {
    const terms = tokenise(query);
    const { hits, stated } = score(query);
    el.results.replaceChildren();

    if (!query.trim()) { close(); return; }

    if (!stated) {
      /* The honest answer, and the spec asks for it to look like one. */
      const box = document.createElement('div');
      box.className = 'search-empty';
      const strong = document.createElement('strong');
      strong.textContent = 'Not stated in this project';
      const detail = document.createElement('p');
      detail.textContent = 'Nothing in the four campaigns, their edits, their structures or '
        + 'their measurements mentions that. Only this project’s own writing and data '
        + 'are searched: the papers themselves are not reproduced here.';
      box.append(strong, detail);
      el.results.append(box);
      el.results.hidden = false;
      return;
    }

    for (const { unit } of hits) {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'search-hit';

      const head = document.createElement('div');
      head.className = 'search-hit-head';
      const title = document.createElement('span');
      title.className = 'search-hit-title';
      title.textContent = unit.title;
      const kind = document.createElement('span');
      kind.className = 'chip no-dot';
      kind.textContent = `${unit.slug} · ${label(unit.kind)}`;
      head.append(title, kind);

      const body = document.createElement('p');
      body.className = 'search-hit-text';
      body.textContent = snippet(unit.text, terms);

      row.append(head, body);
      if (unit.source) {
        const source = document.createElement('span');
        source.className = 'search-hit-source mono';
        source.textContent = unit.source;
        row.append(source);
      }
      row.addEventListener('click', () => open(unit));
      el.results.append(row);
    }
    el.results.hidden = false;
  }

  let timer = null;
  el.input.addEventListener('input', () => {
    clearTimeout(timer);
    const query = el.input.value;
    timer = setTimeout(async () => {
      await load();
      render(query);
    }, 120);
  });
  el.input.addEventListener('focus', load);
  el.input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { el.input.value = ''; close(); el.input.blur(); }
  });
  document.addEventListener('click', (event) => {
    if (!el.results.hidden && !el.results.contains(event.target) && event.target !== el.input) {
      close();
    }
  });

  /* "/" focuses search, the convention everywhere else. */
  window.addEventListener('keydown', (event) => {
    if (event.key !== '/' || event.metaKey || event.ctrlKey) return;
    const target = event.target;
    if (target instanceof HTMLElement
      && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
    event.preventDefault();
    el.input.focus();
  });

  return { render, load };
}
