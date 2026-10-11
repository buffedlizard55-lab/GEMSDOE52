#!/usr/bin/env python3
"""Append this round's irregularities to ``registry/irregularities.json`` — idempotent.

Same contract as ``scripts/h95_irregularities.py``: entries are keyed by ``id`` and rewritten in
place if they already exist, so re-running never duplicates and never renumbers an earlier round.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry/irregularities.json"
ROUND = "H104"
DATE = "2026-10-10"

ENTRIES = [
    dict(
        id="IR-H104-001",
        title="`13gems_..._r13-lattice-s5_v2_nan-outside.tif` is a 5 px lattice probe; the literal "
              "'70 % of dots within 3 px' lane rule is uninformative against it",
        status="closed - explained, no code change needed",
        what_it_is="`data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif` carries 206,895 "
                   "positive pixels arranged as a regular lattice: 746 unique rows x 659 unique cols "
                   "at exactly 5 px spacing (measured this session). A 5 px lattice dilated by 3 px "
                   "tiles the plane, so *any* dense emission has a near-3px fraction approaching 1.",
        how_we_know="Row/column spacing was measured directly from the raster "
                    "(np.unique of the positive rows and columns, median gap 5.0 px); the shared "
                    "`gems52.gates.lane_report` classifies it as a `universal_coverage_probes` entry "
                    "with coverage 0.99903 of the eligible footprint.",
        impact_on_claims="The literal lane verdict for a dense candidate is DUPLICATE/STOP for a "
                         "reason that carries no information: 0.9889 of the H104 dots are 'within 3 px' "
                         "of that lattice. The policy variant of the same shared tool excludes the "
                         "probe and is the reading that must be quoted.",
        disposition="No change to the shared tool: it already reports the literal and the policy "
                    "variant side by side and names the probes. The round quotes both and adds this "
                    "entry so a future session does not read the literal line as a uniqueness failure.",
    ),
    dict(
        id="IR-H104-002",
        title="Count-matched control vs mass-matched primary: an apparent +0.071 HOLDOUT-DTI gain "
              "that is entirely a mass artefact",
        status="closed - arms redesigned and the holdout re-run before reporting",
        what_it_is="The first arm set of this round compared a 867-1,324-dot arm against 9,400-dot "
                   "arms. DTI = T/(0.2*S + 0.8*|G|) is denominator-dominated at these budgets, so a "
                   "budget-matched comparison is mandatory; the frozen 'primary beats random_gap' "
                   "claim is satisfied by construction when the primary emits 7-30x more mass than "
                   "its control.",
        how_we_know="Measured on `gems52-pooled-hide-v1` (60,894 withheld positives, 4 folds, 9,400 "
                    "dots/fold/arm): primary `thermal_gap_cotrain` 0.074709 [0.062414, 0.088008] vs "
                    "count-matched `random_gap` 0.003237 [0.002443, 0.004115] -> paired +0.071471 "
                    "[+0.058852, +0.085253]; vs the mass-matched control `random_gap_full` 0.075335 "
                    "[0.066538, 0.084143] -> paired -0.000627 [-0.013423, +0.012889], i.e. "
                    "indistinguishable.",
        impact_on_claims="The frozen claim is satisfied and is nonetheless not evidence: the "
                         "mass-matched comparison shows the composition's credit density is the same "
                         "as random dots at the same budget. Both numbers are reported; the round is "
                         "a negative on the mechanism.",
        disposition="`random_gap_full` was added as a second, mass-matched control and the holdout "
                    "was re-run with 9 arms before anything was published. Recorded so that no future "
                    "round quotes the count-matched delta alone.",
    ),
    dict(
        id="IR-H104-003",
        title="The registered composition reproduces the repository's own H96 dots: 0.8749 of the "
              "H104 dots lie within 3 px of the H96 file, by construction",
        status="open - design constraint for the next round",
        what_it_is="This round registered 'Views/field = H96 spec (reused, not forked)' and placement "
                   "`gems52.nodes.spacing_select` at 3.0 px. `spacing_select` is deterministic and "
                   "greedy, so an emission from the same field at a budget at or below the H96 budget "
                   "is a prefix of the H96 selection: the field-fill part of the shipped composition "
                   "cannot be a new pattern.",
        how_we_know="`gates.lane_report(..., phase='dots')` on the written raster reports policy "
                    "max_near_3px_fraction 0.8749 with max_near_source = "
                    "`submission/gems52-h96-bidir-cotrain-coverstep-25400px-...-zeros.tif` (and the "
                    "two copies of that file under `docs/downloads/`); exact-pixel uniqueness is "
                    "separate and passes (novel fraction 0.3577 over 193 priors, identical to none).",
        impact_on_claims="The H104 artifact may be downloaded and studied but must not be submitted on "
                         "uniqueness grounds as well as on the holdout bar. Any future full-budget "
                         "emission from an already-shipped field must register a placement that "
                         "cannot reproduce the earlier file (quota placement, or a sub-halo budget) "
                         "BEFORE the fit - the same failure mode as IR-H93-004/IR-H95-006.",
        disposition="Recorded; the artifact is labelled research-only on the site and in the README, "
                    "and this becomes the top-ranked constraint for the next round.",
    ),
    dict(
        id="IR-H104-004",
        title="A stale receipt: `evidence/h104_holdout.json` was first produced by a process launched "
              "before the arm patch landed, and the runner hash is not in the receipt",
        status="closed - re-run with the patched runner; self-hash added to the closure",
        what_it_is="The 8-arm `holdout` job was launched at 00:13:02Z and the arm redesign (9 arms, "
                   "mass-matched control) was written to `scripts/run_h104_thermal_gap.py` at 00:31Z. "
                   "The job finished at 00:15:53Z and wrote the only holdout receipt, so the receipt "
                   "on disk described arms the file no longer contained.",
        how_we_know="`json.load('evidence/h104_holdout.json')['arms']` returned the 8-arm list "
                    "(`... 'random_gap', 'random_uniform', ...` without `random_gap_full`) while "
                    "`grep -n random_gap_full scripts/run_h104_thermal_gap.py` matched; the re-run "
                    "receipt now lists 9 arms.",
        impact_on_claims="Had it gone unnoticed, the round would have published a primary that was "
                         "not the registered composition and a count-matched comparison as if it were "
                         "the claim (see IR-H104-002). This was caught by the second pass (bug/edge "
                         "review) of the required 3-pass protocol.",
        disposition="Holdout re-run with the patched runner; the runner's own SHA-256 is recorded by "
                    "`scripts/h104_supplemental_closure.py` so that a receipt can be matched to the "
                    "code that produced it.",
    ),
    dict(
        id="IR-H104-005",
        title="Holdout/off-catalogue primary arms used `min_px=1.0` while the registered placement "
              "minimum spacing is 3.0 px",
        status="closed - corrected before the reported run",
        what_it_is="Two code paths built the primary composition with `nodes.spacing_select(..., "
                   "min_px=1.0)` (`stage_holdout`'s field fill and `stage_offcat`'s tie-break fill) "
                   "although `registry/h104_preregistration.json` registers "
                   "`placement.min_spacing_px = 3.0` and the write path uses 3.0.",
        how_we_know="`grep -n 'min_px=1.0' scripts/run_h104_thermal_gap.py` matched two lines; after "
                    "the fix it matches none, and the re-run receipt's fold rows show "
                    "`placed = 9400` for the primary at 3.0 px spacing.",
        impact_on_claims="The measured primary was not the registered composition while both arms "
                         "existed; a fabricated difference between 'the composition' and 'the shipped "
                         "file' would have been possible. Corrected before the reported run.",
        disposition="Fixed in the round runner (both call sites now use `SPACING_PX`), recorded here.",
    ),
    dict(
        id="IR-H104-006",
        title= "The 70 % dot-proximity lane rule is not coverage-normalised: the full 526-blob sibling census fires on a prior whose own 3 px halo already covers 81.3 % of the footprint",
        status= "closed - shared tool extended additively (lift), verdicts unchanged",
        what_it_is= "`gates.lane_report` compares the candidate's near-3px fraction to a fixed 0.70. That threshold is only meaningful if the prior localises something. Two priors in the registry do not: `data/scored/13gems_..._r13-lattice-s5_v2_nan-outside.tif` (5 px lattice, own coverage 0.9985) and the censused blob `buffedlizard55-lab/13GEMSDOE docs/downloads/archive/13gems-composite-20260929T183221Z_allfinite.tif` (507,776 positive px, own 3 px coverage 0.8133).",
        how_we_know= "Measured this session on the written H104 raster: near-fraction 0.9863 vs coverage 0.9985 (lift 0.988) for the lattice and 0.7783 vs 0.8133 (lift 0.957) for the 13gems composite - i.e. the H104 dots are **no closer** to either raster than uniformly scattered dots would be, while the raw fractions are 0.99 and 0.78 and both exceed the 0.70 limit. The one genuinely concentrated prior is this repository's own H96 file: near-fraction 0.8632 against its coverage 0.0756, lift **11.42** (IR-H104-003).",
        impact_on_claims= "Without normalisation the lane verdict for H104 is DUPLICATE/STOP for two artefactual reasons and one real one; the real one (our own H96 file) is enough to block submission, so no verdict changed. The artifact's exact-pixel novelty also collapses against the full census: 0.3577 against the 193 rasters on disk, but 0.0000 against the union of the 526 censused sibling blobs, because that union includes dense lattice probes. Both readings are recorded.",
        disposition= "`gems52.gates.lane_report` now also reports `near_3px_lift` (near-fraction / the prior's own coverage), `max_near_3px_lift`, `max_lift_source`, `lift_offenders` (lift > 2.0) and a `coverage_normalization` note. The literal/policy verdicts are byte-for-byte unchanged, so every earlier round's recorded verdict still reproduces; `scripts/h104_supplemental_closure.py` stores the normalised reading in `evidence/h104_gates.json`.",
        round= "H104",
        date= "2026-10-10"
    ),
]


def main() -> int:
    data = json.loads(REG.read_text())
    entries = data["entries"]
    ids = {e["id"] for e in entries}
    added, replaced = [], []
    for new in ENTRIES:
        new = dict(new, round=ROUND, date=DATE)
        if new["id"] in ids:
            for i, e in enumerate(entries):
                if e["id"] == new["id"]:
                    entries[i] = new
                    replaced.append(new["id"])
                    break
        else:
            entries.append(new)
            added.append(new["id"])
    data["generated"] = (data["generated"].split(" ; ")[0] +
                         " ; H104 append (IR-H104-001..%03d)" % len(ENTRIES))
    REG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(dict(added=added, replaced=replaced, total=len(entries)), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
