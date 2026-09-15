"""RDKit work: descriptors, the series scaffold, core-aligned depictions and activity cliffs.

Nothing here invents chemistry. The R-group assignment is hand-curated in compounds.tsv;
this module's job is to verify it, compute properties from it, and draw it consistently.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, Crippen, Descriptors, rdFMCS, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

from . import paths

RDLogger.DisableLog("rdApp.warning")

# Depictions are rendered once and shown on both themes, so carbon and bond black is
# rewritten to currentColor and the CSS decides. Heteroatom colours stay as drawn.
_BLACK = re.compile(r"(#000000|#000\b)", re.IGNORECASE)


@dataclass
class Compound:
    compound_id: str
    label: str
    series: str
    role: str
    smiles: str
    r_groups: dict
    source_table: str
    notes: str = ""
    mol: Chem.Mol | None = None
    props: dict = field(default_factory=dict)


def read_compounds(slug: str) -> list[Compound]:
    path = paths.raw_dir(slug) / "compounds.tsv"
    out: list[Compound] = []
    with path.open() as fh:
        for row in csv.DictReader(_strip_comments(fh), delimiter="\t"):
            mol = Chem.MolFromSmiles(row["smiles"])
            if mol is None:
                raise SystemExit(f"{path}: compound {row['compound_id']} has unparseable SMILES")
            out.append(
                Compound(
                    compound_id=row["compound_id"].strip(),
                    label=row["label"].strip(),
                    series=row["series"].strip(),
                    role=row["role"].strip(),
                    smiles=row["smiles"].strip(),
                    r_groups=json.loads(row.get("r_groups") or "{}"),
                    source_table=row["source_table"].strip(),
                    notes=(row.get("notes") or "").strip(),
                    mol=mol,
                )
            )
    if not out:
        raise SystemExit(f"{path}: no compounds")
    return out


def _strip_comments(fh):
    for line in fh:
        if not line.startswith("#"):
            yield line


def descriptors(mol: Chem.Mol) -> dict:
    return {
        "inchikey": Chem.MolToInchiKey(mol),
        "mw": round(Descriptors.MolWt(mol), 2),
        "clogp": round(Crippen.MolLogP(mol), 2),
        "tpsa": round(rdMolDescriptors.CalcTPSA(mol), 1),
        "hbd": rdMolDescriptors.CalcNumHBD(mol),
        "hba": rdMolDescriptors.CalcNumHBA(mol),
        "rotb": rdMolDescriptors.CalcNumRotatableBonds(mol),
        "hac": mol.GetNumHeavyAtoms(),
        "fsp3": round(rdMolDescriptors.CalcFractionCSP3(mol), 3),
    }


# Common-substructure budgets. Deliberately generous, because the failure they exist to
# prevent is not slowness: it is a search that runs out of time, reports a smaller answer,
# and so makes the published data a function of how busy the machine happened to be.
#
# 300 s is set from measurement rather than taste. The slowest pair in these four campaigns
# is KRAS 3 against 20, two tricyclics of 39 and 49 heavy atoms from different series, which
# converges at 53.6 s on an idle machine. Its true common core is 21 atoms, below the 23.4
# this pair needs, so the honest answer is that they are not a matched pair: the old 5 s code
# reached that answer by running out of time, which was right by accident. At 30 s the search
# could not prove it either way and the build stopped, which is the correct behaviour and the
# reason the budget moved rather than the guard.
#
# rdRascalMCES was measured as an alternative and rejected. It returns 33 atoms for that pair
# in under 10 ms, perfectly stable across repeats, but 33 clears the threshold that the true
# ring-constrained core does not. It does not honour ringMatchesRingOnly or completeRingsOnly,
# so adopting it would quietly redefine what counts as a matched pair. That is a decision
# about the chemistry, not about performance, and it is not one to make for a faster build.
_PAIR_MCS_TIMEOUT_S = 300
_CAMPAIGN_MCS_TIMEOUT_S = 120

# A short first look, before committing the full budget. The hopeless pairs declare themselves
# at once: KRAS 5 against 8 holds 8 atoms of a needed 29.4 at 30 s, at 300 s and at 1800 s
# alike, so the extra 270 s buys nothing but a slower build. A pair is only worth the full
# budget if its partial core is already at least half of what it needs, which keeps KRAS 3
# against 20 (21 of 23.4 at 30 s, converging at 53.6 s) on the expensive path where it belongs.
_PROBE_MCS_TIMEOUT_S = 30
_PROBE_PROMISING = 0.5


class MCSTimeout(RuntimeError):
    """A search that could not answer, which is a different thing from one that answered no."""


# Pairs the pairwise gate could not resolve inside its budget. A cliff table that quietly
# omitted them would be the original defect again, so they are collected rather than dropped
# and reported by the build: excluded, and auditable, rather than excluded and invisible.
_unresolved_pairs: list[dict] = []


def unresolved_pairs() -> list[dict]:
    """What the last call to cliffs() could not decide. Empty is the expected state."""
    return list(_unresolved_pairs)


def scaffold(
    compounds: list[Compound], timeout: int = _CAMPAIGN_MCS_TIMEOUT_S
) -> tuple[Chem.Mol | None, str, bool]:
    """The maximum common substructure across the campaign, used as the depiction template.

    Ring matching is constrained so the MCS cannot cut a ring in half, which would make
    the aligned depictions flip between compounds for no chemical reason.

    Returns the core, its SMARTS, and whether the search converged. A timed-out search is
    not an empty result: RDKit hands back the best core it has found, which is a lower
    bound on the true MCS. This function used to discard that, turning "I ran out of time"
    into "these molecules share nothing", so callers were given a load-dependent answer
    with no way to tell. They now get the partial core and the flag, and decide themselves.
    """
    # Reference compounds are other people's drugs, shown for comparison: including them
    # collapses the MCS to nothing (two atoms, for the FGFR set) and leaves every depiction
    # in the campaign unaligned. The template comes from the campaign's own compounds.
    campaign = [c for c in compounds if c.role != "reference"]
    mols = [c.mol for c in (campaign or compounds) if c.mol is not None]
    if len(mols) < 2:
        return None, "", True
    res = rdFMCS.FindMCS(
        mols,
        timeout=timeout,
        ringMatchesRingOnly=True,
        completeRingsOnly=True,
        matchValences=True,
    )
    if not res or not res.smartsString:
        return None, "", not (res and res.canceled)
    core = Chem.MolFromSmarts(res.smartsString)
    if core is not None:
        AllChem.Compute2DCoords(core)
    return core, res.smartsString, not res.canceled


def check_r_groups(compounds: list[Compound]) -> list[str]:
    """Every curated R-group fragment must really be present in its parent molecule.

    This is the gate that catches a transcription slip in the R-group table: a substituent
    recorded against the wrong compound almost always fails to match.
    """
    problems: list[str] = []
    for c in compounds:
        for position, spec in (c.r_groups or {}).items():
            frag_smiles = spec.get("smiles") if isinstance(spec, dict) else None
            if not frag_smiles:
                problems.append(f"compound {c.compound_id}: {position} has no SMILES")
                continue
            frag = Chem.MolFromSmiles(frag_smiles, sanitize=False)
            if frag is None:
                problems.append(f"compound {c.compound_id}: {position} fragment does not parse")
                continue
            Chem.SanitizeMol(frag, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES, catchErrors=True)
            if not c.mol.HasSubstructMatch(frag, useChirality=False):
                problems.append(
                    f"compound {c.compound_id}: {position} fragment {frag_smiles!r} "
                    f"({spec.get('label')}) is not a substructure of the parent"
                )
    return problems


def depict(mol: Chem.Mol, core: Chem.Mol | None, out: Path, size=(320, 240),
           highlight: list[int] | None = None) -> None:
    """Write one core-aligned SVG. Falls back to free coordinates if alignment fails."""
    target = Chem.Mol(mol)
    AllChem.Compute2DCoords(target)
    if core is not None:
        try:
            rdMolDraw2D.PrepareAndDrawMolecule(rdMolDraw2D.MolDraw2DSVG(1, 1), target)  # sanity
        except Exception:
            pass
        try:
            AllChem.GenerateDepictionMatching2DStructure(target, core, acceptFailure=True)
        except Exception:
            AllChem.Compute2DCoords(target)

    drawer = rdMolDraw2D.MolDraw2DSVG(*size)
    opts = drawer.drawOptions()
    opts.clearBackground = False          # the sheet colour shows through
    opts.bondLineWidth = 2
    opts.padding = 0.08
    opts.additionalAtomLabelPadding = 0.04
    rdMolDraw2D.PrepareAndDrawMolecule(
        drawer, target,
        highlightAtoms=highlight or [],
    )
    drawer.FinishDrawing()
    svg = _BLACK.sub("currentColor", drawer.GetDrawingText())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)


def changed_atoms(from_mol: Chem.Mol, to_mol: Chem.Mol) -> tuple[list[int], list[int]]:
    """Atoms that differ between a matched pair, for the edit-log before and after highlight.

    Unlike the pairwise gate above, a partial core is not safe here. Every atom outside the
    core counts as changed, so a core cut short by the clock overstates the edit and deflates
    fold_per_atom, which is the key the whole cliff table is sorted by. A cancelled search is
    therefore an error rather than a smaller answer.
    """
    res = rdFMCS.FindMCS([from_mol, to_mol], timeout=_PAIR_MCS_TIMEOUT_S,
                         ringMatchesRingOnly=True, completeRingsOnly=True)
    if res is not None and res.canceled:
        # Returning a truncated core here would be worse than returning nothing: every atom
        # outside it counts as changed, so the edit is overstated and fold_per_atom, the key
        # the whole table is sorted by, is wrong. None says "cannot answer", and the caller
        # drops the pair and records it rather than publishing a corrupted ranking.
        return None, None
    if not res or not res.smartsString:
        return [], []
    common = Chem.MolFromSmarts(res.smartsString)
    if common is None:
        return [], []
    a = set(from_mol.GetSubstructMatch(common))
    b = set(to_mol.GetSubstructMatch(common))
    return (
        [i for i in range(from_mol.GetNumAtoms()) if i not in a],
        [i for i in range(to_mol.GetNumAtoms()) if i not in b],
    )


def cliffs(compounds: list[Compound], values: dict[str, float], min_fold: float = 3.0) -> list[dict]:
    """Matched pairs ranked by fold change per heavy atom changed.

    `values` holds the primary potency per compound, already unqualified: a bounded value
    such as '>10000' has no place in a fold ratio and is excluded by the caller.
    """
    _unresolved_pairs.clear()
    by_id = {c.compound_id: c for c in compounds}
    out: list[dict] = []
    ids = [c.compound_id for c in compounds if c.compound_id in values]
    for i, a_id in enumerate(ids):
        for b_id in ids[i + 1:]:
            a, b = by_id[a_id], by_id[b_id]
            # Potency first, scaffold second. Both are filters on the same path, so the order
            # cannot change which pairs come out, but it decides how much work is done to
            # reject one. A pair whose potencies are within min_fold is not a cliff whatever
            # its scaffold, and asking a maximum common substructure search about it is work
            # spent on a question that no longer has consequences: KRAS 5 against 8 spent 30
            # minutes failing to answer, for a pair that the next two lines may discard.
            va, vb = values[a_id], values[b_id]
            if va <= 0 or vb <= 0:
                continue
            fold = max(va, vb) / min(va, vb)
            if fold < min_fold:
                continue
            if a.series != b.series and not _shares_scaffold(a, b):
                continue
            changed_a, changed_b = changed_atoms(a.mol, b.mol)
            if changed_a is None:
                # The pair is a matched pair, but its edit cannot be computed, so it cannot
                # be ranked honestly against the others. Dropped and recorded, not guessed.
                # Same shape as the scaffold exclusions: a record that changes keys
                # depending on which branch produced it breaks every consumer that
                # reads it, which is exactly what happened to the build reporter.
                _unresolved_pairs.append({
                    "compounds": [a_id, b_id],
                    "heavy_atoms": [a.mol.GetNumHeavyAtoms(), b.mol.GetNumHeavyAtoms()],
                    "stage": "edit log",
                    "partial_core": None,
                    "needed": None,
                    "budget_s": _PAIR_MCS_TIMEOUT_S,
                })
                continue
            n_changed = max(len(changed_a) + len(changed_b), 1)
            out.append({
                "from_compound": a_id if va > vb else b_id,   # from the weaker compound
                "to_compound": b_id if va > vb else a_id,
                "fold": round(fold, 1),
                "atoms_changed": n_changed,
                "fold_per_atom": round(fold / n_changed, 2),
            })
    out.sort(key=lambda r: r["fold_per_atom"], reverse=True)
    return out


def _shares_scaffold(a: Compound, b: Compound) -> bool:
    """Whether two compounds share enough of a core to be treated as a matched pair.

    Measured on the JAK1 14/20 pair, the search reaches its final 28-atom core in under a
    second and then spends three more proving that core is maximal. At the old 5 s budget
    the same pair answered False, False, True, True, True across five runs on an idle
    machine, and the 392-fold cliff it supports appeared or vanished from the published
    file to match. The core is 28 of 34 heavy atoms, a ratio of 0.82 against a threshold
    of 0.60, so every False was an artefact of the clock.

    A cancelled search is still usable here, because a partial core is a lower bound: if it
    already clears the threshold, more time could only have grown it. That makes the test
    monotone, so more compute can only ever turn False into True.

    Below the threshold the answer is unknown rather than no, and the search is run in two
    stages so that the unknowns are cheap. A 30 s probe settles most pairs outright; only a
    pair whose partial core already reaches half the threshold earns the full budget. Anything
    still unresolved after that is recorded and treated as not a matched pair, which is a
    judgement rather than a measurement and is kept in the record as one.
    """
    floor = 0.6 * min(a.mol.GetNumHeavyAtoms(), b.mol.GetNumHeavyAtoms())

    # Stage one, a 30 s look. A cancelled core is a lower bound, so one that already clears
    # the floor settles the question outright and never needs the full budget.
    spent = _PROBE_MCS_TIMEOUT_S
    core, _, converged = scaffold([a, b], timeout=_PROBE_MCS_TIMEOUT_S)
    found = core.GetNumHeavyAtoms() if core is not None else 0
    if found >= floor:
        return True
    if converged:
        return False

    # Stage two, only for pairs that are close enough to be worth it.
    if found >= _PROBE_PROMISING * floor:
        spent = _PAIR_MCS_TIMEOUT_S
        core, _, converged = scaffold([a, b], timeout=_PAIR_MCS_TIMEOUT_S)
        found = core.GetNumHeavyAtoms() if core is not None else 0
        if found >= floor:
            return True
        if converged:
            return False
    # Not every question has a computable answer. For the largest KRAS tricyclics the
    # ring-constrained search finds 8 atoms of a needed 30 and then stops improving: measured
    # on compounds 5 and 8, the best core was identical at 300 s and at 1800 s, so six times
    # the compute bought nothing. Reaching the threshold would need it to quadruple.
    #
    # Such a pair is recorded as not a matched pair, and recorded LOUDLY. The judgement is
    # that a core this far short is not about to clear the bar, not that the search succeeded:
    # the distinction is kept in the record instead of being smoothed away, because a cliff
    # table that silently omitted these would be the defect this whole guard exists to prevent.
    _unresolved_pairs.append({
        "compounds": [a.compound_id, b.compound_id],
        "heavy_atoms": [a.mol.GetNumHeavyAtoms(), b.mol.GetNumHeavyAtoms()],
        "stage": "scaffold",
        "partial_core": found,
        "needed": round(floor, 1),
        # The budget actually spent, not the largest one available: a pair dropped at the
        # probe never saw the full 300 s, and recording that it did would overstate the
        # effort made before giving up, in the one record that exists to be audited.
        "budget_s": spent,
    })
    return False


def build(slug: str) -> dict:
    """gc chem: descriptors, scaffold, depictions. Writes build/<slug>/compounds.json."""
    slug = paths.check_slug(slug)
    compounds = read_compounds(slug)
    problems = check_r_groups(compounds)

    core, smarts, converged = scaffold(compounds)
    if not converged:
        raise MCSTimeout(
            f"the campaign scaffold for {slug} did not converge in {_CAMPAIGN_MCS_TIMEOUT_S} s. "
            f"It is the template every depiction is aligned to, so a partial one would make "
            f"all of this campaign's drawings depend on machine load."
        )
    dep_dir = paths.build_dir(slug) / "depictions"
    rows = []
    for c in compounds:
        c.props = descriptors(c.mol)
        rel = f"depictions/{c.compound_id}.svg"
        depict(c.mol, core, dep_dir / f"{c.compound_id}.svg")
        rows.append({
            "compound_id": c.compound_id,
            "label": c.label,
            "series": c.series,
            "role": c.role,
            "smiles": c.smiles,
            "r_groups": c.r_groups,
            "depiction": rel,
            "mol3d": None,
            "source_table": c.source_table,
            "notes": c.notes or None,
            **c.props,
        })

    keys = [r["inchikey"] for r in rows]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        problems.append(f"duplicate InChIKeys, so two rows are the same molecule: {sorted(dupes)}")

    out = paths.build_dir(slug) / "compounds.json"
    out.write_text(json.dumps(rows, indent=1))
    (paths.build_dir(slug) / "scaffold.json").write_text(
        json.dumps({"mcs_smarts": smarts, "n_atoms": core.GetNumHeavyAtoms() if core else 0}, indent=1)
    )
    return {"compounds": len(rows), "scaffold_atoms": core.GetNumHeavyAtoms() if core else 0,
            "problems": problems, "depictions": len(rows)}
