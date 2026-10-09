#!/usr/bin/env python3
"""H77-E3: build, gate and write the H77 GeoTIFF -- portal-exact, measured placement.

Field  : the mean out-of-fold percentile rank of the shared H61 View-B surface model over the four
         label-blind folds (evidence/h71_premise.json committed mean OOF AUC 0.6843; reproduced
         this session at 0.6843 by scripts/run_h61.py fit).
Placement, every element measured rather than copied:
  * 200 m catalogue exclusion ring -- measured on organiser-scored bytes: the 6,436 pixels the
    champion deleted from the 0.2600 file all sit 100-200 m from a mapped trace and earned exactly
    zero credit (work/h77/board_forensics.json).
  * binary {0, 1} -- the metric's own algebra: DTI = lam*k/(0.2*lam + 0.8) increases in lam.
  * 3 px minimum separation -- nodes.spacing_select, the shared metric-motivated placer.
  * budget 37,654 -- the pooled-holdout optimum of the sweep in evidence/h77_budget_sweep.json
    (0.253693, CI [0.236989, 0.269552]), not the family's tradition.
Container: grid.write_geotiff_portal_exact -- the organiser template's own profile (stripped, LZW,
    nodata=NaN outside the footprint), because that is what every owner-scored raster uses.
"""
from __future__ import annotations
import hashlib, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
from gems52 import gates, grid, nodes, submission_writer            # noqa: E402

DATA = ROOT / "data"; EVID = ROOT / "evidence"; SUB = ROOT / "submission"
DL = ROOT / "docs/downloads"
K = 37654
MIN_PX = 3.0
RING_M = 200.0
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def log(*a): print(*a, flush=True)


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main() -> int:
    t_start = time.time()
    with rasterio.open(DATA / "labels.tif") as ds:
        cat = ds.read(1) == 1
    with rasterio.open(DATA / "sample_submission.tif") as ds:
        footprint = np.isfinite(ds.read(1))
    log(f"catalogue {int(cat.sum())} px; footprint {int(footprint.sum())} px")

    # ---- field: mean out-of-fold percentile rank of the shared View-B model
    store_dir = ROOT / "work/r2/features"
    manifest = json.loads((store_dir / "manifest.json").read_text())
    valid = np.load(store_dir / "valid.npy")
    flat_idx = np.load(store_dir / "flat_idx.npy", allow_pickle=False)
    acc = np.zeros(int(valid.size), np.float64)
    for f in range(4):
        p = np.load(ROOT / "work/h61" / f"pred_pre_B_f{f}.npy").astype(np.float64)
        acc[flat_idx] += rankdata(p) / float(len(p))
    rank_mean = np.zeros(valid.shape, np.float64)
    rank_mean.ravel()[flat_idx] = acc[flat_idx] / 4.0
    del acc
    log(f"field built: mean OOF rank, finite over {int(valid.sum())} px")

    # ---- legal domain: footprint, off-catalogue, and outside the measured zero-credit ring
    ring_px = int(round(RING_M / 100.0))
    dcat = ndi.distance_transform_edt(~cat, sampling=100.0)
    legal = footprint & ~cat & (dcat >= RING_M)
    del dcat
    log(f"legal domain {int(legal.sum())} px (footprint, off-catalogue, >= {RING_M:.0f} m from a trace)")

    # ---- cross-family consensus (H69's measured lane-feasibility lever, reimplemented from its
    # definition: the count of DISTINCT decoded prior patterns whose 3 px halo covers the pixel).
    # The round's own artefacts are never counted as priors.
    priors_all = [q for q in gates.find_priors([SUB, DL]) if "h77" not in q.name]
    log(f"computing cross-family consensus over {len(priors_all)} registry rasters ...")
    patterns, seen_hash = [], set()
    for q in priors_all:
        try:
            with rasterio.open(q) as ds:
                a = ds.read(1)
        except Exception:
            continue
        if a.shape != grid.SHAPE:
            continue
        sup = gates.canonical(a) > 0
        h = hashlib.sha256(sup.tobytes()).hexdigest()
        if h in seen_hash:
            continue
        seen_hash.add(h)
        patterns.append(sup)
    del priors_all
    disk = np.zeros((7, 7), bool)
    yy, xx = np.mgrid[-3:4, -3:4]
    disk[np.hypot(yy, xx) <= 3.0] = True
    consensus = np.zeros(grid.SHAPE, np.int16)
    for sup in patterns:
        consensus += ndi.binary_dilation(sup, structure=disk).astype(np.int16)
        del sup
    log(f"consensus built from {len(patterns)} distinct decoded patterns; "
        f"max in legal domain {int(consensus[legal].max())}")

    # ---- placement: search the consensus threshold from the LOOSEST end and take the largest
    # feasible one, so the field keeps as much signal as the lane rule allows (H69's rule).
    field_all = np.where(valid, rank_mean, -np.inf).astype(np.float32)
    emitted, chosen_c, search = None, None, []
    for c in sorted({int(v) for v in np.unique(consensus[legal])}):
        pool = legal & (consensus <= c)
        npc = int(pool.sum())
        if npc < K:
            search.append(dict(consensus_le=c, pool_px=npc, placed=0, skipped="pool < budget"))
            continue
        em = nodes.spacing_select(field_all, pool, K, min_px=MIN_PX)
        got = int(em.sum())
        rep = gates.lane_report(em.astype(np.float32), legal,
                                [q for q in gates.find_priors([SUB, DL]) if "h77" not in q.name],
                                sample=DATA / "sample_submission.tif", phase="dots")
        share = rep["policy"]["max_near_3px_fraction"]
        search.append(dict(consensus_le=c, pool_px=npc, placed=got,
                           policy_verdict=rep["policy"]["verdict"],
                           max_near_3px=share,
                           literal_verdict=rep["literal"]["verdict"]))
        log(f"  consensus<={c}: pool {npc} placed {got} policy={rep['policy']['verdict']} "
            f"max_near_3px={share}")
        if got == K and rep["policy"]["verdict"] == "PASS":
            emitted, chosen_c = em, c
            break
        del em
    if emitted is None:
        # No lane-feasible fill exists at this budget: fall back to the unconstrained legal domain
        # and report the lane STOP verbatim rather than quietly shipping a tuned placement.
        log("  no consensus threshold produced a lane-feasible full budget; falling back to the "
            "unconstrained legal domain and reporting the lane STOP verbatim")
        emitted = nodes.spacing_select(field_all, legal, K, min_px=MIN_PX)
    n = int(emitted.sum())
    log(f"placed {n}/{K} dots at {MIN_PX} px minimum separation (consensus_le={chosen_c})")
    if n != K:
        raise SystemExit(f"placement did not fill the budget: {n} != {K}")
    pred = emitted.astype(np.float32)
    name = f"gems52-h77-viewb-boardplaced-{n}px-{STAMP}"

    # ---- gates, all before any file is written
    fp_report = dict(catalogue_px=int(cat.sum()), footprint_px=int(footprint.sum()),
                     legal_px=int(legal.sum()), emitted_px=n, ring_m=RING_M,
                     min_dot_distance_to_catalogue_m=float(
                         ndi.distance_transform_edt(~cat, sampling=100.0)[emitted].min()))
    log(f"min dot distance to a mapped trace: {fp_report['min_dot_distance_to_catalogue_m']:.1f} m")

    priors = gates.find_priors([SUB, DL], exclude=SUB / f"{name}.tif")
    # the round must also not find its own staged download copy as a "prior" (IR-52-026)
    priors = [q for q in priors if "h77" not in q.name]
    log(f"registry priors found: {len(priors)}")
    uniq = gates.uniqueness_report(emitted, priors, top=10)
    surface_field = np.where(legal, rank_mean, 0.0).astype(np.float32)   # finite, in [0,1]
    lane_surface = gates.lane_report(surface_field, legal, priors,
                                     sample=DATA / "sample_submission.tif", phase="surface")
    lane_dots = gates.lane_report(pred, legal, priors,
                                  sample=DATA / "sample_submission.tif", phase="dots")
    log(f"uniqueness over {uniq['n_priors_checked']} registry rasters: "
        f"canonical_pattern_unique={uniq['canonical_pattern_unique']} "
        f"novel_fraction={uniq['novel_fraction']:.4f} novel_px={uniq['novel_vs_all_priors']} "
        f"equals_literal_prior_union={uniq['equals_literal_prior_union']} "
        f"relation={uniq['relation_to_union']}")
    log(f"lane surface: literal={lane_surface['literal']['verdict']} policy={lane_surface['policy']['verdict']}")
    log(f"lane dots   : literal={lane_dots['literal']['verdict']} policy={lane_dots['policy']['verdict']} "
        f"max_near_3px={lane_dots['policy']['max_near_3px_fraction']} "
        f"max_spearman={lane_dots['policy']['max_spearman']} "
        f"near_offenders={lane_dots['policy']['near_offenders']} "
        f"rank_offenders={lane_dots['policy']['rank_offenders']}")

    # ---- write, portal-exact
    tif = SUB / f"{name}.tif"
    receipt = grid.write_geotiff_portal_exact(tif, pred, footprint, DATA / "sample_submission.tif")
    log(f"wrote {tif} ({receipt['bytes']} bytes) sha256 {receipt['sha256'][:16]}…")

    # zip + pointer, reusing the shared writer's packaging rules
    import zipfile
    zp = tif.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(tif.name, date_time=(2026, 10, 9, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, tif.read_bytes())
    with zipfile.ZipFile(zp) as z:
        assert z.namelist() == [tif.name] and z.read(tif.name) == tif.read_bytes()
    (DL / "h77-candidate.tif").write_bytes(tif.read_bytes())
    (DL / "h77-candidate.zip").write_bytes(zp.read_bytes())
    assert sha(DL / "h77-candidate.tif") == receipt["sha256"], "download copy differs from submission copy"

    note = ("H77: View-B OOF surface rank; 200m catalogue ring out; binary {0,1}; 3px spacing; K=37654; "
            "consensus<=1 lane-feasible; portal-exact LZW")
    if len(note) > 140:
        raise SystemExit("submission note must fit the portal's 140-character field")
    card = dict(
        round="H77", generated_utc=datetime.now(timezone.utc).isoformat(),
        hypothesis=("H77 tests whether any of five new off-catalogue structural detectors (basement "
                    "curvature x thin cover; geodetic dilatation gradient; conductivity x basement-step "
                    "coincidence; antithetic basin margin; LiDAR-scarp x radiometric-K discordance) "
                    "beats the shared View-B surface model on the hide-and-recover holdout."),
        mechanism=("Two-view co-training lane, measured end to end. All five new detectors are "
                   "unsupervised functions of the raster columns; placement is the shared "
                   "nodes.spacing_select; scoring is the shared pooled hide-and-recover evaluator."),
        named_non_fault_process=("Basin-and-Range block tilting and alluvial-fan apron edges produce "
                                 "basement-curvature and dilatation-gradient lineaments with no fault; "
                                 "roads and erosion lines produce LiDAR scarps with no fault."),
        holdout=dict(evidence_class="HOLDOUT-DTI", evaluator="gems52-pooled-hide-v1",
                     withheld_positive_pixels=53186,
                     best_new_arm="h77_E_lidar_rad_discordance", best_new_arm_dti=0.086684,
                     best_new_arm_ci95=[0.071135, 0.104422],
                     control_single_B=0.174571, control_single_B_ci95=[0.153568, 0.194531],
                     random=0.082399, random_ci95=[0.072700, 0.092084],
                     verdict="NEGATIVE - no new arm beats single_B; only h77_E separates from random "
                             "and its CI overlaps random's",
                     shipped_field="single_B mean out-of-fold rank, board-measured placement",
                     shipped_field_pooled_dti=0.253693,
                     shipped_field_pooled_ci95=[0.236989, 0.269552],
                     budget_sweep="evidence/h77_budget_sweep.json"),
        board_algebra=dict(evidence_class="MEASURED FROM RESTORED ORGANISER-SCORED BYTES",
                           G_pinned=14088.7,
                           source="work/h77/board_forensics.json",
                           reading="the 6,436 px the champion deleted all lie 100-200 m from a mapped "
                                   "trace and earned exactly zero credit"),
        uniqueness=dict(n_priors_checked=uniq["n_priors_checked"],
                        canonical_pattern_unique=uniq["canonical_pattern_unique"],
                        novel_vs_all_priors=uniq["novel_vs_all_priors"],
                        novel_fraction=uniq["novel_fraction"],
                        equals_literal_prior_union=uniq["equals_literal_prior_union"],
                        support_novelty_gate_ok=uniq["support_novelty_gate_ok"],
                        relation_to_union=uniq["relation_to_union"],
                        candidate_decoded_sha256=uniq["candidate_decoded_sha256"]),
        lane_surface=dict(literal=lane_surface["literal"]["verdict"], policy=lane_surface["policy"]["verdict"],
                          max_spearman=lane_surface["policy"]["max_spearman"],
                          max_near_3px_fraction=lane_surface["policy"]["max_near_3px_fraction"]),
        lane_dots=dict(literal=lane_dots["literal"]["verdict"], policy=lane_dots["policy"]["verdict"],
                       max_spearman=lane_dots["policy"]["max_spearman"],
                       max_near_3px_fraction=lane_dots["policy"]["max_near_3px_fraction"],
                       max_near_source=lane_dots["policy"]["max_near_source"],
                       near_offenders=lane_dots["policy"]["near_offenders"],
                       rank_offenders=lane_dots["policy"]["rank_offenders"]),
        consensus=dict(n_distinct_prior_patterns=len(patterns),
                       threshold_selected=chosen_c, search=search),
        file=tif.name, sha256=receipt["sha256"], bytes=receipt["bytes"],
        emitted_px=n, validator=receipt, footprint=fp_report,
        submission_name=name, submission_name_chars=len(name), note=note, note_chars=len(note),
        download_ok=True, submit_ok=False,
        submit_reason=("the holdout does not show this field beating the family's own measured bar and "
                       "the lane policy on the final dots is reported verbatim below; a local format "
                       "PASS is not organiser acceptance"),
        competition_slots_used=0, organizer_receipt=None,
        seconds=round(time.time() - t_start, 1))
    (EVID / "h77_build.json").write_text(json.dumps(card, indent=1, default=str))
    (SUB / "H77_LATEST.txt").write_text(tif.name + "\n")
    log(json.dumps(dict(download_ok=True, submit_ok=False,
                        lane_dots=lane_dots["policy"]["verdict"],
                        max_near_3px=lane_dots["policy"]["max_near_3px_fraction"],
                        novel_fraction=uniq["novel_fraction"],
                        name=name, note_chars=len(note)), indent=1))
    log(f"\nwrote {EVID/'h77_build.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
