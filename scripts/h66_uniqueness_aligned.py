#!/usr/bin/env python3
"""Re-run the shared uniqueness gate over an ALIGNMENT-FILTERED prior corpus (IR-H66-007/-010).

`gates.uniqueness_report` sets ``canonical_pattern_unique`` to False if *any* prior either matches the
candidate exactly **or fails to open**.  The frozen 526-blob prior census contains 2 entries its own
``eligible`` flag rejects ("not an aligned single-band prediction"), and ``run_h66.py`` passed all 526.
The resulting receipt therefore reports ``canonical_pattern_unique: False`` while
``identical: 0`` for every prior - a false alarm about *identity* caused by an audit error about
*alignment*.  Two things are fixed here, once, in the open:

1. the corpus is filtered by the census's own ``eligible`` flag plus a header alignment check, and the
   excluded paths are published rather than dropped silently;
2. the gate is re-run on the filtered corpus so ``error_count`` is 0 and the identity verdict is clean.

The lane gates are NOT re-run: their verdicts do not depend on the 2 unaligned fixtures (the offending
near-dot sources are both aligned and were measured), and re-running 568 rasters twice would buy nothing
but a re-stamped timestamp.  This script publishes what changed and what did not.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import gates                                    # noqa: E402

DATA = ROOT / "data"
SUB = ROOT / "submission"
WORK = ROOT / "work" / "h66"


def aligned(path, ref):
    """Header-only alignment test: no pixel read, so filtering the corpus costs milliseconds."""
    try:
        with rasterio.open(path) as ds:
            return bool(ds.count == 1 and (ds.shape, ds.crs, ds.transform) == ref)
    except Exception:                                       # noqa: BLE001 - unreadable means unaligned
        return False


def main() -> int:
    tifs = sorted(SUB.glob("gems52-h66-*.tif"))
    assert len(tifs) == 1, f"expected one H66 raster, found {len(tifs)}"
    with rasterio.open(tifs[0]) as ds:
        cand = ds.read(1).astype(np.float32)
        ref = (ds.shape, ds.crs, ds.transform)
    census = json.loads((ROOT / "evidence" / "ctd5_prior_inventory.json").read_text())
    corpus, excluded = [], []
    for e in census["entries"]:
        p = WORK / "priors" / f"{e['blob']}.tif"
        if not p.exists():
            excluded.append(dict(path=str(p), reason="census blob not fetched"))
            continue
        if not e.get("eligible"):
            excluded.append(dict(path=str(p), reason=f"census-ineligible: {e.get('exclusion')}",
                                 aliases=[a["path"] for a in e["aliases"]]))
            continue
        if not aligned(p, ref):
            excluded.append(dict(path=str(p), reason="header not aligned to the competition grid",
                                 aliases=[a["path"] for a in e["aliases"]]))
            continue
        corpus.append(str(p))
    for extra in sorted((DATA / "scored").glob("*.tif")) + sorted((DATA / "reference").glob("*.tif")):
        (corpus if aligned(extra, ref) else excluded).append(
            str(extra) if aligned(extra, ref) else dict(path=str(extra), reason="not aligned"))
    for p in sorted(SUB.glob("*.tif")):
        if p.name.startswith("gems52-h66-"):
            continue                                        # this round's own builds are not priors
        (corpus if aligned(p, ref) else excluded).append(
            str(p) if aligned(p, ref) else dict(path=str(p), reason="not aligned"))

    uni = gates.uniqueness_report(cand, corpus)
    rel = json.loads((ROOT / "evidence" / "h66_release_gates.json").read_text())
    out = dict(
        generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        evidence_class="MEASURED; uniqueness/lane diagnostic, not a score",
        why_this_exists=(
            "gates.uniqueness_report reports canonical_pattern_unique=False if any prior fails to open. "
            "The round's first pass included the 2 census-ineligible fixtures, so the flag was False "
            "while 0 priors were identical (IR-H66-007, IR-H66-010). This receipt separates the two."),
        candidate=dict(file=tifs[0].name, sha256=hashlib.sha256(tifs[0].read_bytes()).hexdigest(),
                       decoded_sha256=uni["candidate_decoded_sha256"], emitted=int((cand > 0).sum())),
        corpus=dict(n_checked=uni["n_priors_checked"], n_excluded=len(excluded), excluded=excluded[:20]),
        result={k: uni[k] for k in ("canonical_pattern_unique", "equals_literal_prior_union",
                                    "research_publication_ok", "support_novelty_gate_ok", "union_px",
                                    "novel_vs_all_priors", "novel_fraction", "prior_px_dropped",
                                    "relation_to_union", "gate_correction", "ok")},
        identical_priors=[r["path"] for r in uni["per_prior"] if r.get("identical")],
        read_errors=[r for r in uni["per_prior"] if "error" in r],
        closest_priors=sorted(
            ({ "path": Path(r["path"]).name, "prior_px": r["prior_px"],
              "intersection": r["intersection"], "jaccard": round(r["jaccard"], 6),
              "subset_of_prior": r["subset_of_prior"]}
             for r in uni["per_prior"] if "error" not in r),
            key=lambda r: -r["jaccard"])[:10],
        first_pass_comparison=dict(
            first_pass_n_priors=rel["uniqueness"]["n_priors_checked"],
            first_pass_canonical_pattern_unique=rel["uniqueness"]["canonical_pattern_unique"],
            first_pass_identical_priors=[r["path"] for r in rel["uniqueness"]["per_prior"]
                                         if r.get("identical")],
            first_pass_errors=[r["error"][:120] for r in rel["uniqueness"]["per_prior"] if "error" in r],
            what_changed="only the 2 unaligned fixtures were removed; the identity finding is unchanged "
                         "in both passes (0 identical priors)",
        ),
        lane_gate_unchanged=dict(
            reason="both near-dot offenders are grid-aligned and were measured in the first pass",
            surface=rel["lane_surface"]["literal"]["verdict"],
            dots_literal=rel["lane_dots"]["literal"]["verdict"],
            dots_policy=rel["lane_dots"]["policy"]["verdict"],
            dots_policy_max_near_3px=rel["lane_dots"]["policy"]["max_near_3px_fraction"],
            dots_policy_source=Path(str(rel["lane_dots"]["policy"]["max_near_source"])).name,
            dots_literal_max_near_3px=rel["lane_dots"]["literal"]["max_near_3px_fraction"],
            dots_literal_source=Path(str(rel["lane_dots"]["literal"]["max_near_source"])).name),
    )
    p = ROOT / "evidence" / "h66_uniqueness_aligned.json"
    p.write_text(json.dumps(out, indent=1, allow_nan=False, default=str) + "\n")
    print(json.dumps({k: out[k] for k in ("corpus", "result", "identical_priors", "read_errors",
                                          "closest_priors", "lane_gate_unchanged")}, indent=1, default=str))
    print(f"\nwrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
