/* Mol* wrapper. Lifted in spirit from GOBSMACKED/app/static/js/viewer.js, with its traps.
 *
 * Traps carried forward, each of which fails silently if ignored:
 *   - extensions MUST be empty, or creating the viewer makes a network request
 *   - set the representation FIRST and the colour SECOND, or the colour is discarded
 *   - loci indices are positions inside unit.elements, NOT atom ids: getting this wrong
 *     highlights the wrong atoms with no error anywhere
 *   - the canvas sizes itself once, so handleResize must be called from a ResizeObserver
 *   - transparentBackground clears to white, so the panel colour is painted explicitly */

import { loadLibrary } from '../loader.js';

/* Cut an mmCIF down to one copy of the molecule: the chain this bundle describes, plus any
 * polymer chain of a DIFFERENT entity, so a real hetero dimer survives while a second copy
 * of the same protein does not. Filtering the text beats filtering inside Mol*: the viewer
 * then measures, focuses and highlights exactly what it draws, and nothing downstream has to
 * know about the discarded copy.
 *
 * Only the _atom_site loop is touched. Everything else in the file is left alone, and if the
 * loop cannot be understood the original text is returned rather than a half-filtered one. */
export function oneCopy(text, chain) {
  const lines = text.split('\n');
  const headerStart = lines.findIndex((line) => line.startsWith('_atom_site.'));
  if (headerStart < 0) return text;

  const columns = [];
  let index = headerStart;
  while (index < lines.length && lines[index].startsWith('_atom_site.')) {
    columns.push(lines[index].trim().slice('_atom_site.'.length));
    index += 1;
  }
  const authColumn = columns.indexOf('auth_asym_id');
  const entityColumn = columns.indexOf('label_entity_id');
  const groupColumn = columns.indexOf('group_PDB');
  if (authColumn < 0) return text;

  const rowStart = index;
  let rowEnd = rowStart;
  while (rowEnd < lines.length) {
    const line = lines[rowEnd];
    if (!line.trim() || line.startsWith('#') || line.startsWith('loop_') || line.startsWith('_')) break;
    rowEnd += 1;
  }

  /* Values can be quoted, and an atom name such as "C1'" carries a quote of its own. */
  const cells = (line) => line.match(/'[^']*'|"[^"]*"|\S+/g) || [];
  const rows = lines.slice(rowStart, rowEnd).map((line) => ({ line, parts: cells(line) }));
  const isPolymer = (parts) => groupColumn < 0 || parts[groupColumn] === 'ATOM';

  let ownEntity = null;
  const polymerEntities = new Set();
  for (const row of rows) {
    if (!isPolymer(row.parts)) continue;
    const entity = entityColumn >= 0 ? row.parts[entityColumn] : null;
    if (entity !== null) polymerEntities.add(entity);
    if (ownEntity === null && row.parts[authColumn] === chain) ownEntity = entity;
  }

  const keep = new Set([chain]);
  if (ownEntity !== null && entityColumn >= 0) {
    for (const row of rows) {
      if (!isPolymer(row.parts)) continue;
      const entity = row.parts[entityColumn];
      if (polymerEntities.has(entity) && entity !== ownEntity) keep.add(row.parts[authColumn]);
    }
  }

  const kept = rows.filter((row) => keep.has(row.parts[authColumn]));
  if (!kept.length || kept.length === rows.length) return text;
  return [...lines.slice(0, rowStart), ...kept.map((row) => row.line), ...lines.slice(rowEnd)]
    .join('\n');
}

const OPTIONS = {
  extensions: [],
  layoutIsExpanded: false,
  layoutShowControls: false,
  layoutShowRemoteState: false,
  layoutShowSequence: false,
  layoutShowLog: false,
  layoutShowLeftPanel: false,
  viewportShowExpand: false,
  viewportShowControls: false,
  viewportShowSettings: false,
  viewportShowSelectionMode: false,
  viewportShowAnimation: false,
  pdbProvider: 'rcsb',
  emdbProvider: 'rcsb',
};

export class StructureViewer {
  constructor(host) {
    this.host = host;
    this.viewer = null;
    this.plugin = null;
    this.loaded = new Map();      // name -> { structure, components }
    this._clickHandlers = new Set();
    this._observer = null;
  }

  static available() {
    return typeof window !== 'undefined' && typeof window.molstar !== 'undefined';
  }

  /* Mol* is 5 MB of JavaScript, fetched the first time a viewer is actually wanted rather
   * than blocking the first paint. Resolves false if it cannot be loaded. */
  static async ensure() {
    if (StructureViewer.available()) return true;
    try {
      await loadLibrary('molstar');
    } catch (err) {
      console.warn('[molstar] did not load', err);
    }
    return StructureViewer.available();
  }

  async create({ background } = {}) {
    if (!StructureViewer.available()) throw new Error('Mol* is not loaded');
    const gl = document.createElement('canvas').getContext('webgl2')
      || document.createElement('canvas').getContext('webgl');
    if (!gl) throw new Error('no WebGL');

    this.viewer = await window.molstar.Viewer.create(this.host, OPTIONS);
    this.plugin = this.viewer.plugin;

    this.plugin.canvas3d?.setProps({
      transparentBackground: false,
      renderer: { backgroundColor: background ?? 0x0B2542 },
      camera: { helper: { axes: { name: 'off', params: {} } } },
    });

    /* Resizing to a zero box asks WebGL for an empty texture, which throws
     * "empty textures are not allowed" and leaves the viewer dead. A host inside a hidden
     * tab measures exactly 0x0, so every resize is guarded on a real box. */
    this._observer = new ResizeObserver(() => this.resize());
    this._observer.observe(this.host);
    window.addEventListener('resize', () => this.resize());

    this.plugin.behaviors.interaction.click.subscribe((event) => {
      const residue = this._residueFromLoci(event?.current?.loci);
      if (residue) this._clickHandlers.forEach((fn) => fn(residue));
    });
    return this;
  }

  setBackground(colourInt) {
    this.plugin?.canvas3d?.setProps({ renderer: { backgroundColor: colourInt } });
  }

  /* True only when the host actually occupies space: a viewer in a hidden tab does not. */
  visible() {
    return this.host.clientWidth > 0 && this.host.clientHeight > 0;
  }

  resize() {
    if (!this.plugin || !this.visible()) return false;
    this.plugin.handleResize();
    return true;
  }

  /* Load a structure by URL. The format is decided from the URL and the payload, not
   * assumed: an mmCIF served without an extension still has to load.
   *
   * `chain` keeps one copy of the protein: see oneCopy below. */
  async load(name, url, { representation = 'cartoon', colour = null, chain = null } = {}) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${url}: ${response.status}`);
    const raw = await response.text();
    const format = /\.cif|\.bcif/i.test(url) || raw.startsWith('data_') ? 'mmcif' : 'pdb';
    const text = format === 'mmcif' && chain ? oneCopy(raw, chain) : raw;

    if (this.loaded.has(name)) await this.clear(name);
    const data = await this.plugin.builders.data.rawData({ data: text });
    const trajectory = await this.plugin.builders.structure.parseTrajectory(data, format);
    const model = await this.plugin.builders.structure.createModel(trajectory);
    const structure = await this.plugin.builders.structure.createStructure(model);
    const components = {
      polymer: await this.plugin.builders.structure.tryCreateComponentStatic(structure, 'polymer'),
      ligand: await this.plugin.builders.structure.tryCreateComponentStatic(structure, 'ligand'),
      water: await this.plugin.builders.structure.tryCreateComponentStatic(structure, 'water'),
    };

    this.loaded.set(name, { structure, components, model });
    await this.represent(name, representation);
    if (colour) await this.colour(name, colour);
    return this.loaded.get(name);
  }

  async clear(name) {
    const entry = this.loaded.get(name);
    if (!entry) return;
    await this.plugin.build().delete(entry.structure).commit();
    this.loaded.delete(name);
  }

  /* Representation first. Colour second. Never the other way round. */
  async represent(name, preset = 'cartoon') {
    const entry = this.loaded.get(name);
    if (!entry) return;
    const { polymer, ligand, water } = entry.components;
    const builder = this.plugin.builders.structure.representation;

    const polymerType = preset === 'surface' ? 'molecular-surface'
      : preset === 'pocket' ? 'ball-and-stick'
        : 'cartoon';
    const polymerColour = preset === 'bfactor' ? 'uncertainty' : 'chain-id';

    if (polymer) {
      await builder.addRepresentation(polymer, { type: polymerType, color: polymerColour });
    }
    if (ligand) {
      await builder.addRepresentation(ligand, { type: 'ball-and-stick', color: 'element-symbol' });
    }
    if (water && preset === 'pocket') {
      await builder.addRepresentation(water, { type: 'ball-and-stick', color: 'element-symbol' });
    }
  }

  async colour(name, colourInt) {
    const entry = this.loaded.get(name);
    if (!entry) return;
    const components = Object.values(entry.components).filter(Boolean);
    await this.plugin.managers.structure.component.updateRepresentationsTheme(components, {
      color: 'uniform',
      colorParams: { value: colourInt },
    });
  }

  /* ------------------------------------------------------------------ loci */

  /* The plain viewer build exposes only Viewer, lib and version on the global: there is no
   * StructureElement, SortedArray, StructureProperties or Structure to call. So a loci is
   * built as the plain object Mol* accepts internally, exactly as GOBSMACKED does, and every
   * lookup walks model.atomicHierarchy by hand. */
  _structureData(name = null) {
    const entry = name ? this.loaded.get(name) : this.loaded.values().next().value;
    const cell = entry?.structure;
    return cell?.data ?? cell?.obj?.data ?? null;
  }

  _componentData(key, name = null) {
    const entry = name ? this.loaded.get(name) : this.loaded.values().next().value;
    const cell = entry?.components?.[key];
    return cell?.data ?? cell?.obj?.data ?? null;
  }

  _residueLoci(residues, name = null) {
    const structure = this._structureData(name);
    if (!structure) return null;

    const wanted = new Set(residues.map((id) => String(id)));
    const elements = [];
    for (const unit of structure.units) {
      const hierarchy = unit.model?.atomicHierarchy;
      if (!hierarchy?.residueAtomSegments) continue;
      const indices = [];
      /* indices are positions INSIDE unit.elements, not atom ids. A loci built with atom
       * ids is accepted, highlights the wrong atoms, and never errors. */
      for (let i = 0; i < unit.elements.length; i += 1) {
        const element = unit.elements[i];
        const chain = hierarchy.chains.auth_asym_id
          .value(hierarchy.chainAtomSegments.index[element]);
        const seq = hierarchy.residues.auth_seq_id
          .value(hierarchy.residueAtomSegments.index[element]);
        if (wanted.has(`${chain}:${seq}`)) indices.push(i);
      }
      if (indices.length) elements.push({ unit, indices: new Int32Array(indices) });
    }
    if (!elements.length) return null;
    return { kind: 'element-loci', structure, elements };
  }

  _wholeLoci(key = null, name = null) {
    const structure = key ? this._componentData(key, name) : this._structureData(name);
    if (!structure?.units?.length) return null;
    const elements = structure.units.map((unit) => ({
      unit,
      indices: new Int32Array(unit.elements.length).map((_, i) => i),
    }));
    return { kind: 'element-loci', structure, elements };
  }

  _residueFromLoci(loci) {
    if (!loci || loci.kind !== 'element-loci' || !loci.elements?.length) return null;
    const entry = loci.elements[0];
    if (!entry.indices?.length) return null;
    const { unit } = entry;
    const hierarchy = unit.model?.atomicHierarchy;
    if (!hierarchy?.residueAtomSegments) return null;
    const element = unit.elements[entry.indices[0]];
    const residueIndex = hierarchy.residueAtomSegments.index[element];
    const chain = hierarchy.chains.auth_asym_id
      .value(hierarchy.chainAtomSegments.index[element]);
    const seq = hierarchy.residues.auth_seq_id.value(residueIndex);
    const resname = hierarchy.atoms?.auth_comp_id
      ? hierarchy.atoms.auth_comp_id.value(element)
      : hierarchy.residues.auth_comp_id.value(residueIndex);
    return { id: `${chain}:${seq}`, chain, resnum: seq, resname };
  }

  highlight(residues) {
    const loci = this._residueLoci(residues);
    if (!loci) {
      this.plugin.managers.interactivity.lociHighlights.clearHighlights();
      return false;
    }
    this.plugin.managers.interactivity.lociHighlights.highlightOnly({ loci });
    return true;
  }

  select(residues) {
    const loci = this._residueLoci(residues);
    this.plugin.managers.interactivity.lociSelects?.deselectAll?.();
    if (!loci) return false;
    this.plugin.managers.structure.selection.fromLoci('set', loci);
    return true;
  }

  focusResidues(residues, { extraRadius = 6, minRadius = 12 } = {}) {
    const loci = this._residueLoci(residues);
    if (!loci) return false;
    this.plugin.managers.camera.focusLoci(loci, {
      extraRadius, minRadius, durationMs: reduced() ? 0 : 320,
    });
    return true;
  }

  focusLigand({ extraRadius = 12, minRadius = 20 } = {}) {
    /* Fall back to the whole structure when a structure has no ligand component, so an apo
     * entry still opens on something rather than on an empty camera. */
    const loci = this._wholeLoci('ligand') || this._wholeLoci();
    if (!loci) return false;
    this.plugin.managers.camera.focusLoci(loci, {
      extraRadius, minRadius, durationMs: reduced() ? 0 : 320,
    });
    return true;
  }

  resetCamera() {
    const loci = this._wholeLoci();
    if (loci) {
      this.plugin.managers.camera.focusLoci(loci, { durationMs: reduced() ? 0 : 320 });
      return;
    }
    this.plugin?.managers?.camera?.reset(undefined, reduced() ? 0 : 320);
  }

  onResidueClick(fn) {
    this._clickHandlers.add(fn);
    return () => this._clickHandlers.delete(fn);
  }

  /* Camera state for locking a twin viewer to this one. */
  cameraSnapshot() {
    return this.plugin?.canvas3d?.camera?.getSnapshot?.() || null;
  }

  applyCamera(snapshot) {
    if (!snapshot || !this.plugin?.canvas3d) return;
    this.plugin.canvas3d.camera.setState(snapshot, 0);
    this.plugin.canvas3d.requestDraw();
  }

  dispose() {
    this._observer?.disconnect();
    this.viewer?.dispose?.();
    this.loaded.clear();
  }
}

/* Lock two viewers so the anti-target comparison moves as one scene. Mol* has no built-in
 * camera link, so this is a subscription in each direction with a re-entry guard. */
export function lockCameras(a, b) {
  let applying = false;
  const link = (from, to) => from.plugin.canvas3d.didDraw.subscribe(() => {
    if (applying) return;
    applying = true;
    try {
      to.applyCamera(from.cameraSnapshot());
    } finally {
      applying = false;
    }
  });
  const subs = [link(a, b), link(b, a)];
  return () => subs.forEach((sub) => sub.unsubscribe?.());
}

function reduced() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
