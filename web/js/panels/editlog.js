/* The Edit Log sheet: the SBDD narrative made mechanical. BUILD_SPEC 7.3.
 *
 * One card per row of edits.csv: before depiction, arrow, after depiction, the changed atoms
 * highlighted, the change_type as a tag, property deltas coloured by gain or loss, the
 * rationale in the current register, and residue chips that drive the Structure sheet.
 *
 * The isostere filter is the default view, because that is the technique the app most wants
 * to teach. */

import { formatValue } from '../data.js';
import { emptyState, swapRow } from '../draw.js';
import { changedAtoms, depictionFor, ready as rdkitReady } from '../viewers/rdkit.js';

const DEFAULT_FILTER = 'isostere';

export function initEditLog(state) {
  let bundle = null;
  let filter = DEFAULT_FILTER;

  const hosts = [
    { cards: document.getElementById('edit-cards'), filter: document.getElementById('change-type-filter-tab') },
    { cards: document.getElementById('edit-cards-inline'), filter: document.getElementById('change-type-filter') },
  ].filter((h) => h.cards);

  function types() {
    const counts = new Map();
    for (const edit of bundle.edits) {
      counts.set(edit.change_type, (counts.get(edit.change_type) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }

  function renderFilters() {
    for (const host of hosts) {
      if (!host.filter) continue;
      host.filter.replaceChildren();

      const all = chip(`all (${bundle.edits.length})`, filter === null, () => {
        filter = null;
        render();
      });
      host.filter.append(all);

      for (const [type, count] of types()) {
        host.filter.append(chip(
          `${type.replace(/_/g, ' ')} (${count})`,
          filter === type,
          () => { filter = filter === type ? null : type; render(); },
        ));
      }
    }
  }

  function chip(text, active, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'chip no-dot';
    button.textContent = text;
    button.setAttribute('aria-pressed', String(active));
    button.addEventListener('click', onClick);
    return button;
  }

  function visibleEdits() {
    let edits = bundle.edits.slice();
    if (filter) edits = edits.filter((e) => e.change_type === filter);

    /* A residue selection narrows the log to the edits that cite it, which is the
     * structure-to-SAR link working in the other direction. */
    const residues = state.get('residues');
    if (residues.length) {
      const wanted = new Set(residues);
      const cited = edits.filter((e) => (e.structural_basis || []).some((r) => wanted.has(r)));
      if (cited.length) edits = cited;
    }
    return edits;
  }

  async function card(edit, hostIndex) {
    const from = bundle.index.compoundById.get(edit.from_compound);
    const to = bundle.index.compoundById.get(edit.to_compound);
    const wrapper = document.createElement('article');
    wrapper.className = 'edit-card';
    /* The log appears twice in the DOM: inside Structure on desktop and as its own tab
     * below 900px. Only one is visible at a time, but both exist, so ids are namespaced
     * per host. Duplicate ids would make scrollToEdit jump to whichever copy is hidden. */
    wrapper.id = `edit-${hostIndex}-${edit.edit_id}`;
    wrapper.dataset.edit = edit.edit_id;
    wrapper.tabIndex = 0;
    if (state.get('edit') === edit.edit_id) wrapper.classList.add('is-active');

    const head = document.createElement('div');
    head.className = 'sheet-head';
    const title = document.createElement('h3');
    title.textContent = edit.headline;
    const ids = document.createElement('span');
    ids.className = 'mono';
    ids.textContent = `${edit.from_compound} → ${edit.to_compound} · ${edit.vector}`;
    head.append(title, ids);
    wrapper.append(head);

    /* Highlight exactly the atoms that changed, when RDKit.js is available to work out
     * which those are. Without it the precomputed depictions are shown unhighlighted,
     * which is a smaller loss than a wrong highlight. */
    let highlight = null;
    if (rdkitReady() && from && to) {
      highlight = changedAtoms(from.smiles, to.smiles);
    }

    const [beforeSvg, afterSvg] = await Promise.all([
      from ? depictionFor(bundle, from, { highlightAtoms: highlight?.from }) : '',
      to ? depictionFor(bundle, to, { highlightAtoms: highlight?.to }) : '',
    ]);

    const register = state.get('register');
    wrapper.append(swapRow({
      beforeSvg,
      afterSvg,
      changeType: edit.change_type,
      reason: register === 'plain' ? edit.rationale_plain : edit.rationale_specialist,
      deltas: (edit.consequences || []).map((consequence) => ({
        direction: consequence.direction,
        text: deltaText(consequence),
      })),
    }));

    if ((edit.structural_basis || []).length) {
      const chips = document.createElement('div');
      chips.className = 'sheet-tools';
      for (const key of edit.structural_basis) {
        const residue = findResidue(key);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `chip motif-${residue?.motif || 'other'}`;
        button.textContent = residue
          ? `${residue.resname}${residue.resnum}` : key;
        button.title = residue?.role_note || 'Cited as the structural basis for this change';
        button.addEventListener('click', () => {
          state.set({ residues: [key], tab: 'structure', motif: null }, 'editlog:residue-chip');
        });
        chips.append(button);
      }
      wrapper.append(chips);
    }

    const evidence = document.createElement('p');
    evidence.className = 'beat-evidence';
    evidence.textContent = `Evidence: ${edit.evidence}`;
    wrapper.append(evidence);

    const activate = () => {
      /* Both compounds enter a comparison state, and the consequence assays become the
       * plot axes, per the section 8 matrix. */
      const consequences = (edit.consequences || []).map((c) => c.assay_id);
      state.set({
        edit: edit.edit_id,
        compound: edit.to_compound,
        assayX: consequences[1] || state.get('assayX'),
        assayY: consequences[0] || state.get('assayY'),
        residues: edit.structural_basis || [],
      }, 'editlog:card');
    };
    wrapper.addEventListener('click', activate);
    wrapper.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); }
    });
    return wrapper;
  }

  function deltaText(consequence) {
    const spec = bundle.assays[consequence.assay_id] || {};
    const short = spec.short || consequence.assay_id;
    const from = consequence.from === null || consequence.from === undefined ? '?' : consequence.from;
    const to = consequence.to === null || consequence.to === undefined ? '?' : consequence.to;
    const fold = consequence.fold ? ` (${consequence.fold}×)` : '';
    return `${short} ${from} → ${to}${fold}`;
  }

  function findResidue(key) {
    for (const entry of bundle.structures) {
      const residue = bundle.index.residuesByKey.get(`${entry.pdb_id}|${key}`);
      if (residue) return residue;
    }
    return null;
  }

  async function render() {
    if (!bundle) return;
    renderFilters();
    const edits = visibleEdits();

    for (const [hostIndex, host] of hosts.entries()) {
      host.cards.replaceChildren();
      if (!edits.length) {
        host.cards.append(emptyState('No edits of this kind',
          'Choose another change type, or "all", to see the rest of the campaign.'));
        continue;
      }
      /* Each host needs its own nodes: one element cannot live in two places. */
      const cards = await Promise.all(edits.map((edit) => card(edit, hostIndex)));
      host.cards.append(...cards);
    }
  }

  /* Scroll whichever copy of the card is actually on screen. */
  function scrollToEdit(editId) {
    for (const node of document.querySelectorAll(`[data-edit="${editId}"]`)) {
      if (node.offsetParent === null) continue;      // hidden host
      node.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
  }

  state.on(['edit'], () => {
    if (!bundle) return;
    render().then(() => {
      const editId = state.get('edit');
      if (editId) scrollToEdit(editId);
    });
  });
  state.on(['register', 'residues'], render);
  state.on(['compound'], () => {
    /* The log scrolls to the edits entering and leaving the selected compound. */
    if (!bundle) return;
    const compoundId = state.get('compound');
    if (!compoundId) return;
    const ids = bundle.index.editsByCompound[compoundId] || [];
    if (ids.length) scrollToEdit(ids[0]);
  });

  return {
    setBundle(next) {
      bundle = next;
      filter = DEFAULT_FILTER;
      /* A paper may have no isosteres at all, in which case the default filter would show
       * an empty sheet: fall back to showing everything. */
      if (!bundle.edits.some((e) => e.change_type === DEFAULT_FILTER)) filter = null;
      return render();
    },
    render,
  };
}
