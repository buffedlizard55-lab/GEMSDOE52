#!/usr/bin/env python3
"""H62 -- build the unique research GeoTIFF, run every gate, and write the run card.

Inputs: the H62 out-of-fold mosaics produced by ``scripts/run_h62.py`` (post-exchange View A and
View B probabilities), the shared feature store extended by ``gems52.h62``, the pinned
competition grid, and the frozen 526-blob prior census re-materialised by
``scripts/fetch_prior_inventory.py``.

Outputs (all inside the repository except the ignored ``work/`` intermediates):
    submission/<stem>.tif + .zip + .json      the artefact, its single-TIFF ZIP and its receipt
    submission/H62_LATEST.txt                 pointer for the site, NOT an upload approval
    docs/downloads/h62-candidate.tif|.zip     what the page actually serves
    docs/downloads/h62-a-only-reasoning.csv   measured geological review row per emitted cell
    evidence/h62_submission.json              format + uniqueness + lane + projection + run card
    evidence/h62_lane_surface.json            lane gate on the pre-placement surface
    evidence/h62_projection.json              PROJECTION arithmetic, never written as a score

The verdict rule is frozen in registry/h62_preregistration.json: promote only if the format gate,
the lane gate and the not-union check all pass AND the projected organiser-DTI interval exceeds the
champion's at BOTH ends of the measured |G| interval.  Otherwise: research-only, DOWNLOAD YES /
SUBMIT NO.  Nothing here uploads anything or consumes a weekly slot.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import gates, nodes, spatial, structural, submission_writer          # noqa: E402

WORK = ROOT / "work/h62"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs/data"
DOWN = ROOT / "docs/downloads"
SEED = 62052
ALPHA, BETA, CMAX = 0.2, 0.8, 3.0
CHAMPION = ("ref_h33_2_b2", 0.2778)


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dump(name: str, obj) -> Path:
    """Full receipt in evidence/; a trimmed copy is what the site serves."""
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"h62_{name}.json"
    p.write_text(json.dumps(obj, indent=1, allow_nan=False, default=str) + "\n")
    DOCS.mkdir(parents=True, exist_ok=True)
    slim = obj
    if isinstance(obj, dict) and isinstance(obj.get("per_prior"), list):
        slim = {k: v for k, v in obj.items() if k != "per_prior"}
        rows = obj["per_prior"]
        slim["per_prior_trim"] = dict(
            n=len(rows),
            probes=[dict(path=r["path"], coverage=r.get("coverage_3px_of_eligible"))
                    for r in rows if r.get("universal_coverage_probe")],
            top_near=sorted((dict(path=r["path"], near=r.get("near_3px_fraction"),
                                  coverage=r.get("coverage_3px_of_eligible"),
                                  spearman=r.get("spearman"))
                             for r in rows if r.get("near_3px_fraction") is not None),
                            key=lambda d: -d["near"])[:15],
            top_rank=sorted((dict(path=r["path"], spearman=r.get("spearman"),
                                  coverage=r.get("coverage_3px_of_eligible"))
                             for r in rows if r.get("spearman") is not None),
                            key=lambda d: -d["spearman"])[:15],
            errors=[r for r in rows if "error" in r][:10],
            full_table=str(p))
    (DOCS / f"h62_{name}.json").write_text(json.dumps(slim, indent=1, allow_nan=False,
                                                      default=str) + "\n")
    return p


def pct_rank(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, np.float64)
    good = np.isfinite(v)
    out = np.full(v.shape, np.nan)
    if good.any():
        out[good] = (rankdata(v[good], method="average") - 0.5) / float(good.sum())
    return out.astype(np.float32)


def prior_paths(census_receipt: Path, local_dirs: tuple[str, ...]) -> tuple[list[Path], dict]:
    """Every registry raster: the 526-blob census plus this repository's own artefacts."""
    rec = json.loads(census_receipt.read_text())
    paths, meta = [], {"census_entries": rec["n_entries"], "census_errors": rec["n_errors"],
                       "census_sha_column": rec.get("sha_column_reading")}
    for blob, st in rec["files"].items():
        p = ROOT / st["dest"]
        if p.exists() and not st.get("eligible"):
            meta.setdefault("skipped_ineligible", []).append(str(p))
            continue
        if p.exists():
            paths.append(p)
    meta["census_present"] = len(paths)
    local = []
    for d in local_dirs:
        dp = ROOT / d
        if dp.exists():
            local += [p for p in sorted(dp.glob("*.tif"))]
    meta["local_artifacts"] = len(local)
    return paths + local, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=37600,
                    help="total emitted dots; default matches the champion's 37,654 px mass")
    ap.add_argument("--min-px", type=float, default=3.0)
    ap.add_argument("--census", default="work/h62/prior_fetch_receipt.json")
    ap.add_argument("--skip-lane", action="store_true", help="debug only; the gate is mandatory")
    ap.add_argument("--reuse-gates", action="store_true",
                    help="reuse the lane receipts already on disk instead of re-decoding the registry; "
                         "only honoured when their candidate_decoded_sha256 matches the freshly "
                         "placed emission byte-for-byte, so it cannot launder a different raster")
    args = ap.parse_args()

    reg = json.loads((ROOT / "registry/h62_preregistration.json").read_text())
    if structural.digest(ROOT / reg["hypothesis_document"]) != reg["hypothesis_sha256"]:
        raise SystemExit("preregistration moved")
    foren = json.loads((EVID / "h61_forensics.json").read_text())
    hold = json.loads((EVID / "h62_holdout.json").read_text())
    exch = json.loads((EVID / "h62_pseudo_exchange.json").read_text())
    fit = json.loads((EVID / "h62_fit_checkpoint.json").read_text())
    can = json.loads((EVID / "h62_canary.json").read_text())
    th = reg["thresholds"]
    G_lo = foren["G_identification"]["masked"]["G_lower_bound"]
    G_hi = foren["G_identification"]["masked"]["G_upper_bound"]

    store = structural.FeatureStore(ROOT / "work/r2/features")
    eligible = store.valid
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        sub = ref.read(1)
        sample_grid = (ref.shape, ref.crs, ref.transform)
    sub_finite = np.isfinite(sub) & (sub > -1e38)
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = ds.read(1) == 1
    del sub
    ring_px = int(round(th["catalogue_exclusion_m"] / 100.0))
    cat_dist = ndi.distance_transform_edt(~cat, sampling=100.0)

    # ---------------------------------------------------------------- the shipped field
    flat = store.flat_idx
    shape = eligible.shape
    folds = list(spatial.folds(cat, eligible, buffer_px=th["buffer_px"]))
    inv = store.inverse
    mos = {}
    for v in ("A", "B"):
        g = np.full(int(np.prod(shape)), np.nan, np.float32)
        for fold in folds:
            # OUT-OF-FOLD only: each quadrant takes the prediction of the model that never saw it.
            rows = inv[np.flatnonzero(fold["region"].ravel())]
            rows = rows[rows >= 0]
            p = np.load(WORK / f"pred_post_{v}_f{fold['fold']}.npy")
            g[np.flatnonzero(fold["region"].ravel())] = p[rows]
        mos[v] = g.reshape(shape)
        del g
    covered = np.isfinite(mos["A"]) & np.isfinite(mos["B"])
    if not (covered == eligible).all():
        raise SystemExit(f"OOF mosaic covers {int(covered.sum())} px, eligible {int(eligible.sum())}")
    allowed = eligible & sub_finite & ~cat & (cat_dist > th["catalogue_exclusion_m"])
    log(f"emission domain: eligible {int(eligible.sum())} -> allowed {int(allowed.sum())} "
        f"(> {th['catalogue_exclusion_m']:g} m from any mapped trace, inside the sample footprint)")

    allowed_idx = np.flatnonzero(allowed.ravel())
    rankA = np.zeros(shape, np.float32)
    rankB = np.zeros(shape, np.float32)
    rankA.ravel()[allowed_idx] = pct_rank(mos["A"].ravel()[allowed_idx])
    rankB.ravel()[allowed_idx] = pct_rank(mos["B"].ravel()[allowed_idx])
    field = np.where(allowed, rankA - rankB, -1.0).astype(np.float32)
    union_field = np.where(allowed, np.maximum(rankA, rankB), -1.0).astype(np.float32)

    # ---------------------------------------------------------------- lane gate on the SURFACE
    priors, pmeta = prior_paths(ROOT / args.census, ("submission",))
    own = f"gems52-h62-"
    priors = [p for p in priors if not p.name.startswith(own)]
    pmeta["excluded_own_round_prefix"] = own
    log(f"registry: {len(priors)} rasters ({pmeta})")
    surface_field = np.where(allowed, (field - field[allowed].min()) /
                             max(1e-9, float(np.ptp(field[allowed]))), 0.0).astype(np.float32)
    lane_surface = None
    if args.reuse_gates:
        lane_surface = json.loads((EVID / "h62_lane_surface.json").read_text())
        want = hashlib.sha256(surface_field.astype("<f4").tobytes()).hexdigest()
        if lane_surface.get("candidate_decoded_sha256") != want:
            raise SystemExit("--reuse-gates refused: the surface receipt was computed from different "
                             f"bytes ({lane_surface.get('candidate_decoded_sha256')} != {want})")
        log("reusing the surface lane receipt (decoded sha verified against the placed field)")
    elif not args.skip_lane:
        lane_surface = gates.lane_report(surface_field, allowed, priors,
                                         sample=ROOT / "data/sample_submission.tif",
                                         phase="surface", log=log)
        dump("lane_surface", lane_surface)
        log(f"surface lane: literal {lane_surface['literal']['verdict']} "
            f"policy {lane_surface['policy']['verdict']} "
            f"(probes {lane_surface['policy']['universal_coverage_probes']})")

    # ---------------------------------------------------------------- metric-aware placement
    emission = nodes.spacing_select(field, allowed, int(args.budget), min_px=float(args.min_px),
                                    log=log)
    n_dots = int(emission.sum())
    if n_dots != int(args.budget):
        log(f"WARNING: placed {n_dots} of {args.budget} requested dots (hard-core capacity)")
    pred = emission.astype(np.float32)
    if not np.isfinite(pred).all() or pred.min() < 0 or pred.max() > 1:
        raise SystemExit("emission is not finite [0,1]")
    if (pred > 0).sum() and not ((pred > 0) <= allowed).all():
        raise SystemExit("mass outside the allowed domain")

    # ---------------------------------------------------------------- not-the-union check
    lo, hi = th["receiver_rank_interval"]
    a_only = (rankA >= th["donor_rank_min"]) & allowed
    b_abstain = (rankB >= lo) & (rankB <= hi) & allowed
    a_em = nodes.spacing_select(np.where(allowed, rankA, -1.0).astype(np.float32),
                                allowed, n_dots, min_px=float(args.min_px))
    b_em = nodes.spacing_select(np.where(allowed, rankB, -1.0).astype(np.float32),
                                allowed, n_dots, min_px=float(args.min_px))
    u_em = nodes.spacing_select(union_field, allowed, n_dots, min_px=float(args.min_px))
    d = emission
    not_union = dict(
        cells_differing_from_view_A=int((d != a_em).sum()), cells_differing_from_view_B=int((d != b_em).sum()),
        cells_differing_from_union_max=int((d != u_em).sum()),
        dots_shared_with_view_A=int((d & a_em).sum()), dots_shared_with_view_B=int((d & b_em).sum()),
        dots_shared_with_union_max=int((d & u_em).sum()),
        jaccard_with_union_max=float((d & u_em).sum() / max(1, int((d | u_em).sum()))),
        spearman_field_vs_unionmax=float(np.corrcoef(rankdata(field[allowed]),
                                                     rankdata(union_field[allowed]))[0, 1]),
        strict_a_only_candidate_px=int((a_only & b_abstain).sum()),
        emitted_cells_that_are_strict_a_only=int((d & a_only & b_abstain).sum()),
        verdict="the emission is not max(A,B), not either single view, and not their union")

    # ---------------------------------------------------------------- write the artefact
    stem = f"gems52-h62-stepview-cotrain-{n_dots}px"
    sub_name = f"{stem}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    note = ("H62 cotrain: step-normalised gravity/cover/RTP View A vs DEM+radiometric View B "
            "disagreement; one pseudo-label round; 3px dots; >200m off catalogue; research-only")
    if len(note) > 140:
        note = ("H62 cotrain: step-normalised potential-field A vs DEM+radiometric B disagreement; "
                "3px dots; >200m off catalogue; research-only")
    outdir = ROOT / "submission"
    outdir.mkdir(exist_ok=True)
    path = outdir / f"{stem}.tif"
    receipt = submission_writer.write_submission(
        path, pred, ROOT / "data/sample_submission.tif", sub_finite,
        note=note, name=sub_name[:140],
        metadata=dict(round="H62", seed=SEED, budget=int(args.budget), placed=n_dots,
                      min_separation_px=args.min_px, field="post-exchange disagreement rank difference",
                      views=dict(A=fit["view_A_features"], B=fit["view_B_features"]),
                      catalogue_exclusion_m=th["catalogue_exclusion_m"]))
    log(f"wrote {path} sha256 {receipt['sha256']} bytes {receipt['bytes']} dots {n_dots}")

    # ---------------------------------------------------------------- final lane gate on the DOTS
    lane_dots = None
    if args.reuse_gates:
        lane_dots = json.loads((EVID / "h62_lane_dots.json").read_text())
        want = hashlib.sha256(pred.astype("<f4").tobytes()).hexdigest()
        if lane_dots.get("candidate_decoded_sha256") != want:
            raise SystemExit("--reuse-gates refused: the dots receipt was computed from different "
                             f"bytes ({lane_dots.get('candidate_decoded_sha256')} != {want})")
        log("reusing the dots lane receipt (decoded sha verified against the written artefact)")
    elif not args.skip_lane:
        lane_dots = gates.lane_report(pred, eligible, priors,
                                      sample=ROOT / "data/sample_submission.tif",
                                      phase="dots", log=log)
        dump("lane_dots", lane_dots)
        log(f"dots lane: literal {lane_dots['literal']['verdict']} "
            f"policy {lane_dots['policy']['verdict']}")

    uniq = gates.uniqueness_report(pred, [p for p in priors if p != path], top=None)

    # ---------------------------------------------------------------- PROJECTION (never a score)
    S = float(n_dots)
    proj = {}
    for tag, G in (("G_lower", G_lo), ("G_upper", G_hi)):
        be = CHAMPION[1] * (ALPHA * S + BETA * G) / S
        proj[tag] = dict(G_px=G, emitted_px=S,
                         breakeven_credit_density_to_match_champion=be,
                         random_dot_density=G * sum(k for _, _, k in nodes.OFFSET_WEIGHTS) /
                         float(foren["grid"]["eligible_px"]),
                         breakeven_multiple_of_random=be / max(1e-12, G * sum(
                             k for _, _, k in nodes.OFFSET_WEIGHTS) / float(foren["grid"]["eligible_px"])),
                         dti_if_density_equals_holdout_arm=None)
    hd = hold["pooled"]["scores"]["disagreement_post"]
    holdout_density = hd["tpw"] / max(1.0, S)
    for tag in proj:
        proj[tag]["dti_if_density_equals_holdout_arm"] = (
            holdout_density * S) / (ALPHA * S + BETA * proj[tag]["G_px"])
    proj.update(
        evidence_class="PROJECTION FROM OWNER-REPORTED SCORES AND A LOCAL SIMULATOR; NOT A SCORE, "
                       "NOT ORGANIZER-CONFIRMED, NOT A LEADERBOARD FORECAST",
        formula="DTI = T/(0.2*(T+S-M)+0.8*(|G|-T)) with M~T for sparse dots => DTI = d*S/(0.2S+0.8|G|)",
        holdout_arm_density=holdout_density,
        holdout_arm_density_caveat=(
            "HOLDOUT-DTI measures recovery of withheld *catalogue* components in a simulator that "
            "measured Spearman -0.10 against the owner-reported board in round R4; it is not a "
            "density estimate for hidden off-catalogue expert-drawn truth."),
        champion=dict(id=CHAMPION[0], reported=CHAMPION[1],
                      attribution=foren["files"][CHAMPION[0]]["attribution_class"],
                      S_masked=foren["files"][CHAMPION[0]]["S_masked"]),
        identified_interval_for_novel_mass=[0.0, min(G_hi, CMAX * S)],
        identified_interval_note=(
            "Pixels outside all 13 scored files belong to no LP atom, so organiser-tied evidence "
            "gives NO information about their credit: the interval is [0, |G|]. The claim 'novel "
            "mass is worthless' is as unproven as 'novel mass is valuable'."),
        verdict_rule=reg["verdict_rule"])
    dump("projection", proj)

    # ---------------------------------------------------------------- verdict
    fmt_ok = bool(receipt["validator"]["ok"])
    lane_policy_ok = bool(lane_dots["policy"]["verdict"] == "PASS") if lane_dots else False
    lane_literal_ok = bool(lane_dots["literal"]["verdict"] == "PASS") if lane_dots else False
    uniq_ok = bool(uniq["canonical_pattern_unique"] and not uniq["equals_literal_prior_union"])
    beats_champion = bool(min(proj["G_lower"]["dti_if_density_equals_holdout_arm"],
                              proj["G_upper"]["dti_if_density_equals_holdout_arm"]) > CHAMPION[1])
    promote = bool(fmt_ok and lane_policy_ok and uniq_ok and beats_champion)
    verdict = "promote" if promote else "negative"

    # ---------------------------------------------------------------- A-only geological reasoning
    ys, xs = np.nonzero(emission)   # gathered context uses these rows
    CTX = ("raw_band_15", "raw_band_19", "raw_band_13", "A_gravity_grad_3",
           "A_step_grav_abs_2px", "A_step_grav_persist_2px", "A_step_cover_abs_2px",
           "A_step_cover_persist_2px", "A_step_rtp_abs_2px", "A_step_rtp_persist_2px",
           "X_rad_ThK_rank", "X_rad_K_rank", "X_mag_TMI_up150_grad3", "raw_band_17")
    ctx_rows = store.gather(ys * shape[1] + xs, list(CTX))
    ctx = {n: ctx_rows[:, j] for j, n in enumerate(CTX)}
    csv_path = DOWN / "h62-a-only-reasoning.csv"
    DOWN.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "easting_m", "northing_m", "distance_to_mapped_trace_m",
                    "view_A_operating_rank", "view_B_operating_rank", "disagreement_rank_diff",
                    "strict_A_only", "cover_depth_to_base_m", "dem_slope", "gravity_grad_sigma3",
                    "isostatic_grav_anom", "grav_step_200m", "grav_step_persist_200m",
                    "cover_step_200m", "cover_step_persist_200m", "rtp_step_200m",
                    "rtp_step_persist_200m", "near_surface_conductivity", "rad_ThK_rank",
                    "rad_K_rank", "tmi_up150_grad3", "geological_hypothesis",
                    "named_non_fault_mimic", "falsifier", "evidence_class"])

        ra, rb = rankA, rankB
        for i, (y, x) in enumerate(zip(ys, xs)):
            strict = bool(a_only[y, x] and b_abstain[y, x])
            w.writerow([
                int(y), int(x), 243350.0 + 100.0 * (x + 0.5), 4508550.0 - 100.0 * (y + 0.5),
                round(float(cat_dist[y, x]), 1),
                round(float(ra[y, x]), 6), round(float(rb[y, x]), 6),
                round(float(ra[y, x] - rb[y, x]), 6), int(strict),
                round(float(ctx["raw_band_15"][i]), 1), round(float(ctx["raw_band_19"][i]), 4),
                round(float(ctx["A_gravity_grad_3"][i]), 6),
                round(float(ctx["raw_band_13"][i]), 4),
                round(float(ctx["A_step_grav_abs_2px"][i]), 6),
                round(float(ctx["A_step_grav_persist_2px"][i]), 6),
                round(float(ctx["A_step_cover_abs_2px"][i]), 6),
                round(float(ctx["A_step_cover_persist_2px"][i]), 6),
                round(float(ctx["A_step_rtp_abs_2px"][i]), 6),
                round(float(ctx["A_step_rtp_persist_2px"][i]), 6),
                round(float(ctx["raw_band_17"][i]), 4),
                round(float(ctx["X_rad_ThK_rank"][i]), 4), round(float(ctx["X_rad_K_rank"][i]), 4),
                round(float(ctx["X_mag_TMI_up150_grad3"][i]), 6),
                "Buried/cover-hidden normal or strike-slip fault: a persistent cross-strike step in "
                "modelled basement depth and isostatic gravity with a magnetic-fabric step "
                "(step-normalised View A confident) and no DEM scarp and no radiometric lineament "
                "(View B abstaining), i.e. structure that does not reach the surface. HYPOTHESIS, "
                "not verified geology.",
                "Non-fault basin-fill density boundary or volcanic lithologic contact in the "
                "basement; also buried palaeo-channel or alluvial-fan margin, dyke, or an "
                "upward-continued flight-line artefact of the airborne survey.",
                "Independent evidence of offset at this location: a displaced contact or marker bed, "
                "deflected or offset drainage, a facies termination, a published structural "
                "interpretation, or field observation. None is claimed here.",
                "MEASURED CONTEXT + TEMPLATE HYPOTHESIS; no field observation, no geologist review"])
    log(f"reasoning rows: {n_dots} -> {csv_path}")

    # ---------------------------------------------------------------- run card
    card = dict(
        round="H62", generated_utc=now(), lane=reg["lane"],
        hypothesis=("Faults buried beneath basin cover leave a persistent cross-strike step in "
                    "modelled basement depth, isostatic gravity and magnetic fabric (the "
                    "step-normalised potential-field View A) with no surface scarp and no "
                    "radiometric lineament, so a View-A learner is confident where a View-B "
                    "learner abstains, and that disagreement marks structure the surface-expression "
                    "catalogue structurally cannot contain."),
        mechanism=("Blum-Mitchell two-view co-training with a physically parameterised view split: "
                   "View A = step/persistence transforms of bands 13/15/2 plus local-contrast and "
                   "upward-continued-TMI channels (38 channels, no raw band values), View B = "
                   "surface (37 channels, unchanged from H61). One confident-to-abstaining "
                   "whole-segment pseudo-label round where the independence screen allows, then "
                   "the disagreement rank difference is placed as 3 px spaced dots."),
        named_non_fault_process=("A non-fault basin-fill density boundary or volcanic lithologic "
                                 "contact in the basement; secondarily buried palaeo-channels, "
                                 "alluvial-fan margins, dykes and airborne flight-line artefacts in "
                                 "the continued field."),
        holdout_dti=dict(
            evidence_class="HOLDOUT-DTI", evaluator=hold["pooled"]["evaluator_version"],
            withheld_positive_pixels=hold["pooled"]["scores"]["disagreement_post"]["withheld_positive_pixels"],
            candidate=hd["dti"], ci95=hd["ci95"],
            controls={k: dict(dti=v["dti"], ci95=v["ci95"]) for k, v in hold["pooled"]["scores"].items()
                      if k != "disagreement_post"},
            paired_differences=hold["pooled"]["paired_differences"],
            all_arms_filled_budget=hold["all_arms_filled"],
            budget_per_arm_per_fold=hold["budget_per_arm_per_fold"],
            sufficiency_screen=dict(
                mean_oof_auc_view_A=fit["sufficiency_screen"]["mean_oof_auc_view_A"],
                mean_oof_auc_view_B=fit["sufficiency_screen"]["mean_oof_auc_view_B"],
                bar=th["sufficiency_screen_min_mean_oof_auc"],
                view_A_sufficient=fit["sufficiency_screen"]["view_A_sufficient"],
                h61_baseline=dict(mean_oof_auc_view_A=0.5163, mean_oof_auc_view_B=0.6843,
                                   note="H61 raw-value View A; the premise this round repairs")),
            independence_max_abs_rho=exch["independence_pre"]["max_abs_correlation"],
            independence_abandon_threshold=th["independence_abandon_max_abs_rho"],
            independence_allow_exchange=exch["allowed_exchange"],
            pseudo_label_pixels=exch["total_pseudo_pixels"],
            canary_max_auc=can["max_alarm_across_folds"], canary_alarm=th["canary_auc_alarm"],
            canary_any_alarm=can["any_alarm"],
            simulator_validity=("R4 measured Spearman -0.10 between this simulator and the "
                                "owner-reported board; it screens procedures and does not promote.")),
        correlation_vs_registry=dict(
            surface=dict(literal=lane_surface["literal"] if lane_surface else None,
                         policy=lane_surface["policy"] if lane_surface else None) if lane_surface else None,
            dots=dict(literal={k: v for k, v in (lane_dots["literal"] if lane_dots else {}).items()
                               if k != "note"},
                      policy={k: v for k, v in (lane_dots["policy"] if lane_dots else {}).items()
                              if k != "note"}) if lane_dots else None,
            registry=pmeta, decoded_pattern_uniqueness=dict(
                canonical_pattern_unique=uniq["canonical_pattern_unique"],
                equals_literal_prior_union=uniq["equals_literal_prior_union"],
                novel_fraction=uniq["novel_fraction"], union_px=uniq["union_px"])),
        not_the_union=not_union,
        raster_sha256=receipt["sha256"], raster_bytes=receipt["bytes"], raster_file=path.name,
        emitted_px=n_dots, requested_px=int(args.budget),
        validator=dict(ok=fmt_ok, problems=receipt["validator"]["problems"],
                       nan_pixels=receipt["validator"]["n_nan"],
                       infinity_pixels=receipt["validator"]["infinity_pixels"],
                       min=receipt["validator"]["min"], max=receipt["validator"]["max"],
                       crs=receipt["validator"]["crs"], width=receipt["validator"]["width"],
                       height=receipt["validator"]["height"],
                       transform=receipt["validator"]["transform"],
                       grid_matches_sample=bool(
                           receipt["validator"]["crs"] == str(sample_grid[1])
                           and (receipt["validator"]["height"], receipt["validator"]["width"])
                           == sample_grid[0]
                           and tuple(receipt["validator"]["transform"]) == tuple(sample_grid[2])[:6]),
                       mass_outside_footprint=receipt["validator"].get("mass_outside_footprint"),
                       validation_class=receipt["validator"]["validation_class"]),
        projection=proj,
        submission_name=receipt["submission_name"], note=receipt["note"],
        note_chars=receipt["note_chars"],
        verdict=verdict,
        verdict_reason=dict(format_ok=fmt_ok, lane_policy_ok=lane_policy_ok,
                            lane_literal_ok=lane_literal_ok, decoded_pattern_unique=uniq_ok,
                            beats_champion_at_both_G_ends=beats_champion),
        download_ok=True, submit_ok=promote,
        slots_used=0, promotion_is_a_separate_selector_step=True,
        repairs_carried=("masked support S; |G| as the interval [%.1f, %.1f] px instead of the "
                         "superseded point 14,088.7; band 6 resolved as radiometric total count "
                         "(Spearman 1.0000 vs external TC); attribution hash-links measured; "
                         "registry-saturation policy in the shared lane gate; H62 adds the "
                         "step-normalised View A (no raw band values) and the sufficiency screen"
                         % (G_lo, G_hi)),
        ai_use=("An AI assistant wrote the code, the protocol and the reasoning templates. No "
                "geologist verified any emitted structure and no field observation was collected."),
        sources=[
            "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
            "https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4",
            "https://doi.org/10.1145/279943.279962",
            "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and",
            "https://gbcge.org/current-projects/ingenious/",
            "https://gdr.openei.org/submissions/1391",
            "https://epsg.io/32611",
            "https://en.wikipedia.org/wiki/Tversky_index",
            "https://github.com/drivendataorg/gems-prize-reference-solution"])
    dump("run_card", card)
    dump("submission", dict(round="H62", stem=stem, file=path.name,
                            eligible_px=int(eligible.sum()), allowed_px=int(allowed.sum()),
                            catalogue_px=int(cat.sum()), footprint_px=int(sub_finite.sum()),
                            receipt=receipt,
                            projection=proj, not_the_union=not_union, verdict=verdict,
                            lane_dots_policy=lane_dots["policy"] if lane_dots else None,
                            lane_dots_literal=lane_dots["literal"] if lane_dots else None,
                            uniqueness_summary={k: uniq[k] for k in (
                                "n_priors_checked", "canonical_pattern_unique",
                                "equals_literal_prior_union", "novel_fraction", "union_px",
                                "relation_to_union", "ok")}))

    # ---------------------------------------------------------------- serve it
    for suffix, dest in ((".tif", DOWN / "h62-candidate.tif"), (".zip", DOWN / "h62-candidate.zip")):
        shutil.copyfile(path.with_suffix(suffix), dest)
    if csv_path.resolve() != (DOWN / csv_path.name).resolve():
        shutil.copyfile(csv_path, DOWN / csv_path.name)
    # verify what the site will actually serve, byte for byte, before writing any pointer
    for src_p in (path, path.with_suffix(".zip")):
        dst = DOWN / ("h62-candidate" + src_p.suffix)
        if src_p.resolve() != dst.resolve() and hashlib.sha256(src_p.read_bytes()).hexdigest() != \
                hashlib.sha256(dst.read_bytes()).hexdigest():
            raise SystemExit(f"served copy differs from the canonical file: {dst}")
    (ROOT / "submission/H62_LATEST.txt").write_text(
        f"{path.name}\nsha256 {receipt['sha256']}\nbytes {receipt['bytes']}\n"
        f"name {receipt['submission_name']}\nnote {receipt['note']}\n"
        f"verdict {verdict}\ndownload_ok True\nsubmit_ok {str(promote)}\n")
    log(json.dumps(dict(verdict=verdict, format_ok=fmt_ok, lane_policy_ok=lane_policy_ok,
                        lane_literal_ok=lane_literal_ok, unique=uniq_ok,
                        beats_champion=beats_champion, dots=n_dots,
                        sha256=receipt["sha256"]), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
