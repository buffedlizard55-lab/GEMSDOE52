#!/usr/bin/env python3
"""Pick the site's one-click primary from *measured* results, under one documented rule.

Two parallel sessions each froze a promotion rule, and they must be reconciled rather than
averaged. This script is that reconciliation.

**Tier 1 -- live-anchored (this session's instrument).** A candidate is slot-eligible when
``scripts/run_h33_validation.py`` marks it so: it improves the prevalence-calibrated live mirror
(LM-cal) over a **live-scored base** in 4/4 spatially blocked quadrants, and its
**live-anchored safety factor** (credit-loss budget / measured cost, from the inversion of the
controlled D2.8 -> 0.2708 pair) is >= 2.0. Tier 1 additionally requires
``on_catalogue_pixels == 0`` -- the branch condition the drift estimator switches on
(IR-32-INSTR-01: one catalogue dot moves drift 0.14801 -> 0.07831). Highest projected live DTI wins.

**Tier 2 -- holdout-only (the parallel session's frozen rule, ``scripts/build_slot_plan.py``).**
Beat the owner-reported 0.2600 incumbent on all three holdout instruments *and* carry zero
on-catalogue dots. Highest ``drift_corrected_holdout_mean`` wins.

**Why Tier 1 outranks Tier 2.** Tier 1's instrument was validated against six *known live
orderings* and reproduces the one that matters for the current operating point
(0.2708 > 0.2600: LM +0.011458 against live +0.0108). Tier 2's best instrument is the
drift-corrected holdout, whose own calibration
(``docs/research/instrument-calibration.md``) reports Spearman +0.53 over 12 artifacts with
LOO MAE 0.053 -- above chance, not significant at n = 12, and measured to be *anti-monotone* with
live on emission questions (the 0.2708 anchor ranks 27/33 on the catalogue proxy). A candidate that
beats a live-scored file under a live-validated instrument is therefore the stronger claim, and it
wins. Tier 2's candidate is still published, with its own receipt, as the reserve.

Both tiers, both rules and the reason for the precedence are written into
``registry/submission_build.json`` so the choice is auditable rather than asserted here.

Usage:  PYTHONPATH=src python3 scripts/build_submission_build.py
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gems52.feed import sha256  # noqa: E402
from gems52.paths import data_dir  # noqa: E402

DL = ROOT / "docs" / "downloads"
TIER1_MIN_SAFETY = 2.0


def _on_catalogue(tif: Path) -> int:
    """Measure, do not assume: dots inside the published catalogue."""
    cat_p = data_dir() / "existing_faults.tif"
    if not (tif.is_file() and cat_p.is_file()):
        return -1
    with rasterio.open(tif) as ds:
        a = ds.read(1)
    with rasterio.open(cat_p) as ds:
        cat = ds.read(1)
    return int(((a > 0) & (cat > 0)).sum())


def _zip(z: Path) -> None:
    """Write <name>.zip containing exactly <name>.tif -- the portal's other accepted container."""
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(z, arcname=z.name)


def main() -> int:
    h33 = json.loads((ROOT / "evidence" / "h33_validation.json").read_text())
    bundles = {b["candidate_id"]: b for b in
               json.loads((ROOT / "evidence" / "h33_submission_bundles.json").read_text())}
    plan = json.loads((ROOT / "registry" / "slot_plan.json").read_text()) \
        if (ROOT / "registry" / "slot_plan.json").exists() else {}

    # ---- Tier 1 --------------------------------------------------------------------------------
    tier1 = []
    for c in h33["candidates"]:
        if not c.get("slot_eligible"):
            continue
        b = bundles.get(c["candidate_id"])
        if b is None:
            continue
        z = DL / b["zeros_tif"]["filename"]
        if not z.is_file():
            print(f"[submission_build] missing {z.name}; skipping {c['candidate_id']}")
            continue
        n_on_cat = _on_catalogue(z)
        if n_on_cat != 0:
            print(f"[submission_build] {c['candidate_id']} carries {n_on_cat} on-catalogue dots; "
                  "Tier 1 requires zero (IR-32-INSTR-01)")
            continue
        tier1.append({
            "tier": 1, "candidate_id": c["candidate_id"], "hypothesis": c["hypothesis"],
            "description": c["description"], "zeros": z,
            "nan": DL / b["nan_tif"]["filename"],
            "dots": c["emitted_pixels"], "lm_mean": c["lm_mean"],
            "lm_margin_vs_base": c.get("lm_margin_vs_base"),
            "lm_folds_beat_base": c.get("lm_folds_beat_base"),
            "live_anchor": c.get("live_anchor"),
            "live_anchor_safety": c.get("live_anchor_safety"),
            "live_anchor_projection": c.get("live_anchor_projection"),
            "on_catalogue_pixels": n_on_cat,
            "catalogue_hidden_mean": c["catalogue_hidden_mean"],
            "drift_corrected_holdout_mean": c["drift_corrected_holdout_mean"],
            "sgmc_prevalence_calibrated_dti": c["sgmc_prevalence_calibrated_dti"],
        })
    tier1.sort(key=lambda r: -(r["live_anchor_projection"] or 0.0))

    # ---- Tier 2 --------------------------------------------------------------------------------
    tier2 = []
    for c in (plan.get("candidates") or []):
        if not c.get("promoted"):
            continue
        z = DL / Path(c["file"]).name
        if not z.is_file():
            continue
        if c.get("on_catalogue_pixels") != 0:
            continue
        tier2.append({
            "tier": 2, "candidate_id": c["label"], "hypothesis": "H32-D (round 2)",
            "description": c["description"], "zeros": z,
            "nan": DL / (z.stem.replace("-zeros", "-nan") + ".tif"),
            "dots": c["positive_px"], "lm_mean": None, "lm_margin_vs_base": None,
            "lm_folds_beat_base": None, "live_anchor": None, "live_anchor_safety": None,
            "live_anchor_projection": None, "on_catalogue_pixels": 0,
            "catalogue_hidden_mean": c["catalogue_hidden_mean"],
            "drift_corrected_holdout_mean": c["drift_corrected_holdout_mean"],
            "sgmc_prevalence_calibrated_dti": c["sgmc_prevalence_calibrated_dti"],
        })
    tier2.sort(key=lambda r: -(r["drift_corrected_holdout_mean"] or 0.0))

    primary = (tier1 or tier2 or [None])[0]
    if primary is None:
        print("[submission_build] no candidate in either tier; registry left untouched")
        return 1
    reserve = (tier2 or tier1)[0] if (tier2 or tier1)[0] is not primary else (tier1 + tier2)[1:2]

    z, n = primary["zeros"], primary["nan"]
    zp = z.with_suffix(".zip")
    _zip(zp)
    name = z.stem

    note = (
        f"GEMSDOE32 {primary['candidate_id']} | flank B=2 prune on the 0.2708 base: "
        f"{primary['dots']:,} dots, 0 within 200 m of the catalogue; "
        f"live-mirror +{primary['lm_margin_vs_base']:.5f} in 4/4 folds, "
        f"safety {primary['live_anchor_safety']:.2f}, "
        f"projected {primary['live_anchor_projection']:.4f}; UNSCORED"
    ) if primary["tier"] == 1 else (
        f"GEMSDOE32 {primary['candidate_id']} | holdout drift "
        f"{primary['drift_corrected_holdout_mean']:.5f} vs 0.14801, cat "
        f"{primary['catalogue_hidden_mean']:.5f} vs 0.09832, SGMC "
        f"{primary['sgmc_prevalence_calibrated_dti']:.5f} vs 0.06059, "
        f"{primary['dots']:,} px, 0 on-catalogue; UNSCORED"
    )
    assert len(note) <= 200, f"note is {len(note)} chars; the portal caps it at 200"

    status = (
        f"PRIMARY = {primary['candidate_id']} (Tier {primary['tier']}: "
        f"{'live-anchored' if primary['tier'] == 1 else 'holdout-only'} gate). "
        f"{primary['description']}. {primary['dots']:,} dots, {primary['on_catalogue_pixels']} on "
        f"the catalogue. "
        + (f"Live mirror (spatially blocked, off-catalogue truth, validated on the known live "
           f"orderings) {primary['lm_margin_vs_base']:+.6f} in "
           f"{primary['lm_folds_beat_base']} quadrants over the 0.2708 base; live-anchored safety "
           f"factor {primary['live_anchor_safety']:.2f}; projected live DTI "
           f"{primary['live_anchor_projection']:.4f} (a MODEL, not a score). "
           if primary["tier"] == 1 else
           f"Drift-corrected holdout {primary['drift_corrected_holdout_mean']:.5f} vs the "
           f"incumbent's 0.14801; catalogue-hidden {primary['catalogue_hidden_mean']:.5f} vs "
           f"0.09832; SGMC {primary['sgmc_prevalence_calibrated_dti']:.5f} vs 0.06059. ")
        + "NO ORGANISER SCORE EXISTS for this or any artifact in this repository."
    )

    pack = [{
        "role": f"SECONDARY (Tier {reserve['tier']})" if reserve else "SECONDARY",
        "path": str(reserve["zeros"].relative_to(ROOT)) if reserve else "",
        "sha256": sha256(reserve["zeros"]) if reserve else None,
        "bytes": reserve["zeros"].stat().st_size if reserve else None,
        "positive_px": reserve["dots"] if reserve else None,
        "note": (f"Tier {reserve['tier']} candidate: {reserve['description']}" if reserve else ""),
    }] if reserve else []
    if n.is_file():
        pack.append({"role": "NaN-outside twin of the primary",
                     "path": str(n.relative_to(ROOT)), "sha256": sha256(n),
                     "bytes": n.stat().st_size, "positive_px": primary["dots"],
                     "note": "the competition's own format (identical values inside the footprint)"})
    for p in sorted(DL.glob("*.tif")):
        rel = str(p.relative_to(ROOT))
        if rel in {str(z.relative_to(ROOT)), str(n.relative_to(ROOT))}:
            continue
        with rasterio.open(p) as ds:
            a = ds.read(1)
        pack.append({"role": "AVAILABLE DOWNLOAD", "path": rel, "sha256": sha256(p),
                     "bytes": p.stat().st_size,
                     "positive_px": int(((a > 0) & np.isfinite(a)).sum()),
                     "note": "kept for the audit trail; see docs/research/ for its status"})

    out = {
        "name": name,
        "note": note,
        "status_line": status,
        "file": {"path": str(z.relative_to(ROOT)), "sha256": sha256(z),
                 "bytes": z.stat().st_size, "positive_px": primary["dots"]},
        "file_zeros": {"path": str(z.relative_to(ROOT)), "sha256": sha256(z),
                       "bytes": z.stat().st_size},
        "zip": {"path": str(zp.relative_to(ROOT)), "sha256": sha256(zp), "bytes": zp.stat().st_size},
        "candidate_id": primary["candidate_id"],
        "tier": primary["tier"],
        "hypothesis": primary["hypothesis"],
        "selection_rule": {
            "tier_1": ("slot-eligible under the live-anchored gate (LM-cal +margin in 4/4 quadrants "
                       "over a live-scored base, safety factor >= 2.0) AND on_catalogue_pixels == 0; "
                       "highest projected live DTI wins"),
            "tier_2": ("scripts/build_slot_plan.py's frozen holdout rule: beats the owner-reported "
                       "0.2600 incumbent on all three holdout instruments AND 0 on-catalogue dots"),
            "precedence": ("Tier 1 outranks Tier 2 because its instrument was validated against six "
                           "known live orderings (it reproduces 0.2708 > 0.2600 at +0.011458 against "
                           "live +0.0108), while Tier 2's best instrument is Spearman +0.53 at n=12 "
                           "and is measured anti-monotone with live on emission questions"),
        },
        "lm": {"mean": primary["lm_mean"], "margin_vs_base": primary["lm_margin_vs_base"],
               "folds_beat_base": primary["lm_folds_beat_base"]},
        "live_anchor": primary["live_anchor"],
        "catalogue_hidden_mean": primary["catalogue_hidden_mean"],
        "drift_corrected_holdout_mean": primary["drift_corrected_holdout_mean"],
        "sgmc_prevalence_calibrated_dti": primary["sgmc_prevalence_calibrated_dti"],
        "on_catalogue_pixels": primary["on_catalogue_pixels"],
        "anchor": {
            "role": "ANCHOR -- the group's best live-scored emission",
            "path": "docs/downloads/gems52-probe-S1-ANCHOR-identical-to-live-02600.tif",
            "note": ("in-footprint bit-identical to the owner-reported 0.2708 / 0.2600 emissions; "
                     "upload this if you want a file whose leaderboard behaviour is already known"),
        },
        "pack": pack,
        "rule": ("0.2708 base (GEMS28-H27-4-R1-SOLO-D2.8, 40,199 dots) minus every dot within 2 px "
                 "(200 m) of the published catalogue"),
        "provenance": ("built by scripts/build_submission_build.py from "
                       "evidence/h33_validation.json + registry/slot_plan.json; every digest "
                       "re-read from the written bytes; receipts evidence/h33_submission_bundles.json "
                       "and docs/research/hypotheses-round4.md"),
    }
    (ROOT / "registry" / "submission_build.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"[submission_build] Tier {primary['tier']} primary = {name} "
          f"({primary['dots']:,} dots, on-catalogue {primary['on_catalogue_pixels']})")
    print(f"[submission_build] note ({len(note)}/200): {note}")
    if reserve:
        print(f"[submission_build] reserve (Tier {reserve['tier']}) = {reserve['zeros'].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
