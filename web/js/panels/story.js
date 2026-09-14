/* The Story sheet: the Feature. BUILD_SPEC 7.5 and 7.6.
 *
 * A scroll-driven column of beats, set in Newsreader, with the structure and plot pinned
 * beside it following each beat's focus block. The register toggle switches every body and
 * caption in the app at once: it is one control, not a per-panel setting.
 *
 * The graphical abstract strip at the top is our own interactive re-creation, drawn from
 * SMILES. It is never the publisher's image. */

import { emptyState } from '../draw.js';
import { depictionFor } from '../viewers/rdkit.js';
import { StructureViewer } from '../viewers/molstar.js';

export function initStory(state) {
  let bundle = null;
  let viewer = null;
  let observer = null;

  const el = {
    oneLine: document.getElementById('one-line'),
    strip: document.getElementById('abstract-strip'),
    quote: document.getElementById('abstract-quote'),
    beats: document.getElementById('beats'),
    viewerHost: document.getElementById('story-viewer'),
    caption: document.getElementById('story-caption'),
  };

  /* ------------------------------------------------------- graphical abstract */

  async function renderStrip() {
    const panels = bundle.paper.graphical_abstract?.panels || [];
    el.strip.replaceChildren();
    if (!panels.length) {
      el.strip.append(emptyState('No hit-to-lead strip for this paper', ''));
      return;
    }

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
      button.setAttribute('aria-label', `Select compound ${panel.compound_id}`);

      const depiction = document.createElement('div');
      depiction.className = 'depiction';
      if (compound) depiction.innerHTML = await depictionFor(bundle, compound);
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

      /* The last beat hands off to the Structure tab with an explicit control, rather
       * than leaving the reader at the end of a column with nowhere to go. */
      if (beat === beats[beats.length - 1]) {
        const handoff = document.createElement('button');
        handoff.type = 'button';
        handoff.textContent = 'Open this in the structure';
        handoff.addEventListener('click', (event) => {
          event.stopPropagation();
          state.set({
            tab: 'structure',
            structure: beat.focus?.structure || state.get('structure'),
            residues: beat.focus?.residues || [],
            compound: beat.focus?.compound || state.get('compound'),
          }, 'story:handoff');
        });
        article.append(handoff);
      }

      el.beats.append(article);
    }
    watchBeats();
  }

  /* A beat scrolling into view sets `beat` and everything in its focus block. */
  function watchBeats() {
    observer?.disconnect();
    observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      const id = visible.target.dataset.beat;
      if (id && id !== state.get('beat')) {
        state.set({ beat: id }, 'story:scroll');
      }
    }, { rootMargin: '-35% 0px -45% 0px', threshold: [0.1, 0.5, 0.9] });

    for (const article of el.beats.querySelectorAll('.beat')) observer.observe(article);
  }

  async function applyFocus(beatId) {
    if (!bundle) return;
    const beat = (bundle.story?.beats || []).find((b) => b.id === beatId);
    for (const article of el.beats.querySelectorAll('.beat')) {
      article.classList.toggle('is-current', article.dataset.beat === beatId);
    }
    if (!beat?.focus) return;
    const focus = beat.focus;

    /* Set the whole focus block in one dispatch: a beat is one user action, not five. */
    state.set({
      compound: focus.compound || state.get('compound'),
      structure: focus.structure || state.get('structure'),
      residues: focus.residues || [],
      edit: focus.edit || null,
    }, 'story:focus');

    if (focus.structure) await showStructure(focus.structure, focus.residues || []);
  }

  async function showStructure(pdbId, residues) {
    if (!bundle) return;
    if (!StructureViewer.available()) {
      el.viewerHost.replaceChildren(emptyState('The 3D viewer did not load', ''));
      return;
    }
    /* Same rule as the Structure sheet: a 0x0 host means a zero-sized WebGL texture, which
     * Mol* refuses. The Story tab is the opening tab, so this normally passes at once. */
    if (el.viewerHost.clientWidth === 0 || el.viewerHost.clientHeight === 0) return;
    if (!viewer) {
      viewer = new StructureViewer(el.viewerHost);
      await viewer.create({ background: colourInt('--surface-2') });
      viewer.onResidueClick((residue) => {
        state.set({ residues: [residue.id] }, 'story:3d-click');
      });
    }
    const entry = bundle.structures.find((s) => s.pdb_id === pdbId);
    if (!entry) return;
    if (!viewer.loaded.has(`story-${pdbId}`)) {
      for (const name of [...viewer.loaded.keys()]) await viewer.clear(name);
      await viewer.load(`story-${pdbId}`, `https://files.rcsb.org/download/${pdbId}.cif`);
    }
    if (residues.length) viewer.focusResidues(residues);
    else viewer.focusLigand();

    el.caption.textContent = state.get('register') === 'plain'
      ? entry.caption_plain : entry.caption_specialist;
  }

  function renderOneLine() {
    el.oneLine.textContent = bundle.paper.one_line;
  }

  state.on(['beat'], () => applyFocus(state.get('beat')));
  state.on(['register'], () => {
    if (!bundle) return;
    renderBeats();
    const structureId = state.get('structure');
    const entry = bundle.structures.find((s) => s.pdb_id === structureId);
    if (entry) {
      el.caption.textContent = state.get('register') === 'plain'
        ? entry.caption_plain : entry.caption_specialist;
    }
  });

  return {
    async setBundle(next) {
      bundle = next;
      renderOneLine();
      renderQuote();
      await renderStrip();
      renderBeats();
      const first = bundle.story?.beats?.[0];
      const entry = bundle.structures.find((s) => s.role === 'primary') || bundle.structures[0];
      if (first?.focus?.structure) await showStructure(first.focus.structure, first.focus.residues || []);
      else if (entry) await showStructure(entry.pdb_id, []);
    },
    render: renderBeats,
  };
}

function colourInt(token) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  const probe = document.createElement('span');
  probe.style.color = value;
  document.body.appendChild(probe);
  const computed = getComputedStyle(probe).color;
  probe.remove();
  const match = computed.match(/rgba?\((\d+)[,\s]+(\d+)[,\s]+(\d+)/);
  if (!match) return 0x143458;
  const [, r, g, b] = match.map(Number);
  return (r << 16) | (g << 8) | b;
}
