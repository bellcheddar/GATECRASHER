/* The SAR sheet: R-group grid, pivoted compound table, selectivity matrix, activity cliffs.
 * BUILD_SPEC 7.4, and the rows of the section 8 matrix that start in this panel.
 *
 * Qualifiers are preserved as text everywhere. A bound is never sorted as a number, and an
 * empty cell is drawn as deliberately empty rather than left blank. */

import { formatValue, measurement, numericValue, selectivityFold } from '../data.js';
import { emptyState } from '../draw.js';
import { depictFragment, precomputed, ready as rdkitReady } from '../viewers/rdkit.js';

export function initSar(state) {
  let bundle = null;
  let sort = { key: null, dir: 1 };
  let filterCompounds = null;      // Set of ids, set by cross-links from other panels

  const el = {
    grid: document.getElementById('rgroup-grid'),
    table: document.getElementById('compound-table'),
    matrix: document.getElementById('selectivity-matrix'),
    cliffs: document.getElementById('cliffs-table'),
  };

  /* --------------------------------------------------------------- R-group grid
   * Positions across, substituents down, primary potency as colour. Axis labels are
   * rendered substituent drawings, not SMILES strings. */
  async function renderGrid() {
    const positions = new Map();     // position -> Map(label -> {smiles, compounds[]})
    for (const compound of bundle.compounds) {
      for (const [position, spec] of Object.entries(compound.r_groups || {})) {
        if (!positions.has(position)) positions.set(position, new Map());
        const byLabel = positions.get(position);
        if (!byLabel.has(spec.label)) byLabel.set(spec.label, { smiles: spec.smiles, compounds: [] });
        byLabel.get(spec.label).compounds.push(compound.compound_id);
      }
    }
    if (!positions.size) {
      el.grid.replaceChildren(emptyState('No R-group table for this paper',
        'The published SAR is not laid out by substituent position.'));
      return;
    }

    const table = document.createElement('table');
    const head = table.createTHead().insertRow();
    head.appendChild(th(''));
    const positionKeys = [...positions.keys()].sort();
    for (const position of positionKeys) head.appendChild(th(position));

    const labels = new Set();
    for (const byLabel of positions.values()) for (const label of byLabel.keys()) labels.add(label);

    const body = table.createTBody();
    for (const label of [...labels].sort()) {
      const row = body.insertRow();
      const header = document.createElement('th');
      header.scope = 'row';
      const holder = document.createElement('div');
      holder.className = 'depiction';
      header.append(holder);
      const caption = document.createElement('div');
      caption.className = 'mono';
      caption.style.fontSize = '10px';
      caption.textContent = label;
      header.append(caption);
      row.append(header);

      /* A substituent drawing beats its SMILES for a chemist reading a grid. */
      const firstSpec = [...positions.values()].map((m) => m.get(label)).find(Boolean);
      if (firstSpec && rdkitReady()) {
        const svgText = depictFragment(firstSpec.smiles);
        if (svgText) holder.innerHTML = svgText;
      }

      for (const position of positionKeys) {
        const entry = positions.get(position).get(label);
        const cell = row.insertCell();
        if (!entry) {
          cell.className = 'rgroup-cell is-empty';
          cell.title = `No compound in this paper carries ${label} at ${position}`;
          cell.setAttribute('aria-label', 'not made');
          continue;
        }
        cell.className = 'rgroup-cell';
        const compoundId = entry.compounds[0];
        const row0 = measurement(bundle, compoundId, bundle.index.primaryAssay);
        cell.textContent = formatValue(bundle, row0) ?? '·';
        cell.title = `compound ${entry.compounds.join(', ')}`;
        cell.style.background = potencyColour(numericValue(row0));
        cell.tabIndex = 0;
        cell.addEventListener('click', () => {
          state.set({ compound: compoundId }, 'sar:rgroup-cell');
        });
        cell.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            state.set({ compound: compoundId }, 'sar:rgroup-cell');
          }
        });
      }
    }
    el.grid.replaceChildren(table);
  }

  /* Colour on a log scale between the best and worst primary potency in the campaign. */
  function potencyColour(value) {
    if (!value) return 'transparent';
    const values = bundle.compounds
      .map((c) => numericValue(measurement(bundle, c.compound_id, bundle.index.primaryAssay)))
      .filter(Boolean);
    if (!values.length) return 'transparent';
    const min = Math.log10(Math.min(...values));
    const max = Math.log10(Math.max(...values));
    const span = max - min || 1;
    const t = 1 - (Math.log10(value) - min) / span;   // 1 = most potent
    return `color-mix(in srgb, var(--target) ${Math.round(t * 55)}%, var(--surface))`;
  }

  /* ------------------------------------------------------------- compound table */
  function columns() {
    const primary = bundle.index.primaryAssay;
    const order = ['potency', 'selectivity', 'cell', 'property', 'adme', 'pk'];
    const ids = [];
    if (primary) ids.push(primary);
    for (const category of order) {
      for (const id of bundle.index.byCategory[category] || []) {
        if (id !== primary && bundle.index.byAssay.has(id)) ids.push(id);
      }
    }
    return ids;
  }

  function renderTable() {
    const assayIds = columns();
    const table = el.table;
    table.replaceChildren();

    const head = table.createTHead().insertRow();
    head.append(sortableTh('compound', 'compound_id'));
    for (const id of assayIds) {
      const spec = bundle.assays[id];
      const cell = sortableTh(spec.short || id, id, true);
      cell.title = `${spec.label}${spec.units ? ` (${spec.units})` : ''}`
        + `${spec.conditions ? `, ${spec.conditions}` : ''}`;
      head.append(cell);
    }

    let rows = bundle.compounds.slice();
    if (filterCompounds) rows = rows.filter((c) => filterCompounds.has(c.compound_id));

    if (sort.key) {
      rows.sort((a, b) => compare(a, b, sort.key) * sort.dir);
    }

    const body = table.createTBody();
    const selected = state.get('compound');
    for (const compound of rows) {
      const tr = body.insertRow();
      tr.tabIndex = 0;
      if (compound.compound_id === selected) tr.setAttribute('aria-selected', 'true');

      const first = tr.insertCell();
      first.className = 'mono';
      first.textContent = compound.label;
      if (compound.role === 'lead') first.title = 'lead candidate';

      for (const id of assayIds) {
        const cell = tr.insertCell();
        cell.className = 'num';
        const row = measurement(bundle, compound.compound_id, id);
        const text = formatValue(bundle, row);
        if (text === null) {
          cell.className = 'num cell-empty';
          cell.title = 'not reported for this compound';
          continue;
        }
        if (row.qualifier !== '=') {
          cell.classList.add('value-bounded');
          cell.title = `reported as ${row.qualifier}${row.value}: a bound, not a measurement`
            + ` (${row.source_table})`;
        } else {
          cell.title = `${row.source_table}${row.source_note ? `: ${row.source_note}` : ''}`;
        }
        cell.textContent = text;
      }

      const select = () => state.set({ compound: compound.compound_id }, 'sar:table-row');
      tr.addEventListener('click', select);
      tr.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(); }
      });
    }

    if (!rows.length) {
      el.table.replaceChildren();
      el.table.parentElement.replaceChildren(
        emptyState('No compound matches this selection',
          'Clear the residue or motif selection to see the whole campaign again.'));
    }
  }

  function compare(a, b, key) {
    if (key === 'compound_id') {
      return collate(a.compound_id, b.compound_id);
    }
    /* Bounds sort after every measurement rather than pretending to be their number. */
    const rowA = measurement(bundle, a.compound_id, key);
    const rowB = measurement(bundle, b.compound_id, key);
    const valA = numericValue(rowA);
    const valB = numericValue(rowB);
    if (valA === null && valB === null) return 0;
    if (valA === null) return 1;
    if (valB === null) return -1;
    return valA - valB;
  }

  function collate(a, b) {
    const na = parseInt(a, 10);
    const nb = parseInt(b, 10);
    if (Number.isFinite(na) && Number.isFinite(nb) && na !== nb) return na - nb;
    return String(a).localeCompare(String(b));
  }

  function sortableTh(text, key, numeric = false) {
    const cell = document.createElement('th');
    cell.textContent = text;
    cell.scope = 'col';
    if (numeric) cell.classList.add('num');
    cell.tabIndex = 0;
    if (sort.key === key) {
      cell.textContent = `${text} ${sort.dir === 1 ? '↑' : '↓'}`;
      cell.setAttribute('aria-sort', sort.dir === 1 ? 'ascending' : 'descending');
    }
    const activate = () => {
      sort = { key, dir: sort.key === key ? -sort.dir : 1 };
      renderTable();
    };
    cell.addEventListener('click', activate);
    cell.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); }
    });
    return cell;
  }

  /* ---------------------------------------------------------- selectivity matrix
   * Target against every anti-target, fold values, coloured on a log scale. Driven entirely
   * by assays.json anti_target_of, so it needs no per-paper code. */
  function renderMatrix() {
    const antis = bundle.index.antiTargets.filter((a) => bundle.index.byAssay.has(a.id));
    if (!antis.length) {
      el.matrix.replaceChildren();
      el.matrix.parentElement.replaceChildren(
        emptyState('No counter-screen in this paper', 'Nothing is marked as an anti-target assay.'));
      return;
    }
    const table = el.matrix;
    table.replaceChildren();
    const head = table.createTHead().insertRow();
    head.append(th('compound'));
    for (const anti of antis) head.append(th(bundle.assays[anti.id].short || anti.id, true));

    const body = table.createTBody();
    const selected = state.get('compound');
    for (const compound of bundle.compounds) {
      const tr = body.insertRow();
      if (compound.compound_id === selected) tr.setAttribute('aria-selected', 'true');
      const first = tr.insertCell();
      first.className = 'mono';
      first.textContent = compound.label;

      for (const anti of antis) {
        const cell = tr.insertCell();
        cell.className = 'fold';
        /* Prefer the fold the paper printed. Only compute one where the paper did not. */
        const published = measurement(bundle, compound.compound_id, publishedFoldId(anti.id));
        const fold = published ? published.value : selectivityFold(bundle, compound.compound_id, anti.id);
        if (!fold) {
          cell.className = 'fold cell-empty';
          continue;
        }
        cell.textContent = `${fold >= 100 ? Math.round(fold) : fold.toFixed(1)}×`;
        cell.title = published
          ? `published fold (${published.source_table})`
          : 'computed from the IC50 columns, because this paper prints no fold for it';
        if (!published) cell.style.fontStyle = 'italic';
        cell.style.background = foldColour(fold);
      }
    }
  }

  function publishedFoldId(antiAssayId) {
    return Object.keys(bundle.assays)
      .find((id) => bundle.assays[id].of_assay === antiAssayId) || null;
  }

  function foldColour(fold) {
    const t = Math.min(1, Math.max(0, (Math.log10(fold) - 1) / 3));   // 10x to 10000x
    return `color-mix(in srgb, var(--gain) ${Math.round(t * 50)}%, var(--surface))`;
  }

  /* --------------------------------------------------------------- activity cliffs */
  function renderCliffs() {
    const table = el.cliffs;
    table.replaceChildren();
    if (!bundle.cliffs?.length) {
      table.parentElement.replaceChildren(
        emptyState('No matched pairs cleared the threshold',
          'A cliff needs two compounds that differ in one place and in potency.'));
      return;
    }
    const head = table.createTHead().insertRow();
    ['pair', 'fold', 'atoms', 'fold per atom'].forEach((text, i) => head.append(th(text, i > 0)));
    const body = table.createTBody();
    for (const cliff of bundle.cliffs.slice(0, 20)) {
      const tr = body.insertRow();
      tr.tabIndex = 0;
      const pair = tr.insertCell();
      pair.className = 'mono';
      pair.textContent = `${cliff.from_compound} → ${cliff.to_compound}`;
      num(tr, `${cliff.fold}×`);
      num(tr, cliff.atoms_changed);
      num(tr, cliff.fold_per_atom);

      const activate = () => {
        /* Both compounds select, and the edit linking them opens where one exists. */
        const edit = bundle.edits.find((e) =>
          (e.from_compound === cliff.from_compound && e.to_compound === cliff.to_compound)
          || (e.from_compound === cliff.to_compound && e.to_compound === cliff.from_compound));
        state.set({
          compound: cliff.to_compound,
          edit: edit ? edit.edit_id : null,
        }, 'sar:cliff-row');
      };
      tr.addEventListener('click', activate);
      tr.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); }
      });
    }
  }

  function num(tr, text) {
    const cell = tr.insertCell();
    cell.className = 'num';
    cell.textContent = text;
    return cell;
  }

  function th(text, numeric = false) {
    const cell = document.createElement('th');
    cell.textContent = text;
    cell.scope = 'col';
    if (numeric) cell.classList.add('num');
    return cell;
  }

  /* A residue or motif selection filters the table to the compounds whose edits cite it. */
  function applyResidueFilter() {
    const residues = state.get('residues');
    if (!residues.length) {
      filterCompounds = null;
      return;
    }
    const ids = new Set();
    for (const key of residues) {
      for (const editId of bundle.index.editsByResidue[key] || []) {
        const edit = bundle.index.editById.get(editId);
        if (!edit) continue;
        ids.add(edit.from_compound);
        ids.add(edit.to_compound);
      }
    }
    filterCompounds = ids.size ? ids : null;
  }

  async function renderAll() {
    if (!bundle) return;
    applyResidueFilter();
    await renderGrid();
    renderTable();
    renderMatrix();
    renderCliffs();
  }

  state.on(['compound'], () => {
    if (!bundle) return;
    renderTable();
    renderMatrix();
  });
  state.on(['residues'], () => { renderAll(); });

  return {
    setBundle(next) {
      bundle = next;
      sort = { key: null, dir: 1 };
      filterCompounds = null;
      renderAll();
    },
    render: renderAll,
  };
}
