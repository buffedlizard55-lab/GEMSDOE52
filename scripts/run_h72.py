#!/usr/bin/env python3
"""H72 — preregistered strain-only View A × fixed surface View B disagreement test.

This runner redirects the repository's shared H61 stages into ``work/h72`` and never makes a
private model/evaluator/placement/gate fork.  It expects the already-built shared feature store at
``work/r2/features`` and refuses to rebuild it.  H72 has a three-experiment/two-hour ceiling:
E1 = per-feature leakage canary and shared view fits; E2 = spatial-block error-independence screen,
one whole-segment exchange and matched-budget hide-and-recover; E3 = full-registry surface gate,
then (only if it passes) one fixed-budget placement, final-dot lane gate and uniqueness audit.

The lane gate is literal: a saturation-aware policy PASS never waives a literal duplicate/STOP.
A lane failure is a negative result, not an invitation to retune.  This run does not select a
competition slot or submit anything.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import shutil
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

import run_h61 as shared  # noqa: E402 -- reuse/fix shared stages in place; no private fork
import build_h61_submission as h61_build  # noqa: E402 -- shared census and prior-list builder
from gems52 import evaluate_holdout as evaluator  # noqa: E402
from gems52 import gates, nodes, structural  # noqa: E402
from gems52.submission_writer import write_submission  # noqa: E402

PREREG = ROOT / "registry/h72_preregistration.json"
HYP_DOC = ROOT / "knowledge/59_hypotheses_H72_preregistered.md"
AMEND_DOC = ROOT / "knowledge/59a_h72_budget_amendment.md"
WORK = ROOT / "work/h72"
EVID = ROOT / "evidence"
DOCS_DATA = ROOT / "docs/data"
CENSUS = ROOT / "work/h61/prior_fetch_receipt.json"
SAMPLE = ROOT / "data/sample_submission.tif"
LABELS = ROOT / "data/labels.tif"
FEATURE_STORE = ROOT / "work/r2/features"
SUBMISSION_DIR = ROOT / "submission"
DOWNLOAD_DIR = ROOT / "docs/downloads"
SEED = shared.SEED
VIEW_A = ("raw_band_04", "raw_band_07", "raw_band_08")
ROUND = "H72"
MAX_SECONDS = 2 * 60 * 60


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _clean(value):
    """Convert NumPy/path containers and non-finite numbers to strict JSON-compatible values."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return _clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if np.isfinite(x) else None
    if isinstance(value, (np.str_,)):
        return str(value)
    return value


def write_h72(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    path = EVID / f"h72_{name}.json"
    text = json.dumps(_clean(obj), indent=2, allow_nan=False, sort_keys=False) + "\n"
    path.write_text(text)
    (DOCS_DATA / f"h72_{name}.json").write_text(text)
    return path


def log(*args, **kwargs):
    print(*args, flush=True, **kwargs)


def check_prereg() -> dict:
    reg = json.loads(PREREG.read_text())
    if reg.get("round") != ROUND or not reg.get("frozen_before_any_fit"):
        raise SystemExit("H72 registration is missing, unfrozen, or for another round")
    if sha256(HYP_DOC) != reg.get("hypothesis_sha256"):
        raise SystemExit("H72 hypothesis document hash moved after preregistration")
    if reg.get("hypothesis_document") != str(HYP_DOC.relative_to(ROOT)):
        raise SystemExit("H72 hypothesis document path differs from registration")
    amendments = reg.get("amendments", [])
    amend = next((a for a in amendments if a.get("document") == str(AMEND_DOC.relative_to(ROOT))), None)
    if not amend or sha256(AMEND_DOC) != amend.get("sha256") or AMEND_DOC.stat().st_size != amend.get("bytes"):
        raise SystemExit("H72 final-budget amendment is missing or its hash moved")
    th = reg["thresholds"]
    if th.get("matched_budget_dots_per_fold_per_arm") != 1264 or th.get("final_output_dots_total") != 5056:
        raise SystemExit("H72 frozen budgets differ from the runner")
    if (float(th["alpha"]) != evaluator.metric.ALPHA
            or float(th["beta"]) != evaluator.metric.BETA
            or float(th["triangular_kernel_radius_m"]) != evaluator.metric.R_M):
        raise SystemExit("H72 registered DTI constants differ from the shared metric implementation")
    if len(reg.get("budget", {}).get("experiments", [])) != 3:
        raise SystemExit("H72 experiment ledger is not the registered three-stage budget")
    if not FEATURE_STORE.is_dir() or not (FEATURE_STORE / "manifest.json").is_file():
        raise SystemExit("shared feature cache is absent; H72 is not allowed to rebuild it")
    return reg


def _h72_setup():
    """Adapt only the registered H72-A feature list; all shared setup checks remain in H61."""
    reg, store, cat, eligible, folds, _h61_a, vb, ring_px = _ORIGINAL_SETUP()
    manifest_a = tuple(store.manifest["view_A_with_external"])
    manifest_b = tuple(store.manifest["view_B_with_external"])
    if not set(VIEW_A).issubset(manifest_a):
        raise SystemExit(f"registered H72 strain features unavailable: {VIEW_A}")
    if tuple(vb) != manifest_b:
        raise SystemExit("H72 changed the frozen shared View B feature list")
    if set(VIEW_A) & set(vb):
        raise SystemExit("cross-view feature overlap in H72")
    h72_thresholds = json.loads(PREREG.read_text())["thresholds"]
    r = copy.deepcopy(reg)
    th = r["thresholds"]
    th["budget_dots_per_fold_per_arm"] = int(h72_thresholds["matched_budget_dots_per_fold_per_arm"])
    th["matched_budget_dots_per_fold_per_arm"] = int(h72_thresholds["matched_budget_dots_per_fold_per_arm"])
    th["final_output_dots_total"] = int(h72_thresholds["final_output_dots_total"])
    th["min_dot_separation_px"] = float(h72_thresholds["minimum_dot_separation_px"])
    th["minimum_dot_separation_px"] = float(h72_thresholds["minimum_dot_separation_px"])
    th["donor_rank_min"] = float(h72_thresholds["donor_rank_min"])
    th["receiver_rank_interval"] = list(h72_thresholds["receiver_rank_interval"])
    th["catalogue_exclusion_m"] = float(h72_thresholds["catalogue_exclusion_m"])
    th["independence_abandon_max_abs_rho"] = float(h72_thresholds["independence_abandon_max_abs_rho"])
    th["canary_auc_alarm"] = float(h72_thresholds["canary_auc_alarm"])
    th["block_side_px"] = int(h72_thresholds["negative_error_block_side_px"])
    th["min_pseudo_pixels"] = int(h72_thresholds["pseudo_min_pixels"])
    th["pseudo_cap_per_fold"] = int(h72_thresholds["pseudo_cap_per_fold"])
    th["bootstrap_draws"] = int(h72_thresholds["bootstrap_draws"])
    th["bootstrap_block_px"] = int(h72_thresholds["bootstrap_block_px"])
    th["alpha"] = float(h72_thresholds["alpha"])
    th["beta"] = float(h72_thresholds["beta"])
    th["triangular_kernel_radius_m"] = float(h72_thresholds["triangular_kernel_radius_m"])
    th["lane_spearman_stop"] = float(h72_thresholds["lane_spearman_stop"])
    th["lane_near_dot_fraction_stop"] = float(h72_thresholds["lane_near_dot_fraction_stop"])
    th["lane_near_dot_radius_px"] = float(h72_thresholds["lane_near_dot_radius_px"])
    # H72 is a restricted, preregistered A view; B and the fit machinery remain shared.
    return r, store, cat, eligible, folds, list(VIEW_A), list(vb), ring_px


_ORIGINAL_SETUP = shared.setup


def redirect_shared_runner() -> None:
    shared.setup = _h72_setup
    shared.WORK = WORK
    shared.EVID = EVID
    shared.DOCS = DOCS_DATA
    shared.write = write_h72


def prior_inventory() -> tuple[list[Path], dict]:
    if not CENSUS.is_file():
        raise SystemExit("pinned prior-inventory receipt is missing; do not re-fetch automatically")
    paths, meta = h61_build.prior_paths(CENSUS, ("submission", "docs/downloads"))
    paths = [Path(p).resolve() for p in paths if Path(p).is_file()]
    paths = [p for p in paths if not p.name.startswith("gems52-h72-")]
    # Preserve every path for the shared gates; the gates deduplicate decoded patterns and expose
    # aliases.  Record the fetch receipt's actual limitation, rather than treating file hashes as
    # decoded-pattern verification.
    receipt = json.loads(CENSUS.read_text())
    meta.update(
        registry_paths=len(paths),
        fetched_entries=receipt.get("n_fetched"),
        fetch_errors=receipt.get("n_errors"),
        file_hash_matches=receipt.get("n_census_sha_is_file_sha"),
        decoded_hash_matches=receipt.get("n_census_sha_is_decoded_sha"),
        hash_column_reading=receipt.get("sha_column_reading"),
        decoded_hash_caveat="decoded_sha_matches_census was false for all fetched entries; uniqueness gates decode current local bytes themselves",
    )
    return paths, meta


def _rank_on_domain(values: np.ndarray, domain: np.ndarray) -> np.ndarray:
    out = np.full(values.shape, np.nan, np.float32)
    out[domain] = shared.pct_rank(np.asarray(values[domain], np.float32))
    return out


def prior_source_metadata(path) -> dict:
    """Map an H61-census path back to its owner repository/path without claiming authentication."""
    p = Path(path).resolve()
    try:
        rel = str(p.relative_to(ROOT))
    except ValueError:
        rel = str(p)
    if CENSUS.is_file():
        receipt = json.loads(CENSUS.read_text())
        for blob, rec in receipt.get("files", {}).items():
            if rec.get("dest") == rel:
                return dict(path=rel, blob=blob, owner_repo=rec.get("repo"),
                            owner_commit=rec.get("commit"), owner_path=rec.get("path"),
                            file_sha256=rec.get("file_sha256"),
                            decoded_sha256=rec.get("decoded_sha256"),
                            provenance="owner-mirrored census entry; not organizer-authenticated")
    return dict(path=rel, provenance="local accessible prior; no census owner mapping")


def build_oof_mosaics(store, eligible: np.ndarray, folds: list[dict]) -> dict[str, np.ndarray]:
    """Use each fold's own out-of-fold predictions only, covering the eligible domain once."""
    inv = store.inverse
    shape = eligible.shape
    mosaics: dict[str, np.ndarray] = {}
    cover = np.zeros(shape, bool)
    for view in ("A", "B"):
        grid = np.full(int(np.prod(shape)), np.nan, np.float32)
        for fold in folds:
            f = int(fold["fold"])
            region = np.asarray(fold["region"], bool) & eligible
            grid_idx = np.flatnonzero(region.ravel())
            rows = inv[grid_idx]
            if np.any(rows < 0):
                raise SystemExit(f"fold {f} OOF region includes an ineligible feature index")
            pred_path = WORK / f"pred_post_{view}_f{f}.npy"
            if not pred_path.is_file():
                raise SystemExit(f"missing shared post-fit prediction: {pred_path.name}")
            p = np.load(pred_path, mmap_mode="r")
            if p.ndim != 1 or len(p) != len(store.flat_idx):
                raise SystemExit(f"unexpected shared prediction shape: {pred_path.name}")
            grid[grid_idx] = p[rows]
            if view == "A":
                cover.ravel()[grid_idx] = True
        mosaics[view] = grid.reshape(shape)
    if not np.array_equal(cover, eligible):
        raise SystemExit(f"OOF mosaic coverage mismatch: {int(cover.sum())} of {int(eligible.sum())} eligible")
    if not np.isfinite(mosaics["A"][eligible]).all() or not np.isfinite(mosaics["B"][eligible]).all():
        raise SystemExit("nonfinite OOF mosaic inside feature footprint")
    return mosaics


def _full_domain(store, eligible, cat, ring_m: float) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(SAMPLE) as ds:
        sample = ds.read(1)
        sample_ok = np.isfinite(sample) & (sample > -1e38)
        sample_meta = dict(shape=list(ds.shape), crs=str(ds.crs), transform=list(ds.transform)[:6])
    cat_dist_m = ndi.distance_transform_edt(~cat, sampling=100.0)
    allowed = eligible & sample_ok & ~cat & (cat_dist_m > ring_m)
    return allowed, cat_dist_m


def build_a_only_surface(mosaics: dict[str, np.ndarray], allowed: np.ndarray,
                         donor_min: float, receiver_interval: tuple[float, float]):
    ra = _rank_on_domain(mosaics["A"], allowed)
    rb = _rank_on_domain(mosaics["B"], allowed)
    lo, hi = receiver_interval
    stratum = allowed & (ra >= donor_min) & (rb >= lo) & (rb <= hi)
    if not stratum.any():
        raise SystemExit("the preregistered A-only disagreement stratum is empty")
    field = np.where(stratum, ra, 0.0).astype(np.float32)
    vals = field[allowed]
    span = float(np.ptp(vals))
    if not np.isfinite(span) or span <= 0:
        raise SystemExit("constant A-only surface has no lane-rank evidence")
    surface = np.where(allowed, (field - float(vals.min())) / span, 0.0).astype(np.float32)
    return dict(rank_A=ra, rank_B=rb, stratum=stratum, field=field, surface=surface,
                stratum_pixels=int(stratum.sum()))


def surface_lane_gate(mosaics, allowed, priors, reg):
    th = reg["thresholds"]
    candidate = build_a_only_surface(
        mosaics, allowed, float(th["donor_rank_min"]), tuple(th["receiver_rank_interval"]))
    cached_path = EVID / "h72_lane_surface.json"
    rep = None
    if cached_path.is_file():
        cached = json.loads(cached_path.read_text())
        digest = hashlib.sha256(candidate["surface"].astype("<f4").tobytes()).hexdigest()
        if cached.get("candidate_decoded_sha256") == digest:
            rep = cached
            log("H72 surface lane: reusing prior receipt for byte-identical OOF surface")
    if rep is None:
        rep = gates.lane_report(candidate["surface"], allowed, priors, sample=SAMPLE,
                                phase="surface", log=log)
        write_h72("lane_surface", rep)
    literal = rep["literal"]
    rank_rows = [r for r in rep.get("per_prior", []) if r.get("spearman") is not None]
    max_rank_row = max(rank_rows, key=lambda r: r["spearman"]) if rank_rows else None
    pass_literal = bool(literal.get("verdict") == "PASS"
                        and rep.get("error_count", 0) == 0
                        and rep.get("priors_checked", 0) == len(priors)
                        and literal.get("max_spearman") is not None
                        and literal["max_spearman"] <= float(th["lane_spearman_stop"]))
    result = dict(
        candidate=candidate,
        receipt=dict(pass_literal=pass_literal, literal_verdict=literal.get("verdict"),
                     policy_verdict=rep["policy"].get("verdict"),
                     max_spearman=literal.get("max_spearman"),
                     max_spearman_source=(prior_source_metadata(max_rank_row["path"])
                                          if max_rank_row else None),
                     rank_stop=float(th["lane_spearman_stop"]),
                     priors_checked=rep.get("priors_checked"), expected_priors=len(priors),
                     error_count=rep.get("error_count"),
                     evidence_class="uniqueness/lane diagnostic, not a score"))
    return result


def _fold_predictions(fold: dict, store, eligible: np.ndarray) -> dict[str, np.ndarray]:
    out = {}
    for mode in ("pre", "post"):
        for view in ("A", "B"):
            p = np.load(WORK / f"pred_{mode}_{view}_f{fold['fold']}.npy", mmap_mode="r")
            out[f"{mode}_{view}"] = shared.to_grid(store.flat_idx, p, eligible.shape)
    return out


def matched_hide_and_recover(reg) -> dict:
    """Fixed-budget whole-fault-segment hide/recover; all catalog geometry is fold-visible only."""
    th = reg["thresholds"]
    _, store, cat, eligible, folds, _va, _vb, ring_px = shared.setup()
    K = int(th["matched_budget_dots_per_fold_per_arm"])
    min_px = float(th["minimum_dot_separation_px"])
    arms = ("a_only", "single_A", "single_B", "union_max", "disagreement_pre",
            "disagreement_post", "random")
    terms = {arm: None for arm in arms}
    fold_rows, all_filled = [], True
    rng_seed = SEED + 7200
    for fold in folds:
        f = int(fold["fold"])
        # The scoring domain is a whole held-out segment/block. The emission collar is built from
        # this fold's visible faults only; hidden labels never enter placement or catalogue features.
        visible_dist = ndi.distance_transform_edt(~fold["visible"])
        allowed = (fold["region"] & eligible & ~fold["visible"] & (visible_dist > ring_px))
        del visible_dist
        pred = _fold_predictions(fold, store, eligible)
        rank_pre = {v: _rank_on_domain(pred[f"pre_{v}"], allowed) for v in ("A", "B")}
        rank_post = {v: _rank_on_domain(pred[f"post_{v}"], allowed) for v in ("A", "B")}
        lo, hi = map(float, th["receiver_rank_interval"])
        donor = float(th["donor_rank_min"])
        a_stratum = allowed & (rank_post["A"] >= donor) & (rank_post["B"] >= lo) & (rank_post["B"] <= hi)
        fields = {
            "single_A": rank_pre["A"],
            "single_B": rank_pre["B"],
            "union_max": np.maximum(rank_pre["A"], rank_pre["B"]),
            "disagreement_pre": rank_pre["A"] - rank_pre["B"],
            "disagreement_post": rank_post["A"] - rank_post["B"],
        }
        rng = np.random.default_rng(rng_seed + f)
        random_field = np.full(eligible.shape, np.nan, np.float32)
        random_field[allowed] = rng.random(int(allowed.sum()), dtype=np.float32)
        fields["random"] = random_field
        fields["a_only"] = rank_post["A"]
        allowed_by_arm = {a: allowed for a in arms}
        allowed_by_arm["a_only"] = a_stratum
        row = dict(fold=f, allowed_px=int(allowed.sum()), a_only_stratum_px=int(a_stratum.sum()),
                   visible_fault_px=int(fold["visible"].sum()), hidden_positive_px=int((fold["truth"] & fold["region"]).sum()),
                   arms={})
        for arm in arms:
            emission = nodes.spacing_select(fields[arm], allowed_by_arm[arm], K, min_px=min_px)
            placed = int(emission.sum())
            filled = placed == K
            all_filled &= filled
            score, term = evaluator.evaluate(emission.astype(np.float32), fold, eligible,
                                             block_side=int(th["bootstrap_block_px"]))
            terms[arm] = term if terms[arm] is None else terms[arm] + term
            row["arms"][arm] = dict(
                requested=K, placed=placed, filled=filled,
                withheld_positive_pixels=int(score["n_truth"]),
                metric_terms_available_for_pooled_bootstrap=True,
                evidence_class="placement receipt only; pooled score is in pooled.scores with 95% CI",
                evaluator_version=evaluator.VERSION)
        a_mask = nodes.spacing_select(fields["a_only"], a_stratum, K, min_px=min_px)
        union_mask = nodes.spacing_select(fields["union_max"], allowed, K, min_px=min_px)
        a_union_intersection = int((a_mask & union_mask).sum())
        row["not_union"] = dict(
            a_only_dots=int(a_mask.sum()), max_view_union_dots=int(union_mask.sum()),
            intersection=a_union_intersection,
            jaccard=float(a_union_intersection / max(int((a_mask | union_mask).sum()), 1)),
            exactly_equal=bool(np.array_equal(a_mask, union_mask)),
            explanation="The measured arm is ranked only inside high-A / mid-rank-B abstention; it is not the union/max of the two views.")
        fold_rows.append(row)
        del pred, fields, random_field, rank_pre, rank_post

    if all_filled:
        pooled = evaluator.pooled_summary(terms, draws=int(th["bootstrap_draws"]),
                                          seed=SEED + 7200, candidate="a_only")
        matched = True
        paired = pooled["paired_differences"].get("single_B")
    else:
        # Still report each arm's own pooled HOLDOUT-DTI, but do not publish incomparable paired
        # deltas as a matched-budget gate. No candidate-stratum rescue is allowed.
        pooled = {"evidence_class": "HOLDOUT-DTI", "evaluator_version": evaluator.VERSION,
                  "matched_comparison_valid": False, "scores": {}, "paired_differences": {},
                  "reason": "at least one arm failed to fill the fixed per-fold budget; no fallback or retuning"}
        for arm in arms:
            s = evaluator.pooled_summary({arm: terms[arm]}, draws=int(th["bootstrap_draws"]),
                                         seed=SEED + 7200, candidate=arm)
            pooled["scores"][arm] = s["scores"][arm]
        matched, paired = False, None
    out = dict(
        stage="E2 hide-and-recover", started_utc=now(), finished_utc=now(),
        evidence_class="HOLDOUT-DTI", evaluator_version=evaluator.VERSION,
        alpha=float(th["alpha"]), beta=float(th["beta"]),
        triangular_radius_m=float(th["triangular_kernel_radius_m"]),
        matched_budget_dots_per_fold_per_arm=K,
        minimum_separation_px=min_px,
        held_fault_components="whole spatial segments with the registered 80 px train/evaluation buffer; catalogue features/support use fold-visible faults only",
        exact_visible_fault_mask=True,
        exchange_budget=1,
        all_arms_fill_every_fold=bool(all_filled),
        matched_comparison_valid=bool(matched),
        folds=fold_rows,
        pooled=pooled,
        candidate_minus_single_B=paired,
        withheld_positive_pixels=(pooled.get("scores", {}).get("a_only", {})
                                  or {}).get("withheld_positive_pixels"),
        negative_class="held-out catalogue-zero proxies, not verified fault absence",
        bootstrap=dict(method="paired physical 20 km block bootstrap", draws=int(th["bootstrap_draws"]),
                       confidence=0.95, seed=SEED + 7200,
                       caveat="conditional on fixed folds/labels and not a leaderboard interval"),
        note="No projection to a public-board or organizer score.")
    write_h72("holdout", out)
    return out


def format_holdout_summary(holdout: dict) -> dict:
    scores = holdout.get("pooled", {}).get("scores", {})
    out = dict(
        evidence_class="HOLDOUT-DTI",
        evaluator_version=holdout["evaluator_version"],
        alpha=holdout.get("alpha"), beta=holdout.get("beta"),
        triangular_radius_m=holdout.get("triangular_radius_m"),
        withheld_positive_pixels=holdout.get("withheld_positive_pixels"),
        matched_budget_dots_per_fold_per_arm=holdout.get("matched_budget_dots_per_fold_per_arm"),
        minimum_separation_px=holdout.get("minimum_separation_px"),
        all_arms_fill_every_fold=holdout.get("all_arms_fill_every_fold"),
        candidate_placed_by_fold={str(f["fold"]): f["arms"]["a_only"]["placed"]
                                  for f in holdout.get("folds", [])},
        candidate_underfilled_folds=[f["fold"] for f in holdout.get("folds", [])
                                     if not f["arms"]["a_only"]["filled"]],
        matched_comparison_valid=holdout.get("matched_comparison_valid"),
        comparison_invalid_reason=(holdout.get("pooled", {}).get("reason")
                                   if not holdout.get("matched_comparison_valid") else None),
        scores={})
    for arm, score in scores.items():
        out["scores"][arm] = dict(
            evidence_class="HOLDOUT-DTI", evaluator_version=holdout["evaluator_version"],
            withheld_positive_pixels=score.get("withheld_positive_pixels"),
            dti=score.get("dti"), ci95=score.get("ci95"),
            interpretation=("candidate DTI uses its achieved per-fold placement count; no paired delta is valid"
                            if arm == "a_only" and not holdout.get("matched_comparison_valid") else None))
    paired = holdout.get("candidate_minus_single_B")
    if paired:
        out["paired_candidate_minus_single_B"] = paired
    return out


def final_oof_field(mosaics, allowed, reg):
    th = reg["thresholds"]
    cand = build_a_only_surface(
        mosaics, allowed, float(th["donor_rank_min"]), tuple(th["receiver_rank_interval"]))
    field = np.where(cand["stratum"], cand["rank_A"], -np.inf).astype(np.float32)
    return cand, field


def _jaccard(a: np.ndarray, b: np.ndarray) -> float:
    aa, bb = np.asarray(a, bool), np.asarray(b, bool)
    return float((aa & bb).sum() / max(int((aa | bb).sum()), 1))


def not_union_report(emission, candidate, mosaics, allowed, reg):
    th = reg["thresholds"]
    ra, rb = candidate["rank_A"], candidate["rank_B"]
    a_rank = np.where(allowed, ra, -np.inf).astype(np.float32)
    b_rank = np.where(allowed, rb, -np.inf).astype(np.float32)
    union_rank = np.where(allowed, np.maximum(ra, rb), -np.inf).astype(np.float32)
    k = int(th["final_output_dots_total"])
    minpx = float(th["minimum_dot_separation_px"])
    a_dots = nodes.spacing_select(a_rank, allowed, k, min_px=minpx)
    b_dots = nodes.spacing_select(b_rank, allowed, k, min_px=minpx)
    union_dots = nodes.spacing_select(union_rank, allowed, k, min_px=minpx)
    strict = candidate["stratum"]
    exact_union = bool(np.array_equal(emission, union_dots))
    exact_a = bool(np.array_equal(emission, a_dots))
    exact_b = bool(np.array_equal(emission, b_dots))
    return dict(
        method="candidate emitted only from the strict preregistered A-only disagreement stratum; compared to matched-mass single-view and max(A,B) placements",
        candidate_dots=int(emission.sum()),
        every_dot_in_strict_a_only_stratum=bool(np.all(strict[emission])),
        equals_single_A=exact_a, equals_single_B=exact_b, equals_union_max=exact_union,
        jaccard_single_A=_jaccard(emission, a_dots),
        jaccard_single_B=_jaccard(emission, b_dots),
        jaccard_union_max=_jaccard(emission, union_dots),
        cells_different_from_union=int((emission != union_dots).sum()),
        not_union_pass=bool(np.all(strict[emission]) and not exact_union and not exact_a and not exact_b),
        evidence_class="placement/method diagnostic, not a score")


def write_geological_reasoning(path: Path, emitted: np.ndarray, store,
                               candidate: dict, cat_dist_m: np.ndarray) -> dict:
    """One measured, caveated geological rationale row per proposed emitted dot."""
    rows, cols = np.nonzero(emitted)
    grid_idx = np.ravel_multi_index((rows, cols), emitted.shape)
    feature_rows = store.inverse[grid_idx]
    if np.any(feature_rows < 0):
        raise SystemExit("an emitted H72 dot has no shared feature-store row")
    # FeatureStore.gather accepts grid-flat indices (it applies its inverse mapping internally).
    vals = store.gather(grid_idx, list(VIEW_A))
    if not np.isfinite(vals).all():
        raise SystemExit("nonfinite strain-channel value at an emitted H72 candidate")
    coords = []
    with rasterio.open(SAMPLE) as ds:
        transform = ds.transform
        for row, col in zip(rows, cols):
            x, y = transform * (int(col) + 0.5, int(row) + 0.5)
            coords.append((x, y))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row", "col", "easting_m", "northing_m", "raw_band_04", "raw_band_07", "raw_band_08",
                    "oof_rank_view_A", "oof_rank_view_B", "distance_to_visible_catalogue_m",
                    "geological_hypothesis_not_verified", "named_non_fault_mimic", "review_caveat"])
        for i, (row, col) in enumerate(zip(rows, cols)):
            w.writerow([
                int(row), int(col), f"{coords[i][0]:.2f}", f"{coords[i][1]:.2f}",
                f"{float(vals[i, 0]):.8g}", f"{float(vals[i, 1]):.8g}", f"{float(vals[i, 2]):.8g}",
                f"{float(candidate['rank_A'][row, col]):.7f}", f"{float(candidate['rank_B'][row, col]):.7f}",
                f"{float(cat_dist_m[row, col]):.2f}",
                "possible concealed fault-related strain/shear anomaly where View A is high-confidence and fixed View B abstains; hypothesis only",
                "broad interseismic loading or geodetic interpolation/survey seam; not a fault",
                "No independent field/geologic map confirmation; inspect strain coherence, mapped faults, and original survey provenance before interpretation",
            ])
    return dict(file=str(path.relative_to(ROOT)), rows=int(len(rows)),
                rationale="one row per proposed dot, including all three raw preregistered channels and the OOF A/B ranks",
                caveat="unreleased candidate diagnostic, not a submission TIFF; geological interpretation is a testable hypothesis, not fault confirmation")


def make_run_card(reg, state, *, canary=None, fit=None, exchange=None, surface=None,
                  holdout=None, final_gate=None, uniqueness=None, output=None, build=None,
                  stop_reason=None) -> dict:
    th = reg["thresholds"]
    hold_sum = format_holdout_summary(holdout) if holdout else None
    can_summary = None
    if canary:
        can_summary = dict(
            evidence_class="LEAKAGE-CANARY AUC (diagnostic, not a DTI score)",
            alarm_auc=float(th["canary_auc_alarm"]),
            any_alarm=bool(canary.get("any_alarm")),
            max_alarm_auc=canary.get("max_alarm_across_folds"),
            max_fitted_top5_heldout_auc=canary.get("max_fitted_top5_heldout_auc"),
            dropped_features=canary.get("dropped_features"),
            receipt="evidence/h72_canary.json")
    exchange_summary = None
    if exchange:
        independence = exchange.get("independence_pre", {})
        exchange_summary = dict(
            max_abs_error_correlation=independence.get("max_abs_correlation"),
            threshold=float(th["independence_abandon_max_abs_rho"]),
            block_count=independence.get("n_blocks"),
            exchange_allowed=bool(exchange.get("allowed_exchange")),
            pseudo_pixels=exchange.get("total_pseudo_pixels"),
            negative_class="held-out catalogue-zero proxies, not verified absence",
            receipt="evidence/h72_independence.json")
    surface_summary = surface.get("receipt") if surface else None
    final_summary = final_gate
    build_ok = bool(build and build.get("format", {}).get("ok"))
    holdout_pass = bool(holdout and holdout.get("matched_comparison_valid")
                        and holdout.get("candidate_minus_single_B")
                        and holdout["candidate_minus_single_B"].get("ci95", [None, None])[0] is not None
                        and holdout["candidate_minus_single_B"]["ci95"][0] > 0)
    lane_ok = bool(surface_summary and surface_summary.get("pass_literal")
                   and final_summary and final_summary.get("pass_literal"))
    unique_ok = bool(uniqueness and uniqueness.get("canonical_pattern_unique")
                     and not uniqueness.get("equals_literal_prior_union")
                     and (uniqueness.get("novel_fraction") or 0.0)
                     >= float(th["min_novel_fraction_for_research_release"]))
    not_union_ok = bool(output and output.get("not_union", {}).get("not_union_pass"))
    promote = bool(can_summary and not can_summary["any_alarm"]
                   and exchange_summary and exchange_summary["exchange_allowed"]
                   and holdout_pass and lane_ok and unique_ok and not_union_ok and build_ok)
    verdict = ("promote to the separate selector only; not a competition-slot approval" if promote
               else "negative; no selector/slot decision and no submission made")
    validator = build.get("format") if build else None
    registration = dict(
        hypothesis_document=reg["hypothesis_document"], hypothesis_sha256=reg["hypothesis_sha256"],
        amendment_document=str(AMEND_DOC.relative_to(ROOT)), amendment_sha256=sha256(AMEND_DOC),
        view_A=list(VIEW_A), view_B="shared H61/H71 manifest list, unchanged",
        thresholds=th)
    card = dict(
        round=ROUND, generated_utc=now(), preregistration=registration,
        hypothesis="H72-A: a localized, coherent geodetic strain/shear anomaly in raw_band_04, raw_band_07 and raw_band_08 may indicate a concealed fault where the fixed DEM/surface/radiometric View B abstains.",
        mechanism="Two-view co-training only. Spatial-block OOF predictions; one whole-segment exchange where one view is rank>=0.95 and the other is within [0.35,0.65]; emit only the strict A-confident/B-abstaining stratum, never the union.",
        named_non_fault_mimic="broad interseismic loading, a geodetic survey seam, or a strain-grid interpolation edge; any of these can produce a coherent strain anomaly without a fault.",
        reported_score_context=dict(
            public_board_snapshot=dict(value=0.2778, rank=13, team="extradr19", observed_date="2026-10-07",
                evidence_class="PUBLIC-LEADERBOARD OBSERVATION; team-level only, not a file/hash/upload-receipt mapping",
                source="registry/leaderboard_snapshot_2026-10-07.json",
                live_board_checked_in_H72="No — the page fetch rendered Loading; the snapshot is dated and not current-confirmed"),
            owner_reported_file_score=dict(value=0.2778,
                submission_label="h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros",
                evidence_class="OWNER/USER-REPORTED; NOT ORGANIZER-CONFIRMED",
                receipt=None, authenticated_file_sha256=None,
                source="evidence/ctd5_owner_reported_results.json"),
            local_owner_mirror=dict(file="reference/h33-2-b2-zeros.tif",
                file_sha256="c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9",
                decoded_dot_count=37654, dots_on_known_catalogue=0,
                attribution_class="FILENAME-ONLY-OWNER-REPORTED; token_hash_linked is empty",
                source="evidence/h61_forensics.json; a mirror hash proves byte consistency, not organizer authentication"),
            mechanism_evidence=dict(
                relation="the local H33-labelled bitmap is a strict support subset of the owner-reported 0.2600-labelled 44,090-dot bitmap; 6,436 cells are removed",
                removed_cell_distance_to_known_catalogue_m="100–200 for all 6,436 measured cells",
                interpretation="consistent with precision-oriented pruning under the distance-weighted metric, but not causal proof; hidden-truth credit on those flank cells is unknown",
                source="evidence/h61_forensics.json (subset_pairs and catalogue_rings)"),
            organizer_confirmed_submission_receipt=dict(found=False, value=None, file_sha256=None,
                evidence_class="ORGANIZER-CONFIRMED: none located in the repository; no receipt copied from a submission page")),
        canary=can_summary,
        independence=exchange_summary,
        holdout_dti=hold_sum,
        lane_surface=surface_summary,
        lane_final_dots=final_summary,
        decoded_uniqueness=uniqueness,
        output=output,
        raster=build.get("raster") if build else None,
        validator=validator or dict(status="NOT RUN — no GeoTIFF was written"),
        submission_name=(build or {}).get("submission_name"),
        note=(build or {}).get("note"), note_chars=(build or {}).get("note_chars"),
        eligibility=dict(
            downloadable=bool(build),
            portal_format_valid=(bool(build_ok) if build else None),
            portal_format_status=("VALIDATED" if build_ok else "FAILED" if build else "NOT ASSESSED — no H72 TIFF exists"),
            organizer_confirmed=False,
            approved_for_competition_submission=False,
            reason=("No H72 GeoTIFF was written because the preregistered literal lane gate failed; "
                    "portal-format validation is NOT ASSESSED, and no organizer approval can be claimed." if not build else
                    "A research artifact may be downloadable and locally format-valid, but no upload receipt or organizer approval exists.")),
        experiments_used=state.get("experiments_completed", 0),
        execution_notes=state.get("execution_notes", []),
        registered_experiment_budget=3,
        elapsed_seconds=(float(state["elapsed_seconds"]) if state.get("status") == "negative-stop"
                         and state.get("elapsed_seconds") is not None
                         else round(time.monotonic() - state["monotonic_start"], 1)), 
        submission_slots_used=0,
        selector_decision_made=False,
        stop_reason=stop_reason,
        verdict=verdict,
        verdict_promote_to_selector=promote)
    return _clean(card)


def write_reasoning_and_emission_diagnostics(emission, candidate, mosaics, allowed,
                                             cat_dist_m, store, reg):
    """Save only work/evidence arrays and diagnostics until the literal final-dot gate passes."""
    np.save(WORK / "final_emission_mask.npy", emission.astype(np.uint8))
    report = not_union_report(emission, candidate, mosaics, allowed, reg)
    write_h72("not_union", report)
    reason = write_geological_reasoning(EVID / "h72_a_only_reasoning_candidate.csv", emission,
                                       store, candidate, cat_dist_m)
    write_h72("reasoning", reason)
    return report, reason


def write_no_artifact_card(reg, state, stop_reason, *, canary=None, fit=None,
                           exchange=None, holdout=None, surface=None, final_gate=None,
                           uniqueness=None, output=None):
    card = make_run_card(reg, state, canary=canary, fit=fit, exchange=exchange,
                         holdout=holdout, surface=surface, final_gate=final_gate,
                         uniqueness=uniqueness, output=output, stop_reason=stop_reason)
    write_h72("run_card", card)
    state.update(status="negative-stop", last_stage=state.get("stage"), stage="negative-stop",
                 stopped_utc=now(), stop_reason=stop_reason,
                 elapsed_seconds=round(time.monotonic() - float(state["monotonic_start"]), 1))
    _save_state(state)
    return card


def _save_state(state):
    (WORK / "state.json").write_text(json.dumps(_clean(state), indent=2, allow_nan=False) + "\n")


def _budget_guard(state, stage: str) -> None:
    elapsed = time.monotonic() - float(state["monotonic_start"])
    state["elapsed_seconds"] = round(elapsed, 1)
    if elapsed > MAX_SECONDS:
        state.update(status="budget-expired", stage=stage, stopped_utc=now())
        _save_state(state)
        raise SystemExit(f"H72 two-hour wall-clock budget expired during {stage}; no further stage allowed")


def run_all(resume: bool = False) -> dict:
    reg = check_prereg()
    redirect_shared_runner()
    WORK.mkdir(parents=True, exist_ok=True)
    state_path = WORK / "state.json"
    prereg_hash = sha256(PREREG)
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if not resume:
            raise SystemExit("H72 run already started; use --resume only to continue the same frozen run")
        if state.get("preregistration_sha256") != prereg_hash:
            raise SystemExit("cannot resume: the frozen H72 registration changed")
        if state.get("status") in ("complete", "negative-stop"):
            raise SystemExit(f"H72 run already ended with status {state['status']}; no rerun is permitted")
        mono_start = state.get("monotonic_start", time.monotonic())
    else:
        if resume:
            raise SystemExit("--resume requested but there is no H72 state to resume")
        mono_start = time.monotonic()
        state = dict(round=ROUND, status="running", started_utc=now(),
                     preregistration_sha256=prereg_hash, hypothesis_sha256=reg["hypothesis_sha256"],
                     experiments_completed=0, stage="start", monotonic_start=mono_start)
        _save_state(state)
    if time.monotonic() - mono_start > MAX_SECONDS:
        raise SystemExit("H72 wall-clock budget of two hours has expired")

    _budget_guard(state, "prior inventory setup")
    priors, pmeta = prior_inventory()
    state["prior_inventory"] = pmeta
    state["prior_paths"] = [str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p) for p in priors]
    _save_state(state)
    log(f"H72 pinned registry: {len(priors)} paths; receipt caveat decoded_sha matches="
        f"{pmeta.get('decoded_hash_matches')}")

    # E1: leakage canary then the two shared view fits. Canary is itself diagnostic fitting; an alarm
    # is a stop before trusting or building the full view predictions.
    canary_path = EVID / "h72_canary.json"
    if not canary_path.is_file():
        state["stage"] = "E1-canary"
        _save_state(state)
        canary = shared.stage_canary()
        _budget_guard(state, "E1 leakage canary")
        state["canary_complete"] = True
        _save_state(state)
    else:
        canary = json.loads(canary_path.read_text())
    if canary.get("any_alarm"):
        state["experiments_completed"] = 1
        card = write_no_artifact_card(reg, state,
            "LEAKAGE-CANARY AUC exceeded 0.90; treated as leakage and stopped before full view fits.",
            canary=canary)
        return card
    fit_path = EVID / "h72_fit_checkpoint.json"
    if not fit_path.is_file():
        state["stage"] = "E1-view-fits"
        _save_state(state)
        fit = shared.stage_fit()
        _budget_guard(state, "E1 shared view fits")
    else:
        fit = json.loads(fit_path.read_text())
    state["experiments_completed"] = 1
    state["stage"] = "E1-complete"
    _save_state(state)
    log("E1 complete: shared H72 view fits saved")

    # E2: shared spatial-block error independence and at most one whole-segment exchange/refit.
    exchange_path = EVID / "h72_pseudo_exchange.json"
    if not exchange_path.is_file():
        state["stage"] = "E2-independence-exchange"
        _save_state(state)
        exchange = shared.stage_exchange()
        _budget_guard(state, "E2 independence/exchange")
    else:
        exchange = json.loads(exchange_path.read_text())
    if not exchange.get("allowed_exchange", False):
        state["experiments_completed"] = 2
        card = write_no_artifact_card(reg, state,
            "Spatial-block OOF negative-error correlation exceeded 0.60 or had insufficient blocks; co-training exchange abandoned, no holdout or file.",
            canary=canary, fit=fit, exchange=exchange)
        return card
    # E2 hide-and-recover uses the shared evaluator and fixed preregistered matched budgets.
    holdout_path = EVID / "h72_holdout.json"
    if not holdout_path.is_file():
        state["stage"] = "E2-hide-and-recover"
        _save_state(state)
        holdout = matched_hide_and_recover(reg)
        _budget_guard(state, "E2 hide-and-recover")
    else:
        holdout = json.loads(holdout_path.read_text())
    state["experiments_completed"] = 2
    state["stage"] = "E2-complete"
    _save_state(state)
    log("E2 complete: hide-and-recover receipt saved")

    # E3 pre-placement surface uniqueness is evaluated against every accessible prior.
    _reg, store, cat, eligible, folds, _va, _vb, _ring = shared.setup()
    mosaics = build_oof_mosaics(store, eligible, folds)
    allowed, cat_dist_m = _full_domain(store, eligible, cat, float(reg["thresholds"]["catalogue_exclusion_m"]))
    state["stage"] = "E3-pre-placement-surface-gate"
    _save_state(state)
    surface_gate = surface_lane_gate(mosaics, allowed, priors, reg)
    _budget_guard(state, "E3 pre-placement surface lane gate")
    surface_receipt = surface_gate["receipt"]
    if not surface_receipt["pass_literal"]:
        state["experiments_completed"] = 3
        card = write_no_artifact_card(reg, state,
            "Pre-placement literal surface lane gate failed (rank >0.90, incomplete registry audit, or shared gate error); stopped before any final placement.",
            canary=canary, fit=fit, exchange=exchange, holdout=holdout, surface=surface_gate)
        return card

    candidate = surface_gate["candidate"]
    place_field = np.where(candidate["stratum"], candidate["rank_A"], -np.inf).astype(np.float32)
    target = int(reg["thresholds"]["final_output_dots_total"])
    min_px = float(reg["thresholds"]["minimum_dot_separation_px"])
    emission = nodes.spacing_select(place_field, candidate["stratum"], target, min_px=min_px)
    placed = int(emission.sum())
    placement_receipt = dict(
        target_dots=target, placed_dots=placed, filled=placed == target,
        domain="strict A-only OOF stratum, full-grid sample footprint, outside 200 m from the full visible catalogue",
        method="gems52.nodes.spacing_select", minimum_separation_px=min_px,
        no_fallback=True, budget_amendment=str(AMEND_DOC.relative_to(ROOT)),
        evidence_class="placement diagnostic, not a score")
    if placed == 0:
        state["experiments_completed"] = 3
        card = write_no_artifact_card(reg, state,
            "Final A-only stratum yielded no pixels at the fixed placement gate; no TIFF written.",
            canary=canary, fit=fit, exchange=exchange, holdout=holdout,
            surface=surface_gate, output=dict(placement=placement_receipt))
        return card
    output = dict(placement=placement_receipt)
    not_union, reasoning = write_reasoning_and_emission_diagnostics(
        emission, candidate, mosaics, allowed, cat_dist_m, store, reg)
    output["not_union"] = not_union
    output["reasoning"] = reasoning
    dots = emission.astype(np.float32)
    final_lane = gates.lane_report(dots, eligible, priors, sample=SAMPLE,
                                   phase="dots", log=log)
    _budget_guard(state, "E3 final-dot lane gate")
    write_h72("lane_dots", final_lane)
    literal = final_lane["literal"]
    final_pass = bool(
        literal.get("verdict") == "PASS"
        and final_lane.get("error_count", 0) == 0
        and final_lane.get("priors_checked", 0) == len(priors)
        and literal.get("max_spearman") is not None
        and literal["max_spearman"] <= float(reg["thresholds"]["lane_spearman_stop"])
        and literal.get("max_near_3px_fraction") is not None
        and literal["max_near_3px_fraction"] <= float(reg["thresholds"]["lane_near_dot_fraction_stop"]))
    lane_rows = final_lane.get("per_prior", [])
    max_rank_row = max((r for r in lane_rows if r.get("spearman") is not None),
                       key=lambda r: r["spearman"], default=None)
    literal_near_row = next((r for r in lane_rows
                             if r.get("path") == literal.get("max_near_source")), None)
    policy_near_source = final_lane["policy"].get("max_near_source")
    policy_near_row = next((r for r in lane_rows if r.get("path") == policy_near_source), None)
    final_gate = dict(
        pass_literal=final_pass, literal_verdict=literal.get("verdict"),
        policy_verdict=final_lane["policy"].get("verdict"),
        max_spearman=literal.get("max_spearman"),
        max_spearman_source=(prior_source_metadata(max_rank_row["path"]) if max_rank_row else None),
        max_near_3px_fraction=literal.get("max_near_3px_fraction"),
        max_near_source=literal.get("max_near_source"),
        max_near_source_details=(dict(prior_source_metadata(literal_near_row["path"]),
                                      prior_proposals=literal_near_row.get("prior_proposals"),
                                      coverage_3px_of_eligible=literal_near_row.get("coverage_3px_of_eligible"),
                                      universal_coverage_probe=literal_near_row.get("universal_coverage_probe"),
                                      near_3px_fraction=literal_near_row.get("near_3px_fraction"))
                                 if literal_near_row else None),
        policy_max_near_3px_fraction=final_lane["policy"].get("max_near_3px_fraction"),
        policy_max_near_source_details=(dict(prior_source_metadata(policy_near_row["path"]),
                                             coverage_3px_of_eligible=policy_near_row.get("coverage_3px_of_eligible"),
                                             near_3px_fraction=policy_near_row.get("near_3px_fraction"))
                                        if policy_near_row else None),
        near_stop=float(reg["thresholds"]["lane_near_dot_fraction_stop"]),
        radius_px=float(reg["thresholds"]["lane_near_dot_radius_px"]),
        priors_checked=final_lane.get("priors_checked"), expected_priors=len(priors),
        error_count=final_lane.get("error_count"),
        evidence_class="uniqueness/lane diagnostic, not a score")
    output["final_lane"] = final_gate
    if not final_pass:
        # The in-memory candidate is not written as a TIFF. Check decoded support uniqueness using
        # the same shared gates, then stop; literal saturation-aware policy does not waive the rule.
        uniqueness = gates.uniqueness_report(dots, priors, top=None)
        uniqueness_summary = {k: uniqueness.get(k) for k in (
            "n_priors_checked", "canonical_pattern_unique", "equals_literal_prior_union",
            "novel_fraction", "support_novelty_gate_ok", "relation_to_union", "ok", "scope")}
        write_h72("uniqueness", uniqueness_summary)
        state["experiments_completed"] = 3
        card = write_no_artifact_card(reg, state,
            "Final-dot literal lane gate failed; candidate was not written or published. Literal STOP takes precedence over any saturation-aware policy PASS.",
            canary=canary, fit=fit, exchange=exchange, holdout=holdout,
            surface=surface_gate, final_gate=final_gate, uniqueness=uniqueness_summary,
            output=output)
        return card

    # A TIFF is written only if the literal surface and final-dot lane gates both pass.
    if not placement_receipt["filled"]:
        state["experiments_completed"] = 3
        card = write_no_artifact_card(reg, state,
            "Fixed 5,056-dot target underfilled by the shared spacing selector; no fallback or TIFF written.",
            canary=canary, fit=fit, exchange=exchange, holdout=holdout,
            surface=surface_gate, final_gate=final_gate, output=output)
        return card
    if not not_union.get("not_union_pass"):
        state["experiments_completed"] = 3
        card = write_no_artifact_card(reg, state,
            "Not-the-union check failed; no TIFF written.", canary=canary, fit=fit,
            exchange=exchange, holdout=holdout, surface=surface_gate,
            final_gate=final_gate, output=output)
        return card

    uniqueness = gates.uniqueness_report(dots, priors, top=None)
    uniqueness_summary = {k: uniqueness.get(k) for k in (
        "n_priors_checked", "canonical_pattern_unique", "equals_literal_prior_union",
        "novel_fraction", "support_novelty_gate_ok", "relation_to_union", "ok", "scope")}
    write_h72("uniqueness", uniqueness_summary)
    if (not uniqueness_summary.get("canonical_pattern_unique")
            or uniqueness_summary.get("equals_literal_prior_union")
            or (uniqueness_summary.get("novel_fraction") or 0.0)
            < float(reg["thresholds"]["min_novel_fraction_for_research_release"])):
        state["experiments_completed"] = 3
        card = write_no_artifact_card(reg, state,
            "Decoded-pattern uniqueness or preregistered 20% support-novelty gate failed; no TIFF written.", canary=canary,
            fit=fit, exchange=exchange, holdout=holdout, surface=surface_gate,
            final_gate=final_gate, uniqueness=uniqueness_summary, output=output)
        return card

    # Include a fresh run stamp and the deterministic candidate digest in the one allowed name.
    decoded_hash = hashlib.sha256(dots.astype("<f4").tobytes()).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"gems52-h72-strain-aonly-5056px-{stamp}-{decoded_hash[:8]}"
    name = stem
    note = "H72 strain-only A-only; fixed hide-and-recover; research only; not approved for a competition slot"
    if len(note) > 140:
        raise SystemExit("H72 fixed submission note exceeds the 140-character limit")
    SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target_tif = SUBMISSION_DIR / f"{stem}.tif"
    receipt = write_submission(
        target_tif, dots, SAMPLE, eligible,
        note=note, name=name,
        metadata=dict(round=ROUND, evidence_class="research-only local candidate; no organizer receipt",
                      hypothesis_sha256=reg["hypothesis_sha256"],
                      holdout_evidence=holdout.get("pooled", {}).get("scores", {}).get("a_only"),
                      lane_literal="PASS", selector_decision_made=False))
    # Public site filenames stay stable; the downloadable payload remains byte-identical to the
    # uniquely named submission file and is counted as a self-copy by the audit, not a prior.
    download_tif = DOWNLOAD_DIR / "h72-candidate.tif"
    download_zip = DOWNLOAD_DIR / "h72-candidate.zip"
    shutil.copy2(target_tif, download_tif)
    shutil.copy2(target_tif.with_suffix(".zip"), download_zip)
    output_receipt = dict(
        file=str(target_tif.relative_to(ROOT)), download_tif=str(download_tif.relative_to(ROOT)),
        download_zip=str(download_zip.relative_to(ROOT)), sha256=receipt["sha256"],
        bytes=receipt["bytes"], zip_sha256=receipt["zip_sha256"],
        emitted_cells=placed, submission_name=name, note=note, note_chars=len(note),
        approved_for_weekly_slot=False, promoted=False, submission_slots_used=0)
    fmt = receipt["validator"]
    build = dict(raster=output_receipt, format=fmt, submission_name=name, note=note,
                 note_chars=len(note), not_union=not_union, reasoning=reasoning)
    write_h72("build", dict(build=build, receipt=receipt))
    # Cross-check on-disk copy bytes and the ZIP round-trip before the census audit.
    if sha256(target_tif) != sha256(download_tif) or sha256(target_tif.with_suffix(".zip")) != sha256(download_zip):
        raise SystemExit("H72 public download copy hash mismatch")
    state["experiments_completed"] = 3
    state["stage"] = "E3-built"
    _save_state(state)

    # Shared full-registry uniqueness audit: format/local-download status is not organizer approval.
    audit_path = EVID / "h72_audit_uniqueness.json"
    command = [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/audit_uniqueness.py"),
               str(target_tif.relative_to(ROOT)), str(audit_path.relative_to(ROOT)), str(CENSUS.relative_to(ROOT))]
    proc = __import__("subprocess").run(command, cwd=ROOT, capture_output=True, text=True)
    log(proc.stdout[-2500:])
    if proc.returncode != 0:
        log(proc.stderr[-2500:])
        raise SystemExit("shared audit_uniqueness.py failed")
    audit = json.loads(audit_path.read_text())
    write_h72("audit_uniqueness", audit)
    # Both independent shared gates must agree on decoded uniqueness and the required literal rule.
    audit_lane = audit.get("lane_policy_dots", {}).get("literal", {})
    final_gate["audit_literal_verdict"] = audit_lane.get("verdict")
    final_gate["audit_literal_max_near_3px_fraction"] = audit_lane.get("max_near_3px_fraction")
    final_gate["audit_surface_max_spearman"] = audit.get("phases", {}).get("surface", {}).get("max_spearman")
    final_gate["audit_dots_max_near_3px_fraction"] = audit.get("phases", {}).get("dots", {}).get("max_near_3px_fraction")
    final_gate["audit_priors_after_byte_dedupe"] = audit.get("priors_after_byte_dedupe")
    final_gate["pass_literal"] = bool(final_gate["pass_literal"]
        and audit_lane.get("verdict") == "PASS"
        and audit.get("phases", {}).get("dots", {}).get("ok"))
    build["audit"] = dict(candidate_file_sha256=audit.get("candidate_file_sha256"),
                          priors_after_byte_dedupe=audit.get("priors_after_byte_dedupe"),
                          max_jaccard=audit.get("max_jaccard"),
                          share_inside_any_prior=audit.get("share_of_candidate_px_inside_any_prior_support"),
                          literal_lane= audit_lane.get("verdict"))
    card = make_run_card(reg, state, canary=canary, fit=fit, exchange=exchange,
                         surface=surface_gate, holdout=holdout, final_gate=final_gate,
                         uniqueness=uniqueness_summary, output=output, build=build)
    write_h72("run_card", card)
    state.update(status="complete", finished_utc=now(), stage="complete")
    _save_state(state)
    return card


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true", help="continue this exact frozen H72 run without repeating completed stages")
    args = parser.parse_args()
    t0 = time.monotonic()
    card = run_all(resume=args.resume)
    log(json.dumps({"verdict": card.get("verdict"), "stop_reason": card.get("stop_reason"),
                    "elapsed_seconds": card.get("elapsed_seconds"),
                    "eligibility": card.get("eligibility")}, indent=2))
    if time.monotonic() - t0 > MAX_SECONDS:
        log("WARNING: process exceeded its local timing limit; the preregistered budget was recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
