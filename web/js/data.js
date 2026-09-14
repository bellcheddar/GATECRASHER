/* Bundle loading and the indexes every panel reads.
 *
 * One paper bundle is fetched once and then only read: the indexes below are built at load
 * time so no panel has to scan measurements.csv on a click. A qualifier always travels with
 * its value, so a bound such as '>10000' can never be sorted or plotted as a number. */

const CACHE = new Map();

export async function loadIndex(base = 'data') {
  /* A plain fetch, so it can reuse the <link rel="preload"> in index.html; a cache mode of
   * its own would not match the preload. nginx already caches /data/ for five minutes. */
  const response = await fetch(`${base}/index.json`);
  if (!response.ok) throw new Error(`index.json: ${response.status}`);
  return response.json();
}

export async function loadPaper(slug, base = 'data') {
  if (CACHE.has(slug)) return CACHE.get(slug);
  const dir = `${base}/papers/${slug}`;

  /* Every file in one wave. This used to be three: the required files, then the optional
   * ones, then the interactions, each waiting for the last to finish. On a throttled phone
   * connection every wave is another half second of latency before the Story prose can
   * paint. The interactions still need the structure list, so they start the moment
   * structures.json lands rather than after everything else. */
  const structuresRequest = getJson(`${dir}/structures.json`);
  const interactionsRequest = structuresRequest.then((list) => Promise.all(list.map((entry) =>
    getJson(`${dir}/interactions/${entry.pdb_id}.json`)
      .then((data) => [entry.pdb_id, data])
      .catch(() => [entry.pdb_id, null]))));

  const [paper, assays, structures, compoundsCsv, measurementsCsv, edits,
    residuesCsv, story, cliffs, superpositions, dynamics, interactionPairs] = await Promise.all([
    getJson(`${dir}/paper.json`),
    getJson(`${dir}/assays.json`),
    structuresRequest,
    getText(`${dir}/compounds.csv`),
    getText(`${dir}/measurements.csv`),
    getJson(`${dir}/edits.json`),
    /* These are optional at this stage of the build: a paper still loads and renders
     * without them, with the panels that need them showing an explicit empty state. */
    getText(`${dir}/residues.csv`).catch(() => ''),
    getJson(`${dir}/story.json`).catch(() => null),
    getJson(`${dir}/cliffs.json`).catch(() => []),
    /* How each other structure sits on the primary one, for the camera-locked twin view. */
    getJson(`${dir}/superpositions.json`).catch(() => ({})),
    /* What the short MD showed, and the trajectory where one earned its place. */
    getJson(`${dir}/dynamics.json`).catch(() => ({})),
    interactionsRequest,
  ]);

  const compounds = parseCsv(compoundsCsv).map(typeCompound);
  const measurements = parseCsv(measurementsCsv).map(typeMeasurement);
  const residues = residuesCsv ? parseCsv(residuesCsv).map(typeResidue) : [];

  const interactions = {};
  for (const [pdbId, data] of interactionPairs) {
    if (data) interactions[pdbId] = data;
  }

  const bundle = {
    slug, dir, paper, assays, structures, compounds, measurements,
    residues, edits, story, cliffs, interactions, superpositions, dynamics,
    index: buildIndexes({ paper, assays, compounds, measurements, residues, edits, structures, interactions }),
  };
  CACHE.set(slug, bundle);
  return bundle;
}

/* --------------------------------------------------------------------- indexes */

function buildIndexes(b) {
  const byCompound = new Map();
  const byAssay = new Map();
  for (const row of b.measurements) {
    if (!byCompound.has(row.compound_id)) byCompound.set(row.compound_id, new Map());
    /* One compound can carry the same assay from two published tables. The first is kept
     * and the duplicate recorded, because silently overwriting would hide a disagreement
     * between tables, which is exactly the kind of thing the app is meant to surface. */
    const perAssay = byCompound.get(row.compound_id);
    if (perAssay.has(row.assay_id)) {
      perAssay.get(row.assay_id).duplicates.push(row);
    } else {
      perAssay.set(row.assay_id, { ...row, duplicates: [] });
    }
    if (!byAssay.has(row.assay_id)) byAssay.set(row.assay_id, []);
    byAssay.get(row.assay_id).push(row);
  }

  const primaryAssay = Object.keys(b.assays).find((id) => b.assays[id].is_primary) || null;
  const antiTargets = Object.entries(b.assays)
    .filter(([, spec]) => spec.anti_target_of)
    .map(([id, spec]) => ({ id, of: spec.anti_target_of }));

  const byCategory = {};
  for (const [id, spec] of Object.entries(b.assays)) {
    (byCategory[spec.category] ||= []).push(id);
  }

  const compoundById = new Map(b.compounds.map((c) => [c.compound_id, c]));

  const residuesByKey = new Map();
  const residuesByMotif = {};
  const residuesByStructure = {};
  for (const row of b.residues) {
    residuesByKey.set(`${row.pdb_id}|${row.chain}:${row.resnum}`, row);
    (residuesByMotif[row.motif] ||= []).push(row);
    (residuesByStructure[row.pdb_id] ||= []).push(row);
  }

  /* Which compounds does an edit citing this residue involve? This is what lets a click on
   * a residue in 3D filter the SAR table and the edit log. */
  const editsByResidue = {};
  const editsByCompound = {};
  for (const edit of b.edits) {
    for (const ref of edit.structural_basis || []) {
      (editsByResidue[ref] ||= []).push(edit.edit_id);
    }
    for (const key of ['from_compound', 'to_compound']) {
      (editsByCompound[edit[key]] ||= []).push(edit.edit_id);
    }
  }

  const contactsByResidue = {};
  for (const [pdbId, data] of Object.entries(b.interactions)) {
    for (const contact of data.interactions || []) {
      const key = `${contact.chain}:${contact.resnum}`;
      (contactsByResidue[`${pdbId}|${key}`] ||= []).push(contact);
    }
  }

  const structureForCompound = new Map();
  for (const entry of b.structures) {
    const id = entry.contains?.ligand_compound_id;
    if (id) structureForCompound.set(id, entry);
  }

  return {
    byCompound, byAssay, byCategory, compoundById, primaryAssay, antiTargets,
    residuesByKey, residuesByMotif, residuesByStructure,
    editsByResidue, editsByCompound, contactsByResidue, structureForCompound,
    editById: new Map(b.edits.map((e) => [e.edit_id, e])),
  };
}

/* ------------------------------------------------------------------ accessors */

export function measurement(bundle, compoundId, assayId) {
  return bundle.index.byCompound.get(compoundId)?.get(assayId) || null;
}

/* Display form. A qualifier is never dropped and a missing value is never drawn as zero. */
export function formatValue(bundle, row, { withUnits = false } = {}) {
  if (!row || row.value === null) return null;
  const spec = bundle.assays[row.assay_id] || {};
  const magnitude = Math.abs(row.value);
  let text;
  if (magnitude !== 0 && (magnitude < 0.01 || magnitude >= 100000)) {
    text = row.value.toExponential(1);
  } else {
    const decimals = magnitude < 1 ? 2 : (magnitude < 10 ? 2 : (magnitude < 100 ? 1 : 0));
    text = Number(row.value.toFixed(decimals)).toString();
  }
  const qualifier = row.qualifier && row.qualifier !== '=' ? row.qualifier : '';
  return `${qualifier}${text}${withUnits && spec.units ? ` ${spec.units}` : ''}`;
}

/* Only an exact measurement can be plotted on a log axis or ranked. A bound is excluded
 * rather than coerced, and the caller is told so it can render the bound some other way. */
export function numericValue(row) {
  if (!row || row.value === null || row.qualifier !== '=') return null;
  return row.value;
}

export function selectivityFold(bundle, compoundId, antiAssayId) {
  const primary = bundle.index.primaryAssay;
  const target = numericValue(measurement(bundle, compoundId, primary));
  const anti = numericValue(measurement(bundle, compoundId, antiAssayId));
  if (!target || !anti) return null;
  return anti / target;
}

export function compoundsWithResidue(bundle, residueKey) {
  const editIds = bundle.index.editsByResidue[residueKey] || [];
  const out = new Set();
  for (const id of editIds) {
    const edit = bundle.index.editById.get(id);
    if (!edit) continue;
    out.add(edit.from_compound);
    out.add(edit.to_compound);
  }
  return [...out];
}

/* ------------------------------------------------------------------- CSV parse */

/* A small correct parser rather than a library: fields may contain commas, quotes and
 * embedded JSON (r_groups), which a split(',') would destroy. */
export function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  let i = 0;
  const source = text.replace(/\r\n?/g, '\n');

  while (i < source.length) {
    const ch = source[i];
    if (quoted) {
      if (ch === '"') {
        if (source[i + 1] === '"') { field += '"'; i += 2; continue; }
        quoted = false; i += 1; continue;
      }
      field += ch; i += 1; continue;
    }
    if (ch === '"') { quoted = true; i += 1; continue; }
    if (ch === ',') { row.push(field); field = ''; i += 1; continue; }
    if (ch === '\n') { row.push(field); rows.push(row); row = []; field = ''; i += 1; continue; }
    field += ch; i += 1;
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  if (!rows.length) return [];

  const header = rows.shift();
  return rows
    .filter((cells) => cells.some((cell) => cell !== ''))
    .map((cells) => Object.fromEntries(header.map((key, idx) => [key, cells[idx] ?? ''])));
}

function typeCompound(row) {
  return {
    ...row,
    r_groups: safeJson(row.r_groups, {}),
    mw: num(row.mw), clogp: num(row.clogp), tpsa: num(row.tpsa), fsp3: num(row.fsp3),
    hbd: int(row.hbd), hba: int(row.hba), rotb: int(row.rotb), hac: int(row.hac),
    mol3d: row.mol3d || null,
    notes: row.notes || null,
  };
}

function typeMeasurement(row) {
  return {
    ...row,
    value: row.value === '' ? null : num(row.value),
    n: row.n === '' ? null : int(row.n),
    source_note: row.source_note || null,
  };
}

function typeResidue(row) {
  return {
    ...row,
    resnum: int(row.resnum),
    klifs_index: row.klifs_index === 'NA' ? null : int(row.klifs_index),
    role_note: row.role_note || null,
  };
}

function num(value) { const n = Number(value); return Number.isFinite(n) ? n : null; }
function int(value) { const n = parseInt(value, 10); return Number.isFinite(n) ? n : null; }

function safeJson(text, fallback) {
  if (!text) return fallback;
  try { return JSON.parse(text); } catch (err) { return fallback; }
}

async function getJson(url) {
  const response = await fetch(url, { cache: 'no-cache' });
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

async function getText(url) {
  const response = await fetch(url, { cache: 'no-cache' });
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.text();
}
