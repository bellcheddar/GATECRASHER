/* The provenance rail and the sheet title blocks.
 *
 * BUILD_SPEC 7.8: always visible, showing the current paper, compound, structure and source
 * table, with links out to the DOI and the RCSB entry. This is what makes the app defensible
 * to a specialist, and it is the one panel that is never allowed to be empty.
 *
 * The title blocks are driven from the same state, which is what makes the cross-linking
 * visible rather than merely functional. */

import { measurement } from '../data.js';

export function initRail(state) {
  const el = {
    paper: document.getElementById('rail-paper'),
    compound: document.getElementById('rail-compound'),
    structure: document.getElementById('rail-structure'),
    source: document.getElementById('rail-source'),
    links: document.getElementById('rail-links'),
  };

  let bundle = null;

  function sourceFor(compoundId) {
    if (!bundle || !compoundId) return null;
    const compound = bundle.index.compoundById.get(compoundId);
    if (!compound) return null;
    /* Prefer the table the identity came from, then any table a measurement came from:
     * a compound the app can show always has somewhere a reader can check it. */
    const tables = new Set();
    if (compound.source_table) tables.add(compound.source_table);
    for (const row of bundle.index.byCompound.get(compoundId)?.values() || []) {
      if (row.source_table) tables.add(row.source_table);
    }
    return [...tables].join(', ');
  }

  function render() {
    if (!bundle) return;
    const paper = bundle.paper;
    const compoundId = state.get('compound');
    const structureId = state.get('structure');

    el.paper.textContent = `${paper.authors_short} ${paper.year}`;
    el.paper.title = paper.title;

    el.compound.textContent = compoundId ? `cmpd ${compoundId}` : 'none selected';
    el.structure.textContent = structureId || 'none';
    el.source.textContent = sourceFor(compoundId) || 'n/a';

    el.links.replaceChildren();
    el.links.append(link(`https://doi.org/${paper.doi}`, `DOI ${paper.doi}`, 'The published paper'));
    if (structureId) {
      el.links.append(
        link(`https://www.rcsb.org/structure/${structureId}`, `RCSB ${structureId}`,
          'The deposited coordinates this view is drawn from'));
    }
    /* A modelled or referenced structure is labelled as such wherever it appears: the KRAS
     * bundle contains a model of compound 23, and a reader must never mistake it for a
     * crystal structure. */
    const entry = structureId
      ? bundle.structures.find((s) => s.pdb_id === structureId) : null;
    if (entry && entry.source === 'modelled') {
      el.links.append(badge('MODEL, not a crystal structure'));
    } else if (entry && entry.source === 'referenced') {
      el.links.append(badge('referenced structure, different compound'));
    }
  }

  function link(href, text, title) {
    const a = document.createElement('a');
    a.href = href;
    a.textContent = text;
    a.title = title;
    a.target = '_blank';
    a.rel = 'noopener';
    return a;
  }

  function badge(text) {
    const span = document.createElement('span');
    span.className = 'chip no-dot';
    span.style.borderColor = 'var(--measure)';
    span.style.color = 'var(--measure)';
    span.textContent = text;
    return span;
  }

  /* -------------------------------------------------------------- title blocks */

  const SHEET_NAMES = {
    '01': 'STORY', '02': 'STRUCTURE', '03': 'EDIT LOG', '04': 'SAR', '05': 'PROPERTIES',
  };

  function renderTitleBlocks() {
    if (!bundle) return;
    const compoundId = state.get('compound');
    const structureId = state.get('structure');
    for (const block of document.querySelectorAll('.title-block')) {
      const sheet = block.dataset.sheet || '00';
      const subject = sheet === '02' ? (structureId || '-') : (compoundId ? `CMPD ${compoundId}` : '-');
      block.replaceChildren(
        cell(`${sheet} ${SHEET_NAMES[sheet] || ''}`.trim()),
        cell(bundle.slug.toUpperCase()),
        cell(subject, true),
      );
    }
  }

  function cell(text, isValue = false) {
    const span = document.createElement('span');
    span.textContent = text;
    if (isValue) span.className = 'tb-value';
    return span;
  }

  function update() {
    render();
    renderTitleBlocks();
  }

  state.on(['paper', 'compound', 'structure'], update);

  return {
    setBundle(next) {
      bundle = next;
      update();
    },
    update,
  };
}
