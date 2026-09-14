/* The story drawers. BUILD_SPEC 7.5 and 7.6, reshaped.
 *
 * The Story used to be the landing sheet. The pocket is now what every reader lands on, and
 * the story lives in pull-out drawers over it: the campaign (the one line, the hit-to-lead
 * strip and the quoted abstract) and the five beats. A beat drives the Structure sheet's own
 * viewer, rather than a second viewer of its own.
 *
 * The register toggle switches every body and caption in the app at once: it is one
 * control, not a per-panel setting.
 *
 * The graphical abstract strip is our own interactive re-creation, drawn from SMILES. It is
 * never the publisher's image. */

import { emptyState } from '../draw.js';
import { depictionFor } from '../viewers/rdkit.js';

export function initStory(state) {
  let bundle = null;
  let observer = null;

  const el = {
    oneLine: document.getElementById('one-line'),
    strip: document.getElementById('abstract-strip'),
    quote: document.getElementById('abstract-quote'),
    beats: document.getElementById('beats'),
    storyBody: document.querySelector('#drawer-story .drawer-body'),
  };

  /* ------------------------------------------------------- graphical abstract */

  function renderStrip() {
    const panels = bundle.paper.graphical_abstract?.panels || [];
    el.strip.replaceChildren();
    if (!panels.length) {
      el.strip.append(emptyState('No hit-to-lead strip for this paper', ''));
      return Promise.resolve();
    }

    /* Every panel goes into the strip before any drawing arrives, and each drawing box keeps
     * a fixed shape while empty, so the drawings fill in without moving anything. */
    const fills = [];
    for (const panel of panels) {
      if (panel.kind === 'arrow') {
        const arrow = document.createElement('div');
        arrow.className = 'abstract-arrow';
        arrow.textContent = panel.reason;
        el.strip.append(arrow);
        continue;
      }
      const compound = bundle.index.compoundById.get(panel.compound_id);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'abstract-panel';
      /* No aria-label: "Select compound N" did not contain the visible text, which fails
       * WCAG 2.5.3 for anyone using speech control. The visible text is the name, and the
       * drawing's atom labels are kept out of it. */

      const depiction = document.createElement('div');
      depiction.className = 'depiction';
      depiction.setAttribute('aria-hidden', 'true');
      if (compound) {
        fills.push(depictionFor(bundle, compound).then((svgText) => { depiction.innerHTML = svgText; }));
      }
      button.append(depiction);

      const id = document.createElement('div');
      id.className = 'mono';
      id.textContent = `compound ${panel.compound_id}`;
      button.append(id);

      const caption = document.createElement('div');
      caption.className = 'abstract-caption';
      caption.textContent = panel.caption;
      button.append(caption);

      for (const value of panel.values || []) {
        const row = document.createElement('div');
        row.className = 'abstract-value';
        const spec = bundle.assays[value.assay_id];
        row.textContent = `${spec?.short || value.assay_id} ${value.display}`;
        button.append(row);
      }

      button.addEventListener('click', () => {
        state.set({ compound: panel.compound_id }, 'story:abstract-panel');
      });
      el.strip.append(button);
    }
    return Promise.all(fills);
  }

  function renderQuote() {
    const paper = bundle.paper;
    el.quote.replaceChildren();
    const text = document.createElement('p');
    text.textContent = paper.abstract;
    const cite = document.createElement('cite');
    /* Quoted verbatim, marked as a quotation, with its citation and DOI: standard
     * scholarly quotation, and everything around it on this page is written fresh. */
    cite.textContent = `${paper.authors_short}, ${paper.journal} ${paper.year}`
      + `${paper.volume ? `, ${paper.volume}` : ''}${paper.pages ? `, ${paper.pages}` : ''}. `
      + `Abstract quoted verbatim.`;
    const link = document.createElement('a');
    link.href = `https://doi.org/${paper.doi}`;
    link.textContent = ` doi:${paper.doi}`;
    link.target = '_blank';
    link.rel = 'noopener';
    cite.append(link);
    el.quote.append(text, cite);
  }

  function renderOneLine() {
    el.oneLine.textContent = bundle.paper.one_line;
  }

  /* -------------------------------------------------------------------- beats */

  function renderBeats() {
    if (!bundle) return;
    el.beats.replaceChildren();
    const beats = bundle.story?.beats || [];
    if (!beats.length) {
      el.beats.append(emptyState('The story for this paper is not written yet',
        'The data, the structure and the edit log are all here in the meantime.'));
      return;
    }

    const register = state.get('register');
    for (const beat of beats) {
      const article = document.createElement('article');
      article.className = 'beat';
      article.id = `beat-${beat.id}`;
      article.dataset.beat = beat.id;

      const kicker = document.createElement('div');
      kicker.className = 'beat-kicker';
      kicker.textContent = beat.kicker;

      const title = document.createElement('h3');
      title.textContent = beat.title;

      const body = document.createElement('p');
      body.className = 'prose';
      body.textContent = register === 'plain' ? beat.body_plain : beat.body_specialist;

      const evidence = document.createElement('p');
      evidence.className = 'beat-evidence';
      evidence.textContent = `Evidence: ${beat.evidence}`;

      article.append(kicker, title, body, evidence);

      /* Every beat can hand its focus to the Structure sheet explicitly, not only the last
       * one: the drawer sits over the sheet, so the reader is never far from it. */
      if (beat.focus) {
        const show = document.createElement('button');
        show.type = 'button';
        show.className = 'beat-show';
        show.textContent = 'Show this in the structure';
        show.addEventListener('click', () => focusBeat(beat, { openStructure: true }));
        article.append(show);
      }

      el.beats.append(article);
    }
    markCurrent();
    watchBeats();
  }

  /* A beat's whole focus block goes out in ONE set() with the beat itself. The old Story
   * sheet set the beat, then set its focus from inside the beat subscriber, and the state bus
   * drops any set() made during a dispatch, so the compound and residues never followed. */
  function focusBeat(beat, { openStructure = false } = {}) {
    const focus = beat.focus || {};
    const patch = { beat: beat.id, edit: focus.edit || null };
    if (focus.compound && bundle.index.compoundById.has(focus.compound)) patch.compound = focus.compound;
    if (focus.structure && bundle.structures.some((s) => s.pdb_id === focus.structure)) {
      patch.structure = focus.structure;
    }
    if (focus.residues) patch.residues = focus.residues;
    if (openStructure) patch.tab = 'structure';
    state.set(patch, openStructure ? 'story:show-beat' : 'story:scroll');
  }

  /* While the story drawer is out, the beat reading in the middle of it sets the focus. */
  function watchBeats() {
    observer?.disconnect();
    observer = new IntersectionObserver((entries) => {
      if (state.get('drawer') !== 'story') return;
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      const beat = (bundle.story?.beats || []).find((b) => b.id === visible.target.dataset.beat);
      if (beat && beat.id !== state.get('beat')) focusBeat(beat);
    }, { root: el.storyBody, rootMargin: '-30% 0px -45% 0px', threshold: [0.1, 0.5, 0.9] });

    for (const article of el.beats.querySelectorAll('.beat')) observer.observe(article);
  }

  function markCurrent() {
    const current = state.get('beat');
    for (const article of el.beats.querySelectorAll('.beat')) {
      article.classList.toggle('is-current', article.dataset.beat === current);
    }
  }

  state.on(['beat'], markCurrent);
  state.on(['register'], () => { if (bundle) renderBeats(); });

  return {
    async setBundle(next) {
      bundle = next;
      renderOneLine();
      renderQuote();
      renderStrip();
      renderBeats();
    },
    render: renderBeats,
  };
}
