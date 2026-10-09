#!/usr/bin/env python3
"""H74S: frozen seismicity–strain View A × shared surface View B co-training experiment.

This is a thin experiment adapter, not a fork of the shared science: it delegates folds, the
feature store, the learner, the single-feature canary, fit, whole-segment exchange, holdout metric,
metric-aware spacing, lane/uniqueness/format gates, and TIFF writing to the existing template
modules. Only the preregistered View-A feature list, H74S artifact paths and H74S run card are new.
The two-hour/three-experiment limit is checked before each stage. This runner never uploads or
selects a weekly competition slot.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402

import run_h61 as shared  # noqa: E402
import run_h72 as helpers  # noqa: E402 -- reuse audited disagreement/lane helpers, no new evaluator
import build_h61_submission as h61_build  # noqa: E402
from gems52 import evaluate_holdout as evaluator  # noqa: E402
from gems52 import gates, nodes  # noqa: E402
from gems52.submission_writer import write_submission  # noqa: E402

REG = ROOT / "registry/h74s_preregistration.json"
HYP = ROOT / "knowledge/63_hypotheses_H74S_preregistered.md"
FREEZE = ROOT / "evidence/h74s_preregistration_freeze.json"
POSTRUN_FIX = ROOT / "evidence/h74s_postrun_code_correction.json"
WORK = ROOT / "work/h74s"
EVID = ROOT / "evidence"
DOCS_DATA = ROOT / "docs/data"
SAMPLE = ROOT / "data/sample_submission.tif"
CENSUS = WORK / "prior_fetch_receipt.json"
EXTRA_RECEIPT = EVID / "h74s_prior_extension.json"
FEATURE_STORE = ROOT / "work/r2/features"
VIEW_A = ("raw_band_04", "raw_band_07", "raw_band_08", "raw_band_10", "raw_band_16")
ROUND = "H74S"
MAX_SECONDS = 2 * 60 * 60
SEED = shared.SEED
CONTROL_K = 9400


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        n = float(value)
        return n if math.isfinite(n) else None
    if isinstance(value, (np.str_,)):
        return str(value)
    return value


def write_receipt(name: str, obj) -> Path:
    text = json.dumps(clean(obj), indent=2, allow_nan=False) + "\n"
    EVID.mkdir(parents=True, exist_ok=True)
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    path = EVID / f"h74s_{name}.json"
    path.write_text(text)
    (DOCS_DATA / path.name).write_text(text)
    return path


def check_prereg() -> dict:
    reg = json.loads(REG.read_text())
    if reg.get("round") != ROUND or not reg.get("frozen_before_any_fit"):
        raise SystemExit("H74S registration missing, unfrozen, or names another round")
    if sha256(HYP) != reg.get("hypothesis_sha256") or HYP.stat().st_size != reg.get("hypothesis_bytes"):
        raise SystemExit("H74S preregistered hypothesis document moved after registration")
    if tuple(reg.get("view_A_features", ())) != VIEW_A:
        raise SystemExit("H74S runner View A differs from the frozen registration")
    if not FREEZE.is_file():
        raise SystemExit("final H74S pre-run freeze receipt is missing")
    frozen = json.loads(FREEZE.read_text())
    current_runner_sha = sha256(Path(__file__))
    runner_matches_freeze = current_runner_sha == frozen.get("runner_sha256")
    if not runner_matches_freeze and POSTRUN_FIX.is_file():
        correction = json.loads(POSTRUN_FIX.read_text())
        runner_matches_freeze = bool(
            correction.get("executed_runner_sha256") == frozen.get("runner_sha256")
            and correction.get("reviewed_runner_sha256") == current_runner_sha
            and correction.get("scientific_or_method_logic_changed") is False
            and correction.get("experiment_rerun") is False)
    if (frozen.get("preregistration_sha256") != sha256(REG)
            or frozen.get("hypothesis_sha256") != sha256(HYP)
            or not runner_matches_freeze
            or frozen.get("no_h74s_experiment_before_freeze") is not True):
        raise SystemExit("H74S freeze receipt does not pin the current registration, hypothesis and reviewed runner")
    th = reg["thresholds"]
    if (float(th["alpha"]) != evaluator.metric.ALPHA
            or float(th["beta"]) != evaluator.metric.BETA
            or float(th["triangular_kernel_radius_m"]) != evaluator.metric.R_M):
        raise SystemExit("H74S metric constants differ from the shared evaluator")
    if (int(th["matched_budget_dots_per_fold_per_arm"]) != 1264
            or int(th["final_output_dots_total"]) != 5056
            or int(th["control_dots_per_fold"]) != CONTROL_K
            or float(th["minimum_dot_separation_px"]) != 3.0
            or float(th["lane_spearman_stop"]) != 0.90
            or float(th["lane_near_dot_fraction_stop"]) != 0.70
            or float(th["lane_near_dot_radius_px"]) != 3.0):
        raise SystemExit("H74S fixed budgets or literal lane thresholds differ from the runner")
    h61_reg = json.loads((ROOT / "registry/h61_preregistration.json").read_text())
    if int(h61_reg["thresholds"]["buffer_px"]) != int(th["whole_segment_buffer_px"]):
        raise SystemExit("shared spatial fold buffer differs from H74S registration")
    if int(reg["budget"]["max_experiments"]) != 3 or int(reg["budget"]["max_wall_clock_hours"]) != 2:
        raise SystemExit("H74S experiment/time budget differs from the runner")
    if not FEATURE_STORE.is_dir() or not (FEATURE_STORE / "manifest.json").is_file():
        raise SystemExit("shared feature cache is absent; build it once with gems52.structural, not a private builder")
    if not CENSUS.is_file() or not EXTRA_RECEIPT.is_file():
        raise SystemExit("H74S prior registry receipts are missing; no incomplete lane gate is allowed")
    return reg


def configure_shared(reg: dict) -> None:
    """Configure the existing H72 adapter as a new view-list instance without modifying its code."""
    helpers.PREREG = REG
    helpers.HYP_DOC = HYP
    helpers.ROUND = ROUND
    helpers.WORK = WORK
    helpers.EVID = WORK / "helper_evidence"  # keep all H72-named temporary files outside tracked evidence
    helpers.DOCS_DATA = DOCS_DATA
    helpers.CENSUS = CENSUS
    helpers.SAMPLE = SAMPLE
    helpers.LABELS = ROOT / "data/labels.tif"
    helpers.FEATURE_STORE = FEATURE_STORE
    helpers.VIEW_A = VIEW_A
    helpers.write_h72 = write_receipt
    helpers.prior_inventory = prior_inventory
    helpers.prior_source_metadata = prior_source_metadata
    helpers.redirect_shared_runner()
    shared_h74_setup = shared.setup

    def _setup_for_h74s():
        result = list(shared_h74_setup())
        result[0] = dict(result[0])
        result[0]["round"] = ROUND
        return tuple(result)

    shared.setup = _setup_for_h74s
    WORK.mkdir(parents=True, exist_ok=True)


def prior_inventory() -> tuple[list[Path], dict]:
    """The frozen owner census plus local artifacts and user-listed H53–H57 GitHub outputs."""
    receipt = json.loads(CENSUS.read_text())
    if int(receipt.get("n_errors", 0)) != 0:
        raise SystemExit("prior census fetch has errors; no uniqueness/lane decision is allowed")
    paths, meta = h61_build.prior_paths(CENSUS, ("submission", "docs/downloads"))
    extra = json.loads(EXTRA_RECEIPT.read_text())
    if int(extra.get("n_errors", 0)) != 0:
        raise SystemExit("H53–H57 prior extension has errors; no uniqueness/lane decision is allowed")
    extras = [ROOT / rec["local_path"] for rec in extra.get("files", [])
              if rec.get("aligned_single_band")]
    all_paths = [Path(p).resolve() for p in paths if Path(p).is_file()]
    all_paths.extend(p.resolve() for p in extras if p.is_file())
    meta.update(
        local_accessible_paths=len(all_paths),
        prior_extension_repos=extra.get("n_repos"),
        prior_extension_paths=extra.get("n_prediction_raster_paths"),
        prior_extension_aligned=extra.get("n_aligned_single_band"),
        prior_extension_commit_receipt="evidence/h74s_prior_extension.json",
        registry_scope="frozen 2026-10-08 526-blob owner census + current local submission/download TIFFs + H53-H57 public owner repos refreshed 2026-10-09; not private/unlinked",
    )
    return all_paths, meta


def prior_source_metadata(path) -> dict:
    """Resolve a gate offender/max-correlation path to its public owner commit when available."""
    p = Path(path).resolve()
    try:
        rel = str(p.relative_to(ROOT))
    except ValueError:
        rel = str(p)
    if CENSUS.is_file():
        census = json.loads(CENSUS.read_text())
        for blob, rec in census.get("files", {}).items():
            if rec.get("dest") == rel:
                return dict(path=rel, blob=blob, owner_repo=rec.get("repo"),
                            owner_commit=rec.get("commit"), owner_path=rec.get("path"),
                            file_sha256=rec.get("file_sha256"),
                            decoded_sha256=rec.get("decoded_sha256"),
                            provenance="public owner-mirror census; not organizer-authenticated")
    if EXTRA_RECEIPT.is_file():
        extra = json.loads(EXTRA_RECEIPT.read_text())
        for rec in extra.get("files", []):
            if rec.get("local_path") == rel:
                return dict(path=rel, blob_sha=rec.get("blob_sha"), owner_repo=rec.get("repo"),
                            owner_commit=rec.get("commit"), owner_path=rec.get("path"),
                            file_sha256=rec.get("file_sha256"),
                            decoded_sha256=rec.get("decoded_sha256"),
                            provenance="public owner-GitHub extension; Git blob SHA verified; not organizer-authenticated")
    return dict(path=rel, provenance="local accessible prior; no pinned owner-census mapping")


def check_time(start: float, stage: str, experiment: int) -> None:
    elapsed = time.monotonic() - start
    if elapsed > MAX_SECONDS:
        raise SystemExit(f"H74S two-hour budget expired during {stage}; no further stage is permitted")
    if experiment > 3:
        raise SystemExit("H74S three-experiment budget exceeded")


def save_state(state: dict) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "state.json").write_text(json.dumps(clean(state), indent=2, allow_nan=False) + "\n")


def baseline_control_9400() -> dict:
    """Reproduce the same shared single_B control at the registered 9,400-dot/fold budget."""
    _reg, store, _cat, eligible, folds, _va, _vb, ring_px = shared.setup()
    terms = None
    placements = []
    for fold in folds:
        f = int(fold["fold"])
        visible_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = fold["region"] & eligible & ~fold["visible"] & (visible_dist > ring_px)
        del visible_dist
        grid = shared.to_grid(store.flat_idx,
                              np.load(WORK / f"pred_pre_B_f{f}.npy", mmap_mode="r"), eligible.shape)
        field = np.full(eligible.shape, -np.inf, np.float32)
        field[allowed] = shared.pct_rank(grid[allowed])
        emission = nodes.spacing_select(field, allowed, CONTROL_K,
                                        min_px=float(json.loads(REG.read_text())["thresholds"]["minimum_dot_separation_px"]))
        n = int(emission.sum())
        placements.append(dict(fold=f, requested=CONTROL_K, placed=n, filled=n == CONTROL_K))
        _score, term = evaluator.evaluate(emission.astype(np.float32), fold, eligible, block_side=200)
        terms = term if terms is None else terms + term
        del grid, field, emission
    all_filled = all(x["filled"] for x in placements)
    pooled = evaluator.pooled_summary({"single_B": terms}, draws=1000, seed=SEED + 7200,
                                      candidate="single_B") if all_filled else None
    score = pooled["scores"]["single_B"] if pooled else None
    reg = json.loads(REG.read_text())
    target = float(reg["thresholds"]["control_reproduction_target"])
    tolerance = float(reg["thresholds"]["control_reproduction_tolerance"])
    reproduces = bool(score and abs(float(score["dti"]) - target) <= tolerance)
    result = dict(
        evidence_class="HOLDOUT-DTI",
        evaluator_version=evaluator.VERSION,
        alpha=evaluator.metric.ALPHA,
        beta=evaluator.metric.BETA,
        triangular_radius_m=evaluator.metric.R_M,
        dots_per_fold=CONTROL_K,
        withheld_positive_pixels=(score.get("withheld_positive_pixels") if score else None),
        score=score,
        target_evidence_class="HOLDOUT-DTI reference from H71 control receipt; not a leaderboard score",
        reference_target=target,
        tolerance=tolerance,
        placements=placements,
        all_filled=all_filled,
        reproduces=reproduces,
        note="A control reproduction is separate from the matched 1,264-dot candidate comparison; no projection to the board.")
    write_receipt("control_reproduction", result)
    return result


def reasoning_csv(path: Path, emission: np.ndarray, store, candidate: dict,
                  cat_distance_m: np.ndarray) -> dict:
    """One measured/caveated row for every final A-only dot; no geological assertion."""
    rows, cols = np.nonzero(emission)
    grid_idx = np.ravel_multi_index((rows, cols), emission.shape)
    vals = store.gather(grid_idx, list(VIEW_A))
    if not np.isfinite(vals).all():
        raise SystemExit("non-finite View-A value at an emitted H74S location")
    with rasterio.open(SAMPLE) as src:
        transform = src.transform
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "row", "col", "easting_m", "northing_m",
            "raw_band_04_strain_invariant", "raw_band_07_shear_rate", "raw_band_08_dilatation_rate",
            "raw_band_10_distance_to_earthquake", "raw_band_16_earthquake_intensity_or_density",
            "oof_rank_view_A", "oof_rank_view_B", "distance_to_catalogue_m",
            "candidate_geological_reasoning_not_verified", "named_non_fault_mimic", "review_caveat",
        ])
        for i, (row, col) in enumerate(zip(rows, cols)):
            x, y = transform * (int(col) + 0.5, int(row) + 0.5)
            writer.writerow([
                int(row), int(col), f"{x:.2f}", f"{y:.2f}",
                *[f"{float(v):.9g}" for v in vals[i]],
                f"{float(candidate['rank_A'][row, col]):.7f}",
                f"{float(candidate['rank_B'][row, col]):.7f}",
                f"{float(cat_distance_m[row, col]):.2f}",
                "possible strain-plus-seismicity association beneath an abstaining surface view; hypothesis only",
                "geothermal/volcanic swarm or aftershock sequence; geodetic survey/interpolation seam",
                "Owner-mirror band metadata; no field verification; inspect original event/strain provenance and competing lithologic causes.",
            ])
    return dict(file=str(path.relative_to(ROOT)), rows=int(len(rows)),
                evidence_class="geological reasoning diagnostic, not confirmation")


def make_card(state: dict, *, verdict: str, stop_reason: str, canary=None, fit=None,
              exchange=None, holdout=None, control=None, surface=None, placement=None,
              dot_lane=None, uniqueness=None, not_union=None, output=None,
              all_priors_meta=None) -> dict:
    hdt = helpers.format_holdout_summary(holdout) if holdout else {
        "evidence_class": "HOLDOUT-DTI", "evaluator_version": evaluator.VERSION,
        "status": "not run; earlier preregistered stop gate fired"}
    lane = {
        "evidence_class": "registry uniqueness/lane diagnostics, not a score",
        "accessible_registry_scope": all_priors_meta,
        "surface": None,
        "final_dots": None,
        "uniqueness": uniqueness,
        "not_union": not_union,
    }
    if surface:
        lane["surface"] = surface.get("receipt")
    if dot_lane:
        lane["final_dots"] = {
            "literal": dot_lane.get("literal"),
            "policy": dot_lane.get("policy"),
            "priors_checked": dot_lane.get("priors_checked"),
            "error_count": dot_lane.get("error_count"),
            "scope": dot_lane.get("scope"),
        }
    reg = json.loads(REG.read_text())
    proposed_note = "H74S strain+seismic A-only co-training; fixed budget; research-only; no organizer receipt"
    card = {
        "round": ROUND,
        "generated_utc": now(),
        "provenance": {
            "preregistration_sha256": sha256(REG),
            "freeze_receipt_sha256": sha256(FREEZE),
            "hypothesis_document_sha256": sha256(HYP),
            "runner_sha256": sha256(Path(__file__)),
            "feature_cache_manifest_sha256": sha256(FEATURE_STORE / "manifest.json"),
            "core_prior_inventory_receipt_sha256": sha256(CENSUS),
            "h53_h57_prior_extension_receipt_sha256": sha256(EXTRA_RECEIPT),
            "source_boundary": "owner-mirror inputs and public owner GitHub artifacts; no organizer authentication",
        },
        "preregistration_sha256": sha256(REG),
        "hypothesis": reg["hypothesis"],
        "mechanism": "OOF A-confident (rank >=0.95), B-abstaining (rank 0.35-0.65) only; at most one whole-segment buffered pseudo-label exchange; never the union.",
        "named_non_fault_process": reg["named_non_fault_mimic"],
        "holdout_dti": hdt,
        "single_B_control_reproduction": control,
        "correlation_overlap_vs_registry": lane,
        "raster_sha256": (output or {}).get("sha256"),
        "validator_output": (output or {}).get("validator") or {
            "status": "NOT RUN — no TIFF was written",
            "reason": stop_reason,
            "no_nan_inside_footprint": None,
            "values_in_0_1": None,
            "crs_shape_transform_match": None,
        },
        "submission_name": (output or {}).get("submission_name"),
        "submission_note": (output or {}).get("note", proposed_note),
        "submission_note_characters": len((output or {}).get("note", proposed_note)),
        "downloadable": bool(output and (output or {}).get("download_tif")),
        "submit_eligible": False,
        "organizer_confirmed": False,
        "weekly_slot_used": False,
        "experiments_used": int(state.get("experiments_completed", 0)),
        "max_experiments": 3,
        "elapsed_seconds": round(time.monotonic() - float(state["monotonic_start"]), 1),
        "verdict": verdict,
        "stop_reason": stop_reason,
        "phases": {
            "leakage_canary": canary,
            "fit": fit,
            "pseudo_exchange_independence": exchange,
            "placement": placement,
        },
        "output": output,
        "negative_result_is_deliverable": True,
    }
    return clean(card)


def finish(state: dict, *, verdict: str, stop_reason: str, **kw) -> dict:
    state.update(status=verdict, finished_utc=now(), stop_reason=stop_reason,
                 elapsed_seconds=round(time.monotonic() - float(state["monotonic_start"]), 1))
    save_state(state)
    card = make_card(state, verdict=verdict, stop_reason=stop_reason, **kw)
    write_receipt("run_card", card)
    return card


def main() -> int:
    if (EVID / "h74s_run_card.json").is_file():
        raise SystemExit("H74S run card already exists; the frozen round cannot be rerun or retuned")
    if (WORK / "state.json").exists():
        raise SystemExit("H74S state already exists; this frozen round cannot be rerun or retuned")
    reg = check_prereg()
    configure_shared(reg)
    start = time.monotonic()
    priors, prior_meta = prior_inventory()
    state = dict(round=ROUND, status="running", started_utc=now(),
                 preregistration_sha256=sha256(REG), hypothesis_sha256=reg["hypothesis_sha256"],
                 runner_sha256=sha256(Path(__file__)),
                 freeze_receipt_sha256=sha256(FREEZE),
                 feature_cache_manifest_sha256=sha256(FEATURE_STORE / "manifest.json"),
                 core_prior_inventory_receipt_sha256=sha256(CENSUS),
                 prior_extension_receipt_sha256=sha256(EXTRA_RECEIPT),
                 experiments_completed=0, monotonic_start=start,
                 prior_meta=prior_meta, experiment_budget=3,
                 wall_clock_budget_seconds=MAX_SECONDS)
    save_state(state)
    check_time(start, "E1 leakage canary", 1)

    # E1: every individual feature is checked by the shared canary before view fitting is trusted.
    canary = shared.stage_canary()
    state["experiments_completed"] = 1
    state["stage"] = "E1-canary"
    save_state(state)
    check_time(start, "E1 view fit", 1)
    if canary.get("any_alarm"):
        return finish(state, verdict="negative", stop_reason="per-feature leakage canary exceeded 0.90; stopped before full fits",
                      canary=canary, all_priors_meta=prior_meta)
    fit = shared.stage_fit()
    state["stage"] = "E1-view-fits"
    save_state(state)

    # E2: independence is screened first; only a permitted screen may exchange pseudo-labels.
    check_time(start, "E2 independence/exchange", 2)
    exchange = shared.stage_exchange()
    state["experiments_completed"] = 2
    state["stage"] = "E2-independence-exchange"
    save_state(state)
    pre = exchange.get("independence_pre") or {}
    if not exchange.get("allowed_exchange", False):
        return finish(state, verdict="negative", stop_reason="spatial-block negative-error correlation was undefined/strong; co-training abandoned before holdout/build",
                      canary=canary, fit=fit, exchange=exchange, all_priors_meta=prior_meta)

    # E2 hide-and-recover: same masks, evaluator, and fixed matched budget for all arms.
    check_time(start, "E2 hide-and-recover", 2)
    adapted_reg, *_ = shared.setup()
    holdout = helpers.matched_hide_and_recover(adapted_reg)
    control = baseline_control_9400()
    state["stage"] = "E2-holdout"
    save_state(state)
    check_time(start, "E3 pre-placement lane gate", 3)

    # E3: one surface-only uniqueness gate, then one fixed placement if it passes.
    _reg, store, cat, eligible, folds, _va, _vb, _ring_px = shared.setup()
    mosaics = helpers.build_oof_mosaics(store, eligible, folds)
    allowed, cat_distance_m = helpers._full_domain(
        store, eligible, cat, float(adapted_reg["thresholds"]["catalogue_exclusion_m"]))
    surface = helpers.surface_lane_gate(mosaics, allowed, priors, adapted_reg)
    state["stage"] = "E3-surface-lane"
    state["experiments_completed"] = 3
    save_state(state)
    check_time(start, "E3 surface lane gate", 3)
    if not surface["receipt"].get("pass_literal", False):
        return finish(state, verdict="negative", stop_reason="pre-placement surface rank-correlation gate failed or the registry audit was incomplete; no dots placed",
                      canary=canary, fit=fit, exchange=exchange, holdout=holdout,
                      control=control, surface=surface, all_priors_meta=prior_meta)

    candidate = surface["candidate"]
    target = int(adapted_reg["thresholds"]["final_output_dots_total"])
    min_px = float(adapted_reg["thresholds"]["minimum_dot_separation_px"])
    field = np.where(candidate["stratum"], candidate["rank_A"], -np.inf).astype(np.float32)
    emission = nodes.spacing_select(field, candidate["stratum"], target, min_px=min_px)
    placement = dict(target_dots=target, placed_dots=int(emission.sum()),
                     filled=int(emission.sum()) == target,
                     method="gems52.nodes.spacing_select", min_separation_px=min_px,
                     source="strict OOF A-confident/B-abstaining stratum only",
                     no_budget_search=True, evidence_class="placement diagnostic, not a score")

    # The literal user lane rule is applied to every registered prior; no saturation-probe waiver.
    # If the fixed placement is empty, fail closed before asking the nonempty-surface lane checker.
    if int(emission.sum()) == 0:
        return finish(state, verdict="negative", stop_reason="fixed metric-aware placement produced no dots; no second placement or TIFF",
                      canary=canary, fit=fit, exchange=exchange, holdout=holdout,
                      control=control, surface=surface, placement=placement,
                      all_priors_meta=prior_meta)
    dots = emission.astype(np.float32)
    dot_lane = gates.lane_report(
        dots, eligible, priors, sample=SAMPLE, phase="dots",
        rank_limit=float(reg["thresholds"]["lane_spearman_stop"]),
        near_limit=float(reg["thresholds"]["lane_near_dot_fraction_stop"]),
        radius_px=float(reg["thresholds"]["lane_near_dot_radius_px"]))
    write_receipt("lane_dots", dot_lane)
    check_time(start, "E3 final dot lane gate", 3)
    state["stage"] = "E3-final-dot-lane"
    save_state(state)

    lane_ok = bool(
        dot_lane.get("literal", {}).get("verdict") == "PASS"
        and dot_lane.get("error_count", 0) == 0
        and dot_lane.get("priors_checked") == len(priors)
        and dot_lane.get("literal", {}).get("max_spearman") is not None
        and dot_lane["literal"]["max_spearman"] <= float(reg["thresholds"]["lane_spearman_stop"])
        and dot_lane.get("literal", {}).get("max_near_3px_fraction") is not None
        and dot_lane["literal"]["max_near_3px_fraction"] <= float(reg["thresholds"]["lane_near_dot_fraction_stop"]))
    if not placement["filled"] or not lane_ok:
        reason = ("literal final-dot lane DUPLICATE/STOP under the registered all-prior rule; "
                  "no uniqueness waiver, second placement or TIFF" if not lane_ok else
                  "fixed 5,056-dot placement underfilled; no fallback or TIFF")
        return finish(state, verdict="negative", stop_reason=reason,
                      canary=canary, fit=fit, exchange=exchange, holdout=holdout,
                      control=control, surface=surface, placement=placement,
                      dot_lane=dot_lane, all_priors_meta=prior_meta)

    # Only after the literal final-dot rule passes do decoded-pattern, support and not-union gates run.
    check_time(start, "E3 decoded uniqueness", 3)
    uniqueness = gates.uniqueness_report(emission, priors, top=None)
    state["stage"] = "E3-decoded-uniqueness"
    save_state(state)
    check_time(start, "E3 not-union diagnostic", 3)
    uniqueness_ok = bool(
        uniqueness.get("canonical_pattern_unique")
        and not uniqueness.get("equals_literal_prior_union")
        and float(uniqueness.get("novel_fraction") or 0.0)
            >= float(reg["thresholds"]["minimum_support_novel_fraction"]))
    if not uniqueness_ok:
        return finish(state, verdict="negative", stop_reason="decoded-pattern uniqueness/support-novelty gate failed; no TIFF",
                      canary=canary, fit=fit, exchange=exchange, holdout=holdout,
                      control=control, surface=surface, placement=placement,
                      dot_lane=dot_lane, uniqueness=uniqueness,
                      all_priors_meta=prior_meta)
    not_union = helpers.not_union_report(emission, candidate, mosaics, allowed, adapted_reg)
    state["stage"] = "E3-not-union"
    save_state(state)
    check_time(start, "E3 not-union diagnostic", 3)
    if not not_union.get("not_union_pass"):
        return finish(state, verdict="negative", stop_reason="candidate equals a single-view or max-view union placement; no TIFF",
                      canary=canary, fit=fit, exchange=exchange, holdout=holdout,
                      control=control, surface=surface, placement=placement,
                      dot_lane=dot_lane, uniqueness=uniqueness,
                      not_union=not_union, all_priors_meta=prior_meta)

    # Format/bytes are tested only after every lane/uniqueness/not-union gate passes.
    check_time(start, "E3 before artifact write", 3)
    reasoning_path = EVID / "h74s_a_only_geological_reasoning.csv"
    reasoning = reasoning_csv(reasoning_path, emission, store, candidate, cat_distance_m)
    decoded_hash = hashlib.sha256(dots.astype("<f4").tobytes()).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"gems52-h74s-seis-strain-aonly-{int(emission.sum())}px-{stamp}-{decoded_hash[:8]}"
    note = "H74S strain+seismic A-only co-training; fixed budget; research-only; no organizer receipt"
    if len(stem) > 140 or len(note) > 140:
        raise SystemExit("submission name or note exceeds the portal's 140-character field limit")
    submission_path = ROOT / "submission" / f"{stem}.tif"
    receipt = write_submission(
        submission_path, dots, SAMPLE, eligible, name=stem, note=note,
        metadata=dict(round=ROUND, hypothesis_sha256=reg["hypothesis_sha256"],
                      evidence_class="local research candidate; no organizer receipt",
                      submission_slots_used=0, selector_decision_made=False,
                      holdout=helpers.format_holdout_summary(holdout),
                      lane_rule="literal all-prior gate passed"))
    download_dir = ROOT / "docs/downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    dl_tif = download_dir / "h74s-candidate.tif"
    dl_zip = download_dir / "h74s-candidate.zip"
    dl_tif.write_bytes(submission_path.read_bytes())
    dl_zip.write_bytes(submission_path.with_suffix(".zip").read_bytes())
    if sha256(dl_tif) != receipt["sha256"] or sha256(dl_zip) != receipt["zip_sha256"]:
        raise SystemExit("public download byte-copy check failed")
    output = dict(
        file=str(submission_path.relative_to(ROOT)), download_tif=str(dl_tif.relative_to(ROOT)),
        download_zip=str(dl_zip.relative_to(ROOT)), sha256=receipt["sha256"], bytes=receipt["bytes"],
        decoded_sha256=decoded_hash, zip_sha256=receipt["zip_sha256"], emitted_pixels=int(emission.sum()),
        submission_name=stem, note=note, note_characters=len(note), validator=receipt["validator"],
        reasoning=reasoning, downloadable=True, approved_for_weekly_slot=False,
        submission_slots_used=0, organizer_confirmed=False)
    card = make_card(state, verdict="negative" if not _holdout_gate_pass(holdout, control) else "selector-eligible",
                     stop_reason="all local technical gates passed; not uploaded or slot-selected",
                     canary=canary, fit=fit, exchange=exchange, holdout=holdout,
                     control=control, surface=surface, placement=placement,
                     dot_lane=dot_lane, uniqueness=uniqueness, not_union=not_union,
                     output=output, all_priors_meta=prior_meta)
    write_receipt("run_card", card)
    state.update(status=card["verdict"], finished_utc=now(), output=output)
    save_state(state)
    return 0


def _holdout_gate_pass(holdout: dict, control: dict) -> bool:
    """Frozen scientific promotion gate; no board-score projection."""
    if not control or not control.get("reproduces"):
        return False
    pooled = holdout.get("pooled", {})
    if not holdout.get("matched_comparison_valid") or not holdout.get("all_arms_fill_every_fold"):
        return False
    scores = pooled.get("scores", {})
    cand = scores.get("a_only")
    random = scores.get("random")
    paired = holdout.get("candidate_minus_single_B") or {}
    if not cand or not random:
        return False
    delta_ci = paired.get("ci95") or []
    if len(delta_ci) != 2 or float(delta_ci[0]) <= 0:
        return False
    if float(cand.get("dti", -math.inf)) <= float(random.get("dti", math.inf)):
        return False
    return True


def _normalized_exit_code(result) -> int:
    """Negative run cards are successful scientific outcomes, not process exceptions."""
    if isinstance(result, dict):
        return 0
    return int(result or 0)


def _hard_deadline(_signum, _frame):
    raise TimeoutError("H74S hard wall-clock limit of two hours reached; the run is fail-closed")


def _record_failure(exc: BaseException) -> None:
    """Save a negative incident/run card whether failure occurred before or during a stage."""
    WORK.mkdir(parents=True, exist_ok=True)
    state_path = WORK / "state.json"
    state = {}
    if not state_path.exists() and (EVID / "h74s_run_card.json").is_file():
        incident = {
            "round": ROUND, "generated_utc": now(), "verdict": "negative",
            "status": "rerun-rejected", "failure": f"{type(exc).__name__}: {str(exc)[:600]}",
            "downloadable": False, "submit_eligible": False,
            "organizer_confirmed": False, "weekly_slot_used": 0,
            "note": "The tracked completed H74S run card was preserved; a completed frozen round is never rerun.",
        }
        try:
            write_receipt("rerun_rejected", incident)
        except Exception as receipt_exc:
            print(f"could not persist rerun receipt: {type(receipt_exc).__name__}: {receipt_exc}", file=sys.stderr)
        return
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except Exception:
            state = {}
    if state.get("status") in {"negative", "selector-eligible", "complete"}:
        incident = {
            "round": ROUND, "generated_utc": now(), "verdict": "negative",
            "status": "rerun-rejected", "failure": f"{type(exc).__name__}: {str(exc)[:600]}",
            "previous_terminal_status": state.get("status"),
            "downloadable": False, "submit_eligible": False,
            "organizer_confirmed": False, "weekly_slot_used": 0,
            "note": "The completed H74S run was left unchanged; this frozen round is never rerun.",
        }
        try:
            write_receipt("rerun_rejected", incident)
        except Exception as receipt_exc:
            print(f"could not persist rerun receipt: {type(receipt_exc).__name__}: {receipt_exc}", file=sys.stderr)
        return
    state.update(round=ROUND, status="failed", failure_utc=now(),
                 error=f"{type(exc).__name__}: {str(exc)[:600]}")
    if "monotonic_start" in state:
        state["elapsed_seconds"] = round(time.monotonic() - float(state["monotonic_start"]), 1)
    try:
        save_state(state)
        incident = {
            "round": ROUND, "generated_utc": now(), "verdict": "negative",
            "status": "failed-closed", "failure": state["error"],
            "last_stage": state.get("stage"),
            "experiments_completed": state.get("experiments_completed", 0),
            "elapsed_seconds": state.get("elapsed_seconds"),
            "preregistration_sha256": sha256(REG) if REG.is_file() else None,
            "downloadable": False, "submit_eligible": False,
            "organizer_confirmed": False, "weekly_slot_used": False,
            "note": "A failed or interrupted stage is not resumed, retuned, or treated as a measured result.",
        }
        write_receipt("failure", incident)
        write_receipt("run_card", incident)
    except Exception as receipt_exc:
        print(f"could not persist failure receipt: {type(receipt_exc).__name__}: {receipt_exc}", file=sys.stderr)


if __name__ == "__main__":
    signal.signal(signal.SIGALRM, _hard_deadline)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    try:
        exit_code = _normalized_exit_code(main())
    except BaseException as exc:
        _record_failure(exc)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    raise SystemExit(exit_code)
