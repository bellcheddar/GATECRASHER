/* The Structure sheet. BUILD_SPEC 7.2, and every row of the section 8 matrix that starts here.
 *
 * The pocket ruler degrades to a plain sequence ruler when a structure has no KLIFS mapping,
 * with no missing-data holes in the UI: KRAS is not a kinase and must not look like a kinase
 * with gaps.
 *
 * Contacts are listed from PLIP. Hovering one draws its amber measure line between the two
 * real coordinates. Mol* has no shape builder, so a line is a two-atom HETATM fragment
 * joined by a CONECT record, loaded as a line representation: the same trick GOBSMACKED uses.
 * A contact whose coordinates are missing is listed but never drawn, because a measure line
 * without a measurement is the one thing this drawing grammar forbids. */

import { formatValue, measurement } from '../data.js';
import { colourToInt, emptyState, motifColour, svg } from '../draw.js';
import { StructureViewer, lockCameras } from '../viewers/molstar.js';
import { depictionFor } from '../viewers/rdkit.js';

const MOTIF_ORDER = [
  'gatekeeper', 'hinge', 'DFG', 'catalytic_lys', 'glycine_rich_loop', 'P_loop',
  'switch_I', 'switch_II', 'front_pocket', 'back_pocket', 'solvent_front', 'mutation_site',
];

const TYPE_LABELS = {
  hbond: 'Hydrogen bonds',
  water_bridge: 'Water bridges',
  hydrophobic: 'Hydrophobic',
  pi_stack: 'Pi stacking',
  pi_cation: 'Pi cation',
  salt_bridge: 'Salt bridges',
  halogen: 'Halogen bonds',
};

export function initStructure(state) {
  let bundle = null;
  let target = null;          // StructureViewer
  let anti = null;
  let unlock = null;
  let lineCounter = 0;

  const el = {
    pair: document.getElementById('viewer-pair'),
    targetHost: document.getElementById('viewer-target'),
    antiHost: document.getElementById('viewer-anti'),
    targetLabel: document.getElementById('viewer-target-label'),
    antiLabel: document.getElementById('viewer-anti-label'),
    antiToggle: document.getElementById('anti-toggle'),
    representation: document.getElementById('representation'),
    reset: document.getElementById('reset-camera'),
    chips: document.getElementById('motif-chips'),
    ruler: document.getElementById('klifs-ruler'),
    contacts: document.getElementById('contact-list'),
    contactsNote: document.getElementById('contacts-note'),
    caption: document.getElementById('structure-caption'),
    depiction: document.getElementById('selected-depiction'),
    properties: document.getElementById('selected-properties'),
  };

  /* ------------------------------------------------------------------- viewers */

  function primaryStructure() {
    const chosen = state.get('structure');
    return bundle.structures.find((s) => s.pdb_id === chosen)
      || bundle.structures.find((s) => s.role === 'primary')
      || bundle.structures[0]
      || null;
  }

  function structureUrl(pdbId) {
    /* Coordinates come from RCSB, as BUILD_SPEC 1.3 requires: we publish no copyrighted
     * coordinate files of our own. */
    return `https://files.rcsb.org/download/${pdbId}.cif`;
  }

  async function ensureTarget() {
    if (target) return target;
    if (!StructureViewer.available()) {
      el.pair.replaceChildren(emptyState('The 3D viewer did not load',
        'Everything else on this page still works, and the contacts below are the same data the viewer would draw.'));
      return null;
    }
    target = new StructureViewer(el.targetHost);
    await target.create({ background: colourToInt(cssToken('--surface-2')) });
    target.onResidueClick((residue) => {
      state.set({ residues: [residue.id], motif: null }, 'structure:3d-click');
    });
    return target;
  }

  async function loadTarget() {
    const entry = primaryStructure();
    if (!entry) {
      el.pair.replaceChildren(emptyState('No structure for this campaign',
        'The paper reports no deposited coordinates, so the pocket cannot be drawn.'));
      return;
    }
    const viewer = await ensureTarget();
    if (!viewer) return;
    el.targetLabel.textContent = `${entry.pdb_id} ${entry.contains.protein}`
      + (entry.resolution_a ? ` ${entry.resolution_a} Å` : '');
    await viewer.load('target', structureUrl(entry.pdb_id), {
      representation: el.representation.value,
    });
    viewer.focusLigand();
  }

  /* Creating a WebGL viewer in a hidden tab gives it a 0x0 canvas, and Mol* then throws
   * "empty textures are not allowed" on its first resize. So the load waits until the
   * Structure tab is actually on screen. */
  let pendingLoad = false;

  async function loadTargetWhenVisible() {
    if (!bundle) return;
    if (el.targetHost.clientWidth === 0 || el.targetHost.clientHeight === 0) {
      pendingLoad = true;
      return;
    }
    pendingLoad = false;
    await loadTarget();
  }

  /* The anti-target viewer is off by default and opens on demand: the comparison is
   * available, never imposed. */
  async function toggleAnti(on) {
    el.antiHost.hidden = !on;
    el.antiToggle.setAttribute('aria-pressed', String(on));
    if (!on) {
      unlock?.();
      unlock = null;
      anti?.dispose();
      anti = null;
      return;
    }
    const twin = bundle.structures.find((s) => s.role === 'anti_target');
    if (!twin) {
      el.antiHost.replaceChildren(emptyState('No paired anti-target structure',
        'This paper has no co-structure of the same compound in the protein to be avoided.'));
      return;
    }
    anti = new StructureViewer(el.antiHost);
    await anti.create({ background: colourToInt(cssToken('--surface-2')) });
    el.antiLabel.textContent = `${twin.pdb_id} ${twin.contains.protein}`;
    await anti.load('anti', structureUrl(twin.pdb_id), {
      representation: el.representation.value,
    });
    anti.focusLigand();
    if (target) unlock = lockCameras(target, anti);
  }

  /* --------------------------------------------------------------- motif chips */

  function renderChips() {
    if (!bundle) return;
    const entry = primaryStructure();
    const present = new Set(
      (bundle.index.residuesByStructure[entry?.pdb_id] || []).map((r) => r.motif));
    el.chips.replaceChildren();
    const active = state.get('motif');
    for (const motif of MOTIF_ORDER) {
      if (!present.has(motif)) continue;      // no empty affordances for motifs this protein lacks
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = `chip motif-${motif}`;
      chip.textContent = motif.replace(/_/g, ' ');
      chip.setAttribute('aria-pressed', String(active === motif));
      chip.addEventListener('click', () => {
        const residues = (bundle.index.residuesByMotif[motif] || [])
          .filter((r) => r.pdb_id === entry.pdb_id)
          .map((r) => `${r.chain}:${r.resnum}`);
        state.set({
          motif: active === motif ? null : motif,
          residues: active === motif ? [] : residues,
        }, 'structure:motif-chip');
      });
      el.chips.append(chip);
    }
  }

  /* -------------------------------------------------------------------- ruler */

  function renderRuler() {
    if (!bundle) return;
    const entry = primaryStructure();
    if (!entry) return;
    const residues = (bundle.index.residuesByStructure[entry.pdb_id] || []);
    const isKinase = Boolean(entry.klifs) && residues.some((r) => r.klifs_index !== null);

    /* A kinase shows the 85-position pocket in KLIFS order. Anything else shows its own
     * sequence, in residue order: the same component, no gaps, no dead controls. */
    const track = isKinase
      ? residues.filter((r) => r.klifs_index !== null)
        .sort((a, b) => a.klifs_index - b.klifs_index)
      : residues.slice().sort((a, b) => a.resnum - b.resnum);

    const cellWidth = isKinase ? 13 : 8;
    const height = 46;
    const width = Math.max(track.length * cellWidth, 100);
    el.ruler.replaceChildren();
    const root = svg('svg', {
      viewBox: `0 0 ${width} ${height}`,
      width,
      height,
      role: 'group',
      'aria-label': isKinase ? 'KLIFS pocket ruler, 85 positions' : 'Sequence ruler',
    }, el.ruler);

    const selected = new Set(state.get('residues'));
    track.forEach((residue, i) => {
      const key = `${residue.chain}:${residue.resnum}`;
      const cell = svg('rect', {
        class: 'ruler-cell',
        x: i * cellWidth,
        y: 12,
        width: cellWidth - 1,
        height: 18,
        rx: 1,
        fill: residue.motif === 'other' ? cssToken('--surface') : motifColour(residue.motif),
        'fill-opacity': residue.motif === 'other' ? 0.9 : 0.85,
        stroke: selected.has(key) ? cssToken('--focus') : cssToken('--line'),
        'stroke-width': selected.has(key) ? 1.5 : 0.5,
        'aria-selected': String(selected.has(key)),
        tabindex: '-1',
      }, root);
      cell.dataset.residue = key;
      const title = svg('title', {}, cell);
      title.textContent = `${residue.resname}${residue.resnum}`
        + (residue.klifs_index ? ` · KLIFS ${residue.klifs_index}` : '')
        + (residue.motif !== 'other' ? ` · ${residue.motif.replace(/_/g, ' ')}` : '')
        + (residue.role_note ? ` · ${residue.role_note}` : '');

      cell.addEventListener('click', () => {
        state.set({ residues: [key], motif: null }, 'structure:ruler-click');
      });
      cell.addEventListener('mouseenter', () => target?.highlight([key]));

      /* Ticks: the first position and every tenth, so the ruler reads as a ruler. */
      const tickEvery = isKinase ? 10 : 25;
      if (i === 0 || (i + 1) % tickEvery === 0) {
        const label = svg('text', {
          class: 'ruler-tick',
          x: i * cellWidth + (cellWidth - 1) / 2,
          y: 42,
          'text-anchor': 'middle',
        }, root);
        label.textContent = isKinase ? String(residue.klifs_index) : String(residue.resnum);
      }
    });

    if (!track.length) {
      el.ruler.replaceChildren(emptyState('No residue annotation yet',
        'Run gc struct for this paper to build the pocket ruler.'));
    }
  }

  function scrollRulerTo(residueKey) {
    const cell = el.ruler.querySelector(`[data-residue="${residueKey}"]`);
    if (!cell) return;
    const box = cell.getBoundingClientRect();
    const host = el.ruler.getBoundingClientRect();
    /* Only scroll when the position is actually out of view, so selecting a visible
     * residue does not make the ruler jump. */
    if (box.left < host.left || box.right > host.right) {
      el.ruler.scrollLeft += box.left - host.left - host.width / 2;
    }
  }

  /* ----------------------------------------------------------------- contacts */

  function renderContacts() {
    if (!bundle) return;
    const entry = primaryStructure();
    const data = entry ? bundle.interactions[entry.pdb_id] : null;
    el.contacts.replaceChildren();

    if (!data || !data.interactions.length) {
      el.contacts.append(emptyState('No contacts computed',
        'PLIP has not run for this structure yet.'));
      return;
    }

    const selected = new Set(state.get('residues'));
    const groups = new Map();
    for (const contact of data.interactions) {
      if (!groups.has(contact.type)) groups.set(contact.type, []);
      groups.get(contact.type).push(contact);
    }

    for (const [type, contacts] of [...groups.entries()]
      .sort((a, b) => Object.keys(TYPE_LABELS).indexOf(a[0]) - Object.keys(TYPE_LABELS).indexOf(b[0]))) {
      const head = document.createElement('div');
      head.className = 'contact-group-head';
      head.textContent = `${TYPE_LABELS[type] || type} (${contacts.length})`;
      el.contacts.append(head);

      for (const contact of contacts.sort((a, b) => a.distance_a - b.distance_a)) {
        const key = `${contact.chain}:${contact.resnum}`;
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'contact-row';
        if (selected.has(key)) row.style.borderColor = cssToken('--focus');

        const residue = document.createElement('span');
        residue.className = 'residue';
        residue.textContent = `${contact.residue}${contact.resnum}`;

        const kind = document.createElement('span');
        kind.className = 'contact-type';
        kind.textContent = contact.type === 'water_bridge'
          ? `via water${contact.water_idx ? ` ${contact.water_idx}` : ''}`
          : (contact.protein_is_donor === true ? 'protein donates'
            : contact.protein_is_donor === false ? 'ligand donates' : '');

        const distance = document.createElement('span');
        distance.className = 'contact-distance';
        distance.textContent = `${contact.distance_a.toFixed(2)} Å`;
        if (contact.type === 'water_bridge' && contact.distance_donor_water_a) {
          distance.textContent = `${contact.distance_a.toFixed(2)} / `
            + `${contact.distance_donor_water_a.toFixed(2)} Å`;
          distance.title = 'acceptor-to-water and donor-to-water legs';
        }
        if (!contact.ligand_coords || !contact.protein_coords) {
          distance.title = (distance.title ? `${distance.title}. ` : '')
            + 'PLIP reported no coordinates for this contact, so it is listed but not drawn';
          distance.style.opacity = '0.75';
        }

        row.append(residue, kind, distance);
        row.addEventListener('mouseenter', () => {
          target?.highlight([key]);
          drawMeasure(contact);
        });
        row.addEventListener('mouseleave', () => clearMeasure());
        row.addEventListener('click', () => {
          state.set({ residues: [key], motif: null }, 'structure:contact-row');
        });
        el.contacts.append(row);
      }
    }

    const note = [];
    if (data.ligand_code) note.push(`ligand ${data.ligand_code}`);
    note.push(`${data.interactions.length} contacts from PLIP`);
    el.contactsNote.textContent = note.join(' · ');
  }

  /* A two-atom fragment, joined by CONECT, drawn as a line: Mol* has no shape builder. */
  async function drawMeasure(contact) {
    if (!target || !contact.ligand_coords || !contact.protein_coords) return;
    const name = `measure-${lineCounter += 1}`;
    const pdb = measurePdb(contact.ligand_coords, contact.protein_coords);
    await target.clear('measure').catch(() => {});
    try {
      const data = await target.plugin.builders.data.rawData({ data: pdb });
      const trajectory = await target.plugin.builders.structure.parseTrajectory(data, 'pdb');
      const model = await target.plugin.builders.structure.createModel(trajectory);
      const structure = await target.plugin.builders.structure.createStructure(model);
      const component = await target.plugin.builders.structure
        .tryCreateComponentStatic(structure, 'all');
      if (component) {
        await target.plugin.builders.structure.representation.addRepresentation(component, {
          type: 'line',
          color: 'uniform',
          colorParams: { value: colourToInt(cssToken('--measure')) },
        });
      }
      target.loaded.set('measure', { structure, components: { all: component }, model, name });
    } catch (err) {
      /* A measure line that cannot be drawn is not worth an error to the reader: the
       * distance is already on the row they are hovering. */
    }
  }

  function clearMeasure() {
    target?.clear('measure').catch(() => {});
  }

  function measurePdb([x1, y1, z1], [x2, y2, z2]) {
    const atom = (serial, x, y, z) =>
      `HETATM${String(serial).padStart(5)} X${serial}  MSR X   1    `
      + `${x.toFixed(3).padStart(8)}${y.toFixed(3).padStart(8)}${z.toFixed(3).padStart(8)}`
      + '  1.00  0.00           X';
    return [
      atom(1, x1, y1, z1),
      atom(2, x2, y2, z2),
      'CONECT    1    2',
      'CONECT    2    1',
      'END',
    ].join('\n');
  }

  /* ------------------------------------------------------- selected compound */

  async function renderSelected() {
    if (!bundle) return;
    const compoundId = state.get('compound');
    const compound = compoundId ? bundle.index.compoundById.get(compoundId) : null;
    if (!compound) {
      el.depiction.replaceChildren(emptyState('No compound selected',
        'Pick a compound in the SAR table, on a plot, or in the edit log.'));
      el.properties.replaceChildren();
      return;
    }

    el.depiction.innerHTML = await depictionFor(bundle, compound);

    /* Does a structure exist for this compound? If not, say so explicitly rather than
     * leaving the viewer showing someone else's ligand without comment. */
    const entry = bundle.index.structureForCompound.get(compoundId);
    const rows = [
      ['MW', compound.mw],
      ['cLogP', compound.clogp],
      ['TPSA', compound.tpsa],
      ['HAC', compound.hac],
      ['Fsp3', compound.fsp3],
    ];
    const primary = bundle.index.primaryAssay;
    const potency = measurement(bundle, compoundId, primary);
    if (potency) {
      rows.unshift([bundle.assays[primary].short,
        `${formatValue(bundle, potency, { withUnits: true })}`]);
    }

    el.properties.replaceChildren();
    const body = el.properties.createTBody();
    for (const [label, value] of rows) {
      const tr = body.insertRow();
      const key = tr.insertCell();
      key.textContent = label;
      const val = tr.insertCell();
      val.className = 'num';
      val.textContent = value;
    }
    const tr = body.insertRow();
    const note = tr.insertCell();
    note.colSpan = 2;
    note.className = 'mono';
    note.textContent = entry
      ? `crystallised in ${entry.pdb_id}`
      : 'no structure for this compound in this paper';
    if (!entry) note.style.color = cssToken('--ink-dim');
  }

  function renderCaption() {
    if (!bundle) return;
    const entry = primaryStructure();
    if (!entry) return;
    const register = state.get('register');
    el.caption.textContent = register === 'plain'
      ? entry.caption_plain : entry.caption_specialist;
  }

  /* ------------------------------------------------------------------ wiring */

  el.antiToggle.addEventListener('click', () => {
    state.set({ antiTargetOn: !state.get('antiTargetOn') }, 'structure:anti-toggle');
  });
  el.representation.addEventListener('change', () => {
    target?.represent('target', el.representation.value);
    anti?.represent('anti', el.representation.value);
  });
  el.reset.addEventListener('click', () => {
    target?.focusLigand();
    state.set({ residues: [], motif: null }, 'structure:reset');
  });

  /* Every subscriber guards on the bundle: state is applied before the panels are handed
   * their data, so the first dispatch of a paper swap reaches panels that have nothing to
   * render yet. */
  state.on(['residues'], () => {
    if (!bundle) return;
    const residues = state.get('residues');
    renderRuler();
    renderContacts();
    if (residues.length) {
      target?.select(residues);
      target?.focusResidues(residues);
      scrollRulerTo(residues[0]);
    }
  });
  state.on(['tab'], () => {
    if (state.get('tab') !== 'structure') return;
    /* This panel subscribed before the shell did, and subscribers run in registration
     * order, so at this moment the tab section is still hidden and the host still measures
     * 0x0. Waiting a frame lets the shell unhide it first, which is the whole point of
     * deferring the load. */
    requestAnimationFrame(() => {
      if (state.get('tab') !== 'structure') return;
      if (pendingLoad) loadTargetWhenVisible();
      else target?.resize();
    });
  });
  state.on(['motif'], () => { if (bundle) renderChips(); });
  state.on(['compound'], renderSelected);
  state.on(['register'], () => { if (bundle) renderCaption(); });
  state.on(['antiTargetOn'], () => { if (bundle) toggleAnti(state.get('antiTargetOn')); });

  return {
    async setBundle(next) {
      bundle = next;
      unlock?.();
      unlock = null;
      anti?.dispose();
      anti = null;
      el.antiHost.hidden = true;
      el.antiToggle.setAttribute('aria-pressed', 'false');
      await loadTargetWhenVisible();
      renderChips();
      renderRuler();
      renderContacts();
      renderCaption();
      await renderSelected();
    },
    render() {
      renderChips();
      renderRuler();
      renderContacts();
      renderCaption();
      renderSelected();
    },
  };
}

function cssToken(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
