/* RDKit.js depictions, core-aligned in the browser.
 *
 * The pipeline already writes a core-aligned SVG per compound, which is what the app shows
 * by default: it is identical to what the R-group decomposition used, and it costs no WASM.
 * RDKit.js is for what a precomputed file cannot do: highlighting the atoms that changed in
 * an edit, and drawing a substituent fragment on demand.
 *
 * If the WASM does not load, every function here falls back to the precomputed SVG, so the
 * app degrades to static depictions rather than to blank panels. */

let rdkitPromise = null;
let rdkit = null;

export function initRdkit() {
  if (rdkitPromise) return rdkitPromise;
  if (typeof window.initRDKitModule !== 'function') {
    rdkitPromise = Promise.resolve(null);
    return rdkitPromise;
  }
  rdkitPromise = window.initRDKitModule({
    /* RDKit_minimal.js resolves the wasm relative to the document, so point it at the
     * vendor directory explicitly rather than hoping the page sits at the root. */
    locateFile: (file) => `js/vendor/${file}`,
  }).then((module) => {
    rdkit = module;
    return module;
  }).catch((err) => {
    console.warn('[rdkit] WASM did not load, falling back to precomputed depictions', err);
    rdkit = null;
    return null;
  });
  return rdkitPromise;
}

export function ready() {
  return rdkit !== null;
}

const DRAW_OPTIONS = {
  width: 320,
  height: 240,
  bondLineWidth: 2,
  clearBackground: false,
  addStereoAnnotation: true,
};

/* Carbon and bond black becomes currentColor so one depiction serves both themes, exactly
 * as gc chem does for the precomputed files. */
function themeable(svgText) {
  return svgText.replace(/#000000|#000\b/gi, 'currentColor');
}

export function depict(smiles, {
  template = null, highlightAtoms = null, highlightColour = [1.0, 0.82, 0.4],
  width = DRAW_OPTIONS.width, height = DRAW_OPTIONS.height,
} = {}) {
  if (!rdkit) return null;
  let mol = null;
  let templateMol = null;
  try {
    mol = rdkit.get_mol(smiles);
    if (!mol || !mol.is_valid()) return null;

    if (template) {
      templateMol = rdkit.get_qmol(template);
      if (templateMol && templateMol.is_valid()) {
        /* Aligns this molecule's coordinates onto the shared core, so every depiction in a
         * series sits the same way up. */
        mol.generate_aligned_coords(templateMol, JSON.stringify({ acceptFailure: true }));
      }
    }

    const details = { ...DRAW_OPTIONS, width, height };
    if (highlightAtoms && highlightAtoms.length) {
      details.atoms = highlightAtoms;
      details.highlightColour = highlightColour;
    }
    return themeable(mol.get_svg_with_highlights(JSON.stringify(details)));
  } catch (err) {
    console.warn('[rdkit] depiction failed', smiles, err);
    return null;
  } finally {
    mol?.delete?.();
    templateMol?.delete?.();
  }
}

/* The atoms that differ between two compounds, for the edit-log before and after.
 * Returns { from: number[], to: number[] } as atom indices, or null if MCS is unavailable. */
export function changedAtoms(fromSmiles, toSmiles) {
  if (!rdkit) return null;
  let a = null;
  let b = null;
  try {
    a = rdkit.get_mol(fromSmiles);
    b = rdkit.get_mol(toSmiles);
    if (!a?.is_valid() || !b?.is_valid()) return null;

    /* MinimalLib exposes MCS through get_mcs_as_smarts on a MolList. */
    if (typeof rdkit.get_mcs_as_smarts !== 'function' || typeof rdkit.MolList !== 'function') {
      return null;
    }
    const list = new rdkit.MolList();
    list.append(a);
    list.append(b);
    const smarts = rdkit.get_mcs_as_smarts(list, JSON.stringify({
      RingMatchesRingOnly: true, CompleteRingsOnly: true, Timeout: 5,
    }));
    list.delete();
    if (!smarts) return null;

    const core = rdkit.get_qmol(smarts);
    const shared = (mol) => {
      const matches = JSON.parse(mol.get_substruct_match(core) || '{}');
      return new Set(matches.atoms || []);
    };
    const inA = shared(a);
    const inB = shared(b);
    core.delete();

    const all = (mol, keep) => {
      const count = JSON.parse(mol.get_json()).molecules?.[0]?.atoms?.length
        ?? mol.get_num_atoms?.() ?? 0;
      const out = [];
      for (let i = 0; i < count; i += 1) if (!keep.has(i)) out.push(i);
      return out;
    };
    return { from: all(a, inA), to: all(b, inB) };
  } catch (err) {
    console.warn('[rdkit] MCS failed', err);
    return null;
  } finally {
    a?.delete?.();
    b?.delete?.();
  }
}

/* A substituent drawn on its own, for R-group grid axis labels. The fragment SMILES in
 * compounds.csv describe the group as it appears in the paper's table. */
export function depictFragment(smiles, { width = 110, height = 70 } = {}) {
  return depict(smiles, { width, height });
}

/* Fetch a precomputed depiction. This is the default path and the fallback path. */
const svgCache = new Map();

export async function precomputed(dir, relativePath) {
  const url = `${dir}/${relativePath}`;
  if (svgCache.has(url)) return svgCache.get(url);
  const promise = fetch(url)
    .then((response) => (response.ok ? response.text() : null))
    .catch(() => null);
  svgCache.set(url, promise);
  return promise;
}

/* What a panel actually calls: the precomputed drawing unless atoms must be highlighted,
 * in which case RDKit.js redraws it aligned on the same core. */
export async function depictionFor(bundle, compound, { highlightAtoms = null, template = null } = {}) {
  if (highlightAtoms && highlightAtoms.length && ready()) {
    const svgText = depict(compound.smiles, { highlightAtoms, template });
    if (svgText) return svgText;
  }
  const svgText = await precomputed(bundle.dir, compound.depiction);
  return svgText || '';
}
